#!/usr/bin/env python3

import socketio
import time
import sys

def test_websocket():
    print("🧪 Testing WebSocket connection to backend...")
    
    # Create a Socket.IO client
    sio = socketio.Client()
    
    @sio.event
    def connect():
        print("✅ WebSocket connected successfully!")
        sio.disconnect()
        
    @sio.event
    def connect_error(data):
        print(f"❌ WebSocket connection failed: {data}")
        
    @sio.event
    def disconnect():
        print("📤 WebSocket disconnected")
    
    try:
        # Try to connect
        sio.connect('http://localhost:8000', wait_timeout=5)
        print("✅ WebSocket test completed successfully!")
        return True
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_websocket()
    sys.exit(0 if success else 1) 