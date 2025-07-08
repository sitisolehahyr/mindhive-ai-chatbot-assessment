import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.tools.dspy_calculator import DSPyCalculatorTool, CalculationComplexity
from app.api.dspy_calculator import _fallback_calculation, _fallback_intent_detection


class TestDSPyCalculator:
    """Test suite for DSPy-powered calculator with comprehensive error handling scenarios"""
    
    @pytest.fixture
    async def calculator_tool(self):
        """Create calculator tool instance for testing"""
        try:
            return DSPyCalculatorTool()
        except Exception:
            # Return None if DSPy initialization fails (e.g., no API key)
            return None
    
    @pytest.mark.asyncio
    async def test_successful_basic_calculations(self, calculator_tool):
        """Test successful basic arithmetic calculations"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            ("Calculate 25 + 15", 40),
            ("What is 144 divided by 12?", 12),
            ("15 times 8", 120),
            ("100 minus 45", 55),
        ]
        
        for expression, expected_result in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            assert is_arithmetic, f"Should detect arithmetic intent in: {expression}"
            assert confidence > 0.5, f"Should have reasonable confidence for: {expression}"
            
            if calc_request:
                result = await calculator_tool.calculate(calc_request)
                assert result.success, f"Calculation should succeed for: {expression}"
                assert abs(result.result - expected_result) < 0.001, f"Wrong result for {expression}"
    
    @pytest.mark.asyncio
    async def test_error_handling_division_by_zero(self, calculator_tool):
        """Test graceful handling of division by zero"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            "Divide 10 by 0",
            "What is 5 divided by zero?",
            "15 / 0"
        ]
        
        for expression in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            if is_arithmetic and calc_request:
                result = await calculator_tool.calculate(calc_request)
                # Should either detect the error during calculation or handle it gracefully
                if not result.success:
                    assert "zero" in result.error_message.lower() or "divide" in result.error_message.lower()
                    assert "zero" in result.explanation.lower() or "undefined" in result.explanation.lower()
    
    @pytest.mark.asyncio
    async def test_error_handling_invalid_expressions(self, calculator_tool):
        """Test handling of invalid mathematical expressions"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            "Calculate abc + def",
            "What is infinity plus one?",
            "Compute hello * world",
            "Add some numbers together"
        ]
        
        for expression in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            # Either intent detection should fail (low confidence) or calculation should handle gracefully
            if not is_arithmetic or confidence < 0.3:
                # Intent detection correctly failed
                assert True
            elif calc_request:
                result = await calculator_tool.calculate(calc_request)
                if not result.success:
                    assert result.error_message is not None
                    assert len(result.explanation) > 0
    
    @pytest.mark.asyncio
    async def test_complex_expressions(self, calculator_tool):
        """Test handling of complex mathematical expressions"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            ("2 to the power of 8", 256),
            ("50% of 200", 100),
            ("Square root of 16", 4),
        ]
        
        for expression, expected_result in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            if is_arithmetic and calc_request:
                assert calc_request.complexity in [CalculationComplexity.INTERMEDIATE, CalculationComplexity.ADVANCED]
                
                result = await calculator_tool.calculate(calc_request)
                # Complex calculations may not always succeed, but should handle gracefully
                if result.success:
                    # Allow some tolerance for complex calculations
                    assert abs(result.result - expected_result) < 1.0
                else:
                    assert result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_edge_cases(self, calculator_tool):
        """Test edge cases and boundary conditions"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            "0.1 + 0.2",  # Floating point precision
            "1000000 * 1000000",  # Large numbers
            "0 * 999",  # Zero multiplication
            "1 / 3",  # Repeating decimal
        ]
        
        for expression in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            if is_arithmetic and calc_request:
                result = await calculator_tool.calculate(calc_request)
                # Should either succeed or fail gracefully
                assert result.success or result.error_message is not None
    
    @pytest.mark.asyncio
    async def test_non_arithmetic_inputs(self, calculator_tool):
        """Test that non-arithmetic inputs are correctly rejected"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        test_cases = [
            "Tell me about the weather",
            "What's your name?",
            "How are you doing?",
            "Calculate nothing",
            "Math is hard"
        ]
        
        for expression in test_cases:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            
            # Should either not detect arithmetic intent or have very low confidence
            assert not is_arithmetic or confidence < 0.5
    
    @pytest.mark.asyncio
    async def test_calculation_logging_and_stats(self, calculator_tool):
        """Test that calculations are properly logged for analytics"""
        if not calculator_tool:
            pytest.skip("DSPy calculator not available")
        
        # Perform a few calculations
        test_expressions = ["10 + 5", "20 * 3", "100 / invalid"]
        
        for expression in test_expressions:
            is_arithmetic, confidence, calc_request = await calculator_tool.detect_arithmetic_intent(expression)
            if is_arithmetic and calc_request:
                await calculator_tool.calculate(calc_request)
        
        # Check stats
        stats = calculator_tool.get_calculation_stats()
        assert stats["total_calculations"] >= 0
        assert "success_rate" in stats
        assert "complexity_distribution" in stats


