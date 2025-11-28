# Deployment Guide

This guide covers various deployment options for the Bill Data Extractor API.

## Local Development

### Prerequisites
- Python 3.11+
- Google Gemini API Key
- Git

### Setup Steps

1. **Clone repository**
```bash
git clone <repo-url>
cd bill-extractor
```

2. **Create and activate virtual environment**
```bash
# On Windows
python -m venv venv
venv\Scripts\activate

# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

5. **Run tests (optional)**
```bash
pytest tests/ -v
```

6. **Start development server**
```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Access at: http://localhost:8000

## Docker Deployment

### Using Docker Compose (Recommended)

1. **Clone repository**
```bash
git clone <repo-url>
cd bill-extractor
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

3. **Build and run**
```bash
docker-compose up --build
```

4. **Access the API**
```
http://localhost:8000/docs
```

5. **View logs**
```bash
docker-compose logs -f bill-extractor
```

6. **Stop services**
```bash
docker-compose down
```

### Manual Docker Setup

1. **Build image**
```bash
docker build -t bill-extractor:latest .
```

2. **Run container**
```bash
docker run -d \
  --name bill-extractor \
  -p 8000:8000 \
  -e GEMINI_API_KEY=your_key_here \
  -e LOG_LEVEL=INFO \
  bill-extractor:latest
```

3. **View logs**
```bash
docker logs -f bill-extractor
```

4. **Stop container**
```bash
docker stop bill-extractor
docker rm bill-extractor
```

## Cloud Deployment

### Google Cloud Run

1. **Install Cloud SDK**
```bash
# Download from: https://cloud.google.com/sdk/docs/install
```

2. **Authenticate**
```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
```

3. **Deploy**
```bash
gcloud run deploy bill-extractor \
  --source . \
  --platform managed \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=your_key_here \
  --allow-unauthenticated
```

### AWS EC2

1. **Launch EC2 instance** (Ubuntu 22.04)

2. **Connect to instance**
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

3. **Install dependencies**
```bash
sudo apt-get update
sudo apt-get install -y python3.11 python3-pip docker.io docker-compose

# Add user to docker group
sudo usermod -aG docker ubuntu
```

4. **Clone and deploy**
```bash
git clone <repo-url>
cd bill-extractor
docker-compose up -d
```

### Azure Container Instances

1. **Install Azure CLI**
```bash
# Download from: https://learn.microsoft.com/cli/azure/
```

2. **Login**
```bash
az login
```

3. **Create resource group**
```bash
az group create --name bill-extractor-rg --location eastus
```

4. **Deploy container**
```bash
az container create \
  --resource-group bill-extractor-rg \
  --name bill-extractor \
  --image bill-extractor:latest \
  --cpu 2 --memory 2 \
  --ports 8000 \
  --environment-variables GEMINI_API_KEY=your_key_here \
  --dns-name-label bill-extractor-api
```

## Environment Variables

Required for all deployments:
```
GEMINI_API_KEY=your_gemini_api_key
```

Optional (defaults provided):
```
API_HOST=0.0.0.0
API_PORT=8000
LLM_MODEL=gemini-2.0-flash
TARGET_DPI=300
MIN_RESOLUTION=800
RECONCILIATION_THRESHOLD=0.01
MAX_RETRY_ATTEMPTS=3
LOG_LEVEL=INFO
```

## Performance Optimization

### For High Traffic

1. **Increase worker processes**
```bash
# In docker-compose.yml or run command
python -m uvicorn app.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --loop uvloop
```

2. **Add load balancer**
- Use Nginx reverse proxy
- Configure caching headers
- Set up health checks

3. **Enable caching**
- Redis for processed image cache
- API response caching

### Memory Optimization

- Default: ~500MB per instance
- With heavy images: ~1GB recommended
- Adjust MIN_RESOLUTION if needed

## Monitoring & Logging

### Log Levels

```
ERROR   - Critical issues only
WARNING - Warnings and errors
INFO    - General operation info
DEBUG   - Detailed debug information
```

Set via `LOG_LEVEL` environment variable.

### Health Check

All deployments include `/health` endpoint:
```bash
curl http://localhost:8000/health
```

### Metrics to Monitor

- API response time
- Error rate (extraction failures)
- Reconciliation accuracy
- Gemini API quota usage
- Memory usage

## Scaling

### Horizontal Scaling (Recommended)

1. **Docker Swarm**
```bash
docker swarm init
docker stack deploy -c docker-compose.yml bill-extractor
```

2. **Kubernetes**
```bash
kubectl apply -f k8s-deployment.yaml
```

### Vertical Scaling

Increase instance resources in cloud provider settings.

## Troubleshooting

### Issue: API won't start
```bash
# Check logs
docker-compose logs bill-extractor

# Verify environment variables
docker-compose config

# Check port availability
netstat -an | grep 8000
```

### Issue: Gemini API errors
- Verify API key is correct
- Check quota usage in Google Cloud Console
- Review rate limits

### Issue: Out of memory
- Reduce MIN_RESOLUTION
- Enable image compression
- Increase instance memory

### Issue: Slow extraction
- Check network connectivity to Gemini API
- Monitor instance CPU/memory
- Review image file sizes
- Consider enabling caching

## Backup & Recovery

### Database (if using persistence)
```bash
# Backup
docker exec bill-extractor tar -czf backup.tar.gz /app/data/

# Restore
docker cp backup.tar.gz bill-extractor:/app/
docker exec bill-extractor tar -xzf backup.tar.gz
```

### Configuration
- Keep `.env` files backed up
- Version control Dockerfile
- Document custom modifications

## Security

### For Production

1. **Use HTTPS**
- Deploy behind reverse proxy (Nginx, CloudFlare)
- Enable SSL certificates

2. **Restrict Access**
- Use API keys/authentication
- Implement rate limiting
- Add IP whitelisting if possible

3. **Secure Secrets**
- Use cloud secret managers (AWS Secrets Manager, Azure Key Vault)
- Never commit `.env` files
- Rotate API keys regularly

4. **Network**
- Run in private VPC
- Use security groups/firewalls
- Enable VPN if needed

## Support

For deployment issues:
1. Check logs: `docker-compose logs -f`
2. Verify configuration: `docker-compose config`
3. Test API: `curl http://localhost:8000/health`
4. Review error messages carefully

---

**Last Updated**: November 2025
**Version**: 1.0.0
