class BotException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class ClientException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)
