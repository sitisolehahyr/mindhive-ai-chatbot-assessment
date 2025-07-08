import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.chatbot_service import ChatbotService
from app.core.memory_manager import MemoryManager
from app.models.conversation import IntentType, ConversationState


class TestConversationFlows:
    @pytest.fixture
    async def chatbot_service(self):
        memory_manager = MemoryManager(":memory:")
        return ChatbotService(memory_manager)
    
    @pytest.mark.asyncio
    async def test_sequential_outlet_inquiry_happy_path(self, chatbot_service):
        """Test the main example flow from the assessment"""
        user_id = "test_user_1"
        
        # Turn 1: Initial outlet inquiry
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Is there an outlet in Petaling Jaya?"
        )
        assert "Yes!" in response1
        assert "SS2" in response1
        assert conv_id is not None
        
        # Turn 2: Specify outlet location
        response2, conv_id2 = await chatbot_service.process_message(
            user_id, "SS 2, whats the opening time?", conv_id
        )
        assert conv_id == conv_id2
        assert "9:00" in response2
        assert "AM" in response2
        
        # Verify conversation memory
        memory = await chatbot_service.get_conversation_history(conv_id)
        assert memory is not None
        assert len(memory.turns) == 2
        assert memory.turns[0].intent == IntentType.OUTLET_INQUIRY
        assert memory.turns[1].intent == IntentType.OUTLET_INQUIRY
        
        # Verify slots are tracked
        assert memory.get_slot_value('pending_location') == 'ss2'
        assert memory.get_slot_value('last_query_type') == 'opening_hours'
    
    @pytest.mark.asyncio
    async def test_interrupted_conversation_flow(self, chatbot_service):
        """Test when user changes topic mid-conversation"""
        user_id = "test_user_2"
        
        # Turn 1: Start outlet inquiry
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Is there an outlet in Petaling Jaya?"
        )
        assert "Yes!" in response1
        
        # Turn 2: Interrupt with calculation
        response2, conv_id2 = await chatbot_service.process_message(
            user_id, "Calculate 10 + 5", conv_id
        )
        assert conv_id == conv_id2
        assert "15" in response2
        
        # Turn 3: Return to outlet inquiry with specific location
        response3, conv_id3 = await chatbot_service.process_message(
            user_id, "SS2 opening hours", conv_id
        )
        assert conv_id == conv_id3
        assert "9:00" in response3
        
        # Verify conversation memory persists across interruptions
        memory = await chatbot_service.get_conversation_history(conv_id)
        assert len(memory.turns) == 3
        assert memory.turns[0].intent == IntentType.OUTLET_INQUIRY
        assert memory.turns[1].intent == IntentType.CALCULATION
        assert memory.turns[2].intent == IntentType.OUTLET_INQUIRY
    
    @pytest.mark.asyncio
    async def test_multi_turn_outlet_disambiguation(self, chatbot_service):
        """Test disambiguation when multiple outlets exist"""
        user_id = "test_user_3"
        
        # Turn 1: General outlet inquiry
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Do you have any outlets?"
        )
        assert "SS2" in response1
        assert "Mid Valley" in response1
        assert "1 Utama" in response1
        
        # Turn 2: Specify Mid Valley
        response2, conv_id2 = await chatbot_service.process_message(
            user_id, "Mid Valley", conv_id
        )
        assert "Mid Valley" in response2
        assert "10:00 AM" in response2
        
        # Turn 3: Ask for contact info
        response3, conv_id3 = await chatbot_service.process_message(
            user_id, "What's the phone number?", conv_id
        )
        assert "+603-8765-4321" in response3
    
    @pytest.mark.asyncio
    async def test_unknown_location_handling(self, chatbot_service):
        """Test graceful handling of unknown locations"""
        user_id = "test_user_4"
        
        response, conv_id = await chatbot_service.process_message(
            user_id, "Is there an outlet in Johor Bahru?"
        )
        assert "sorry" in response.lower()
        assert "Petaling Jaya" in response
        assert "Mid Valley" in response
    
    @pytest.mark.asyncio
    async def test_calculation_tool_integration(self, chatbot_service):
        """Test calculator functionality"""
        user_id = "test_user_5"
        
        # Test addition
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Calculate 25 + 15"
        )
        assert "40" in response1
        
        # Test subtraction
        response2, _ = await chatbot_service.process_message(
            user_id, "What is 100 - 37", conv_id
        )
        assert "63" in response2
        
        # Test multiplication
        response3, _ = await chatbot_service.process_message(
            user_id, "Multiply 8 times 7", conv_id
        )
        assert "56" in response3
        
        # Test division
        response4, _ = await chatbot_service.process_message(
            user_id, "Divide 100 by 4", conv_id
        )
        assert "25" in response4
        
        # Test division by zero
        response5, _ = await chatbot_service.process_message(
            user_id, "10 divided by 0", conv_id
        )
        assert "can't divide by zero" in response5.lower()
    
    @pytest.mark.asyncio
    async def test_conversation_context_tracking(self, chatbot_service):
        """Test that conversation context is maintained across turns"""
        user_id = "test_user_6"
        
        # Turn 1
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Tell me about outlets"
        )
        
        # Turn 2
        response2, _ = await chatbot_service.process_message(
            user_id, "What about SS2?", conv_id
        )
        
        # Turn 3
        response3, _ = await chatbot_service.process_message(
            user_id, "Opening hours?", conv_id
        )
        
        # Verify context is maintained
        memory = await chatbot_service.get_conversation_history(conv_id)
        context = memory.get_conversation_context()
        
        assert "outlets" in context.lower()
        assert "ss2" in context.lower()
        assert len(memory.turns) == 3
    
    @pytest.mark.asyncio
    async def test_conversation_state_management(self, chatbot_service):
        """Test conversation state transitions"""
        user_id = "test_user_7"
        
        # Create conversation
        response, conv_id = await chatbot_service.process_message(
            user_id, "Hello"
        )
        
        memory = await chatbot_service.get_conversation_history(conv_id)
        assert memory.state == ConversationState.ACTIVE
        
        # Test conversation reset
        await chatbot_service.reset_conversation(conv_id)
        
        # Verify conversation is deleted
        memory_after_reset = await chatbot_service.get_conversation_history(conv_id)
        assert memory_after_reset is None
    
    @pytest.mark.asyncio
    async def test_slot_persistence_across_turns(self, chatbot_service):
        """Test that slots are maintained across conversation turns"""
        user_id = "test_user_8"
        
        # Turn 1: Set location slot
        response1, conv_id = await chatbot_service.process_message(
            user_id, "Is there an outlet in SS2?"
        )
        
        # Turn 2: Different topic
        response2, _ = await chatbot_service.process_message(
            user_id, "Calculate 5 + 3", conv_id
        )
        
        # Turn 3: Return to outlet topic - should remember SS2
        response3, _ = await chatbot_service.process_message(
            user_id, "What time do you open?", conv_id
        )
        
        memory = await chatbot_service.get_conversation_history(conv_id)
        assert memory.get_slot_value('pending_location') == 'ss2'
        assert "9:00" in response3
    
    @pytest.mark.asyncio
    async def test_multiple_concurrent_conversations(self, chatbot_service):
        """Test handling multiple conversations simultaneously"""
        user1_id = "user1"
        user2_id = "user2"
        
        # User 1 starts conversation
        response1a, conv1_id = await chatbot_service.process_message(
            user1_id, "Outlet in SS2?"
        )
        
        # User 2 starts different conversation
        response2a, conv2_id = await chatbot_service.process_message(
            user2_id, "Calculate 10 + 20"
        )
        
        # User 1 continues their conversation
        response1b, _ = await chatbot_service.process_message(
            user1_id, "Opening hours?", conv1_id
        )
        
        # User 2 continues their conversation
        response2b, _ = await chatbot_service.process_message(
            user2_id, "What is 5 * 6?", conv2_id
        )
        
        # Verify conversations are separate
        assert conv1_id != conv2_id
        assert "9:00" in response1b
        assert "30" in response2b
        
        # Verify separate memories
        memory1 = await chatbot_service.get_conversation_history(conv1_id)
        memory2 = await chatbot_service.get_conversation_history(conv2_id)
        
        assert memory1.user_id == user1_id
        assert memory2.user_id == user2_id
        assert memory1.turns[0].intent == IntentType.OUTLET_INQUIRY
        assert memory2.turns[0].intent == IntentType.CALCULATION
    
    @pytest.mark.asyncio
    async def test_entity_extraction_accuracy(self, chatbot_service):
        """Test accuracy of entity extraction from user messages"""
        user_id = "test_user_9"
        
        # Test location extraction variations
        test_cases = [
            ("SS2 outlet", "ss2"),
            ("Mid Valley location", "mid_valley"),
            ("1 Utama branch", "one_utama"),
            ("Petaling Jaya store", "ss2"),  # Should map to SS2
            ("KL outlet", "mid_valley"),  # Should map to Mid Valley
        ]
        
        for message, expected_location in test_cases:
            response, conv_id = await chatbot_service.process_message(
                user_id, f"Tell me about {message}"
            )
            
            memory = await chatbot_service.get_conversation_history(conv_id)
            actual_location = memory.get_slot_value('pending_location')
            
            assert actual_location == expected_location, f"Failed for {message}: expected {expected_location}, got {actual_location}"
            
            # Reset conversation for next test
            await chatbot_service.reset_conversation(conv_id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])