import time
import pytest

from test_utils import Swarm

# Define an array for the number of nodes to be used in parameterized tests
NUM_NODES_ARRAY = [5]
PROGRAM_FILE_PATH = "../src/node.py"
TEST_TOPIC = "test_topic"
TEST_TOPIC_2 = "test_topic_2"
TEST_MESSAGE = "Test Message"
TEST_MESSAGE_2 = "Test Message_2"

ELECTION_TIMEOUT = 2.0
NUMBER_OF_LOOP_FOR_SEARCHING_LEADER = 3

@pytest.fixture
def swarm(num_nodes):
    """
    Setup a swarm of Raft nodes for testing.
    """
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    swarm.start(ELECTION_TIMEOUT)
    yield swarm
    swarm.clean()

def wait_for_commit(seconds=1):
    """
    Wait for a specified amount of time to simulate commit delay.
    """
    time.sleep(seconds)

@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_one_follower_dead(swarm: Swarm, num_nodes: int):
    # get leader node, put topics and messages
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader1 != None)
    assert (leader1.create_topic(TEST_TOPIC).json() == {"success": True})
    assert (leader1.put_message(TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    
    follower_nodes = [node for node in swarm.nodes if node != leader1]
    assert len(follower_nodes) > 0
    node_to_remove = follower_nodes[0]
    node_to_remove.commit_clean(ELECTION_TIMEOUT)

    assert (leader1.create_topic(TEST_TOPIC_2).json() == {"success": True})
    assert (leader1.put_message(TEST_TOPIC_2, TEST_MESSAGE_2).json() == {"success": True})

    node_to_remove.start()

    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    # check nodes if they has all the topics
    topics = node_to_remove.get_topics().json()
    assert (topics == {"success": True, "topics": [TEST_TOPIC, TEST_TOPIC_2]})
    # we cannot get message from follower as they cannnot create logentry    
    assert(node_to_remove.get_message(
        TEST_TOPIC_2).json() == {"success": False})

    assert(node_to_remove.get_message(
        TEST_TOPIC).json() == {"success": False})

@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_less_than_half_followers_down_and_recover(swarm: Swarm, num_nodes: int):
    """
    Test that the system can still function with N/2-1 nodes down and recover afterwards.
    """
    # Get initial leader
    leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(leader != None)
    
    # Create topics and messages
    assert(leader.create_topic(TEST_TOPIC).json() == {"success": True})
    wait_for_commit(0.1)  
    assert(leader.put_message(TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    
    # Shut down N/2-1 nodes
    nodes_to_close = (num_nodes // 2) - 1
    closed_nodes = []
    for _ in range(nodes_to_close):
        for node in swarm.nodes:
            if node != leader and node not in closed_nodes:
                node.commit_clean(ELECTION_TIMEOUT)
                closed_nodes.append(node)
                break

    # Check that the leader still functions
    new_leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(new_leader != None)
    assert(new_leader.create_topic(TEST_TOPIC_2).json() == {"success": True})
    assert(new_leader.get_message(TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})
    
    # Restart the closed nodes
    for node in closed_nodes:
        node.start()

    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    # Check that the nodes are still functional
    for node in closed_nodes:
        assert(node.get_topics().json() == {"success": True, "topics": [TEST_TOPIC, TEST_TOPIC_2]})
        assert(node.get_message(TEST_TOPIC).json() == {"success": False})

@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_majority_followers_down_and_recovery(swarm: Swarm, num_nodes: int):
    """
    Test to ensure that if more than half of the nodes in the swarm are down, 
    the system cannot process new topic creation or message sending requests.
    """
    # Get initial leader
    leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(leader != None)
    assert (leader.create_topic(TEST_TOPIC).json() == {"success": True})
    assert (leader.put_message(TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})

    
    # Shut down more than half of the nodes
    nodes_to_close = (num_nodes // 2) + 1
    closed_nodes = []
    for _ in range(nodes_to_close):
        for node in swarm.nodes:
            if node != leader and node not in closed_nodes:
                node.clean()
                closed_nodes.append(node)
                break

    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)


    # Check the old leader exist
    assert leader == swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    

    # Restart the closed nodes and wait for the cluster to possibly elect a new leader
    for i in closed_nodes:
        i.start()
    
    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    # Check if the system can elect a new leader and return to normal operation
    new_leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(new_leader != None)
    assert (new_leader.get_topics().json() == {"success": True, "topics": [TEST_TOPIC]})
    assert (new_leader.get_message(TEST_TOPIC_2).json() == {"success": False})



@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_all_followers_down_and_recovery(swarm: Swarm, num_nodes: int):
    """
    Test the cluster's ability to function and recover after multiple followers fail.
    """
    initial_leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(initial_leader != None)

    # Shut down a majority of follower nodes
    followers_to_close = num_nodes - 1
    closed_followers = []
    for node in swarm.nodes:
        if node != initial_leader and len(closed_followers) < followers_to_close:
            node.clean()
            closed_followers.append(node)

    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    # Attempt operations with a minority of nodes; expect failure
    #response = initial_leader.create_topic(TEST_TOPIC_2).json()
    #assert(response == {"success": False})

    # Restart the closed nodes
    for node in closed_followers:
        node.start()

    time.sleep(ELECTION_TIMEOUT * NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    # Verify the cluster can recover and elect a new leader
    new_leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert(new_leader != None)
    assert(new_leader.create_topic(TEST_TOPIC_2).json() == {"success": True})
