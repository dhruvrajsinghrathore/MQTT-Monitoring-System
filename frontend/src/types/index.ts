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
}

export interface SensorReading {
  sensor_type: string;
  value: number | string | object;
  unit: string;
  timestamp: string;
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