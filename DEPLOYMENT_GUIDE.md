# Deployment Guide

## Fixed Issues Summary

### 1. **Dependency Conflicts Resolved**
- **Problem**: `langchain-openai==0.0.2` conflicted with `openai==1.3.0`
- **Solution**: Updated to compatible versions:
  - `langchain-openai>=0.0.8`
  - `openai>=1.6.1,<2.0.0`

### 2. **Python Version Compatibility**
- **Problem**: Some packages like `pandas==2.1.3` don't work with Python 3.13
- **Solution**: 
  - Updated to `pandas>=2.2.0` for Python 3.13 compatibility
  - Used flexible version ranges (`>=`) instead of exact versions
  - Created `requirements-minimal.txt` for production

### 3. **Hardcoded Paths Fixed**
- **Problem**: Hardcoded paths like `/Users/solehahyunita/mindhive-chatbot/...`
- **Solution**: 
  - Created `app/config.py` with centralized path management
  - Updated all files to use `os.path.join()` with relative paths
  - Fixed paths in `rag_endpoints.py`, `text2sql_system.py`, `product_vectorstore.py`

## Installation Options

### Option 1: Development Install
```bash
# Clone repository
git clone <repository-url>
cd mindhive-chatbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install all dependencies (including dev tools)
pip install -r requirements.txt
```

### Option 2: Production Install
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install minimal production dependencies
pip install -r requirements-minimal.txt
```

### Option 3: Docker Deployment
```bash
# Build Docker image
docker build -t mindhive-chatbot .

# Run container
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=your_key_here \
  mindhive-chatbot
```

## Environment Configuration

### Required Environment Variables
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Optional Environment Variables
```env
CALCULATOR_API_URL=http://localhost:8001
DATABASE_URL=sqlite:///./chatbot.db
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

## Deployment Platforms

### Render.com
1. Create new web service
2. Connect to GitHub repository
3. Use `render.yaml` configuration (already created)
4. Set environment variables in dashboard

### Docker/Kubernetes
1. Build image: `docker build -t mindhive-chatbot .`
2. Push to registry
3. Deploy using provided `Dockerfile`

### Local Development
```bash
# Start development server
python main.py

# Or with auto-reload
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## Health Checks

The application includes:
- Health check endpoint: `GET /`
- Docker health check configured
- API documentation: `GET /docs`

## File Structure Changes

### New Files Created:
- `app/config.py` - Centralized configuration
- `requirements-minimal.txt` - Production dependencies
- `Dockerfile` - Container configuration
- `render.yaml` - Render.com deployment config
- `.dockerignore` - Docker build optimization
- `INTENT_PARSING_APPROACH.md` - Architecture documentation

### Modified Files:
- `requirements.txt` - Updated dependency versions
- `app/api/rag_endpoints.py` - Fixed hardcoded paths
- `app/rag/text2sql_system.py` - Fixed hardcoded paths
- `app/rag/product_vectorstore.py` - Fixed hardcoded paths
- `app/services/chatbot_service.py` - Added documentation
- `README.md` - Updated installation instructions

## Troubleshooting

### Common Issues:

1. **ImportError**: Missing dependencies
   - Solution: Use `requirements-minimal.txt` for production
   - Check Python version compatibility

2. **File Not Found**: Data files missing
   - Solution: Ensure `app/data/` directory exists with JSON files
   - Check file permissions

3. **API Key Issues**: OpenAI authentication
   - Solution: Set `OPENAI_API_KEY` environment variable
   - Verify API key is valid and has credits

4. **Port Already in Use**: 8000 port occupied
   - Solution: Use different port or kill existing process
   - Command: `lsof -ti:8000 | xargs kill -9`

## Production Recommendations

### Security
- Set up proper authentication
- Use environment variables for secrets
- Enable HTTPS
- Implement rate limiting

### Monitoring
- Add logging and metrics
- Set up health checks
- Monitor API usage and costs

### Performance
- Use production ASGI server (Gunicorn + Uvicorn)
- Implement caching (Redis)
- Database optimization (PostgreSQL)

### Scaling
- Use load balancers
- Implement container orchestration
- Database connection pooling