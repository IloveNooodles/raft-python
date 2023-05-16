from module.struct.address      import Address
from xmlrpc.client import ServerProxy

import sys

def start_serving(addr: Address):
    print(f"Starting Raft Client at {addr.ip}:{addr.port}")
    client = ServerProxy(f"http://{addr.ip}:{addr.port}")

    while True:
        command = input(">> ")
        if command == "exit":
            break
        response = client.execute(command)
        print(response)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("client.py <ip> <port> <opt: contact ip> <opt: contact port>")
        exit()

    if len(sys.argv) == 5:
        contact_addr = Address(sys.argv[3], int(sys.argv[4]))
    client_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(client_addr)