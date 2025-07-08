from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass
from app.models.conversation import ConversationMemory, IntentType
import json
import asyncio


class ActionType(str, Enum):
    """Available actions the planner can choose"""
    ASK_CLARIFICATION = "ask_clarification"
    CALL_CALCULATOR = "call_calculator"
    CALL_OUTLET_API = "call_outlet_api"
    CALL_RESTAURANT_API = "call_restaurant_api"
    CALL_PRODUCT_API = "call_product_api"
    CALL_RAG_SYSTEM = "call_rag_system"
    PROVIDE_RESPONSE = "provide_response"
    REQUEST_MISSING_INFO = "request_missing_info"
    FINISH = "finish"


@dataclass
class PlanningContext:
    """Context information for planning decisions"""
    intent: IntentType
    entities: Dict[str, Any]
    confidence: float
    conversation_memory: ConversationMemory
    user_message: str
    missing_slots: List[str]
    available_slots: Dict[str, Any]


@dataclass
class PlannerAction:
    """Represents a planned action with its parameters"""
    action_type: ActionType
    parameters: Dict[str, Any]
    confidence: float
    reasoning: str
    execution_priority: int = 1


@dataclass
class PlannerDecision:
    """Complete planning decision with multiple possible actions"""
    primary_action: PlannerAction
    fallback_actions: List[PlannerAction]
    decision_reasoning: str
    confidence: float


