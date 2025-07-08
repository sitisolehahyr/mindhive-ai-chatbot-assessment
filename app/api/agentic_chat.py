from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.agentic_chatbot_service import AgenticChatbotService
from app.core.memory_manager import MemoryManager


class AgenticChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None


class AgenticChatResponse(BaseModel):
    response: str
    conversation_id: str
    user_id: str
    planning_details: Dict[str, Any]


class PlanningAnalyticsResponse(BaseModel):
    analytics: Dict[str, Any]
    decision_points: list


# Initialize agentic chatbot service
memory_manager = MemoryManager()
agentic_chatbot_service = AgenticChatbotService(memory_manager)

router = APIRouter(prefix="/api/agentic-chat", tags=["agentic-chat"])


@router.post("/message", response_model=AgenticChatResponse)
async def send_agentic_message(request: AgenticChatRequest):
    """
    Send a message to the agentic chatbot with full planning details
    
    This endpoint demonstrates Part 2 of the Mindhive Assessment:
    - Shows how the bot decides its next action
    - Returns planning reasoning and execution details
    """
    try:
        response, conversation_id, planning_details = await agentic_chatbot_service.process_message_with_planning(
            user_id=request.user_id,
            message=request.message,
            conversation_id=request.conversation_id
        )
        
        return AgenticChatResponse(
            response=response,
            conversation_id=conversation_id,
            user_id=request.user_id,
            planning_details=planning_details
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics", response_model=PlanningAnalyticsResponse)
async def get_planning_analytics():
    """
    Get analytics about planning decisions and execution
    
    Provides insights into:
    - Action distribution
    - Success rates
    - Decision reasoning patterns
    - Performance metrics
    """
    try:
        analytics = agentic_chatbot_service.get_planning_analytics()
        decision_points = agentic_chatbot_service.get_decision_points_summary()
        
        return PlanningAnalyticsResponse(
            analytics=analytics,
            decision_points=decision_points[-10:]  # Return last 10 decision points
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/decision-trace/{conversation_id}")
async def get_decision_trace(conversation_id: str):
    """
    Get detailed decision trace for a specific conversation
    
    Shows the complete decision-making process:
    1. Intent parsing
    2. Missing information analysis
    3. Action planning
    4. Execution results
    """
    try:
        # Filter decision log for this conversation
        conversation_decisions = []
        for entry in agentic_chatbot_service.decision_log:
            # Note: In a production system, you'd link decisions to conversation IDs
            conversation_decisions.append({
                "step": len(conversation_decisions) + 1,
                "user_input": entry["user_message"],
                "parsed_intent": {
                    "intent": entry["intent"],
                    "entities": entry["entities"],
                    "confidence": entry["confidence"]
                },
                "planning_decision": {
                    "chosen_action": entry["planned_action"],
                    "reasoning": entry["decision_reasoning"],
                    "confidence": entry.get("action_confidence", 0.0)
                },
                "execution_result": {
                    "success": entry["execution_success"],
                    "execution_time": entry["execution_time"],
                    "response": entry["response"]
                },
                "timestamp": entry["timestamp"]
            })
        
        return {
            "conversation_id": conversation_id,
            "decision_trace": conversation_decisions[-10:],  # Last 10 decisions
            "summary": {
                "total_decisions": len(conversation_decisions),
                "success_rate": sum(1 for d in conversation_decisions if d["execution_result"]["success"]) / max(len(conversation_decisions), 1),
                "avg_confidence": sum(d["parsed_intent"]["confidence"] for d in conversation_decisions) / max(len(conversation_decisions), 1)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain-decision")
async def explain_decision(request: AgenticChatRequest):
    """
    Explain the decision-making process without executing actions
    
    This endpoint shows:
    1. How the intent would be parsed
    2. What information is missing
    3. What action would be chosen and why
    4. Alternative actions considered
    """
    try:
        # Create a temporary planning context without execution
        memory = await agentic_chatbot_service.memory_manager.get_conversation(request.conversation_id) if request.conversation_id else None
        
        if not memory:
            # Create temporary memory for analysis
            from app.models.conversation import ConversationMemory, ConversationState
            memory = ConversationMemory(
                conversation_id="temp",
                user_id=request.user_id,
                state=ConversationState.ACTIVE
            )
        
        # Parse intent
        intent, entities, confidence = await agentic_chatbot_service._parse_intent(request.message, memory)
        
        # Create planning context
        from app.core.planner import PlanningContext
        planning_context = PlanningContext(
            intent=intent,
            entities=entities,
            confidence=confidence,
            conversation_memory=memory,
            user_message=request.message,
            missing_slots=agentic_chatbot_service._identify_missing_slots(intent, entities),
            available_slots=entities
        )
        
        # Get planning decision
        decision = await agentic_chatbot_service.planner.plan_next_action(planning_context)
        
        # Format explanation
        explanation = {
            "user_input": request.message,
            "intent_analysis": {
                "detected_intent": intent.value,
                "confidence": confidence,
                "extracted_entities": entities,
                "missing_information": planning_context.missing_slots
            },
            "planning_process": {
                "primary_action": {
                    "action_type": decision.primary_action.action_type.value,
                    "reasoning": decision.primary_action.reasoning,
                    "confidence": decision.primary_action.confidence,
                    "parameters": decision.primary_action.parameters
                },
                "fallback_actions": [
                    {
                        "action_type": action.action_type.value,
                        "reasoning": action.reasoning,
                        "confidence": action.confidence
                    } for action in decision.fallback_actions
                ],
                "decision_reasoning": decision.decision_reasoning,
                "overall_confidence": decision.confidence
            },
            "next_steps": {
                "will_execute": decision.primary_action.action_type.value,
                "expected_outcome": decision.primary_action.reasoning,
                "user_expectations": "The bot will " + decision.primary_action.action_type.value.replace("_", " ").lower()
            }
        }
        
        return explanation
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def agentic_health_check():
    """Health check for agentic chat service"""
    return {
        "status": "healthy", 
        "service": "agentic-chatbot",
        "planner_active": True,
        "executor_active": True
    }