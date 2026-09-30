"""
Safe Mathematical Calculator Tool for Sarala AI.
Uses Python's Abstract Syntax Tree (AST) parser to strictly evaluate mathematical expressions.
CRITICAL SECURITY:
- Absolutely NO Python eval or exec execution
- Absolutely NO arbitrary Python code execution
- Whitelisted operations and mathematical functions only
"""

import ast
import math
import operator
from typing import Dict, Any, Union, Callable
from ai.tools.errors import InvalidArgumentsError


# Supported binary operators
_SAFE_OPERATORS: Dict[Any, Callable[[Any, Any], Union[int, float]]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Supported unary operators
_SAFE_UNARY_OPERATORS: Dict[Any, Callable[[Any], Union[int, float]]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Whitelisted mathematical constants
_SAFE_CONSTANTS: Dict[str, Union[int, float]] = {
    "pi": math.pi,
    "e": math.e,
}

# Whitelisted mathematical functions
_SAFE_FUNCTIONS: Dict[str, Callable[..., Any]] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sqrt": math.sqrt,
    "ceil": math.ceil,
    "floor": math.floor,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "exp": math.exp,
}


def _safe_eval_node(node: ast.AST) -> Union[int, float]:
    """Recursively evaluates an AST node under strict mathematical bounds."""
    if isinstance(node, ast.Expression):
        return _safe_eval_node(node.body)

    # Numeric constants
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise InvalidArgumentsError(f"Unsupported constant type in math expression: {type(node.value).__name__}")

    # Legacy python < 3.8 AST compatibility for numbers
    if hasattr(ast, "Num") and isinstance(node, getattr(ast, "Num")):
        return getattr(node, "n")

    # Binary Operations: a + b, a * b, a ** b
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _SAFE_OPERATORS:
            raise InvalidArgumentsError(f"Unsupported mathematical operator: {op_type.__name__}")
        
        left_val = _safe_eval_node(node.left)
        right_val = _safe_eval_node(node.right)

        # Safety bound for exponentiation to prevent CPU denial of service
        if op_type is ast.Pow:
            if abs(right_val) > 1000 or (abs(left_val) > 1000 and right_val > 10):
                raise InvalidArgumentsError("Exponentiation exceeds maximum safe compute limits.")

        # Division by zero protection
        if op_type in (ast.Div, ast.FloorDiv, ast.Mod) and right_val == 0:
            raise InvalidArgumentsError("Division by zero is undefined.")

        op_func = _SAFE_OPERATORS[op_type]
        return op_func(left_val, right_val)

    # Unary Operations: -a, +a
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _SAFE_UNARY_OPERATORS:
            raise InvalidArgumentsError(f"Unsupported unary operator: {op_type.__name__}")
        operand_val = _safe_eval_node(node.operand)
        return _SAFE_UNARY_OPERATORS[op_type](operand_val)

    # Function calls: sqrt(144), round(3.14159, 2)
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise InvalidArgumentsError("Arbitrary function or method execution is forbidden.")
        func_name = node.func.id
        if func_name not in _SAFE_FUNCTIONS:
            raise InvalidArgumentsError(f"Function '{func_name}' is not in the mathematical whitelist.")
        
        args = [_safe_eval_node(arg) for arg in node.args]
        func = _SAFE_FUNCTIONS[func_name]
        try:
            val = func(*args)
            if isinstance(val, (int, float)):
                return val
            raise InvalidArgumentsError(f"Function '{func_name}' returned a non-numeric value.")
        except Exception as err:
            if isinstance(err, InvalidArgumentsError):
                raise
            raise InvalidArgumentsError(f"Math evaluation error in '{func_name}': {str(err)}")

    # Named Constants (e.g. pi, e)
    if isinstance(node, ast.Name):
        if node.id in _SAFE_CONSTANTS:
            return _SAFE_CONSTANTS[node.id]
        raise InvalidArgumentsError(f"Variable or identifier '{node.id}' is not recognized in calculator.")

    raise InvalidArgumentsError(f"Unsupported syntax in expression: {type(node).__name__}")


def calculate(expression: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Evaluates a mathematical expression safely using AST parsing.
    Returns: {"expression": str, "result": float/int}
    """
    if not expression or not isinstance(expression, str):
        raise InvalidArgumentsError("Expression parameter must be a non-empty string.")

    clean_expr = expression.strip()
    if len(clean_expr) > 200:
        raise InvalidArgumentsError("Expression length exceeds maximum permitted limit (200 characters).")

    # Reject obvious dangerous keywords before parsing
    dangerous_keywords = ["import", "eval", "exec", "os", "sys", "subprocess", "open", "__", "lambda", "class", "def"]
    for kw in dangerous_keywords:
        if kw in clean_expr.lower():
            raise InvalidArgumentsError(f"Prohibited keyword '{kw}' detected in expression.")

    try:
        parsed = ast.parse(clean_expr, mode="eval")
        result = _safe_eval_node(parsed)

        # Handle float precision rounding nicely
        if isinstance(result, float):
            if float.is_integer(result):
                result = int(result)
            else:
                result = round(result, 8)

        return {
            "expression": clean_expr,
            "result": result,
            "formatted": f"{clean_expr} = {result}"
        }
    except InvalidArgumentsError:
        raise
    except SyntaxError as e:
        raise InvalidArgumentsError(f"Invalid mathematical syntax: {e.msg}")
    except Exception as e:
        raise InvalidArgumentsError(f"Failed to calculate expression: {str(e)}")
