"""
Configuration settings for the Mindhive Chatbot application.
"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Data directories
DATA_DIR = BASE_DIR / "app" / "data"
VECTOR_STORE_DIR = BASE_DIR / "data" / "vector_store"

# Data files
ZUS_PRODUCTS_FILE = DATA_DIR / "zus_products.json"
ZUS_OUTLETS_FILE = DATA_DIR / "zus_outlets.json"

# Database settings
DEFAULT_DB_PATH = "data/zus_outlets.db"

# Vector store settings
DEFAULT_VECTOR_STORE_PATH = "data/vector_store"
DEFAULT_SENTENCE_TRANSFORMER_MODEL = "all-MiniLM-L6-v2"

# API Settings
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000

# OpenAI Settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Intent Classification Thresholds
INTENT_CONFIDENCE_THRESHOLD = 0.6
HIGH_CONFIDENCE_THRESHOLD = 0.8

# Response Settings
MAX_SEARCH_RESULTS = 20
DEFAULT_SEARCH_RESULTS = 5

# Ensure directories exist
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)