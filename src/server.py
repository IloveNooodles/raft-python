import json
import os
import signal
import sys
import asyncio
from xmlrpc.server import SimpleXMLRPCServer

from module.raft import RaftNode
from module.struct.address import Address
from module.struct.message_queue import MessageQueue
from module.struct.append_entries import AppendEntry
from module.struct.request_vote import RequestVote


def start_serving(addr: Address, contact_node_addr: Address):
    """ 
    Spin the server forever
    
    Can be killed using ctrl-c
    
    We need to make sure the server request is IDEMPOTENT to implement at least once RPC
    
    We can do this by adding ID to each request
    """
    print(f"Starting Raft Server at {addr.ip}:{addr.port}")

    with SimpleXMLRPCServer((addr.ip, addr.port), logRequests=False) as server:
        server.register_introspection_functions()
        server.register_instance(RaftNode(MessageQueue(), addr, contact_node_addr),)

        @server.register_function
        def apply_membership(request):
            """ 
            When server connect to another server this function will get called via RPC
            
            Need to make sure
            1. All available nodes know when there's new node
            2. If this ip and port are already in the list then don't run again
            """
            request = json.loads(request)
            addr = Address(request["ip"], int(request["port"]))

            server.instance.cluster_addr_list.append(addr)
            server.instance.match_index[str(addr)] = 0
            server.instance.next_index[str(addr)] = len(server.instance.log)
            print(f"[LEADER] New node {addr.ip}:{addr.port} joined the cluster")

            # print(server.instance.cluster_addr_list)
            # server.instance.__broadcast_cluster_addr_list()
            
            return json.dumps(
                {
                    "status": "success",
                    "log": server.instance.log,
                    "cluster_addr_list": server.instance.cluster_addr_list,
                }
            )

        # TODO harusnya append entry kosong
        @server.register_function
        def append_entry(request):
            """ 
            this function will get called via RPC call
            
            Should be the follower that receives this
            """
            request = json.loads(request)
            addr = Address(request["leader_addr"]["ip"], int(request["leader_addr"]["port"]))

            response = AppendEntry.Response(
                server.instance.election_term,
                False,
            )

            # ? Kalo leader term lebih kecil dari term server ini tolak
  
            if (request["term"] > server.instance.election_term):
                print(f"[FOLLOWER] Heartbeat from {addr.ip}:{addr.port}")
                server.instance._set_election_timeout()
                return json.dumps(response.toDict())
            
            # ? Cek prevLogIndex, kalo di log server ini gak punya entry dari prev log index return false

            # ! Ini masi harus dicek ?
            if (len(server.instance.log) - 1 if len(server.instance.log) > 0 else 0 != request["prev_log_index"]):
                print(f"[FOLLOWER] Heartbeat from {addr.ip}:{addr.port}")
                server.instance._set_election_timeout()
                return json.dumps(response.toDict())
            
            # ? Kalo index di posisi tersebut udah keisi di server, INTINYA kita ngikutin leader. Leader selalu bener, jadi kita harus rollback semua log yang ada di server 
            if (len(server.instance.log) > 0):
                if (server.instance.log[request["prev_log_index"]][0] != request["prev_log_term"]):
                    server.instance.log = server.instance.log[:request["prev_log_index"]]

            # ? Append entries yg baru dikirim dr leader ke semua log, klo gak ya heartbeat aja ga usah di append
            if (len(request["entries"]) != 0 ):
                entry = request["entries"]
                server.instance.log.append(entry)
                print(f"[FOLLOWER] Append entries from {addr.ip}:{addr.port}: {entry}")
            else:
                print(f"[FOLLOWER] Heartbeat from {addr.ip}:{addr.port}")

            # ? Kalo leader commit nya lebih gede dari current server commit index, set commit index nya jadi min(leaderCommit, index New Entry)
            if (request["leader_commit_index"] > server.instance.commit_index):
                server.instance.commit_index = min(request["leader_commit_index"], len(server.instance.log) - 1)

            response = AppendEntry.Response(
                server.instance.election_term,
                True,
            )

            # Update election timeout when receive heartbeat
            server.instance._set_election_timeout()
            return json.dumps(response.toDict())
        
        @server.register_function
        def update_cluster_addr_list(request):
            """ 
            this function will get called via RPC call
            broadcast cluster address list to all nodes
            each time a new node is applying membership
            
            Should be the follower that receives this
            """
            request = json.loads(request)

            print(f"[FOLLOWER] Update cluster addr list")

            cluster_addr_list = []
            for addr in request["cluster_addr_list"]:
                cluster_addr_list.append(Address(addr["ip"], int(addr["port"])))

            server.instance.cluster_addr_list = cluster_addr_list

            # Update election timeout when receive addr list
            server.instance._set_election_timeout()

            return json.dumps(
                {
                    "status": "success",
                    "log": server.instance.log,
                    "cluster_addr_list": server.instance.cluster_addr_list,
                }
            )
        
        # ? Ini harusnya di cek di heartbeat
        @server.register_function
        def execute_from_client(request):
            """
            Leader will execute the command if majority agrees
            If follower receives this then it will redirect to leader
            """

            request = json.loads(request)

            if (server.instance.type == RaftNode.NodeType.LEADER):
                print(f"[LEADER] Execute from client {request}")
                entry = [server.instance.election_term, request["command"], request["args"]]
                server.instance.log.append(entry)
                server.instance.entry = entry

                # TODO implement execute command
                return json.dumps(
                    {
                        "status": "success",
                    }
                )
            
            elif (server.instance.type == RaftNode.NodeType.FOLLOWER):
                print(f"[FOLLOWER] Redirecting to Leader")

                response = {
                    "status": "redirected",
                    "address": {
                        "ip":   server.instance.cluster_leader_addr.ip,
                        "port": server.instance.cluster_leader_addr.port,
                    } 
                }

                return json.dumps(response)
            else:
                return json.dumps(
                    {
                        "status": "error",
                        "message": "Not a leader or follower",
                    }
                )

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
            os.kill(os.getpid(), signal.SIGTERM)

        @server.register_function
        def request_log(request):
            """
            Client will request request_log of the current state

            Must return the current consistent server log
            """

            request = json.loads(request)


        @server.register_function
        def request_vote(request):
            """ 
            Request vote for the election

            Invoked by candidate
            """

            # TODO
            # ? cek apakah current term server > term, kalo iya return false klo ga true

            # ? cek apakah si server ini udah pernah ngevote buat leader tertentu apa belom. Cek juga log nya klo lognya uptodate baru grant vote, klo ga gasuah di vote

            request = RequestVote.Request(**request)
            response = RequestVote.Response(server.instance.election_term, False)

            # Check if the candidate term is greater than follower term
            if request.term > server.instance.election_term:
                if server.instance.voted_for == -1 or server.instance.voted_for == request.candidate_id:
                    server.instance.__print_log(f"Vote for candidate {request.candidate_id} for term {request.term}")
                    server.instance.election_term = request.term
                    server.instance.type = RaftNode.NodeType.FOLLOWER
                    server.instance.voted_for = request.candidate_id
                    server.instance._set_election_timeout()
                    response.vote_granted = True
            else:
                server.instance.__print_log(f"Reject vote for candidate {request.candidate_id} for term {request.term}")

            return response.toDict()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("server.py <ip> <port> <opt: contact ip> <opt: contact port>")
        exit()

    contact_addr = None

    if len(sys.argv) == 5:
        contact_addr = Address(sys.argv[3], int(sys.argv[4]))

    server_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(server_addr, contact_addr)