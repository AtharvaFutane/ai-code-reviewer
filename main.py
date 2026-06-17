# main.py
"""
FastAPI application entry point.
Run with: uvicorn main:app --reload
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()  # Must be called BEFORE any module that reads env vars

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

logging.basicConfig(
    level=getattr(logging, os.getenv("APP_LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

app = FastAPI(
    title="Infravox AI Code Reviewer",
    description="LangGraph-powered multi-agent PR diff reviewer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
        log_level=os.getenv("APP_LOG_LEVEL", "info").lower(),
    )
