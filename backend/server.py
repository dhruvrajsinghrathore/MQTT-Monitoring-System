#!/usr/bin/env python3

import asyncio
import csv
import io
import json
import logging
import threading
import time
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database_service import db
from alert_service import alert_service
from vectorstore_service import vector_store
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Add the parent directory to Python path to import from Scenario_2
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '../../Scenario_2'))

try:
    from dynamic_workflow_subscriber import AdaptiveSchemaLearner
except ImportError as e:
    print(f"Warning: Could not import AdaptiveSchemaLearner: {e}")
    AdaptiveSchemaLearner = None

# Add this after the imports, before the FastAPI app definition

class GraphDataManager:
    """Manages graph data and builds complete node structures with sensor data"""
    
    def __init__(self):
        self.nodes_data = {}  # {equipment_id: node_data}
        self.sensor_data = {}  # {equipment_id: {sensor_type: sensor_reading}}
        self.project = None
        self.last_update_time = 0  # Throttling
        self.update_interval = 0.5  # Send updates max every 500ms
        
    def set_project(self, project):
        """Set the current project and initialize nodes from project data"""
        self.project = project

        # ALWAYS clear existing data when setting a new project
        self.nodes_data = {}
        self.sensor_data = {}

        # Set up alert thresholds for the project
        if project and project.get('alert_thresholds'):
            alert_service.set_project_thresholds(project.get('id', ''), project['alert_thresholds'])

        if project and project.get('graph_layout', {}).get('nodes'):
            logger.info(f"🔍 GraphDataManager initializing with {len(project['graph_layout']['nodes'])} nodes from project")
            for node in project['graph_layout']['nodes']:
                equipment_id = node['data']['equipment_id']
                logger.info(f"🔍 Initializing node: {equipment_id}")
                self.nodes_data[equipment_id] = {
                    'id': node['id'],
                    'type': 'custom',
                    'position': node['position'],
                    'data': {
                        **node['data'],
                        'sensors': [],
                        'status': 'idle',
                        'last_updated': None
                    }
                }
                self.sensor_data[equipment_id] = {}

            logger.info(f"🔍 GraphDataManager initialized with nodes: {list(self.nodes_data.keys())}")
        else:
            logger.info("🔍 No graph layout nodes found in project")
    
    def update_sensor_data(self, equipment_id: str, sensor_type: str, sensor_reading: dict):
        """Update sensor data for a specific equipment and sensor type"""
        # Only process equipment that exists in the project's graph layout
        if equipment_id not in self.sensor_data:
            logger.debug(f"🔍 Equipment {equipment_id} not in sensor_data, checking if it's in graph layout")
            
            # Check if this equipment is in the project's graph layout
            if not self.project or not self.project.get('graph_layout', {}).get('nodes'):
                logger.debug(f"🔍 No project or graph layout, skipping {equipment_id}")
                return  # No project or no graph layout, skip
            
            # Check if this equipment_id is in the graph layout
            equipment_in_layout = any(
                node['data']['equipment_id'] == equipment_id 
                for node in self.project['graph_layout']['nodes']
            )
            
            if not equipment_in_layout:
                logger.debug(f"🔍 Equipment {equipment_id} not in graph layout, skipping")
                return  # Equipment not in graph layout, skip
            
            logger.debug(f"🔍 Equipment {equipment_id} is in graph layout, creating node")
            
            # Find the original node data from the graph layout
            original_node = next(
                node for node in self.project['graph_layout']['nodes']
                if node['data']['equipment_id'] == equipment_id
            )
            
            # Create a new node using the original node data
            self.nodes_data[equipment_id] = {
                'id': original_node['id'],
                'type': 'custom',
                'position': original_node['position'],
                'data': {
                    **original_node['data'],
                    'sensors': [],
                    'status': 'idle',
                    'last_updated': None
                }
            }
            self.sensor_data[equipment_id] = {}
        
        # Update sensor data
        self.sensor_data[equipment_id][sensor_type] = sensor_reading
        
        # Rebuild sensors array for the node
        sensors = []
        for stype, sreading in self.sensor_data[equipment_id].items():
            sensors.append({
                'sensor_type': stype,
                'value': sreading.get('value', 0),
                'unit': sreading.get('unit', ''),
                'timestamp': sreading.get('timestamp'),
                'status': sreading.get('status', 'active')
            })
        
        # Update node data
        self.nodes_data[equipment_id]['data']['sensors'] = sensors
        self.nodes_data[equipment_id]['data']['status'] = 'active' if sensors else 'idle'
        self.nodes_data[equipment_id]['data']['last_updated'] = datetime.now().isoformat()
    
    def should_send_update(self):
        """Check if enough time has passed to send an update"""
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_interval:
            self.last_update_time = current_time
            return True
        return False
    
    def get_graph_data(self):
        """Get complete graph data with all nodes and their sensor data"""
        nodes = list(self.nodes_data.values())
        edges = []
        
        # Get edges from project if available
        if self.project and self.project.get('graph_layout', {}).get('edges'):
            edges = self.project['graph_layout']['edges']
        
        logger.debug(f"🔍 GraphDataManager sending {len(nodes)} nodes: {[n['id'] for n in nodes]}")
        
        return {
            'nodes': nodes,
            'edges': edges,
            'last_updated': datetime.now().isoformat(),
            'first_message': len(nodes) > 0
        }

# Create global graph data manager
graph_manager = GraphDataManager()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="MQTT GUI Backend", version="1.0.0")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class MQTTConfig(BaseModel):
    broker_host: str
    broker_port: int
    topic: str
    username: Optional[str] = None
    password: Optional[str] = None

class DiscoveredNode(BaseModel):
    id: str
    equipment_id: str
    equipment_type: str
    topics: List[str]
    sample_data: Optional[Dict[str, Any]] = None
    message_count: int = 0
    first_seen: str
    last_seen: str

