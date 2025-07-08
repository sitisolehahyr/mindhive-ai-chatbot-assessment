# Part 2: Agentic Planning - Decision Points Analysis

## Overview

This document explains the agentic planning system implemented for the Mindhive Assessment Part 2. The system demonstrates how the chatbot intelligently decides its next action through a sophisticated planner/controller loop.

## Architecture Components

### 1. AgenticPlanner (`app/core/planner.py`)
The core decision-making component that analyzes conversation context and determines optimal actions.

### 2. ActionExecutor (`app/core/action_executor.py`)
Executes planned actions with fallback handling and error recovery.

### 3. AgenticChatbotService (`app/services/agentic_chatbot_service.py`)
Orchestrates the planning and execution cycle with conversation management.

## Decision-Making Process

### Step 1: Context Analysis
The planner analyzes multiple dimensions of the conversation:

```python
# Conversation completeness analysis
completeness_score = self._analyze_completeness(context)

# Missing information identification
missing_info = self._identify_missing_information(context)

# Tool availability assessment
tool_analysis = self._analyze_available_tools(context)

# Conversation flow analysis
flow_analysis = self._analyze_conversation_flow(context)
```

### Step 2: Decision Tree Logic

The planner follows a sophisticated decision tree:

1. **Low Confidence Check** (< 0.5)
   - **Action**: `ASK_CLARIFICATION`
   - **Reasoning**: Intent unclear, need user clarification
   - **Example**: "Something something" → Ask for clarification

2. **Missing Critical Information**
   - **Action**: `REQUEST_MISSING_INFO`
   - **Reasoning**: Cannot proceed without required slots
   - **Example**: "Restaurant search" without cuisine → Ask for cuisine type

3. **High Completeness + Good Tool Match** (≥ 0.8 completeness, > 0.8 tool relevance)
   - **Action**: Tool execution (`CALL_CALCULATOR`, `CALL_OUTLET_API`, etc.)
   - **Reasoning**: All information available, execute appropriate tool
   - **Example**: "Calculate 10 + 5" → Execute calculator

4. **High Urgency** (> 0.7 urgency score)
   - **Action**: `PROVIDE_RESPONSE`
   - **Reasoning**: User needs immediate response
   - **Example**: "I urgently need SS2 phone!" → Provide immediate answer

5. **Low Completeness** (< 0.5)
   - **Action**: `REQUEST_MISSING_INFO`
   - **Reasoning**: Need more information to provide good response
   - **Example**: "Tell me about products" → Ask for product category

6. **Default Fallback**
   - **Action**: `PROVIDE_RESPONSE`
   - **Reasoning**: Provide best available response
   - **Example**: Generic helpful response

## Key Decision Points

### 1. Intent Confidence Threshold
```python
if context.confidence < 0.5:
    return self._create_clarification_decision(context, "Low intent confidence")
```

**Reasoning**: When the system is uncertain about user intent, it's better to ask for clarification than to guess incorrectly.

**Example Flow**:
```
User: "Something about stuff"
Confidence: 0.3
Decision: ASK_CLARIFICATION
Response: "I'd like to help you better. Could you clarify if you're asking about..."
```

### 2. Critical Information Requirements
```python
if missing_info["critical_missing"]:
    return self._create_missing_info_decision(context, missing_info)
```

**Reasoning**: Certain intents require specific information to be actionable. The system identifies critical vs. optional slots.

**Critical Slots by Intent**:
- `OUTLET_INQUIRY`: location
- `CALCULATION`: expression
- `RESTAURANT_SEARCH`: cuisine
- `PRODUCT_SEARCH`: category

**Example Flow**:
```
User: "Tell me about outlets"
Missing: ["location"] (critical)
Decision: REQUEST_MISSING_INFO
Response: "Which outlet are you referring to? We have outlets in SS2, Mid Valley, and 1 Utama."
```

### 3. Tool Relevance Scoring
```python
if completeness["completeness"] >= 0.8 and tool_analysis["best_tool_relevance"] > 0.8:
    return self._create_tool_execution_decision(context, tool_analysis)
```

**Reasoning**: When we have enough information and a highly relevant tool, execute it directly.

**Tool Relevance Matrix**:
- Calculator: 1.0 for CALCULATION intent, 0.0 otherwise
- Outlet API: 1.0 for OUTLET_INQUIRY, 0.0 otherwise
- Restaurant API: 1.0 for RESTAURANT_SEARCH, 0.0 otherwise
- Product API: 1.0 for PRODUCT_SEARCH, 0.0 otherwise

**Example Flow**:
```
User: "Calculate 15 * 8"
Intent: CALCULATION (confidence: 0.9)
Tool: Calculator (relevance: 1.0)
Decision: CALL_CALCULATOR
Response: "The result of 15.0 × 8.0 is 120.0."
```

### 4. Urgency Detection
```python
urgency_indicators = self._detect_urgency(context.user_message)
if flow_analysis["urgency_score"] > 0.7:
    return self._create_urgent_response_decision(context, flow_analysis)
```

**Urgency Keywords**: "urgent", "quickly", "asap", "immediately", "now", "fast", "hurry"

**Reasoning**: When users express urgency, prioritize immediate response over information gathering.

**Example Flow**:
```
User: "I urgently need SS2 outlet phone number now!"
Urgency Score: 0.9
Decision: PROVIDE_RESPONSE (urgent)
Response: Immediate answer with available information
```

