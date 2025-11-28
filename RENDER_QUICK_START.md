# 🚀 Deploy to Render - Quick Reference

## TL;DR: 3 Steps to Live API

### 1. Get Gemini API Key
- Visit: https://aistudio.google.com/apikey
- Click "Get API Key"
- Copy the key

### 2. Push to GitHub
```bash
cd bill-extractor
git add .
git commit -m "Ready for Render deployment"
git push origin main
```

### 3. Deploy on Render
1. Go to https://render.com → Sign Up
2. Click **New +** → **Web Service**
3. Connect your GitHub repo
4. Fill in:
   - **Name**: `bill-extractor-api`
   - **Environment**: Python 3
   - **Plan**: Free (or Starter for reliability)
5. Click **Advanced** and add env var:
   - Key: `GEMINI_API_KEY`
   - Value: `[paste your key]`
6. Click **Create Web Service**
7. Wait 3-5 minutes...
8. Your API is live! 🎉

---

## Your API URLs (after deployment)

```
Web:     https://bill-extractor-api.onrender.com
Docs:    https://bill-extractor-api.onrender.com/docs
ReDoc:   https://bill-extractor-api.onrender.com/redoc
Health:  https://bill-extractor-api.onrender.com/health
API:     https://bill-extractor-api.onrender.com/api/extract-bill-data
```

---

## Test It Immediately

```bash
# Health check
curl https://bill-extractor-api.onrender.com/

# View interactive API docs
# Open in browser: https://bill-extractor-api.onrender.com/docs
```

---

## Key Environment Variables

Required:
- `GEMINI_API_KEY` ← GET THIS FROM Google AI Studio

Optional (defaults included):
- `LLM_MODEL` = gemini-2.0-flash
- `LOG_LEVEL` = INFO
- `TARGET_DPI` = 300
- `MIN_RESOLUTION` = 800
- `RECONCILIATION_THRESHOLD` = 0.01
- `MAX_RETRY_ATTEMPTS` = 3

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Build fails | Check build logs, ensure Python 3.11 |
| 502 Bad Gateway | Missing GEMINI_API_KEY, check runtime logs |
| Slow first request | Normal on free tier (cold start), 30-60s |
| Large PDF timeout | Upgrade to Starter plan |

---

## Limitations & Tips

✅ Works great for production
✅ Free tier available
✅ Auto-redeploys on git push
✅ Auto-restarts on failure

⚠️ Free tier: 15 min inactivity = sleep
⚠️ Free tier: ~500MB RAM available
⚠️ First request: 30-60s slower (cold start)

💡 Upgrade to Starter ($7/mo) for:
- Always-on availability
- No cold starts
- Better performance

---

## Full Documentation

See: `RENDER_DEPLOYMENT.md` for complete guide with advanced options

