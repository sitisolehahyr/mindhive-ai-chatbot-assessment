#!/bin/bash

# Activate virtual environment
source .venv/bin/activate

# Check if requirements are installed
echo "Checking dependencies..."
python3 -c "import fastapi" 2>/dev/null || { echo "Installing dependencies..."; pip install -r requirements-minimal.txt; }

# Set environment variables if needed
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Start the server
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop the server"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload