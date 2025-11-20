# SensorFlow

A minimal, user-friendly MQTT workflow editor that allows you to:
1. Configure MQTT connections and discover available nodes
2. Create editable workflow graphs with React Flow
3. Monitor live MQTT data with your custom layout

## Features

- **Minimal UI**: Clean gray/white design focused on functionality
- **3-Step Workflow**: 
  - Page 1: MQTT Configuration & Node Discovery
  - Page 2: Drag-and-drop Graph Editor 
  - Page 3: Live Data Monitoring
- **Editable Graphs**: Full React Flow integration with node placement and edge creation
- **Real-time Updates**: WebSocket-based live data streaming
- **Adaptive Schema**: Automatically adapts to any JSON MQTT payload structure

## Setup

### Frontend (React + Vite)

1. Install dependencies:
```bash
cd frontend
npm install
```

2. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3001`

### Backend (Python Flask)

1. Install Python dependencies:
```bash
cd backend
pip install -r requirements.txt
```

2. Start the backend server:
```bash
python server.py
```

The backend will be available at `http://localhost:8000`

## Usage

1. **Configuration Page** (`/config`):
   - Enter your MQTT broker details (host, port, credentials)
   - Specify topic patterns (e.g., `lab/#` or `device/+/sensor`)
   - Test connection and start node discovery
   - View discovered equipment and proceed to editor

2. **Graph Editor Page** (`/editor`):
   - Drag discovered nodes from sidebar to canvas
   - Create connections between nodes by dragging
   - Arrange your workflow layout
   - Save and proceed to monitoring

3. **Monitoring Page** (`/monitor`):
   - View live MQTT data updates on your custom graph
   - Start/stop monitoring
   - Nodes change color based on data values
   - Real-time connection status

## MQTT Integration

This application integrates with the existing Scenario_2 MQTT infrastructure:
- Uses the same adaptive schema learning
- Compatible with existing MQTT configurations
- Reuses authentication and connection helpers

## Architecture

- **Frontend**: React + TypeScript + Vite + Tailwind CSS + React Flow
- **Backend**: Flask + SocketIO + paho-mqtt
- **Communication**: WebSocket for real-time data, REST API for configuration
- **Styling**: Minimal gray/white theme with Tailwind CSS

## Development

The application is designed to be:
- Easy to extend with new node types
- Compatible with any MQTT broker
- Responsive and user-friendly
- Maintainable with TypeScript 