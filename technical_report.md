# RRMQ Technical Report

## 1. Introduction

This report delves into the implementation specifics of the Raft consensus algorithm within the Raft REST Message Queue (RRMQ) project. Emphasizing the core aspects of leader election, log replication, and fault tolerance, we detail how these components collectively ensure a consistent, distributed state across nodes in the system.

## 2. Structure

The implementation is divided into three primary Python files:

- `raft_node.py`: Contains the `RaftNode` class, implementing the core Raft protocol, including leader election, log replication, and maintaining the node's state. The nodes maintained several important variables shown below:

  - | Variable                                                     | Description                                                  |
    | ------------------------------------------------------------ | ------------------------------------------------------------ |
    | `id`, `port`, `internal_port`                                | Identifiers and communication endpoints.                     |
    | `current_term`                                               | The node's current term in the election.                     |
    | `logs`                                                       | Log entries for replication.                                 |
    | `state_machine`                                              | The application state managed by the cluster.                |
    | `role`                                                       | Node's role: Follower, Leader, or Candidate.                 |
    | `vote_count`                                                 | Votes received in the current election.                      |
    | `state_lock`                                                 | Synchronizes access to shared resources.                     |
    | `heartbeat_thread`                                           | Sends heartbeats to other nodes as the leader.               |
    | `last_voted_term`, `commit_index`, `last_applied`            | Voting history, highest committed log entry, and highest applied log entry. |
    | `next_index`, `match_index`                                  | Tracks log replication progress on followers.                |
    | `heartbeat_received`                                         | Tracks heartbeats from each node.                            |
    | `timer_generation`, `election_timeout_event`, `election_timeout_thread` | Manages the election timeout mechanism.                      |

- `node.py`: Utilizes Flask to create RESTful APIs for external and internal communication, handling client requests and inter-node communication.

  - `internal_app` for internal communications within the Raft cluster, such as leader elections and log replication
  - `external_app` for external interactions, handling client requests to the raft swam. 

- `log.py`: Defines the `Log` class, representing the log entries that are replicated across nodes to ensure consistency.

  - 
    The `Log` class maintains the following variables:

    | Variable    | Description                                                |
    | ----------- | ---------------------------------------------------------- |
    | `term`      | The term number in which the log entry was created.        |
    | `topic`     | The topic associated with the log entry.                   |
    | `message`   | The message content of the log entry.                      |
    | `operation` | The operation type, indicating the action to be performed. |

    Operations include:

    - `PUT_TOPIC_FLAG` (+1) for adding a new topic.
    - `PUT_MESSAGE_FLAG` (+2) for adding a new message to a topic.
    - `GET_TOPIC_FLAG` (-1) for retrieving topics (not explicitly used in the provided `Log` class).
    - `GET_MESSAGE_FLAG` (-2) for consuming a message from a topic.



## 3. Part1 Message Queue Implementation

