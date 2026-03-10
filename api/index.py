"""
Vercel Serverless Entry Point

This module wraps the FastAPI application for Vercel's Python runtime.
Vercel natively supports ASGI apps — we just need to export the `app` object.
"""

import sys
import os

# Add the backend directory to Python path so imports work
backend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.main import app

# Vercel picks up the `app` variable as the ASGI handler
