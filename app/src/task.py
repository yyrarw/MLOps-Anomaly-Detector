from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class MLTask:
    def __init__(self, user, model, input_file_path: str):
        self._id = None
        self._user  = user
        self._model = model
        self._input_file_path: str = input_file_path
        self._status: TaskStatus = TaskStatus.PENDING
 
    def execute(self, validator):
        """Валидация -> детекция -> результат."""
        pass