- ### Topic

  #### PUT Topic

  - **Process Flow**:
    - Checks if the current node is the leader. If not, returns an error (HTTP 400).
    - Validates if the topic exists. If it does or no topic is provided, returns an error (HTTP 400).
    - If the topic is new, it adds a log entry with the `PUT_TOPIC_FLAG`.
    - Waits for the log entry to be committed to the state machine.
      - If successful, applies the log to the state machine and returns success.
      - If not successful within a certain timeout, returns an error (HTTP 408).
  - **Involved Methods and Logic**:
    - `create_topic()`: Main function to handle PUT topic requests.
    - `add_log_entry(term, topic, message="", flag=None)`: Adds a new log entry for the topic.
    - `await_commit_confirmation(log_index)`: Waits for the commit confirmation of the log entry.

  #### GET Topic

  - **Process Flow**:
    - Returns a list of all topics stored in the state machine.
  - **Involved Methods and Logic**:
    - `get_topics()`: Main function to handle GET topic requests.

  ### Message

  #### PUT Message

  - **Process Flow**:
    - Checks if the current node is the leader. If not, returns an error (HTTP 400).
    - Validates if the topic exists. If not, returns an error (HTTP 404).
    - If the topic exists, adds a log entry with the `PUT_MESSAGE_FLAG` and the message.
    - Waits for the log entry to be committed to the state machine.
      - If successful, applies the log to the state machine and returns success.
      - If not successful within a certain timeout, returns an error (HTTP 408).
  - **Involved Methods and Logic**:
    - `put_message()`: Main function to handle PUT message requests.
    - Uses `add_log_entry` and `await_commit_confirmation` similar to PUT Topic.

  #### GET Message

  - **Process Flow**:
    - Checks if the current node is the leader. If not, returns an error (HTTP 400).
    - Validates if the topic exists and has messages. If not, returns an error.
    - Adds a log entry with the `GET_MESSAGE_FLAG`.
    - Waits for the log entry to be committed to the state machine.
      - If successful, retrieves the first message from the state machine for the topic and returns it.
      - If not successful within a certain timeout, returns an error (HTTP 408).
  - **Involved Methods and Logic**:
    - `get_message(topic)`: Main function to handle GET message requests.
    - Uses similar auxiliary functions as PUT operations..

  ### Status

  - **Process Flow**:
    - Returns the current role (`Follower`, `Leader`, `Candidate`) and term of the node.
  - **Involved Methods and Logic**:
    - `get_status()`: Main function to provide the status of the node.
  - **Variables and Execution Content**:
    - `raft_node.role`, `raft_node.current_term`: The current role and term of the node.

  ### Auxiliary Functions

  ###### `await_commit_confirmation(log_index)`

  - **Purpose**: Waits for a log entry at a specified index to be committed to the state machine.
  - **Logic**: Executes `wait_for_commit` within a ThreadPoolExecutor to check if the `commit_index` is greater than or equal to the `log_index` within a timeout.

  ###### `add_log_entry(term, topic, message="", flag=None)`

  - **Purpose**: Adds a new log entry for either a topic or message operation



## 4. Part2 Leader Election Implementation

- To detail the leader election logic in the provided code, focusing on the transitions between follower, candidate, and follower roles, including function design, variable comparisons, and special case handling:
  1. **Initial State (Follower)**: Each node begins as a follower with a randomized election timeout (`get_randomized_election_timeout()`).
  2. **Election Timeout**: If a follower doesn't hear from a leader within its timeout, it transitions to a candidate (`from_follower_to_candidate()`), increments its `current_term`, votes for itself, and resets its election timeout.
  3. **Requesting Votes**: As a candidate, it sends `request_vote` messages to all nodes (`send_request_vote()`), including its `current_term` and last log index/term for log integrity comparison.
  4. **Vote Collection**:
     - Nodes respond to vote requests based on several conditions: not having voted in the current term, the candidate's log being at least as up-to-date as the responder’s log.
     - If receiving a vote request with a higher term, a node updates its term and reverts to follower status.
  5. **Majority Votes**: If a candidate receives a majority, it transitions to a leader (`from_candidate_to_leader()`), begins sending heartbeats (`send_heartbeat()`), and manages log replication.
  6. **Split Vote**: If multiple candidates vie for votes, leading to no majority, nodes reset their election timeout. The process repeats until a single leader is elected.
  7. **Leader Heartbeats**: The leader periodically sends heartbeats to all followers to assert its role and manage the cluster's state.
  8. **Reverting to Follower**:
     - During elections, if a node discovers another node with a higher term or receives a valid heartbeat, it transitions back to follower status (`from_candidate_to_follower()`).
     - This ensures that only one leader exists per term and that the leader has the most up-to-date logs.
  9. **Variables and Functions**:
     - `current_term`, `vote_count`, and `logs` track the node's state.
     - `election_timeout_event` and related functions manage the timing for elections.
     - `state_lock` ensures thread-safe operations.
  10. **Handling Edge Cases**:
      - The implementation accounts for network partitions and node failures by allowing re-elections and using heartbeats to detect unreachable leaders.
      - Log integrity checks during the voting process prevent electing leaders with outdated logs.



## 5. Part3 Log Replication Implementation

### Log Replication Process

1. **Initialization**:

   - Once the node becomes leader, it initialized two variables,

     - `next_Index[]` : it stores index of the next log entry to send to that server (initialized to leader last log index + 1)
     - `mach_index[]`: it stores highest log entry known to be replicated on server (initialized to 0, increases monotonically)

   - Once upon success election, the leader send an heart beat to notify all the follower to increase the term

     

