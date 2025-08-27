#!/bin/bash

echo "🧪 Testing MQTT Workflow Editor Setup"
echo "===================================="

# Test 1: Check if dependencies are installed
echo "1. Checking Node.js dependencies..."
if [ -d "node_modules" ]; then
    echo "   ✅ Node.js dependencies installed"
else
    echo "   ❌ Node.js dependencies missing"
    exit 1
fi

# Test 2: Check if Python virtual environment exists
echo "2. Checking Python virtual environment..."
if [ -d "backend/.venv" ]; then
    echo "   ✅ Python virtual environment exists"
else
    echo "   ❌ Python virtual environment missing"
    exit 1
fi

# Test 3: Check if Python dependencies are installed
echo "3. Checking Python dependencies..."
cd backend
source .venv/bin/activate
if python -c "import flask, flask_socketio, paho.mqtt" 2>/dev/null; then
    echo "   ✅ Python dependencies installed"
else
    echo "   ❌ Python dependencies missing"
    exit 1
fi
cd ..

# Test 4: Test React build
echo "4. Testing React build..."
if npm run build >/dev/null 2>&1; then
    echo "   ✅ React build successful"
else
    echo "   ❌ React build failed"
    exit 1
fi

# Test 5: Test backend server imports
echo "5. Testing backend server..."
cd backend
source .venv/bin/activate
if python -c "import server; print('Backend imports OK')" >/dev/null 2>&1; then
    echo "   ✅ Backend server imports work"
else
    echo "   ❌ Backend server imports failed"
    exit 1
fi
cd ..

echo ""
echo "🎉 All tests passed! The MQTT Workflow Editor is ready to use."
echo ""
echo "To start the application:"
echo "  Development: ./start.sh"
echo "  Production:  ./start-production.sh"
echo ""
echo "Then open http://localhost:3001 in your browser" 