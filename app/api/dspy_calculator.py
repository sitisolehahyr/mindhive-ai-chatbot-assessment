from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import asyncio
from app.tools.dspy_calculator import DSPyCalculatorTool, CalculationRequest, CalculationResult
import time


class CalculatorRequest(BaseModel):
    expression: str = Field(..., description="Mathematical expression or natural language calculation request")
    user_id: str = Field(..., description="Unique identifier for the user making the request")
    detect_intent: bool = Field(True, description="Whether to use DSPy for intent detection")


class CalculatorResponse(BaseModel):
    success: bool
    result: Optional[float]
    formatted_result: str
    explanation: str
    intent_detected: bool
    confidence: float
    complexity: str
    calculation_steps: List[str]
    execution_time: float
    error_message: Optional[str] = None


class IntentDetectionRequest(BaseModel):
    user_input: str = Field(..., description="User input to analyze for arithmetic intent")


class IntentDetectionResponse(BaseModel):
    is_arithmetic: bool
    confidence: float
    detected_expression: str
    operation_type: str
    numbers_found: List[float]
    operations_found: List[str]


class CalculatorStatsResponse(BaseModel):
    total_calculations: int
    success_rate: float
    complexity_distribution: Dict[str, int]
    average_confidence: float
    recent_calculations: List[Dict[str, Any]]


router = APIRouter(prefix="/api/dspy-calculator", tags=["dspy-calculator"])

# Initialize the DSPy calculator tool
# Note: In production, you'd want to configure this with proper API keys
try:
    dspy_calculator = DSPyCalculatorTool()
except Exception as e:
    print(f"Warning: DSPy calculator initialization failed: {e}")
    print("Falling back to basic calculator implementation")
    dspy_calculator = None


@router.post("/calculate", response_model=CalculatorResponse)
async def calculate_with_dspy(request: CalculatorRequest):
    """
    Advanced calculator endpoint using DSPy for intent detection and calculation
    
    Features:
    - Intelligent arithmetic intent detection
    - Natural language math expression parsing
    - Safe expression evaluation with error handling
    - Detailed explanations and step-by-step calculations
    - Graceful fallback for DSPy failures
    """
    start_time = time.time()
    
    try:
        if dspy_calculator and request.detect_intent:
            # Use DSPy for advanced intent detection and calculation
            is_arithmetic, confidence, calculation_request = await dspy_calculator.detect_arithmetic_intent(
                request.expression
            )
            
            if is_arithmetic and calculation_request:
                # Perform calculation using DSPy
                result = await dspy_calculator.calculate(calculation_request)
                
                return CalculatorResponse(
                    success=result.success,
                    result=result.result,
                    formatted_result=result.formatted_result,
                    explanation=result.explanation,
                    intent_detected=True,
                    confidence=confidence,
                    complexity=calculation_request.complexity.value,
                    calculation_steps=result.calculation_steps or [],
                    execution_time=time.time() - start_time,
                    error_message=result.error_message
                )
            else:
                # Intent not detected or confidence too low
                return CalculatorResponse(
                    success=False,
                    result=None,
                    formatted_result="",
                    explanation=f"Could not detect arithmetic intent in the input. Confidence: {confidence:.2f}",
                    intent_detected=False,
                    confidence=confidence,
                    complexity="unknown",
                    calculation_steps=[],
                    execution_time=time.time() - start_time,
                    error_message="No arithmetic intent detected"
                )
        else:
            # Fallback to basic calculation
            result = await _fallback_calculation(request.expression)
            
            return CalculatorResponse(
                success=result["success"],
                result=result.get("result"),
                formatted_result=result.get("formatted_result", ""),
                explanation=result.get("explanation", ""),
                intent_detected=True,  # Assume intent for fallback
                confidence=0.8,  # Default confidence for fallback
                complexity="simple",
                calculation_steps=result.get("steps", []),
                execution_time=time.time() - start_time,
                error_message=result.get("error")
            )
            
    except Exception as e:
        return CalculatorResponse(
            success=False,
            result=None,
            formatted_result="",
            explanation="An unexpected error occurred during calculation",
            intent_detected=False,
            confidence=0.0,
            complexity="unknown",
            calculation_steps=[],
            execution_time=time.time() - start_time,
            error_message=f"Unexpected error: {str(e)}"
        )