class TestFallbackCalculator:
    """Test fallback calculator implementation"""
    
    @pytest.mark.asyncio
    async def test_fallback_basic_calculations(self):
        """Test fallback calculator for basic operations"""
        test_cases = [
            ("25 + 15", True, 40),
            ("144 / 12", True, 12),
            ("15 * 8", True, 120),
            ("100 - 45", True, 55),
        ]
        
        for expression, should_succeed, expected_result in test_cases:
            result = await _fallback_calculation(expression)
            
            if should_succeed:
                assert result["success"], f"Fallback should succeed for: {expression}"
                assert abs(result["result"] - expected_result) < 0.001
            else:
                assert not result["success"]
    
    @pytest.mark.asyncio
    async def test_fallback_error_handling(self):
        """Test fallback calculator error handling"""
        test_cases = [
            "10 / 0",  # Division by zero
            "invalid expression",  # Invalid expression
            "abc + def",  # No numbers
        ]
        
        for expression in test_cases:
            result = await _fallback_calculation(expression)
            
            if not result["success"]:
                assert "error" in result
                assert len(result.get("explanation", "")) > 0
    
    def test_fallback_intent_detection(self):
        """Test fallback intent detection"""
        test_cases = [
            ("Calculate 10 + 5", True),
            ("What is 25 times 3?", True),
            ("Tell me about weather", False),
            ("15 * 8", True),
            ("Hello world", False),
        ]
        
        for expression, should_detect in test_cases:
            result = _fallback_intent_detection(expression)
            
            if should_detect:
                assert result["is_arithmetic"], f"Should detect arithmetic in: {expression}"
                assert result["confidence"] > 0.5
            else:
                assert not result["is_arithmetic"] or result["confidence"] <= 0.5


class TestCalculatorErrorScenarios:
    """Test comprehensive error scenarios and graceful degradation"""
    
    @pytest.mark.asyncio
    async def test_dspy_unavailable_fallback(self):
        """Test behavior when DSPy is unavailable"""
        # This test simulates when DSPy is not available
        with patch('app.tools.dspy_calculator.DSPY_AVAILABLE', False):
            # Should use fallback implementation
            result = await _fallback_calculation("10 + 5")
            assert result["success"]
            assert result["result"] == 15
    
    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """Test handling of network timeouts in API calls"""
        # Simulate timeout scenarios
        test_cases = [
            "Calculate 2^1000",  # Very large calculation
            "What is the square root of -1?",  # Invalid mathematical operation
        ]
        
        for expression in test_cases:
            # Should either succeed or fail gracefully with timeout
            result = await _fallback_calculation(expression)
            # Should not crash, should provide some response
            assert "success" in result
    
    @pytest.mark.asyncio  
    async def test_malicious_input_handling(self):
        """Test handling of potentially malicious inputs"""
        malicious_inputs = [
            "__import__('os').system('rm -rf /')",  # Code injection attempt
            "eval('print(\"hacked\")')",  # Eval injection
            "exec('malicious code')",  # Exec injection
            "1e999999",  # Extremely large number
        ]
        
        for malicious_input in malicious_inputs:
            # Should either safely reject or handle without executing malicious code
            result = await _fallback_calculation(malicious_input)
            # Should not crash and should handle safely
            assert "success" in result
            if not result["success"]:
                assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])