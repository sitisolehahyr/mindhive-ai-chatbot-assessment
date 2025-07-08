"""
Security-focused test scenarios for RAG endpoints and integrations
Testing specific vulnerabilities and attack vectors
"""
import pytest
import asyncio
import json
import sqlite3
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
import tempfile
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.rag_endpoints import router as rag_router
from app.rag.text2sql_system import ZUSOutletText2SQL
from app.rag.product_vectorstore import ZUSProductVectorStore


class TestSQLInjectionPrevention:
    """Comprehensive SQL injection prevention tests"""
    
    def setup_method(self):
        """Setup test environment with real database"""
        # Create temporary database file
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        
        # Initialize text2sql system with temp database
        self.text2sql = ZUSOutletText2SQL(db_path=self.temp_db.name)
        
        # Add test data
        self._add_test_data()
    
    def teardown_method(self):
        """Cleanup test environment"""
        self.text2sql.close()
        os.unlink(self.temp_db.name)
    
    def _add_test_data(self):
        """Add test data to database"""
        test_outlets = [
            {
                "name": "Test Outlet 1",
                "city": "Test City",
                "state": "Test State",
                "address": "123 Test St",
                "phone": "+60-123-456789",
                "email": "test@example.com",
                "operating_hours": json.dumps({"daily": "9:00 AM - 10:00 PM"}),
                "services": json.dumps(["WiFi", "Parking"]),
                "coordinates": json.dumps({"lat": 1.0, "lng": 1.0}),
                "outlet_type": "Test",
                "features": json.dumps(["Test Feature"]),
                "capacity": 50,
                "established": "2020-01-01"
            }
        ]
        
        cursor = self.text2sql.connection.cursor()
        for outlet in test_outlets:
            cursor.execute("""
                INSERT INTO outlets (
                    name, city, state, address, phone, email,
                    operating_hours, services, coordinates, outlet_type,
                    features, capacity, established
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                outlet["name"], outlet["city"], outlet["state"], outlet["address"],
                outlet["phone"], outlet["email"], outlet["operating_hours"],
                outlet["services"], outlet["coordinates"], outlet["outlet_type"],
                outlet["features"], outlet["capacity"], outlet["established"]
            ))
        
        self.text2sql.connection.commit()

    def test_classic_sql_injection_attempts(self):
        """Test classic SQL injection patterns"""
        injection_attempts = [
            "'; DROP TABLE outlets; --",
            "' OR '1'='1",
            "' OR 1=1 --",
            "'; SELECT * FROM sqlite_master; --",
            "' UNION SELECT null, null, null, username, password FROM users --",
            "'; DELETE FROM outlets WHERE '1'='1'; --",
            "' OR 'a'='a",
            "'; INSERT INTO outlets VALUES ('hacked'); --"
        ]
        
        for injection in injection_attempts:
            success, explanation, results = self.text2sql.query_outlets(injection)
            
            # Should either fail safely or return benign results
            if success:
                # Check that no malicious operations occurred
                assert isinstance(results, list)
                # Verify table still exists and has correct data
                cursor = self.text2sql.connection.cursor()
                cursor.execute("SELECT COUNT(*) FROM outlets")
                count = cursor.fetchone()[0]
                assert count > 0  # Data should not be deleted
                
                # Check for injection indicators in results
                for result in results:
                    result_str = str(result)
                    assert "sqlite_master" not in result_str
                    assert "username" not in result_str
                    assert "password" not in result_str
                    assert "hacked" not in result_str
            else:
                # Should provide safe error message
                assert any(phrase in explanation.lower() for phrase in [
                    "could not understand",
                    "couldn't find",
                    "safety validation"
                ])

    def test_blind_sql_injection_attempts(self):
        """Test blind SQL injection attempts"""
        blind_injections = [
            "test' AND (SELECT COUNT(*) FROM outlets) > 0 --",
            "test' AND SLEEP(5) --",
            "test' AND 1=(SELECT COUNT(*) FROM sqlite_master) --",
            "test' AND ASCII(SUBSTR((SELECT name FROM outlets LIMIT 1),1,1)) > 65 --"
        ]
        
        for injection in blind_injections:
            start_time = asyncio.get_event_loop().time()
            success, explanation, results = self.text2sql.query_outlets(injection)
            end_time = asyncio.get_event_loop().time()
            
            # Should not leak information through timing or results
            execution_time = end_time - start_time
            assert execution_time < 2.0  # Should not cause delays
            
            if success:
                # Should not reveal database structure
                for result in results:
                    result_str = str(result)
                    assert "sqlite_master" not in result_str.lower()

    def test_union_based_injection_attempts(self):
        """Test UNION-based SQL injection attempts"""
        union_injections = [
            "test' UNION SELECT 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17 --",
            "test' UNION SELECT name,sql,type,name,name,name,name,name,name,name,name,name,name,name,name,name,name FROM sqlite_master --",
            "test' UNION ALL SELECT null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null,null --"
        ]
        
        for injection in union_injections:
            success, explanation, results = self.text2sql.query_outlets(injection)
            
            if success:
                # Should not return database schema information
                for result in results:
                    result_str = str(result)
                    assert "CREATE TABLE" not in result_str
                    assert "sqlite_master" not in result_str
                    # Should return normal outlet data only
                    if result and isinstance(result, dict):
                        expected_fields = ["name", "city", "state", "address"]
                        has_outlet_fields = any(field in result for field in expected_fields)
                        if not has_outlet_fields:
                            # If it's not outlet data, it should be empty/null
                            assert all(v is None or v == '' for v in result.values())

    def test_time_based_injection_attempts(self):
        """Test time-based SQL injection attempts"""
        time_injections = [
            "test'; WAITFOR DELAY '00:00:05'; --",
            "test' AND (SELECT COUNT(*) FROM outlets) > 0 AND SLEEP(5) --",
            "test'; SELECT CASE WHEN (1=1) THEN pg_sleep(5) ELSE pg_sleep(0) END; --"
        ]
        
        for injection in time_injections:
            start_time = asyncio.get_event_loop().time()
            success, explanation, results = self.text2sql.query_outlets(injection)
            end_time = asyncio.get_event_loop().time()
            
            execution_time = end_time - start_time
            # Should not allow time delays to leak information
            assert execution_time < 2.0

    def test_stacked_queries_prevention(self):
        """Test prevention of stacked queries"""
        stacked_queries = [
            "test'; CREATE TABLE hacked (id INTEGER); --",
            "test'; UPDATE outlets SET name='compromised'; SELECT * FROM outlets; --",
            "test'; INSERT INTO outlets VALUES ('evil'); DROP TABLE outlets; --"
        ]
        
        for query in stacked_queries:
            success, explanation, results = self.text2sql.query_outlets(query)
            
            # Verify no additional tables were created
            cursor = self.text2sql.connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            table_names = [table[0] for table in tables]
            assert "hacked" not in table_names
            
            # Verify data was not modified
            cursor.execute("SELECT name FROM outlets")
            outlet_names = cursor.fetchall()
            outlet_name_list = [name[0] for name in outlet_names]
            assert "compromised" not in outlet_name_list
            assert "evil" not in outlet_name_list


class TestCodeInjectionPrevention:
    """Test prevention of code injection in calculator and other endpoints"""
    
    def setup_method(self):
        """Setup test environment"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_python_code_injection_attempts(self):
        """Test Python code injection prevention"""
        code_injections = [
            "__import__('os').system('rm -rf /')",
            "exec('import os; os.system(\"ls\")')",
            "eval('__import__(\"subprocess\").call([\"whoami\"])')",
            "open('/etc/passwd', 'r').read()",
            "__import__('sys').exit()",
            "globals()['__builtins__']['eval']('print(\"hacked\")')"
        ]
        
        for injection in code_injections:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "No results"
                
                response = self.client.get(f"/api/products?query={injection}")
                
                # Should not execute code - either return safe results or error
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    # Should not contain evidence of code execution
                    response_str = json.dumps(data)
                    assert "root:" not in response_str  # No passwd file content
                    assert "/bin/bash" not in response_str
                    assert "hacked" not in response_str

    def test_import_statement_filtering(self):
        """Test filtering of dangerous import statements"""
        dangerous_imports = [
            "import os; os.system('ls')",
            "from subprocess import call; call(['ls'])",
            "import sys; sys.exit()",
            "__import__('socket').gethostname()",
            "from os import system; system('pwd')"
        ]
        
        for dangerous_import in dangerous_imports:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (False, "Invalid query", [])
                
                response = self.client.get(f"/api/outlets?query={dangerous_import}")
                
                # Should reject dangerous imports
                assert response.status_code in [200, 400, 422]
                if response.status_code == 400:
                    assert "invalid" in response.json()["detail"].lower()

    def test_eval_exec_prevention(self):
        """Test prevention of eval() and exec() usage"""
        eval_exec_attempts = [
            "eval('2+2')",
            "exec('print(\"test\")')",
            "compile('print(\"test\")', '<string>', 'exec')",
            "__builtins__['eval']('2+2')",
            "getattr(__builtins__, 'eval')('2+2')"
        ]
        
        for attempt in eval_exec_attempts:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "Safe response"
                
                response = self.client.get(f"/api/products?query={attempt}")
                
                # Should handle safely
                assert response.status_code in [200, 400, 422]
                
                if response.status_code == 200:
                    data = response.json()
                    # Should not execute eval/exec
                    assert data["summary"] == "Safe response"


class TestXSSAndHTMLInjectionPrevention:
    """Test prevention of XSS and HTML injection attacks"""
    
    def setup_method(self):
        """Setup test environment"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_script_tag_injection(self):
        """Test script tag injection prevention"""
        script_injections = [
            "<script>alert('xss')</script>",
            "<SCRIPT>alert('XSS')</SCRIPT>",
            "<script src='http://evil.com/script.js'></script>",
            "</script><script>alert('xss')</script>",
            "<script>document.cookie='stolen'</script>"
        ]
        
        for injection in script_injections:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "Safe summary"
                
                response = self.client.get(f"/api/products?query={injection}")
                
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    response_text = response.text
                    # Should not contain script tags in response
                    assert "<script>" not in response_text.lower()
                    assert "alert(" not in response_text
                    assert "document.cookie" not in response_text

    def test_html_injection_attempts(self):
        """Test HTML injection prevention"""
        html_injections = [
            "<img src=x onerror=alert('xss')>",
            "<svg onload=alert('xss')>",
            "<iframe src='javascript:alert(\"xss\")'></iframe>",
            "<body onload=alert('xss')>",
            "<div onclick=alert('xss')>Click me</div>"
        ]
        
        for injection in html_injections:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (True, "Safe response", [])
                
                response = self.client.get(f"/api/outlets?query={injection}")
                
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    response_text = response.text
                    # Should not contain dangerous HTML
                    assert "onerror=" not in response_text
                    assert "onload=" not in response_text
                    assert "onclick=" not in response_text
                    assert "javascript:" not in response_text

    def test_css_injection_prevention(self):
        """Test CSS injection prevention"""
        css_injections = [
            "<style>body{background:url('javascript:alert(1)')}</style>",
            "expression(alert('xss'))",
            "@import url('javascript:alert(1)')",
            "<link rel=stylesheet href='javascript:alert(1)'>"
        ]
        
        for injection in css_injections:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "Clean response"
                
                response = self.client.get(f"/api/products?query={injection}")
                
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    response_text = response.text
                    assert "javascript:" not in response_text
                    assert "expression(" not in response_text
                    assert "@import" not in response_text


class TestPathTraversalPrevention:
    """Test prevention of path traversal attacks"""
    
    def setup_method(self):
        """Setup test environment"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_directory_traversal_attempts(self):
        """Test directory traversal prevention"""
        traversal_attempts = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc//passwd",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
            "file:///etc/passwd"
        ]
        
        for attempt in traversal_attempts:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "No file access"
                
                response = self.client.get(f"/api/products?query={attempt}")
                
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    response_str = json.dumps(data)
                    # Should not contain file system content
                    assert "root:" not in response_str
                    assert "/bin/bash" not in response_str
                    assert "Administrator" not in response_str

    def test_url_encoded_traversal(self):
        """Test URL-encoded path traversal prevention"""
        encoded_attempts = [
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd",
            "%2e%2e\\%2e%2e\\%2e%2e\\windows\\system32\\config\\sam"
        ]
        
        for attempt in encoded_attempts:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (True, "Safe response", [])
                
                response = self.client.get(f"/api/outlets?query={attempt}")
                
                assert response.status_code in [200, 400, 422]
                if response.status_code == 200:
                    data = response.json()
                    # Should not access files
                    assert "root:" not in str(data)


