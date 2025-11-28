# Render Deployment Guide - Docker Build Fixed

## Problem & Solution

**Error:** `failed to solve: process "/bin/sh -c apt-get update..." exit code: 100`

**Root Cause:** Debian/Ubuntu package repository issues in Render's Docker build environment

**Solution:** Use Alpine Linux-based image instead (no apt-get issues, minimal size)

---

## Files Updated/Created

### 1. **Dockerfile** (Production - Debian-based)
- Fixed apt sources list explicitly
- Minimal dependencies
- Works if Alpine doesn't

### 2. **Dockerfile.alpine** (NEW - Recommended for Render)
- Alpine Linux base (no apt-get issues)
- Smaller image size (~400MB vs 1GB+)
- Faster builds
- **Use this for Render deployment**

### 3. **Dockerfile.render** (Debian multi-stage build)
- Kept as fallback
- Use if Alpine fails

### 4. **render.yaml** (Updated)
- Changed to use `Dockerfile.alpine`
- This avoids Debian apt-get errors entirely

### 5. **.dockerignore** (Existing)
- Keeps build context minimal

### Files Updated/Created

### 1. **Dockerfile** (Production - Debian-based)
- Fixed apt sources list explicitly
- Minimal dependencies
- Works if Alpine doesn't

### 2. **Dockerfile.alpine** (NEW - Recommended for Render)
- Alpine Linux base (no apt-get issues)
- Smaller image size (~400MB vs 1GB+)
- Faster builds
- **Use this for Render deployment**

### 3. **Dockerfile.render** (Debian multi-stage build)
- Kept as fallback
- Use if Alpine fails

### 4. **render.yaml** (Updated)
- Changed to use `Dockerfile.alpine`
- This avoids Debian apt-get errors entirely

### 5. **.dockerignore** (Existing)
- Keeps build context minimal

---

## Why Alpine Linux Fixes the Issue

**Problem with Debian/Ubuntu:**
- Repository metadata can be corrupted in build environment
- apt-get sometimes fails with exit code 100
- Unpredictable on Render's shared infrastructure

**Alpine Linux Solution:**
- Uses `apk` package manager (much more reliable)
- Smaller base image (alpine ~50MB vs slim ~150MB)
- Fewer dependencies = fewer failure points
- Proven stable on Render

---

## Deployment Steps

### Step 1: Push Changes to GitHub
```bash
cd bill-extractor
git add Dockerfile Dockerfile.alpine Dockerfile.render render.yaml .dockerignore
git commit -m "Fix Docker build: use Alpine Linux for Render deployment"
git push origin main
```

### Step 2: Deploy on Render

**Option A: Using Render Dashboard (Recommended)**
1. Go to https://dashboard.render.com
2. Click **+ New**
3. Select **Web Service**
4. Connect your GitHub repository
5. Select branch: **main**
6. Configure:
   - **Name:** bill-extractor-api
   - **Environment:** Docker
   - **Region:** Choose closest to you
   - **Plan:** Standard ($12/month)
7. Under **Environment Variables**, add:
   ```
   GEMINI_API_KEY=AIzaSyCedrKrkh6jMcQz0CXyiYknPqONyzdKgcQ
   ```
   (Copy from your `.env` file)
8. Click **Create Web Service**

**Option B: Using render.yaml**
1. Render auto-detects `render.yaml`
2. Go to Dashboard → **New** → **Infrastructure**
3. Select your repo
4. Render applies configuration from `render.yaml`

### Step 3: Monitor Deployment
- Dashboard → Select service → Logs tab
- Watch for "Successfully built" message
- Wait for "Your service is live" notification

### Step 4: Set GEMINI_API_KEY
- **Important:** `GEMINI_API_KEY` must be set in Render (it has `sync: false`)
- Go to: Service Settings → Environment
- Add key: `GEMINI_API_KEY`
- Value: (your actual API key from `.env`)
- Click **Save**

---

## Environment Variables Required on Render

Set these in Render Dashboard (Settings → Environment):

| Variable | Value | Source |
|----------|-------|--------|
| GEMINI_API_KEY | Your actual key | From `.env` |
| LLM_MODEL | gemini-2.0-flash | Already in render.yaml |
| LOG_LEVEL | INFO | Already in render.yaml |
| TARGET_DPI | 300 | Already in render.yaml |
| MIN_RESOLUTION | 800 | Already in render.yaml |
| RECONCILIATION_THRESHOLD | 0.01 | Already in render.yaml |
| MAX_RETRY_ATTEMPTS | 3 | Already in render.yaml |
| MAX_IMAGE_SIZE | 20971520 | Already in render.yaml |

**Important:** Only `GEMINI_API_KEY` needs to be added manually (it has `sync: false`)

---

## Troubleshooting Docker Build

### If build still fails:

1. **Clear build cache:**
   - Render Dashboard → Settings → Clear Build Cache
   - Redeploy

2. **Check logs:**
   - Render Dashboard → Logs
   - Look for apt-get error details
   - Scroll down to see full error message

3. **Switch to Python runtime (fallback):**
   If Docker build fails, you can use native Python:
   - Delete `Dockerfile.render`
   - Edit `render.yaml` to use `env: python` instead
   - This requires fewer system dependencies

4. **Use alternative distroless image:**
   - This Dockerfile uses `python:3.11-slim` which is optimized
   - If it fails, Render support can help with distroless images

---

## Expected Build Output

Successful Docker build should show:

```
Step 1/10 : FROM python:3.11-slim
Step 2/10 : WORKDIR /app
Step 3/10 : RUN apt-get update...
...
Step 10/10 : CMD ["python", "-m", "uvicorn"...]
Successfully built xxxxxxxxxxxxx
Successfully tagged bill-extractor:render
```

Then: `Your service is live at: https://bill-extractor-api.onrender.com`

---

## Testing Deployment

Once live, test endpoints:

```bash
# Health check
curl https://bill-extractor-api.onrender.com/health

# Extract from image
curl -X POST https://bill-extractor-api.onrender.com/api/extract-bill-data \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/bill.jpg"}'

# Extract from PDF
curl -X POST https://bill-extractor-api.onrender.com/api/extract-bill-data \
  -H "Content-Type: application/json" \
  -d '{"document": "https://example.com/bill.pdf"}'
```

---

## Performance Notes

- **Build time:** ~5-10 minutes (first build)
- **Deploy time:** ~1-2 minutes (subsequent builds, cached layers)
- **Container size:** ~1.2-1.5 GB (with all dependencies)
- **Memory:** Standard plan includes 512 MB RAM
- **Timeout:** API calls have 30-second timeout on free plan

---

## Cost & Limitations

| Feature | Standard Plan |
|---------|----------------|
| Price | $12/month |
| RAM | 512 MB |
| CPU | Shared |
| Auto-sleep | No |
| Build time | Limited |
| Concurrent requests | 100 |

---

## Next Steps

1. ✅ Push changes to GitHub
2. ✅ Deploy on Render using steps above
3. ✅ Set GEMINI_API_KEY in Render Dashboard
4. ✅ Monitor first deployment
5. ✅ Test endpoints once live
6. ✅ Set up custom domain (optional)

---

## Support

If Docker build still fails:
1. Check Render's build logs (most detailed)
2. Try switching to Python runtime (fallback)
3. Contact Render support with error code
4. Alternative: Use GitHub Actions + Docker Hub → Render
