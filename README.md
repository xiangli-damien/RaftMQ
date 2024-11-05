# Raft Message Queue (RMQ)


<img src="./Raft_Picture.svg" alt="./Raft_Picture" width="300"/>

## Overview

**Raft Message Queue (RMQ)** is a distributed message queue implemented in Python, designed to demonstrate the Raft consensus algorithm's power in managing distributed logs and achieving fault-tolerant consensus. RMQ allows distributed nodes to synchronize a key-value message queue across a cluster, ensuring that each node processes messages in a consistent and reliable order.

### Key Features

- **Distributed Message Queue**: Supports topic creation, message publication, and consumption using a consistent log for ordered message processing.
- **Raft Consensus**: Utilizes Raft for leader election and log replication, ensuring system consistency even during network partitions or node failures.
- **Fault Tolerance**: Continues operation as long as a majority of nodes are functioning, offering resilience against partial system failures.

## Project Structure

- src/:
  - **`log.py`**: Defines the log handling, ensuring consistency in message operations across nodes.
  - **`node.py`**: Defines a node in the cluster, managing REST APIs for communication.
  - **`raft_node.py`**: Implements the Raft protocol with leader election and log replication functionalities.
- **config.json**: Configuration file specifying node addresses in the cluster.
- **test/**: Directory for tests validating leader election, log replication, and message queue functionality. Detailed test reports are included in `testing_report.md`.

## Installation and Setup

To get started with RMQ, clone the repository and ensure all dependencies are installed. Then, configure `config.json` with the IPs and ports for each node in your cluster.

```bash
git clone https://github.com/xli0808/RaftMessageQueue.git
cd RaftMessageQueue
pip install -r requirements.txt
```

## Running the System

To start the system, launch each node on separate terminals or servers, referencing the `config.json` configuration.

```bash
python src/raft_node.py --config config.json --node_id <NODE_ID>
```

Each node will assume an initial role as a follower, triggering leader election upon system startup.

## Architecture and Design

### 1. Raft Consensus and Message Queue

This project integrates the Raft algorithm to manage message queues, ensuring each node in the cluster shares a consistent view of topics and messages.

#### Core Components

- **Leader Election**: A leader node is dynamically elected to coordinate log replication, ensuring only one leader exists per term.
- **Log Replication**: The leader appends log entries, replicating these across followers to maintain consistent state.
- **Fault Tolerance**: The system remains operational as long as a majority of nodes are active.

### 2. Key Functionalities

#### Topic Management

1. **Create Topic**:
   - Checks if the current node is the leader.
   - Adds a topic entry to the log with a unique identifier (`PUT_TOPIC_FLAG`).
   - Waits for log entry commitment, ensuring the topic is distributed across nodes.
2. **Get Topics**:
   - Retrieves all topic names stored in the state machine, reflecting the consistent state across the cluster.

#### Message Handling

1. **Publish Message**:
   - Checks leader status before accepting messages.
   - Validates topic existence, then appends message data to the log (`PUT_MESSAGE_FLAG`).
   - Waits for replication to achieve consistency.
2. **Consume Message**:
   - Retrieves the first message available for a specified topic, removing it from the queue.
   - Returns error if no messages are available or topic is absent.

#### Leader Status

- Provides the current status of the node (`Follower`, `Leader`, `Candidate`) along with the term, useful for debugging and monitoring the system’s health.

### 3. Raft-Specific Implementations

#### Leader Election Process

1. **Role Transitions**:
   - Each node starts as a follower with a randomized election timeout.
   - Upon timeout without a heartbeat from a leader, the node transitions to a candidate, initiating leader election.
2. **Voting and Term Management**:
   - A candidate requests votes from other nodes, gaining leadership upon majority approval.
   - The candidate becomes leader if a majority of nodes respond with approval, beginning log replication.
3. **Heartbeat Mechanism**:
   - The leader periodically sends heartbeats to followers to maintain control, resetting their election timers and confirming cluster stability.
4. **Handling Split Votes and Network Partitions**:
   - In case of tie votes, each candidate resets its election timer, ensuring repeated elections until one node secures the majority.
   - If a leader discovers a higher-term candidate or fails to maintain majority, it relinquishes its role, reverting to follower status.

#### Log Replication Process

1. **Client Interaction**:
   - Log entries are appended when the leader receives requests from clients (e.g., adding topics, publishing messages).
2. **AppendEntries RPC**:
   - Each follower validates log consistency with the leader, checking term and index.
   - Conflict resolution is managed by discarding conflicting entries, ensuring an accurate log is maintained across nodes.
3. **Commit Process**:
   - When a log entry is committed, it’s applied to the state machine, solidifying its position in the cluster’s state.
4. **Consistency Guarantees**:
   - The leader commits entries only after securing majority replication, reinforcing consistency across the cluster.

### Data Structures and Synchronization

1. **State Variables**:
   - Each node maintains state variables, including `current_term`, `commit_index`, and `next_index` for log tracking.
2. **Locks for Thread Safety**:
   - To ensure consistency, `state_lock` synchronizes access to shared resources, preventing data races in concurrent operations.
3. **Log Integrity**:
   - `log.py` maintains each log entry's term, topic, message, and operation, using flags to differentiate actions (e.g., `PUT_TOPIC_FLAG`).

## Limitations and Considerations

1. **Scalability**:
   - As the number of topics or messages grows, efficiency may be impacted, especially during high-load periods.
2. **Election Limitations**:
   - If fewer than half of the nodes are active, the system cannot elect a new leader, impacting availability.
3. **Log Consistency Optimization**:
   - Additional strategies for reducing AppendEntries retries could improve performance.

## References

- [Raft Consensus Algorithm](https://raft.github.io/)

