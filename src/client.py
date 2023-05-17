import sys
from xmlrpc.client import ServerProxy

from module.struct.address import Address


def start_serving(addr: Address):
    """
    Spin the client server with the given address
    
    Try Connect, if failed try again to ensure the At least once
    """
    print(f"Starting Raft Client at {addr.ip}:{addr.port}")
    client = ServerProxy(f"http://{addr.ip}:{addr.port}")
  
    while True:
        command = input(">> ")
        if command == "exit":
            break
        try:
          # Client will run `execute` functions in server.py
          response = client.execute(command)
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
