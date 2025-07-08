from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ConversationState(str, Enum):
    ACTIVE = "active"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETED = "completed"
    ERROR = "error"


class IntentType(str, Enum):
    OUTLET_INQUIRY = "outlet_inquiry"
    RESTAURANT_SEARCH = "restaurant_search"
    PRODUCT_SEARCH = "product_search"
    CALCULATION = "calculation"
    GENERAL_QUERY = "general_query"
    UNKNOWN = "unknown"


class ConversationSlot(BaseModel):
    name: str
    value: Optional[Any] = None
    confidence: float = 0.0
    last_updated: datetime = Field(default_factory=datetime.now)


class ConversationTurn(BaseModel):
    turn_id: str
    user_message: str
    bot_response: str
    intent: IntentType
    entities: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence: float = 0.0


class ConversationMemory(BaseModel):
    conversation_id: str
    user_id: str
    turns: List[ConversationTurn] = Field(default_factory=list)
    slots: Dict[str, ConversationSlot] = Field(default_factory=dict)
    state: ConversationState = ConversationState.ACTIVE
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    def add_turn(self, turn: ConversationTurn):
        self.turns.append(turn)
        self.updated_at = datetime.now()
    
    def update_slot(self, name: str, value: Any, confidence: float = 1.0):
        self.slots[name] = ConversationSlot(
            name=name,
            value=value,
            confidence=confidence,
            last_updated=datetime.now()
        )
        self.updated_at = datetime.now()
    
    def get_slot_value(self, name: str) -> Optional[Any]:
        slot = self.slots.get(name)
        return slot.value if slot else None
    
    def get_latest_turn(self) -> Optional[ConversationTurn]:
        return self.turns[-1] if self.turns else None
    
    def get_conversation_context(self) -> str:
        context_parts = []
        
        if len(self.turns) > 0:
            context_parts.append("Recent conversation:")
            for turn in self.turns[-3:]:
                context_parts.append(f"User: {turn.user_message}")
                context_parts.append(f"Bot: {turn.bot_response}")
        
        if self.slots:
            context_parts.append("\nCurrent slots:")
            for name, slot in self.slots.items():
                context_parts.append(f"- {name}: {slot.value}")
        
        return "\n".join(context_parts)


class OutletInfo(BaseModel):
    name: str
    location: str
    address: str
    opening_hours: str
    phone: Optional[str] = None
    services: List[str] = Field(default_factory=list)


class RestaurantInfo(BaseModel):
    name: str
    cuisine: str
    location: str
    rating: float
    price_range: str
    description: Optional[str] = None


class ProductInfo(BaseModel):
    name: str
    category: str
    price: float
    description: str
    availability: bool = True
    specifications: Dict[str, Any] = Field(default_factory=dict)