# Global state
current_discovery: Optional['MQTTDiscovery'] = None
current_monitoring: Optional['MQTTMonitoring'] = None
discovered_nodes: List[DiscoveredNode] = []
connected_websockets: List[WebSocket] = []

# Event loop for handling async tasks from sync contexts
main_loop: Optional[asyncio.AbstractEventLoop] = None

class MQTTDiscovery:
    """Handles MQTT topic discovery"""
    
    def __init__(self, config: MQTTConfig):
        self.config = config
        self.client = None
        self.is_running = False
        self.discovered_data = {}
        self.schema_learner = AdaptiveSchemaLearner() if AdaptiveSchemaLearner else None
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker for discovery")
            # Validate topic before subscribing
            topic = self.config.topic.strip() if self.config.topic else ""
            if not topic:
                logger.error(f"No topic pattern provided. Using default '#' to subscribe to all topics")
                topic = "#"
            elif topic.startswith('/') or topic.endswith('/'):
                # Clean up topic pattern
                topic = topic.strip('/')
                logger.warning(f"Cleaned topic pattern: '{topic}'")
            client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if self.schema_learner:
                # Use the adaptive schema learner to analyze the message
                analyzed = self.schema_learner.analyze_message(payload, topic)
                equipment_id = analyzed.get('equipment_id', 'unknown')
                sensor_type = analyzed.get('sensor_type', 'unknown')
                
                if equipment_id != 'unknown' and sensor_type != 'unknown':
                    key = f"{equipment_id}_{sensor_type}"
                    self.discovered_data[key] = {
                        'equipment_id': equipment_id,
                        'sensor_type': sensor_type,
                        'topic': topic,
                        'last_seen': datetime.now().isoformat(),
                        'sample_data': payload
                    }
                    logger.debug(f"Discovered: {equipment_id} / {sensor_type} on topic {topic}")
            else:
                logger.warning("AdaptiveSchemaLearner not available for discovery")
            
        except Exception as e:
            logger.error(f"Error processing discovery message: {e}")
    

    
    def start(self):
        try:
            self.client = mqtt.Client()
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)
            
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            
            self.client.connect(self.config.broker_host, self.config.broker_port, 60)
            self.is_running = True
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to start MQTT discovery: {e}")
            raise
    
    def stop(self):
        if self.client and self.is_running:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_running = False
    
    def get_discovered_nodes(self) -> List[DiscoveredNode]:
        # Group by equipment_id to create equipment-based nodes
        equipment_groups = {}
        
        for data in self.discovered_data.values():
            equipment_id = data['equipment_id']
            
            if equipment_id not in equipment_groups:
                equipment_groups[equipment_id] = {
                    'equipment_id': equipment_id,
                    'equipment_type': data['sensor_type'],  # Use first sensor type as equipment type
                    'topics': [],
                    'sample_data': data['sample_data'],
                    'message_count': 0,
                    'first_seen': data['last_seen'],
                    'last_seen': data['last_seen']
                }
            
            # Update the group data
            group = equipment_groups[equipment_id]
            if data['topic'] not in group['topics']:
                group['topics'].append(data['topic'])
            group['message_count'] += 1
            group['last_seen'] = max(group['last_seen'], data['last_seen'])
            group['first_seen'] = min(group['first_seen'], data['last_seen'])
            
            # Dynamically infer equipment type from equipment_id or topic structure
            if '_' in equipment_id:
                # Extract the base name from equipment_id (e.g., "cell_1" -> "cell", "lab_furnace01" -> "lab")
                equipment_base = equipment_id.split('_')[0].lower()
            else:
                # Use the root topic as equipment type for single-level equipment IDs
                topic_parts = data['topic'].split('/')
                equipment_base = topic_parts[0].lower() if topic_parts else equipment_id.lower()
            group['equipment_type'] = equipment_base
        
        # Convert to DiscoveredNode objects
        nodes = []
        for group in equipment_groups.values():
            nodes.append(DiscoveredNode(
                id=f"node_{group['equipment_id']}",
                equipment_id=group['equipment_id'],
                equipment_type=group['equipment_type'],
                topics=group['topics'],
                sample_data=group['sample_data'],
                message_count=group['message_count'],
                first_seen=group['first_seen'],
                last_seen=group['last_seen']
            ))
        
        return nodes

