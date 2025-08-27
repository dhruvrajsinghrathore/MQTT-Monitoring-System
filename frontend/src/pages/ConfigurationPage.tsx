import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Server, Clock, Search, CheckCircle, AlertCircle } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { MQTTConfig, Project, DiscoveredNode } from '../types';
import { getApiUrl, API_ENDPOINTS } from '../config/api';

const ConfigurationPage: React.FC = () => {
  const navigate = useNavigate();
  const { setProject, setDiscoveredNodes } = useProject();
  
  const [config, setConfig] = useState<MQTTConfig>({
    broker_host: 'cloud.dtkit.org',
    broker_port: 1883,
    username: '',
    password: '',
    topic: 'cell/#',
    discovery_duration: 30
  });

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryProgress, setDiscoveryProgress] = useState(0);
  const [discoveredNodes, setDiscoveredNodesState] = useState<DiscoveredNode[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');

  const handleConfigChange = (field: keyof MQTTConfig, value: string | number) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const testConnection = async () => {
    setConnectionStatus('connecting');
    try {
      const response = await fetch(getApiUrl(API_ENDPOINTS.MQTT_TEST), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      
      if (response.ok) {
        setConnectionStatus('connected');
      } else {
        setConnectionStatus('error');
      }
    } catch (error) {
      console.error('Connection test failed:', error);
      setConnectionStatus('error');
    }
  };

  const startDiscovery = async () => {
    setIsDiscovering(true);
    setDiscoveryProgress(0);
    setDiscoveredNodesState([]);

    try {
      // Start discovery process
      const response = await fetch(getApiUrl(API_ENDPOINTS.MQTT_DISCOVER), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });

      if (!response.ok) {
        throw new Error('Failed to start discovery');
      }

      // Show progress and poll for results
      const interval = setInterval(async () => {
        setDiscoveryProgress(prev => {
          const newProgress = prev + (100 / config.discovery_duration);
          return Math.min(newProgress, 100);
        });
      }, 1000);

      // Wait for discovery duration, then get results
      setTimeout(async () => {
        clearInterval(interval);
        setDiscoveryProgress(100);
        
        try {
          // Get actual discovery results from backend
          const statusResponse = await fetch(getApiUrl(API_ENDPOINTS.MQTT_DISCOVERY_STATUS));
          if (statusResponse.ok) {
            const discoveryData = await statusResponse.json();
            setDiscoveredNodesState(discoveryData.discovered_nodes || []);
          }
        } catch (error) {
          console.error('Failed to get discovery results:', error);
          setDiscoveredNodesState([]);
        }
        
        setIsDiscovering(false);
      }, config.discovery_duration * 1000);

    } catch (error) {
      console.error('Discovery failed:', error);
      setIsDiscovering(false);
    }
  };

  const createProject = () => {
    const newProject: Project = {
      id: Date.now().toString(),
      name: `MQTT Project - ${config.broker_host}`,
      mqtt_config: config,
      discovered_nodes: discoveredNodes,
      graph_layout: { nodes: [], edges: [] },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    setProject(newProject);
    setDiscoveredNodes(discoveredNodes);
    navigate('/editor');
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">MQTT Project Configuration</h1>
          <p className="text-gray-600">Configure your MQTT connection and discover available nodes</p>
        </div>

        {/* Configuration Form */}
        <div className="minimal-card p-6 mb-6">
          <div className="flex items-center mb-4">
            <Server className="w-5 h-5 text-gray-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">MQTT Broker Configuration</h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Broker Host</label>
              <input
                type="text"
                className="minimal-input"
                value={config.broker_host}
                onChange={(e) => handleConfigChange('broker_host', e.target.value)}
                placeholder="localhost or mqtt.example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Port</label>
              <input
                type="number"
                className="minimal-input"
                value={config.broker_port}
                onChange={(e) => handleConfigChange('broker_port', parseInt(e.target.value))}
                placeholder="1883"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Username (optional)</label>
              <input
                type="text"
                className="minimal-input"
                value={config.username}
                onChange={(e) => handleConfigChange('username', e.target.value)}
                placeholder="Enter username"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password (optional)</label>
              <input
                type="password"
                className="minimal-input"
                value={config.password}
                onChange={(e) => handleConfigChange('password', e.target.value)}
                placeholder="Enter password"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Topic Pattern</label>
              <input
                type="text"
                className="minimal-input"
                value={config.topic}
                onChange={(e) => handleConfigChange('topic', e.target.value)}
                placeholder="lab/# or device/+/sensor"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Discovery Duration (seconds)</label>
              <input
                type="number"
                className="minimal-input"
                value={config.discovery_duration}
                onChange={(e) => handleConfigChange('discovery_duration', parseInt(e.target.value))}
                placeholder="30"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={testConnection}
              disabled={connectionStatus === 'connecting'}
              className="minimal-button"
            >
              {connectionStatus === 'connecting' ? 'Testing...' : 'Test Connection'}
            </button>
            {connectionStatus === 'connected' && (
              <div className="flex items-center text-green-600">
                <CheckCircle className="w-4 h-4 mr-1" />
                <span className="text-sm">Connected</span>
              </div>
            )}
            {connectionStatus === 'error' && (
              <div className="flex items-center text-red-600">
                <AlertCircle className="w-4 h-4 mr-1" />
                <span className="text-sm">Connection failed</span>
              </div>
            )}
          </div>
        </div>

        {/* Discovery Section */}
        <div className="minimal-card p-6 mb-6">
          <div className="flex items-center mb-4">
            <Search className="w-5 h-5 text-gray-600 mr-2" />
            <h2 className="text-lg font-semibold text-gray-900">Node Discovery</h2>
          </div>

          {!isDiscovering && discoveredNodes.length === 0 && (
            <div className="text-center py-8">
              <Clock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-4">Start discovery to find available MQTT nodes</p>
              <button
                onClick={startDiscovery}
                className="minimal-button-primary"
                disabled={connectionStatus !== 'connected'}
              >
                Start Discovery
              </button>
            </div>
          )}

          {isDiscovering && (
            <div className="text-center py-8">
              <div className="mb-4">
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className="bg-gray-800 h-2 rounded-full transition-all duration-1000"
                    style={{ width: `${discoveryProgress}%` }}
                  ></div>
                </div>
              </div>
              <p className="text-gray-600">Discovering nodes... {Math.round(discoveryProgress)}%</p>
            </div>
          )}

          {discoveredNodes.length > 0 && (
            <div>
              <p className="text-sm text-gray-600 mb-4">Found {discoveredNodes.length} nodes:</p>
              <div className="space-y-2 mb-6">
                {discoveredNodes.map((node) => (
                  <div key={node.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <h3 className="font-medium text-gray-900">{node.equipment_id}</h3>
                      <p className="text-sm text-gray-600">{node.equipment_type} • {node.message_count} messages</p>
                      <p className="text-xs text-gray-500">{node.topics.join(', ')}</p>
                    </div>
                  </div>
                ))}
              </div>
              
              <div className="text-center">
                <button
                  onClick={createProject}
                  className="minimal-button-primary"
                >
                  Create Project & Continue to Editor
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ConfigurationPage; 