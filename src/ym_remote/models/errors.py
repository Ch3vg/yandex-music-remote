class RemoteError(Exception):
    """Ошибка, текст которой можно отдать пульту."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
