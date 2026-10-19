class Calculator:
    def __init__(self) -> None:
        self._current_val:float = 0.0

    def add(self, x: float, y: float) -> None:
        self._current_val = x + y
    def subtract(self, x: float, y: float) -> None:
        self._current_val = x - y
    def multiply(self, x: float, y: float) -> None:
        self._current_val = x * y
    def divide(self, x: float, y: float) -> float:
        if y == 0:
            raise ValueError("Cannot divide by zero")
        self._current_val = x / y
        return self._current_val
