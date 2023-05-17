import asyncio
import json
import socket
import time
from enum import Enum
from threading import Thread
from typing import Any, List
from xmlrpc.client import ServerProxy

from module.struct.address import Address
from module.struct.message_queue import MessageQueue


class RaftNode:
    """ 
    Implementation of Raft Node
    
    1. Election time is mostly between T and 2T (150ms - 300ms)
    2. If server is follower and not receiveing anything from client, upgrade to candidate
    3. Candidate will start election
    """
    HEARTBEAT_INTERVAL   = 1
    ELECTION_TIMEOUT_MIN = 2
    ELECTION_TIMEOUT_MAX = 3
    RPC_TIMEOUT          = 0.5

    class NodeType(Enum):
        LEADER    = 1
        CANDIDATE = 2
        FOLLOWER  = 3
        
        def __str__(self) -> str:
            return self.name

    def __init__(self, application : Any, addr: Address, contact_addr: Address = None):
        socket.setdefaulttimeout(RaftNode.RPC_TIMEOUT)
        self.address:             Address           = addr
        self.type:                RaftNode.NodeType = RaftNode.NodeType.FOLLOWER
        self.log:                 List[str, str]    = []
        self.app:                 Any               = application
        self.election_term:       int               = 0
        self.cluster_addr_list:   List[Address]     = []
        self.cluster_leader_addr: Address           = None
        if contact_addr is None:
            self.cluster_addr_list.append(self.address)
            self.__initialize_as_leader()
        else:
            self.__try_to_apply_membership(contact_addr)

    # Internal Raft Node methods
    def __print_log(self, text: str):
        print(f"[{self.address}] [{time.strftime('%H:%M:%S')}] [{self.type}] {text}")

    def __initialize_as_leader(self):
        self.__print_log("Initialize as leader node...")
        self.cluster_leader_addr = self.address
        self.type                = RaftNode.NodeType.LEADER
        request = {
            "cluster_leader_addr": self.address
        }
        # TODO : Inform to all node this is new leader
        self.heartbeat_thread = Thread(target=asyncio.run,args=[self.__leader_heartbeat()])
        self.heartbeat_thread.start()

    async def __leader_heartbeat(self):
        while True:
            self.__print_log("Sending heartbeat...")
            for addr in self.cluster_addr_list:
                if addr == self.address:
                    continue
                self.heartbeat(addr)
            await asyncio.sleep(RaftNode.HEARTBEAT_INTERVAL)

    def __try_to_apply_membership(self, contact_addr: Address):
        """ 
        Follower wants to apply membership to leader
        
        1. Contact the leader first
        """
        redirected_addr = contact_addr
        response = {
            "status": "redirected",
            "address": {
                "ip":   contact_addr.ip,
                "port": contact_addr.port,
            } 
        }

        while response["status"] != "success":
            redirected_addr = Address(response["address"]["ip"], response["address"]["port"])
            response        = self.__send_request(self.address, "apply_membership", redirected_addr)
        
        self.log.append(response["log"])
        self.cluster_addr_list   = response["cluster_addr_list"]
        self.cluster_leader_addr = redirected_addr

    def __send_request(self, request: Any, rpc_name: str, addr: Address) -> "json":
        """ 
        Send Request is invoking the RPC in another server
        
        Need to check
        
        1. If the follower is down, just reply follower ignore (tetep ngirim kayak biasa aja walaupun mati)
        """
        # Warning : This method is blocking
        node         = ServerProxy(f"http://{addr.ip}:{addr.port}")
        json_request = json.dumps(request)
        rpc_function = getattr(node, rpc_name)
        response = {
            "heartbeat_response": "nack",
            "address":            self.address,
        }
        try:
          response     = json.loads(rpc_function(json_request))
          self.__print_log(response)
        except:
          self.__print_log(f"[{addr}] Is not replying (nack)")
        
        return response

    # Inter-node RPCs
    def heartbeat(self, follower_addr: Address) -> "json":
        """ 
        This function will send heartbeat to follower address
        """
        response = {
            "heartbeat_response": "nack",
            "address":            self.address,
        }

        while response["heartbeat_response"] != "ack":
            request = {
                "ip":   self.address.ip,
                "port": self.address.port,
            }
            response = self.__send_request(request, "heartbeat", follower_addr)

    # Client RPCs 
    def execute(self, json_request: str) -> "json":
        request = json.loads(json_request)
        # TODO : Implement execute
        return response
