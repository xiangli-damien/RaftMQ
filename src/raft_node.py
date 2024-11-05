import random
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread, Event
from threading import Lock
from log import Log

import requests

CONFIG_PATH = "../config.json"

FOLLOWER = "Follower"
LEADER = "Leader"
CANDIDATE = "Candidate"

PUT_TOPIC_FLAG = 1
PUT_MESSAGE_FLAG = 2
GET_TOPIC_FLAG = -1
GET_MESSAGE_FLAG = -2

MIN_ELECTION_TIMEOUT = 0.15
MAX_ELECTION_TIMEOUT = 0.3
HEARTBEAT_INTERVAL = 0.02


def get_randomized_election_timeout():
    return random.uniform(MIN_ELECTION_TIMEOUT, MAX_ELECTION_TIMEOUT)


def send_request_vote(server, data):
    # print(f'http://{server["ip"]}:{server["internal_port"]}/request_vote')
    try:
        # print(server)
        # print("server type: " + str(type(server)))
        response = requests.post(f'http://{server["ip"]}:{server["internal_port"]}/request_vote', json=data)
        print("response = " + str(response))
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        return None


def send_append_entries(server, data):
    try:
        response = requests.post(f'http://{server["ip"]}:{server["internal_port"]}/append_entries', json=data)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        return None


