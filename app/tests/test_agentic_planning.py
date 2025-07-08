import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.services.agentic_chatbot_service import AgenticChatbotService
from app.core.memory_manager import MemoryManager
from app.core.planner import AgenticPlanner, PlanningContext, ActionType
from app.core.action_executor import ActionExecutor
from app.models.conversation import IntentType, ConversationState


class TestAgenticPlanning:
    @pytest.fixture
    async def agentic_service(self):
        memory_manager = MemoryManager(":memory:")
        return AgenticChatbotService(memory_manager)
    
    @pytest.mark.asyncio
    async def test_decision_making_outlet_inquiry(self, agentic_service):
        """Test decision-making process for outlet inquiry"""
        user_id = "test_user_agentic_1"
        
        # Test with complete information
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "Is there an outlet in SS2?"
        )
        
        # Verify planning details
        assert planning_details["intent"] == "outlet_inquiry"
        assert "ss2" in planning_details["entities"]["location"]
        assert planning_details["planned_action"] == "call_outlet_api"
        assert planning_details["execution_success"] == True
        assert "SS2 Outlet" in response
        
        # Test follow-up with missing info request
        response2, conv_id2, planning_details2 = await agentic_service.process_message_with_planning(
            user_id, "What time?", conv_id
        )
        
        assert conv_id == conv_id2
        assert planning_details2["planned_action"] == "call_outlet_api"
        assert "9:00" in response2
    
    @pytest.mark.asyncio
    async def test_decision_making_missing_information(self, agentic_service):
        """Test decision-making when information is missing"""
        user_id = "test_user_agentic_2"
        
        # Test with incomplete restaurant search
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "I want food"
        )
        
        # Should ask for more information
        assert planning_details["planned_action"] in ["request_missing_info", "ask_clarification"]
        assert "cuisine" in response.lower() or "type" in response.lower()
        
        # Provide more specific information
        response2, conv_id2, planning_details2 = await agentic_service.process_message_with_planning(
            user_id, "Japanese food in Petaling Jaya", conv_id
        )
        
        assert planning_details2["planned_action"] == "call_restaurant_api"
        assert planning_details2["execution_success"] == True
    
    @pytest.mark.asyncio
    async def test_decision_making_calculation(self, agentic_service):
        """Test decision-making for calculations"""
        user_id = "test_user_agentic_3"
        
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "Calculate 15 * 8"
        )
        
        assert planning_details["intent"] == "calculation"
        assert planning_details["planned_action"] == "call_calculator"
        assert planning_details["execution_success"] == True
        assert "120" in response
    
    @pytest.mark.asyncio
    async def test_decision_making_low_confidence(self, agentic_service):
        """Test decision-making with low confidence input"""
        user_id = "test_user_agentic_4"
        
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "Something something"
        )
        
        # Should ask for clarification due to low confidence
        assert planning_details["confidence"] < 0.5
        assert planning_details["planned_action"] in ["ask_clarification", "provide_response"]
        assert "help" in response.lower() or "clarify" in response.lower()
    
    @pytest.mark.asyncio
    async def test_action_execution_fallback(self, agentic_service):
        """Test fallback action execution when primary action fails"""
        user_id = "test_user_agentic_5"
        
        # Test with a scenario that might need fallback
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "Tell me about outlets in Mars"  # Non-existent location
        )
        
        # Should either succeed with error message or use fallback
        assert planning_details["execution_success"] in [True, False]
        if not planning_details["execution_success"]:
            assert planning_details.get("fallback_used", False)
    
    @pytest.mark.asyncio
    async def test_conversation_context_awareness(self, agentic_service):
        """Test that planning considers conversation context"""
        user_id = "test_user_agentic_6"
        
        # Start conversation about outlets
        response1, conv_id, planning_details1 = await agentic_service.process_message_with_planning(
            user_id, "Tell me about SS2 outlet"
        )
        
        # Follow up with context-dependent question
        response2, conv_id2, planning_details2 = await agentic_service.process_message_with_planning(
            user_id, "What are the opening hours?", conv_id
        )
        
        # Should understand this refers to SS2 outlet
        assert conv_id == conv_id2
        assert planning_details2["planned_action"] == "call_outlet_api"
        assert "9:00" in response2
    
    @pytest.mark.asyncio
    async def test_planning_analytics_tracking(self, agentic_service):
        """Test that planning decisions are tracked for analytics"""
        user_id = "test_user_agentic_7"
        
        # Make several decisions
        await agentic_service.process_message_with_planning(user_id, "SS2 outlet hours")
        await agentic_service.process_message_with_planning(user_id, "Calculate 10 + 5")
        await agentic_service.process_message_with_planning(user_id, "Japanese restaurants")
        
        # Get analytics
        analytics = agentic_service.get_planning_analytics()
        
        assert analytics["total_decisions"] >= 3
        assert "action_distribution" in analytics
        assert "intent_distribution" in analytics
        assert "success_rate" in analytics
        assert analytics["success_rate"] >= 0.0
        
        # Get decision points
        decision_points = agentic_service.get_decision_points_summary()
        assert len(decision_points) >= 3
        assert all("user_input" in dp for dp in decision_points)
        assert all("chosen_action" in dp for dp in decision_points)
        assert all("reasoning" in dp for dp in decision_points)
    
    @pytest.mark.asyncio
    async def test_urgency_detection(self, agentic_service):
        """Test detection of urgent requests"""
        user_id = "test_user_agentic_8"
        
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "I urgently need the SS2 outlet phone number now!"
        )
        
        # Should detect urgency and provide quick response
        assert planning_details["execution_success"] == True
        assert "+603-1234-5678" in response
    
    @pytest.mark.asyncio
    async def test_multi_intent_handling(self, agentic_service):
        """Test handling of messages with multiple possible intents"""
        user_id = "test_user_agentic_9"
        
        response, conv_id, planning_details = await agentic_service.process_message_with_planning(
            user_id, "Can you calculate the distance to SS2 outlet?"
        )
        
        # Should choose the most appropriate action
        assert planning_details["planned_action"] in ["call_outlet_api", "ask_clarification"]
        assert planning_details["confidence"] > 0.0


