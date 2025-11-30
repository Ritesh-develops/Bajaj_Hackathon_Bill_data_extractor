"""Main application entry point"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.api import routes
from app.config import API_HOST, API_PORT

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Bill Data Extractor",
    description="Extract line items and totals from bill images using AI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router, prefix="/api", tags=["extraction"])


@app.on_event("startup")
async def startup_event():
    logger.info("Starting Bill Data Extractor API")
    logger.info(f"API will run on {API_HOST}:{API_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Bill Data Extractor API")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Bill Data Extractor API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host=API_HOST,
        port=API_PORT,
        log_level=logging.getLogger().level,
        timeout_keep_alive=120, 
        timeout_notify=120       
    )
