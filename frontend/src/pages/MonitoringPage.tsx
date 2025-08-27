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
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected'>('disconnected');
  const [liveData, setLiveData] = useState<{[equipmentId: string]: {[sensorType: string]: SensorReading & {status: string}}}>({});
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [isSimulationMode, setIsSimulationMode] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messageCount, setMessageCount] = useState(0);
  
  const websocketRef = useRef<WebSocket | null>(null);
  const simulationIntervalRef = useRef<number | null>(null);

  const getUnitForSensorType = (sensorType: string): string => {
    const unitMap: {[key: string]: string} = {
      'temperature': '°C',
      'pressure': 'PSI',
      'flow': 'L/min',
      'level': '%',
      'speed': 'RPM',
      'vibration': 'Hz',
      'force': 'N',
      'flow_rate': 'L/min',
      'position': 'mm',
      'composition': '%'
    };
    return unitMap[sensorType.toLowerCase()] || '';
  };

  const getSensorTypesForEquipment = (equipmentType: string): string[] => {
    const sensorMap: {[key: string]: string[]} = {
      'furnace': ['temperature', 'composition'],
      'melter': ['temperature', 'flow_rate'],
      'anvil': ['force', 'position'],
      'conveyor': ['speed', 'vibration']
    };
    return sensorMap[equipmentType.toLowerCase()] || ['temperature'];
  };

  // Redirect if no project
  useEffect(() => {
    if (!project) {
      navigate('/');
    }
  }, [project, navigate]);

  const testMQTTConnection = async () => {
    if (!project) return;
    
    setIsTestingConnection(true);
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.MQTT_TEST), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(project.mqtt_config)
      });
      
      if (response.ok) {
        setConnectionStatus('connected');
        // Auto-start monitoring for direct project access
        setIsMonitoring(true);
      } else {
        // Backend is running but MQTT connection failed, use simulation
        console.warn('MQTT broker connection failed, starting simulation mode');
        setIsSimulationMode(true);
        setConnectionStatus('connected');
        setIsMonitoring(true);
      }
    } catch (error) {
      // Backend is not running, use simulation mode immediately
      console.warn('Backend not available, starting simulation mode:', error);
      setIsSimulationMode(true);
      setConnectionStatus('connected');
      setIsMonitoring(true);
    } finally {
      setIsTestingConnection(false);
    }
  };

  const startSimulation = () => {
    if (!project?.discovered_nodes || simulationIntervalRef.current) return;
    
    console.log('Starting simulation mode');
    
    // Generate mock data for each discovered node
    const interval = window.setInterval(() => {
      project.discovered_nodes.forEach(node => {
        // Generate multiple sensor types for each equipment
        const sensorTypes = getSensorTypesForEquipment(node.equipment_type);
        const equipmentData: {[sensorType: string]: SensorReading & {status: string}} = {};
        
        sensorTypes.forEach((sensorType: string) => {
          const mockValue = Math.random() * 100;
          const sensorData = {
            sensor_type: sensorType,
            value: sensorType === 'composition' 
              ? { iron: Math.floor(Math.random() * 30 + 60), carbon: Math.floor(Math.random() * 5 + 2) }
              : mockValue,
            unit: getUnitForSensorType(sensorType),
            timestamp: new Date().toISOString(),
            status: mockValue > 80 ? 'warning' : mockValue > 95 ? 'error' : 'active'
          };
          
          equipmentData[sensorType] = sensorData;
          
          // In simulation mode, we just track message count for UI
          // Backend handles actual storage when real MQTT is connected
          if (currentSessionId) {
            setMessageCount(prev => prev + 1);
          }
        });
        
        setLiveData(prev => ({
          ...prev,
          [node.equipment_id]: equipmentData
        }));
      });
    }, 2000); // Update every 2 seconds
    
    simulationIntervalRef.current = interval;
  };



  // Load project and test connection on mount
  useEffect(() => {
    if (project) {
      testMQTTConnection();
    }
  }, [project]);

  // Handle monitoring start/stop
  useEffect(() => {
    if (isMonitoring && connectionStatus === 'connected') {
      if (isSimulationMode) {
        // Use simulation mode
        console.log('Starting in simulation mode');
        startSimulation();
      } else {
        // Try WebSocket connection
        setConnectionStatus('connecting');
        
        try {
          // Connect to backend WebSocket for live data
          const wsUrl = WEBSOCKET_URL.replace('http', 'ws') + '/ws';
          const ws = new WebSocket(wsUrl);
          
          ws.onopen = () => {
            console.log('WebSocket connected');
            setConnectionStatus('connected');
            websocketRef.current = ws;
            // Send MQTT configuration to start monitoring
            // Include session info if we're recording
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
          };

          ws.onclose = () => {
            console.log('WebSocket disconnected');
            setConnectionStatus('disconnected');
            websocketRef.current = null;
          };

          ws.onerror = (error: any) => {
            console.error('WebSocket connection error:', error);
            
            // Fallback to simulation mode
            console.log('Falling back to simulation mode');
            setIsSimulationMode(true);
            setConnectionStatus('connected');
            startSimulation();
          };

          ws.onmessage = (event) => {
            try {
              const message = JSON.parse(event.data);
              
              if (message.type === 'mqtt_data') {
                console.log('Received MQTT data:', message.data);
                
                // Note: Message storage is now handled automatically by the backend
                // when monitoring starts. We just track the count for UI purposes.
                if (currentSessionId) {
                  setMessageCount(prev => prev + 1);
                }
                
                // Update live data for the specific equipment and sensor type
                const equipmentId = message.data.equipment_id;
                const sensorType = message.data.sensor_type || 'unknown';
                setLiveData(prev => ({
                  ...prev,
                  [equipmentId]: {
                    ...prev[equipmentId],
                    [sensorType]: {
                      sensor_type: sensorType,
                      value: message.data.value || 0,
                      unit: getUnitForSensorType(sensorType),
                      timestamp: message.data.timestamp,
                      status: message.data.status || 'active'
                    }
                  }
                }));
              }
            } catch (error) {
              console.error('Error parsing WebSocket message:', error);
            }
          };
          
        } catch (error) {
          console.error('Failed to create WebSocket connection:', error);
          // Fallback to simulation mode
          setIsSimulationMode(true);
          setConnectionStatus('connected');
          startSimulation();
        }
      }
    }
    
    // Cleanup function
    return () => {
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      if (simulationIntervalRef.current) {
        clearInterval(simulationIntervalRef.current);
        simulationIntervalRef.current = null;
      }
    };
  }, [isMonitoring, isSimulationMode]); // Removed connectionStatus and project to prevent re-renders

  // Separate effect for stopping monitoring
  useEffect(() => {
    if (!isMonitoring) {
      // Stop monitoring
      if (websocketRef.current) {
        websocketRef.current.close();
        websocketRef.current = null;
      }
      if (simulationIntervalRef.current) {
        clearInterval(simulationIntervalRef.current);
        simulationIntervalRef.current = null;
      }
    }
  }, [isMonitoring]);

  const toggleMonitoring = async () => {
    const newMonitoringState = !isMonitoring;
    setIsMonitoring(newMonitoringState);

    if (newMonitoringState && project) {
      try {
        // Start a new recording session
        const sessionId = await DatabaseService.startSession(project.id, project.name);
        setCurrentSessionId(sessionId);
        setMessageCount(0);
        console.log(`🎬 Started recording session for project: ${project.name}`);
      } catch (error) {
        console.error('Failed to start recording session:', error);
      }
    } else if (currentSessionId && project) {
      try {
        // Stop the current recording session
        await DatabaseService.stopSession(project.id, currentSessionId);
        console.log(`🛑 Stopped recording session. Total messages: ${messageCount}`);
        setCurrentSessionId(null);
      } catch (error) {
        console.error('Failed to stop recording session:', error);
      }
    }
  };

  // Update node styles and data based on live data
  useEffect(() => {
    if (nodes.length > 0) {
      const updatedNodes = nodes.map(node => {
        const equipmentId = node.data?.label || node.data?.equipment_id;
        const equipmentSensors = liveData[equipmentId];
        
        if (equipmentSensors && Object.keys(equipmentSensors).length > 0) {
          // Convert all sensor types to array format
          const sensorsArray = Object.values(equipmentSensors);
          const latestSensor = sensorsArray[sensorsArray.length - 1]; // Use latest for overall status
          
          return {
            ...node,
            type: 'custom', // Ensure all nodes use custom type
            data: {
              ...node.data,
              equipment_id: equipmentId,
              equipment_type: node.data?.equipment_type || sensorsArray[0].sensor_type,
              sensors: sensorsArray, // Pass all sensors, not just one
              status: latestSensor.status,
              last_updated: latestSensor.timestamp
            }
          };
        }
        
        return {
          ...node,
          type: 'custom' // Ensure all nodes use custom type
        };
      });
      
      setNodes(updatedNodes);
    }
  }, [liveData, setNodes]);



  if (!project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-medium text-gray-900 mb-4">No Project Selected</h2>
          <p className="text-gray-600 mb-6">Please select a project to monitor.</p>
          <button
            onClick={() => navigate('/')}
            className="minimal-button-primary"
          >
            Back to Projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/')}
              className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg"
            >
              <ArrowLeft className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-xl font-medium text-gray-900">
                {project.name} {isSimulationMode && '(Simulation)'}
              </h1>
              <p className="text-sm text-gray-600">
                Live monitoring • {project.mqtt_config.broker_host}
              </p>
            </div>
          </div>
          
          <div className="flex items-center space-x-4">
            {/* Connection Status */}
            <div className={`flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium ${
              connectionStatus === 'connected' 
                ? 'bg-green-100 text-green-800' 
                : connectionStatus === 'connecting'
                ? 'bg-yellow-100 text-yellow-800'
                : 'bg-red-100 text-red-800'
            }`}>
              <Activity className="w-4 h-4" />
              <span>{connectionStatus === 'connected' ? 'Connected' : connectionStatus === 'connecting' ? 'Connecting' : 'Disconnected'}</span>
            </div>

            {/* Recording Status & Message Count */}
            {currentSessionId && (
              <div className="flex items-center space-x-2 px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse"></div>
                <span>Recording • {messageCount} messages</span>
              </div>
            )}
            
            {/* Monitoring Controls */}
            <button
              onClick={toggleMonitoring}
              disabled={isTestingConnection}
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium ${
                isMonitoring 
                  ? 'bg-red-100 text-red-700 hover:bg-red-200' 
                  : 'bg-green-100 text-green-700 hover:bg-green-200'
              }`}
            >
              {isMonitoring ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              <span>{isMonitoring ? 'Stop' : 'Start'}</span>
            </button>
            
            <button
              onClick={() => navigate('/editor', { state: { project } })}
              className="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 hover:bg-gray-200 rounded-lg font-medium"
            >
              <Settings className="w-4 h-4" />
              <span>Edit</span>
            </button>
          </div>
        </div>
      </div>

            {/* Main Content - Full Width Graph */}
      <div className="h-[calc(100vh-80px)] relative">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          className="bg-gray-50"
        >
          <Controls />
          <MiniMap />
          <Background variant={BackgroundVariant.Dots as BackgroundVariant} gap={12} size={1} />
        </ReactFlow>
          
          {/* Status overlay when not monitoring */}
          {!isMonitoring && (
            <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center">
              <div className="bg-white p-6 rounded-lg shadow-lg border border-gray-200 text-center">
                <h3 className="text-lg font-medium text-gray-900 mb-2">Monitoring Paused</h3>
                <p className="text-gray-600 mb-4">
                  Click "Start" to begin receiving {isSimulationMode ? 'simulated' : 'live'} MQTT data
                </p>
                {isSimulationMode && (
                  <p className="text-sm text-yellow-600 mb-4">
                    Running in simulation mode (backend not available)
                  </p>
                )}
                <button
                  onClick={toggleMonitoring}
                  className="minimal-button-primary flex items-center mx-auto"
                >
                  <Play className="w-4 h-4 mr-2" />
                  Start Monitoring
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  };

export default MonitoringPage; 