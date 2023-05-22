import sys
import json
import traceback
from xmlrpc.client import ServerProxy
from typing import Any

from module.struct.address import Address
from module.struct.client_rpc import ClientRPC


def __send_request(request: Any, rpc_name: str, addr: Address) -> "json":
    """ 
    Send Request is invoking the RPC to server
    """

    node = ServerProxy(f"http://{addr.ip}:{addr.port}")
    json_request = json.dumps(request)
    rpc_function = getattr(node, rpc_name)
    response = ClientRPC.Response(status=False)
    try:
        response = json.loads(rpc_function(json_request))
    except:
        # ? Harusnya retry
        traceback.print_exc()

    return response


def menu():
    print("Available commands")
    print("1. queue")
    print("2. dequeue")
    print("3. request_log")
    print("4. exit")


def validate_input(command):
    available_command = ["queue", "dequeue", "request_log", "exit"]

    if len(command) != 4:
        print("Please input correct command")
        return False

    ip, port, command, args = command

    # Validate port
    try:
        port = int(port)
    except:
        print("Invalid port")
        return False

    # validate args
    if command not in available_command:
        print("Invalid command")
        return False

    return True


def start_serving(addr: Address):
    """
    Spin the client server with the given address

    Try Connect, if failed try again to ensure the At least once

    # Client will run `execute` functions in server.py
    # Commands will be either queue or dequeue
    """
    print(f"Starting Raft Client at {addr.ip}:{addr.port}")
    print(f"Argument: <ip> <port> <command> <args>")

    request_id = 1

    while True:
        menu()
        command = input(">> ")
        command = command.split()

        # Validate command
        is_valid = validate_input(command)

        if not is_valid:
            continue

        ip, port, command_to_execute, args = command

        address = Address(ip, int(port))

        if command == "exit":
            break
        try:
            requests = ClientRPC.Request(request_id, command_to_execute, args)
            response = __send_request(
                requests.to_dict(), "execute_from_client", address)

            print(response)

            if response["status"] == ClientRPC.REDIRECTED:
                contact_address = Address(
                    response["address"]["ip"], response["address"]["port"])
                response = __send_request(
                    requests, "execute_from_client", contact_address)
        except:
            # TODO implement retry execute command
            print("Can't connect to server. retrying...")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("client.py <ip> <port>")
        exit()

    client_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(client_addr)