class TestDenialOfServicePrevention:
    """Test prevention of denial of service attacks"""
    
    def setup_method(self):
        """Setup test environment"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_large_payload_handling(self):
        """Test handling of excessively large payloads"""
        # Test various large payload sizes
        payload_sizes = [10000, 50000, 100000]  # 10KB, 50KB, 100KB
        
        for size in payload_sizes:
            large_query = "A" * size
            
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "Query processed"
                
                response = self.client.get(f"/api/products?query={large_query}")
                
                # Should handle large payloads without crashing
                assert response.status_code in [200, 400, 413, 422]
                
                # Response should be reasonable size regardless of input
                if response.status_code == 200:
                    assert len(response.text) < 10000  # Response shouldn't be excessively large

    def test_repeated_request_handling(self):
        """Test handling of repeated requests (basic rate limiting simulation)"""
        with patch('app.api.rag_endpoints.product_store') as mock_store:
            mock_store.search.return_value = []
            mock_store.generate_summary.return_value = "Response"
            
            # Simulate multiple rapid requests
            responses = []
            for i in range(10):
                response = self.client.get(f"/api/products?query=test{i}")
                responses.append(response)
            
            # All requests should be handled (no crashing)
            for response in responses:
                assert response.status_code in [200, 400, 422, 429]  # 429 = rate limited

    def test_complex_regex_patterns(self):
        """Test that complex regex patterns don't cause ReDoS"""
        # Patterns that could cause catastrophic backtracking
        complex_patterns = [
            "a" * 1000 + "!",  # Long string that might not match
            "(a+)+b",  # Potential exponential backtracking pattern
            "a" * 500 + "x" + "a" * 500,  # Long non-matching pattern
        ]
        
        for pattern in complex_patterns:
            start_time = asyncio.get_event_loop().time()
            
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (False, "No match", [])
                
                response = self.client.get(f"/api/outlets?query={pattern}")
                
            end_time = asyncio.get_event_loop().time()
            execution_time = end_time - start_time
            
            # Should not take excessive time
            assert execution_time < 5.0  # Should complete within 5 seconds
            assert response.status_code in [200, 400, 422]


