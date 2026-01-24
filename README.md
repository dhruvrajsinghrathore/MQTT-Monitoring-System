# MQTT Monitor - Real-Time IoT Analytics Platform

A comprehensive real-time IoT analytics platform that ingests live MQTT sensor data, stores it in TDengine time-series database, and provides an interactive dashboard with an AI-powered chatbot for natural language querying of sensor data and domain knowledge.

## 🎯 Project Overview

This platform enables real-time monitoring and analysis of IoT sensor data through:

- **Real-time MQTT Data Ingestion**: Subscribes to MQTT topics and processes live sensor streams
- **Time-Series Database**: TDengine stores and manages high-frequency sensor data
- **Interactive Dashboard**: React-based UI for visualizing equipment, sensors, and real-time data
- **AI-Powered Chatbot**: CrewAI multi-agent system that interprets natural language queries and generates optimized SQL queries
- **Domain Knowledge Search**: Semantic search through uploaded technical documents using ChromaDB vector embeddings
- **Real-time WebSocket Streaming**: Live data updates to the frontend dashboard

## ✨ Key Features

### 1. **MQTT Data Monitoring**
- Real-time MQTT message ingestion and processing
- Adaptive schema learning for any JSON payload structure
- Equipment and sensor discovery from MQTT topics
- Live data visualization with customizable workflows

### 2. **TDengine Integration**
- High-performance time-series database for sensor data
- Optimized SQL queries with aggregation strategies
- Support for multi-cell queries, correlations, and statistical analysis
- Query response time within 20 seconds through efficient aggregation

### 3. **AI Chatbot (CrewAI Multi-Agent System)**
- **Data Extraction Agent**: Intelligently routes queries, extracts parameters, and generates optimized SQL queries
- **Response Generation Agent**: Transforms query results into clear, natural language responses
- **Prompt Engineering**: Advanced instructions guide agents to handle complex queries, reduce hallucinations, and optimize database access
- **Tool-Based Architecture**: Agents use specialized tools to query TDengine, search domain knowledge, and access database schemas

### 4. **Domain Knowledge Management**
- Upload technical documents (PDFs, text files, etc.)
- Automatic document chunking and embedding generation
- Semantic search using ChromaDB vector database
- Per-project document collections for organized knowledge bases

### 5. **Interactive Dashboard**
- Equipment monitoring with real-time sensor values
- Equipment detail pages with historical data visualization
- Project management for organizing equipment and documents
- Alert system for threshold-based notifications

## 🏗️ Architecture

```
┌─────────────────┐
│ Synthetic Data  │
│   Generator     │──┐
│  (synthetic_    │  │
│   data.py)      │  │
└─────────────────┘  │
                     │ MQTT Messages
                     │ (cell/<id>/<sensor>)
                     ▼
              ┌──────────────┐
              │  MQTT Broker │
              │ (cloud.dtkit │
              │    .org)     │
              └──────────────┘
                     │
                     │ (External Service)
                     ▼
              ┌──────────────┐
              │   TDengine   │
              │  Time-Series │
              │   Database   │
              └──────────────┘
                     ▲
                     │ SQL Queries
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼────────┐      ┌────────▼────────┐
│  FastAPI       │      │  React Frontend │
│  Backend       │◄────►│  (TypeScript)   │
│                │      │                 │
│  - CrewAI      │      │  - Dashboard    │
│  - WebSocket   │      │  - Chatbot UI   │
│  - TDengine    │      │  - Monitoring   │
│  - ChromaDB    │      │  - Projects     │
└────────────────┘      └─────────────────┘
```

## 📋 Prerequisites

- **Node.js** (v16 or higher) and npm
- **Python** (v3.8 or higher) and pip
- **Access to MQTT broker** (default: `cloud.dtkit.org:1883`)
- **TDengine database** (external service at `http://213.218.240.182:6041`)
- **LLM API Key** (TAMUS AI or Google Gemini API key)

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd MQTT-Monitor
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration

Create a `.env` file in the `backend` directory:

```bash
# LLM Provider Configuration
# Choose 'tamus' (default) or 'gemini'
LLM_PROVIDER=tamus

# TAMUS AI Configuration (for LLM_PROVIDER=tamus)
TAMUS_AI_CHAT_API_KEY=your_tamus_ai_api_key_here
TAMUS_AI_CHAT_API_ENDPOINT=https://chat-api.tamu.ai
TAMUS_AI_MODEL=protected.gemini-2.0-flash-lite

# Gemini Configuration (for LLM_PROVIDER=gemini)
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here  # Optional fallback
```

**LLM Provider Options:**
- **`tamus`** (default): Uses TAMU's AI inference platform. Requires `TAMUS_AI_CHAT_API_KEY`.
- **`gemini`**: Uses Google Gemini API. Requires `GEMINI_API_KEY`.

### 4. Frontend Setup

```bash
cd frontend

# Install Node.js dependencies
npm install
```

### 5. Generate Synthetic Data (MQTT Publisher)

To populate the MQTT broker with test data that TDengine can ingest:

```bash
cd data_gen

# Install MQTT client dependencies (if not already installed)
pip install paho-mqtt

# Run synthetic data generator
# Example: 2 Hz for 30 seconds, 4 cells
python synthetic_data.py --hz 2 --duration 30 --cells 4

# For continuous streaming (infinite):
python synthetic_data.py --hz 1 --cells 10

# With custom sensor ranges:
python synthetic_data.py --hz 2 --duration 30 --cells 4 \
  --range o2_percent=65:95 --range pH=7.2:7.5
```

