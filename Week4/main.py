from custom_classes import Calculator

calculator = Calculator()
calculator.add(10, 5)
calculator.multiply(calculator._current_val, 2)
calculator.divide(calculator._current_val, 3)

print(calculator._current_val)
