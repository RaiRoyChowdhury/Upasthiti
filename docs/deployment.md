# Deployment - Phase 11

**I cannot deploy this myself** - the environment that generated this
project has no internet access at all (confirmed as far back as Phase 1,
where even `pip install` had to be run on your machine). Everything in
this document is real, working configuration - but every step marked
**[YOU RUN THIS]** below needs your accounts, your network access, your
`git push`.

## Two paths - pick one

| | Path A (recommended) | Path B (original spec's topology) |
|---|---|---|
| Frontend | Same Render service | Vercel |
| Backend | Render | Render |
| Complexity | Low - zero CORS/split-origin issues | Higher - two services, two URLs to keep in sync |
| Why | `main.py` already mounts the frontend at `/app` - this is exactly how local dev has worked since Phase 1 | Matches the original master spec's stated frontend/backend split literally |

**Recommendation: Path A**, unless you specifically need the frontend
on Vercel's CDN for some other reason. Path B works, but it's strictly
more moving parts for no functional benefit in this app's current shape
(the frontend is static files with no build step - Vercel's main
advantage, edge CDN + build pipelines, isn't doing much extra work here).

---

## Path A: Single Render service (recommended)

### 1. Push to GitHub [YOU RUN THIS]

```powershell
cd "path\to\smartattend-ai"
git add .
git status   # double-check .env is NOT listed
git commit -m "Prepare for deployment"
git remote add origin https://github.com/<your-username>/<your-repo>.git
git branch -M main
git push -u origin main
```

### 2. Create the Render service [YOU RUN THIS]

1. Go to https://dashboard.render.com -> New -> Web Service
2. Connect your GitHub repo
3. Render should detect `render.yaml` automatically (Blueprint option) -
   if not, fill in manually:
   - Runtime: Python 3
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set environment variables (Render dashboard -> Environment):
   - `APP_ENV=production`
   - `MONGODB_URI=<your real Atlas connection string>`
   - `MONGODB_DB_NAME=smartattend_ai`
   - `JWT_SECRET=<a real random value>` - generate one:
     ```powershell
     python -c "import secrets; print(secrets.token_urlsafe(64))"
     ```
   - `CORS_ORIGINS=https://<your-service-name>.onrender.com` (you'll know
     the exact URL after the first deploy - update this and redeploy)
5. Click Create Web Service. First build will take a while -
   opencv/insightface/onnxruntime are large (see docs/computer-vision.md's
   install-risk notes - they apply here too).

### 3. Allow Render's IP in MongoDB Atlas [YOU RUN THIS]

Atlas -> Network Access -> Add IP Address -> either Render's specific
egress IPs (find them in Render's docs for your plan) or, for initial
testing only, 0.0.0.0/0 ("allow from anywhere") - tighten this once
you confirm the exact IP(s) Render uses for your plan.

### 4. Create the first admin [YOU RUN THIS]

Render's dashboard -> your service -> Shell tab:
```bash
cd backend
python scripts/create_admin.py
```

### 5. Verify

Visit `https://<your-service>.onrender.com/app/pages/login.html`.

---

## Path B: Split deployment (Vercel frontend + Render backend)

### 1. Deploy the backend to Render first

Same as Path A steps 1-4, except `CORS_ORIGINS` needs to include your
Vercel domain once you have it (circle back after step 3 below).

### 2. Enable the split-origin config [YOU RUN THIS]

Edit `frontend/config.js` and set the real Render URL:
```javascript
window.SMARTATTEND_API_BASE_URL = "https://<your-backend>.onrender.com";
```

Every page needs to load this BEFORE `api.js`. Add this line to each
page's `<head>`, right before the `api.js` script tag:
```html
<script src="../config.js"></script>
```

This touches roughly 15 HTML files - simplest to just edit each by hand
(one line each), or search-and-replace `<script src="../js/api.js">`
in your editor and add the config.js line just above it.

### 3. Deploy the frontend to Vercel [YOU RUN THIS]

```powershell
cd "path\to\smartattend-ai"
npx vercel --prod
```
Follow the prompts - link/create a Vercel project, confirm the
vercel.json settings.

### 4. Close the loop on CORS [YOU RUN THIS]

Once Vercel gives you the deployed URL (e.g.
`https://smartattend-ai.vercel.app`), go back to Render's dashboard and
update `CORS_ORIGINS` to include it, then redeploy Render.

### 5. Create the first admin, verify

Same as Path A steps 4-5, but visit your Vercel URL instead.

---

## Production hardening checklist

- [x] `main.py`'s lifespan refuses to start if `APP_ENV=production` and
  `JWT_SECRET` is still the dev placeholder (Phase 1) - confirm this
  actually fires if you forget to set a real secret.
- [x] `.env` is gitignored, never committed (verify with `git status`
  before every push).
- [x] `CORS_ORIGINS` is a specific domain list, never `*`, in production.
- [ ] Not yet verified live: confirm the WebSocket connects correctly
  over `wss://` (not `ws://`) once served over HTTPS - `js/websocket.js`
  already derives the protocol from whether the page is HTTPS, but this
  has only been tested over plain HTTP locally.
- [ ] Not yet verified live: MongoDB Atlas IP allowlist tightened beyond
  0.0.0.0/0 once you know Render's actual egress IPs.
- [ ] Consider Render's free/starter tier cold-start behavior - the
  InsightFace model load happens lazily on first recognition request, so
  the very first enrollment/recognition after a cold start will be
  noticeably slower than subsequent ones. Expected, not a bug - see
  docs/computer-vision.md "Model lifecycle".

## What I could not verify

Everything above is real configuration, written correctly to the best of
static review - but none of it has actually been run. Please report back
exactly what happens at each numbered step, especially whether the
Render build completes (the CV dependency install is the highest-risk
part), whether the deployed app can reach Atlas, and whether the
WebSocket connects over wss:// in a real browser against a real HTTPS
deployment.