**Data Flow:**
1. `synthetic_data.py` publishes sensor data to MQTT topics: `cell/<cell_id>/<field_name>`
2. **TDengine** (external service) subscribes to MQTT and automatically ingests data into time-series tables
3. The backend queries TDengine via REST API to retrieve stored sensor data

**Note:** TDengine ingestion from MQTT is handled by an external service. Ensure your MQTT broker is accessible and TDengine is configured to subscribe to the appropriate topics.

### 6. Start the Application

**Option A: Using the startup script (recommended)**

```bash
# From project root
chmod +x start.sh
./start.sh
```

**Option B: Manual startup**

```bash
# Terminal 1: Start backend
cd backend
source .venv/bin/activate
python server.py

# Terminal 2: Start frontend
cd frontend
npm run dev
```

### 7. Access the Application

- **Frontend Dashboard**: http://localhost:3001
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (FastAPI Swagger UI)

## 📖 Usage Guide

### Dashboard Features

1. **Projects Page** (`/projects`):
   - Create and manage projects
   - Organize equipment and documents by project

2. **Configuration Page** (`/config`):
   - Configure MQTT broker connection
   - Discover available equipment and sensors
   - Set up topic patterns for monitoring

3. **Monitoring Page** (`/monitor`):
   - View real-time sensor data
   - Monitor equipment status
   - Access AI chatbot for data queries

4. **Equipment Detail Page** (`/equipment/:id`):
   - View detailed sensor information
   - Historical data visualization
   - Equipment-specific chatbot queries

### AI Chatbot Usage

The chatbot supports natural language queries about sensor data:

**Example Queries:**
- "What's the pressure in cell_1?"
- "Show me the average glucose levels for all cells over the last 24 hours"
- "Compare pH values between cell_1 and cell_2"
- "What's the correlation between glucose and pH in cell_1?"
- "Show me the trend of oxygen levels in cell_3 over the past week"

**Features:**
- Automatic SQL query generation optimized for TDengine
- Statistical analysis (averages, standard deviation, correlations)
- Multi-cell comparisons
- Time-based trend analysis
- Domain knowledge search from uploaded documents

### Domain Knowledge Upload

1. Navigate to a project page
2. Upload technical documents (PDFs, text files)
3. Documents are automatically processed, chunked, and embedded
4. Query domain knowledge through the chatbot: "What does the manual say about cell maintenance?"

## 🗂️ Project Structure

```
MQTT-Monitor/
├── backend/
│   ├── config/
│   │   ├── agents.yaml          # CrewAI agent definitions
│   │   └── tasks.yaml            # CrewAI task definitions
│   ├── tools/
│   │   ├── tdengine_tool.py     # TDengine query tools
│   │   └── vector_search_tool.py # Domain knowledge search tool
│   ├── crew.py                  # CrewAI orchestration
│   ├── crewai_service.py         # Service wrapper
│   ├── server.py                # FastAPI application
│   ├── tdengine_service.py       # TDengine database service
│   ├── vectorstore_service.py   # ChromaDB vector store service
│   ├── tamu_agent_demo.py       # TAMUS AI LLM wrapper
│   └── requirements.txt          # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/          # React components
│   │   │   ├── ChatBot.tsx      # AI chatbot UI
│   │   │   └── ...
│   │   ├── pages/               # Page components
│   │   ├── services/            # API services
│   │   └── types/               # TypeScript types
│   └── package.json
├── data_gen/
│   ├── synthetic_data.py        # MQTT data publisher
│   └── mqtt_client_helper.py    # MQTT client utilities
├── start.sh                     # Development startup script
└── README.md
```

## 🛠️ Technologies Used

### Backend
- **FastAPI**: Modern Python web framework
- **CrewAI**: Multi-agent AI framework for intelligent query processing
- **TDengine**: High-performance time-series database
- **ChromaDB**: Vector database for semantic search
- **paho-mqtt**: MQTT client library
- **WebSockets**: Real-time data streaming
- **LangChain**: LLM integration and document processing

### Frontend
- **React**: UI framework
- **TypeScript**: Type-safe JavaScript
- **Vite**: Build tool and dev server
- **Tailwind CSS**: Utility-first CSS framework
- **React Flow**: Interactive graph/flow visualization

### AI/ML
- **TAMUS AI / Google Gemini**: Large language models
- **CrewAI Agents**: Specialized AI agents for data extraction and response generation
- **Vector Embeddings**: Document semantic search

## 🔧 Development

### Running in Development Mode

```bash
./start.sh
```

### Running in Production Mode

```bash
chmod +x start-production.sh
./start-production.sh
```

### Testing

```bash
# Test setup
./test-setup.sh

# Test API
./test-api.sh
```

## 📝 Key Implementation Details

### CrewAI Multi-Agent System

The chatbot uses a two-agent system:

1. **Data Extraction Agent**: 
   - Analyzes query intent
   - Extracts parameters (cells, sensors, time periods)
   - Generates optimized SQL queries
   - Executes queries against TDengine
   - Returns structured JSON data

2. **Response Generation Agent**:
   - Interprets structured data from Agent 1
   - Generates natural language responses
   - Explains statistical results
   - Handles multi-cell comparisons

### Query Optimization

- **Aggregation Strategies**: All queries use SQL aggregation (AVG, STDDEV, MIN, MAX) to prevent context overflow
- **Time-based Sampling**: Trend queries use INTERVAL grouping for efficient data sampling
- **Multi-cell Queries**: UNION ALL for parallel cell queries
- **Response Time**: Optimized to stay within 20 seconds through efficient aggregation

### Domain Knowledge Search

- Documents are chunked and embedded using LangChain
- ChromaDB stores embeddings per project
- Semantic search finds relevant document sections
- Results are integrated into chatbot responses