@router.post("/detect-intent", response_model=IntentDetectionResponse)
async def detect_arithmetic_intent(request: IntentDetectionRequest):
    """
    Analyze user input to detect arithmetic intent without performing calculation
    
    This endpoint demonstrates the DSPy intent detection capabilities:
    - Natural language understanding for math expressions
    - Confidence scoring for arithmetic intent
    - Extraction of numbers and operations
    - Classification of operation types
    """
    try:
        if dspy_calculator:
            is_arithmetic, confidence, calculation_request = await dspy_calculator.detect_arithmetic_intent(
                request.user_input
            )
            
            if calculation_request:
                return IntentDetectionResponse(
                    is_arithmetic=is_arithmetic,
                    confidence=confidence,
                    detected_expression=calculation_request.expression,
                    operation_type=calculation_request.complexity.value,
                    numbers_found=calculation_request.numbers,
                    operations_found=calculation_request.operations
                )
            else:
                return IntentDetectionResponse(
                    is_arithmetic=is_arithmetic,
                    confidence=confidence,
                    detected_expression="",
                    operation_type="none",
                    numbers_found=[],
                    operations_found=[]
                )
        else:
            # Fallback intent detection
            result = _fallback_intent_detection(request.user_input)
            return IntentDetectionResponse(**result)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Intent detection failed: {str(e)}")


