# Mindhive Chatbot - Usage Examples

This document demonstrates the implemented features of the Mindhive Assessment chatbot, showcasing sequential conversation flows, state management, and API integrations.

## Part 1: Sequential Conversation Flow ✅

### Example 1: Main Assessment Flow
```
User: "Is there an outlet in Petaling Jaya?"
Bot: "Yes! The SS2 Outlet is located at No. 123, Jalan SS2/24, SS2, 47300 Petaling Jaya, Selangor. Operating hours: 9:00 AM - 9:00 PM. Phone: +603-1234-5678."

User: "SS2, whats the opening time?"
Bot: "The SS2 Outlet opens at 9:00 AM - 9:00 PM."
```

### Example 2: Multi-turn Disambiguation
```
User: "Do you have any outlets?"
Bot: "Yes! We have outlets in SS2, Petaling Jaya, Mid Valley, Kuala Lumpur, 1 Utama, Petaling Jaya. Which outlet are you referring to?"

User: "Mid Valley"
Bot: "Yes! The Mid Valley Outlet is located at L2-034, Mid Valley Megamall, Kuala Lumpur. Operating hours: 10:00 AM - 10:00 PM. Phone: +603-8765-4321."

User: "What's the phone number?"
Bot: "You can contact the Mid Valley Outlet at +603-8765-4321."
```

## Features Implemented

### 1. State Management & Memory ✅
- **Conversation persistence**: Each conversation has a unique ID
- **Slot tracking**: Location, query type, and context maintained across turns
- **SQLite database**: Persistent storage for conversation history
- **Multi-user support**: Separate conversations for different users

### 2. Planner/Controller Logic ✅
- **Intent parsing**: Recognizes outlet inquiries, calculations, restaurants, products
- **Entity extraction**: Extracts locations (SS2, Mid Valley, 1 Utama, etc.)
- **Context awareness**: Understands follow-up questions based on conversation history
- **Confidence scoring**: Tracks confidence levels for intent recognition

### 3. Tool Integration ✅
- **Calculator API**: Handles mathematical operations
  ```
  User: "Calculate 25 + 15"
  Bot: "The result of 25.0 + 15.0 is 40.0."
  ```
- **Error handling**: Graceful handling of division by zero and invalid expressions

### 4. Custom API Endpoints ✅

#### Outlets API (Mock Data)
- **3 outlets**: SS2 (Petaling Jaya), Mid Valley (KL), 1 Utama (PJ)
- **Full details**: Address, opening hours, phone, services
- **Location mapping**: Intelligent mapping of user queries to specific outlets

#### Restaurants API
- **10 restaurants**: Malaysian, Chinese, Indian, Japanese, Italian, Thai, American cuisines
- **Search filters**: Cuisine, location, price range, rating
- **Endpoints**: `/api/restaurants/search`, `/api/restaurants/recommend`

#### Products API
- **12 products**: Electronics, Health & Fitness, Food & Beverage, etc.
- **Search filters**: Category, price range, availability, search terms
- **Endpoints**: `/api/products/search`, `/api/products/recommend`

## API Usage Examples

### Chat API
```bash
# Send a message
curl -X POST "http://localhost:8000/api/chat/message" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Is there an outlet in Petaling Jaya?",
    "user_id": "user123"
  }'

# Get conversation history
curl "http://localhost:8000/api/chat/history/{conversation_id}"
```

### Restaurant Search
```bash
# Search Malaysian restaurants
curl "http://localhost:8000/api/restaurants/search?cuisine=Malaysian"

# Get recommendations
curl -X POST "http://localhost:8000/api/restaurants/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "cuisine": "Japanese",
    "location": "Petaling Jaya",
    "price_range": "$$"
  }'
```

### Product Search
```bash
# Search electronics
curl "http://localhost:8000/api/products/search?category=Electronics"

# Search with price filter
curl "http://localhost:8000/api/products/search?price_min=20&price_max=100"
```

## Testing

### Automated Tests ✅
- **Conversation flow tests**: 10 comprehensive test scenarios
- **API endpoint tests**: Full coverage of all endpoints
- **Happy path testing**: Main assessment flow
- **Unhappy path testing**: Interruptions, unknown locations, invalid inputs
- **Concurrent conversations**: Multiple users simultaneously

### Run Tests
```bash
# Run all tests
python3 -m pytest app/tests/ -v

# Run specific test file
python3 -m pytest app/tests/test_conversation_flows.py -v
```

## Architecture

### Core Components
1. **ConversationMemory**: Pydantic models for conversation state
2. **MemoryManager**: SQLite-based persistence layer
3. **ChatbotService**: Main conversation processing logic
4. **FastAPI Routes**: RESTful API endpoints

### Database Schema
- **conversations**: Main conversation records
- **conversation_turns**: Individual turns with intent/entities
- **conversation_slots**: Persistent slot values

## Robustness Features ✅

### Error Handling
- **Graceful degradation**: Continues operation when components fail
- **Input validation**: Pydantic models ensure data integrity
- **Database errors**: Proper transaction handling
- **API timeouts**: Reasonable timeout settings

### Security Considerations
- **Input sanitization**: Protection against malicious payloads
- **SQL injection prevention**: Parameterized queries
- **CORS configuration**: Proper cross-origin handling

## Running the Application

### Start the Server
```bash
# Install dependencies
pip install fastapi uvicorn httpx pytest pytest-asyncio

# Start the server
python3 main.py

# Or with uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Access Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Assessment Completion Status

### ✅ Completed Features
1. **Sequential Conversation**: 3+ turn conversations with state persistence
2. **FastAPI Endpoints**: Full RESTful API with proper error handling
3. **Intent Recognition**: Outlet inquiries, calculations, restaurants, products
4. **Memory Management**: SQLite-based conversation persistence
5. **Tool Integration**: Calculator with mathematical operations
6. **Mock APIs**: Restaurants and products with realistic data
7. **Comprehensive Testing**: Automated tests for all scenarios
8. **Error Handling**: Graceful degradation and validation

### 🚧 Future Enhancements (Optional)
1. **RAG Pipeline**: Vector store integration for enhanced responses
2. **Advanced NLP**: More sophisticated intent recognition
3. **Real-time Updates**: WebSocket support for live conversations
4. **Analytics**: Conversation analytics and insights

## Conclusion

This implementation demonstrates a robust, production-ready chatbot system that meets all the requirements of the Mindhive Assessment. The system successfully handles multi-turn conversations, maintains state across interactions, integrates with external tools, and provides comprehensive API coverage with proper error handling.