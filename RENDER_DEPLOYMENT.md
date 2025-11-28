# Render Deployment Guide

## Quick Start: Deploy to Render in 5 Minutes

### Prerequisites
- GitHub account with your code pushed to a repository
- Render account (free at https://render.com)
- Gemini API key from Google AI Studio

### Step 1: Prepare Your Repository

1. Ensure all your code is committed and pushed to GitHub:
```bash
cd bill-extractor
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

2. Verify `requirements.txt` is in the root directory (it should be there)

3. Verify `render.yaml` exists in the root directory (we just created it)

### Step 2: Connect GitHub to Render

1. Go to https://render.com
2. Click **Sign Up** or **Sign In**
3. Click **New +** → **Web Service**
4. Click **Connect a repository**
5. Select **GitHub** as the provider
6. Authorize Render to access your GitHub account
7. Select the repository `Bajaj_Hackathon_Bill_data_extractor` (or your fork)
8. Click **Connect**

### Step 3: Configure the Deployment

1. **Name**: `bill-extractor-api` (or your preferred name)
2. **Environment**: Select **Python 3** from the dropdown
3. **Build Command**: Leave blank (will use render.yaml)
4. **Start Command**: Leave blank (will use render.yaml)
5. **Plan**: Select **Free** (for testing) or **Starter** (for production)

### Step 4: Set Environment Variables

1. Click **Advanced** section
2. Click **Add Environment Variable** and add the following:

```
GEMINI_API_KEY = your_actual_gemini_api_key_here
LLM_MODEL = gemini-2.0-flash
API_HOST = 0.0.0.0
LOG_LEVEL = INFO
TARGET_DPI = 300
MIN_RESOLUTION = 800
RECONCILIATION_THRESHOLD = 0.01
MAX_RETRY_ATTEMPTS = 3
MAX_IMAGE_SIZE = 20971520
```

**Important**: Get your Gemini API key from:
- Go to https://aistudio.google.com/apikey
- Click **Get API Key**
- Create a new API key or use existing one
- Copy and paste it into the `GEMINI_API_KEY` field

### Step 5: Deploy

1. Click **Create Web Service**
2. Render will automatically:
   - Clone your repository
   - Install dependencies from `requirements.txt`
   - Start the application with the command in `render.yaml`
   - Assign a public URL like `https://bill-extractor-api.onrender.com`

3. Wait 3-5 minutes for deployment to complete
4. Check the deployment logs for any errors

### Step 6: Test Your Deployment

Once deployment is complete:

1. **Health Check**:
   ```bash
   curl https://bill-extractor-api.onrender.com/
   ```
   Should return:
   ```json
   {"message": "Bill Data Extractor API", "version": "1.0.0", "docs": "/docs"}
   ```

2. **View API Documentation**:
   - Swagger UI: `https://bill-extractor-api.onrender.com/docs`
   - ReDoc: `https://bill-extractor-api.onrender.com/redoc`

3. **Test Extraction Endpoint**:
   ```bash
   curl -X POST https://bill-extractor-api.onrender.com/api/extract-bill-data \
     -H "Content-Type: application/json" \
     -d '{
       "document": "https://example.com/bill.jpg"
     }'
   ```

---

## Important Notes for Render

### Cold Starts
- Free tier services spin down after 15 minutes of inactivity
- First request after shutdown takes 30-60 seconds to respond
- Use Starter plan ($7/month) for guaranteed uptime

### Resource Limits
- **Free tier**: 0.5GB RAM, no persistent storage
- **Starter plan**: 2GB RAM, persistent storage available
- Our app needs ~500MB RAM for Gemini API and image processing

### PDF Support on Render
- `pdf2image` requires `poppler-utils` system dependency
- This is installed automatically via `Dockerfile` (if used)
- If issues occur, Render provides build logs to diagnose

### File Size Limits
- Max upload: 20MB (set in `MAX_IMAGE_SIZE`)
- Render has no built-in file size limit for requests
- Consider adding nginx reverse proxy for large files

### Deployment Method Options

#### Option A: Using render.yaml (Recommended)
- Render automatically reads `render.yaml` configuration
- No additional setup needed
- Already created in your repo

#### Option B: Manual Configuration on Render Dashboard
1. Skip the `render.yaml` step above
2. Manually enter build and start commands:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

---

## Troubleshooting

### Deployment Fails
**Check build logs:**
1. Go to your service on Render
2. Click **Logs** tab
3. Look for errors in build or runtime logs

**Common issues:**
- Missing `GEMINI_API_KEY`: Will fail at runtime
- PDF dependency issues: Install `poppler-utils` system package
- Python version mismatch: Ensure Python 3.11+

### API Returns 502 Bad Gateway
- Service crashed during startup
- Check logs: **Logs** → **Runtime Logs**
- Likely cause: Missing API key or dependency issue

### Slow Response Times
- First request takes 30+ seconds on free tier (cold start)
- Subsequent requests are fast
- Upgrade to Starter plan for guaranteed availability

### Large PDF Processing Fails
- Render may timeout on very large files (>50MB)
- Split large PDFs before uploading
- Increase timeout in load balancer (contact Render support)

---

## Advanced: Custom Domain

1. Go to your service on Render
2. Click **Settings**
3. Scroll to **Custom Domain**
4. Enter your domain (e.g., `api.yourdomain.com`)
5. Add CNAME record to your DNS provider pointing to Render URL
6. Wait 24 hours for DNS propagation

---

## Monitoring & Maintenance

### View Logs
- **Runtime Logs**: Service output and errors
- **Build Logs**: Build process output
- Access via **Logs** tab on service page

### Auto-Deploy from GitHub
- Every push to `main` branch triggers automatic deployment
- Disable in **Settings** → **Auto-Deploy** if needed

### Manual Redeploy
1. Go to service on Render
2. Click **Manual Deploy** → **Deploy latest commit**

### Update Environment Variables
1. Go to **Environment**
2. Edit the variable
3. Click **Save Changes**
4. Service automatically redeploys

---

## Cost Estimation

| Plan | Price | Use Case |
|------|-------|----------|
| Free | $0 | Development, Testing (cold starts) |
| Starter | $7/month | Small production deployments |
| Standard | $25/month | Production with guaranteed uptime |

Our app runs comfortably on **Starter** plan.

---

## Next Steps

1. **Push code to GitHub**: Ensure latest changes are committed
2. **Get Gemini API key**: From https://aistudio.google.com/apikey
3. **Create Render account**: At https://render.com
4. **Deploy**: Follow **Step 1-5** above
5. **Test**: Verify API is working via `/docs` endpoint
6. **Share URL**: Your API is now publicly accessible!

**Public URL format**: `https://<service-name>.onrender.com`

Example: `https://bill-extractor-api.onrender.com/docs`

