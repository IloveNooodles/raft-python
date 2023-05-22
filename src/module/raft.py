import asyncio
import json
import socket
import time
import traceback
from enum import Enum
from random import random, uniform
from threading import Thread
from typing import Any, List, Dict
from xmlrpc.client import ServerProxy
import threading
import aioxmlrpc.client

from module.struct.thread_with_value import ThreadWithValue
from module.struct.address import Address
from module.struct.append_entries import AppendEntry
from module.struct.request_vote import RequestVote
from module.struct.color import Colors
from module.struct.message_queue import MessageQueue


class RaftNode:
    """ 
    Implementation of Raft Node
    https://raft.github.io/raft.pdf

    1. Election time is mostly between T and 2T (150ms - 300ms)
    2. If server is follower and not receiveing anything from client, upgrade to candidate
    3. Candidate will start election
    """
    HEARTBEAT_INTERVAL = 1
    ELECTION_TIMEOUT_MIN = 20
    ELECTION_TIMEOUT_MAX = 25
    RPC_TIMEOUT          = 5

    class NodeType(Enum):
        """ 
        # LEADER
        # ? Send Empty append entries (heartbeat) buat prevent timeouts
        # ? Klo client minta execute, append entry dulu ke diri DISINI STATE MASIH UNCOMMITED. Abis itu coba minta ke semua buat replication
        # ? cek apakah last log index >= nextIndex untuk setiap follower. Kalo sukses update nextIndex sama matchIndex buat follower. matchIndex ini kek sampe index mana log follower sm log server sama, klo nextIndex itu index kosongnya lah intinya

        # ? LOG MATCHING GAMING Klo ternyata ada ada network partition, trs ada server yang punya commit index N lebih tinggi dari current commit index, majority response nya ternyata matchIndexnya lebih gededari N, dan term di response N itu sama kaya current Term, update commit index

        # ? 

        """
        LEADER = 1
        CANDIDATE = 2
        FOLLOWER = 3

        def __str__(self) -> str:
            return self.name

    def __init__(self, application: Any, addr: Address, contact_addr: Address = None):
        # ? random float for timeout, called here so in this node, the random float is the same
        random_float = uniform(RaftNode.ELECTION_TIMEOUT_MIN,
                               RaftNode.ELECTION_TIMEOUT_MAX)
        socket.setdefaulttimeout(RaftNode.RPC_TIMEOUT)
        self.leader_id:           int = -1
        self.address:             Address = addr
        self.type:                RaftNode.NodeType = RaftNode.NodeType.FOLLOWER
        self.log:                 List[int, str,
                                       str, int] = []  # [term, command, args, request_id]
        self.app:                 MessageQueue = application

        # Election stuff
        self.election_term:       int = 0
        self.election_timeout:    int = time.time(
        ) + random_float
        self.election_interval:   int = random_float
        self.voted_for:           int = -1
        self.vote_count:          int = 0

        self.commit_index:        int = -1
        self.last_applied:        int = -1
        self.last_heartbeat_received: int = time.time()

        # Reinit after election
        self.match_index:         Dict[str, int] = {}
        self.next_index:          Dict[str, int] = {}

        self.cluster_addr_list:   List[Address] = []
        self.cluster_leader_addr: Address = None

        self.timeout_thread = None
        self.heartbeat_thread = None

        if contact_addr is None:
            self.cluster_addr_list.append(self.address)
            self.__initialize_as_leader()
        else:
            self.__listen_timeout()
            self.__try_to_apply_membership(contact_addr)

    
    def __shutdown(self):
        self.__print_log("Shutting down...")
        if self.timeout_thread is not None:
            self.timeout_thread.join()
            self.timeout_thread = None
        if self.heartbeat_thread is not None:
            self.heartbeat_thread.join()
            self.heartbeat_thread = None
        exit(0)

    # Internal Raft Node methods
    def __print_log(self, text: str):
        # ? Log format : [address] [time] [type] text
        if self.type == RaftNode.NodeType.LEADER:
            color = Colors.OKBLUE
        elif self.type == RaftNode.NodeType.CANDIDATE:
            color = Colors.OKGREEN
        elif self.type == RaftNode.NodeType.FOLLOWER:
            color = Colors.OKCYAN

        print(Colors.OKBLUE + f"[{self.address}]" + Colors.ENDC +
              f"[{time.strftime('%H:%M:%S')}]" + color + f"[{self.type}]" + Colors.ENDC + f" {text}")

    def __initialize_as_leader(self):
        # ? Initialize as leader node
        self.__print_log("Initialize as leader node...")
        self.cluster_leader_addr = self.address
        self.type = RaftNode.NodeType.LEADER
        request = {
            "cluster_leader_addr": self.address
        }
        # TODO : Inform to all node this is new leader
        self.heartbeat_thread = Thread(target=asyncio.run, args=[
                                       self.__leader_heartbeat()])
        self.heartbeat_thread.start()
        
        # if self.timeout_thread is not None:
        #     self.timeout_thread.join()
        #     self.timeout_thread = None

    def initialize_as_follower(self):
        # ? Initialize as follower node
        self.__print_log("Initialize as follower node...")
        self.type = RaftNode.NodeType.FOLLOWER
        # print("MASUK Ga heart")
        # if self.heartbeat_thread is not None:
        #     print("masuk")
        #     self.heartbeat_thread.join()
        #     self.heartbeat_thread = None
        self.__listen_timeout()


    def get_address_index(self):
        # ? Get index of this address in cluster_addr_list (equivalent to id)
        for i in range(len(self.cluster_addr_list)):
            if Address(self.cluster_addr_list[i]['ip'], self.cluster_addr_list[i]['port']) == self.address:
                return i
        return -1

    def get_address_index_by_addr(self, addr: Address):
        # ? Get index of this address in cluster_addr_list
        for i in range(len(self.cluster_addr_list)):
            if Address(self.cluster_addr_list[i]['ip'], self.cluster_addr_list[i]['port']) == addr:
                return i
        return -1

    async def __leader_heartbeat(self):
        while self.type == RaftNode.NodeType.LEADER:
            self.__print_log("Sending heartbeat...")

            for addr in self.cluster_addr_list:
                if Address(addr['ip'], addr['port']) == self.address:
                    continue
                self.append_entries(addr)

            # await self.__broadcast_cluster_addr_list()
            await asyncio.sleep(RaftNode.HEARTBEAT_INTERVAL)

    def _set_election_timeout(self, timeout=None):
        if timeout:
            self.election_timeout = timeout
        else:
            random_float = uniform(
                RaftNode.ELECTION_TIMEOUT_MIN, RaftNode.ELECTION_TIMEOUT_MAX)
            self.election_timeout = time.time() + random_float
            self.election_interval = random_float

    def __listen_timeout(self):
        # if self.timeout_thread:
        #     self.timeout_thread.join()
        self.timeout_thread = Thread(
            target=asyncio.run, args=[self.__on_timeout()])
        self.timeout_thread.start()
    

    async def __on_timeout(self):
        """ 
        This async function will run if follower not hearing heartbeat from leader

        1. Follower will swtich to candidate
        2. Candidate will up his term
        3. Start the election 
        """

        has_leader = False
        try:
            while not has_leader and not self.type == RaftNode.NodeType.LEADER:
                is_candidate = self.type == RaftNode.NodeType.CANDIDATE
                is_follower = self.type == RaftNode.NodeType.FOLLOWER
                is_timeout = time.time() > self.election_timeout
                if (is_candidate or is_follower) and is_timeout:
                    
                    if self.cluster_leader_addr is not None:
                        self.__print_log("Leader is found")
                        self.type = RaftNode.NodeType.FOLLOWER
                        has_leader = True

                    if is_follower:
                        self.__print_log("No heartbeat found from leader")
                        self.cluster_leader_addr = None
                        self.type = RaftNode.NodeType.CANDIDATE
                        self.__print_log("Switching to candidate")

                    self.election_term += 1
                    self.__print_log(
                        f"Current election term [{self.election_term}]")
                    await self.__start_election()
                    self._set_election_timeout()
                    self.__listen_timeout()
                    break

                await asyncio.sleep(self.election_interval)
        except KeyboardInterrupt:
            self.__shutdown()

    async def __start_election(self):
        # ? Pas jadi candidate,
        # ? Vote diri sendiri
        # ? Reset Election timer
        # ? Send Request Vote Ke semua server

        self._set_election_timeout()
        self.voted_for = self.get_address_index()
        self.__print_log(f"Start election for term [{self.election_term}]")

        self.vote_count = 1
        await self.__request_votes()

        # ? Kalo dapet majority yes, jadi leader trs send append entries ke semuanya.
        # ? Klo misal dia ternyata discover leader yang punya term lebih gede, balik jadi follower
        # ? klo stalemate, reelection

    async def __request_votes(self):
        request = {
            "term": self.election_term,
            "candidate_id": self.get_address_index(),
            "last_log_index": len(self.log) - 1,
            "last_log_term": self.log[-1][0] if len(self.log) > 0 else 0
        }

        vote_request_tasks = []

        majority_threshold = len(self.cluster_addr_list) // 2 + 1

        # ? async tasks to request vote
        for addr in self.cluster_addr_list:
            addr = Address(addr['ip'], addr['port'])
            if addr == self.address:
                continue
            self.__print_log(f"Requesting vote to {addr.ip}:{addr.port}")
            try:
                # ? Try to request vote async
                task = self.__send_request_async(request,"request_vote",addr)
                vote_request_tasks.append(task)
            except TimeoutError:
                # ? If timeout, continue to next node
                self.__print_log(
                    f"Request vote to {addr.ip}:{addr.port} timeout")
                continue
            except Exception as e:
                # ? If key error, continue to next node
                self.__print_log(
                    f"Request vote to {addr.ip}:{addr.port}. Error: " + str(e))
                continue

        # ? async tasks to get vote response
        for task in asyncio.as_completed(vote_request_tasks):
            try:
                response = await task
                if "vote_granted" in response and response['vote_granted']:
                    self.vote_count += 1
                    self.__print_log(f"+1 Vote granted")
            except Exception as e:
                self.__print_log(f"Error: " + str(e))
                continue
            # Check if majority is reached
            if self.vote_count >= majority_threshold:
                self.__print_log("Majority, elected as leader")
                self.type = RaftNode.NodeType.LEADER
                self.__initialize_as_leader()
                break

    def __try_to_apply_membership(self, contact_addr: Address):
        """ 
        Follower wants to apply membership to leader

        1. Contact the leader first
        2. Kalo gagal coba terus sampe berhasil
        """
        # ? Contact the leader first
        redirected_addr = contact_addr
        response = {
            "status": "redirected",
            "address": {
                "ip":   contact_addr.ip,
                "port": contact_addr.port,
            }
        }

        redirected_addr = Address(
            response["address"]["ip"], response["address"]["port"])
        # ? Retry if not success
        while response.get("status") != "success":
            self.__print_log(
                f"Applying membership for {self.address.ip}:{self.address.port}")
            response = self.__send_request(
                self.address, "apply_membership", redirected_addr)

        self.log = response["log"]
        self.cluster_addr_list = response["cluster_addr_list"]
        self.cluster_leader_addr = response["cluster_leader_addr"]

        request = {
            "cluster_addr_list": self.cluster_addr_list,
        }
        for addr in self.cluster_addr_list:
            addr = Address(addr["ip"], addr["port"])
            if addr == self.address or addr == redirected_addr:
                continue
            self.__send_request(request, "update_cluster_addr_list", addr)

    # ! This is unused!
    async def __broadcast_cluster_addr_list(self):
        """
        Broadcast cluster address list to all nodes
        """
        request = {
            "cluster_addr_list": self.cluster_addr_list,
        }
        self.__print_log(f"Broadcasting cluster address list to all nodes")
        for addr in self.cluster_addr_list:
            addr = Address(addr["ip"], addr["port"])
            if addr == self.cluster_leader_addr:
                continue
            try:
                await self.__send_request_async(request, "update_cluster_addr_list", addr)
            except TimeoutError:
                self.__print_log(
                    f"Broadcast cluster address list to {addr.ip}:{addr.port} timeout")
                continue

    def __send_request(self, request: Any, rpc_name: str, addr: Address) -> "json":
        """ 
        Send Request is invoking the RPC in another server

        Need to check

        1. If the follower is down, just reply follower ignore (tetep ngirim kayak biasa aja walaupun mati)
        """
        # Warning : This method is blocking
        if not isinstance(addr, Address):
            addr = Address(addr["ip"], addr["port"])

        node = ServerProxy(f"http://{addr.ip}:{addr.port}")
        json_request = json.dumps(request)
        rpc_function = getattr(node, rpc_name)
        response = {
            "success": False,
        }
        try:
            response = json.loads(rpc_function(json_request))
            self.__print_log(response)
        except KeyboardInterrupt:
            exit(1)
        except ConnectionRefusedError:
            self.__print_log(f"[{addr}] is not replying (refused, likely down)")    
        except:
            # traceback.print_exc()
            self.__print_log(f"[{addr}] is not replying (nack)")

        return response

    # ! This is unused!
    async def __send_request_async(self, request: Any, rpc_name: str, addr: Address) -> "json":
        """
        send request async will invoke the RPC in another server asynchronously

        Need to check:

        1. If the follower is down, just reply follower ignore (tetep ngirim kayak biasa aja walaupun mati)
        """
        if not isinstance(addr, Address):
            addr = Address(addr["ip"], addr["port"])

        # ? Send request async
        node = aioxmlrpc.client.ServerProxy(f"http://{addr.ip}:{addr.port}")
        json_request = json.dumps(request)
        rpc_function = getattr(node, rpc_name)
        response = {
            "success": False,
        }
        try:
            response = await rpc_function(json_request)
            response = json.loads(response)
            self.__print_log(response)
        except KeyboardInterrupt:
            exit(1)
        except:
            # traceback.print_exc()
            self.__print_log(f"[{addr}] Is not replying (nack)")

        return response

    def _apply_log(self):
        """ 
        This function will apply entries to the state machine
        """
        while self.commit_index > self.last_applied:
            self.last_applied += 1

            if (self.log[self.last_applied][1] == "queue"):
                self.app.enqueue(self.log[self.last_applied][2])
            else:
                self.app.dequeue()

            self.__print_log("State Machine: " + str(self.app))

    # Inter-node RPCs
    def append_entries(self, follower_addr: Address) -> "json":
        """ 
        This function will send heartbeat to follower address
        """
        self.last_heartbeat_received = time.time()

        # Kalo belom punya log kasih
        prev_log_index = len(self.log) - 1
        prev_log_term = 0

        if len(self.log) > 0:
            prev_log_term = self.log[prev_log_index][0]

        append_entry = AppendEntry.Request(
            self.election_term,
            self.cluster_leader_addr,
            prev_log_index,
            prev_log_term,
            [],
            self.commit_index,
        )

        # ? fail-safe for follower_addr
        if not isinstance(follower_addr, Address):
            follower_addr = Address(follower_addr['ip'], follower_addr['port'])

        # ? If follower is not in the cluster, just ignore
        index = self.next_index[str(follower_addr)] if str(
            follower_addr) in self.next_index else 0

        # ? Klo prev nya kelebihan dari log index skrg, rollback sampe ketemu
        if (prev_log_index >= index):
            append_entry.entries = self.log[index+1:]
            self.__print_log(
                f"Sending entries {append_entry.entries} to {follower_addr}")

            request = append_entry.to_dict()
            response = self.__send_request(
                request, "append_entry", follower_addr)

            if (response["success"] == False):
                if (self.next_index[str(follower_addr)] > 0):
                    self.next_index[str(follower_addr)] -= 1
            else:
                self.match_index[str(follower_addr)] = prev_log_index
                self.next_index[str(follower_addr)] = prev_log_index

        else:
            request = append_entry.to_dict()
            response = self.__send_request(
                request, "append_entry", follower_addr)

        return response

    def request_vote(self, request: "json") -> "json":
        """ 
        This RPC function will handle request vote from candidate
        """
        print("Request Vote from", request['candidate_id'])
        request = RequestVote.Request(**request)
        response = RequestVote.Response(self.election_term, False)

        # ? Check if the candidate term is greater than follower term
        if request.term > self.election_term:
            if self.voted_for == -1 or self.voted_for == request.candidate_id:
                self.__print_log(
                    f"Vote for candidate {request.candidate_id} for term {request.term}")
                self.election_term = request.term
                # ? Set voted for to candidate id, become follower
                self.type = RaftNode.NodeType.FOLLOWER
                self.voted_for = request.candidate_id
                self._set_election_timeout()
                response.vote_granted = True
        else:
            # ? Reject vote if candidate term is less than follower term
            self.__print_log(
                f"Reject vote for candidate {request.candidate_id} for term {request.term}")

        print("Response", response.to_dict())

        return response.to_dict()

    # Client RPCs
    def execute(self, json_request: str) -> "json":
        request = json.loads(json_request)
        print(request)
        return response

