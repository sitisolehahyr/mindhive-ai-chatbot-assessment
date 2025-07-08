import asyncio
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from app.core.planner import ActionType, PlannerAction, PlannerDecision
from app.models.conversation import ConversationMemory, IntentType
import httpx

# Try to import DSPy calculator, fallback to basic implementation
try:
    from app.tools.dspy_calculator import DSPyCalculatorTool
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    DSPyCalculatorTool = None


@dataclass
class ActionResult:
    """Result of an executed action"""
    success: bool
    response: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    follow_up_actions: List[PlannerAction] = None


class ActionExecutor:
    """
    Executes actions decided by the AgenticPlanner
    
    Handles:
    1. Tool calls (calculator, APIs)
    2. Information requests
    3. Response generation
    4. Error handling and fallbacks
    """
    
    def __init__(self, outlets_db: Dict = None, restaurants_api_url: str = None, products_api_url: str = None):
        self.outlets_db = outlets_db or {}
        self.restaurants_api_url = restaurants_api_url or "http://localhost:8000/api/restaurants"
        self.products_api_url = products_api_url or "http://localhost:8000/api/products"
        self.execution_history: List[Dict[str, Any]] = []
        
        # Initialize DSPy calculator if available
        if DSPY_AVAILABLE:
            try:
                self.dspy_calculator = DSPyCalculatorTool()
            except Exception as e:
                print(f"Warning: DSPy calculator initialization failed: {e}")
                self.dspy_calculator = None
        else:
            self.dspy_calculator = None
    
    async def execute_decision(self, decision: PlannerDecision, context: Dict[str, Any]) -> ActionResult:
        """
        Execute a planner decision with fallback handling
        
        Args:
            decision: The planner decision to execute
            context: Execution context including memory, user message, etc.
            
        Returns:
            ActionResult with the execution outcome
        """
        start_time = asyncio.get_event_loop().time()
        
        # Try primary action first
        try:
            result = await self._execute_action(decision.primary_action, context)
            
            if result.success:
                execution_time = asyncio.get_event_loop().time() - start_time
                result.execution_time = execution_time
                
                # Log successful execution
                self._log_execution(decision.primary_action, result, "success")
                return result
            
        except Exception as e:
            # Log primary action failure
            self._log_execution(decision.primary_action, None, f"error: {str(e)}")
        
        # Try fallback actions if primary fails
        for fallback_action in decision.fallback_actions:
            try:
                result = await self._execute_action(fallback_action, context)
                
                if result.success:
                    execution_time = asyncio.get_event_loop().time() - start_time
                    result.execution_time = execution_time
                    
                    # Add note that this was a fallback
                    result.response += " (Note: Used fallback action due to primary action failure)"
                    
                    self._log_execution(fallback_action, result, "fallback_success")
                    return result
                    
            except Exception as e:
                self._log_execution(fallback_action, None, f"fallback_error: {str(e)}")
                continue
        
        # All actions failed - return error result
        execution_time = asyncio.get_event_loop().time() - start_time
        error_result = ActionResult(
            success=False,
            response="I apologize, but I'm having trouble processing your request right now. Please try again.",
            error="All planned actions failed",
            execution_time=execution_time
        )
        
        return error_result
    
    async def _execute_action(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Execute a specific action based on its type"""
        
        action_handlers = {
            ActionType.ASK_CLARIFICATION: self._handle_ask_clarification,
            ActionType.CALL_CALCULATOR: self._handle_calculator_call,
            ActionType.CALL_OUTLET_API: self._handle_outlet_api_call,
            ActionType.CALL_RESTAURANT_API: self._handle_restaurant_api_call,
            ActionType.CALL_PRODUCT_API: self._handle_product_api_call,
            ActionType.CALL_RAG_SYSTEM: self._handle_rag_system_call,
            ActionType.PROVIDE_RESPONSE: self._handle_provide_response,
            ActionType.REQUEST_MISSING_INFO: self._handle_request_missing_info,
            ActionType.FINISH: self._handle_finish
        }
        
        handler = action_handlers.get(action.action_type)
        if not handler:
            return ActionResult(
                success=False,
                response="Unknown action type",
                error=f"No handler for action type: {action.action_type}"
            )
        
        return await handler(action, context)
    
    async def _handle_ask_clarification(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle clarification requests"""
        params = action.parameters
        clarification_type = params.get("clarification_type", "general")
        
        if clarification_type == "intent":
            response = (
                "I'm not entirely sure what you're looking for. Could you clarify if you're asking about:\n"
                "• Outlet locations and information\n"
                "• Restaurant recommendations\n"
                "• Product searches\n"
                "• Mathematical calculations\n"
                "Please let me know which one matches your request!"
            )
        else:
            response = (
                "I'd like to help you better. Could you provide more details about what you're looking for? "
                "For example, are you asking about locations, products, restaurants, or something else?"
            )
        
        return ActionResult(
            success=True,
            response=response,
            data={"clarification_type": clarification_type}
        )
    
    async def _handle_calculator_call(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle calculator tool calls using DSPy for advanced calculation"""
        params = action.parameters
        input_data = params.get("input_data", {})
        expression = input_data.get("expression", params.get("context", ""))
        
        try:
            if self.dspy_calculator:
                # Use DSPy calculator for advanced calculation
                is_arithmetic, confidence, calculation_request = await self.dspy_calculator.detect_arithmetic_intent(expression)
                
                if is_arithmetic and calculation_request:
                    calc_result = await self.dspy_calculator.calculate(calculation_request)
                    
                    if calc_result.success:
                        return ActionResult(
                            success=True,
                            response=calc_result.explanation,
                            data={
                                "calculation": {
                                    "expression": expression,
                                    "result": calc_result.result,
                                    "formatted_result": calc_result.formatted_result,
                                    "steps": calc_result.calculation_steps,
                                    "complexity": calculation_request.complexity.value,
                                    "confidence": confidence
                                }
                            }
                        )
                    else:
                        return ActionResult(
                            success=False,
                            response=calc_result.explanation,
                            error=calc_result.error_message
                        )
                else:
                    return ActionResult(
                        success=False,
                        response=f"I couldn't detect arithmetic intent in '{expression}'. Please provide a clearer mathematical expression.",
                        error="No arithmetic intent detected"
                    )
            else:
                # Fallback to basic calculator
                return await self._fallback_calculator_call(expression)
                
        except Exception as e:
            # Final fallback
            return await self._fallback_calculator_call(expression)
    
    async def _fallback_calculator_call(self, expression: str) -> ActionResult:
        """Fallback calculator implementation without DSPy"""
        try:
            # Extract numbers and operation from expression
            numbers = re.findall(r'\d+\.?\d*', expression)
            if len(numbers) < 2:
                return ActionResult(
                    success=False,
                    response="I need at least two numbers to perform a calculation.",
                    error="Insufficient numbers in expression"
                )
            
            a, b = float(numbers[0]), float(numbers[1])
            
            # Determine operation
            if any(op in expression for op in ['+', 'add', 'plus']):
                result = a + b
                response = f"The result of {a} + {b} is {result}."
            elif any(op in expression for op in ['-', 'subtract', 'minus']):
                result = a - b
                response = f"The result of {a} - {b} is {result}."
            elif any(op in expression for op in ['*', 'multiply', 'times']):
                result = a * b
                response = f"The result of {a} × {b} is {result}."
            elif any(op in expression for op in ['/', 'divide', 'divided by']):
                if b == 0:
                    return ActionResult(
                        success=False,
                        response="I can't divide by zero!",
                        error="Division by zero"
                    )
                result = a / b
                response = f"The result of {a} ÷ {b} is {result}."
            else:
                return ActionResult(
                    success=False,
                    response="I couldn't determine the mathematical operation. Please specify add, subtract, multiply, or divide.",
                    error="Unknown operation"
                )
            
            return ActionResult(
                success=True,
                response=response,
                data={"calculation": {"a": a, "b": b, "result": result, "operation": expression}}
            )
            
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I couldn't perform that calculation. Please try with a clearer expression.",
                error=str(e)
            )
    
    async def _handle_outlet_api_call(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle outlet API calls"""
        params = action.parameters
        input_data = params.get("input_data", {})
        location = input_data.get("location")
        query_type = input_data.get("query_type", "general")
        
        # Map location to outlet
        outlet_key = self._map_location_to_outlet(location)
        if not outlet_key or outlet_key not in self.outlets_db:
            return ActionResult(
                success=False,
                response=f"I'm sorry, I don't have information about an outlet in {location}. We have outlets in Petaling Jaya (SS2), Mid Valley (KL), and 1 Utama (PJ).",
                error="Outlet not found"
            )
        
        outlet = self.outlets_db[outlet_key]
        
        # Generate response based on query type
        if query_type == "opening_hours":
            response = f"The {outlet.name} opens at {outlet.opening_hours}."
        elif query_type == "contact":
            response = f"You can contact the {outlet.name} at {outlet.phone}."
        elif query_type == "address":
            response = f"The {outlet.name} is located at {outlet.address}."
        else:
            response = (
                f"Yes! The {outlet.name} is located at {outlet.address}. "
                f"Operating hours: {outlet.opening_hours}. Phone: {outlet.phone}."
            )
        
        return ActionResult(
            success=True,
            response=response,
            data={"outlet": outlet.__dict__, "query_type": query_type}
        )
    
    async def _handle_restaurant_api_call(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle restaurant API calls"""
        params = action.parameters
        input_data = params.get("input_data", {})
        
        try:
            # Build query parameters
            query_params = {}
            if "cuisine" in input_data:
                query_params["cuisine"] = input_data["cuisine"]
            if "location" in input_data:
                query_params["location"] = input_data["location"]
            
            # Make API call
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.restaurants_api_url}/search", params=query_params)
                
                if response.status_code == 200:
                    data = response.json()
                    restaurants = data.get("restaurants", [])
                    
                    if not restaurants:
                        return ActionResult(
                            success=True,
                            response="I couldn't find any restaurants matching your criteria. Try a different cuisine or location.",
                            data={"restaurants": [], "query": query_params}
                        )
                    
                    # Format response
                    response_text = f"I found {len(restaurants)} restaurant(s) for you:\n\n"
                    for i, restaurant in enumerate(restaurants[:3], 1):  # Show top 3
                        response_text += (
                            f"{i}. **{restaurant['name']}** ({restaurant['cuisine']})\n"
                            f"   📍 {restaurant['location']}\n"
                            f"   ⭐ {restaurant['rating']}/5.0 | {restaurant['price_range']}\n"
                            f"   {restaurant['description']}\n\n"
                        )
                    
                    if len(restaurants) > 3:
                        response_text += f"...and {len(restaurants) - 3} more options available."
                    
                    return ActionResult(
                        success=True,
                        response=response_text,
                        data={"restaurants": restaurants, "query": query_params}
                    )
                else:
                    return ActionResult(
                        success=False,
                        response="I'm having trouble accessing restaurant information right now.",
                        error=f"API returned status {response.status_code}"
                    )
                    
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I can't search for restaurants at the moment. Please try again later.",
                error=str(e)
            )
    
    async def _handle_product_api_call(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle product API calls"""
        params = action.parameters
        input_data = params.get("input_data", {})
        
        try:
            # Build query parameters
            query_params = {}
            if "category" in input_data:
                query_params["category"] = input_data["category"]
            if "search_term" in input_data:
                query_params["search_term"] = input_data["search_term"]
            
            # Make API call
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.products_api_url}/search", params=query_params)
                
                if response.status_code == 200:
                    data = response.json()
                    products = data.get("products", [])
                    
                    if not products:
                        return ActionResult(
                            success=True,
                            response="I couldn't find any products matching your criteria. Try a different category or search term.",
                            data={"products": [], "query": query_params}
                        )
                    
                    # Format response
                    response_text = f"I found {len(products)} product(s) for you:\n\n"
                    for i, product in enumerate(products[:3], 1):  # Show top 3
                        availability = "✅ In Stock" if product['availability'] else "❌ Out of Stock"
                        response_text += (
                            f"{i}. **{product['name']}**\n"
                            f"   💰 RM {product['price']:.2f} | {availability}\n"
                            f"   📂 {product['category']}\n"
                            f"   {product['description']}\n\n"
                        )
                    
                    if len(products) > 3:
                        response_text += f"...and {len(products) - 3} more products available."
                    
                    return ActionResult(
                        success=True,
                        response=response_text,
                        data={"products": products, "query": query_params}
                    )
                else:
                    return ActionResult(
                        success=False,
                        response="I'm having trouble accessing product information right now.",
                        error=f"API returned status {response.status_code}"
                    )
                    
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I can't search for products at the moment. Please try again later.",
                error=str(e)
            )
    
    async def _handle_rag_system_call(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle RAG system calls for products and outlets"""
        params = action.parameters
        input_data = params.get("input_data", {})
        rag_type = input_data.get("rag_type", "product")  # "product" or "outlet"
        query = input_data.get("query", "")
        
        if not query:
            return ActionResult(
                success=False,
                response="I need a search query to help you. What would you like to know?",
                error="Missing query"
            )
        
        try:
            if rag_type == "product":
                return await self._handle_product_rag_call(query, input_data)
            elif rag_type == "outlet":
                return await self._handle_outlet_rag_call(query, input_data)
            else:
                return ActionResult(
                    success=False,
                    response="I'm not sure what type of information you're looking for. Could you clarify if you need product or outlet information?",
                    error="Unknown RAG type"
                )
                
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I'm having trouble accessing that information right now. Please try again later.",
                error=str(e)
            )
    
    async def _handle_product_rag_call(self, query: str, input_data: Dict[str, Any]) -> ActionResult:
        """Handle product search using vector store RAG"""
        try:
            # Build query parameters
            query_params = {"query": query}
            
            # Add optional filters
            if "category" in input_data:
                query_params["category"] = input_data["category"]
            if "availability" in input_data:
                query_params["availability"] = input_data["availability"]
            if "min_price" in input_data:
                query_params["min_price"] = input_data["min_price"]
            if "max_price" in input_data:
                query_params["max_price"] = input_data["max_price"]
            
            # Set search type (semantic by default, hybrid for complex queries)
            if len(query.split()) > 3 or any(word in query.lower() for word in ['and', 'or', 'but', 'with']):
                query_params["search_type"] = "hybrid"
            else:
                query_params["search_type"] = "semantic"
            
            # Make API call to RAG endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/api/products", params=query_params)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    summary = data.get("summary", "")
                    
                    if not results:
                        return ActionResult(
                            success=True,
                            response=summary or f"I couldn't find any ZUS Coffee products matching '{query}'. You might want to try searching for 'tumbler', 'mug', or 'cup' instead.",
                            data={"query": query, "results": [], "search_type": query_params.get("search_type")}
                        )
                    
                    # Use the AI-generated summary as the primary response
                    response_text = summary
                    
                    # Add additional context if helpful
                    if len(results) > 3:
                        response_text += f"\n\nI can provide more details about any of these products if you'd like!"
                    
                    return ActionResult(
                        success=True,
                        response=response_text,
                        data={
                            "query": query,
                            "results": results,
                            "total_found": data.get("total_found", len(results)),
                            "execution_time": data.get("execution_time", 0),
                            "search_type": query_params.get("search_type"),
                            "filters_applied": data.get("filters_applied")
                        }
                    )
                else:
                    return ActionResult(
                        success=False,
                        response="I'm having trouble searching for products right now. Please try again later.",
                        error=f"Product search API returned status {response.status_code}"
                    )
                    
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I can't search for products at the moment. Please try again later.",
                error=str(e)
            )
    
    async def _handle_outlet_rag_call(self, query: str, input_data: Dict[str, Any]) -> ActionResult:
        """Handle outlet query using Text2SQL RAG"""
        try:
            # Build query parameters
            query_params = {"query": query}
            
            if "limit" in input_data:
                query_params["limit"] = input_data["limit"]
            
            # Make API call to RAG endpoint
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/api/outlets", params=query_params)
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    summary = data.get("summary", "")
                    sql_explanation = data.get("sql_explanation", "")
                    
                    if not results:
                        return ActionResult(
                            success=True,
                            response=summary or f"I couldn't find any ZUS Coffee outlets matching '{query}'. You might want to try searching for specific cities like 'Kuala Lumpur', 'Petaling Jaya', or 'Selangor'.",
                            data={"query": query, "results": [], "explanation": sql_explanation}
                        )
                    
                    # Use the AI-generated summary as the primary response
                    response_text = summary
                    
                    return ActionResult(
                        success=True,
                        response=response_text,
                        data={
                            "query": query,
                            "results": results,
                            "total_found": data.get("total_found", len(results)),
                            "execution_time": data.get("execution_time", 0),
                            "sql_explanation": sql_explanation
                        }
                    )
                else:
                    error_detail = ""
                    try:
                        error_data = response.json()
                        error_detail = error_data.get("detail", "")
                    except:
                        pass
                    
                    return ActionResult(
                        success=False,
                        response=f"I couldn't process your outlet query: {error_detail}" if error_detail else "I'm having trouble searching for outlets right now. Please try again later.",
                        error=f"Outlet query API returned status {response.status_code}: {error_detail}"
                    )
                    
        except Exception as e:
            return ActionResult(
                success=False,
                response="I'm sorry, I can't search for outlets at the moment. Please try again later.",
                error=str(e)
            )
    
    async def _handle_provide_response(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle generic response provision"""
        params = action.parameters
        response_type = params.get("response_type", "default")
        available_info = params.get("available_info", {})
        
        if response_type == "urgent":
            urgency_level = params.get("urgency_level", 0.5)
            response = (
                f"I understand this seems urgent (urgency level: {urgency_level:.1f}). "
                f"Based on what I have: {self._format_available_info(available_info)}. "
                f"How can I help you further?"
            )
        elif response_type == "partial_information":
            response = (
                f"Here's what I can tell you based on the information available: "
                f"{self._format_available_info(available_info)}. "
                f"Would you like me to look up more specific details?"
            )
        elif response_type == "generic_help":
            response = (
                "I'm here to help you with:\n"
                "• Outlet locations and information\n"
                "• Restaurant recommendations\n"
                "• Product searches\n"
                "• Mathematical calculations\n\n"
                "What would you like to know more about?"
            )
        else:
            response = (
                "I'm here to help you with outlet information, restaurant recommendations, "
                "and product searches. How can I assist you today?"
            )
        
        return ActionResult(
            success=True,
            response=response,
            data={"response_type": response_type, "available_info": available_info}
        )
    
    async def _handle_request_missing_info(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle requests for missing information"""
        params = action.parameters
        missing_slots = params.get("missing_slots", [])
        user_friendly_names = params.get("user_friendly_names", {})
        context_intent = params.get("context", IntentType.GENERAL_QUERY)
        
        if not missing_slots:
            return ActionResult(
                success=True,
                response="I have all the information I need. How else can I help you?",
                data={"missing_slots": []}
            )
        
        # Create user-friendly request
        friendly_missing = [user_friendly_names.get(slot, slot) for slot in missing_slots]
        
        if len(friendly_missing) == 1:
            response = f"To help you better, could you please specify the {friendly_missing[0]}?"
        else:
            response = f"To help you better, could you please provide: {', '.join(friendly_missing[:-1])} and {friendly_missing[-1]}?"
        
        # Add context-specific guidance
        if context_intent == IntentType.OUTLET_INQUIRY:
            response += " For example, you can ask about SS2, Mid Valley, or 1 Utama outlets."
        elif context_intent == IntentType.RESTAURANT_SEARCH:
            response += " For example, 'Japanese restaurants in Petaling Jaya' or 'Italian food in Mid Valley'."
        elif context_intent == IntentType.PRODUCT_SEARCH:
            response += " For example, 'electronics' or 'health and fitness products'."
        
        return ActionResult(
            success=True,
            response=response,
            data={"missing_slots": missing_slots, "context": context_intent}
        )
    
    async def _handle_finish(self, action: PlannerAction, context: Dict[str, Any]) -> ActionResult:
        """Handle conversation finishing"""
        return ActionResult(
            success=True,
            response="Is there anything else I can help you with today?",
            data={"action": "finish"}
        )
    
    # Helper methods
    def _map_location_to_outlet(self, location: str) -> Optional[str]:
        """Map location string to outlet key"""
        if not location:
            return None
            
        location_lower = location.lower()
        
        if location_lower in ['ss2', 'ss 2']:
            return 'ss2'
        elif location_lower in ['mid_valley', 'midvalley', 'mid-valley']:
            return 'mid_valley'
        elif location_lower in ['one_utama', '1_utama', '1utama']:
            return 'one_utama'
        elif location_lower in ['petaling_jaya', 'pj', 'petaling']:
            return 'ss2'  # Default PJ outlet
        elif location_lower in ['kuala_lumpur', 'kl', 'kuala']:
            return 'mid_valley'  # Default KL outlet
        
        return None
    
    def _format_available_info(self, available_info: Dict[str, Any]) -> str:
        """Format available information for user display"""
        if not available_info:
            return "limited information"
        
        formatted_parts = []
        for key, value in available_info.items():
            if key == "location":
                formatted_parts.append(f"location: {value}")
            elif key == "cuisine":
                formatted_parts.append(f"cuisine: {value}")
            elif key == "category":
                formatted_parts.append(f"category: {value}")
            else:
                formatted_parts.append(f"{key}: {value}")
        
        return ", ".join(formatted_parts) if formatted_parts else "some available information"
    
    def _log_execution(self, action: PlannerAction, result: Optional[ActionResult], status: str):
        """Log action execution for debugging and improvement"""
        log_entry = {
            "action_type": action.action_type,
            "status": status,
            "confidence": action.confidence,
            "reasoning": action.reasoning,
            "success": result.success if result else False,
            "execution_time": result.execution_time if result else 0.0,
            "timestamp": asyncio.get_event_loop().time()
        }
        
        self.execution_history.append(log_entry)
        
        # Keep only last 100 entries
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        if not self.execution_history:
            return {"total_executions": 0}
        
        total = len(self.execution_history)
        successful = sum(1 for entry in self.execution_history if entry["success"])
        
        action_counts = {}
        for entry in self.execution_history:
            action_type = entry["action_type"]
            action_counts[action_type] = action_counts.get(action_type, 0) + 1
        
        return {
            "total_executions": total,
            "success_rate": successful / total,
            "action_distribution": action_counts,
            "average_execution_time": sum(e["execution_time"] for e in self.execution_history) / total
        }