"""
A small, safe expression evaluator for the admin-configurable driven_distance
charge formula.

Supports: the variable `km`, numeric constants, + - * operators, unary minus,
parentheses, and max(...)/min(...) with any number of arguments. Deliberately
nothing else (no division, no names besides km, no attribute/call access to
anything but max/min) since this expression comes from an admin text field
and is evaluated on every driven_distance contribution.
"""

import ast
import re

ALLOWED_FUNCTIONS = {"max": max, "min": min}


class FormulaError(ValueError):
    pass


def _preprocess(expr: str) -> str:
    # allow 'x' as an alternative multiplication symbol, e.g. "km x 0.88"
    return re.sub(r"\bx\b", "*", expr)


def _eval_node(node, km):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, km)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise FormulaError("only numbers are allowed as constants")

    if isinstance(node, ast.Name):
        if node.id == "km":
            return float(km)
        raise FormulaError(f"unknown variable '{node.id}' (only 'km' is allowed)")

    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, km)
        right = _eval_node(node.right, km)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        raise FormulaError("only +, -, * are allowed")

    if isinstance(node, ast.UnaryOp):
        value = _eval_node(node.operand, km)
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return value
        raise FormulaError("unsupported unary operator")

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in ALLOWED_FUNCTIONS:
            raise FormulaError("only max(...) and min(...) functions are allowed")
        if node.keywords:
            raise FormulaError("keyword arguments are not allowed")
        args = [_eval_node(a, km) for a in node.args]
        if len(args) < 2:
            raise FormulaError(f"{node.func.id}(...) needs at least 2 arguments")
        return ALLOWED_FUNCTIONS[node.func.id](*args)

    raise FormulaError(f"unsupported expression: {type(node).__name__}")


def evaluate(expr: str, km: float) -> float:
    """Evaluates a distance-charge formula for the given km. Raises
    FormulaError on any invalid or disallowed expression."""
    try:
        tree = ast.parse(_preprocess(expr), mode="eval")
    except SyntaxError as e:
        raise FormulaError(f"invalid expression: {e}") from e
    return _eval_node(tree, km)


def validate(expr: str) -> None:
    """Raises FormulaError if the expression can't be evaluated at all."""
    evaluate(expr, km=1.0)
