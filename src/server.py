import json
import os
import signal
import sys
import asyncio
import time
from xmlrpc.server import SimpleXMLRPCServer
from time import sleep
from module.raft import RaftNode
from module.struct.address import Address
from module.struct.message_queue import MessageQueue
from module.struct.append_entries import AppendEntry
from module.struct.request_vote import RequestVote
from module.struct.client_rpc import ClientRPC
from module.struct.color import Colors


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
        server.register_instance(
            RaftNode(MessageQueue(), addr, contact_node_addr),)

        def __success_append_entry_response():
            response = AppendEntry.Response(
                server.instance.election_term,
                True,
            )
            return json.dumps(response.to_dict())

        def __fail_append_entry_response():
            response = AppendEntry.Response(
                server.instance.election_term,
                False,
            )
            return json.dumps(response.to_dict())

        def __log_replication(request, addr):

            if (len(server.instance.log) > 0 and request["prev_log_index"] <= len(server.instance.log)):
                # if log doesnt match then delete the difference
                if (server.instance.log[request["prev_log_index"]][0] != request["prev_log_term"]):
                    __print_log_server(f"Log is invalid")
                    server.instance.log = server.instance.log[:request["prev_log_index"]]
                    return __fail_append_entry_response()

            # ! Need fix
            # server.instance.log = server.instance.log[:request["prev_log_index"] + 1]
            # server.instance.log.extend(request["entries"])

            # ? Append log to log list
            for entry in request["entries"]:
                server.instance.log.append(entry)

            __print_log_server(server.instance.log)

            server.instance._set_election_timeout()

            return __success_append_entry_response()

        def __commit_log(request, addr):
            __print_log_server(f"Commit log from {addr.ip}:{addr.port}")
            server.instance.commit_index = min(
                request["leader_commit_index"], len(server.instance.log) - 1)
            # ? Apply log to state machine
            server.instance._apply_log()
            server.instance._set_election_timeout()

            return __success_append_entry_response()

        def __heartbeat(request, addr):
            # __print_log_server("Heartbeat from " + addr.ip + ":" + str(addr.port))
            __print_log_server(f"Heartbeat from {addr.ip}:{addr.port}")
            if request["term"] >= server.instance.election_term:
                server.instance.election_term = request["term"]
                server.instance.type = RaftNode.NodeType.FOLLOWER
            server.instance._set_election_timeout()

            return __success_append_entry_response()

        def __print_log_server(text: str):
            # ? Log format : [address] [time] [type] text
            if server.instance.type == RaftNode.NodeType.LEADER:
                color = Colors.OKBLUE
            elif server.instance.type == RaftNode.NodeType.CANDIDATE:
                color = Colors.OKGREEN
            elif server.instance.type == RaftNode.NodeType.FOLLOWER:
                color = Colors.OKCYAN

            print(Colors.OKBLUE + f"[{server.instance.address}]" + Colors.ENDC +
                  f"[{time.strftime('%H:%M:%S')}]" + color + f"[{server.instance.type}]" + Colors.ENDC + f" {text}")

        @server.register_function
        def apply_membership(request):
            # ! Need fix
            """ 
            When server connect to another server this function will get called via RPC

            Need to make sure
            1. All available nodes know when there's new node
            2. If this ip and port are already in the list then don't run again
            """
            request = json.loads(request)
            addr = Address(request["ip"], int(request["port"]))

            server.instance.cluster_addr_list.append(addr)

            # Ini buat log replication
            server.instance.match_index[str(addr)] = 0
            server.instance.next_index[str(addr)] = 0

            __print_log_server(
                f"New node {addr.ip}:{addr.port} joined the cluster")

            return json.dumps(
                {
                    "status": "success",
                    "log": server.instance.log,
                    "cluster_addr_list": server.instance.cluster_addr_list,
                }
            )

        @server.register_function
        def append_entry(request):
            """ 
            this function will get called via RPC call

            Should be the follower that receives this
            """
            request = json.loads(request)
            addr = Address(request["leader_addr"]["ip"],
                           int(request["leader_addr"]["port"]))

            if request["term"] < server.instance.election_term:
                return __fail_append_entry_response()

            if server.instance.type == RaftNode.NodeType.CANDIDATE:
                server.instance.type = RaftNode.NodeType.FOLLOWER
                server.instance.cluster_leader_addr = addr


            __heartbeat(request, addr)
            if len(request["entries"]) != 0:
                __log_replication(request, addr)
                

            if request["leader_commit_index"] > server.instance.commit_index:
                __commit_log(request, addr)

            return __success_append_entry_response()

        # harusnya di masukin ke heatbeat?
        @server.register_function
        def update_cluster_addr_list(request):
            """ 
            this function will get called via RPC call
            broadcast cluster address list to all nodes
            each time a new node is applying membership

            Should be the follower that receives this
            """
            request = json.loads(request)

            # __print_log_server("Update cluster addr list")

            # print(f"[FOLLOWER] Update cluster addr list")

            __print_log_server("Update cluster addr list")

            # print("cluuseter", server.instance.cluster_addr_list)

            cluster_addr_list = []
            for addr in request["cluster_addr_list"]:
                cluster_addr_list.append(
                    Address(addr["ip"], int(addr["port"])))

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

        @server.register_function
        def execute_from_client(request):
            """
            Leader will execute the command if majority agrees
            If follower receives this then it will redirect to leader
            """
            request = json.loads(request)

            if (server.instance.type == RaftNode.NodeType.LEADER):
                # __print_log_server("Execute from client " + request)
                __print_log_server(f"Execute from client {request}")
                entry = [server.instance.election_term,
                         request["command"], request["args"]]

                # 1. masukin log
                server.instance.log.append(entry)

                # 2. lakukan log replication
                # AppendEntry RPC with entry
                responses = []
                list_addr = server.instance.cluster_addr_list

                for addr in list_addr:
                    # Jangan kirim log ke leader lagi
                    if addr == server.instance.cluster_leader_addr:
                        continue

                    response = server.instance.append_entries(addr)
                    responses.append(response)

                # 3. Kalo majority agree, berarti
                majority_threshold = len(
                    server.instance.cluster_addr_list) // 2 + 1
                # ? leader termasuk majority, mulai dari 1
                count_success = 1
                # ? cek berapa banyak follower yang agree
                for response in responses:
                    if response["success"]:
                        count_success += 1

                if (count_success >= majority_threshold):
                    # ? kalo majority agree, leader commit log dan apply ke state machine
                    __print_log_server(f"Majority agree, commit log")
                    server.instance.commit_index += 1
                    server.instance._apply_log()
                    server.instance._set_election_timeout()

                    # ? kalo udah commit log, kirim response ke client

                response = ClientRPC.Response(ClientRPC.SUCCESS)

                return json.dumps(
                    response.to_dict()
                )

            elif (server.instance.type == RaftNode.NodeType.FOLLOWER):
                # __print_log_server("Redirecting to Leader")
                __print_log_server(f"[FOLLOWER] Redirecting to Leader")

                leader_address = server.instance.cluster_leader_addr
                response = ClientRPC.Response(
                    ClientRPC.REDIRECTED, leader_address)

                return json.dumps(response.to_dict())
            else:
                response = ClientRPC.Response(ClientRPC.FAILED)
                return json.dumps(response.to_dict())
            
        @server.register_function
        def request_log(request):
            request = json.loads(request)

            if (server.instance.type == RaftNode.NodeType.LEADER):
                __print_log_server(f"Request log from client")
                response = {
                    "status": "success",
                    "log": server.instance.log,
                }
                return json.dumps(response)
            elif (server.instance.type == RaftNode.NodeType.FOLLOWER):
                # __print_log_server("Redirecting to Leader")
                __print_log_server(f"[FOLLOWER] Redirecting to Leader")

                leader_address = server.instance.cluster_leader_addr
                response = ClientRPC.Response(
                    ClientRPC.REDIRECTED, leader_address)

                return json.dumps(response.to_dict())
            else:
                response = ClientRPC.Response(ClientRPC.FAILED)
                return json.dumps(response.to_dict())

        @server.register_function
        def request_vote(request):
            """ 
            Request vote for the election

            Invoked by candidate
            """

            # TODO
            # ? cek apakah current term server > term, kalo iya return false klo ga true

            # ? cek apakah si server ini udah pernah ngevote buat leader tertentu apa belom. Cek juga log nya klo lognya uptodate baru grant vote, klo ga gasuah di vote

            request = json.loads(request)

            __print_log_server(
                f"Receive vote request from candidate {request['candidate_id']} for term {request['term']}")

            response = RequestVote.Response()
            response.term = server.instance.election_term
            response.vote_granted = False

            # __print_log_server(f"Receive vote request from candidate {request.candidate_id} for term {request.term}")

            # Check if the candidate term is greater than follower term
            if request['term'] > server.instance.election_term:
                if server.instance.voted_for == -1 or server.instance.voted_for == request['candidate_id']:
                    __print_log_server(
                        f"Vote for candidate {request['candidate_id']} for term {request['term']}")
                    server.instance.election_term = request['term']
                    server.instance.initialize_as_follower()
                    server.instance.type = RaftNode.NodeType.FOLLOWER
                    server.instance.voted_for = request['candidate_id']
                    server.instance._set_election_timeout()
                    response.vote_granted = True
            else:
                __print_log_server(
                    f"Reject vote for candidate {request['candidate_id']} for term {request['term']}")

            __print_log_server(
                f"Send vote response to candidate {request['candidate_id']} for term {request['term']}: {response.vote_granted}")

            return json.dumps(response.to_dict())

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
            os.kill(os.getpid(), signal.SIGTERM)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("server.py <ip> <port> <opt: contact ip> <opt: contact port>")
        exit()

    contact_addr = None

    if len(sys.argv) == 5:
        contact_addr = Address(sys.argv[3], int(sys.argv[4]))

    server_addr = Address(sys.argv[1], int(sys.argv[2]))

    start_serving(server_addr, contact_addr)
