from typing import Protocol


class DocumentStorage(Protocol):
    def write(self, key: str, data: bytes) -> None: ...
    def read(self, key: str, max_bytes: int) -> bytes: ...


class DocumentTooLargeError(Exception):
    pass
