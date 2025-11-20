#!/bin/bash

echo "🚀 Starting MQTT Workflow Editor (Production Mode)"
echo "=================================================="

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Check if virtual environment exists
if [ ! -d "backend/.venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: cd backend && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Build frontend for production
echo "🏗️  Building frontend for production..."
cd frontend
npm run build
cd ..

# Start backend server with gunicorn (using uvicorn workers for FastAPI)
echo "📡 Starting backend server (production) on http://localhost:8000"
cd backend
source .venv/bin/activate
# Note: Requires: pip install gunicorn uvicorn
gunicorn -k uvicorn.workers.UvicornWorker -w 1 --bind 0.0.0.0:8000 wsgi:app &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 3

# Serve built frontend with a simple HTTP server
echo "🌐 Starting frontend server (production) on http://localhost:3001"
npx serve -s frontend/dist -l 3001 &
FRONTEND_PID=$!

echo ""
echo "✅ Production servers started successfully!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3001"
echo ""
echo "Open http://localhost:3001 in your browser to start using the application"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for processes
wait 