from module.struct.address import Address


class MessageQueue:
    def __init__(self):
        self.queue = []

    def __str__(self):
        return f"{self.queue}"

    def enqueue(self, message: str):
        self.queue.append(message)

    def dequeue(self):
        cur_len = len(self.queue)
        if cur_len <= 0:
            return None

        return self.queue.pop(0)