class MQTTMonitoring:
    """Handles MQTT monitoring for live data"""
    
    def __init__(self, config: MQTTConfig):
        self.config = config
        self.client = None
        self.is_running = False
        self.schema_learner = AdaptiveSchemaLearner() if AdaptiveSchemaLearner else None
        self.current_session_id = None
        self.project_id = None
        
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info(f"Connected to MQTT broker for monitoring")
            # Validate topic before subscribing
            topic = self.config.topic.strip() if self.config.topic else ""
            if not topic:
                logger.error(f"No topic pattern provided. Using default '#' to subscribe to all topics")
                topic = "#"
            elif topic.startswith('/') or topic.endswith('/'):
                # Clean up topic pattern
                topic = topic.strip('/')
                logger.warning(f"Cleaned topic pattern: '{topic}'")
            client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode())
            
            if self.schema_learner:
                # Extract data using schema learner
                analyzed = self.schema_learner.analyze_message(payload, topic)
                equipment_id = analyzed.get('equipment_id', 'unknown')
                sensor_type = analyzed.get('sensor_type', 'unknown')
                value = analyzed.get('value')
                status = analyzed.get('status', 'active')
            else:
                logger.warning("AdaptiveSchemaLearner not available for monitoring")
                equipment_id = 'unknown'
                sensor_type = 'unknown'
                value = payload.get('value', 0)
                status = payload.get('status', 'active')
            
            if equipment_id != 'unknown':
                # Get unit from payload or schema learner
                unit = payload.get('unit', '')
                if not unit and 'field' in payload:
                    # Extract unit from field name (e.g., "temperature_C" -> "C")
                    field = payload.get('field', '')
                    if '_' in field:
                        unit = field.split('_')[-1]
                
                # Update graph manager with sensor data
                sensor_reading = {
                    'value': value,
                    'unit': unit,
                    'status': status,
                    'timestamp': datetime.now().isoformat(),
                    'topic': topic,
                    'raw_payload': payload
                }
                
                graph_manager.update_sensor_data(equipment_id, sensor_type, sensor_reading)

                # Evaluate sensor reading against alert thresholds
                alert = alert_service.evaluate_sensor_reading(
                    equipment_id, sensor_type, value, topic,
                    datetime.now().isoformat(), self.project_id or ''
                )

                # Only send graph updates if enough time has passed (throttling)
                if graph_manager.should_send_update():
                    graph_data = graph_manager.get_graph_data()
                    message = {
                        'type': 'graph_update',
                        'data': graph_data
                    }

                    # Send to all connected WebSocket clients - use thread-safe approach
                    if main_loop and not main_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(broadcast_to_websockets(message), main_loop)

                # Send alert updates immediately (not throttled)
                if alert:
                    alert_message = {
                        'type': 'alert_update',
                        'data': alert
                    }

                    # Send alert to all connected WebSocket clients
                    if main_loop and not main_loop.is_closed():
                        asyncio.run_coroutine_threadsafe(broadcast_to_websockets(alert_message), main_loop)
                    
                # Store message in database if session is active
                if self.current_session_id and self.project_id:
                    try:
                        db.store_message(self.project_id, self.current_session_id, {
                            'equipment_id': equipment_id,
                            'sensor_type': sensor_type,
                            'value': value,
                            'status': status,
                            'timestamp': datetime.now().isoformat(),
                            'topic': topic,
                            'raw_payload': payload
                        })
                    except Exception as e:
                        logger.error(f"Failed to store message in database: {e}")
            
        except Exception as e:
            logger.error(f"Error processing monitoring message: {e}")
    

    
    def start(self):
        try:
            self.client = mqtt.Client()
            if self.config.username and self.config.password:
                self.client.username_pw_set(self.config.username, self.config.password)
            
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message
            
            self.client.connect(self.config.broker_host, self.config.broker_port, 60)
            self.is_running = True
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to start MQTT monitoring: {e}")
            raise
    
    def start_recording_session(self, project_id: str, project_name: str) -> str:
        """Start a new recording session for this monitoring instance"""
        self.project_id = project_id
        self.current_session_id = db.start_session(project_id, project_name)
        logger.info(f"Started recording session {self.current_session_id} for project {project_name}")
        return self.current_session_id
    
    def stop_recording_session(self):
        """Stop the current recording session"""
        if self.current_session_id and self.project_id:
            db.stop_session(self.project_id, self.current_session_id)
            logger.info(f"Stopped recording session {self.current_session_id}")
            self.current_session_id = None
            self.project_id = None

    def stop(self):
        # Stop recording session if active
        self.stop_recording_session()
        
        if self.client and self.is_running:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_running = False

async def broadcast_to_websockets(message: dict):
    """Broadcast message to all connected WebSocket clients"""
    if connected_websockets:
        disconnected = []
        for websocket in connected_websockets:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to WebSocket: {e}")
                disconnected.append(websocket)
        
        # Remove disconnected WebSockets
        for ws in disconnected:
            connected_websockets.remove(ws)

# API Routes
@app.post("/api/mqtt/test")
async def test_mqtt_connection(config: MQTTConfig):
    """Test MQTT broker connection"""
    try:
        client = mqtt.Client()
        if config.username and config.password:
            client.username_pw_set(config.username, config.password)
        
        # Test connection
        result = client.connect(config.broker_host, config.broker_port, 60)
        client.disconnect()
        
        if result == 0:
            return {"status": "success", "message": "Connected to MQTT broker successfully"}
        else:
            raise HTTPException(status_code=400, detail=f"Failed to connect to MQTT broker (code: {result})")
            
    except Exception as e:
        logger.error(f"MQTT connection test failed: {e}")
        raise HTTPException(status_code=400, detail=f"Connection failed: {str(e)}")

@app.post("/api/mqtt/discover")
async def start_mqtt_discovery(config: MQTTConfig):
    """Start MQTT topic discovery"""
    global current_discovery, discovered_nodes
    
    try:
        # Stop existing discovery
        if current_discovery:
            current_discovery.stop()
        
        # Start new discovery
        current_discovery = MQTTDiscovery(config)
        current_discovery.start()
        discovered_nodes = []
        
        return {"status": "success", "message": "MQTT discovery started"}
        
    except Exception as e:
        logger.error(f"Failed to start MQTT discovery: {e}")
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")

@app.get("/api/mqtt/discovery/status")
async def get_discovery_status():
    """Get current discovery status and discovered nodes"""
    global current_discovery, discovered_nodes
    
    if current_discovery and current_discovery.is_running:
        discovered_nodes = current_discovery.get_discovered_nodes()
        return {
            "status": "running",
            "discovered_nodes": [node.model_dump() for node in discovered_nodes],
            "count": len(discovered_nodes)
        }
    else:
        return {
            "status": "stopped",
            "discovered_nodes": [node.dict() for node in discovered_nodes],
            "count": len(discovered_nodes)
        }

@app.post("/api/mqtt/discovery/stop")
async def stop_mqtt_discovery():
    """Stop MQTT discovery"""
    global current_discovery, discovered_nodes
    
    if current_discovery:
        current_discovery.stop()
        current_discovery = None
    
    # Clear the discovered nodes cache
    discovered_nodes = []
    
    return {"status": "success", "message": "MQTT discovery stopped"}

