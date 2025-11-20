// API Configuration
export const API_BASE_URL = 'http://localhost:8001'; // Backend server URL
export const WEBSOCKET_URL = 'http://localhost:8001'; // WebSocket server URL

// API Endpoints
export const API_ENDPOINTS = {
  MQTT_TEST: '/api/mqtt/test',
  MQTT_DISCOVER: '/api/mqtt/discover',
  MQTT_DISCOVERY_STATUS: '/api/mqtt/discovery/status'
};

// Helper function to build full API URL
export const getApiUrl = (endpoint: string): string => {
  return `${API_BASE_URL}${endpoint}`;
}; 