2. **Receive Request from Client** 

   - The leader appends new log entries to its log as it receives commands from clients(put topic, put message, get message).
   - Set Append Entry RPC variable value:
     - `prevLogIndex` for Each Follower**: This is determined based on the `nextIndex` for each follower. `prevLogIndex` is set to `nextIndex[follower] - 1`. 
     - `prevLogTerm` for Each Follower**: This is based on the `prevLogIndex` and is set to the term of the log entry at `prevLogIndex` in the leader's log. 
     - **Entries to Send**: The leader includes log entries starting from `nextIndex[follower]` to the end of its log.
     - `leaderCommit`, `term`, `leaderId`
   - then it send `AppendEntries RPC` to each of the follower nodes containing the new entries.

   

3. **Follower Handle Append Entries RPC**:

   - Once the nodes receive the `AppendEntries RPC`, it will go through all the following test:

     - **Term Check**: The receiver first compares the term in the RPC with its own `current term`. If the RPC's term is less than the receiver's current term, the receiver rejects the RPC and responds with `false`.

     - **Log Consistency Check**: The receiver checks if its log contains an entry at `prevLogIndex` whose term matches `prevLogTerm`. If it does not find such an entry, it rejects the RPC and responds with `false`, and nodes `current term`.

     - **Conflict Resolution**: If there is a conflict between an existing entry in the receiver's log and a new entry in the same index (same index but different terms), the receiver deletes the existing entry and all following it. 

     - **Appending Entries**: If there are new entries in the `AppendEntries` RPC that are not present in the receiver's log, it appends these entries to its log.

     - **Leader Commit Check**: If `leaderCommit` (the leader’s commit index) in the RPC is greater than the receiver's `commitIndex`, the receiver sets its `commitIndex` to the minimum of `leaderCommit` and the index of the last new entry

       

4. **Leader Handle Followers Response**:

   - ==Successful Response==

     When a leader receives a successful response (`true`) to an `AppendEntries` RPC:

     1. **Update `matchIndex`**: Set `matchIndex` for a follower to the index of the highest log entry known to be replicated on that follower. 
     2. **Update `nextIndex`**: Set`nextIndex` to the `matchIndex` for that follower plus one. 
     3. **Try to Commit Entries**: The leader checks if there are entries that can now be considered committed. 

   - ==Failed Response==

     When a leader receives a failed response (`false`) indicating a log inconsistency:

     1. **Decrement `nextIndex`**: The leader decrements the `nextIndex` for the follower that sent the failed response. 
     2. **Retry `AppendEntries` RPC**

5. **Committing Entries**:

   - The leader looks for the highest index `N` such that:

     - `N` is greater than the leader's current `commitIndex`,
     - A majority of `matchIndex[i]` (for all servers `i`) are greater than or equal to `N`,
     - And the term of the log entry at index `N` is equal to the leader’s current term.

     If such an `N` exists, the leader sets its `commitIndex` to `N` and applies the log entries up to `N` to its state machine. 

### Locks

To ensure thread safety, especially when accessing and modifying shared data structures like `logs`, `commit_index`, `match_index`, and `heartbeat_received`, the code makes use of a `state_lock`. This lock is critical for maintaining consistency across the system state in a concurrent environment.

## 6. Shortcomings and Discussion

#### Part1

- Scalability: The current approach does not explicitly address scalability issues. As the number of topics or messages grows, the system might struggle with performance due to the linear search of topics and messages.
- Efficiency: The system processes GET and PUT requests sequentially. In high-load scenarios, this could lead to bottlenecks. Implementing more efficient data structures or introducing caching mechanisms could mitigate this issue.

#### Part2

- Fault-Tolerance: when during the election, more than half of the nodes shut down, the system will not select a new leader.

#### Part3

- Efficiency in Log Matching: Optimizing the process to reduce the number of required AppendEntries RPCs for log inconsistency resolution could enhance performance.





## 7. Reference

- raft web: https://raft.github.io/

- raft paper detail elobration: https://github.com/maemual/raft-zh_cn/blob/master/raft-zh_cn.md

- Raft paper