from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class TransactionType(Enum):
    TOPUP = "topup"
    DEBIT = "debit"


class Transaction(ABC):
    def __init__(self, user, amount: float, task = None):
        self._id: Optional[int] = None
        self._user  = user
        self._amount: float = amount
        self._task = task
 
    @abstractmethod
    def apply(self):
        pass
 
 
class TopUpTransaction(Transaction):
    """Пополнение баланса."""
 
    def apply(self) -> None:
        pass
 
 
class DebitTransaction(Transaction):
    """Списание за выполненную ML-задачу."""
 
    def apply(self) -> None:
        pass
