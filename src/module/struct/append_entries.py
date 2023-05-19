from typing import List


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
      def __init__(self) -> None:
          self.term: int = 0
          self.leader_id: int = 0
          self.prev_log_index: int = 0
          self.prev_log_term: int = 0
          self.entries: List[str] = []
          self.leader_commit_index: int = 0
  
  class Response:
      def __init__(self) -> None:
          self.term: int = 0
          self.success: bool = False
          self.conflict_index: int = -1
          self.conflict_term: int = -1