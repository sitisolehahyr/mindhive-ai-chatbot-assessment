#!/usr/bin/env python3
"""
Simple demo untuk testing Mindhive Chatbot tanpa web interface
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.action_executor import ActionExecutor
from app.core.planner import AgenticPlanner, PlannerAction, ActionType
from app.models.conversation import ConversationMemory, IntentType

class SimpleChatbotDemo:
    """Simple chatbot demo untuk testing"""
    
    def __init__(self):
        self.executor = ActionExecutor()
        self.planner = AgenticPlanner()
        self.session_id = "demo-session"
        self.memory = ConversationMemory(
            conversation_id=self.session_id,
            user_id="demo-user"
        )
        
    def print_header(self):
        """Print demo header"""
        print("=" * 60)
        print("🤖 MINDHIVE CHATBOT - SIMPLE DEMO")
        print("=" * 60)
        print()
        print("Features to try:")
        print("• Calculator: 'Calculate 25 + 37'")
        print("• Outlets: 'Find outlets in Kuala Lumpur'")
        print("• Products: 'Show me coffee tumblers'")
        print("• Restaurants: 'Find Italian restaurants'")
        print("• Error testing: 'Calculate' (missing params)")
        print("• Security: '; DROP TABLE outlets; --'")
        print()
        print("Type 'quit' to exit")
        print("-" * 60)
    
    async def process_message(self, user_message: str):
        """Process user message and return response"""
        try:
            # Create context
            context = {
                "user_message": user_message,
                "memory": self.memory,
                "session_id": self.session_id
            }
            
            # Create planning context
            from app.core.planner import PlanningContext
            
            # Simple intent detection (basic implementation)
            intent = self._detect_intent(user_message)
            entities = self._extract_entities(user_message)
            
            planning_context = PlanningContext(
                intent=intent,
                entities=entities,
                confidence=0.8,
                conversation_memory=self.memory,
                user_message=user_message,
                missing_slots=[],
                available_slots={}
            )
            
            # Plan the response
            decision = await self.planner.plan_next_action(planning_context)
            
            # Execute the decision
            result = await self.executor.execute_decision(decision, context)
            
            # Update memory with turn
            from app.models.conversation import ConversationTurn
            turn = ConversationTurn(
                turn_id=f"turn_{len(self.memory.turns)}",
                user_message=user_message,
                bot_response=result.response,
                intent=IntentType.GENERAL_QUERY
            )
            self.memory.add_turn(turn)
            
            return result.response, result.success
            
        except Exception as e:
            return f"Error processing message: {str(e)}", False
    
    def _detect_intent(self, message: str) -> IntentType:
        """Simple intent detection"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ['calculate', 'math', '+', '-', '*', '/', 'divide']):
            return IntentType.CALCULATION
        elif any(word in message_lower for word in ['outlet', 'location', 'address', 'hours']):
            return IntentType.OUTLET_INQUIRY
        elif any(word in message_lower for word in ['restaurant', 'food', 'cuisine', 'italian', 'chinese']):
            return IntentType.RESTAURANT_SEARCH
        elif any(word in message_lower for word in ['product', 'tumbler', 'cup', 'mug', 'show me']):
            return IntentType.PRODUCT_SEARCH
        else:
            return IntentType.GENERAL_QUERY
    
    def _extract_entities(self, message: str) -> dict:
        """Simple entity extraction"""
        entities = {}
        message_lower = message.lower()
        
        # Extract numbers for calculation
        import re
        numbers = re.findall(r'\d+\.?\d*', message)
        if numbers:
            entities['numbers'] = numbers
        
        # Extract locations
        locations = ['kuala lumpur', 'kl', 'petaling jaya', 'pj', 'selangor', 'ss2', 'mid valley', 'klcc']
        for location in locations:
            if location in message_lower:
                entities['location'] = location
                break
        
        # Extract cuisines
        cuisines = ['italian', 'chinese', 'japanese', 'indian', 'western', 'local']
        for cuisine in cuisines:
            if cuisine in message_lower:
                entities['cuisine'] = cuisine
                break
        
        return entities
    
    async def run_demo(self):
        """Run the interactive demo"""
        self.print_header()
        
        while True:
            try:
                # Get user input
                user_input = input("\n🗣️  You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    print("\n👋 Goodbye! Thanks for testing the Mindhive Chatbot!")
                    break
                
                if not user_input:
                    continue
                
                # Process message
                print("\n🤖 Bot: ", end="")
                print("Thinking...", end="", flush=True)
                
                response, success = await self.process_message(user_input)
                
                # Clear "Thinking..." and print response
                print("\r🤖 Bot: " + " " * 20)  # Clear the line
                print(f"🤖 Bot: {response}")
                
                # Show success indicator
                status = "✅ Success" if success else "⚠️  Handled gracefully"
                print(f"      ({status})")
                
            except KeyboardInterrupt:
                print("\n\n👋 Demo interrupted. Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Demo error: {e}")

async def run_test_scenarios():
    """Run automated test scenarios"""
    demo = SimpleChatbotDemo()
    
    print("🧪 AUTOMATED TEST SCENARIOS")
    print("=" * 60)
    
    test_cases = [
        # Normal functionality
        ("Calculate 15 + 25", "Testing calculator functionality"),
        ("Find outlets in Kuala Lumpur", "Testing outlet search"),
        ("Show me eco-friendly cups", "Testing product RAG search"),
        
        # Missing parameters
        ("Calculate", "Testing missing parameters"),
        ("Find outlets", "Testing missing location"),
        ("Show me products", "Testing missing search query"),
        
        # Security tests
        ("'; DROP TABLE outlets; --", "Testing SQL injection"),
        ("<script>alert('xss')</script>", "Testing XSS prevention"),
        ("__import__('os').system('ls')", "Testing code injection"),
    ]
    
    for i, (message, description) in enumerate(test_cases, 1):
        print(f"\n{i}. {description}")
        print(f"   Input: '{message}'")
        
        response, success = await demo.process_message(message)
        status = "✅ Pass" if success else "⚠️  Safe Error"
        
        print(f"   Output: {response[:100]}{'...' if len(response) > 100 else ''}")
        print(f"   Status: {status}")
    
    print(f"\n🎉 All {len(test_cases)} test scenarios completed!")

async def main():
    """Main function"""
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        await run_test_scenarios()
    else:
        demo = SimpleChatbotDemo()
        await demo.run_demo()

if __name__ == "__main__":
    asyncio.run(main())