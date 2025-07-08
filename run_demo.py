#!/usr/bin/env python3
"""
Demo runner for Mindhive Chatbot
Starts both the FastAPI backend and opens the frontend
"""
import subprocess
import webbrowser
import time
import os
import signal
import sys
from pathlib import Path

def start_backend():
    """Start the FastAPI backend server"""
    print("🚀 Starting FastAPI backend server...")
    
    # Start uvicorn server
    backend_process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", 
        "main:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ], cwd=Path(__file__).parent)
    
    return backend_process

def open_frontend():
    """Open the frontend in browser"""
    frontend_path = Path(__file__).parent / "frontend" / "index.html"
    
    if frontend_path.exists():
        print("🌐 Opening frontend in browser...")
        webbrowser.open(f"file://{frontend_path.absolute()}")
    else:
        print("❌ Frontend file not found!")

def main():
    """Main demo runner"""
    print("=" * 60)
    print("🤖 MINDHIVE CHATBOT DEMO")
    print("=" * 60)
    print()
    
    backend_process = None
    
    try:
        # Start backend
        backend_process = start_backend()
        
        # Wait a bit for backend to start
        print("⏳ Waiting for backend to start...")
        time.sleep(3)
        
        # Open frontend
        open_frontend()
        
        print()
        print("✅ Demo is ready!")
        print()
        print("📋 Available features to test:")
        print("  • 🧮 Calculator: 'Calculate 25 + 37'")
        print("  • 📍 Outlets: 'Find outlets in Kuala Lumpur'") 
        print("  • 🔍 Products: 'Show me coffee tumblers'")
        print("  • 🍝 Restaurants: 'Find Italian restaurants in KL'")
        print("  • 🌱 RAG Search: 'Show me eco-friendly cups'")
        print("  • ⚠️ Error Testing: SQL injection, XSS, etc.")
        print()
        print("🌐 Frontend: file:///.../frontend/index.html")
        print("🔧 Backend API: http://localhost:8000")
        print("📚 API Docs: http://localhost:8000/docs")
        print()
        print("Press Ctrl+C to stop the demo")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping demo...")
        
    finally:
        if backend_process:
            print("🔌 Shutting down backend server...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
        
        print("✅ Demo stopped successfully!")

if __name__ == "__main__":
    main()