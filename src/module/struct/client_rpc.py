from typing import Dict


class ClientRPC:
    class Request:
        def __init__(self, request_id: int, command: str, args: str) -> None:
            self.request_id = request_id
            self.command = command
            self.args = str

        def to_dict(self) -> Dict:
            return {
                "request_id": self.request_id,
                "command": self.command,
                "args": self.args
            }
