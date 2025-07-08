from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.chatbot_service import ChatbotService
from app.core.memory_manager import MemoryManager


class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    user_id: str


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    turns: list
    slots: dict


memory_manager = MemoryManager()
chatbot_service = ChatbotService(memory_manager)

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    try:
        response, conversation_id = await chatbot_service.process_message(
            user_id=request.user_id,
            message=request.message,
            conversation_id=request.conversation_id
        )
        
        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            user_id=request.user_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation_history(conversation_id: str):
    try:
        memory = await chatbot_service.get_conversation_history(conversation_id)
        if not memory:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        turns = []
        for turn in memory.turns:
            turns.append({
                "turn_id": turn.turn_id,
                "user_message": turn.user_message,
                "bot_response": turn.bot_response,
                "intent": turn.intent.value,
                "entities": turn.entities,
                "timestamp": turn.timestamp.isoformat(),
                "confidence": turn.confidence
            })
        
        slots = {}
        for slot_name, slot in memory.slots.items():
            slots[slot_name] = {
                "value": slot.value,
                "confidence": slot.confidence,
                "last_updated": slot.last_updated.isoformat()
            }
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            turns=turns,
            slots=slots
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/{conversation_id}")
async def reset_conversation(conversation_id: str):
    try:
        await chatbot_service.reset_conversation(conversation_id)
        return {"message": "Conversation reset successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "chatbot"}