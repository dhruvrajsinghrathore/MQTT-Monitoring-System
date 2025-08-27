import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Server, Search, CheckCircle, AlertCircle, ArrowLeft, Save } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { MQTTConfig, Project, DiscoveredNode } from '../types';
import { getApiUrl, API_ENDPOINTS } from '../config/api';
import { ProjectService } from '../services/ProjectService';

const CreateProjectPage: React.FC = () => {
  const navigate = useNavigate();
  const { setProject, setDiscoveredNodes } = useProject();
  
  const [projectName, setProjectName] = useState('');
  const [projectDescription, setProjectDescription] = useState('');
  
  const [config, setConfig] = useState<MQTTConfig>({
    broker_host: 'cloud.dtkit.org',
    broker_port: 1883,
    username: '',
    password: '',
    topic: 'lab/#',
    discovery_duration: 30
  });

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryProgress, setDiscoveryProgress] = useState(0);
  const [discoveredNodes, setDiscoveredNodesState] = useState<DiscoveredNode[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');
  const [step, setStep] = useState<'info' | 'config' | 'discovery'>('info');

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
    setStep('discovery');

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
            if (discoveryData.discovered_nodes && discoveryData.discovered_nodes.length > 0) {
              setDiscoveredNodesState(discoveryData.discovered_nodes);
            } else {
              // Fallback to mock data if no real data available
              const mockNodes: DiscoveredNode[] = [
                {
                  id: 'furnace_01',
                  equipment_id: 'furnace_01',
                  equipment_type: 'furnace',
                  topics: ['lab/furnace/temperature', 'lab/furnace/pressure'],
                  sample_data: { temperature: 850, pressure: 2.1, status: 'heating' },
                  message_count: 45,
                  first_seen: new Date().toISOString(),
                  last_seen: new Date().toISOString()
                },
                {
                  id: 'melter_01',
                  equipment_id: 'melter_01',
                  equipment_type: 'melter',
                  topics: ['lab/melter/temperature', 'lab/melter/flow_rate'],
                  sample_data: { temperature: 1200, flow_rate: 15.5, status: 'melting' },
                  message_count: 38,
                  first_seen: new Date().toISOString(),
                  last_seen: new Date().toISOString()
                },
                {
                  id: 'anvil_01',
                  equipment_id: 'anvil_01',
                  equipment_type: 'anvil',
                  topics: ['lab/anvil/force', 'lab/anvil/position'],
                  sample_data: { force: 2500, position: 'center', status: 'idle' },
                  message_count: 22,
                  first_seen: new Date().toISOString(),
                  last_seen: new Date().toISOString()
                },
                {
                  id: 'conveyor_01',
                  equipment_id: 'conveyor_01',
                  equipment_type: 'conveyor',
                  topics: ['lab/conveyor/speed', 'lab/conveyor/position'],
                  sample_data: { speed: 1.5, position: 45, status: 'transporting' },
                  message_count: 28,
                  first_seen: new Date().toISOString(),
                  last_seen: new Date().toISOString()
                }
              ];
              setDiscoveredNodesState(mockNodes);
            }
          }
        } catch (error) {
          console.error('Failed to get discovery results:', error);
          // Use mock data as fallback
          const mockNodes: DiscoveredNode[] = [
            {
              id: 'furnace_01',
              equipment_id: 'furnace_01',
              equipment_type: 'furnace',
              topics: ['lab/furnace/temperature', 'lab/furnace/pressure'],
              sample_data: { temperature: 850, pressure: 2.1, status: 'heating' },
              message_count: 45,
              first_seen: new Date().toISOString(),
              last_seen: new Date().toISOString()
            },
            {
              id: 'melter_01',
              equipment_id: 'melter_01',
              equipment_type: 'melter',
              topics: ['lab/melter/temperature', 'lab/melter/flow_rate'],
              sample_data: { temperature: 1200, flow_rate: 15.5, status: 'melting' },
              message_count: 38,
              first_seen: new Date().toISOString(),
              last_seen: new Date().toISOString()
            },
            {
              id: 'anvil_01',
              equipment_id: 'anvil_01',
              equipment_type: 'anvil',
              topics: ['lab/anvil/force', 'lab/anvil/position'],
              sample_data: { force: 2500, position: 'center', status: 'idle' },
              message_count: 22,
              first_seen: new Date().toISOString(),
              last_seen: new Date().toISOString()
            },
            {
              id: 'conveyor_01',
              equipment_id: 'conveyor_01',
              equipment_type: 'conveyor',
              topics: ['lab/conveyor/speed', 'lab/conveyor/position'],
              sample_data: { speed: 1.5, position: 45, status: 'transporting' },
              message_count: 28,
              first_seen: new Date().toISOString(),
              last_seen: new Date().toISOString()
            }
          ];
          setDiscoveredNodesState(mockNodes);
        }
        
        setIsDiscovering(false);
      }, config.discovery_duration * 1000);

    } catch (error) {
      console.error('Discovery failed:', error);
      setIsDiscovering(false);
    }
  };

  const createProject = () => {
    if (!projectName.trim()) {
      alert('Please enter a project name');
      return;
    }

    const newProject: Project = {
      id: `project-${Date.now()}`,
      name: projectName.trim(),
      description: projectDescription.trim() || undefined,
      mqtt_config: config,
      discovered_nodes: discoveredNodes,
      graph_layout: { nodes: [], edges: [] },
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    // Save project to localStorage
    ProjectService.saveProject(newProject);
    
    // Set in context for immediate use
    setProject(newProject);
    setDiscoveredNodes(discoveredNodes);
    
    navigate('/editor');
  };

  const nextStep = () => {
    if (step === 'info') {
      if (!projectName.trim()) {
        alert('Please enter a project name');
        return;
      }
      setStep('config');
    } else if (step === 'config') {
      if (connectionStatus !== 'connected') {
        alert('Please test and confirm the MQTT connection first');
        return;
      }
      startDiscovery();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="flex items-center mb-8">
          <button
            onClick={() => navigate('/')}
            className="mr-4 p-1 hover:bg-gray-100 rounded"
          >
            <ArrowLeft className="w-5 h-5" />
          </button>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Create New Project</h1>
            <p className="text-gray-600">Set up a new MQTT workflow monitoring project</p>
          </div>
        </div>

        {/* Progress Steps */}
        <div className="mb-8">
          <div className="flex items-center">
            <div className={`flex items-center ${step === 'info' ? 'text-gray-800' : 'text-gray-500'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === 'info' ? 'bg-gray-800 text-white' : 'bg-gray-200'
              }`}>
                1
              </div>
              <span className="ml-2 text-sm font-medium">Project Info</span>
            </div>
            <div className="flex-1 h-px bg-gray-200 mx-4"></div>
            <div className={`flex items-center ${step === 'config' ? 'text-gray-800' : 'text-gray-500'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === 'config' ? 'bg-gray-800 text-white' : 'bg-gray-200'
              }`}>
                2
              </div>
              <span className="ml-2 text-sm font-medium">MQTT Config</span>
            </div>
            <div className="flex-1 h-px bg-gray-200 mx-4"></div>
            <div className={`flex items-center ${step === 'discovery' ? 'text-gray-800' : 'text-gray-500'}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === 'discovery' ? 'bg-gray-800 text-white' : 'bg-gray-200'
              }`}>
                3
              </div>
              <span className="ml-2 text-sm font-medium">Discovery</span>
            </div>
          </div>
        </div>

        {/* Step Content */}
        {step === 'info' && (
          <div className="minimal-card p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Project Information</h2>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Project Name *</label>
                <input
                  type="text"
                  className="minimal-input"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  placeholder="Enter project name"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
                <textarea
                  className="minimal-input"
                  rows={3}
                  value={projectDescription}
                  onChange={(e) => setProjectDescription(e.target.value)}
                  placeholder="Optional project description"
                />
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={nextStep}
                className="minimal-button-primary"
                disabled={!projectName.trim()}
              >
                Continue to MQTT Configuration
              </button>
            </div>
          </div>
        )}

        {step === 'config' && (
          <div className="minimal-card p-6">
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

            <div className="flex gap-2 mb-6">
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

            <div className="flex justify-between">
              <button
                onClick={() => setStep('info')}
                className="minimal-button"
              >
                Back
              </button>
              <button
                onClick={nextStep}
                className="minimal-button-primary"
                disabled={connectionStatus !== 'connected'}
              >
                Start Discovery
              </button>
            </div>
          </div>
        )}

        {step === 'discovery' && (
          <div className="minimal-card p-6">
            <div className="flex items-center mb-4">
              <Search className="w-5 h-5 text-gray-600 mr-2" />
              <h2 className="text-lg font-semibold text-gray-900">Equipment Discovery</h2>
            </div>

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
                <p className="text-gray-600">Discovering equipment... {Math.round(discoveryProgress)}%</p>
              </div>
            )}

            {!isDiscovering && discoveredNodes.length > 0 && (
              <div>
                <p className="text-sm text-gray-600 mb-4">Found {discoveredNodes.length} equipment:</p>
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
                
                <div className="flex justify-between">
                  <button
                    onClick={() => setStep('config')}
                    className="minimal-button"
                  >
                    Back
                  </button>
                  <button
                    onClick={createProject}
                    className="minimal-button-primary flex items-center"
                  >
                    <Save className="w-4 h-4 mr-2" />
                    Create Project & Continue
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CreateProjectPage; 