@app.post("/api/mqtt/discovery/clear")
async def clear_discovered_nodes():
    """Clear the discovered nodes cache"""
    global discovered_nodes
    
    discovered_nodes = []
    
    return {"status": "success", "message": "Discovered nodes cache cleared"}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_websockets.append(websocket)
    logger.info(f"WebSocket client connected. Total clients: {len(connected_websockets)}")
    
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get('type') == 'start_monitoring':
                # Start MQTT monitoring
                global current_monitoring
                config_data = message.get('config')
                session_info = message.get('session_info')
                project_data = message.get('project')
                
                if config_data:
                    config = MQTTConfig(**config_data)
                    
                    # Initialize graph manager with project data
                    if project_data:
                        graph_manager.set_project(project_data)
                        logger.info(f"📊 Initialized graph manager with project: {project_data.get('name', 'Unknown')}")
                    
                    # Stop existing monitoring
                    if current_monitoring:
                        current_monitoring.stop()
                    
                    # Start new monitoring
                    current_monitoring = MQTTMonitoring(config)
                    current_monitoring.start()
                    
                    # Start recording session if session info provided
                    if session_info and session_info.get('session_id'):
                        project_id = session_info.get('project_id')
                        project_name = session_info.get('project_name')
                        session_id = session_info.get('session_id')
                        
                        # Set the session in the monitoring instance
                        current_monitoring.project_id = project_id
                        current_monitoring.current_session_id = session_id
                        
                        logger.info(f"🎬 Backend monitoring linked to recording session: {session_id}")
                    
                    await websocket.send_text(json.dumps({
                        'type': 'monitoring_started',
                        'message': 'MQTT monitoring started successfully',
                        'recording_session': session_info.get('session_id') if session_info else None
                    }))
            
            elif message.get('type') == 'stop_monitoring':
                # Stop MQTT monitoring
                if current_monitoring:
                    current_monitoring.stop()
                    current_monitoring = None
                
                await websocket.send_text(json.dumps({
                    'type': 'monitoring_stopped',
                    'message': 'MQTT monitoring stopped'
                }))
                
    except WebSocketDisconnect:
        connected_websockets.remove(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(connected_websockets)}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if websocket in connected_websockets:
            connected_websockets.remove(websocket)

