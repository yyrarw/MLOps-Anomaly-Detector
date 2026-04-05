from enum import Enum
from typing import Optional


class Severity(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PredictionResult:
    def __init__(self, task):
        self._id: Optional[int] = None
        self._task = task
        self._anomalies = []
        self._valid_rows_count: int = 0
        self._invalid_rows = []
        self._credits_charged: float = 0.0
 
    @property
    def summary(self) -> dict:
        """Сводка: кол-во аномалий, проблемные метрики и ноды."""
        pass
