import sys
import json
import traceback
from xmlrpc.client import ServerProxy
from typing import Any

from module.struct.address import Address

def __send_request(request: Any, rpc_name : str, addr: Address) -> "json":
    """ 
    Send Request is invoking the RPC to server
    """
    # Warning : This method is blocking
    node         = ServerProxy(f"http://{addr.ip}:{addr.port}")
    json_request = json.dumps(request)
    rpc_function = getattr(node, rpc_name)

    # ? Darimana
    response = {
        "success": False,
    }

    try:
        response     = json.loads(rpc_function(json_request))
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


def start_serving(addr: Address):
    """
    Spin the client server with the given address
    
    Try Connect, if failed try again to ensure the At least once
    """
    print(f"Starting Raft Client at {addr.ip}:{addr.port}")
    print(f"Argument: <ip> <port> <command> <args>")

    while True:
        menu()
        command = input(">> ")
        command = command.split()
        address = Address(command[0], int(command[1]))

        
        requests = {
            "command": command[2],
            "args": command[3]
        }
        
        if command == "exit":
            break
        try:
            # Client will run `execute` functions in server.py
            # Commands will be either queue or dequeue
            response = __send_request(requests, "execute_from_client", address)
            
            if response["status"] == "redirected":
                response = __send_request(requests, "execute_from_client", Address(response["address"]["ip"], response["address"]["port"]))
                
            print(response)
        except:
            # TODO implement retry execute command
            print("Can't connect to server. retrying...")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("client.py <ip> <port>")
        exit()

    client_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(client_addr)
