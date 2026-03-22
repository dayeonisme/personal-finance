from abc import ABC, abstractmethod
from datetime import date
from models import Transaction


class AuthenticationError(Exception):
    """Raised when crawler session is expired or login fails."""


class BaseCrawler(ABC):
    def __enter__(self) -> "BaseCrawler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        try:
            self.logout()
        except Exception:
            pass  # never mask the original exception
        return False  # re-raise any exception from the with block

    @abstractmethod
    def login(self) -> None: ...

    @abstractmethod
    def fetch_transactions(self, start_date: date, end_date: date) -> list[Transaction]: ...

    @abstractmethod
    def logout(self) -> None: ...
