from enum import Enum
from typing import Optional


class UserRole(Enum):
    USER = "user"
    ADMIN = "admin"


class User:
    def __init__(self, email: str, hashed_password: str, role: UserRole = UserRole.USER):
        self._id: Optional[int] = None
        self._email: str = email
        self._hashed_password: str = hashed_password
        self._role: UserRole = role
        self._balance: float = 0.0
 
    def check_balance(self, amount: float) -> bool:
        return self._balance >= amount
 
    def top_up(self, amount: float) -> None:
        """Пополнение баланса."""
        if amount <= 0:
            raise ValueError("Сумма пополнения должна быть положительной")
        self._balance += amount
 
    def debit(self, amount: float) -> None:
        """Списание с баланса."""
        if not self.check_balance(amount):
            raise ValueError("Недостаточно кредитов")
        self._balance -= amount
 
    @property
    def balance(self) -> float:
        return self._balance
 
    @property
    def is_admin(self) -> bool:
        return self._role == UserRole.ADMIN
