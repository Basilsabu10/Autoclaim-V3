# 🚀 AutoClaim-V3 Deployment Steps

You are now ready to deploy! The code has been modified for cloud compatibility and pushed to your GitHub repository.

Follow these 3 phases to deploy your presentation demo:

---

## Phase 1: Create Free PostgreSQL Database (Neon.tech)
Your SQLite database cannot be used on Render free tier.

1. Go to [Neon.tech](https://neon.tech) and sign up with GitHub.
2. Click **Create Project**.
3. Name it `autoclaim-db`. Leave the region as default.
4. Once created, click **"Connection string"** and copy the URI.
   - *It will look like `postgresql://user:password@hostname/...`*
5. Save this URI for Phase 2.

---

## Phase 2: Deploy Backend (Render.com)

1. Go to [Render.com](https://render.com) and sign in with GitHub.
2. Click **New +** → **Web Service**.
3. Select **"Build and deploy from a Git repository"** and connect your `Autoclaim-V3` repository.
4. Render will automatically detect the **`render.yaml`** configuration I created. You just need to click **"Create Web Service"**.
5. Once it starts deploying, go to the **"Environment"** tab on the left.
6. Add these exact Environment Variables:

| Key | Value (Example) |
|---|---|
| `DATABASE_URL` | *(Paste your Neon.tech URL from Phase 1)* |
| `SECRET_KEY` | `basil_secure_key_12345` *(or any random secure string)* |
| `GROQ_API_KEY` | *(Paste your Groq API Key)* |
| `AI_MODE` | `yolo_only` |
| `FRONTEND_URL` | *(Leave blank for now, we will add it after Phase 3)* |

7. Wait for the deployment to finish (~5 minutes). It will give you a URL like `https://autoclaim-api.onrender.com`. Save this for Phase 3!

---

## Phase 3: Deploy Frontend (Vercel)

1. Go to [Vercel.com](https://vercel.com) and log in with GitHub.
2. Click **"Add New..."** → **"Project"**.
3. Import your `Autoclaim-V3` repository.
4. In the configuration screen:
   - **Framework Preset**: select `Vite`
   - **Root Directory**: click Edit and select `Autoclaim-V3/autoclaim_project/client`
5. Expand the **Environment Variables** section and add:
   - **Name**: `VITE_API_URL`
   - **Value**: *(Paste your Render backend URL from Phase 2)*
6. Click **Deploy**.

---

## Final Step (Crucial for Login/CORS)

Once Vercel gives you your frontend deploy link (e.g. `https://autoclaim-client.vercel.app`), you MUST go back to **Render.com**.
1. Open your backend service on Render.
2. Go to **Environment**.
3. Update the `FRONTEND_URL` variable with your actual Vercel link.
4. Render will automatically redeploy the backend with the updated CORS rule.

**You are done! 🎉** Your full-stack system is now live.

> Note regarding AI functionality: The backend is running on `yolo_only` mode but with CPU. Heavy tensor operations will likely time out or fail gracefully on the free Render tier (due to 512MB RAM limits) but the web app itself (login, claim forms, history) will function perfectly for your demo. To run AI, use Google Colab with exposing the port as defined previously!
