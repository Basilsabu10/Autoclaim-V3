# 🚀 AutoClaim-V3 — Deploy Steps (Zero Cost)

> Complete step-by-step guide to deploy AutoClaim-V3 for free.
> **Estimated time: ~30 minutes**

---

## 📋 What You'll Need Before Starting

| Item | Where to Get |
|---|---|
| GitHub account (repo already pushed) | github.com |
| Groq API Key | [console.groq.com](https://console.groq.com) → Free |
| Gemini API Key | [aistudio.google.com](https://aistudio.google.com) → Free |

---

## STEP 1 — Create PostgreSQL Database (Neon.tech)

1. Go to **[neon.tech](https://neon.tech)** → click **"Start Free"**
2. Sign up with your **GitHub account** (no credit card needed)
3. Click **"New Project"** → name it `autoclaim-db` → click **"Create Project"**
4. On the project dashboard, click **"Connection string"**
5. Select **"psycopg2"** format → copy the full URI:
   ```
   postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
6. **Save this URI** — you'll need it in Step 2

---

## STEP 2 — Deploy Backend API (Render.com)

1. Go to **[render.com](https://render.com)** → click **"Get Started"**
2. Sign up with **GitHub** (no credit card needed)
3. Click **"New +"** → **"Web Service"**
4. Click **"Connect a repository"** → select your `Autoclaim-V3` (or `Autoclaim-main`) repo
5. Render will auto-detect the `render.yaml` file
6. **Confirm these settings**:
   - **Name**: `autoclaim-api`
   - **Root Directory**: `Autoclaim-V3/autoclaim_project/server`
   - **Build Command**: `pip install -r requirements-render.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
7. Click **"Create Web Service"**
8. While it's building, click the **"Environment"** tab on the left and add:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | *(Paste your Neon URI from Step 1)* |
   | `SECRET_KEY` | `autoclaim_demo_key_2026_secure` |
   | `GROQ_API_KEY` | *(Paste your Groq API key)* |
   | `GEMINI_API_KEY` | *(Paste your Gemini API key)* |
   | `AI_MODE` | `yolo_only` |
   | `FRONTEND_URL` | *(Leave blank for now — fill after Step 4)* |
   | `PRICE_API_URL` | *(Leave blank for now — fill after Step 3)* |

9. Wait ~5 minutes for the build to complete
10. **Copy your backend URL** → looks like: `https://autoclaim-api.onrender.com`

> ⚠️ **First cold start takes ~30 seconds.** Visit the URL once and wait for the `{"name":"AutoClaim API"...}` response before continuing.

---

## STEP 3 — Deploy Price API (Render.com — Second Service)

1. In Render → click **"New +"** → **"Web Service"**
2. Select the **same repository**
3. Set these settings **manually** (render.yaml defines both, but verify):
   - **Name**: `autoclaim-price-api`
   - **Root Directory**: `Price_api`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Click **"Create Web Service"**
5. Wait for deploy → copy the URL: `https://autoclaim-price-api.onrender.com`
6. Go back to **Step 2 backend → Environment** → update:
   - `PRICE_API_URL` = `https://autoclaim-price-api.onrender.com/api/price-estimate`

---

## STEP 4 — Deploy Frontend (Vercel)

1. Go to **[vercel.com](https://vercel.com)** → click **"Sign Up"**
2. Sign up with **GitHub**
3. Click **"Add New..."** → **"Project"**
4. Click **"Import"** next to your `Autoclaim-V3` repository
5. Configure the project:
   - **Framework Preset**: `Vite`
   - **Root Directory**: click **"Edit"** → type `Autoclaim-V3/autoclaim_project/client` → click **"Continue"**
6. Expand **"Environment Variables"** and add:
   - `VITE_API_URL` = `https://autoclaim-api.onrender.com`
   - `VITE_PRICE_API_URL` = `https://autoclaim-price-api.onrender.com`
7. Click **"Deploy"**
8. Wait ~2 minutes → **Copy your frontend URL**: `https://autoclaim-v3.vercel.app`

---

## STEP 5 — Wire CORS (Final Connection)

1. Go to **Render.com** → open `autoclaim-api` service → **"Environment"** tab
2. Update: `FRONTEND_URL` = `https://autoclaim-v3.vercel.app` *(your actual Vercel URL)*
3. Render will automatically redeploy the backend (~2 min)

---

## STEP 6 — Initialize Database Indexes (Performance)

This runs the pre-built index script on your production database:

1. In Render → `autoclaim-api` → click **"Shell"** (top right)
2. Run:
   ```bash
   python add_indexes.py
   ```
3. You should see index creation confirmation messages

---

## ✅ Test Your Deployment

Visit your Vercel URL and test:
- [ ] Login with `admin@autoclaim.com` / `admin123` (auto-created on first startup)
- [ ] Submit a new claim
- [ ] View claim history
- [ ] Check price estimate feature

---

## 🤖 Optional: Full AI Demo via Google Colab

> Use this to show live YOLO damage detection during your presentation.

1. Open **[Google Colab](https://colab.research.google.com)**
2. Runtime → **Change runtime type** → **T4 GPU** → Save
3. Create a new notebook and paste this:

```python
# Install dependencies
!pip install pyngrok uvicorn
!pip install -r requirements.txt  # Full stack with torch/YOLO

# Clone your repo (or upload directly)
!git clone https://github.com/YOUR_GITHUB_USERNAME/Autoclaim-V3.git
%cd Autoclaim-V3/autoclaim_project/server

# Set ENV variables
import os
os.environ["DATABASE_URL"] = "YOUR_NEON_DB_URL"
os.environ["SECRET_KEY"] = "autoclaim_demo_key_2026_secure"
os.environ["GROQ_API_KEY"] = "YOUR_GROQ_KEY"
os.environ["GEMINI_API_KEY"] = "YOUR_GEMINI_KEY"
os.environ["AI_MODE"] = "full"

# Start server + expose via ngrok
from pyngrok import ngrok
import threading, uvicorn

ngrok.set_auth_token("YOUR_NGROK_TOKEN")  # free at ngrok.com
tunnel = ngrok.connect(8000)
print("🚀 AI Backend live at:", tunnel.public_url)

threading.Thread(
    target=lambda: uvicorn.run("app.main:app", host="0.0.0.0", port=8000)
).start()
```

4. Copy the printed ngrok URL (e.g. `https://xxxx.ngrok.io`)
5. In Vercel dashboard → Project Settings → Environment Variables → Update `VITE_API_URL` to the ngrok URL → **Redeploy**

> Ngrok free tier: 1 session per account. Session lasts 4-12 hours. Start 30 min before demo.

---

## 💰 Cost Summary

| Service | Plan | Cost |
|---|---|---|
| Neon.tech | Free Tier | **$0** |
| Render.com (2 services) | Free Tier | **$0** |
| Vercel | Hobby (Free) | **$0** |
| Groq API | Free Tier | **$0** |
| Gemini API | Free Tier | **$0** |
| **Total** | | **$0.00/month** |

---

## 🌡️ Demo Day Checklist

```
T-120min  Open your Vercel URL to wake all Render services
T-60min   Start Google Colab AI notebook (if showing live AI)
T-15min   Login and do a full test claim submission
T-5min    Clear any test data, reset to clean state
T-0       Present! ✅
```

---

## 🔑 Key URLs Summary (fill in after deploying)

| Service | Your URL |
|---|---|
| Frontend (Vercel) | `https://_____.vercel.app` |
| Backend API (Render) | `https://autoclaim-api.onrender.com` |
| Price API (Render) | `https://autoclaim-price-api.onrender.com` |
| API Docs (Swagger) | `https://autoclaim-api.onrender.com/docs` |
