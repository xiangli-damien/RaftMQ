import json

import requests


def send_append_entries(server, data):
    try:
        response = requests.post(f'http://{server["ip"]}:{server["port"]}/append_entries', json=data)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except requests.RequestException:
        return None


if __name__ == "__main__":
    with open("../config.json", 'r') as config_file:
        config = json.load(config_file)

    data = {}
    my_address = config['addresses']
    for server in config['addresses']:
        print(type(server))
        print(server)
        send_append_entries(server, data)
    # print(my_address)
    # my_port = my_address[0]['port']
    # print(my_port)

