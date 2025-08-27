import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  BackgroundVariant
} from 'reactflow';
import CustomNode from '../components/CustomNode';
import { ArrowLeft, Pause, Play, Settings, Activity } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { Project, SensorReading } from '../types';
import { WEBSOCKET_URL, getApiUrl, API_ENDPOINTS } from '../config/api';
import { DatabaseService } from '../services/DatabaseService';

import 'reactflow/dist/style.css';

// Define node types for ReactFlow
const nodeTypes = {
  custom: CustomNode,
};

const MonitoringPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { project: contextProject } = useProject();
  
  // Get project from location state or context
  const project: Project | null = (location.state as any)?.project || contextProject;
  
  const [nodes, setNodes, onNodesChange] = useNodesState(project?.graph_layout?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(project?.graph_layout?.edges || []);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
    // Note: Live data is now managed by backend and sent as complete graph updates
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);

  const websocketRef = useRef<WebSocket | null>(null);

  // Note: Nodes are now updated directly via WebSocket graph_update messages from backend

  // Handle node clicks for navigation to equipment detail
  const handleNodeClick = (event: React.MouseEvent, node: any) => {
    navigate(`/equipment/${node.data.equipment_id}`, {
      state: {
        equipment: node.data,
        project: project
      }
    });
  };

  const getUnitForSensorType = (sensorType: string): string => {
    // Common unit patterns that can be extracted from field names
    const unitPatterns: {[key: string]: string} = {
      // Direct unit extraction from field names
      'kOhm': 'kOhm',
      'percent': '%', 
      'pct': '%',
      'pH': 'pH',
      'mM': 'mM',
      'uL_min': 'µL/min',
      'mbar': 'mbar',
      'nM': 'nM',
      'index': 'index',
      'pg': 'pg',
      'count': 'count',
      'AU': 'AU',
      'ratio': 'ratio',
      
      // Common sensor types
      'temperature': '°C',
      'pressure': 'mbar',
      'force': 'N',
      'flow_rate': 'µL/min',
      'speed': 'm/s',
      'position': 'mm',
      'composition': '%',
      'level': '%',
      'vibration': 'Hz',
      'voltage': 'V',
      'current': 'A',
      'power': 'W',
      'frequency': 'Hz'
    };
    
    // Try to extract unit from field name (e.g., "pressure_mbar" -> "mbar")
    for (const [pattern, unit] of Object.entries(unitPatterns)) {
      if (sensorType.toLowerCase().includes(pattern.toLowerCase())) {
        return unit;
      }
    }
    
    return 'units'; // Fallback for unknown types
  };



  const testMQTTConnection = async () => {
    if (!project) return;
    
    setIsTestingConnection(true);
    setConnectionStatus('connecting');
    
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.MQTT_TEST), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(project.mqtt_config)
      });
      
      if (response.ok) {
        setConnectionStatus('connected');
        console.log('✅ MQTT connection test successful');
      } else {
        setConnectionStatus('error');
        const errorText = await response.text();
        console.error('❌ MQTT connection failed:', errorText);
      }
    } catch (error) {
      setConnectionStatus('error');
      console.error('❌ Backend connection failed:', error);
    } finally {
      setIsTestingConnection(false);
    }
  };

  // Load project and test connection on mount
  useEffect(() => {
    if (project) {
      testMQTTConnection();
    }
  }, [project]);

  // Auto-start monitoring when coming from editor
  useEffect(() => {
    if (project && connectionStatus === 'connected' && !isMonitoring) {
      // Auto-start monitoring after connection is established
      setIsMonitoring(true);
    }
  }, [project, connectionStatus]);

  // Handle monitoring start/stop
  useEffect(() => {
    if (isMonitoring && connectionStatus === 'connected' && !websocketRef.current) {
      // Connect to backend WebSocket for live data
      setConnectionStatus('connecting');
      
      try {
        const wsUrl = WEBSOCKET_URL.replace('http', 'ws') + '/ws';
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
          console.log('✅ WebSocket connected');
          setConnectionStatus('connected');
          websocketRef.current = ws;
          
          // Send MQTT configuration to start monitoring
          const message: any = {
            type: 'start_monitoring',
            config: project?.mqtt_config,
            project: project // Send the complete project data
          };
          
          if (currentSessionId && project) {
            message.session_info = {
              session_id: currentSessionId,
              project_id: project.id,
              project_name: project.name
            };
          }
          
          ws.send(JSON.stringify(message));
          console.log('📡 Started MQTT monitoring with config:', project?.mqtt_config);
        };

        ws.onclose = () => {
          console.log('🔌 WebSocket disconnected');
          setConnectionStatus('disconnected');
          websocketRef.current = null;
        };

        ws.onerror = (error: any) => {
          console.error('❌ WebSocket connection error:', error);
          setConnectionStatus('error');
          websocketRef.current = null;
        };

        ws.onmessage = (event) => {
          try {
            const message = JSON.parse(event.data);
            
            if (message.type === 'graph_update') {
              console.log('📊 Received graph update:', message.data);
              
              // Track message count for UI
              if (currentSessionId) {
                setMessageCount(prev => prev + 1);
              }
              
              // Update nodes directly with the complete graph data from backend
              if (message.data && message.data.nodes) {
                setNodes(message.data.nodes.map((node: any) => ({
                  ...node,
                  type: 'custom' // Ensure custom node type
                })));
                
                if (message.data.edges) {
                  setEdges(message.data.edges);
                }
              }
            } else if (message.type === 'monitoring_started') {
              console.log('✅ MQTT monitoring started successfully');
              setConnectionStatus('connected');
            } else if (message.type === 'monitoring_stopped') {
              console.log('🛑 MQTT monitoring stopped');
              setConnectionStatus('disconnected');
            }
          } catch (error) {
            console.error('❌ Error parsing WebSocket message:', error);
          }
        };
        
      } catch (error) {
        console.error('❌ Failed to create WebSocket connection:', error);
        setConnectionStatus('error');
      }
    }
    
    // Cleanup function
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
    };
  }, [isMonitoring]); // Only depend on isMonitoring to prevent reconnection loops

  // Separate effect for stopping monitoring
  useEffect(() => {
    if (!isMonitoring) {
      // Stop monitoring
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      setConnectionStatus('disconnected');
      setMessageCount(0);
    }
  }, [isMonitoring]);

  const handleToggleMonitoring = () => {
    if (connectionStatus === 'error') {
      // Retry connection
      testMQTTConnection();
      return;
    }
    
    setIsMonitoring(!isMonitoring);
  };

  const handleStartRecordingSession = async () => {
    if (!project) return;
    
    // Simple session ID generation for now
    const sessionId = `session_${Date.now()}`;
    setCurrentSessionId(sessionId);
    setMessageCount(0);
    console.log('🎬 Started recording session:', sessionId);
    
    // If monitoring is already active, send session info to backend
    if (websocketRef.current && isMonitoring) {
      const message = {
        type: 'start_monitoring',
        config: project.mqtt_config,
        session_info: {
          session_id: sessionId,
          project_id: project.id,
          project_name: project.name
        }
      };
      websocketRef.current.send(JSON.stringify(message));
    }
  };

  const handleStopRecordingSession = () => {
    setCurrentSessionId(null);
    setMessageCount(0);
    console.log('🛑 Stopped recording session');
  };

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">No Project Selected</h2>
          <p className="text-gray-600 mb-4">Please select a project to monitor.</p>
          <button
            onClick={() => navigate('/projects')}
            className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded-lg"
          >
            Go to Projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => navigate('/')}
                className="flex items-center text-gray-600 hover:text-gray-900"
              >
                <ArrowLeft className="w-5 h-5 mr-2" />
                Back to Projects
              </button>
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {project.name}
                </h1>
                <p className="text-sm text-gray-600">
                  Topic: {project.mqtt_config?.topic || 'Not configured'}
                </p>
              </div>
            </div>
            
            {/* Status and Controls */}
            <div className="flex items-center space-x-4">
              {/* Connection Status */}
              <div className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${
                  connectionStatus === 'connected' ? 'bg-green-500' : 
                  connectionStatus === 'connecting' ? 'bg-yellow-500' : 
                  connectionStatus === 'error' ? 'bg-red-500' : 'bg-gray-400'
                }`} />
                <span className="text-sm text-gray-600">
                  {connectionStatus === 'connected' ? 'Connected' : 
                   connectionStatus === 'connecting' ? 'Connecting...' : 
                   connectionStatus === 'error' ? 'Connection Error' : 'Disconnected'}
                </span>
              </div>

              {/* Message Counter */}
              {currentSessionId && (
                <div className="flex items-center space-x-2 bg-blue-50 px-3 py-1 rounded-lg">
                  <Activity className="w-4 h-4 text-blue-600" />
                  <span className="text-sm font-medium text-blue-900">
                    {messageCount} messages
                  </span>
                </div>
              )}

              {/* Recording Controls */}
              {!currentSessionId ? (
                <button
                  onClick={handleStartRecordingSession}
                  disabled={!isMonitoring || connectionStatus !== 'connected'}
                  className="bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
                >
                  <div className="w-2 h-2 bg-white rounded-full" />
                  <span>Start Recording</span>
                </button>
              ) : (
                <button
                  onClick={handleStopRecordingSession}
                  className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
                >
                  <div className="w-2 h-2 bg-white" />
                  <span>Stop Recording</span>
                </button>
              )}

              {/* Start/Stop Monitoring */}
              <button
                onClick={handleToggleMonitoring}
                disabled={isTestingConnection}
                className={`px-4 py-2 rounded-lg flex items-center space-x-2 ${
                  isMonitoring
                    ? 'bg-orange-500 hover:bg-orange-600 text-white'
                    : connectionStatus === 'error'
                    ? 'bg-red-500 hover:bg-red-600 text-white'
                    : 'bg-green-500 hover:bg-green-600 text-white'
                }`}
              >
                {isTestingConnection ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" />
                    <span>Testing...</span>
                  </>
                ) : isMonitoring ? (
                  <>
                    <Pause className="w-4 h-4" />
                    <span>Stop</span>
                  </>
                ) : connectionStatus === 'error' ? (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Retry</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    <span>Start</span>
                  </>
                )}
              </button>

              <button
                onClick={() => navigate(`/projects/${project.id}/configuration`)}
                className="bg-gray-500 hover:bg-gray-600 text-white px-4 py-2 rounded-lg flex items-center space-x-2"
              >
                <Settings className="w-4 h-4" />
                <span>Configure</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {connectionStatus === 'error' ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <h3 className="text-lg font-medium text-red-800 mb-2">Connection Error</h3>
            <p className="text-red-600 mb-4">
              Unable to connect to MQTT broker or backend. Please check:
            </p>
            <ul className="text-left text-red-600 mb-4 space-y-1">
              <li>• Backend server is running</li>
              <li>• MQTT broker ({project.mqtt_config?.broker_host}) is accessible</li>
              <li>• Topic pattern ({project.mqtt_config?.topic}) is correct</li>
              <li>• Cell data publisher is running and publishing to cell/# topics</li>
            </ul>
            <button
              onClick={testMQTTConnection}
              className="bg-red-500 hover:bg-red-600 text-white px-4 py-2 rounded-lg"
            >
              Retry Connection
            </button>
          </div>
        ) : (
          <div className="space-y-6">


            {/* React Flow Visualization */}
            {project.graph_layout && (
              <div className="bg-white rounded-lg shadow" style={{ height: 'calc(100vh - 200px)' }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  onNodeClick={handleNodeClick}
                  fitView
                  fitViewOptions={{ padding: 0.2 }}
                  className="bg-gray-50"
                >
                  <Controls />
                  <MiniMap />
                  <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
                </ReactFlow>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default MonitoringPage; 