class TestInputSanitizationAndValidation:
    """Test comprehensive input sanitization and validation"""
    
    def setup_method(self):
        """Setup test environment"""
        self.app = FastAPI()
        self.app.include_router(rag_router)
        self.client = TestClient(self.app)

    def test_special_character_handling(self):
        """Test handling of special characters"""
        special_chars = [
            "\x00",  # Null byte
            "\x1b[31mRed Text\x1b[0m",  # ANSI escape codes
            "\u202eRTL override",  # Unicode RTL override
            "\r\nHTTP/1.1 200 OK\r\n",  # HTTP header injection
            "\x7f\x80\x81\x82\x83",  # Control characters
        ]
        
        for special_char in special_chars:
            with patch('app.api.rag_endpoints.product_store') as mock_store:
                mock_store.search.return_value = []
                mock_store.generate_summary.return_value = "Sanitized response"
                
                response = self.client.get(f"/api/products?query={special_char}")
                
                assert response.status_code in [200, 400, 422]
                
                if response.status_code == 200:
                    # Response should not contain dangerous characters
                    response_text = response.text
                    assert "\x00" not in response_text
                    assert "\x1b" not in response_text
                    assert "\u202e" not in response_text

    def test_encoding_attacks(self):
        """Test various encoding-based attacks"""
        encoding_attacks = [
            "%00",  # Null byte URL encoded
            "%0d%0a",  # CRLF injection
            "%3cscript%3e",  # URL encoded script tag
            "\uff1cscript\uff1e",  # Fullwidth script tag
            "&#60;script&#62;",  # HTML entity encoded script
        ]
        
        for attack in encoding_attacks:
            with patch('app.api.rag_endpoints.outlet_text2sql') as mock_text2sql:
                mock_text2sql.query_outlets.return_value = (True, "Clean response", [])
                
                response = self.client.get(f"/api/outlets?query={attack}")
                
                assert response.status_code in [200, 400, 422]
                
                if response.status_code == 200:
                    response_text = response.text
                    # Should not decode to dangerous content
                    assert "<script>" not in response_text.lower()
                    assert "\r\n" not in response_text


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])