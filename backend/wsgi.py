#!/usr/bin/env python3
"""
WSGI entry point for production deployment
"""

from server import app, socketio

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=8000, debug=False) 