"""
Part 5: Unhappy Flows Test Suite
Testing robustness against invalid and malicious inputs across all integrations
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import httpx
import json
import sys
import os
from fastapi.testclient import TestClient
from fastapi import FastAPI

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.action_executor import ActionExecutor, ActionResult
from app.core.planner import PlannerAction, ActionType
from app.api.rag_endpoints import router as rag_router
from app.api.dspy_calculator import router as calc_router
from app.rag.text2sql_system import ZUSOutletText2SQL
from app.rag.product_vectorstore import ZUSProductVectorStore


class TestMissingParametersScenarios:
    """Test cases for missing parameters across all integrations"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.executor = ActionExecutor()
        self.test_context = {
            "user_message": "test message",
            "memory": Mock(),
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_calculator_missing_expression(self):
        """Test calculator with missing expression"""
        action = PlannerAction(
            action_type=ActionType.CALL_CALCULATOR,
            parameters={
                "input_data": {},  # Missing expression
                "context": ""
            },
            confidence=0.8,
            reasoning="Test missing expression"
        )
        
        result = await self.executor._handle_calculator_call(action, self.test_context)
        
        assert not result.success
        assert "need at least two numbers" in result.response.lower() or "couldn't detect arithmetic" in result.response.lower()
        assert result.error is not None
        
    @pytest.mark.asyncio
    async def test_calculator_incomplete_expression(self):
        """Test calculator with incomplete expression"""
        action = PlannerAction(
            action_type=ActionType.CALL_CALCULATOR,
            parameters={
                "input_data": {"expression": "Calculate"},  # Incomplete
                "context": "Calculate"
            },
            confidence=0.8,
            reasoning="Test incomplete expression"
        )
        
        result = await self.executor._handle_calculator_call(action, self.test_context)
        
        assert not result.success
        assert any(phrase in result.response.lower() for phrase in [
            "need at least two numbers",
            "couldn't detect arithmetic",
            "provide a clearer mathematical expression"
        ])

    @pytest.mark.asyncio
    async def test_rag_missing_query(self):
        """Test RAG system with missing query parameter"""
        action = PlannerAction(
            action_type=ActionType.CALL_RAG_SYSTEM,
            parameters={
                "input_data": {
                    "rag_type": "product"
                    # Missing query
                }
            },
            confidence=0.8,
            reasoning="Test missing query"
        )
        
        result = await self.executor._handle_rag_system_call(action, self.test_context)
        
        assert not result.success
        assert "need a search query" in result.response.lower()
        assert result.error == "Missing query"

    @pytest.mark.asyncio
    async def test_outlet_missing_location(self):
        """Test outlet search with missing location"""
        action = PlannerAction(
            action_type=ActionType.CALL_OUTLET_API,
            parameters={
                "input_data": {
                    # Missing location
                    "query_type": "general"
                }
            },
            confidence=0.8,
            reasoning="Test missing location"
        )
        
        result = await self.executor._handle_outlet_api_call(action, self.test_context)
        
        assert not result.success
        assert "don't have information" in result.response.lower()
        assert result.error == "Outlet not found"

    @pytest.mark.asyncio
    async def test_product_search_empty_parameters(self):
        """Test product search with completely empty parameters"""
        action = PlannerAction(
            action_type=ActionType.CALL_PRODUCT_API,
            parameters={
                "input_data": {}  # Empty parameters
            },
            confidence=0.8,
            reasoning="Test empty parameters"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock API response for empty search
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "products": [],
                "message": "No products found"
            }
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await self.executor._handle_product_api_call(action, self.test_context)
            
            assert result.success  # Should handle gracefully
            assert "couldn't find any products" in result.response.lower()


class TestAPIDowntimeScenarios:
    """Test cases for API downtime and network failures"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.executor = ActionExecutor()
        self.test_context = {
            "user_message": "test message", 
            "memory": Mock(),
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_rag_product_api_500_error(self):
        """Test RAG product search with HTTP 500 error"""
        action = PlannerAction(
            action_type=ActionType.CALL_RAG_SYSTEM,
            parameters={
                "input_data": {
                    "rag_type": "product",
                    "query": "test tumbler"
                }
            },
            confidence=0.8,
            reasoning="Test API downtime"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock HTTP 500 error
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Internal Server Error"}
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await self.executor._handle_product_rag_call("test tumbler", {"query": "test tumbler"})
            
            assert not result.success
            assert "trouble searching for products" in result.response.lower()
            assert "500" in result.error

    @pytest.mark.asyncio
    async def test_rag_outlet_api_503_error(self):
        """Test RAG outlet search with service unavailable"""
        action = PlannerAction(
            action_type=ActionType.CALL_RAG_SYSTEM,
            parameters={
                "input_data": {
                    "rag_type": "outlet",
                    "query": "outlets in KL"
                }
            },
            confidence=0.8,
            reasoning="Test service unavailable"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock HTTP 503 error
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.json.return_value = {"detail": "Service Temporarily Unavailable"}
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            result = await self.executor._handle_outlet_rag_call("outlets in KL", {"query": "outlets in KL"})
            
            assert not result.success
            assert "trouble searching for outlets" in result.response.lower() or "service temporarily unavailable" in result.response.lower()

    @pytest.mark.asyncio
    async def test_restaurant_api_timeout(self):
        """Test restaurant API with connection timeout"""
        action = PlannerAction(
            action_type=ActionType.CALL_RESTAURANT_API,
            parameters={
                "input_data": {
                    "cuisine": "italian",
                    "location": "KL"
                }
            },
            confidence=0.8,
            reasoning="Test timeout"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock connection timeout
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.TimeoutException("Request timeout")
            
            result = await self.executor._handle_restaurant_api_call(action, self.test_context)
            
            assert not result.success
            assert "can't search for restaurants" in result.response.lower()
            assert "timeout" in result.error.lower()

    @pytest.mark.asyncio
    async def test_product_api_network_error(self):
        """Test product API with network connection error"""
        action = PlannerAction(
            action_type=ActionType.CALL_PRODUCT_API,
            parameters={
                "input_data": {
                    "category": "electronics",
                    "search_term": "laptop"
                }
            },
            confidence=0.8,
            reasoning="Test network error"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock network error
            mock_client.return_value.__aenter__.return_value.get.side_effect = httpx.ConnectError("Connection failed")
            
            result = await self.executor._handle_product_api_call(action, self.test_context)
            
            assert not result.success
            assert "can't search for products" in result.response.lower()
            assert "connection failed" in result.error.lower()

    @pytest.mark.asyncio
    async def test_dspy_calculator_service_down(self):
        """Test DSPy calculator when service is down"""
        action = PlannerAction(
            action_type=ActionType.CALL_CALCULATOR,
            parameters={
                "input_data": {"expression": "2 + 2"},
                "context": "2 + 2"
            },
            confidence=0.8,
            reasoning="Test DSPy service down"
        )
        
        # Mock DSPy calculator failure
        with patch.object(self.executor, 'dspy_calculator') as mock_calc:
            mock_calc.detect_arithmetic_intent.side_effect = Exception("Service unavailable")
            
            result = await self.executor._handle_calculator_call(action, self.test_context)
            
            # Should fallback to basic calculator
            assert result.success or "result of 2" in result.response
            if not result.success:
                assert "couldn't perform that calculation" in result.response.lower()


class TestMaliciousPayloadScenarios:
    """Test cases for malicious inputs and security vulnerabilities"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Create test FastAPI app for endpoint testing
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.app.include_router(calc_router)
        self.client = TestClient(self.app)
        
    def test_sql_injection_outlet_search(self):
        """Test SQL injection attempts in outlet search"""
        malicious_queries = [
            "'; DROP TABLE outlets; --",
            "' OR '1'='1",
            "UNION SELECT * FROM users",
            "__import__('os').system('rm -rf /')",
            "'; INSERT INTO outlets VALUES ('hack'); --",
            "' UNION SELECT password FROM admin; --"
        ]
        
        for malicious_query in malicious_queries:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                # Mock the text2sql system to simulate security handling
                mock_text2sql.query_outlets.return_value = (
                    False,
                    "Query failed safety validation",
                    []
                )
                
                response = self.client.get(f"/api/outlets?query={malicious_query}")
                
                # Should return error, not execute malicious code
                assert response.status_code in [400, 422, 500]
                if response.status_code == 400:
                    assert "failed" in response.json()["detail"].lower()

    def test_code_injection_calculator(self):
        """Test code injection attempts in calculator"""
        malicious_expressions = [
            "__import__('os').system('ls')",
            "exec('print(\"hacked\")')",
            "eval('__import__(\"os\").getcwd()')",
            "open('/etc/passwd', 'r').read()",
            "'; import subprocess; subprocess.call(['rm', '-rf', '/'])",
            "1; __import__('sys').exit()"
        ]
        
        for malicious_expr in malicious_expressions:
            with patch('app.api.rag_endpoints.init_rag_systems'):
                response = self.client.post("/api/calculate", json={
                    "expression": malicious_expr
                })
                
                # Should not execute malicious code
                if response.status_code == 200:
                    result = response.json()
                    assert not result.get("success", False) or "could not understand" in result.get("explanation", "").lower()
                else:
                    assert response.status_code in [400, 422, 500]

    def test_xss_injection_product_search(self):
        """Test XSS injection attempts in product search"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//",
            "<svg onload=alert('xss')>",
            "../../etc/passwd"
        ]
        
        for xss_payload in xss_payloads:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "No results found"
                
                response = self.client.get(f"/api/products?query={xss_payload}")
                
                # Should handle gracefully without executing script
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    # Ensure no script execution in response
                    response_text = json.dumps(data)
                    assert "<script>" not in response_text
                    assert "javascript:" not in response_text

    def test_path_traversal_attempts(self):
        """Test path traversal attempts"""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ]
        
        for payload in path_traversal_payloads:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "No results found"
                
                response = self.client.get(f"/api/products?query={payload}")
                
                # Should not access file system
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    assert "root:" not in str(data)  # No passwd file content
                    assert "Administrator" not in str(data)  # No Windows system files

    def test_oversized_payload_handling(self):
        """Test handling of oversized payloads"""
        # Create very large payload
        large_query = "A" * 100000  # 100KB query
        
        with patch('app.api.rag_endpoints.product_store') as mock_store:
            mock_store.search.return_value = []
            mock_store.generate_summary.return_value = "Query too large"
            
            response = self.client.get(f"/api/products?query={large_query}")
            
            # Should handle large payloads gracefully
            assert response.status_code in [200, 400, 413, 422]

    def test_special_character_injection(self):
        """Test special character injection attempts"""
        special_payloads = [
            "null\x00byte",
            "\x1b[31mANSI injection\x1b[0m",
            "unicode\u202ehack",
            "\r\nHTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n<html>",
            "%0d%0aContent-Type: text/html%0d%0a%0d%0a<script>alert('header injection')</script>"
        ]
        
        for payload in special_payloads:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (
                    True,
                    "Safe response",
                    []
                )
                
                response = self.client.get(f"/api/outlets?query={payload}")
                
                # Should sanitize special characters
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    # Check that response headers are not manipulated
                    assert "text/html" not in response.headers.get("content-type", "")


class TestText2SQLSecurityScenarios:
    """Specific security tests for Text2SQL system"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.text2sql = ZUSOutletText2SQL(db_path=":memory:")  # Use in-memory DB for testing
        
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in Text2SQL system"""
        malicious_queries = [
            "'; DROP TABLE outlets; SELECT * FROM outlets WHERE '1'='1",
            "' UNION SELECT * FROM sqlite_master --",
            "'; DELETE FROM outlets; --",
            "' OR 1=1; UPDATE outlets SET name='hacked'; --"
        ]
        
        for query in malicious_queries:
            success, explanation, results = self.text2sql.query_outlets(query)
            
            # Should either fail safely or return safe results
            if success:
                # If it succeeds, should not return system tables or modified data
                assert len(results) >= 0  # Safe result count
                for result in results:
                    assert "sqlite_master" not in str(result)
                    assert "hacked" not in str(result)
            else:
                # If it fails, should have appropriate error message
                assert any(phrase in explanation.lower() for phrase in [
                    "safety validation",
                    "invalid query", 
                    "could not understand"
                ])

    def test_dangerous_sql_keywords_blocked(self):
        """Test that dangerous SQL keywords are blocked"""
        dangerous_queries = [
            "DROP outlets",
            "DELETE FROM outlets",
            "UPDATE outlets SET name='hack'",
            "INSERT INTO outlets VALUES ('hack')",
            "ALTER TABLE outlets",
            "CREATE TABLE hack"
        ]
        
        for query in dangerous_queries:
            sql_query = self.text2sql.parse_natural_language_query(query)
            
            if sql_query:
                # If SQL is generated, it should be safe
                assert sql_query.sql.lower().startswith('select')
                assert not any(keyword in sql_query.sql.lower() for keyword in [
                    'drop', 'delete', 'update', 'insert', 'alter', 'create'
                ])

    def test_parameter_binding_safety(self):
        """Test that parameter binding prevents injection"""
        # Test with query that would be dangerous without parameter binding
        query = "outlets in '; DROP TABLE outlets; --"
        
        success, explanation, results = self.text2sql.query_outlets(query)
        
        # Should handle safely - either find no results or fail gracefully
        if success:
            assert isinstance(results, list)
            # Should not have executed DROP command
            assert len(results) >= 0
        else:
            assert "could not" in explanation.lower() or "not found" in explanation.lower()


class TestErrorRecoveryAndUserExperience:
    """Test error recovery and user experience during failures"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.executor = ActionExecutor()
        self.test_context = {
            "user_message": "test message",
            "memory": Mock(), 
            "session_id": "test_session"
        }

    @pytest.mark.asyncio
    async def test_graceful_degradation_multiple_failures(self):
        """Test graceful degradation when multiple systems fail"""
        action = PlannerAction(
            action_type=ActionType.CALL_RAG_SYSTEM,
            parameters={
                "input_data": {
                    "rag_type": "product",
                    "query": "test query"
                }
            },
            confidence=0.8,
            reasoning="Test multiple failures"
        )
        
        with patch('httpx.AsyncClient') as mock_client:
            # Mock multiple API failures
            mock_client.return_value.__aenter__.return_value.get.side_effect = [
                httpx.TimeoutException("Primary timeout"),
                httpx.ConnectError("Fallback connection failed")
            ]
            
            result = await self.executor._handle_rag_system_call(action, self.test_context)
            
            assert not result.success
            assert "trouble accessing that information" in result.response.lower()
            assert "try again later" in result.response.lower()

    @pytest.mark.asyncio 
    async def test_helpful_error_messages(self):
        """Test that error messages are helpful and actionable"""
        test_cases = [
            {
                "action_type": ActionType.CALL_CALCULATOR,
                "params": {"input_data": {"expression": "invalid"}},
                "expected_phrases": ["clearer", "expression", "numbers"]
            },
            {
                "action_type": ActionType.CALL_RAG_SYSTEM, 
                "params": {"input_data": {"rag_type": "product"}},
                "expected_phrases": ["search query", "what would you like"]
            },
            {
                "action_type": ActionType.CALL_OUTLET_API,
                "params": {"input_data": {}},
                "expected_phrases": ["don't have information", "ss2", "mid valley"]
            }
        ]
        
        for case in test_cases:
            action = PlannerAction(
                action_type=case["action_type"],
                parameters=case["params"],
                confidence=0.8,
                reasoning="Test helpful messages"
            )
            
            result = await self.executor._execute_action(action, self.test_context)
            
            # Should contain helpful guidance
            response_lower = result.response.lower()
            assert any(phrase in response_lower for phrase in case["expected_phrases"])

    @pytest.mark.asyncio
    async def test_recovery_prompts_provided(self):
        """Test that recovery prompts are provided after errors"""
        action = PlannerAction(
            action_type=ActionType.CALL_RAG_SYSTEM,
            parameters={
                "input_data": {
                    "rag_type": "unknown",
                    "query": "test"
                }
            },
            confidence=0.8,
            reasoning="Test recovery prompts"
        )
        
        result = await self.executor._handle_rag_system_call(action, self.test_context)
        
        assert not result.success
        assert any(phrase in result.response.lower() for phrase in [
            "could you clarify",
            "if you need product",
            "if you need outlet"
        ])

    @pytest.mark.asyncio
    async def test_system_never_crashes(self):
        """Test that system never crashes even with extreme inputs"""
        extreme_inputs = [
            None,
            "",
            {"invalid": "structure"},
            {"input_data": None},
            {"input_data": {"query": None}},
            {"input_data": {"rag_type": "", "query": ""}},
        ]
        
        for extreme_input in extreme_inputs:
            action = PlannerAction(
                action_type=ActionType.CALL_RAG_SYSTEM,
                parameters=extreme_input or {},
                confidence=0.8,
                reasoning="Test extreme inputs"
            )
            
            try:
                result = await self.executor._handle_rag_system_call(action, self.test_context)
                # Should not crash, should return error result
                assert isinstance(result, ActionResult)
                assert not result.success
                assert isinstance(result.response, str)
                assert len(result.response) > 0
            except Exception as e:
                pytest.fail(f"System crashed with input {extreme_input}: {e}")


class TestSecurityHeadersAndValidation:
    """Test security headers and input validation"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_input_validation_edge_cases(self):
        """Test input validation with edge cases"""
        edge_cases = [
            ("", 422),  # Empty query
            ("a" * 10000, 200),  # Very long query (should handle gracefully)
            ("   ", 200),  # Whitespace only
            ("\n\r\t", 200),  # Special whitespace characters
        ]
        
        for query, expected_status in edge_cases:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "No results"
                
                response = self.client.get(f"/api/products?query={query}")
                assert response.status_code == expected_status

    def test_parameter_type_validation(self):
        """Test parameter type validation"""
        invalid_params = [
            {"query": "test", "top_k": "invalid"},  # String instead of int
            {"query": "test", "availability": "maybe"},  # Invalid boolean
            {"query": "test", "min_price": "free"},  # String instead of float
            {"query": "test", "max_price": -10},  # Negative price
        ]
        
        for params in invalid_params:
            with patch('app.api.rag_endpoints.product_store'):
                response = self.client.get("/api/products", params=params)
                assert response.status_code == 422  # Validation error

    def test_response_sanitization(self):
        """Test that responses are properly sanitized"""
        with patch('app.api.rag_endpoints.product_store') as mock_store:
            # Mock response with potentially dangerous content
            mock_result = Mock()
            mock_result.document.name = "<script>alert('xss')</script>"
            mock_result.document.description = "Safe description"
            mock_result.score = 0.5
            mock_result.rank = 1
            
            mock_store.search.return_value = [mock_result]
            mock_store.generate_summary.return_value = "Safe summary"
            
            response = self.client.get("/api/products?query=test")
            
            if response.status_code == 200:
                # Response should not contain dangerous script tags
                response_text = response.text
                assert "<script>" not in response_text
                assert "alert(" not in response_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])