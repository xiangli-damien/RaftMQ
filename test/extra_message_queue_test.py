from test_utils import Swarm, Node
import threading
import pytest
import time
import requests

NUM_NODES_ARRAY = [5]
TEST_TOPIC = "test_topic"
TEST_MESSAGES = ["Message 1", "Message 2", "Message 3", "Message 4", "Message 5"]
BASE_URL = "http://localhost:5000"

PROGRAM_FILE_PATH = "../src/node.py"
ELECTION_TIMEOUT = 2.0


@pytest.fixture
def node_with_test_topic():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    node.start()
    time.sleep(ELECTION_TIMEOUT)
    assert(node.create_topic(TEST_TOPIC).json() == {"success": True})
    yield node
    node.clean()


@pytest.fixture
def node():
    node = Swarm(PROGRAM_FILE_PATH, 1)[0]
    node.start()
    time.sleep(ELECTION_TIMEOUT)
    yield node
    node.clean()


def concurrent_topic_creation(node, topic, responses):
    # Encapsulates the call that creates the topic and captures the response
    response = node.create_topic(topic)
    responses.append(response.json())

def test_concurrent_creation_of_same_topic(node):
    topic = "concurrent_topic"
    threads = []
    responses = []

    # Create 10 threads that simulate 10 clients to create the same topic concurrently
    for _ in range(10):
        thread = threading.Thread(target=concurrent_topic_creation, args=(node, topic, responses))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # Check that only one request successfully created the topic
    success_count = sum(response["success"] for response in responses)
    assert success_count == 1, f"Only one topic creation should succeed, but got {success_count} successes."


def test_message_order(node):
    assert node.create_topic(TEST_TOPIC).json()["success"] == True, "Failed to create topic"

    # Send a series of messages to this topic
    for message in TEST_MESSAGES:
        node.put_message(TEST_TOPIC, message)

    # Get the messages one by one in the order they were sent, and verify that the returned messages remain in the correct order
    for expected_message in TEST_MESSAGES:
        response = node.get_message(TEST_TOPIC).json()
        assert response["success"] == True, "Failed to get message"
        assert response["message"] == expected_message, f"Expected message '{expected_message}', but got '{response['message']}'"

    # Get messages that exceed the number of messages sent, making sure to return a failure
    response = node.get_message(TEST_TOPIC).json()
    assert response["success"] == False, "Expected no more messages, but got one"

def test_undefined_command(node):
    
    response = node.send_wrong_command()
    assert response.status_code == 404, f"Expected 404 Not Found for undefined command, got {response.status_code}"

