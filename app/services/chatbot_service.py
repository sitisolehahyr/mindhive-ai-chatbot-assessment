import re
import uuid
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from app.models.conversation import (
    ConversationMemory, ConversationTurn, IntentType, 
    ConversationState, OutletInfo
)
from app.core.memory_manager import MemoryManager
from app.config import INTENT_CONFIDENCE_THRESHOLD, HIGH_CONFIDENCE_THRESHOLD

logger = logging.getLogger(__name__)


class ChatbotService:
    """
    Intent-based chatbot service for handling customer inquiries.
    
    This service uses a rule-based intent classification system to understand
    user queries and provide appropriate responses. It maintains conversation
    state and context through a memory manager.
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.outlets_db = self._initialize_outlets_db()
        logger.info("ChatbotService initialized with intent-based classification")
    
    def _initialize_outlets_db(self) -> Dict[str, OutletInfo]:
        return {
            "ss2": OutletInfo(
                name="SS2 Outlet",
                location="SS2, Petaling Jaya",
                address="No. 123, Jalan SS2/24, SS2, 47300 Petaling Jaya, Selangor",
                opening_hours="9:00 AM - 9:00 PM",
                phone="+603-1234-5678",
                services=["Dine-in", "Takeaway", "Delivery"]
            ),
            "mid_valley": OutletInfo(
                name="Mid Valley Outlet",
                location="Mid Valley, Kuala Lumpur",
                address="L2-034, Mid Valley Megamall, Kuala Lumpur",
                opening_hours="10:00 AM - 10:00 PM",
                phone="+603-8765-4321",
                services=["Dine-in", "Takeaway"]
            ),
            "one_utama": OutletInfo(
                name="1 Utama Outlet",
                location="1 Utama, Petaling Jaya",
                address="LG-234, 1 Utama Shopping Centre, Petaling Jaya",
                opening_hours="10:00 AM - 10:00 PM",
                phone="+603-5555-1234",
                services=["Dine-in", "Takeaway", "Delivery"]
            )
        }
    
    async def process_message(self, user_id: str, message: str, 
                            conversation_id: Optional[str] = None) -> Tuple[str, str]:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            await self.memory_manager.create_conversation(user_id, conversation_id)
        
        memory = await self.memory_manager.get_conversation(conversation_id)
        if not memory:
            memory = await self.memory_manager.create_conversation(user_id, conversation_id)
        
        intent, entities, confidence = await self._parse_intent(message, memory)
        
        response = await self._generate_response(intent, entities, memory, message)
        
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            user_message=message,
            bot_response=response,
            intent=intent,
            entities=entities,
            confidence=confidence
        )
        
        await self.memory_manager.add_turn(conversation_id, turn)
        
        await self._update_slots(conversation_id, intent, entities, memory)
        
        return response, conversation_id
    
    async def _parse_intent(self, message: str, memory: ConversationMemory) -> Tuple[IntentType, Dict[str, Any], float]:
        message_lower = message.lower()
        entities = {}
        
        context = memory.get_conversation_context()
        latest_turn = memory.get_latest_turn()
        
        if any(keyword in message_lower for keyword in ['outlet', 'store', 'branch', 'location']):
            intent = IntentType.OUTLET_INQUIRY
            confidence = 0.9
            
            locations = self._extract_locations(message)
            if locations:
                entities['location'] = locations[0]
            
            if any(keyword in message_lower for keyword in ['open', 'opening', 'hours', 'time']):
                entities['query_type'] = 'opening_hours'
            elif any(keyword in message_lower for keyword in ['phone', 'contact', 'number']):
                entities['query_type'] = 'contact'
            elif any(keyword in message_lower for keyword in ['address', 'where']):
                entities['query_type'] = 'address'
            else:
                entities['query_type'] = 'general'
        
        elif latest_turn and latest_turn.intent == IntentType.OUTLET_INQUIRY:
            if memory.get_slot_value('pending_outlet_query'):
                intent = IntentType.OUTLET_INQUIRY
                confidence = 0.8
                
                locations = self._extract_locations(message)
                if locations:
                    entities['location'] = locations[0]
                
                if any(keyword in message_lower for keyword in ['open', 'opening', 'hours', 'time']):
                    entities['query_type'] = 'opening_hours'
                elif any(keyword in message_lower for keyword in ['phone', 'contact', 'number']):
                    entities['query_type'] = 'contact'
                elif any(keyword in message_lower for keyword in ['address', 'where']):
                    entities['query_type'] = 'address'
                else:
                    entities['query_type'] = 'general'
            else:
                # Check if this is a follow-up outlet question
                locations = self._extract_locations(message)
                if locations or any(keyword in message_lower for keyword in ['open', 'opening', 'hours', 'time', 'phone', 'contact', 'address']):
                    intent = IntentType.OUTLET_INQUIRY
                    confidence = 0.7
                    if locations:
                        entities['location'] = locations[0]
                    if any(keyword in message_lower for keyword in ['open', 'opening', 'hours', 'time']):
                        entities['query_type'] = 'opening_hours'
                    elif any(keyword in message_lower for keyword in ['phone', 'contact', 'number']):
                        entities['query_type'] = 'contact'
                    elif any(keyword in message_lower for keyword in ['address', 'where']):
                        entities['query_type'] = 'address'
                    else:
                        entities['query_type'] = 'general'
                else:
                    intent = IntentType.GENERAL_QUERY
                    confidence = 0.6
        
        elif any(keyword in message_lower for keyword in ['restaurant', 'food', 'eat', 'dining']):
            intent = IntentType.RESTAURANT_SEARCH
            confidence = 0.8
        
        elif any(keyword in message_lower for keyword in ['product', 'buy', 'purchase', 'item']):
            intent = IntentType.PRODUCT_SEARCH
            confidence = 0.8
        
        elif any(keyword in message_lower for keyword in ['calculate', 'compute', 'math', '+', '-', '*', '/', 'add', 'subtract']):
            intent = IntentType.CALCULATION
            confidence = 0.9
            entities['expression'] = message
        
        else:
            intent = IntentType.GENERAL_QUERY
            confidence = 0.5
        
        return intent, entities, confidence
    
    def _extract_locations(self, message: str) -> List[str]:
        message_lower = message.lower()
        locations = []
        
        location_patterns = {
            'ss2': ['ss2', 'ss 2', 'sea park'],
            'mid_valley': ['mid valley', 'midvalley', 'mid-valley'],
            '1_utama': ['1 utama', 'one utama', '1utama'],
            'petaling_jaya': ['petaling jaya', 'pj', 'petaling'],
            'kuala_lumpur': ['kuala lumpur', 'kl', 'kuala']
        }
        
        for location_key, patterns in location_patterns.items():
            for pattern in patterns:
                if pattern in message_lower:
                    if location_key == 'ss2':
                        locations.append('ss2')
                    elif location_key == 'mid_valley':
                        locations.append('mid_valley')
                    elif location_key == '1_utama':
                        locations.append('one_utama')
                    elif location_key == 'petaling_jaya':
                        locations.append('petaling_jaya')
                    elif location_key == 'kuala_lumpur':
                        locations.append('kuala_lumpur')
                    break
        
        return list(set(locations))
    
    async def _generate_response(self, intent: IntentType, entities: Dict[str, Any], 
                               memory: ConversationMemory, message: str) -> str:
        if intent == IntentType.OUTLET_INQUIRY:
            return await self._handle_outlet_inquiry(entities, memory, message)
        elif intent == IntentType.RESTAURANT_SEARCH:
            return "I can help you find restaurants. What type of cuisine are you looking for?"
        elif intent == IntentType.PRODUCT_SEARCH:
            return "I can help you find products. What are you looking for?"
        elif intent == IntentType.CALCULATION:
            return await self._handle_calculation(entities.get('expression', ''))
        else:
            return "I'm here to help you with outlet information, restaurant recommendations, and product searches. How can I assist you today?"
    
    async def _handle_outlet_inquiry(self, entities: Dict[str, Any], 
                                   memory: ConversationMemory, message: str) -> str:
        location = entities.get('location')
        query_type = entities.get('query_type', 'general')
        
        if not location:
            pending_location = memory.get_slot_value('pending_location')
            if pending_location:
                location = pending_location
            else:
                available_locations = list(self.outlets_db.keys())
                locations_text = ", ".join([self.outlets_db[loc].location for loc in available_locations])
                await self.memory_manager.update_slot(
                    memory.conversation_id, 
                    'pending_outlet_query', 
                    True, 
                    0.9
                )
                return f"Yes! We have outlets in {locations_text}. Which outlet are you referring to?"
        
        outlet_key = self._map_location_to_outlet(location)
        if not outlet_key:
            return f"I'm sorry, I don't have information about an outlet in {location}. We have outlets in Petaling Jaya (SS2), Mid Valley (KL), and 1 Utama (PJ)."
        
        outlet = self.outlets_db[outlet_key]
        
        if query_type == 'opening_hours':
            return f"The {outlet.name} opens at {outlet.opening_hours}."
        elif query_type == 'contact':
            return f"You can contact the {outlet.name} at {outlet.phone}."
        elif query_type == 'address':
            return f"The {outlet.name} is located at {outlet.address}."
        else:
            return f"Yes! The {outlet.name} is located at {outlet.address}. Operating hours: {outlet.opening_hours}. Phone: {outlet.phone}."
    
    def _map_location_to_outlet(self, location: str) -> Optional[str]:
        location_lower = location.lower()
        
        if location_lower in ['ss2', 'ss 2']:
            return 'ss2'
        elif location_lower in ['mid_valley', 'midvalley', 'mid-valley']:
            return 'mid_valley'
        elif location_lower in ['one_utama', '1_utama', '1utama']:
            return 'one_utama'
        elif location_lower in ['petaling_jaya', 'pj', 'petaling']:
            return 'ss2'
        elif location_lower in ['kuala_lumpur', 'kl', 'kuala']:
            return 'mid_valley'
        
        return None
    
    async def _handle_calculation(self, expression: str) -> str:
        try:
            numbers = re.findall(r'\d+\.?\d*', expression)
            if len(numbers) >= 2:
                a, b = float(numbers[0]), float(numbers[1])
                
                if any(op in expression for op in ['+', 'add', 'plus']):
                    result = a + b
                    return f"The result of {a} + {b} is {result}."
                elif any(op in expression for op in ['-', 'subtract', 'minus']):
                    result = a - b
                    return f"The result of {a} - {b} is {result}."
                elif any(op in expression for op in ['*', 'multiply', 'times']):
                    result = a * b
                    return f"The result of {a} × {b} is {result}."
                elif any(op in expression for op in ['/', 'divide', 'divided by']):
                    if b != 0:
                        result = a / b
                        return f"The result of {a} ÷ {b} is {result}."
                    else:
                        return "I can't divide by zero!"
            
            return "I need more information to perform the calculation. Please provide two numbers and an operation."
        except Exception as e:
            return "I'm sorry, I couldn't perform that calculation. Please try again with a clearer expression."
    
    async def _update_slots(self, conversation_id: str, intent: IntentType, 
                          entities: Dict[str, Any], memory: ConversationMemory):
        if intent == IntentType.OUTLET_INQUIRY:
            if 'location' in entities:
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'pending_location', 
                    entities['location'], 
                    0.9
                )
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'pending_outlet_query', 
                    False, 
                    1.0
                )
            
            if 'query_type' in entities:
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'last_query_type', 
                    entities['query_type'], 
                    0.9
                )
    
    async def get_conversation_history(self, conversation_id: str) -> Optional[ConversationMemory]:
        return await self.memory_manager.get_conversation(conversation_id)
    
    async def reset_conversation(self, conversation_id: str):
        await self.memory_manager.delete_conversation(conversation_id)