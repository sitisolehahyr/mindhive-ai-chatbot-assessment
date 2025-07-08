from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.chat import router as chat_router
from app.api.agentic_chat import router as agentic_chat_router
from app.api.dspy_calculator import router as dspy_calculator_router
from app.api.restaurants import router as restaurants_router
from app.api.products import router as products_router
from app.api.rag_endpoints import router as rag_router

app = FastAPI(
    title="Mindhive Chatbot API",
    description="Technical assessment chatbot with sequential conversation tracking",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(agentic_chat_router)
app.include_router(dspy_calculator_router)
app.include_router(restaurants_router)
app.include_router(products_router)
app.include_router(rag_router)

@app.get("/")
async def root():
    return {"message": "Mindhive Chatbot API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)