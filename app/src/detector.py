from abc import ABC, abstractmethod
from typing import Optional


class AnomalyDetector(ABC):
    """Базовый класс для всех моделей детекции аномалий."""
 
    def __init__(self, name: str, description: str, cost_per_request: float):
        self._id: Optional[int] = None
        self._name: str = name
        self._description: str = description
        self._cost_per_request: float = cost_per_request
 
    @abstractmethod
    def detect(self, data):
        """Принимает валидные данные, возвращает список аномалий."""
        pass
 
    @property
    def cost(self) -> float:
        return self._cost_per_request
