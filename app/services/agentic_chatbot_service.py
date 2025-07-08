import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from app.models.conversation import (
    ConversationMemory, ConversationTurn, IntentType, 
    ConversationState, OutletInfo
)
from app.core.memory_manager import MemoryManager
from app.core.planner import AgenticPlanner, PlanningContext, ActionType
from app.core.action_executor import ActionExecutor


class AgenticChatbotService:
    """
    Advanced chatbot service with agentic planning capabilities
    
    This service demonstrates Part 2 of the Mindhive Assessment:
    - Parses intent and missing information
    - Chooses appropriate actions (ask, call tool, finish)
    - Executes actions and returns results
    """
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.planner = AgenticPlanner()
        self.outlets_db = self._initialize_outlets_db()
        self.executor = ActionExecutor(outlets_db=self.outlets_db)
        
        # Track decision points for analysis
        self.decision_log: List[Dict[str, Any]] = []
    
    def _initialize_outlets_db(self) -> Dict[str, OutletInfo]:
        """Initialize the outlets database"""
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
    
    async def process_message_with_planning(self, user_id: str, message: str, 
                                          conversation_id: Optional[str] = None) -> Tuple[str, str, Dict[str, Any]]:
        """
        Process message using agentic planning approach
        
        Returns:
            Tuple of (response, conversation_id, planning_details)
        """
        
        # Step 1: Get or create conversation
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            await self.memory_manager.create_conversation(user_id, conversation_id)
        
        memory = await self.memory_manager.get_conversation(conversation_id)
        if not memory:
            memory = await self.memory_manager.create_conversation(user_id, conversation_id)
        
        # Step 2: Parse intent and entities (existing logic)
        intent, entities, confidence = await self._parse_intent(message, memory)
        
        # Step 3: Create planning context
        planning_context = PlanningContext(
            intent=intent,
            entities=entities,
            confidence=confidence,
            conversation_memory=memory,
            user_message=message,
            missing_slots=self._identify_missing_slots(intent, entities),
            available_slots=entities
        )
        
        # Step 4: Plan next action
        decision = await self.planner.plan_next_action(planning_context)
        
        # Step 5: Execute the planned action
        execution_context = {
            "memory": memory,
            "user_message": message,
            "entities": entities,
            "intent": intent
        }
        
        action_result = await self.executor.execute_decision(decision, execution_context)
        
        # Step 6: Create conversation turn
        turn = ConversationTurn(
            turn_id=str(uuid.uuid4()),
            user_message=message,
            bot_response=action_result.response,
            intent=intent,
            entities=entities,
            confidence=confidence
        )
        
        await self.memory_manager.add_turn(conversation_id, turn)
        
        # Step 7: Update slots based on execution results
        await self._update_slots_from_execution(conversation_id, action_result, entities)
        
        # Step 8: Log decision for analysis
        decision_log_entry = {
            "timestamp": datetime.now().isoformat(),
            "user_message": message,
            "intent": intent.value,
            "entities": entities,
            "confidence": confidence,
            "planned_action": decision.primary_action.action_type.value,
            "action_confidence": decision.primary_action.confidence,
            "decision_reasoning": decision.decision_reasoning,
            "execution_success": action_result.success,
            "execution_time": action_result.execution_time,
            "response": action_result.response
        }
        self.decision_log.append(decision_log_entry)
        
        # Step 9: Return response with planning details
        planning_details = {
            "intent": intent.value,
            "entities": entities,
            "confidence": confidence,
            "planned_action": decision.primary_action.action_type.value,
            "action_reasoning": decision.primary_action.reasoning,
            "decision_confidence": decision.confidence,
            "execution_success": action_result.success,
            "execution_time": action_result.execution_time,
            "fallback_used": len(decision.fallback_actions) > 0 and not action_result.success
        }
        
        return action_result.response, conversation_id, planning_details
    
    async def _parse_intent(self, message: str, memory: ConversationMemory) -> Tuple[IntentType, Dict[str, Any], float]:
        """Parse intent using enhanced logic with context awareness"""
        message_lower = message.lower()
        entities = {}
        
        # Get conversation context
        context = memory.get_conversation_context()
        latest_turn = memory.get_latest_turn()
        
        # Primary intent detection
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
        
        # Context-aware follow-up detection
        elif latest_turn and latest_turn.intent == IntentType.OUTLET_INQUIRY:
            # Check if this is a follow-up outlet question
            locations = self._extract_locations(message)
            if locations or any(keyword in message_lower for keyword in ['open', 'opening', 'hours', 'time', 'phone', 'contact', 'address']):
                intent = IntentType.OUTLET_INQUIRY
                confidence = 0.8
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
            
            # Extract cuisine if mentioned
            cuisines = ['malaysian', 'chinese', 'indian', 'japanese', 'italian', 'thai', 'american']
            for cuisine in cuisines:
                if cuisine in message_lower:
                    entities['cuisine'] = cuisine.title()
                    break
            
            # Extract location
            locations = self._extract_locations(message)
            if locations:
                entities['location'] = locations[0]
        
        elif any(keyword in message_lower for keyword in ['product', 'buy', 'purchase', 'item']):
            intent = IntentType.PRODUCT_SEARCH
            confidence = 0.8
            
            # Extract product category
            categories = ['electronics', 'health', 'fitness', 'food', 'beverage', 'furniture', 'home', 'garden', 'fashion']
            for category in categories:
                if category in message_lower:
                    entities['category'] = category.title()
                    break
        
        elif any(keyword in message_lower for keyword in ['calculate', 'compute', 'math', '+', '-', '*', '/', 'add', 'subtract']):
            intent = IntentType.CALCULATION
            confidence = 0.9
            entities['expression'] = message
        
        else:
            intent = IntentType.GENERAL_QUERY
            confidence = 0.4  # Lower confidence for unclear intents
        
        return intent, entities, confidence
    
    def _extract_locations(self, message: str) -> List[str]:
        """Extract location entities from message"""
        message_lower = message.lower()
        locations = []
        
        location_patterns = {
            'ss2': ['ss2', 'ss 2', 'sea park'],
            'mid_valley': ['mid valley', 'midvalley', 'mid-valley'],
            'one_utama': ['1 utama', 'one utama', '1utama'],
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
                    elif location_key == 'one_utama':
                        locations.append('one_utama')
                    elif location_key == 'petaling_jaya':
                        locations.append('petaling_jaya')
                    elif location_key == 'kuala_lumpur':
                        locations.append('kuala_lumpur')
                    break
        
        return list(set(locations))
    
    def _identify_missing_slots(self, intent: IntentType, entities: Dict[str, Any]) -> List[str]:
        """Identify missing required slots for the given intent"""
        required_slots = {
            IntentType.OUTLET_INQUIRY: ["location"],
            IntentType.RESTAURANT_SEARCH: ["cuisine"],
            IntentType.PRODUCT_SEARCH: ["category"],
            IntentType.CALCULATION: ["expression"]
        }
        
        intent_requirements = required_slots.get(intent, [])
        missing = [slot for slot in intent_requirements if slot not in entities]
        
        return missing
    
    async def _update_slots_from_execution(self, conversation_id: str, action_result, entities: Dict[str, Any]):
        """Update conversation slots based on action execution results"""
        if action_result.success and action_result.data:
            # Extract useful information from execution results
            data = action_result.data
            
            # Update location slot if outlet was found
            if "outlet" in data:
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'last_outlet_accessed', 
                    data["outlet"]["name"], 
                    0.9
                )
            
            # Update search history
            if "restaurants" in data:
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'last_restaurant_search', 
                    data["query"], 
                    0.8
                )
            
            if "products" in data:
                await self.memory_manager.update_slot(
                    conversation_id, 
                    'last_product_search', 
                    data["query"], 
                    0.8
                )
        
        # Update slots from entities
        for key, value in entities.items():
            await self.memory_manager.update_slot(conversation_id, key, value, 0.9)
    
    def get_planning_analytics(self) -> Dict[str, Any]:
        """Get analytics about planning decisions"""
        if not self.decision_log:
            return {"total_decisions": 0}
        
        total_decisions = len(self.decision_log)
        successful_executions = sum(1 for entry in self.decision_log if entry["execution_success"])
        
        # Analyze action distribution
        action_counts = {}
        intent_counts = {}
        for entry in self.decision_log:
            action = entry["planned_action"]
            intent = entry["intent"]
            action_counts[action] = action_counts.get(action, 0) + 1
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        # Calculate average metrics
        avg_confidence = sum(entry["confidence"] for entry in self.decision_log) / total_decisions
        avg_execution_time = sum(entry["execution_time"] for entry in self.decision_log) / total_decisions
        
        return {
            "total_decisions": total_decisions,
            "success_rate": successful_executions / total_decisions,
            "average_confidence": avg_confidence,
            "average_execution_time": avg_execution_time,
            "action_distribution": action_counts,
            "intent_distribution": intent_counts,
            "planner_stats": self.planner.get_decision_summary(),
            "executor_stats": self.executor.get_execution_stats()
        }
    
    def get_decision_points_summary(self) -> List[Dict[str, Any]]:
        """Get summary of key decision points for analysis"""
        decision_points = []
        
        for entry in self.decision_log:
            decision_points.append({
                "user_input": entry["user_message"],
                "detected_intent": entry["intent"],
                "confidence": entry["confidence"],
                "chosen_action": entry["planned_action"],
                "reasoning": entry["decision_reasoning"],
                "success": entry["execution_success"],
                "response_quality": "high" if entry["execution_success"] and entry["confidence"] > 0.8 else "medium" if entry["execution_success"] else "low"
            })
        
        return decision_points
    
    # Compatibility methods for existing API
    async def process_message(self, user_id: str, message: str, 
                            conversation_id: Optional[str] = None) -> Tuple[str, str]:
        """Compatibility method that uses agentic planning"""
        response, conv_id, _ = await self.process_message_with_planning(user_id, message, conversation_id)
        return response, conv_id
    
    async def get_conversation_history(self, conversation_id: str) -> Optional[ConversationMemory]:
        """Get conversation history"""
        return await self.memory_manager.get_conversation(conversation_id)
    
    async def reset_conversation(self, conversation_id: str):
        """Reset conversation"""
        await self.memory_manager.delete_conversation(conversation_id)