import dspy
import re
import ast
import operator
import math
from typing import Dict, Any, Tuple, Optional, List
from dataclasses import dataclass
from enum import Enum
import traceback


class CalculationComplexity(str, Enum):
    SIMPLE = "simple"  # Basic arithmetic: +, -, *, /
    INTERMEDIATE = "intermediate"  # Powers, square roots, percentages
    ADVANCED = "advanced"  # Trigonometry, logarithms, complex expressions


@dataclass
class CalculationRequest:
    expression: str
    complexity: CalculationComplexity
    numbers: List[float]
    operations: List[str]
    confidence: float


@dataclass
class CalculationResult:
    success: bool
    result: Optional[float]
    formatted_result: str
    explanation: str
    error_message: Optional[str] = None
    calculation_steps: List[str] = None
    execution_time: float = 0.0


class ArithmeticIntentClassifier(dspy.Signature):
    """Classify whether a user input contains arithmetic intent and extract calculation details."""
    
    user_input = dspy.InputField(desc="User's message that may contain arithmetic operations")
    
    is_arithmetic = dspy.OutputField(desc="True if the input contains arithmetic intent, False otherwise")
    confidence = dspy.OutputField(desc="Confidence score from 0.0 to 1.0 for the arithmetic classification")
    mathematical_expression = dspy.OutputField(desc="The mathematical expression extracted from the input, or empty if none")
    operation_type = dspy.OutputField(desc="Type of operation: basic, percentage, power, trigonometry, or complex")
    explanation = dspy.OutputField(desc="Brief explanation of what arithmetic operation was detected")


class ExpressionSanitizer(dspy.Signature):
    """Clean and standardize mathematical expressions for safe evaluation."""
    
    raw_expression = dspy.InputField(desc="Raw mathematical expression from user input")
    
    sanitized_expression = dspy.OutputField(desc="Clean, safe mathematical expression ready for evaluation")
    is_safe = dspy.OutputField(desc="True if the expression is safe to evaluate, False if potentially dangerous")
    normalization_notes = dspy.OutputField(desc="Notes about what was changed during sanitization")


class CalculationExplainer(dspy.Signature):
    """Generate human-friendly explanations for mathematical calculations."""
    
    original_expression = dspy.InputField(desc="The original mathematical expression")
    result = dspy.InputField(desc="The calculated result")
    calculation_steps = dspy.InputField(desc="Step-by-step calculation process")
    
    explanation = dspy.OutputField(desc="Human-friendly explanation of the calculation and result")
    confidence_note = dspy.OutputField(desc="Note about the reliability of the calculation")


