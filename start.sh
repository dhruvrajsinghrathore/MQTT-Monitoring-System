#!/bin/bash

echo "🚀 Starting MQTT Workflow Editor"
echo "================================"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    kill -9 $(lsof -i :8000)
    kill -9 $(lsof -i :3001)
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

# Start backend server
echo "📡 Starting backend server on http://localhost:8000"
cd backend
source .venv/bin/activate
python server.py &
BACKEND_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Start frontend server
echo "🌐 Starting frontend server on http://localhost:3001"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "✅ Servers started successfully!"
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3001"
echo ""
echo "Open http://localhost:3001 in your browser to start using the application"
echo ""
echo "Press Ctrl+C to stop both servers"

# Wait for processes
wait 