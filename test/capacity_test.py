import time
import pytest

from test_utils import Swarm

NUM_NODES_ARRAY = [19]
PROGRAM_FILE_PATH = "../src/node.py"
TEST_TOPIC = "test_topic"
TEST_TOPIC_2 = "test_topic_2"
TEST_MESSAGE = "Test Message"
TEST_MESSAGE_2 = "Test Message_2"

ELECTION_TIMEOUT = 2.0
NUMBER_OF_LOOP_FOR_SEARCHING_LEADER = 2

@pytest.fixture
def swarm(num_nodes):
    swarm = Swarm(PROGRAM_FILE_PATH, num_nodes)
    swarm.start(ELECTION_TIMEOUT)
    yield swarm
    swarm.clean()

def wait_for_commit(seconds=1):
    time.sleep(seconds)

@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_cannot_add_duplicate_topics(swarm: Swarm, num_nodes: int):
    leader = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)
    assert leader is not None

    response = leader.create_topic(TEST_TOPIC)
    assert response.json() == {"success": True}

    duplicate_response = leader.create_topic(TEST_TOPIC)
    assert duplicate_response.json() == {"success": False}

    topics_response = leader.get_topics()
    assert topics_response.json() == {"success": True, "topics": [TEST_TOPIC]}

@pytest.mark.parametrize('num_nodes', NUM_NODES_ARRAY)
def test_multi_leaders(swarm: Swarm, num_nodes: int):
    # get leader node, put topics and messages
    leader1 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader1 != None)
    assert (leader1.create_topic(TEST_TOPIC).json() == {"success": True})
    assert (leader1.put_message(TEST_TOPIC, TEST_MESSAGE).json() == {"success": True})
    
    # kill leader1 get leader2, get topics
    leader1.commit_clean(ELECTION_TIMEOUT)
    leader2 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader2 != None)
    assert (leader2.get_message(TEST_TOPIC).json() == {"success": True, "message": TEST_MESSAGE})
    assert (leader2.create_topic(TEST_TOPIC).json() == {"success": False})

    # kill leader2, get leader3, get topic and message
    leader2.commit_clean(ELECTION_TIMEOUT)
    leader3 = swarm.get_leader_loop(NUMBER_OF_LOOP_FOR_SEARCHING_LEADER)

    assert (leader3 != None)
    assert (leader3.get_topics().json() == {"success": True, "topics": [TEST_TOPIC]})
    assert (leader3.get_message(TEST_TOPIC).json() == {"success": False})

