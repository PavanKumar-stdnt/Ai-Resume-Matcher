# AI Resume Matcher v2 — Deployment Guide
# (Kubernetes excluded — free stack only)

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│   Streamlit Cloud       │  HTTPS  │   Render / AWS EC2       │
│   (Frontend UI)         │────────▶│   FastAPI + Docker       │
│   streamlit.app         │         │   Port 8000              │
└─────────────────────────┘         └──────────┬───────────────┘
                                               │
                          ┌────────────────────┼──────────────┐
                          │                    │              │
                   ┌──────▼──────┐    ┌────────▼───────┐  ┌──▼──────────┐
                   │ Qdrant Cloud│    │ MLflow Server  │  │ Gemini API  │
                   │  (Free tier)│    │ (Self-hosted)  │  │ Google AI   │
                   └─────────────┘    └────────────────┘  └─────────────┘
```

## Cost Summary — All Free

| Service | Platform | Cost |
|---------|----------|------|
| Frontend | Streamlit Cloud | FREE |
| Backend | Render.com | FREE |
| Vector DB | Qdrant Cloud | FREE |
| Embeddings | FastEmbed (local CPU) | FREE |
| LLM | Gemini free tier | FREE |
| Tracking | MLflow self-hosted | FREE |
| CI/CD | GitHub Actions | FREE |
| **Total** | | **$0/month** |

---

## Step 1 — Qdrant Cloud Setup

1. Go to https://cloud.qdrant.io → Sign up free
2. Create Cluster → Free tier → any region
3. Copy your **Cluster URL** and **API Key**
4. Add to `.env`:
   ```
   QDRANT_URL=https://xxxx.qdrant.io:6333
   QDRANT_API_KEY=your_qdrant_api_key
   ```

---

## Step 2 — GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit — AI Resume Matcher v2"
git remote add origin https://github.com/YOUR_USERNAME/ai-resume-matcher.git
git branch -M main
git push -u origin main
```

### GitHub Secrets (Settings → Secrets → Actions)

**For Render deployment:**
| Secret | Value |
|--------|-------|
| RENDER_DEPLOY_HOOK_URL | From Render dashboard → Settings → Deploy Hook |

**For EC2 deployment:**
| Secret | Value |
|--------|-------|
| EC2_HOST | Your EC2 public IP |
| EC2_USER | ubuntu |
| EC2_SSH_KEY | Your .pem private key content |

### GitHub Variables (Settings → Variables → Actions)
| Variable | Value |
|----------|-------|
| DEPLOY_TARGET | `render` OR `ec2` |

---

## Step 3A — Deploy Backend on Render (Recommended)

1. Go to https://render.com → New → Blueprint
2. Connect GitHub → select your repository
3. Render reads `render.yaml` automatically
4. Set these env vars manually in Render dashboard:
   - `GOOGLE_API_KEY`
   - `API_SECRET_KEY`
   - `QDRANT_URL`
   - `QDRANT_API_KEY`
5. Click **Deploy**
6. API URL: `https://resume-matcher-api.onrender.com`

Verify:
```
https://resume-matcher-api.onrender.com/api/v1/health
→ {"status": "ok"}
```

---

## Step 3B — Deploy Backend on AWS EC2

```bash
# 1. Launch: Ubuntu 22.04, t3.medium, ports 22/80/443/8000/5000 open

# 2. SSH in
ssh -i your-key.pem ubuntu@YOUR_EC2_IP

# 3. Bootstrap (one-time)
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/ai-resume-matcher/main/ec2-setup.sh
chmod +x ec2-setup.sh && sudo ./ec2-setup.sh

# 4. Clone and configure
cd /opt/ai-resume-matcher
git clone https://github.com/YOUR_USERNAME/ai-resume-matcher.git .
cp .env.example .env && nano .env

# 5. Start
docker compose up -d

# 6. Verify
curl http://localhost:8000/api/v1/health
```

---

## Step 4 — Deploy Frontend on Streamlit Cloud

1. Go to https://share.streamlit.io → New app
2. Repository: `YOUR_USERNAME/ai-resume-matcher`
3. Main file: `streamlit_app.py`
4. Advanced settings → Secrets:
   ```toml
   API_BASE_URL = "https://resume-matcher-api.onrender.com"
   API_SECRET_KEY = "your_secret_key"
   ```
5. Click **Deploy**

---

## Step 5 — MLflow Tracking

Access MLflow UI:
```
Render:  https://resume-matcher-mlflow.onrender.com
EC2:     http://YOUR_EC2_IP:5000
```

Each match run logs:
- **Params**: model names, chunk size/overlap, weights
- **Metrics**: vector_score, llm_score, final_score, elapsed_seconds
- **Artifacts**: retrieved_chunks.json, llm_analysis.txt

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| GOOGLE_API_KEY | ✅ | — | Google Gemini API key |
| API_SECRET_KEY | ✅ | — | X-API-KEY header token |
| QDRANT_URL | ✅ | — | Qdrant Cloud cluster URL |
| QDRANT_API_KEY | ✅ | — | Qdrant Cloud API key |
| MLFLOW_TRACKING_URI | ✅ | ./mlruns | MLflow server URL |
| ENVIRONMENT | Optional | production | development/production |
| ALLOWED_ORIGINS | Optional | * | Comma-separated CORS origins |
| GEMINI_MODEL | Optional | gemini-2.5-flash | Gemini model name |
| MLFLOW_ENABLED | Optional | true | Enable/disable tracking |
