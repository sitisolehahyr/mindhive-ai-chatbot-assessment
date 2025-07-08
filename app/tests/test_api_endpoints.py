import pytest
from fastapi.testclient import TestClient
from main import app
import json


class TestChatAPI:
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test API health check"""
        response = client.get("/api/chat/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "chatbot"}
    
    def test_send_message_new_conversation(self, client):
        """Test sending a message to start a new conversation"""
        payload = {
            "message": "Is there an outlet in Petaling Jaya?",
            "user_id": "test_user_api_1"
        }
        
        response = client.post("/api/chat/message", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "response" in data
        assert "conversation_id" in data
        assert "user_id" in data
        assert data["user_id"] == "test_user_api_1"
        assert "Yes!" in data["response"]
        assert data["conversation_id"] is not None
    
    def test_send_message_existing_conversation(self, client):
        """Test sending multiple messages in the same conversation"""
        # First message
        payload1 = {
            "message": "Is there an outlet in Petaling Jaya?",
            "user_id": "test_user_api_2"
        }
        response1 = client.post("/api/chat/message", json=payload1)
        conv_id = response1.json()["conversation_id"]
        
        # Second message in same conversation
        payload2 = {
            "message": "SS2 opening hours?",
            "user_id": "test_user_api_2",
            "conversation_id": conv_id
        }
        response2 = client.post("/api/chat/message", json=payload2)
        
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["conversation_id"] == conv_id
        assert "9:00" in data2["response"]
    
    def test_get_conversation_history(self, client):
        """Test retrieving conversation history"""
        # Create a conversation with multiple turns
        user_id = "test_user_api_3"
        
        # Turn 1
        payload1 = {
            "message": "Tell me about outlets",
            "user_id": user_id
        }
        response1 = client.post("/api/chat/message", json=payload1)
        conv_id = response1.json()["conversation_id"]
        
        # Turn 2
        payload2 = {
            "message": "SS2 location",
            "user_id": user_id,
            "conversation_id": conv_id
        }
        client.post("/api/chat/message", json=payload2)
        
        # Get history
        history_response = client.get(f"/api/chat/history/{conv_id}")
        assert history_response.status_code == 200
        
        history_data = history_response.json()
        assert "conversation_id" in history_data
        assert "turns" in history_data
        assert "slots" in history_data
        assert len(history_data["turns"]) == 2
        
        # Verify turn structure
        turn = history_data["turns"][0]
        assert "turn_id" in turn
        assert "user_message" in turn
        assert "bot_response" in turn
        assert "intent" in turn
        assert "entities" in turn
        assert "timestamp" in turn
        assert "confidence" in turn
    
    def test_get_nonexistent_conversation_history(self, client):
        """Test retrieving history for non-existent conversation"""
        fake_conv_id = "fake-conversation-id"
        response = client.get(f"/api/chat/history/{fake_conv_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_reset_conversation(self, client):
        """Test resetting a conversation"""
        # Create a conversation
        payload = {
            "message": "Hello",
            "user_id": "test_user_api_4"
        }
        response = client.post("/api/chat/message", json=payload)
        conv_id = response.json()["conversation_id"]
        
        # Reset the conversation
        reset_response = client.delete(f"/api/chat/conversation/{conv_id}")
        assert reset_response.status_code == 200
        assert "reset successfully" in reset_response.json()["message"]
        
        # Verify conversation is gone
        history_response = client.get(f"/api/chat/history/{conv_id}")
        assert history_response.status_code == 404
    
    def test_invalid_message_payload(self, client):
        """Test sending invalid message payload"""
        # Missing required fields
        payload = {
            "message": "Hello"
            # Missing user_id
        }
        
        response = client.post("/api/chat/message", json=payload)
        assert response.status_code == 422  # Validation error
    
    def test_empty_message(self, client):
        """Test sending empty message"""
        payload = {
            "message": "",
            "user_id": "test_user_api_5"
        }
        
        response = client.post("/api/chat/message", json=payload)
        assert response.status_code == 200
        # Should still work, just might give generic response
    
    def test_calculator_api_integration(self, client):
        """Test calculator functionality through API"""
        payload = {
            "message": "Calculate 15 + 25",
            "user_id": "test_user_api_calc"
        }
        
        response = client.post("/api/chat/message", json=payload)
        assert response.status_code == 200
        
        data = response.json()
        assert "40" in data["response"]
    
    def test_sequential_conversation_api(self, client):
        """Test the main assessment example through API"""
        user_id = "test_user_api_sequential"
        
        # Turn 1: "Is there an outlet in Petaling Jaya?"
        payload1 = {
            "message": "Is there an outlet in Petaling Jaya?",
            "user_id": user_id
        }
        response1 = client.post("/api/chat/message", json=payload1)
        assert response1.status_code == 200
        data1 = response1.json()
        conv_id = data1["conversation_id"]
        assert "Yes!" in data1["response"]
        
        # Turn 2: "SS 2, whats the opening time?"
        payload2 = {
            "message": "SS 2, whats the opening time?",
            "user_id": user_id,
            "conversation_id": conv_id
        }
        response2 = client.post("/api/chat/message", json=payload2)
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["conversation_id"] == conv_id
        assert "9:00" in data2["response"]
        
        # Verify conversation history
        history_response = client.get(f"/api/chat/history/{conv_id}")
        history_data = history_response.json()
        assert len(history_data["turns"]) == 2
        assert "pending_location" in history_data["slots"]
        assert history_data["slots"]["pending_location"]["value"] == "ss2"
    
    def test_cors_headers(self, client):
        """Test CORS headers are properly set"""
        response = client.options("/api/chat/message")
        # FastAPI/Starlette handles OPTIONS automatically with CORS middleware
        assert response.status_code in [200, 405]  # 405 is also acceptable for OPTIONS
    
    def test_concurrent_api_conversations(self, client):
        """Test multiple concurrent conversations through API"""
        # User 1 conversation
        payload1a = {
            "message": "Outlet in SS2?",
            "user_id": "user1_api"
        }
        response1a = client.post("/api/chat/message", json=payload1a)
        conv1_id = response1a.json()["conversation_id"]
        
        # User 2 conversation
        payload2a = {
            "message": "Calculate 10 + 20",
            "user_id": "user2_api"
        }
        response2a = client.post("/api/chat/message", json=payload2a)
        conv2_id = response2a.json()["conversation_id"]
        
        # Continue user 1 conversation
        payload1b = {
            "message": "Opening hours?",
            "user_id": "user1_api",
            "conversation_id": conv1_id
        }
        response1b = client.post("/api/chat/message", json=payload1b)
        
        # Continue user 2 conversation
        payload2b = {
            "message": "What is 5 * 6?",
            "user_id": "user2_api",
            "conversation_id": conv2_id
        }
        response2b = client.post("/api/chat/message", json=payload2b)
        
        # Verify conversations are separate
        assert conv1_id != conv2_id
        assert "9:00" in response1b.json()["response"]
        assert "30" in response2b.json()["response"]
    
    def test_api_error_handling(self, client):
        """Test API error handling for various scenarios"""
        # Test with malformed JSON
        response = client.post(
            "/api/chat/message",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422
        
        # Test with wrong conversation ID format
        payload = {
            "message": "Hello",
            "user_id": "test_user",
            "conversation_id": "invalid-format"
        }
        response = client.post("/api/chat/message", json=payload)
        # Should still work but create new conversation or handle gracefully
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])