class DSPyCalculatorTool:
    """
    Advanced calculator tool using DSPy for intelligent arithmetic intent detection,
    expression parsing, safe evaluation, and error handling.
    """
    
    def __init__(self, lm_model: str = "gpt-3.5-turbo"):
        # Initialize DSPy with a language model
        self.lm = dspy.OpenAI(model=lm_model, max_tokens=1000, temperature=0.1)
        dspy.settings.configure(lm=self.lm)
        
        # Initialize DSPy modules
        self.intent_classifier = dspy.Predict(ArithmeticIntentClassifier)
        self.expression_sanitizer = dspy.Predict(ExpressionSanitizer)
        self.calculation_explainer = dspy.Predict(CalculationExplainer)
        
        # Safe mathematical operations
        self.safe_operations = {
            '+': operator.add,
            '-': operator.sub,
            '*': operator.mul,
            '/': operator.truediv,
            '//': operator.floordiv,
            '%': operator.mod,
            '**': operator.pow,
            '^': operator.pow,  # Alternative power notation
            'sqrt': math.sqrt,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'log': math.log,
            'ln': math.log,
            'log10': math.log10,
            'exp': math.exp,
            'abs': abs,
            'round': round,
            'floor': math.floor,
            'ceil': math.ceil,
            'pi': math.pi,
            'e': math.e
        }
        
        # Track calculation history for learning
        self.calculation_history: List[Dict[str, Any]] = []
    
    async def detect_arithmetic_intent(self, user_input: str) -> Tuple[bool, float, CalculationRequest]:
        """
        Use DSPy to detect arithmetic intent in user input
        
        Args:
            user_input: Raw user message
            
        Returns:
            Tuple of (is_arithmetic, confidence, calculation_request)
        """
        try:
            # Use DSPy to classify the input
            prediction = self.intent_classifier(user_input=user_input)
            
            is_arithmetic = prediction.is_arithmetic.lower() in ['true', 'yes', '1']
            confidence = float(prediction.confidence) if prediction.confidence.replace('.', '').isdigit() else 0.0
            
            if is_arithmetic and confidence > 0.3:
                # Extract numbers and operations
                numbers = self._extract_numbers(user_input)
                operations = self._extract_operations(user_input)
                complexity = self._determine_complexity(prediction.operation_type, user_input)
                
                calculation_request = CalculationRequest(
                    expression=prediction.mathematical_expression,
                    complexity=complexity,
                    numbers=numbers,
                    operations=operations,
                    confidence=confidence
                )
                
                return True, confidence, calculation_request
            else:
                return False, confidence, None
                
        except Exception as e:
            # Fallback to regex-based detection
            return self._fallback_intent_detection(user_input)
    
    async def calculate(self, calculation_request: CalculationRequest) -> CalculationResult:
        """
        Perform the calculation with comprehensive error handling
        
        Args:
            calculation_request: Structured calculation request
            
        Returns:
            CalculationResult with success status and result
        """
        start_time = dspy.utils.get_current_time() if hasattr(dspy.utils, 'get_current_time') else 0
        
        try:
            # Sanitize the expression using DSPy
            sanitization = self.expression_sanitizer(raw_expression=calculation_request.expression)
            
            if sanitization.is_safe.lower() not in ['true', 'yes', '1']:
                return CalculationResult(
                    success=False,
                    result=None,
                    formatted_result="",
                    explanation="Expression deemed unsafe for evaluation",
                    error_message=f"Unsafe expression: {sanitization.normalization_notes}"
                )
            
            # Perform the calculation
            sanitized_expr = sanitization.sanitized_expression
            result, steps = await self._safe_evaluate(sanitized_expr)
            
            if result is None:
                return CalculationResult(
                    success=False,
                    result=None,
                    formatted_result="",
                    explanation="Could not evaluate the mathematical expression",
                    error_message="Evaluation failed"
                )
            
            # Generate explanation using DSPy
            explanation_pred = self.calculation_explainer(
                original_expression=calculation_request.expression,
                result=str(result),
                calculation_steps="; ".join(steps)
            )
            
            # Format the result
            formatted_result = self._format_number(result)
            
            execution_time = (dspy.utils.get_current_time() if hasattr(dspy.utils, 'get_current_time') else 0) - start_time
            
            calculation_result = CalculationResult(
                success=True,
                result=result,
                formatted_result=formatted_result,
                explanation=explanation_pred.explanation,
                calculation_steps=steps,
                execution_time=execution_time
            )
            
            # Log for learning
            self._log_calculation(calculation_request, calculation_result)
            
            return calculation_result
            
        except ZeroDivisionError:
            return CalculationResult(
                success=False,
                result=None,
                formatted_result="",
                explanation="Cannot divide by zero",
                error_message="Division by zero error"
            )
        except OverflowError:
            return CalculationResult(
                success=False,
                result=None,
                formatted_result="",
                explanation="The result is too large to compute",
                error_message="Numeric overflow"
            )
        except ValueError as e:
            return CalculationResult(
                success=False,
                result=None,
                formatted_result="",
                explanation="Invalid mathematical operation",
                error_message=f"Value error: {str(e)}"
            )
        except Exception as e:
            return CalculationResult(
                success=False,
                result=None,
                formatted_result="",
                explanation="An unexpected error occurred during calculation",
                error_message=f"Unexpected error: {str(e)}"
            )
    
    async def _safe_evaluate(self, expression: str) -> Tuple[Optional[float], List[str]]:
        """Safely evaluate mathematical expressions"""
        steps = []
        
        try:
            # Handle basic arithmetic expressions
            if self._is_simple_arithmetic(expression):
                result = self._evaluate_simple_arithmetic(expression, steps)
                return result, steps
            
            # Handle more complex expressions using ast
            result = self._evaluate_with_ast(expression, steps)
            return result, steps
            
        except Exception as e:
            steps.append(f"Error during evaluation: {str(e)}")
            return None, steps
    
    def _is_simple_arithmetic(self, expression: str) -> bool:
        """Check if expression is simple arithmetic"""
        # Remove spaces and check for basic operators
        expr = expression.replace(' ', '')
        return bool(re.match(r'^[\d+\-*/().%^]+$', expr))
    
    def _evaluate_simple_arithmetic(self, expression: str, steps: List[str]) -> float:
        """Evaluate simple arithmetic expressions"""
        steps.append(f"Evaluating: {expression}")
        
        # Replace ^ with ** for Python power operator
        expr = expression.replace('^', '**')
        steps.append(f"Normalized: {expr}")
        
        # Use eval with restricted globals for safety
        allowed_names = {
            "__builtins__": {},
            "abs": abs,
            "round": round,
            "pow": pow,
            "max": max,
            "min": min
        }
        
        result = eval(expr, allowed_names, {})
        steps.append(f"Result: {result}")
        
        return float(result)
    
    def _evaluate_with_ast(self, expression: str, steps: List[str]) -> float:
        """Evaluate expressions using AST for additional safety"""
        steps.append(f"AST evaluation of: {expression}")
        
        # Parse the expression into an AST
        tree = ast.parse(expression, mode='eval')
        
        # Validate the AST for safety
        if not self._is_safe_ast(tree):
            raise ValueError("Expression contains unsafe operations")
        
        # Evaluate the AST
        result = self._eval_ast_node(tree.body)
        steps.append(f"AST result: {result}")
        
        return float(result)
    
    def _is_safe_ast(self, node) -> bool:
        """Check if AST node contains only safe operations"""
        allowed_types = (
            ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
            ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow,
            ast.USub, ast.UAdd
        )
        
        for child in ast.walk(node):
            if not isinstance(child, allowed_types):
                return False
        
        return True
    
    def _eval_ast_node(self, node):
        """Evaluate AST node"""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Num):  # For older Python versions
            return node.n
        elif isinstance(node, ast.BinOp):
            left = self._eval_ast_node(node.left)
            right = self._eval_ast_node(node.right)
            return self._apply_binop(node.op, left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_ast_node(node.operand)
            return self._apply_unaryop(node.op, operand)
        else:
            raise ValueError(f"Unsupported AST node type: {type(node)}")
    
    def _apply_binop(self, op, left, right):
        """Apply binary operations"""
        if isinstance(op, ast.Add):
            return left + right
        elif isinstance(op, ast.Sub):
            return left - right
        elif isinstance(op, ast.Mult):
            return left * right
        elif isinstance(op, ast.Div):
            if right == 0:
                raise ZeroDivisionError("Division by zero")
            return left / right
        elif isinstance(op, ast.Mod):
            return left % right
        elif isinstance(op, ast.Pow):
            return left ** right
        else:
            raise ValueError(f"Unsupported binary operation: {type(op)}")
    
    def _apply_unaryop(self, op, operand):
        """Apply unary operations"""
        if isinstance(op, ast.UAdd):
            return +operand
        elif isinstance(op, ast.USub):
            return -operand
        else:
            raise ValueError(f"Unsupported unary operation: {type(op)}")
    
    def _extract_numbers(self, text: str) -> List[float]:
        """Extract numbers from text"""
        # Find all numbers including decimals
        number_pattern = r'\b\d+\.?\d*\b'
        matches = re.findall(number_pattern, text)
        return [float(match) for match in matches]
    
    def _extract_operations(self, text: str) -> List[str]:
        """Extract operation keywords from text"""
        operations = []
        text_lower = text.lower()
        
        operation_keywords = {
            'add': '+', 'plus': '+', 'sum': '+',
            'subtract': '-', 'minus': '-', 'difference': '-',
            'multiply': '*', 'times': '*', 'product': '*',
            'divide': '/', 'divided by': '/', 'quotient': '/',
            'power': '**', 'to the power of': '**', 'squared': '**2',
            'percent': '%', 'percentage': '%'
        }
        
        for keyword, symbol in operation_keywords.items():
            if keyword in text_lower:
                operations.append(symbol)
        
        # Also find symbolic operations
        symbolic_ops = re.findall(r'[+\-*/^%]', text)
        operations.extend(symbolic_ops)
        
        return list(set(operations))  # Remove duplicates
    
    def _determine_complexity(self, operation_type: str, user_input: str) -> CalculationComplexity:
        """Determine the complexity of the calculation"""
        operation_type_lower = operation_type.lower()
        user_input_lower = user_input.lower()
        
        if any(word in user_input_lower for word in ['sin', 'cos', 'tan', 'log', 'ln']):
            return CalculationComplexity.ADVANCED
        elif any(word in user_input_lower for word in ['power', 'square', 'root', 'percent']):
            return CalculationComplexity.INTERMEDIATE
        else:
            return CalculationComplexity.SIMPLE
    
    def _format_number(self, number: float) -> str:
        """Format number for human-readable output"""
        if number == int(number):
            return str(int(number))
        elif abs(number) < 0.001 or abs(number) > 1000000:
            return f"{number:.2e}"
        else:
            return f"{number:.4f}".rstrip('0').rstrip('.')
    
    def _fallback_intent_detection(self, user_input: str) -> Tuple[bool, float, Optional[CalculationRequest]]:
        """Fallback arithmetic intent detection using regex"""
        # Look for mathematical expressions
        math_patterns = [
            r'\b\d+\s*[+\-*/^%]\s*\d+\b',  # Basic arithmetic
            r'\bcalculate\b|\bcompute\b|\bmath\b',  # Calculation keywords
            r'\bwhat\s+is\s+\d+.*\d+\b',  # "What is X + Y" pattern
        ]
        
        user_input_lower = user_input.lower()
        confidence = 0.0
        
        for pattern in math_patterns:
            if re.search(pattern, user_input_lower):
                confidence += 0.3
        
        if confidence > 0.5:
            numbers = self._extract_numbers(user_input)
            operations = self._extract_operations(user_input)
            
            calculation_request = CalculationRequest(
                expression=user_input,
                complexity=CalculationComplexity.SIMPLE,
                numbers=numbers,
                operations=operations,
                confidence=confidence
            )
            
            return True, confidence, calculation_request
        
        return False, confidence, None
    
    def _log_calculation(self, request: CalculationRequest, result: CalculationResult):
        """Log calculation for learning and improvement"""
        log_entry = {
            "timestamp": dspy.utils.get_current_time() if hasattr(dspy.utils, 'get_current_time') else 0,
            "expression": request.expression,
            "complexity": request.complexity.value,
            "confidence": request.confidence,
            "success": result.success,
            "result": result.result,
            "error": result.error_message,
            "execution_time": result.execution_time
        }
        
        self.calculation_history.append(log_entry)
        
        # Keep only last 100 calculations
        if len(self.calculation_history) > 100:
            self.calculation_history = self.calculation_history[-100:]
    
    def get_calculation_stats(self) -> Dict[str, Any]:
        """Get statistics about calculator usage"""
        if not self.calculation_history:
            return {"total_calculations": 0}
        
        total = len(self.calculation_history)
        successful = sum(1 for calc in self.calculation_history if calc["success"])
        
        complexity_counts = {}
        for calc in self.calculation_history:
            complexity = calc["complexity"]
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1
        
        return {
            "total_calculations": total,
            "success_rate": successful / total,
            "complexity_distribution": complexity_counts,
            "average_confidence": sum(calc["confidence"] for calc in self.calculation_history) / total,
            "recent_calculations": self.calculation_history[-5:]
        }