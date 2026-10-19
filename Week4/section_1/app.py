import math

from flask import Flask, jsonify, render_template, request
from custom_classes import Calculator

app = Flask(__name__)


@app.get("/")
def calculator():
    return render_template("index.html")


@app.post("/api/calculate")
def calculate():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Request body must be a JSON object."), 400

    operator = data.get("operator")
    if not isinstance(operator, str) or operator not in {"+", "-", "*", "/"}:
        return jsonify(error="Operator must be one of +, -, *, or /."), 400

    operands = data.get("operands")
    if not isinstance(operands, list) or len(operands) != 2:
        return jsonify(error="Provide exactly two numeric operands."), 400

    if any(
        isinstance(value, bool) or not isinstance(value, (int, float))
        for value in operands
    ):
        return jsonify(error="Both operands must be numbers."), 400
    try:
        left, right = (float(value) for value in operands)
    except (TypeError, ValueError):
        return jsonify(error="Both operands must be numbers."), 400

    if not math.isfinite(left) or not math.isfinite(right):
        return jsonify(error="Operands must be finite numbers."), 400
    calculator = Calculator()
    operations = {
        "+": calculator.add,
        "-": calculator.subtract,
        "*": calculator.multiply,
        "/": calculator.divide,
    }
    try:
        value = operations[operator](left, right)
    except ValueError as error:
        return jsonify(error=str(error) + "."), 400

    if not math.isfinite(value):
        return jsonify(error="Result is outside the supported numeric range."), 400
    return jsonify(result=value)


if __name__ == "__main__":
    app.run(debug=True)
