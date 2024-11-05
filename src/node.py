from flask import Flask, jsonify, request
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys
import json
import time
from raft_node import RaftNode
from threading import Thread
from log import Log

FOLLOWER = "Follower"
LEADER = "Leader"
CANDIDATE = "Candidate"

PUT_TOPIC_FLAG = 1
PUT_MESSAGE_FLAG = 2
GET_TOPIC_FLAG = -1
GET_MESSAGE_FLAG = -2

CLIENT_REQUEST_TIMEOUT = 1

# Set up before request
raft_node = RaftNode()
internal_app = Flask("internal_app")
external_app = Flask("external_app")


def wait_for_commit(log_index, timeout):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if raft_node.commit_index >= log_index:
            return True
        time.sleep(0.1)
    return False


def add_log_entry(term, topic, message="", flag=None):
    this_index = len(raft_node.logs)
    raft_node.logs.append(Log(term, topic, message, flag))
    raft_node.match_index[raft_node.id] = this_index
    return this_index


# Topic APIs
# Put a topic
@external_app.route('/topic', methods=['PUT'])
def create_topic():
    if raft_node.role != LEADER:
        return jsonify(success=False), 400
    topic = request.json.get('topic')
    if topic and topic not in raft_node.state_machine:
        log_index = add_log_entry(raft_node.current_term, topic, flag=PUT_TOPIC_FLAG)
        if len(raft_node.config['addresses']) == 1 or await_commit_confirmation(log_index):
            raft_node.apply_to_state_machine(log_index)
            return jsonify(success=True)
        else:
            return jsonify(success=False), 408
    else:
        return jsonify(success=False), 400


# Return all the topics in a list
@external_app.route('/topic', methods=['GET'])
def get_topics():
    return jsonify(success=True, topics=list(raft_node.state_machine.keys()))


# Message APIs
# Put a message
@external_app.route('/message', methods=['PUT'])
def put_message():
    if raft_node.role != LEADER:
        return jsonify(success=False), 400
    topic, message = request.json.get('topic'), request.json.get('message')
    if topic in raft_node.state_machine:
        log_index = add_log_entry(raft_node.current_term, topic, message, PUT_MESSAGE_FLAG)
        if len(raft_node.config['addresses']) == 1 or await_commit_confirmation(log_index):
            raft_node.apply_to_state_machine(log_index)
            return jsonify(success=True)
        else:
            return jsonify(success=False), 408
    else:
        return jsonify(success=False), 404


def await_commit_confirmation(log_index):
    """    
    active_nodes = sum(1 for count in raft_node.heartbeat_received.values() if count > 0)
    majority_needed = len(raft_node.config['addresses']) // 2 + 1

    if active_nodes < majority_needed:
        # Immediately return False if not enough active nodes for majority
        return False
    


    with ThreadPoolExecutor() as executor:
        future = executor.submit(wait_for_commit, log_index, CLIENT_REQUEST_TIMEOUT)
        return future.result()
    """
    with ThreadPoolExecutor() as executor:
        future = executor.submit(wait_for_commit, log_index, CLIENT_REQUEST_TIMEOUT)
        return future.result()

# Get a message
@external_app.route('/message/<topic>', methods=['GET'])
def get_message(topic):

    if raft_node.role != LEADER:
        return jsonify(success=False), 400

    
    if topic not in raft_node.state_machine or raft_node.state_machine[topic] == []:
        return jsonify(success=False)
    else:
        this_index = len(raft_node.logs)
        message = raft_node.state_machine[topic][0]
        raft_node.logs.append(Log(raft_node.current_term, topic, "", GET_MESSAGE_FLAG))
        raft_node.match_index[raft_node.id] = this_index
        # case 1: only 1 node in swarm, no need to wait majority consent
        if len(raft_node.config['addresses']) == 1:
            raft_node.apply_to_state_machine(this_index)
            return jsonify(success=True, message=message)
        # case 2: > 1 node in swarm, wait until success
        with ThreadPoolExecutor() as executor:
            future = executor.submit(wait_for_commit, this_index, CLIENT_REQUEST_TIMEOUT)
            success = future.result()
        if success:
            # print(str(raft_node.id) + " state_machine" + str(raft_node.state_machine))
            # raft_node.apply_to_state_machine(this_index)
            return jsonify(success=True, message=message)
        else:
            return jsonify(success=False), 408


# Status API
@external_app.route('/status', methods=['GET'])
def get_status():
    return jsonify(role=raft_node.role, term=raft_node.current_term)


# Request Vote RPC, logic to respond a vote request
# If term < candidate's term, update term to same as candidate
# Situation that will lead to NOT VOTE
# already voted at this term
# self.term is > candidate's term
# self log is more up to date (last log term > candidate's or last log index > candidate's)
# NOTE I DO NOT CHECK LOG FOR NOW BECAUSE I HAVE NOT IMPLEMENT REPLICATE LOG
# If grant vote, reset the election timeout
@internal_app.route('/request_vote', methods=['POST'])
def request_vote():
    data = request.json
    print(" node " + str(raft_node.id) + " received " + str(data))
    candidate_term = data['term']
    candidate_id = data['candidateId']
    last_log_index = data['lastLogIndex']
    last_log_term = data['lastLogTerm']

    # Add logic to compare logs in future
    if raft_node.last_voted_term >= candidate_term or raft_node.current_term > candidate_term:
        print(str(raft_node.id) + " do not grant vote to " + str(candidate_id))
        return jsonify(term=raft_node.current_term, voteGranted=False)
    else:
        raft_node.restart_election_timer()
        print(str(raft_node.id) + " grant vote to " + str(candidate_id))
        return jsonify(term=raft_node.current_term, voteGranted=True)


# Logic respond to append entries RPC
# Reset the election timeout
# Update term
# Change back to follower
@internal_app.route('/append_entries', methods=['POST'])
def append_entries():
    data = request.json
    leader_id = data["leaderId"]

    raft_node.from_candidate_to_follower()
    # raft_node.restart_election_timer()
    # make the node's log same as leader's log
    raft_node.logs = [Log.from_dict(entry) for entry in data["entries"]]
    # print("node " + str(raft_node.id) + "received APE from " + str(leader_id) + " logs: " + str(raft_node.logs))
    # commit to same stage as leader does
    # if leader_commit > my_last_commit, then commit these logs
    if data["leaderCommit"] > raft_node.commit_index:
        raft_node.follower_commit(data["leaderCommit"])
    return jsonify(term=raft_node.current_term, success=True)


def run_internal():
    internal_app.run(debug=False, port=internal_port)


def run_external():
    external_app.run(debug=False, port=port)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python3 src/node.py config.json <index_of_node>")
        exit(1)

    config_path = sys.argv[1]
    index_of_node = int(sys.argv[2])

    with open(config_path, 'r') as config_file:
        config_data = json.load(config_file)

    raft_node.id = index_of_node
    port = config_data['addresses'][index_of_node]['port']
    internal_port = config_data['addresses'][index_of_node]['internal_port']
    raft_node.port = port
    raft_node.internal_port = internal_port

    t1 = Thread(target=run_internal)
    t2 = Thread(target=run_external)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
