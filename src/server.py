from module.struct.address      import Address
from module.struct.message_queue           import MessageQueue
from module.raft        import RaftNode
from xmlrpc.server      import SimpleXMLRPCServer

import sys, json

def start_serving(addr: Address, contact_node_addr: Address):
    print(f"Starting Raft Server at {addr.ip}:{addr.port}")
    
    with SimpleXMLRPCServer((addr.ip, addr.port)) as server:
        server.register_introspection_functions()
        server.register_instance(RaftNode(MessageQueue(), addr, contact_node_addr))

        @server.register_function
        def apply_membership(request):
            request = json.loads(request)
            addr = Address(request["ip"], int(request["port"]))
            
            print(f"Applying membership for {addr.ip}:{addr.port}")
            server.instance.log.append(f"Applying membership for {addr.ip}:{addr.port}")
            server.instance.cluster_addr_list.append(addr)

            return json.dumps({
                "status": "success",
                "log":    server.instance.log,
                "cluster_addr_list": server.instance.cluster_addr_list,
            })
        
        @server.register_function
        def heartbeat(request):
            request = json.loads(request)
            addr = Address(request["ip"], int(request["port"]))
            
            print(f"Heartbeat from {addr.ip}:{addr.port}")
            
            return json.dumps({
                "heartbeat_response": "ack",
                "log":                server.instance.log,
            })

        server.serve_forever()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("server.py <ip> <port> <opt: contact ip> <opt: contact port>")
        exit()

    contact_addr = None
    if len(sys.argv) == 5:
        contact_addr = Address(sys.argv[3], int(sys.argv[4]))
    server_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(server_addr, contact_addr)
