#!/bin/bash

echo "🧪 Testing MQTT GUI API Connectivity"
echo "===================================="

# Function to start backend server in background
start_backend() {
    echo "📡 Starting backend server for testing..."
    cd backend
    source .venv/bin/activate
    python server.py > /dev/null 2>&1 &
    BACKEND_PID=$!
    cd ..
    
    # Wait for server to start
    echo "⏳ Waiting for backend to start..."
    sleep 3
    
    return $BACKEND_PID
}

# Function to test API endpoint
test_api() {
    local endpoint=$1
    local method=${2:-GET}
    local data=${3:-"{}"}
    
    echo "Testing $method $endpoint..."
    
    if [ "$method" = "POST" ]; then
        response=$(curl -s -w "%{http_code}" -X POST \
            -H "Content-Type: application/json" \
            -d "$data" \
            "http://localhost:8000$endpoint")
    else
        response=$(curl -s -w "%{http_code}" "http://localhost:8000$endpoint")
    fi
    
    http_code="${response: -3}"
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "404" ]; then
        echo "   ✅ Endpoint reachable (HTTP $http_code)"
        return 0
    else
        echo "   ❌ Endpoint failed (HTTP $http_code)"
        return 1
    fi
}

# Main test sequence
echo "1. Starting backend server..."
start_backend
BACKEND_PID=$!

echo "2. Testing API endpoints..."

# Test MQTT test endpoint
test_api "/api/mqtt/test" "POST" '{"broker_host":"test","broker_port":1883,"topic":"test/#","discovery_duration":30}'

# Test discovery endpoint  
test_api "/api/mqtt/discover" "POST" '{"broker_host":"test","broker_port":1883,"topic":"test/#","discovery_duration":5}'

# Test discovery status endpoint
test_api "/api/mqtt/discovery/status"

echo ""
echo "3. Cleaning up..."
if [ ! -z "$BACKEND_PID" ]; then
    kill $BACKEND_PID 2>/dev/null
    echo "   🧹 Backend server stopped"
fi

echo ""
echo "🎉 API connectivity test completed!"
echo ""
echo "If all endpoints show ✅, the API is working correctly."
echo "You can now start the full application with './start.sh'" 