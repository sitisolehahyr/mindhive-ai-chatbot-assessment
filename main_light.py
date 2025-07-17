"""
Lightweight version of the main app for Render deployment
Excludes heavy AI models that cause memory issues
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Mindhive Chatbot API - Lightweight",
    description="Technical assessment chatbot optimized for deployment",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic models
class ChatRequest(BaseModel):
    message: str
    user_id: str
    conversation_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    conversation_id: str
    user_id: str

class ProductResult(BaseModel):
    name: str
    category: str
    price: str
    description: str
    features: List[str]
    availability: bool

class ProductSearchResponse(BaseModel):
    query: str
    results: List[ProductResult]
    total_found: int
    summary: str

# Mock data for demonstration
MOCK_PRODUCTS = [
    {
        "name": "ZUS Travel Tumbler Premium",
        "category": "Drinkware",
        "price": "RM 55.00",
        "description": "Premium travel tumbler designed for the modern coffee lover on the go. Features advanced insulation technology and spill-proof design.",
        "features": ["Advanced insulation", "Spill-proof design", "Travel-friendly", "Premium finish"],
        "availability": True
    },
    {
        "name": "ZUS All Day Cup 500ml - Mountain",
        "category": "Drinkware", 
        "price": "RM 45.00",
        "description": "ZUS All Day Cup in mountain green color. Premium double-wall vacuum insulated tumbler designed for coffee enthusiasts.",
        "features": ["Double-wall vacuum insulation", "500ml capacity", "Stainless steel", "BPA-free"],
        "availability": True
    },
    {
        "name": "ZUS Eco-Friendly Cup",
        "category": "Drinkware",
        "price": "RM 35.00", 
        "description": "Sustainable coffee cup made from eco-friendly materials. Perfect for environmentally conscious coffee lovers.",
        "features": ["Eco-friendly materials", "Biodegradable", "Sustainable design", "Lightweight"],
        "availability": True
    }
]

MOCK_OUTLETS = [
    {
        "name": "Mid Valley Outlet",
        "city": "Kuala Lumpur",
        "state": "Selangor",
        "address": "L2-034, Mid Valley Megamall, Kuala Lumpur",
        "phone": "+603-8765-4321",
        "operating_hours": {"daily": "10:00 AM - 10:00 PM"},
        "services": ["Dine-in", "Takeaway"]
    },
    {
        "name": "SS2 Outlet", 
        "city": "Petaling Jaya",
        "state": "Selangor",
        "address": "No. 123, Jalan SS2/24, SS2, 47300 Petaling Jaya, Selangor",
        "phone": "+603-1234-5678",
        "operating_hours": {"daily": "9:00 AM - 9:00 PM"},
        "services": ["Dine-in", "Takeaway", "Delivery"]
    }
]

@app.get("/")
async def root():
    return {"message": "Mindhive Chatbot API is running (Lightweight Version)"}

@app.post("/api/chat/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Basic chat endpoint with simple responses"""
    try:
        message = request.message.lower()
        
        # Simple intent-based responses
        if any(word in message for word in ['calculate', 'math', '+', '-', '*', '/']):
            # Extract numbers and operators
            import re
            numbers = re.findall(r'\d+\.?\d*', message)
            if len(numbers) >= 2:
                a, b = float(numbers[0]), float(numbers[1])
                if '+' in message:
                    result = a + b
                    response = f"The result of {a} + {b} is {result}."
                elif '-' in message:
                    result = a - b
                    response = f"The result of {a} - {b} is {result}."
                elif '*' in message:
                    result = a * b
                    response = f"The result of {a} × {b} is {result}."
                elif '/' in message:
                    result = a / b if b != 0 else "Error: Division by zero"
                    response = f"The result of {a} ÷ {b} is {result}."
                else:
                    response = "I can help you calculate. Please provide numbers with +, -, *, or /."
            else:
                response = "I need two numbers to calculate. Try: 'Calculate 5 + 3'"
                
        elif any(word in message for word in ['outlet', 'store', 'location']):
            if 'kuala lumpur' in message or 'kl' in message:
                outlet = MOCK_OUTLETS[0]
                response = f"Yes! The {outlet['name']} is located at {outlet['address']}. Operating hours: {outlet['operating_hours']['daily']}. Phone: {outlet['phone']}."
            else:
                response = "We have outlets in Kuala Lumpur (Mid Valley) and Petaling Jaya (SS2). Which one would you like to know about?"
                
        elif any(word in message for word in ['product', 'tumbler', 'cup']):
            response = "I can help you find ZUS products! Try using the product search endpoint at /api/products or ask about specific items like 'coffee tumbler' or 'eco-friendly cup'."
            
        else:
            response = "I'm here to help you with mathematical calculations, outlet information, and product searches. How can I assist you today?"
        
        return ChatResponse(
            response=response,
            conversation_id=request.conversation_id or f"conv_{request.user_id}_{hash(request.message)}",
            user_id=request.user_id
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products", response_model=ProductSearchResponse)
async def search_products(query: str):
    """Simple product search without heavy AI models"""
    try:
        query_lower = query.lower()
        
        # Simple keyword matching
        results = []
        for product in MOCK_PRODUCTS:
            if (query_lower in product['name'].lower() or 
                query_lower in product['description'].lower() or
                any(query_lower in feature.lower() for feature in product['features'])):
                results.append(ProductResult(**product))
        
        # If no specific matches, return all products
        if not results:
            results = [ProductResult(**product) for product in MOCK_PRODUCTS]
        
        summary = f"Found {len(results)} ZUS Coffee products matching '{query}'. Here are the top results:"
        
        return ProductSearchResponse(
            query=query,
            results=results,
            total_found=len(results),
            summary=summary
        )
        
    except Exception as e:
        logger.error(f"Product search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/outlets")
async def get_outlets():
    """Get outlet information"""
    return {
        "outlets": MOCK_OUTLETS,
        "total_count": len(MOCK_OUTLETS)
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "lightweight",
        "memory_optimized": True
    }

@app.get("/docs")
async def get_docs():
    """Redirect to OpenAPI docs"""
    return {"message": "API documentation available at /docs"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)