# RRMQ Test Report

 The tests are divided into four main categories: `extra_message_queue_test`, `complex_election_replication`, `capacity_test`, and `fault_tolerance_follower_test`. Below is a summary of each test function and its purpose, all of these test has been passed: 



#### Usage

run test

```bash
cd test 
python3 -m pytest message_queue_test.py 
python3 -m pytest election_test.py
python3 -m pytest replication_test.py
# extra test
python3 -m pytest extra_message_queue_test.py
python3 -m pytest complex_election_replication.py
python3 -m pytest capacity_test.py
python3 -m pytest fault_tolerance_follower_test.py
```

run a single node:
```
python3 src/node.py config.json 0
```

### 1. extra_message_queue_test (part1)

- `test_concurrent_creation_of_same_topic`: Validates that when multiple clients attempt to create the same topic concurrently, only one succeeds, ensuring mutual exclusion in topic creation.
- `test_message_order`: Ensures messages are received in the same order they were sent to a topic, verifying message ordering integrity.
- `test_undefined_command`: Checks the system's handling of undefined commands, expecting a 404 Not Found response to prevent unintended behaviors.

### 2. complex_election_replication (part1 & part2 & part3)

- `test_cannot_add_duplicate_topics`: Confirms that the system prevents the creation of duplicate topics, maintaining uniqueness of topics.
- `test_complex_request_1` & `test_complex_request_2`: These tests simulate leader failures and verify that subsequent leaders can correctly handle pending tasks, maitaining the consistency of logs and statemachine.

### 3. capacity_test

- `test_multi_leaders`: Tests the system's behavior under the scenario where the amount of nodes increase.

### 4. fault_tolerance_follower_test (part1 & part2 & part3)

- `test_one_follower_dead`: Verifies the system's ability to continue functioning when a follower node fails, ensuring fault tolerance.
- `test_less_than_half_followers_down_and_recover`: Tests the system's resilience by shutting down ==N/2-1== follower nodes and verifying recovery, demonstrating the system's ability to maintain quorum and continue operations.
- `test_majority_followers_down_and_recovery`: Assesses the system's behavior when ==N/2+1== nodes are down, showing that it stops processing requests, as expected by the Raft consensus rules, and recovers once a majority is restored.
- `test_all_followers_down_and_recovery`: Evaluates the system's response to all followers failing and later recovering, ensuring that the system can halt and resume operations in accordance with Raft's safety.

### 5. Original Test

The Raft has passed all the original test provided including:

- `election_test`
- `message_queue_test`
- `replication_test`

### 6. Short Coming

- System Leads to a long response time of dealing complex request when dramatically increasing nodes amount like 99.
- Did not test the case with large amount of topics and message
- Did not test dynamic changes in the cluster configuration, such as adding or removing nodes while the system running.
