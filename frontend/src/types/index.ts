// MQTT Configuration types
export interface MQTTConfig {
  broker_host: string;
  broker_port: number;
  username?: string;
  password?: string;
  topic: string;
  discovery_duration: number; // seconds
}

// Node and Edge types for React Flow
export interface NodeData {
  label: string;
  equipment_id: string;
  equipment_type: string;
  sensors: SensorReading[];
  status: string;
  last_updated: string;
  workflow_step?: string;
  image_url?: string;
}

export interface SensorReading {
  sensor_type: string;
  value: number | string | object;
  unit: string;
  timestamp: string;
}

// Domain Knowledge types
export interface DomainDocument {
  id: string;
  filename: string;
  file_type: string; // 'pdf', 'docx', 'txt', 'md', etc.
  equipment_id?: string; // Optional - if associated with specific equipment
  sensor_type?: string; // Optional - if associated with specific sensor type
  uploaded_at: string;
  file_size: number;
  chunk_count?: number; // Number of chunks after processing
}

// Alert types
export interface AlertThreshold {
  id: string;
  topic_name: string; // e.g., "cell/1/temperature" or just "temperature"
  sensor_type: string;
  min_value?: number;
  max_value?: number;
  enabled: boolean;
  created_at: string;
}

export interface Alert {
  id: string;
  equipment_id: string;
  sensor_type: string;
  topic: string;
  current_value: number;
  threshold_value: number;
  threshold_type: 'min' | 'max';
  severity: 'warning' | 'critical';
  message: string;
  timestamp: string;
  resolved: boolean;
  resolved_at?: string;
}

// Enhanced Project types with persistence
export interface Project {
  id: string;
  name: string;
  description?: string;
  mqtt_config: MQTTConfig;
  discovered_nodes: DiscoveredNode[];
  graph_layout: {
    nodes: any[];
    edges: any[];
  };
  domain_documents?: DomainDocument[];
  alert_thresholds?: AlertThreshold[];
  created_at: string;
  updated_at: string;
  last_accessed?: string;
  is_favorite?: boolean;
}

// Project export format for sharing
export interface ProjectExport {
  project_info: {
    name: string;
    description?: string;
    created_at: string;
    exported_at: string;
    version: string;
  };
  mqtt_config: MQTTConfig;
  graph_schema: {
    nodes: any[];
    edges: any[];
  };
  discovered_nodes: DiscoveredNode[];
}

export interface DiscoveredNode {
  id: string;
  equipment_id: string;
  equipment_type: string;
  topics: string[];
  sample_data: any;
  message_count: number;
  first_seen: string;
  last_seen: string;
  image_url?: string; // Added for node image support
}

// API Response types
export interface DiscoveryResponse {
  discovered_nodes: DiscoveredNode[];
  total_messages: number;
  discovery_duration: number;
  topics_found: string[];
}

export interface LiveDataMessage {
  equipment_id: string;
  sensor_data: SensorReading;
  timestamp: string;
  topic: string;
  raw_data: any;
}

// Storage types
export interface ProjectSummary {
  id: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  last_accessed?: string;
  is_favorite?: boolean;
  node_count: number;
  equipment_types: string[];
  broker_host: string;
} 