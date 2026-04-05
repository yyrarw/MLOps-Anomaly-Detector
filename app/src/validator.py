class DataValidator:
    """Разделяет входные строки на валидные и ошибочные."""
    
    def __init__(self, supported_metrics):
        self.supported_metrics = supported_metrics
 
    def validate(self, rows):
        """Возвращает валидные и не валидные метрики."""
        pass