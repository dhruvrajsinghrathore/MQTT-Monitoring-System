// API Configuration
export const API_BASE_URL = 'http://localhost:8001'; // Backend server URL
export const WEBSOCKET_URL = 'http://localhost:8001'; // WebSocket server URL

// API Endpoints
export const API_ENDPOINTS = {
  BASE: '/api',
  MQTT_TEST: '/api/mqtt/test',
  MQTT_DISCOVER: '/api/mqtt/discover',
  MQTT_DISCOVERY_STATUS: '/api/mqtt/discovery/status',

  // Document endpoints
  DOCUMENTS_UPLOAD: '/api/projects/{project_id}/documents/upload',
  DOCUMENTS_LIST: '/api/projects/{project_id}/documents',
  DOCUMENTS_DELETE: '/api/projects/{project_id}/documents/{doc_id}',
  DOCUMENTS_STATS: '/api/projects/{project_id}/documents/stats',

  // Alert endpoints
  ALERTS_CONFIG: '/api/projects/{project_id}/alerts/config',
  ALERTS_CONFIG_THRESHOLD: '/api/projects/{project_id}/alerts/config/threshold',
  ALERTS_ACTIVE: '/api/projects/{project_id}/alerts/active',
  ALERTS_HISTORY: '/api/projects/{project_id}/alerts/history',
  ALERTS_STATS: '/api/projects/{project_id}/alerts/stats',

  // Node endpoints
  NODE_IMAGE: '/api/projects/{project_id}/nodes/{equipment_id}/image'
};

// Helper function to build full API URL
export const getApiUrl = (endpoint: string): string => {
  return `${API_BASE_URL}${endpoint}`;
};

// Helper function to build API URL with parameter replacement
export const getApiUrlWithParams = (endpoint: string, params: Record<string, string>): string => {
  let url = endpoint;
  Object.keys(params).forEach(key => {
    url = url.replace(`{${key}}`, params[key]);
  });
  return `${API_BASE_URL}${url}`;
}; 