# Database API Endpoints
@app.post("/api/database/session/start")
async def start_recording_session(request: dict):
    """Start a new message recording session"""
    try:
        project_id = request.get('project_id')
        project_name = request.get('project_name')
        
        if not project_id or not project_name:
            raise HTTPException(status_code=400, detail="project_id and project_name are required")
        
        session_id = db.start_session(project_id, project_name)
        return {"session_id": session_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/database/session/stop")
async def stop_recording_session(request: dict):
    """Stop a recording session"""
    try:
        project_id = request.get('project_id')
        session_id = request.get('session_id')
        
        if not project_id or not session_id:
            raise HTTPException(status_code=400, detail="project_id and session_id are required")
        
        db.stop_session(project_id, session_id)
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/database/message/store")
async def store_message(request: dict):
    """Store a new MQTT message"""
    try:
        project_id = request.get('project_id')
        session_id = request.get('session_id')
        message_data = request.get('message_data')
        
        if not all([project_id, session_id, message_data]):
            raise HTTPException(status_code=400, detail="project_id, session_id, and message_data are required")
        
        db.store_message(project_id, session_id, message_data)
        return {"status": "stored"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/messages/{project_id}")
async def get_project_messages(project_id: str, limit: Optional[int] = None):
    """Get all messages for a project"""
    try:
        messages = db.get_messages_for_project(project_id, limit)
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/messages/{project_id}/{equipment_id}")
async def get_equipment_messages(project_id: str, equipment_id: str, limit: Optional[int] = None):
    """Get messages for specific equipment"""
    try:
        messages = db.get_messages_for_equipment(project_id, equipment_id, limit)
        return {"messages": messages, "count": len(messages)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/sessions/{project_id}")
async def get_project_sessions(project_id: str):
    """Get all sessions for a project"""
    try:
        sessions = db.get_sessions_for_project(project_id)
        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/export/{project_id}")
async def export_project_data(project_id: str):
    """Export all data for a project"""
    try:
        data = db.export_project_data(project_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/database/import")
async def import_project_data(request: dict):
    """Import project data"""
    try:
        data = request.get('data')
        if not data:
            raise HTTPException(status_code=400, detail="data is required")
        
        project_id = db.import_project_data(data)
        return {"project_id": project_id, "status": "imported"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/database/project/{project_id}")
async def delete_project_data(project_id: str):
    """Delete all data for a project"""
    try:
        db.delete_project_data(project_id)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/stats")
async def get_storage_stats():
    """Get storage statistics"""
    try:
        stats = db.get_storage_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chatbot API Endpoints
@app.post("/api/chatbot/query")
async def chatbot_query(request: dict):
    """Process chatbot query with CrewAI"""
    try:
        from crewai_service import crewai_service
        
        user_query = request.get('query', '')
        page_type = request.get('page_type', 'monitor')  # 'monitor' or 'equipment'
        cell_id = request.get('cell_id', None)
        references = request.get('references', [])  # Get @ references from frontend
        project_id = request.get('project_id', None)  # Get project_id from frontend
        
        if not user_query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Process query with CrewAI
        response = await crewai_service.process_query(
            user_query=user_query,
            page_type=page_type,
            cell_id=cell_id,
            references=references,
            project_id=project_id
        )
        
        return {
            "response": response,
            "timestamp": datetime.now().isoformat(),
            "page_type": page_type,
            "cell_id": cell_id,
            "references": references
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Chatbot query failed: {error_msg}")
        
        # Check if it's a quota/API error
        if "429" in error_msg or "quota" in error_msg.lower() or "RESOURCE_EXHAUSTED" in error_msg:
            user_message = (
                "I apologize, but the AI service is currently experiencing quota limitations. "
                "Please try again in a few minutes. "
                "If this persists, you may need to upgrade your API plan or wait for quota reset."
            )
        elif "API" in error_msg or "api_key" in error_msg.lower():
            user_message = (
                "I apologize, but there's an issue with the AI service configuration. "
                "Please check that your API key (GROQ_API_KEY or GEMINI_API_KEY) is valid and has available quota."
            )
        else:
            user_message = f"I apologize, but I encountered an error processing your query: {error_msg[:200]}"
        
        raise HTTPException(status_code=500, detail=user_message)

@app.get("/api/chatbot/cells")
async def get_available_cells():
    """Get list of available cells for chatbot context"""
    try:
        from tdengine_service import tdengine_service
        cells = tdengine_service.get_available_cells()
        return {"cells": cells, "count": len(cells)}
    except Exception as e:
        logger.error(f"Failed to get available cells: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_id}/nodes/{equipment_id}/image")
async def upload_node_image(project_id: str, equipment_id: str, file: UploadFile = File(...)):
    """Upload an image for a specific node/equipment"""
    try:
        # Validate file type
        allowed_types = ["image/png", "image/jpeg", "image/jpg", "image/svg+xml", "image/gif"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Allowed: PNG, JPG, SVG, GIF"
            )

        # Create project images directory
        images_dir = os.path.join(os.path.dirname(__file__), 'data', 'projects', project_id, 'images')
        os.makedirs(images_dir, exist_ok=True)

        # Generate filename with equipment_id
        file_extension = os.path.splitext(file.filename)[1] if file.filename else '.png'
        filename = f"{equipment_id}{file_extension}"
        file_path = os.path.join(images_dir, filename)

        # Save the uploaded file
        contents = await file.read()
        with open(file_path, 'wb') as f:
            f.write(contents)

        # Return the relative path that frontend can use
        image_url = f"/api/projects/{project_id}/images/{filename}"

        logger.info(f"Uploaded image for equipment {equipment_id} in project {project_id}")
        return {
            "success": True,
            "image_url": image_url,
            "equipment_id": equipment_id,
            "filename": filename,
            "file_size": len(contents)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload image for {equipment_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

@app.get("/api/projects/{project_id}/images/{filename}")
async def get_node_image(project_id: str, filename: str):
    """Serve uploaded node images"""
    try:
        from fastapi.responses import FileResponse

        file_path = os.path.join(os.path.dirname(__file__), 'data', 'projects', project_id, 'images', filename)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Image not found")

        return FileResponse(file_path, media_type='image/*')

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve image {filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to serve image: {str(e)}")

@app.post("/api/projects/{project_id}/alerts/config/threshold")
async def create_alert_threshold(project_id: str, threshold_data: dict):
    """Create a new alert threshold"""
    try:
        # Validate required fields
        if not threshold_data.get('topic_name'):
            raise HTTPException(status_code=400, detail="topic_name is required")

        # Generate URL-safe ID
        safe_topic = threshold_data['topic_name'].replace('/', '_')
        threshold_id = f"{safe_topic}_{str(uuid.uuid4())[:8]}"

        # Create threshold object
        threshold = {
            'id': threshold_id,
            'project_id': project_id,
            'topic_name': threshold_data['topic_name'],
            'sensor_type': threshold_data['topic_name'].split('/')[-1] if '/' in threshold_data['topic_name'] else threshold_data['topic_name'],
            'min_value': threshold_data.get('min_value'),
            'max_value': threshold_data.get('max_value'),
            'enabled': threshold_data.get('enabled', True)
        }

        # Load project
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Initialize alert_thresholds if it doesn't exist
        if 'alert_thresholds' not in project:
            project['alert_thresholds'] = []

        # Migrate any existing thresholds with problematic IDs
        project['alert_thresholds'] = migrate_threshold_ids(project['alert_thresholds'])

        # Add new threshold
        project['alert_thresholds'].append(threshold)

        # Save project
        db.save_project(project)

        return {
            "success": True,
            "id": threshold_id,
            "threshold": threshold
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert threshold for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create alert threshold: {str(e)}")

def migrate_threshold_ids(thresholds: list) -> list:
    """Migrate any threshold IDs containing slashes to URL-safe format"""
    migrated = []
    for threshold in thresholds:
        threshold_id = threshold.get('id', '')
        if '/' in threshold_id:
            # Generate new safe ID
            topic_name = threshold.get('topic_name', '')
            safe_topic = topic_name.replace('/', '_') if topic_name else 'unknown'
            new_id = f"{safe_topic}_{str(uuid.uuid4())[:8]}"

            # Create migrated threshold with new ID
            migrated_threshold = threshold.copy()
            migrated_threshold['id'] = new_id
            migrated.append(migrated_threshold)
            logger.info(f"Migrated threshold ID from '{threshold_id}' to '{new_id}'")
        else:
            migrated.append(threshold)

    return migrated
    """Create a new alert threshold"""
    try:
        # Validate required fields
        if not threshold_data.get('topic_name'):
            raise HTTPException(status_code=400, detail="topic_name is required")

        # Generate URL-safe ID
        safe_topic = threshold_data['topic_name'].replace('/', '_')
        threshold_id = f"{safe_topic}_{str(uuid.uuid4())[:8]}"

        # Create threshold object
        threshold = {
            'id': threshold_id,
            'project_id': project_id,
            'topic_name': threshold_data['topic_name'],
            'sensor_type': threshold_data['topic_name'].split('/')[-1] if '/' in threshold_data['topic_name'] else threshold_data['topic_name'],
            'min_value': threshold_data.get('min_value'),
            'max_value': threshold_data.get('max_value'),
            'enabled': threshold_data.get('enabled', True)
        }

        # Load project
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Add threshold to project
        if 'alert_thresholds' not in project:
            project['alert_thresholds'] = []
        project['alert_thresholds'].append(threshold)

        # Save project
        db.save_project(project)

        return {
            "success": True,
            "id": threshold_id,
            "threshold": threshold
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert threshold for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create alert threshold: {str(e)}")

@app.post("/api/projects/{project_id}/alerts/config")
async def upload_alert_config(project_id: str, file: UploadFile = File(...)):
    """Upload CSV file with alert thresholds for sensors"""
    try:
        # Validate file type
        if not file.filename.endswith('.csv'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only CSV files are allowed."
            )

        # Read CSV content
        content = await file.read()
        csv_content = content.decode('utf-8')

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_content))

        # Validate CSV headers
        required_headers = ['topic_name', 'min_value', 'max_value']
        if not all(header in csv_reader.fieldnames for header in required_headers):
            raise HTTPException(
                status_code=400,
                detail=f"CSV must contain columns: {', '.join(required_headers)}"
            )

        alert_thresholds = []
        for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
            try:
                # Parse values - allow empty strings for optional thresholds
                min_value = float(row['min_value']) if row['min_value'].strip() else None
                max_value = float(row['max_value']) if row['max_value'].strip() else None

                # At least one threshold must be specified
                if min_value is None and max_value is None:
                    raise ValueError("At least one of min_value or max_value must be specified")

                # Extract sensor type from topic (last part after '/')
                topic_parts = row['topic_name'].strip().split('/')
                sensor_type = topic_parts[-1] if topic_parts else 'unknown'

                # Generate URL-safe ID by replacing slashes with underscores and adding UUID
                safe_topic = row['topic_name'].strip().replace('/', '_')
                threshold_id = f"{safe_topic}_{row_num}_{str(uuid.uuid4())[:8]}"

                alert_threshold = {
                    'id': threshold_id,
                    'topic_name': row['topic_name'].strip(),
                    'sensor_type': sensor_type,
                    'min_value': min_value,
                    'max_value': max_value,
                    'enabled': True,
                    'created_at': datetime.now().isoformat()
                }

                alert_thresholds.append(alert_threshold)

            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {row_num}: Invalid numeric value in min_value or max_value - {str(e)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Row {row_num}: Error parsing row - {str(e)}"
                )

        if not alert_thresholds:
            raise HTTPException(status_code=400, detail="No valid alert thresholds found in CSV")

        # Load existing project
        from database_service import db
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Update project with alert thresholds
        project['alert_thresholds'] = alert_thresholds
        project['updated_at'] = datetime.now().isoformat()

        # Save updated project
        db.save_project(project)

        logger.info(f"Uploaded {len(alert_thresholds)} alert thresholds for project {project_id}")

        return {
            "success": True,
            "alert_thresholds": alert_thresholds,
            "count": len(alert_thresholds),
            "message": f"Successfully uploaded {len(alert_thresholds)} alert thresholds"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload alert config for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload alert config: {str(e)}")

@app.get("/api/projects/{project_id}/alerts/config")
async def get_alert_config(project_id: str):
    """Get alert thresholds for a project"""
    try:
        from database_service import db
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        alert_thresholds = project.get('alert_thresholds', [])

        return {
            "alert_thresholds": alert_thresholds,
            "count": len(alert_thresholds)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get alert config for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alert config: {str(e)}")

@app.get("/api/projects/{project_id}/alerts/active")
async def get_active_alerts(project_id: str, equipment_id: Optional[str] = None):
    """Get active alerts for a project"""
    try:
        active_alerts = alert_service.get_active_alerts(equipment_id)

        return {
            "alerts": active_alerts,
            "count": len(active_alerts)
        }

    except Exception as e:
        logger.error(f"Failed to get active alerts for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get active alerts: {str(e)}")

@app.get("/api/projects/{project_id}/alerts/history")
async def get_alert_history(project_id: str, limit: int = 50, equipment_id: Optional[str] = None):
    """Get alert history for a project"""
    try:
        history = alert_service.get_alert_history(limit, equipment_id)

        return {
            "alerts": history,
            "count": len(history)
        }

    except Exception as e:
        logger.error(f"Failed to get alert history for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alert history: {str(e)}")

@app.delete("/api/projects/{project_id}/alerts/resolved")
async def clear_resolved_alerts(project_id: str, older_than_hours: int = 24):
    """Clear resolved alerts older than specified hours"""
    try:
        alert_service.clear_resolved_alerts(older_than_hours)
        return {"message": f"Cleared resolved alerts older than {older_than_hours} hours"}

    except Exception as e:
        logger.error(f"Failed to clear resolved alerts for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear resolved alerts: {str(e)}")

@app.get("/api/projects/{project_id}/alerts/stats")
async def get_alert_stats(project_id: str):
    """Get alert statistics for a project"""
    try:
        stats = alert_service.get_alert_stats()

        return stats

    except Exception as e:
        logger.error(f"Failed to get alert stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get alert stats: {str(e)}")

@app.put("/api/projects/{project_id}/alerts/config/{threshold_id}")
async def update_alert_threshold(project_id: str, threshold_id: str, threshold_data: dict):
    """Update a specific alert threshold"""
    try:
        from database_service import db
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        thresholds = project.get('alert_thresholds', [])
        threshold_index = None

        for i, threshold in enumerate(thresholds):
            if threshold['id'] == threshold_id:
                threshold_index = i
                break

        if threshold_index is None:
            raise HTTPException(status_code=404, detail="Threshold not found")

        # Validate threshold data
        min_value = threshold_data.get('min_value')
        max_value = threshold_data.get('max_value')

        if min_value is not None and not isinstance(min_value, (int, float)):
            raise HTTPException(status_code=400, detail="min_value must be a number")
        if max_value is not None and not isinstance(max_value, (int, float)):
            raise HTTPException(status_code=400, detail="max_value must be a number")

        # At least one threshold must be specified
        if min_value is None and max_value is None:
            raise HTTPException(status_code=400, detail="At least one of min_value or max_value must be specified")

        # Update threshold
        thresholds[threshold_index].update({
            'min_value': min_value,
            'max_value': max_value,
            'enabled': threshold_data.get('enabled', thresholds[threshold_index].get('enabled', True))
        })

        # Update project
        project['alert_thresholds'] = thresholds
        project['updated_at'] = datetime.now().isoformat()
        db.save_project(project)

        logger.info(f"Updated alert threshold {threshold_id} for project {project_id}")

        return {
            "success": True,
            "threshold": thresholds[threshold_index]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update alert threshold {threshold_id} for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update threshold: {str(e)}")

@app.delete("/api/projects/{project_id}/alerts/config/{threshold_id}")
async def delete_alert_threshold(project_id: str, threshold_id: str):
    """Delete a specific alert threshold"""
    try:
        from database_service import db
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        thresholds = project.get('alert_thresholds', [])
        threshold_index = None

        for i, threshold in enumerate(thresholds):
            if threshold['id'] == threshold_id:
                threshold_index = i
                break

        if threshold_index is None:
            raise HTTPException(status_code=404, detail="Threshold not found")

        # Remove threshold
        deleted_threshold = thresholds.pop(threshold_index)

        # Update project
        project['alert_thresholds'] = thresholds
        project['updated_at'] = datetime.now().isoformat()
        db.save_project(project)

        logger.info(f"Deleted alert threshold {threshold_id} for project {project_id}")

        return {
            "success": True,
            "message": f"Threshold '{deleted_threshold.get('topic_name', threshold_id)}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert threshold {threshold_id} for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete threshold: {str(e)}")

@app.patch("/api/projects/{project_id}/alerts/config/{threshold_id}/toggle")
async def toggle_alert_threshold(project_id: str, threshold_id: str):
    """Toggle enable/disable status of a specific alert threshold"""
    try:
        from database_service import db
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        thresholds = project.get('alert_thresholds', [])
        threshold_index = None

        for i, threshold in enumerate(thresholds):
            if threshold['id'] == threshold_id:
                threshold_index = i
                break

        if threshold_index is None:
            raise HTTPException(status_code=404, detail="Threshold not found")

        # Toggle enabled status
        current_status = thresholds[threshold_index].get('enabled', True)
        thresholds[threshold_index]['enabled'] = not current_status

        # Update project
        project['alert_thresholds'] = thresholds
        project['updated_at'] = datetime.now().isoformat()
        db.save_project(project)

        logger.info(f"Toggled alert threshold {threshold_id} to {not current_status} for project {project_id}")

        return {
            "success": True,
            "threshold": thresholds[threshold_index]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle alert threshold {threshold_id} for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to toggle threshold: {str(e)}")

@app.post("/api/projects/{project_id}/documents/upload")
async def upload_document(project_id: str, file: UploadFile = File(...),
                        equipment_id: str = None, sensor_type: str = None,
                        document_type: str = "general"):
    """Upload a document for domain knowledge"""
    try:
        # Validate file type
        allowed_extensions = ['.pdf', '.docx', '.txt', '.md']
        file_extension = Path(file.filename).suffix.lower()

        if file_extension not in allowed_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file_extension}. Allowed: {', '.join(allowed_extensions)}"
            )

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size and file.size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {file.size} bytes. Maximum allowed: {max_size} bytes"
            )

        # Read file contents
        contents = await file.read()

        try:
            # Add document to vector store (async processing with content)
            doc_id = await vector_store.add_document_async(
                project_id=project_id,
                file_content=contents,
                filename=file.filename,
                equipment_id=equipment_id,
                sensor_type=sensor_type,
                document_type=document_type
            )

            # Update project with document metadata
            project = db.load_project(project_id)
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")

            # Add document to project metadata
            if 'domain_documents' not in project:
                project['domain_documents'] = []

            doc_metadata = {
                'id': doc_id,
                'filename': file.filename,
                'file_type': file_extension[1:],  # Remove the dot
                'equipment_id': equipment_id,
                'sensor_type': sensor_type,
                'document_type': document_type,
                'uploaded_at': datetime.now().isoformat(),
                'file_size': len(contents),
                'chunk_count': None  # Will be updated after processing
            }

            project['domain_documents'].append(doc_metadata)
            project['updated_at'] = datetime.now().isoformat()

            # Save updated project
            db.save_project(project)

            logger.info(f"Document uploaded: {file.filename} (ID: {doc_id}) for project {project_id}")

            return {
                "success": True,
                "doc_id": doc_id,
                "filename": file.filename,
                "message": f"Document '{file.filename}' uploaded successfully. Processing in background.",
                "status": "processing"
            }

        except Exception as e:
            logger.error(f"Failed to add document to vector store: {e}")
            # Continue with upload even if vector store fails
            pass

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload document for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")

@app.get("/api/projects/{project_id}/documents")
async def get_project_documents(project_id: str):
    """Get all documents for a project"""
    try:
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        documents = project.get('domain_documents', [])

        return {
            "documents": documents,
            "count": len(documents)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get documents for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get documents: {str(e)}")

@app.delete("/api/projects/{project_id}/documents/{doc_id}")
async def delete_document(project_id: str, doc_id: str):
    """Delete a document from a project"""
    try:
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Find and remove document from project
        documents = project.get('domain_documents', [])
        doc_to_delete = None

        for i, doc in enumerate(documents):
            if doc['id'] == doc_id:
                doc_to_delete = doc
                documents.pop(i)
                break

        if not doc_to_delete:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from vector store (now requires project_id for per-project collections)
        deleted = vector_store.delete_document(project_id, doc_id)
        if not deleted:
            logger.warning(f"Document {doc_id} not found in vector store during deletion")

        # Update project
        project['domain_documents'] = documents
        project['updated_at'] = datetime.now().isoformat()
        db.save_project(project)

        logger.info(f"Document deleted: {doc_id} from project {project_id}")

        return {
            "success": True,
            "message": f"Document '{doc_to_delete['filename']}' deleted successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document {doc_id} from project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@app.get("/api/projects/{project_id}/documents/stats")
async def get_document_stats(project_id: str):
    """Get document statistics for a project"""
    try:
        # Get vector store stats
        vector_stats = vector_store.get_document_stats(project_id)

        # Get project document metadata
        project = db.load_project(project_id)
        documents = project.get('domain_documents', []) if project else []

        # Calculate additional stats
        total_size = sum(doc.get('file_size', 0) for doc in documents)
        file_types = {}
        equipment_docs = {}

        for doc in documents:
            # Count file types
            file_type = doc.get('file_type', 'unknown')
            file_types[file_type] = file_types.get(file_type, 0) + 1

            # Count equipment associations
            equipment_id = doc.get('equipment_id')
            if equipment_id:
                equipment_docs[equipment_id] = equipment_docs.get(equipment_id, 0) + 1

        return {
            "total_chunks": vector_stats.get('total_chunks', 0),
            "unique_documents": len(documents),
            "total_size_bytes": total_size,
            "file_types": file_types,
            "equipment_associations": equipment_docs,
            "sensor_types": list(set(doc.get('sensor_type') for doc in documents if doc.get('sensor_type')))
        }

    except Exception as e:
        logger.error(f"Failed to get document stats for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document stats: {str(e)}")

# Project Management Endpoints
@app.post("/api/projects")
async def create_project(project: Dict[str, Any]):
    """Create a new project"""
    try:
        # Validate required fields
        if not project.get('id'):
            raise HTTPException(status_code=400, detail="Project must have an 'id' field")
        if not project.get('name'):
            raise HTTPException(status_code=400, detail="Project must have a 'name' field")

        # Set timestamps
        project['created_at'] = datetime.now().isoformat()
        project['updated_at'] = datetime.now().isoformat()

        # Initialize empty arrays if not present
        project.setdefault('domain_documents', [])
        project.setdefault('alert_thresholds', [])
        project.setdefault('graph_layout', {'nodes': [], 'edges': []})
        project.setdefault('discovered_nodes', [])
        project.setdefault('description', None)
        project.setdefault('last_accessed', None)
        project.setdefault('is_favorite', False)

        # Save to database
        db.save_project(project)

        return {
            "status": "created",
            "project": project
        }
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")

@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, project: Dict[str, Any]):
    """Update an existing project"""
    try:
        # Load existing project
        existing_project = db.load_project(project_id)
        if not existing_project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Update project data
        updated_project = {**existing_project, **project}
        updated_project['id'] = project_id  # Ensure ID is correct
        updated_project['updated_at'] = datetime.now().isoformat()

        # Save to database
        db.save_project(updated_project)

        return {
            "status": "updated",
            "project": updated_project
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")

@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project"""
    try:
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return project
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get project: {str(e)}")

@app.get("/api/projects")
async def list_projects():
    """List all projects"""
    try:
        # Get all project IDs from the projects directory
        if not db.projects_dir.exists():
            return {"projects": [], "count": 0}

        projects = []
        for project_file in db.projects_dir.glob("*.json"):
            project_id = project_file.stem  # Remove .json extension
            project = db.load_project(project_id)
            if project:
                # Return full project data
                projects.append(project)

        return {
            "projects": projects,
            "count": len(projects)
        }
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")

@app.get("/api/projects/summaries")
async def list_project_summaries():
    """List project summaries"""
    try:
        # Get all project IDs from the projects directory
        if not db.projects_dir.exists():
            return {"projects": [], "count": 0}

        projects = []
        for project_file in db.projects_dir.glob("*.json"):
            project_id = project_file.stem  # Remove .json extension
            project = db.load_project(project_id)
            if project:
                # Return summary info
                projects.append({
                    "id": project.get("id"),
                    "name": project.get("name"),
                    "created_at": project.get("created_at"),
                    "updated_at": project.get("updated_at"),
                    "description": project.get("description")
                })

        return {
            "projects": projects,
            "count": len(projects)
        }
    except Exception as e:
        logger.error(f"Failed to list project summaries: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list project summaries: {str(e)}")

@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project and all its data"""
    try:
        # Check if project exists
        project = db.load_project(project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Delete project file
        project_file = db._get_project_file(project_id)
        if project_file.exists():
            project_file.unlink()

        # Delete associated data (messages, sessions, etc.)
        db.delete_project_data(project_id)

        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.on_event("startup")
async def startup_event():
    """Store the main event loop for thread-safe async operations"""
    global main_loop
    main_loop = asyncio.get_event_loop()
    logger.info("FastAPI application started")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global current_discovery, current_monitoring
    if current_discovery:
        current_discovery.stop()
    if current_monitoring:
        current_monitoring.stop()
    logger.info("FastAPI application shutdown")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting MQTT GUI Backend Server (FastAPI) on http://localhost:8001")
    print("📡 WebSocket will be available at ws://localhost:8001/ws")
    uvicorn.run(app, host="0.0.0.0", port=8001) 