class RaftNode:
    def __init__(self):
        # Configure information

        self.id = -1
        self.port = -1
        self.internal_port = -1

        self.current_term = 0
        self.logs = []
        self.state_machine = {}
        self.role = FOLLOWER
        # Vote information
        self.vote_count = 0
        self.state_lock = Lock()
        # Leader related
        self.heartbeat_thread = None
        # change according to need
        self.last_voted_term = -1
        self.commit_index = -1
        self.last_applied = 0
        self.next_index = {}
        # the match_index[1] = 7 means: the server with id = 1 have log0 to log7 same as leader
        self.match_index = []

        # Timer used to track the election timeout
        self.timer_generation = 0
        self.election_timeout_event = Event()
        self.start_election_timer()
        self.election_timeout_thread = None

        with open("../config.json", 'r') as config_file:
            self.config = json.load(config_file)

    # Timer handling methods
    def start_election_timer(self):
        current_generation = self.timer_generation
        self.election_timeout_thread = Thread(target=self.handle_election_timeout, args=(current_generation,))
        self.election_timeout_thread.daemon = True
        self.election_timeout_thread.start()

    def handle_election_timeout(self, my_generation):
        time_duration = get_randomized_election_timeout()
        election_timeout_occurred = not self.election_timeout_event.wait(time_duration)
        if election_timeout_occurred and self.role is not LEADER and my_generation == self.timer_generation:
            print("node" + str(self.id) + "changed to candidate")
            # Election timed out and change to candidate
            self.from_follower_to_candidate()

    def restart_election_timer(self):
        self.timer_generation += 1
        self.election_timeout_event.clear()
        self.start_election_timer()

    def from_follower_to_candidate(self):
        # Increase current term
        # Change to candidate
        # Vote for itself (May then be leader if there's only one node)
        # Update last_voted_term
        # Issue Request Vote RPC in parallel to others
        # Reset election timeout
        self.current_term += 1
        self.role = CANDIDATE
        self.vote_count += 1
        self.last_voted_term = self.current_term
        garbage = -1

        # Address the case with single node
        if len(self.config['addresses']) == 1:
            self.from_candidate_to_leader()
            return

        data = {
            "term": self.current_term,
            "candidateId": self.id,
            "lastLogIndex": garbage,
            "lastLogTerm": garbage
        }

        # Send request Vote in parallel
        # with ThreadPoolExecutor() as executor:
        with ThreadPoolExecutor() as executor:
            futures = []
            for server in self.config['addresses']:
                if server["internal_port"] != self.internal_port:
                    futures.append(executor.submit(send_request_vote, server, data))

            for future in as_completed(futures):
                result = future.result()
                print("node " + str(self.id) + " result = " + str(result))
                if result and result.get('term') > self.current_term:
                    self.current_term = result.get('term')
                    self.from_candidate_to_follower()
                    break
                if result and result.get('voteGranted') and self.role == CANDIDATE:
                    with self.state_lock:
                        self.vote_count += 1
                        if self.vote_count > len(self.config['addresses']) / 2:
                            self.from_candidate_to_leader()  # Transition to leader if majority votes received
                            break

        self.restart_election_timer()

    # Send append entries RPC to all others so that it can be recognized
    # Clear all votes received
    def from_candidate_to_leader(self):
        print(str(self.id) + " CHANGED TO LEADER")
        print(str(self.id) + " logs: " + str(self.logs))
        # with self.state_lock:
        self.role = LEADER
        self.vote_count = 0
        # assume each follower has no match index(?)
        self.match_index = len(self.config['addresses']) * [-1]
        self.match_index[self.id] = len(self.logs) - 1
        # Send append entries RPC to all others so that it can be recognized
        print(str(self.id) + " READY TO START HEARTBEAT")
        self.heartbeat_thread = Thread(target=self.start_heartbeat_loop)
        self.heartbeat_thread.start()

    def send_heartbeat(self):

        current_log_index = len(self.logs) - 1
        serialized_logs = [log.to_dict() for log in self.logs]
        data = {
            "term": self.current_term,
            "leaderId": self.id,
            "entries": serialized_logs,
            "leaderCommit": self.commit_index,
        }

        with ThreadPoolExecutor() as executor:
            futures_to_server = {
                executor.submit(send_append_entries, server, data): index
                for index, server in enumerate(self.config['addresses'])
                if server["internal_port"] != self.internal_port  # Ensuring not to send heartbeat to itself
            }

            for future in as_completed(futures_to_server):
                server_index = futures_to_server[future]
                try:
                    result = future.result()
                    if result and result.get('success'):
                        # The follower successfully appended the entry, update match_index accordingly
                        with self.state_lock:  # Assuming you're using a lock to protect shared state
                            self.match_index[server_index] = max(self.match_index[server_index], current_log_index)
                        # try to find if new commit can be made
                        self.leader_try_to_commit()
                except Exception as e:
                    # Handle cases where send_append_entries raises an exception or future.result() fails
                    print(f"Error sending heartbeat to server {server_index}: {e}")
        

    def start_heartbeat_loop(self):
        print("node " + str(self.id) + "started heart_beat_loop")
        while self.role == LEADER:
            self.send_heartbeat()
            time.sleep(HEARTBEAT_INTERVAL)

    # Called when receive append entries RPC
    # Clear all votes received
    # Reset the election timeout
    def from_candidate_to_follower(self):
        self.role = FOLLOWER
        self.vote_count = 0
        self.restart_election_timer()

    def from_leader_to_follower(self):
        self.role = FOLLOWER
        self.heartbeat_thread.join()

    # apply log at index-index to state machine
    def apply_to_state_machine(self, index):
        if self.logs[index].operation == PUT_TOPIC_FLAG:
            self.state_machine[self.logs[index].topic] = []
            # suppose get topic will simply return a list, not deleting them
        elif self.logs[index].operation == PUT_MESSAGE_FLAG:
            print(str(self.id) + "before insert message: "+str(self.state_machine))
            self.state_machine[self.logs[index].topic].append(self.logs[index].message)
            print(str(self.id) + "after insert message: " + str(self.state_machine))
        elif self.logs[index].operation == GET_MESSAGE_FLAG:
            self.state_machine[self.logs[index].topic].pop(0)


    # try to find all commits that can be committed
    def leader_try_to_commit(self):
        # Calculate the majority needed to commit a log entry
        majority = len(self.match_index) // 2 + 1
        # Iterate over the log entries that have not yet been committed
        for index in range(self.commit_index + 1, len(self.logs)):
            # Count how many followers have replicated the log up to this index
            count_replicated = sum(num >= index for num in self.match_index)
            # If the log entry at this index has been replicated on a majority of servers
            if count_replicated >= majority:
                # Commit this log entry and all prior uncommitted entries
                for commit_index in range(self.commit_index + 1, index + 1):
                    self.apply_to_state_machine(commit_index)
                # Update the commit_index to the latest index that was committed
                self.commit_index = index

    def follower_commit(self, leader_commit):
        last_log_index = len(self.logs) - 1  # Adjust for 0-based indexing
        new_commit_index = min(leader_commit, last_log_index)
        # Update commit_index if leader_commit is ahead of the follower's commit_index
        if new_commit_index > self.commit_index:
            for index in range(self.commit_index + 1, new_commit_index + 1):
                # Apply each newly committed log entry to the state machine
                self.apply_to_state_machine(index)
            # Update the follower's commit_index to reflect the new commit level
            self.commit_index = new_commit_index


