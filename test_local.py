#!/usr/bin/env python3
"""
Simple test script to verify the application works locally
"""
import requests
import time
import json

def test_server():
    base_url = "http://localhost:8000"
    
    print("🔍 Testing local server...")
    
    # Test 1: Health check
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✅ Health check passed!")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running on port 8000")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False
    
    # Test 2: API documentation
    try:
        response = requests.get(f"{base_url}/docs")
        if response.status_code == 200:
            print("✅ API documentation accessible!")
        else:
            print(f"⚠️  API docs returned: {response.status_code}")
    except Exception as e:
        print(f"⚠️  API docs error: {e}")
    
    # Test 3: Test a simple endpoint
    try:
        # Try to get available endpoints
        response = requests.get(f"{base_url}/openapi.json")
        if response.status_code == 200:
            print("✅ OpenAPI schema accessible!")
            openapi_data = response.json()
            endpoints = list(openapi_data.get('paths', {}).keys())
            print(f"   Available endpoints: {endpoints[:5]}...")
        else:
            print(f"⚠️  OpenAPI schema: {response.status_code}")
    except Exception as e:
        print(f"⚠️  OpenAPI error: {e}")
    
    print("\n🚀 Server is running successfully!")
    print(f"   📍 Main URL: {base_url}")
    print(f"   📖 API Docs: {base_url}/docs")
    print(f"   🔧 OpenAPI: {base_url}/openapi.json")
    
    return True

if __name__ == "__main__":
    success = test_server()
    if not success:
        print("\n💡 To start the server, run:")
        print("   ./start_server.sh")
        print("   or")
        print("   source .venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000")