### 5. Context-Aware Follow-ups
```python
# Check for topic continuity
topic_continuity = self._check_topic_continuity(context)

# Context-aware intent parsing
elif latest_turn and latest_turn.intent == IntentType.OUTLET_INQUIRY:
    if locations or any(keyword in message_lower for keyword in ['open', 'opening', 'hours']):
        intent = IntentType.OUTLET_INQUIRY
```

**Reasoning**: Follow-up questions often omit context that was established in previous turns.

**Example Flow**:
```
Turn 1:
User: "Tell me about SS2 outlet"
Response: "The SS2 Outlet is located at..."

Turn 2:
User: "What time do you open?"
Context: Previous turn was about SS2 outlet
Decision: CALL_OUTLET_API with SS2 context
Response: "The SS2 Outlet opens at 9:00 AM - 9:00 PM."
```

## Fallback Strategy

The system implements a robust fallback strategy:

### Primary Action Failure
```python
# Try primary action first
result = await self._execute_action(decision.primary_action, context)
if result.success:
    return result

# Try fallback actions if primary fails
for fallback_action in decision.fallback_actions:
    result = await self._execute_action(fallback_action, context)
    if result.success:
        return result
```

### Common Fallback Patterns
1. **Tool Call → Generic Response**: If API fails, provide general information
2. **Specific Query → Clarification**: If specific action fails, ask for clarification
3. **Complex Action → Simple Action**: Break down complex requests

## Performance Metrics

The system tracks detailed performance metrics:

### Decision Quality Metrics
- **Confidence Distribution**: Tracks confidence levels of decisions
- **Success Rate**: Percentage of successful action executions
- **Action Distribution**: Which actions are most commonly chosen
- **Fallback Usage**: How often fallback actions are needed

### Execution Metrics
- **Average Execution Time**: Performance of action execution
- **Error Rates**: Frequency of execution failures
- **Tool Performance**: Success rates by tool type

## Example Decision Flows

### 1. Complete Information Flow
```
Input: "Calculate 25 + 15"
Intent: CALCULATION (confidence: 0.9)
Entities: {expression: "25 + 15"}
Missing: []
Decision: CALL_CALCULATOR
Execution: Success
Result: "The result of 25.0 + 15.0 is 40.0."
```

### 2. Missing Information Flow
```
Input: "I want food"
Intent: RESTAURANT_SEARCH (confidence: 0.6)
Entities: {}
Missing: ["cuisine"]
Decision: REQUEST_MISSING_INFO
Result: "To help you better, could you please specify the cuisine type?"
```

### 3. Context-Aware Flow
```
Previous: "SS2 outlet information"
Input: "Opening hours?"
Intent: OUTLET_INQUIRY (confidence: 0.8)
Entities: {query_type: "opening_hours"}
Context: location="ss2" from previous turn
Decision: CALL_OUTLET_API
Result: "The SS2 Outlet opens at 9:00 AM - 9:00 PM."
```

### 4. Low Confidence Flow
```
Input: "Something about stuff"
Intent: GENERAL_QUERY (confidence: 0.3)
Entities: {}
Decision: ASK_CLARIFICATION
Result: "I'm not entirely sure what you're looking for. Could you clarify..."
```

### 5. Urgent Request Flow
```
Input: "I urgently need SS2 phone number now!"
Intent: OUTLET_INQUIRY (confidence: 0.8)
Urgency: 0.9
Decision: PROVIDE_RESPONSE (urgent)
Result: Immediate response with phone number
```

## API Demonstration

The agentic planning system is exposed through several API endpoints:

### 1. `/api/agentic-chat/message`
Returns full planning details with each response:
```json
{
  "response": "The result of 10.0 + 5.0 is 15.0.",
  "planning_details": {
    "intent": "calculation",
    "confidence": 0.9,
    "planned_action": "call_calculator",
    "action_reasoning": "High confidence tool match: calculator",
    "execution_success": true,
    "execution_time": 0.05
  }
}
```

### 2. `/api/agentic-chat/explain-decision`
Explains decision-making without execution:
```json
{
  "intent_analysis": {
    "detected_intent": "outlet_inquiry",
    "confidence": 0.8,
    "missing_information": ["location"]
  },
  "planning_process": {
    "primary_action": {
      "action_type": "request_missing_info",
      "reasoning": "Missing critical information: ['location']"
    }
  }
}
```

### 3. `/api/agentic-chat/analytics`
Provides system-wide planning analytics:
```json
{
  "analytics": {
    "total_decisions": 156,
    "success_rate": 0.94,
    "action_distribution": {
      "call_outlet_api": 45,
      "call_calculator": 32,
      "request_missing_info": 28
    }
  }
}
```

## Continuous Improvement

The system includes mechanisms for continuous improvement:

1. **Decision Logging**: All decisions are logged with context and outcomes
2. **Performance Tracking**: Success rates and execution times are monitored
3. **Pattern Analysis**: Common decision patterns are identified
4. **Feedback Loop**: Decision quality can be assessed and improved

## Conclusion

The agentic planning system demonstrates sophisticated decision-making capabilities that go beyond simple rule-based chatbots. By analyzing conversation context, missing information, tool availability, and user urgency, the system makes intelligent decisions about what action to take next.

Key strengths of the implementation:
- **Context Awareness**: Considers conversation history and flow
- **Robust Fallbacks**: Handles failures gracefully
- **Performance Monitoring**: Tracks and analyzes decision quality
- **Transparency**: Provides detailed reasoning for each decision
- **Flexibility**: Easily extensible with new actions and decision criteria

This foundation provides a solid base for more advanced agentic behaviors and can be extended with machine learning approaches for even more sophisticated decision-making.