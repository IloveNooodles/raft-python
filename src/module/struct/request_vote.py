class RequestVote:
    """ 
    Arguments:
    1. term candidate’s term
    2. candidateId candidate requesting vote
    3. lastLogIndex index of candidate’s last log entry (§5.4)
    4. lastLogTerm term of candidate’s last log entry (§5.4)

    Results:
    1. term currentTerm, for candidate to update itself
    2. voteGranted true means candidate received vote

    Receiver implementation:
    1. Reply false if term < currentTerm (§5.1)
    2. If votedFor is null or candidateId, and candidate’s log is at
    least as up-to-date as receiver’s log, grant vote (§5.2, §5.4)
    """
    pass

    class Request:
        def __init__(self) -> None:
            self.term: int = 0
            self.candidate_id: int = 0
            self.last_log_index: int = 0
            self.last_log_term: int = 0

        def to_dict(self) -> dict:
            return {
                "term": self.term,
                "candidate_id": self.candidate_id,
                "last_log_index": self.last_log_index,
                "last_log_term": self.last_log_term
            }

    class Response:
        def __init__(self) -> None:
            self.term: int = 0
            self.vote_granted: bool = False

        def to_dict(self) -> dict:
            return {
                "term": self.term,
                "vote_granted": self.vote_granted,
            }
