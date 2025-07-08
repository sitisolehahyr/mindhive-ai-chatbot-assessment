import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.api.rag_endpoints import router
from app.rag.product_vectorstore import ZUSProductVectorStore, ProductDocument, SearchResult
from app.rag.text2sql_system import ZUSOutletText2SQL
from fastapi import FastAPI

# Create test app
app = FastAPI()
app.include_router(router)

client = TestClient(app)

class TestRAGEndpoints:
    """Test suite for RAG endpoints"""

    def setup_method(self):
        """Setup test fixtures"""
        self.sample_products = [
            {
                "name": "ZUS Test Tumbler",
                "category": "Drinkware",
                "price": "RM 45.00",
                "description": "Test tumbler for testing",
                "features": ["Test feature 1", "Test feature 2"],
                "availability": True
            }
        ]
        
        self.sample_outlets = [
            {
                "name": "ZUS Coffee Test Outlet",
                "city": "Test City",
                "state": "Test State",
                "address": "Test Address",
                "phone": "+60-123-456789",
                "operating_hours": {"daily": "9:00 AM - 10:00 PM"},
                "services": ["Dine-in", "WiFi"],
                "outlet_type": "Standalone"
            }
        ]

    @patch('app.api.rag_endpoints.product_store')
    def test_search_products_success(self, mock_product_store):
        """Test successful product search"""
        # Setup mock
        mock_document = ProductDocument(
            id="test_1",
            name="ZUS Test Tumbler",
            category="Drinkware",
            description="Test tumbler for testing",
            features=["Test feature 1", "Test feature 2"],
            price="RM 45.00",
            availability=True,
            metadata={},
            text_content="ZUS Test Tumbler Drinkware Test tumbler for testing Test feature 1 Test feature 2"
        )
        
        mock_result = SearchResult(
            document=mock_document,
            score=0.85,
            rank=1
        )
        
        mock_product_store.search.return_value = [mock_result]
        mock_product_store.generate_summary.return_value = "Found 1 test product"
        
        # Test request
        response = client.get("/api/products?query=test tumbler")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "test tumbler"
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "ZUS Test Tumbler"
        assert data["results"][0]["score"] == 0.85
        assert data["summary"] == "Found 1 test product"

    @patch('app.api.rag_endpoints.product_store')
    def test_search_products_with_filters(self, mock_product_store):
        """Test product search with filters"""
        mock_product_store.search.return_value = []
        mock_product_store.generate_summary.return_value = "No products found"
        
        response = client.get(
            "/api/products?query=tumbler&category=Drinkware&availability=true&min_price=40&max_price=50"
        )
        
        assert response.status_code == 200
        
        # Verify filters were applied
        call_args = mock_product_store.search.call_args
        filters = call_args[1]["filters"]
        
        assert filters["category"] == "Drinkware"
        assert filters["availability"] == True
        assert filters["price_range"]["min"] == 40
        assert filters["price_range"]["max"] == 50

    @patch('app.api.rag_endpoints.product_store')
    def test_search_products_hybrid_search(self, mock_product_store):
        """Test hybrid search mode"""
        mock_product_store.hybrid_search.return_value = []
        mock_product_store.generate_summary.return_value = "No products found"
        
        response = client.get("/api/products?query=tumbler&search_type=hybrid")
        
        assert response.status_code == 200
        mock_product_store.hybrid_search.assert_called_once()

    def test_search_products_service_unavailable(self):
        """Test product search when service is unavailable"""
        with patch('app.api.rag_endpoints.product_store', None):
            response = client.get("/api/products?query=tumbler")
            assert response.status_code == 503
            assert "not available" in response.json()["detail"]

    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_query_outlets_success(self, mock_text2sql):
        """Test successful outlet query"""
        mock_text2sql.query_outlets.return_value = (
            True, 
            "Found 1 outlet",
            [self.sample_outlets[0]]
        )
        mock_text2sql.generate_response_summary.return_value = "Found 1 ZUS Coffee outlet"
        
        response = client.get("/api/outlets?query=outlets in test city")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["query"] == "outlets in test city"
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "ZUS Coffee Test Outlet"
        assert data["sql_explanation"] == "Found 1 outlet"

    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_query_outlets_failed(self, mock_text2sql):
        """Test failed outlet query"""
        mock_text2sql.query_outlets.return_value = (
            False, 
            "Invalid query",
            []
        )
        
        response = client.get("/api/outlets?query=invalid query")
        
        assert response.status_code == 400
        assert "Invalid query" in response.json()["detail"]

    def test_query_outlets_service_unavailable(self):
        """Test outlet query when service is unavailable"""
        with patch('app.api.rag_endpoints.outlet_text2sql', None):
            response = client.get("/api/outlets?query=outlets")
            assert response.status_code == 503

    @patch('app.api.rag_endpoints.product_store')
    def test_get_product_categories(self, mock_product_store):
        """Test get product categories"""
        mock_product_store.get_categories.return_value = ["Drinkware", "Accessories"]
        
        response = client.get("/api/products/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert data["categories"] == ["Drinkware", "Accessories"]

    @patch('app.api.rag_endpoints.product_store')
    def test_get_product_stats(self, mock_product_store):
        """Test get product statistics"""
        mock_stats = {
            "total_documents": 8,
            "categories": {"Drinkware": 8},
            "availability": {"available": 7, "unavailable": 1}
        }
        mock_product_store.get_statistics.return_value = mock_stats
        
        response = client.get("/api/products/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_documents"] == 8

    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_get_outlet_schema(self, mock_text2sql):
        """Test get outlet schema"""
        mock_schema = {
            "columns": [
                {"name": "name", "type": "TEXT"},
                {"name": "city", "type": "TEXT"}
            ],
            "sample_data": [{"name": "Test Outlet", "city": "Test City"}]
        }
        mock_text2sql.get_schema_info.return_value = mock_schema
        
        response = client.get("/api/outlets/schema")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["columns"]) == 2

    @patch('app.api.rag_endpoints.product_store')
    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_health_check(self, mock_text2sql, mock_product_store):
        """Test health check endpoint"""
        mock_product_store.documents = [Mock()] * 8
        mock_product_store.index = Mock()
        mock_text2sql.connection = Mock()
        
        response = client.get("/api/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["services"]["product_search"] == True
        assert data["services"]["outlet_query"] == True
        assert data["services"]["product_search_details"]["total_products"] == 8

    def test_validation_errors(self):
        """Test request validation errors"""
        # Missing query parameter
        response = client.get("/api/products")
        assert response.status_code == 422
        
        # Invalid top_k value
        response = client.get("/api/products?query=test&top_k=0")
        assert response.status_code == 422
        
        # Invalid limit value
        response = client.get("/api/outlets?query=test&limit=0")
        assert response.status_code == 422

    @patch('app.api.rag_endpoints.product_store')
    def test_search_products_exception_handling(self, mock_product_store):
        """Test exception handling in product search"""
        mock_product_store.search.side_effect = Exception("Database error")
        
        response = client.get("/api/products?query=test")
        
        assert response.status_code == 500
        assert "Database error" in response.json()["detail"]

    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_query_outlets_exception_handling(self, mock_text2sql):
        """Test exception handling in outlet query"""
        mock_text2sql.query_outlets.side_effect = Exception("SQL error")
        
        response = client.get("/api/outlets?query=test")
        
        assert response.status_code == 500
        assert "SQL error" in response.json()["detail"]

    def test_query_parameter_validation(self):
        """Test query parameter validation"""
        # Test top_k limits
        response = client.get("/api/products?query=test&top_k=25")
        assert response.status_code == 422
        
        # Test limit values
        response = client.get("/api/outlets?query=test&limit=100")
        assert response.status_code == 422

    @patch('app.api.rag_endpoints.product_store')
    def test_search_different_types(self, mock_product_store):
        """Test different search types"""
        mock_product_store.search.return_value = []
        mock_product_store.hybrid_search.return_value = []
        mock_product_store._keyword_search.return_value = []
        mock_product_store.generate_summary.return_value = "No results"
        
        # Test semantic search (default)
        response = client.get("/api/products?query=test")
        assert response.status_code == 200
        mock_product_store.search.assert_called()
        
        # Test hybrid search
        response = client.get("/api/products?query=test&search_type=hybrid")
        assert response.status_code == 200
        mock_product_store.hybrid_search.assert_called()
        
        # Test keyword search
        response = client.get("/api/products?query=test&search_type=keyword")
        assert response.status_code == 200
        mock_product_store._keyword_search.assert_called()

    @patch('app.api.rag_endpoints.outlet_text2sql')
    def test_outlet_query_limit(self, mock_text2sql):
        """Test outlet query with different limits"""
        # Create more results than limit
        mock_results = [self.sample_outlets[0]] * 15
        mock_text2sql.query_outlets.return_value = (True, "Found 15 outlets", mock_results)
        mock_text2sql.generate_response_summary.return_value = "Found 15 outlets"
        
        response = client.get("/api/outlets?query=all outlets&limit=5")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 5  # Limited to 5
        assert data["total_found"] == 15  # But total found is 15

if __name__ == "__main__":
    pytest.main([__file__, "-v"])