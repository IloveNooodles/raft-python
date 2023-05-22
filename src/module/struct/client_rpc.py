from typing import Dict
from enum import Enum
from module.struct.address import Address
import json


class ClientRPC:

    SUCCESS = "SUCCESS"
    REDIRECTED = "REDIRECTED"
    FAILED = "FAILED"

    class Request:
        def __init__(self, request_id: int, command: str, args: str) -> None:
            self.request_id = request_id
            self.command = command
            self.args = args

        def to_dict(self) -> Dict:
            return {
                "request_id": self.request_id,
                "command": self.command,
                "args": self.args
            }

    class Response:
        def __init__(self, status: str, address: Address = None) -> None:
            self.status = status
            self.address = address

        def to_dict(self) -> Dict:
            if not self.address:
                return {
                    "status": self.status
                }

            return {
                "status": self.status,
                "address": {
                    "ip": self.address.ip,
                    "port": self.address.port
                }
            }
