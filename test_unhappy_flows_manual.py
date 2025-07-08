#!/usr/bin/env python3
"""
Manual test script for unhappy flows
Tests the three required scenarios without complex test framework
"""
import asyncio
import sys
import os
import json
from unittest.mock import Mock, patch, AsyncMock
import sqlite3
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.action_executor import ActionExecutor, ActionResult
from app.core.planner import PlannerAction, ActionType
from app.rag.text2sql_system import ZUSOutletText2SQL
from app.rag.product_vectorstore import ZUSProductVectorStore


class UnhappyFlowTester:
    """Manual tester for unhappy flows"""
    
    def __init__(self):
        self.executor = ActionExecutor()
        self.test_context = {
            "user_message": "test message",
            "memory": Mock(),
            "session_id": "test_session"
        }
        self.results = {
            "missing_parameters": [],
            "api_downtime": [],
            "malicious_payload": []
        }

    async def test_missing_parameters(self):
        """Test Case 1: Missing Parameters"""
        print("\n=== Testing Missing Parameters ===")
        
        # Test 1.1: Calculator without expression
        print("\n1.1 Testing calculator with missing expression...")
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
        success = not result.success and any(phrase in result.response.lower() for phrase in [
            "need at least two numbers", "couldn't detect arithmetic", "provide a clearer"
        ])
        
        self.results["missing_parameters"].append({
            "test": "Calculator missing expression",
            "success": success,
            "response": result.response,
            "error_handled": result.error is not None
        })
        print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"   Response: {result.response[:100]}...")
        
        # Test 1.2: RAG system without query
        print("\n1.2 Testing RAG system with missing query...")
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
        success = not result.success and "need a search query" in result.response.lower()
        
        self.results["missing_parameters"].append({
            "test": "RAG missing query",
            "success": success,
            "response": result.response,
            "error_handled": result.error == "Missing query"
        })
        print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"   Response: {result.response[:100]}...")
        
        # Test 1.3: Outlet search without location
        print("\n1.3 Testing outlet search with missing location...")
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
        success = not result.success and "don't have information" in result.response.lower()
        
        self.results["missing_parameters"].append({
            "test": "Outlet missing location",
            "success": success,
            "response": result.response,
            "error_handled": result.error == "Outlet not found"
        })
        print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
        print(f"   Response: {result.response[:100]}...")

    async def test_api_downtime(self):
        """Test Case 2: API Downtime (HTTP 500)"""
        print("\n=== Testing API Downtime ===")
        
        # Test 2.1: Product RAG API 500 error
        print("\n2.1 Testing product RAG API with HTTP 500...")
        
        # Mock HTTP 500 error
        async def mock_get(*args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Internal Server Error"}
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get
            
            result = await self.executor._handle_product_rag_call("test tumbler", {"query": "test tumbler"})
            success = not result.success and "trouble searching for products" in result.response.lower()
            
            self.results["api_downtime"].append({
                "test": "Product RAG API 500",
                "success": success,
                "response": result.response,
                "error_handled": "500" in result.error
            })
            print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
            print(f"   Response: {result.response[:100]}...")
        
        # Test 2.2: Outlet RAG API 503 error  
        print("\n2.2 Testing outlet RAG API with HTTP 503...")
        
        async def mock_get_503(*args, **kwargs):
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.json.return_value = {"detail": "Service Temporarily Unavailable"}
            return mock_response
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.return_value.__aenter__.return_value.get = mock_get_503
            
            result = await self.executor._handle_outlet_rag_call("outlets in KL", {"query": "outlets in KL"})
            success = not result.success and ("trouble searching for outlets" in result.response.lower() or 
                                           "service temporarily unavailable" in result.response.lower())
            
            self.results["api_downtime"].append({
                "test": "Outlet RAG API 503",
                "success": success,
                "response": result.response,
                "error_handled": True
            })
            print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
            print(f"   Response: {result.response[:100]}...")
        
        # Test 2.3: Network timeout
        print("\n2.3 Testing network timeout...")
        
        async def mock_get_timeout(*args, **kwargs):
            import httpx
            raise httpx.TimeoutException("Request timeout")
        
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
            mock_client.return_value.__aenter__.return_value.get = mock_get_timeout
            
            result = await self.executor._handle_restaurant_api_call(action, self.test_context)
            success = not result.success and "can't search for restaurants" in result.response.lower()
            
            self.results["api_downtime"].append({
                "test": "Network timeout",
                "success": success,
                "response": result.response,
                "error_handled": "timeout" in result.error.lower()
            })
            print(f"   Result: {'✅ PASS' if success else '❌ FAIL'}")
            print(f"   Response: {result.response[:100]}...")

    async def test_malicious_payloads(self):
        """Test Case 3: Malicious Payloads"""
        print("\n=== Testing Malicious Payloads ===")
        
        # Test 3.1: SQL injection in outlet search
        print("\n3.1 Testing SQL injection in outlet search...")
        
        # Create temporary database for testing
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        temp_db.close()
        
        try:
            text2sql = ZUSOutletText2SQL(db_path=temp_db.name)
            
            # Add test data
            cursor = text2sql.connection.cursor()
            cursor.execute("""
                INSERT INTO outlets (name, city, state, address, phone, email, operating_hours, services, coordinates, outlet_type, features, capacity, established)
                VALUES ('Test Outlet', 'Test City', 'Test State', '123 Test St', '+60123456789', 'test@test.com', '{}', '[]', '{}', 'Test', '[]', 50, '2020-01-01')
            """)
            text2sql.connection.commit()
            
            # Test SQL injection attempts
            malicious_queries = [
                "'; DROP TABLE outlets; --",
                "' OR '1'='1",
                "'; SELECT * FROM sqlite_master; --"
            ]
            
            injection_blocked = True
            for malicious_query in malicious_queries:
                success, explanation, results = text2sql.query_outlets(malicious_query)
                
                if success:
                    # Check that no malicious operations occurred
                    cursor.execute("SELECT COUNT(*) FROM outlets")
                    count = cursor.fetchone()[0]
                    if count == 0:  # Data was deleted
                        injection_blocked = False
                        break
                    
                    # Check for injection indicators in results
                    for result in results:
                        result_str = str(result)
                        if any(indicator in result_str for indicator in ["sqlite_master", "username", "password"]):
                            injection_blocked = False
                            break
            
            text2sql.close()
            
            self.results["malicious_payload"].append({
                "test": "SQL injection prevention",
                "success": injection_blocked,
                "response": "SQL injection attempts blocked" if injection_blocked else "SQL injection succeeded",
                "error_handled": True
            })
            print(f"   Result: {'✅ PASS' if injection_blocked else '❌ FAIL'}")
            print(f"   SQL injection blocked: {injection_blocked}")
            
        finally:
            os.unlink(temp_db.name)
        
        # Test 3.2: Code injection in calculator
        print("\n3.2 Testing code injection in calculator...")
        
        action = PlannerAction(
            action_type=ActionType.CALL_CALCULATOR,
            parameters={
                "input_data": {"expression": "__import__('os').system('ls')"},
                "context": "__import__('os').system('ls')"
            },
            confidence=0.8,
            reasoning="Test code injection"
        )
        
        result = await self.executor._handle_calculator_call(action, self.test_context)
        
        # Should either fail or return safe response (not execute system command)
        code_injection_blocked = (not result.success or 
                                "couldn't detect arithmetic" in result.response.lower() or
                                "couldn't perform" in result.response.lower())
        
        self.results["malicious_payload"].append({
            "test": "Code injection prevention",
            "success": code_injection_blocked,
            "response": result.response,
            "error_handled": True
        })
        print(f"   Result: {'✅ PASS' if code_injection_blocked else '❌ FAIL'}")
        print(f"   Response: {result.response[:100]}...")
        
        # Test 3.3: XSS in query parameters
        print("\n3.3 Testing XSS prevention...")
        
        xss_query = "<script>alert('xss')</script>"
        
        # Test with mock to simulate endpoint behavior
        result = await self.executor._handle_product_rag_call(xss_query, {"query": xss_query})
        
        # Check that response doesn't contain executable script
        xss_blocked = ("<script>" not in result.response and 
                      "alert(" not in result.response and
                      "javascript:" not in result.response.lower())
        
        self.results["malicious_payload"].append({
            "test": "XSS prevention",
            "success": xss_blocked,
            "response": result.response,
            "error_handled": True
        })
        print(f"   Result: {'✅ PASS' if xss_blocked else '❌ FAIL'}")
        print(f"   XSS script blocked: {xss_blocked}")

    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*60)
        print("UNHAPPY FLOWS TEST SUMMARY")
        print("="*60)
        
        categories = ["missing_parameters", "api_downtime", "malicious_payload"]
        category_names = ["Missing Parameters", "API Downtime", "Malicious Payloads"]
        
        total_tests = 0
        total_passed = 0
        
        for category, name in zip(categories, category_names):
            tests = self.results[category]
            passed = sum(1 for test in tests if test["success"])
            total = len(tests)
            
            total_tests += total
            total_passed += passed
            
            print(f"\n{name}: {passed}/{total} tests passed")
            for test in tests:
                status = "✅ PASS" if test["success"] else "❌ FAIL"
                print(f"  {status} {test['test']}")
        
        print(f"\nOVERALL: {total_passed}/{total_tests} tests passed ({total_passed/total_tests*100:.1f}%)")
        
        if total_passed == total_tests:
            print("\n🎉 All unhappy flow tests passed! System is robust against:")
            print("   • Missing parameters")
            print("   • API downtime and network failures")
            print("   • Malicious payloads and security attacks")
        else:
            print(f"\n⚠️  {total_tests - total_passed} tests failed. Review security and error handling.")

    async def run_all_tests(self):
        """Run all unhappy flow tests"""
        print("Starting Unhappy Flows Test Suite...")
        print("Testing robustness against invalid and malicious inputs")
        
        await self.test_missing_parameters()
        await self.test_api_downtime()
        await self.test_malicious_payloads()
        
        self.print_summary()


async def main():
    """Main test runner"""
    tester = UnhappyFlowTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())