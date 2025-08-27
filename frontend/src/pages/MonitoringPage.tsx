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
  const [edges, , onEdgesChange] = useEdgesState(project?.graph_layout?.edges || []);
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [liveData, setLiveData] = useState<{[equipmentId: string]: {[sensorType: string]: SensorReading & {status: string}}}>({});
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);
  
  const websocketRef = useRef<WebSocket | null>(null);

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
            config: project?.mqtt_config
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
            
            if (message.type === 'mqtt_data') {
              console.log('📡 Received MQTT data:', message.data);
              
              // Track message count for UI
              if (currentSessionId) {
                setMessageCount(prev => prev + 1);
              }
              
              // Extract cell ID and field from topic (cell/1/temperature -> equipment_id: "cell_1", sensor_type: "temperature")
              const topic = message.data.topic || '';
              const topicParts = topic.split('/');
              
              if (topicParts.length >= 3 && topicParts[0] === 'cell') {
                const cellId = topicParts[1];
                const fieldName = topicParts[2];
                const equipmentId = `cell_${cellId}`;
                
                // Use the field name as sensor type and get unit from message or fallback
                const sensorType = fieldName;
                const unit = message.data.unit || getUnitForSensorType(sensorType);
                
                setLiveData(prev => ({
                  ...prev,
                  [equipmentId]: {
                    ...prev[equipmentId],
                    [sensorType]: {
                      sensor_type: sensorType,
                      value: message.data.value || 0,
                      unit: unit,
                      timestamp: message.data.timestamp,
                      status: message.data.status || 'active'
                    }
                  }
                }));
              } else {
                console.warn('⚠️ Received message with unexpected topic format:', topic);
              }
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
      setLiveData({});
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
                onClick={() => navigate('/projects')}
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
            {/* Live Data Grid */}
            {Object.keys(liveData).length > 0 && (
            <div className="bg-white rounded-lg shadow p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Live Data</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {Object.entries(liveData).map(([equipmentId, sensors]) => (
                  <div key={equipmentId} className="border rounded-lg p-4">
                    <h4 className="font-medium text-gray-900 mb-3 capitalize">
                      {equipmentId.replace('_', ' ')}
                    </h4>
                    <div className="space-y-2">
                      {Object.entries(sensors).map(([sensorType, data]) => (
                        <div key={sensorType} className="flex justify-between items-center">
                          <span className="text-sm text-gray-600 capitalize">
                            {sensorType.replace(/_/g, ' ')}:
                          </span>
                          <div className="text-right">
                            <span className="font-mono text-sm">
                              {typeof data.value === 'object' 
                                ? JSON.stringify(data.value)
                                : `${data.value} ${data.unit}`
                              }
                            </span>
                            <div className={`text-xs px-2 py-1 rounded-full inline-block ml-2 ${
                              data.status === 'active' ? 'bg-green-100 text-green-800' :
                              data.status === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                              data.status === 'error' ? 'bg-red-100 text-red-800' :
                              'bg-gray-100 text-gray-800'
                            }`}>
                              {data.status}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            )}

            {/* React Flow Visualization */}
            {project.graph_layout && (
              <div className="bg-white rounded-lg shadow" style={{ height: '600px' }}>
                <ReactFlow
                  nodes={nodes.map(node => ({
                    ...node,
                    data: {
                      ...node.data,
                      sensorData: liveData[node.data.equipment_id] || {}
                    }
                  }))}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  nodeTypes={nodeTypes}
                  fitView
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