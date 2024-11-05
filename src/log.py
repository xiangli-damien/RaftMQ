class Log:
    def __init__(self, term, topic, message, operation):
        self.term = term
        self.topic = topic
        self.message = message
        # operation: get = -1; put +1
        self.operation = operation

    def to_dict(self):
        return {
            "term": self.term,
            "topic": self.topic,
            "message": self.message,
            "operation": self.operation,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            term=data["term"],
            topic=data["topic"],
            message=data["message"],
            operation=data["operation"],
        )