class TestPlannerComponents:
    @pytest.fixture
    def planner(self):
        return AgenticPlanner()
    
    @pytest.fixture
    def executor(self):
        return ActionExecutor()
    
    @pytest.mark.asyncio
    async def test_planner_completeness_analysis(self, planner):
        """Test planner's completeness analysis"""
        from app.models.conversation import ConversationMemory, ConversationState
        
        # Create test context
        memory = ConversationMemory(
            conversation_id="test",
            user_id="test_user",
            state=ConversationState.ACTIVE
        )
        
        context = PlanningContext(
            intent=IntentType.OUTLET_INQUIRY,
            entities={"location": "ss2"},
            confidence=0.9,
            conversation_memory=memory,
            user_message="SS2 outlet hours",
            missing_slots=[],
            available_slots={"location": "ss2"}
        )
        
        decision = await planner.plan_next_action(context)
        
        assert decision.primary_action.action_type == ActionType.CALL_OUTLET_API
        assert decision.confidence > 0.8
        assert "outlet" in decision.decision_reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_planner_missing_info_detection(self, planner):
        """Test planner's missing information detection"""
        from app.models.conversation import ConversationMemory, ConversationState
        
        memory = ConversationMemory(
            conversation_id="test",
            user_id="test_user",
            state=ConversationState.ACTIVE
        )
        
        # Context with missing critical information
        context = PlanningContext(
            intent=IntentType.OUTLET_INQUIRY,
            entities={},
            confidence=0.7,
            conversation_memory=memory,
            user_message="outlet hours",
            missing_slots=["location"],
            available_slots={}
        )
        
        decision = await planner.plan_next_action(context)
        
        assert decision.primary_action.action_type == ActionType.REQUEST_MISSING_INFO
        assert "location" in decision.primary_action.parameters.get("missing_slots", [])
    
    @pytest.mark.asyncio
    async def test_executor_calculator_action(self, executor):
        """Test executor's calculator action handling"""
        from app.core.planner import PlannerAction
        
        action = PlannerAction(
            action_type=ActionType.CALL_CALCULATOR,
            parameters={
                "input_data": {"expression": "25 + 35"},
                "context": "Calculate 25 + 35"
            },
            confidence=0.9,
            reasoning="Calculator operation requested"
        )
        
        context = {"user_message": "Calculate 25 + 35"}
        result = await executor._execute_action(action, context)
        
        assert result.success == True
        assert "60" in result.response
        assert result.data["calculation"]["result"] == 60.0
    
    @pytest.mark.asyncio
    async def test_executor_clarification_action(self, executor):
        """Test executor's clarification action handling"""
        from app.core.planner import PlannerAction
        
        action = PlannerAction(
            action_type=ActionType.ASK_CLARIFICATION,
            parameters={
                "clarification_type": "intent",
                "context": "unclear request"
            },
            confidence=0.8,
            reasoning="Intent unclear"
        )
        
        context = {"user_message": "something"}
        result = await executor._execute_action(action, context)
        
        assert result.success == True
        assert "clarify" in result.response.lower() or "help" in result.response.lower()
    
    @pytest.mark.asyncio
    async def test_executor_error_handling(self, executor):
        """Test executor's error handling"""
        from app.core.planner import PlannerAction
        
        # Test with invalid action type
        action = PlannerAction(
            action_type="invalid_action",  # This will fail
            parameters={},
            confidence=0.5,
            reasoning="Test error handling"
        )
        
        context = {"user_message": "test"}
        result = await executor._execute_action(action, context)
        
        assert result.success == False
        assert result.error is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])