from module.struct.address import Address

class MessageQueue():
    def __init__(self):
        self.queue   = []

    def __str__ (self):
        return f"{self.queue}"
    
    def enqueu(self, message: str):
        self.queue.append(message)

    def dequeu(self):
        return self.queue.pop(0)