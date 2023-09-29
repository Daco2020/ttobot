class BotException(Exception):
    def __init__(self, message: str) -> None:
        self.message = f"⚠️ {message} ⚠️"
        super().__init__(self.message)
