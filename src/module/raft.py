import asyncio
import json
import socket
import time
import traceback
from enum import Enum
from random import random
from threading import Thread
from typing import Any, List, Dict
from xmlrpc.client import ServerProxy
import threading

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
    ELECTION_TIMEOUT_MIN = 2
    ELECTION_TIMEOUT_MAX = 3
    RPC_TIMEOUT = 0.5

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
        random_float = random()
        socket.setdefaulttimeout(RaftNode.RPC_TIMEOUT)
        self.leader_id = -1
        self.address:             Address = addr
        self.type:                RaftNode.NodeType = RaftNode.NodeType.FOLLOWER
        self.log:                 List[int, str,
                                       str] = []  # [term, command, args]
        self.entry:               List[str, str] = []
        self.app:                 MessageQueue = application

        # Election stuff
        self.election_term:       int = 0
        self.election_timeout:    int = time.time(
        ) + RaftNode.ELECTION_TIMEOUT_MIN + random_float
        self.election_interval:   int = RaftNode.ELECTION_TIMEOUT_MIN + random_float
        self.voted_for:           int = -1
        self.vote_count:          int = 0

        self.commit_index:        int = 0
        self.last_applied:        int = 0
        self.last_heartbeat_received: int = time.time()

        # Reinit after election
        self.match_index:         Dict[str, int] = {}
        self.next_index:          Dict[str, int] = {}

        self.cluster_addr_list:   List[Address] = []
        self.cluster_leader_addr: Address = None

        if contact_addr is None:
            self.cluster_addr_list.append(self.address)
            self.__initialize_as_leader()
        else:
            self.__listen_timeout()
            self.__try_to_apply_membership(contact_addr)

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
              f"[{time.strftime('%H:%M:%S')}]" + color + f"[{self.type}]" + Colors.ENDC + f"{text}")

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

    def __get_address_index(self):
        # ? Get index of this address in cluster_addr_list (equivalent to id)
        for i in range(len(self.cluster_addr_list)):
            if Address(self.cluster_addr_list[i]['ip'], self.cluster_addr_list[i]['port']) == self.address:
                return i
        return -1

    def __get_address_index_by_addr(self, addr: Address):
        # ? Get index of this address in cluster_addr_list
        for i in range(len(self.cluster_addr_list)):
            if Address(self.cluster_addr_list[i]['ip'], self.cluster_addr_list[i]['port']) == addr:
                return i
        return -1

    async def __leader_heartbeat(self):
        while True:
            self.__print_log("Sending heartbeat...")

            for addr in self.cluster_addr_list:
                if Address(addr['ip'], addr['port']) == self.address:
                    continue
                self.heartbeat(addr)

            await self.__broadcast_cluster_addr_list()
            await asyncio.sleep(RaftNode.HEARTBEAT_INTERVAL)

    def _set_election_timeout(self, timeout=None):
        if timeout:
            self.election_timeout = timeout
        else:
            random_float = random()
            self.election_timeout = time.time() + RaftNode.ELECTION_TIMEOUT_MIN + random_float
            self.election_interval = RaftNode.ELECTION_TIMEOUT_MIN + random_float

    def __listen_timeout(self):
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
        while True:
            is_candidate = self.type == RaftNode.NodeType.CANDIDATE
            is_follower = self.type == RaftNode.NodeType.FOLLOWER
            is_timeout = time.time() > self.election_timeout
            if (is_candidate or is_follower) and is_timeout:

                if is_follower:
                    self.__print_log("No heartbeat found from leader")
                    self.type = RaftNode.NodeType.CANDIDATE
                    self.__print_log("Switching to candidate")

                self.election_term += 1
                self.__print_log(
                    f"Current election term [{self.election_term}]")
                await self.__start_election()
                break

            await asyncio.sleep(self.election_interval)

    async def __start_election(self):
        # ? Pas jadi candidate,
        # ? Vote diri sendiri
        # ? Reset Election timer
        # ? Send Request Vote Ke semua server

        self._set_election_timeout()
        self.voted_for = self.__get_address_index()
        self.__print_log(f"Start election for term [{self.election_term}]")

        self.vote_count = 1
        await self.__request_votes()

        # ? Kalo dapet majority yes, jadi leader trs send append entries ke semuanya.
        # ? Klo misal dia ternyata discover leader yang punya term lebih gede, balik jadi follower
        # ? klo stalemate, reelection

    async def __request_votes(self):
        request = {
            "term": self.election_term,
            "candidate_id": self.__get_address_index(),
            "last_log_index": len(self.log) - 1,
            "last_log_term": self.log[-1][0] if len(self.log) > 0 else 0
        }

        vote_request_threads = []

        majority_threshold = len(self.cluster_addr_list) // 2 + 1

        for addr in self.cluster_addr_list:
            addr = Address(addr['ip'], addr['port'])
            if addr == self.address:
                continue
            self.__print_log(f"Requesting vote to {addr.ip}:{addr.port}")
            try:
                # ? Try to request vote
                thread = ThreadWithValue(target=asyncio.run, args=[
                                         self.__send_request_async(request, "request_vote", addr)])
                vote_request_threads.append(thread)
                thread.start()
            except TimeoutError:
                # ? If timeout, continue to next node
                self.__print_log(
                    f"Request vote to {addr.ip}:{addr.port} timeout")
                continue
            except KeyError:
                # ? If key error, continue to next node
                self.__print_log(
                    f"Request vote to {addr.ip}:{addr.port} failed")
                continue

        # ? async tasks to get vote response
        for thread in vote_request_threads:
            result = thread.join()
            if "vote_granted" in result:
                if result["vote_granted"]:
                    self.vote_count += 1
                    self.__print_log(f"+1 Vote granted")

            # Check if majority is reached
            if self.vote_count >= majority_threshold:
                break

    def __try_to_apply_membership(self, contact_addr: Address):
        """ 
        Follower wants to apply membership to leader

        1. Contact the leader first
        2. Kalo gagal coba terus sampe berhasil
        """
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
        # Retry if not success
        while response.get("status") != "success":
            self.__print_log(
                f"Applying membership for {self.address.ip}:{self.address.port}")
            response = self.__send_request(
                self.address, "apply_membership", redirected_addr)

        self.log = response["log"]
        self.cluster_addr_list = response["cluster_addr_list"]
        self.cluster_leader_addr = redirected_addr

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
        node = ServerProxy(f"http://{addr.ip}:{addr.port}")
        json_request = json.dumps(request)
        rpc_function = getattr(node, rpc_name)
        response = {
            "success": False,
        }
        try:
            # response     = await rpc_function(json_request)
            # response     = json.loads(response)
            response = json.loads(rpc_function(json_request))
            self.__print_log(response)
        except KeyboardInterrupt:
            exit(1)
        except:
            # traceback.print_exc()
            self.__print_log(f"[{addr}] Is not replying (nack)")

        return response

    async def __send_request_async(self, request: Any, rpc_name: str, addr: Address) -> "json":
        """ 
        This is the async version of send request so that it wont block the main thread
        """
        node = ServerProxy(f"http://{addr.ip}:{addr.port}")
        json_request = json.dumps(request)
        rpc_function = getattr(node, rpc_name)
        response = {
            "success": False,
        }
        try:
            response = await json.loads(rpc_function(json_request))
            # response     = json.loads(response)
            # response     = json.loads(rpc_function(json_request))
            self.__print_log(response)
        except KeyboardInterrupt:
            exit(1)
        except:
            # traceback.print_exc()
            self.__print_log(f"[{addr}] Is not replying (nack)")

        return response

    # Inter-node RPCs
    def heartbeat(self, follower_addr: Address) -> "json":
        """ 
        This function will send heartbeat to follower address
        """
        self.last_heartbeat_received = time.time()
        last_log_index = len(self.log) - 1 if len(self.log) > 0 else 0

        append_entry = AppendEntry.Request(
            self.election_term,
            self.cluster_leader_addr,
            last_log_index,
            self.log[-1][0] if len(self.log) > 0 else 0,
            self.entry,
            self.commit_index,
        )

        # ? fail-safe for follower_addr
        if not isinstance(follower_addr, Address):
            follower_addr = Address(follower_addr['ip'], follower_addr['port'])

        # ? If follower is not in the cluster, just ignore
        index = self.next_index[str(follower_addr)] if str(
            follower_addr) in self.next_index else 0

        if (last_log_index >= index):
            append_entry.entries = self.log[index:]
            self.__print_log(
                f"Sending entries from {index} to {last_log_index} to {follower_addr}")

            request = append_entry.toDict()
            response = self.__send_request(
                request, "append_entry", follower_addr)

            if (response["success"] == False):
                self.next_index[str(follower_addr)] -= 1
            else:
                self.match_index[str(follower_addr)] = last_log_index
                self.next_index[str(follower_addr)] = last_log_index

        else:
            request = append_entry.toDict()
            response = self.__send_request(
                request, "append_entry", follower_addr)

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

        print("Response", response.toDict())

        return response.toDict()

    # Client RPCs

    def execute(self, json_request: str) -> "json":
        request = json.loads(json_request)
        # TODO : Implement execute

        # ? Kalo commitIndex > lastApplied, increment lastApplied trs commit ?

        # ? Kalo ada request yang punya TERM lebih gede dari term server ini, convert ke follower.
        return response


# TODO for election:
# Todo: handle vote request response & count votes
# detecting majority (looks like done)
# change state to leader if majority (looks like done)
# Todo: broadcast address list to all nodes
# Todo: make async
# Todo: Handle case when a candidate fails to get majority votes
# Todo: handle listen to timeout again after failed election
# Inti permasalahan sekarang: requestnya gak masuk karena ke block saat dia jadi candidate
