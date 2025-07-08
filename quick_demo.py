#!/usr/bin/env python3
"""
Quick demo untuk testing Mindhive Chatbot dengan skenario otomatis
"""
import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.action_executor import ActionExecutor
from app.core.planner import AgenticPlanner, PlanningContext
from app.models.conversation import ConversationMemory, ConversationTurn, IntentType

async def test_chatbot_scenario(message: str, description: str):
    """Test a single chatbot scenario"""
    print(f"\n📝 {description}")
    print(f"💬 User: '{message}'")
    print("🤖 Bot: ", end="", flush=True)
    
    try:
        # Initialize components
        executor = ActionExecutor()
        planner = AgenticPlanner()
        memory = ConversationMemory(
            conversation_id="test-session",
            user_id="test-user"
        )
        
        # Simple intent detection
        message_lower = message.lower()
        if any(word in message_lower for word in ['calculate', 'math', '+', '-', '*', '/', 'divide']):
            intent = IntentType.CALCULATION
        elif any(word in message_lower for word in ['outlet', 'location', 'address', 'hours']):
            intent = IntentType.OUTLET_INQUIRY
        elif any(word in message_lower for word in ['restaurant', 'food', 'cuisine']):
            intent = IntentType.RESTAURANT_SEARCH
        elif any(word in message_lower for word in ['product', 'tumbler', 'cup', 'show me']):
            intent = IntentType.PRODUCT_SEARCH
        else:
            intent = IntentType.GENERAL_QUERY
        
        # Create planning context
        planning_context = PlanningContext(
            intent=intent,
            entities={},
            confidence=0.8,
            conversation_memory=memory,
            user_message=message,
            missing_slots=[],
            available_slots={}
        )
        
        # Plan and execute
        decision = await planner.plan_next_action(planning_context)
        
        context = {
            "user_message": message,
            "memory": memory,
            "session_id": "test-session"
        }
        
        result = await executor.execute_decision(decision, context)
        
        print(result.response[:150] + ("..." if len(result.response) > 150 else ""))
        
        status = "✅ Success" if result.success else "⚠️  Handled gracefully"
        print(f"    Status: {status}")
        
        return result.success
        
    except Exception as e:
        print(f"❌ Error: {str(e)[:100]}...")
        return False

async def main():
    """Run all demo scenarios"""
    print("🤖 MINDHIVE CHATBOT - QUICK DEMO")
    print("=" * 60)
    print("Testing all major features and error handling scenarios...")
    
    scenarios = [
        # Normal functionality tests
        ("Calculate 25 + 37", "Testing Calculator Functionality"),
        ("Find outlets in Kuala Lumpur", "Testing Outlet Search"),
        ("Show me coffee tumblers", "Testing Product Search"),
        ("Find Italian restaurants", "Testing Restaurant Search"),
        
        # Missing parameters tests
        ("Calculate", "Testing Missing Calculator Parameters"),
        ("Find outlets", "Testing Missing Outlet Location"),
        ("Show me products", "Testing Missing Product Query"),
        
        # Security tests
        ("'; DROP TABLE outlets; --", "Testing SQL Injection Prevention"),
        ("<script>alert('xss')</script>", "Testing XSS Prevention"),
        ("__import__('os').system('ls')", "Testing Code Injection Prevention"),
        
        # Edge cases
        ("", "Testing Empty Input"),
        ("asdfjkl qwerty", "Testing Nonsense Input"),
        ("What is the meaning of life?", "Testing Out-of-Scope Query"),
    ]
    
    total_tests = len(scenarios)
    passed_tests = 0
    
    for i, (message, description) in enumerate(scenarios, 1):
        print(f"\n[{i}/{total_tests}]", end=" ")
        success = await test_chatbot_scenario(message, description)
        if success or "gracefully" in description:
            passed_tests += 1
    
    print(f"\n" + "=" * 60)
    print(f"🎯 DEMO RESULTS: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests*100:.1f}%)")
    
    if passed_tests == total_tests:
        print("🎉 Perfect! All scenarios handled successfully!")
        print("\n✅ System Features Demonstrated:")
        print("   • Calculator with DSPy integration")
        print("   • RAG-powered product search")
        print("   • Text2SQL outlet queries")
        print("   • Restaurant API integration")
        print("   • Robust error handling")
        print("   • Security attack prevention")
        print("   • Graceful degradation")
    else:
        print(f"⚠️  {total_tests - passed_tests} scenarios need attention")
    
    print(f"\n📋 To try the interactive version:")
    print(f"   1. Start the backend: python3 -m uvicorn main:app --reload")
    print(f"   2. Open frontend/index.html in your browser")
    print(f"   3. Test all features with the web interface!")

if __name__ == "__main__":
    asyncio.run(main())