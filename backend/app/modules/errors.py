"""Errors raised by use cases and translated by HTTP adapters."""


class UseCaseError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(message)
