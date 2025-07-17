# Render.com Deployment Instructions

## 🚀 Quick Deploy Steps

### 1. Manual Deployment (Recommended)

1. **Sign up/Login** to [Render.com](https://render.com)
2. **Click "New +"** → **"Web Service"**
3. **Connect GitHub** repository: `sitisolehahyr/mindhive-ai-chatbot-assessment`
4. **Configure settings**:

| Setting | Value |
|---------|-------|
| **Name** | `mindhive-chatbot` |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements-render.txt` |
| **Start Command** | `uvicorn main_light:app --host 0.0.0.0 --port $PORT` |

5. **Environment Variables** (under Advanced):
   - `OPENAI_API_KEY` = `your_openai_api_key_here`

6. **Choose Instance Type**: `Free`
7. **Click "Create Web Service"**

### 2. Auto-Deploy with render.yaml

If you have the render.yaml file in your repo, Render will automatically detect the configuration.

## 🔧 Key Configuration Details

### Port Configuration
- **Default Port**: Render uses port `10000` by default
- **Port Binding**: Must bind to `0.0.0.0:$PORT`
- **Environment Variable**: `$PORT` is automatically set by Render

### Memory Optimization
- **Requirements**: Using `requirements-render.txt` (lightweight)
- **Main App**: Using `main_light.py` (memory-optimized)
- **Dependencies**: Removed heavy AI libraries for free tier

### Build Process
```bash
# Build command
pip install -r requirements-render.txt

# Start command  
uvicorn main_light:app --host 0.0.0.0 --port $PORT
```

## 📊 Expected Deployment Timeline
- **Build Time**: 2-3 minutes
- **Deploy Time**: 1-2 minutes
- **Total**: 3-5 minutes

## 🧪 Testing After Deployment

Your app will be available at: `https://mindhive-chatbot.onrender.com`

### Test Endpoints:
1. **Health Check**: `GET /`
2. **API Docs**: `GET /docs`
3. **Chat**: `POST /api/chat/message`
4. **Products**: `GET /api/products?query=tumbler`
5. **Outlets**: `GET /api/outlets`

### Sample Test:
```bash
curl https://mindhive-chatbot.onrender.com/
curl https://mindhive-chatbot.onrender.com/api/products?query=coffee
```

## 🔍 Troubleshooting

### Common Issues:

1. **"No open ports detected"**
   - Ensure start command includes `--host 0.0.0.0 --port $PORT`
   - Check that the app actually starts and binds to the port

2. **"Out of memory"**
   - Use `requirements-render.txt` instead of `requirements.txt`
   - Use `main_light.py` instead of `main.py`

3. **Build failures**
   - Check build logs in Render dashboard
   - Verify requirements file exists and is valid

4. **Runtime errors**
   - Check deploy logs in Render dashboard
   - Verify all environment variables are set

## 🆙 Upgrading for Full Features

For the full-featured version with RAG, vector search, and agentic planning:
- Upgrade to Render's paid plan (2GB+ memory)
- Use `requirements.txt` and `main.py`
- Add environment variables for OpenAI API

## 📞 Support

If deployment fails:
1. Check Render's deployment logs
2. Verify GitHub repository access
3. Ensure all files are committed and pushed
4. Contact Render support if needed