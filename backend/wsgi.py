#!/usr/bin/env python3
"""
WSGI/ASGI entry point for production deployment
Exports FastAPI app for use with Gunicorn + Uvicorn workers
"""

from server import app

# For Gunicorn: gunicorn -k uvicorn.workers.UvicornWorker wsgi:app
# For direct run: python wsgi.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000) 