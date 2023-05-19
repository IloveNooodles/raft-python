from typing import List
from module.struct.address import Address

class AppendEntry:
    """ 
    Invoked by leader to replicate log entries (§5.3); also used as
    heartbeat (§5.2).

    Arguments:
    1. term leader’s term
    2. leaderId so follower can redirect clients
    3. prevLogIndex index of log entry immediately preceding
    new ones
    4. prevLogTerm term of prevLogIndex entry
    5. entries[] log entries to store (empty for heartbeat;
    may send more than one for efficiency)
    6. leaderCommit leader’s commitIndex

    Results:
    1. term currentTerm, for leader to update itself
    2. success true if follower contained entry matching
    prevLogIndex and prevLogTerm

    Receiver implementation:
    1. Reply false if term < currentTerm (§5.1)
    2. Reply false if log doesn’t contain an entry at prevLogIndex
    whose term matches prevLogTerm (§5.3)
    3. If an existing entry conflicts with a new one (same index
    but different terms), delete the existing entry and all that
    follow it (§5.3)
    4. Append any new entries not already in the log
    5. If leaderCommit > commitIndex, set commitIndex =
    min(leaderCommit, index of last new entry)
    """
    pass

    class Request:
        def __init__(self, 
                     term, 
                     leader_addr, 
                     prev_log_index, 
                     prev_log_term, 
                     entries, 
                     leader_commit_index) -> None:
            
            self.term               : int       = term
            self.leader_addr        : Address   = leader_addr
            self.prev_log_index     : int       = prev_log_index
            self.prev_log_term      : int       = prev_log_term
            self.entries            : List[str] = entries
            self.leader_commit_index: int       = leader_commit_index

        def toDict(self) -> dict:
            return {"term": self.term, 
                    "leader_addr": {
                        "ip": self.leader_addr.ip,
                        "port": self.leader_addr.port
                    }, 
                    "prev_log_index": self.prev_log_index, 
                    "prev_log_term": self.prev_log_term, 
                    "entries": self.entries, 
                    "leader_commit_index": self.leader_commit_index}

    class Response:
        def __init__(self, term, success) -> None:
            self.term               : int   = term
            self.success            : bool  = success

        def toDict(self) -> dict:
            return {"term": self.term, 
                    "success": self.success,}