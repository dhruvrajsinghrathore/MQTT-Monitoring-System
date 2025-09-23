#!/usr/bin/env python3

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from concurrent.futures import ThreadPoolExecutor

import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database_service import db
from pydantic import BaseModel

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
        
    def set_project(self, project):
        """Set the current project and initialize nodes from project data"""
        self.project = project
        self.nodes_data = {}
        self.sensor_data = {}
        
        if project and project.get('graph_layout', {}).get('nodes'):
            for node in project['graph_layout']['nodes']:
                equipment_id = node['data']['equipment_id']
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
    
    def update_sensor_data(self, equipment_id: str, sensor_type: str, sensor_reading: dict):
        """Update sensor data for a specific equipment and sensor type"""
        # Ensure equipment exists in our data
        if equipment_id not in self.sensor_data:
            # Create a new node if it doesn't exist
            self.nodes_data[equipment_id] = {
                'id': f"{equipment_id}_{int(time.time())}",
                'type': 'custom',
                'position': {'x': len(self.nodes_data) * 200, 'y': len(self.nodes_data) * 100},
                'data': {
                    'equipment_id': equipment_id,
                    'equipment_type': equipment_id.split('_')[0] if '_' in equipment_id else 'unknown',
                    'label': equipment_id,
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
    
    def get_graph_data(self):
        """Get complete graph data with all nodes and their sensor data"""
        nodes = list(self.nodes_data.values())
        edges = []
        
        # Get edges from project if available
        if self.project and self.project.get('graph_layout', {}).get('edges'):
            edges = self.project['graph_layout']['edges']
        
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
                    logger.info(f"Discovered: {equipment_id} / {sensor_type} on topic {topic}")
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
                
                # Get complete graph data and send to all connected WebSocket clients
                graph_data = graph_manager.get_graph_data()
                message = {
                    'type': 'graph_update',
                    'data': graph_data
                }
                    
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
                
                # Send to all connected WebSocket clients - use thread-safe approach
                if main_loop and not main_loop.is_closed():
                    asyncio.run_coroutine_threadsafe(broadcast_to_websockets(message), main_loop)
            
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
    print("🚀 Starting MQTT GUI Backend Server (FastAPI) on http://localhost:8000")
    print("📡 WebSocket will be available at ws://localhost:8000/ws")
    uvicorn.run(app, host="0.0.0.0", port=8000) 