@router.get("/stats", response_model=CalculatorStatsResponse)
async def get_calculator_stats():
    """
    Get statistics about calculator usage and performance
    
    Provides insights into:
    - Total number of calculations performed
    - Success rate of calculations
    - Distribution of calculation complexity
    - Average confidence scores
    - Recent calculation history
    """
    try:
        if dspy_calculator:
            stats = dspy_calculator.get_calculation_stats()
            
            return CalculatorStatsResponse(
                total_calculations=stats.get("total_calculations", 0),
                success_rate=stats.get("success_rate", 0.0),
                complexity_distribution=stats.get("complexity_distribution", {}),
                average_confidence=stats.get("average_confidence", 0.0),
                recent_calculations=stats.get("recent_calculations", [])
            )
        else:
            return CalculatorStatsResponse(
                total_calculations=0,
                success_rate=0.0,
                complexity_distribution={},
                average_confidence=0.0,
                recent_calculations=[]
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.post("/test-scenarios")
async def test_calculation_scenarios():
    """
    Test various calculation scenarios to demonstrate capabilities and error handling
    
    This endpoint runs a comprehensive test suite covering:
    - Successful calculations (basic, intermediate, advanced)
    - Error scenarios (division by zero, invalid expressions)
    - Edge cases (very large numbers, complex expressions)
    - Natural language inputs
    """
    test_cases = [
        # Successful calculations
        "Calculate 25 + 37",
        "What is 144 divided by 12?",
        "15 * 8",
        "100 - 45",
        "2 to the power of 8",
        "Square root of 16",
        "50% of 200",
        
        # Error scenarios
        "Divide 10 by 0",
        "Calculate abc + def",
        "What is infinity plus one?",
        "2 to the power of 1000",
        
        # Edge cases
        "0.1 + 0.2",
        "1000000 * 1000000",
        "Calculate nothing",
        "Tell me about weather"
    ]
    
    results = []
    
    for test_case in test_cases:
        try:
            request = CalculatorRequest(
                expression=test_case,
                user_id="test_user",
                detect_intent=True
            )
            
            # Use the actual endpoint logic
            start_time = time.time()
            
            if dspy_calculator:
                is_arithmetic, confidence, calculation_request = await dspy_calculator.detect_arithmetic_intent(
                    test_case
                )
                
                if is_arithmetic and calculation_request:
                    calc_result = await dspy_calculator.calculate(calculation_request)
                    
                    result = {
                        "input": test_case,
                        "success": calc_result.success,
                        "result": calc_result.result,
                        "explanation": calc_result.explanation,
                        "confidence": confidence,
                        "error": calc_result.error_message,
                        "execution_time": time.time() - start_time
                    }
                else:
                    result = {
                        "input": test_case,
                        "success": False,
                        "result": None,
                        "explanation": "No arithmetic intent detected",
                        "confidence": confidence,
                        "error": "Intent detection failed",
                        "execution_time": time.time() - start_time
                    }
            else:
                # Fallback testing
                calc_result = await _fallback_calculation(test_case)
                result = {
                    "input": test_case,
                    "success": calc_result["success"],
                    "result": calc_result.get("result"),
                    "explanation": calc_result.get("explanation", ""),
                    "confidence": 0.8,
                    "error": calc_result.get("error"),
                    "execution_time": time.time() - start_time
                }
            
            results.append(result)
            
        except Exception as e:
            results.append({
                "input": test_case,
                "success": False,
                "result": None,
                "explanation": "Test execution failed",
                "confidence": 0.0,
                "error": str(e),
                "execution_time": time.time() - start_time
            })
    
    # Analyze results
    total_tests = len(results)
    successful_tests = sum(1 for r in results if r["success"])
    success_rate = successful_tests / total_tests
    
    return {
        "test_summary": {
            "total_tests": total_tests,
            "successful_tests": successful_tests,
            "success_rate": success_rate,
            "average_confidence": sum(r["confidence"] for r in results) / total_tests
        },
        "test_results": results
    }


@router.get("/health")
async def calculator_health_check():
    """Health check for DSPy calculator service"""
    return {
        "status": "healthy",
        "service": "dspy-calculator",
        "dspy_available": dspy_calculator is not None,
        "fallback_available": True
    }


# Fallback functions for when DSPy is not available
async def _fallback_calculation(expression: str) -> Dict[str, Any]:
    """Fallback calculation without DSPy"""
    import re
    
    try:
        # Simple regex-based number and operation extraction
        numbers = re.findall(r'\d+\.?\d*', expression)
        
        if len(numbers) >= 2:
            a, b = float(numbers[0]), float(numbers[1])
            
            if any(op in expression for op in ['+', 'add', 'plus']):
                result = a + b
                return {
                    "success": True,
                    "result": result,
                    "formatted_result": str(result),
                    "explanation": f"Added {a} and {b} to get {result}",
                    "steps": [f"{a} + {b} = {result}"]
                }
            elif any(op in expression for op in ['-', 'subtract', 'minus']):
                result = a - b
                return {
                    "success": True,
                    "result": result,
                    "formatted_result": str(result),
                    "explanation": f"Subtracted {b} from {a} to get {result}",
                    "steps": [f"{a} - {b} = {result}"]
                }
            elif any(op in expression for op in ['*', 'multiply', 'times']):
                result = a * b
                return {
                    "success": True,
                    "result": result,
                    "formatted_result": str(result),
                    "explanation": f"Multiplied {a} by {b} to get {result}",
                    "steps": [f"{a} × {b} = {result}"]
                }
            elif any(op in expression for op in ['/', 'divide', 'divided by']):
                if b == 0:
                    return {
                        "success": False,
                        "error": "Cannot divide by zero",
                        "explanation": "Division by zero is undefined"
                    }
                result = a / b
                return {
                    "success": True,
                    "result": result,
                    "formatted_result": str(result),
                    "explanation": f"Divided {a} by {b} to get {result}",
                    "steps": [f"{a} ÷ {b} = {result}"]
                }
        
        return {
            "success": False,
            "error": "Could not parse mathematical expression",
            "explanation": "Unable to identify numbers and operations"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Calculation error: {str(e)}",
            "explanation": "An error occurred during fallback calculation"
        }


def _fallback_intent_detection(user_input: str) -> Dict[str, Any]:
    """Fallback intent detection without DSPy"""
    import re
    
    user_input_lower = user_input.lower()
    
    # Check for arithmetic keywords
    arithmetic_keywords = ['calculate', 'compute', 'math', 'add', 'subtract', 'multiply', 'divide', 'plus', 'minus', 'times']
    has_keywords = any(keyword in user_input_lower for keyword in arithmetic_keywords)
    
    # Check for numbers and operators
    has_numbers = bool(re.search(r'\d+', user_input))
    has_operators = bool(re.search(r'[+\-*/]', user_input))
    
    # Simple scoring
    confidence = 0.0
    if has_keywords:
        confidence += 0.4
    if has_numbers:
        confidence += 0.3
    if has_operators:
        confidence += 0.3
    
    is_arithmetic = confidence > 0.5
    
    numbers = [float(match) for match in re.findall(r'\d+\.?\d*', user_input)]
    operations = re.findall(r'[+\-*/]', user_input)
    
    return {
        "is_arithmetic": is_arithmetic,
        "confidence": confidence,
        "detected_expression": user_input if is_arithmetic else "",
        "operation_type": "basic" if is_arithmetic else "none",
        "numbers_found": numbers,
        "operations_found": operations
    }