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
    response = ClientRPC.Response(ClientRPC.FAILED).to_dict()

    while response["status"] == ClientRPC.FAILED:
        print("[REQUEST] Sending to server")
        try:
            response = json.loads(rpc_function(json_request))
        except KeyboardInterrupt:
            break
        except:
            traceback.print_exc()
            print("[RESPONSE] Can't connect to server. retrying...")
            continue

    return response


def menu():
    print("Available commands")
    print("1. queue")
    print("2. dequeue")
    print("3. request_log")
    print("4. exit")


def validate_input(command):
    available_command = ["queue", "dequeue", "request_log", "exit"]

    if len(command) == 1 and (command[0] == "exit"):
        return True

    if len(command) < 3 or len(command) > 4:
        print("Please input correct command")
        return False

    port = command[1]
    command = command[2]

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

        if command[0] == "exit":
            break

        if command[0] == "queue":
            ip, port, command_to_execute, args = command
        else:
            ip, port, command_to_execute = command
            args = ""

        address = Address(ip, int(port))

        requests = ClientRPC.Request(request_id, command_to_execute, args)

        if (command_to_execute == "request_log"):
            response = __send_request(
                requests.to_dict(), "request_log", address) 
        else:
            response = __send_request(
                requests.to_dict(), "execute_from_client", address)

        if response["status"] == ClientRPC.REDIRECTED:
            contact_address = Address(
                response["address"]["ip"], response["address"]["port"])
            if (command_to_execute == "request_log"):
                response = __send_request(
                    requests.to_dict(), "request_log", contact_address)
            else:
                response = __send_request(
                    requests.to_dict(), "execute_from_client", contact_address)

        if response["status"] == ClientRPC.SUCCESS:
            request_id += 1

        print("[RESPONSE]", response)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("client.py <ip> <port>")
        exit()

    client_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(client_addr)