class AgenticPlanner:
    """
    Advanced planner that decides the bot's next action based on:
    1. Current intent and entities
    2. Missing information analysis
    3. Conversation context and history
    4. Available tools and APIs
    """
    
    def __init__(self):
        self.required_slots = {
            IntentType.OUTLET_INQUIRY: ["location"],
            IntentType.RESTAURANT_SEARCH: ["cuisine", "location"],
            IntentType.PRODUCT_SEARCH: ["category"],
            IntentType.CALCULATION: ["expression"]
        }
        
        self.decision_history: List[PlannerDecision] = []
    
    async def plan_next_action(self, context: PlanningContext) -> PlannerDecision:
        """
        Main planning method that analyzes context and decides next action
        
        Decision Process:
        1. Analyze conversation completeness
        2. Identify missing critical information
        3. Evaluate available tools and APIs
        4. Consider conversation flow and user expectations
        5. Choose optimal action with fallbacks
        """
        
        # Step 1: Analyze conversation completeness
        completeness_score = self._analyze_completeness(context)
        
        # Step 2: Identify missing information
        missing_info = self._identify_missing_information(context)
        
        # Step 3: Evaluate tool availability and relevance
        tool_analysis = self._analyze_available_tools(context)
        
        # Step 4: Consider conversation flow
        flow_analysis = self._analyze_conversation_flow(context)
        
        # Step 5: Make planning decision
        decision = self._make_planning_decision(
            context, completeness_score, missing_info, tool_analysis, flow_analysis
        )
        
        # Store decision for learning
        self.decision_history.append(decision)
        
        return decision
    
    def _analyze_completeness(self, context: PlanningContext) -> Dict[str, float]:
        """Analyze how complete the current conversation state is"""
        required_slots = self.required_slots.get(context.intent, [])
        
        if not required_slots:
            return {"completeness": 1.0, "missing_slots": 0}
        
        filled_slots = sum(1 for slot in required_slots if slot in context.entities)
        completeness = filled_slots / len(required_slots)
        
        return {
            "completeness": completeness,
            "missing_slots": len(required_slots) - filled_slots,
            "total_slots": len(required_slots),
            "filled_slots": filled_slots
        }
    
    def _identify_missing_information(self, context: PlanningContext) -> Dict[str, Any]:
        """Identify what information is missing to complete the request"""
        missing = []
        critical_missing = []
        
        required_slots = self.required_slots.get(context.intent, [])
        
        for slot in required_slots:
            if slot not in context.entities:
                missing.append(slot)
                
                # Determine if this is critical based on intent
                if self._is_critical_slot(context.intent, slot):
                    critical_missing.append(slot)
        
        # Check for contextual missing information
        contextual_missing = self._check_contextual_missing(context)
        
        return {
            "missing_slots": missing,
            "critical_missing": critical_missing,
            "contextual_missing": contextual_missing,
            "can_proceed": len(critical_missing) == 0,
            "missing_count": len(missing)
        }
    
    def _analyze_available_tools(self, context: PlanningContext) -> Dict[str, Any]:
        """Analyze which tools are available and relevant for the current intent"""
        tools = {
            "calculator": {
                "available": True,
                "relevance": 1.0 if context.intent == IntentType.CALCULATION else 0.0,
                "confidence": 0.95
            },
            "outlet_api": {
                "available": True,
                "relevance": 1.0 if context.intent == IntentType.OUTLET_INQUIRY else 0.0,
                "confidence": 0.9
            },
            "restaurant_api": {
                "available": True,
                "relevance": 1.0 if context.intent == IntentType.RESTAURANT_SEARCH else 0.0,
                "confidence": 0.85
            },
            "product_api": {
                "available": True,
                "relevance": 1.0 if context.intent == IntentType.PRODUCT_SEARCH else 0.0,
                "confidence": 0.85
            },
            "rag_system": {
                "available": False,  # Not implemented yet
                "relevance": 0.3,
                "confidence": 0.0
            }
        }
        
        # Find most relevant tool
        best_tool = max(tools.items(), key=lambda x: x[1]["relevance"])
        
        return {
            "available_tools": tools,
            "best_tool": best_tool[0],
            "best_tool_relevance": best_tool[1]["relevance"],
            "tool_count": sum(1 for tool in tools.values() if tool["available"])
        }
    
    def _analyze_conversation_flow(self, context: PlanningContext) -> Dict[str, Any]:
        """Analyze conversation flow to understand user expectations"""
        turns_count = len(context.conversation_memory.turns)
        latest_turn = context.conversation_memory.get_latest_turn()
        
        # Analyze conversation patterns
        if turns_count == 0:
            flow_state = "initial"
        elif turns_count == 1:
            flow_state = "follow_up"
        else:
            flow_state = "ongoing"
        
        # Check for topic changes
        topic_continuity = self._check_topic_continuity(context)
        
        # Analyze user patience/urgency
        urgency_indicators = self._detect_urgency(context.user_message)
        
        return {
            "flow_state": flow_state,
            "turns_count": turns_count,
            "topic_continuity": topic_continuity,
            "urgency_score": urgency_indicators["score"],
            "urgency_indicators": urgency_indicators["indicators"],
            "user_patience": self._estimate_user_patience(context)
        }
    
    def _make_planning_decision(
        self,
        context: PlanningContext,
        completeness: Dict[str, float],
        missing_info: Dict[str, Any],
        tool_analysis: Dict[str, Any],
        flow_analysis: Dict[str, Any]
    ) -> PlannerDecision:
        """Core decision-making logic"""
        
        # Decision tree based on analysis
        if context.confidence < 0.5:
            # Low confidence - ask for clarification
            return self._create_clarification_decision(context, "Low intent confidence")
        
        if missing_info["critical_missing"]:
            # Missing critical information - request it
            return self._create_missing_info_decision(context, missing_info)
        
        if completeness["completeness"] >= 0.8 and tool_analysis["best_tool_relevance"] > 0.8:
            # High completeness and good tool match - execute tool
            return self._create_tool_execution_decision(context, tool_analysis)
        
        if flow_analysis["urgency_score"] > 0.7:
            # High urgency - provide best available response
            return self._create_urgent_response_decision(context, flow_analysis)
        
        if completeness["completeness"] < 0.5:
            # Low completeness - ask for more information
            return self._create_information_request_decision(context, missing_info)
        
        # Default - provide response with available information
        return self._create_default_response_decision(context)
    
    def _create_clarification_decision(self, context: PlanningContext, reason: str) -> PlannerDecision:
        """Create decision to ask for clarification"""
        primary_action = PlannerAction(
            action_type=ActionType.ASK_CLARIFICATION,
            parameters={
                "clarification_type": "intent",
                "context": context.user_message,
                "suggested_intents": [IntentType.OUTLET_INQUIRY, IntentType.RESTAURANT_SEARCH]
            },
            confidence=0.8,
            reasoning=f"Asking for clarification due to: {reason}",
            execution_priority=1
        )
        
        fallback_actions = [
            PlannerAction(
                action_type=ActionType.PROVIDE_RESPONSE,
                parameters={"response_type": "generic_help"},
                confidence=0.5,
                reasoning="Fallback to generic help response",
                execution_priority=2
            )
        ]
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=fallback_actions,
            decision_reasoning=f"Intent confidence too low ({context.confidence:.2f}). {reason}",
            confidence=0.8
        )
    
    def _create_missing_info_decision(self, context: PlanningContext, missing_info: Dict[str, Any]) -> PlannerDecision:
        """Create decision to request missing information"""
        primary_action = PlannerAction(
            action_type=ActionType.REQUEST_MISSING_INFO,
            parameters={
                "missing_slots": missing_info["critical_missing"],
                "context": context.intent,
                "user_friendly_names": self._get_user_friendly_names(missing_info["critical_missing"])
            },
            confidence=0.9,
            reasoning=f"Missing critical information: {missing_info['critical_missing']}",
            execution_priority=1
        )
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=[],
            decision_reasoning=f"Cannot proceed without: {', '.join(missing_info['critical_missing'])}",
            confidence=0.9
        )
    
    def _create_tool_execution_decision(self, context: PlanningContext, tool_analysis: Dict[str, Any]) -> PlannerDecision:
        """Create decision to execute the most appropriate tool"""
        best_tool = tool_analysis["best_tool"]
        
        action_map = {
            "calculator": ActionType.CALL_CALCULATOR,
            "outlet_api": ActionType.CALL_OUTLET_API,
            "restaurant_api": ActionType.CALL_RESTAURANT_API,
            "product_api": ActionType.CALL_PRODUCT_API,
            "rag_system": ActionType.CALL_RAG_SYSTEM
        }
        
        primary_action = PlannerAction(
            action_type=action_map[best_tool],
            parameters={
                "tool_name": best_tool,
                "input_data": context.entities,
                "context": context.user_message
            },
            confidence=tool_analysis["available_tools"][best_tool]["confidence"],
            reasoning=f"High confidence tool match: {best_tool}",
            execution_priority=1
        )
        
        # Add fallback action
        fallback_actions = [
            PlannerAction(
                action_type=ActionType.PROVIDE_RESPONSE,
                parameters={"response_type": "partial_information"},
                confidence=0.6,
                reasoning="Fallback if tool execution fails",
                execution_priority=2
            )
        ]
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=fallback_actions,
            decision_reasoning=f"Executing {best_tool} with {tool_analysis['best_tool_relevance']:.2f} relevance",
            confidence=primary_action.confidence
        )
    
    def _create_urgent_response_decision(self, context: PlanningContext, flow_analysis: Dict[str, Any]) -> PlannerDecision:
        """Create decision for urgent responses"""
        primary_action = PlannerAction(
            action_type=ActionType.PROVIDE_RESPONSE,
            parameters={
                "response_type": "urgent",
                "available_info": context.entities,
                "urgency_level": flow_analysis["urgency_score"]
            },
            confidence=0.7,
            reasoning=f"High urgency detected: {flow_analysis['urgency_score']:.2f}",
            execution_priority=1
        )
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=[],
            decision_reasoning=f"Urgent response required due to: {flow_analysis['urgency_indicators']}",
            confidence=0.7
        )
    
    def _create_information_request_decision(self, context: PlanningContext, missing_info: Dict[str, Any]) -> PlannerDecision:
        """Create decision to request additional information"""
        primary_action = PlannerAction(
            action_type=ActionType.REQUEST_MISSING_INFO,
            parameters={
                "missing_slots": missing_info["missing_slots"],
                "context": context.intent,
                "suggestion_type": "optional_enhancement"
            },
            confidence=0.7,
            reasoning="Requesting additional information to improve response",
            execution_priority=1
        )
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=[],
            decision_reasoning=f"Could benefit from additional info: {missing_info['missing_slots']}",
            confidence=0.7
        )
    
    def _create_default_response_decision(self, context: PlanningContext) -> PlannerDecision:
        """Create default response decision"""
        primary_action = PlannerAction(
            action_type=ActionType.PROVIDE_RESPONSE,
            parameters={
                "response_type": "default",
                "available_info": context.entities,
                "intent": context.intent
            },
            confidence=0.6,
            reasoning="Default response with available information",
            execution_priority=1
        )
        
        return PlannerDecision(
            primary_action=primary_action,
            fallback_actions=[],
            decision_reasoning="Providing response with available information",
            confidence=0.6
        )
    
    # Helper methods
    def _is_critical_slot(self, intent: IntentType, slot: str) -> bool:
        """Determine if a slot is critical for the given intent"""
        critical_slots = {
            IntentType.OUTLET_INQUIRY: ["location"],
            IntentType.CALCULATION: ["expression"],
            IntentType.RESTAURANT_SEARCH: ["cuisine"],
            IntentType.PRODUCT_SEARCH: ["category"]
        }
        return slot in critical_slots.get(intent, [])
    
    def _check_contextual_missing(self, context: PlanningContext) -> List[str]:
        """Check for missing contextual information"""
        contextual_missing = []
        
        if context.intent == IntentType.OUTLET_INQUIRY:
            if "location" in context.entities and "query_type" not in context.entities:
                contextual_missing.append("specific_query")
        
        return contextual_missing
    
    def _check_topic_continuity(self, context: PlanningContext) -> Dict[str, Any]:
        """Check if the conversation topic is continuous"""
        if len(context.conversation_memory.turns) < 2:
            return {"continuous": True, "topic_change": False}
        
        current_intent = context.intent
        previous_intent = context.conversation_memory.turns[-1].intent
        
        return {
            "continuous": current_intent == previous_intent,
            "topic_change": current_intent != previous_intent,
            "previous_intent": previous_intent,
            "current_intent": current_intent
        }
    
    def _detect_urgency(self, message: str) -> Dict[str, Any]:
        """Detect urgency indicators in user message"""
        urgency_keywords = ["urgent", "quickly", "asap", "immediately", "now", "fast", "hurry"]
        question_marks = message.count("?")
        exclamation_marks = message.count("!")
        
        urgency_score = 0
        indicators = []
        
        for keyword in urgency_keywords:
            if keyword in message.lower():
                urgency_score += 0.3
                indicators.append(keyword)
        
        if question_marks > 1:
            urgency_score += 0.2
            indicators.append("multiple_questions")
        
        if exclamation_marks > 0:
            urgency_score += 0.1 * exclamation_marks
            indicators.append("exclamation_marks")
        
        return {
            "score": min(urgency_score, 1.0),
            "indicators": indicators
        }
    
    def _estimate_user_patience(self, context: PlanningContext) -> float:
        """Estimate user patience based on conversation history"""
        turns_count = len(context.conversation_memory.turns)
        
        if turns_count == 0:
            return 1.0
        elif turns_count < 3:
            return 0.8
        elif turns_count < 5:
            return 0.6
        else:
            return 0.4
    
    def _get_user_friendly_names(self, slots: List[str]) -> Dict[str, str]:
        """Convert slot names to user-friendly names"""
        friendly_names = {
            "location": "location or outlet",
            "cuisine": "cuisine type",
            "category": "product category",
            "expression": "calculation",
            "query_type": "specific information needed"
        }
        return {slot: friendly_names.get(slot, slot) for slot in slots}
    
    def get_decision_summary(self) -> Dict[str, Any]:
        """Get summary of planning decisions made"""
        if not self.decision_history:
            return {"total_decisions": 0, "patterns": []}
        
        action_counts = {}
        for decision in self.decision_history:
            action_type = decision.primary_action.action_type
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
        
        return {
            "total_decisions": len(self.decision_history),
            "action_distribution": action_counts,
            "average_confidence": sum(d.confidence for d in self.decision_history) / len(self.decision_history),
            "recent_decisions": [d.decision_reasoning for d in self.decision_history[-5:]]
        }