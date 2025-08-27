# MQTT Workflow Editor Setup Guide

This guide will help you set up and run the MQTT Workflow Editor application.

## Quick Start

1. **One-command setup** (from the GUI directory):
```bash
./start.sh
```

2. **Test your setup** (optional):
```bash
./test-setup.sh
```

If this doesn't work, follow the detailed setup below.

## Detailed Setup

### Prerequisites

- **Node.js** (v16 or higher) and npm
- **Python** (v3.8 or higher) and pip
- **Access to an MQTT broker** (or use the default cloud.dtkit.org)

### 1. Frontend Setup (React + Vite)

```bash
# Navigate to GUI directory
cd GUI

# Install Node.js dependencies
npm install

# Start development server (optional - also done by start.sh)
npm run dev
```

### 2. Backend Setup (Python Flask)

```bash
# Navigate to backend directory
cd GUI/backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Start backend server (optional - also done by start.sh)
python server.py
```

### 3. Run Both Servers

From the GUI directory:

**Development Mode:**
```bash
# Make script executable (if not already)
chmod +x start.sh

# Start both frontend and backend
./start.sh
```

**Production Mode:**
```bash
# Make script executable (if not already)
chmod +x start-production.sh

# Build and start production servers
./start-production.sh
```

### 4. Test Setup (Optional)

```bash
# Verify everything is installed correctly
./test-setup.sh
```

## Application URLs

- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8000

## Usage Workflow

### Page 1: Configuration (`/config`)
1. Enter your MQTT broker details:
   - **Host**: Your MQTT broker URL (default: cloud.dtkit.org)
   - **Port**: Usually 1883 for non-SSL
   - **Username/Password**: If required by your broker
   - **Topic Pattern**: Use wildcards like `lab/#` or `device/+/sensor`
   - **Discovery Duration**: How long to listen for messages (30 seconds default)

2. Test the connection
3. Start discovery to find available MQTT nodes
4. Review discovered equipment and proceed to editor

### Page 2: Graph Editor (`/editor`)
1. **Available Nodes** are shown in the left sidebar
2. **Drag nodes** from sidebar onto the canvas
3. **Connect nodes** by dragging from one node to another
4. **Arrange your workflow** as desired
5. **Save layout** and proceed to monitoring

### Page 3: Live Monitoring (`/monitor`)
1. **Start monitoring** to receive live MQTT data
2. **Watch nodes update** with real-time sensor values
3. **Node colors change** based on data values:
   - Light blue: Low values (< 500)
   - Light yellow: Medium values (500-1000)
   - Light red: High values (> 1000)
4. **Connection status** is shown in the header

## MQTT Compatibility

This application works with any MQTT broker and automatically adapts to JSON message structures. It reuses the adaptive schema learning from Scenario_2.

### Supported Topic Patterns
- `lab/#` - All topics under lab/
- `device/+/sensor` - Specific pattern with wildcards
- `factory/equipment/+/status` - Equipment status messages
- Any valid MQTT topic pattern

### Supported Message Formats
The application automatically adapts to any JSON payload structure by:
- Extracting equipment IDs from various fields
- Identifying sensor types and values
- Learning field relationships over time
- Creating appropriate node representations

## Troubleshooting

### Common Issues

#### RuntimeError: The Werkzeug web server is not designed to run in production
**Fixed**: This error has been resolved by adding `allow_unsafe_werkzeug=True` to the development server configuration.

#### Backend Issues
```bash
# Check if backend is running
curl http://localhost:8000/api/mqtt/test

# Check Python dependencies
cd backend
source .venv/bin/activate
pip list

# Run the setup test
./test-setup.sh
```

#### Frontend Issues
```bash
# Check if frontend is running
curl http://localhost:3001

# Reinstall dependencies
npm install

# Test build
npm run build
```

### MQTT Connection Issues
- Verify broker URL and port
- Check authentication credentials
- Ensure topic patterns are valid
- Test with a simple MQTT client first

### Port Conflicts
If ports 3001 or 8000 are in use:
- Frontend: Edit `vite.config.ts` to change port
- Backend: Edit `server.py` to change port
- Update the start script accordingly

## Development vs Production

### Development Mode (`./start.sh`)
- Uses Vite dev server for hot reloading
- Uses Flask development server with debug mode
- Suitable for development and testing

### Production Mode (`./start-production.sh`)
- Builds optimized React bundle
- Uses Gunicorn WSGI server for better performance
- Serves static files efficiently
- Suitable for production deployment

## Development

### Project Structure
```
GUI/
├── src/                    # React frontend source
│   ├── pages/             # Main application pages
│   ├── components/        # React components
│   ├── contexts/          # React contexts
│   └── types/             # TypeScript types
├── backend/               # Python Flask backend
│   ├── server.py          # Main backend server
│   ├── wsgi.py            # Production WSGI entry point
│   ├── requirements.txt   # Python dependencies
│   └── .venv/             # Virtual environment
├── package.json           # Node.js dependencies
├── start.sh              # Development startup script
├── start-production.sh   # Production startup script
└── test-setup.sh         # Setup verification script
```

### Adding New Features
- **Frontend**: Add new React components in `src/components/`
- **Backend**: Add new API routes in `backend/server.py`
- **MQTT**: Extend the schema learner for new message types

### Integration with Scenario_2
The backend automatically imports and uses existing MQTT modules from Scenario_2:
- `mqtt_config.py` - Configuration management
- `mqtt_client_helper.py` - Connection utilities
- `dynamic_workflow_subscriber.py` - Schema learning

This ensures compatibility and reuses proven MQTT handling logic. 