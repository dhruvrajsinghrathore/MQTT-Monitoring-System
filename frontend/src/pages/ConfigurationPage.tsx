import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Server, Clock, CheckCircle, AlertCircle, FileText, AlertTriangle, Upload, Trash2, Edit, Plus } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { MQTTConfig, Project, DiscoveredNode, DomainDocument, AlertThreshold } from '../types';
import { getApiUrl, API_ENDPOINTS } from '../config/api';
import { ProjectService } from '../services/ProjectService';

const ConfigurationPage: React.FC = () => {
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const { project, setProject, setDiscoveredNodes } = useProject();
  
  const [config, setConfig] = useState<MQTTConfig>({
    broker_host: 'cloud.dtkit.org',
    broker_port: 1883,
    username: '',
    password: '',
    topic: '#',  // Universal topic pattern - subscribes to everything by default
    discovery_duration: 30
  });

  const [isDiscovering, setIsDiscovering] = useState(false);
  const [discoveryProgress, setDiscoveryProgress] = useState(0);
  const [discoveredNodes, setDiscoveredNodesState] = useState<DiscoveredNode[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');

  // Tab management
  const [activeTab, setActiveTab] = useState<'mqtt' | 'documents' | 'alerts'>('mqtt');

  // Document management
  const [documents, setDocuments] = useState<DomainDocument[]>([]);
  const [isUploadingDocument, setIsUploadingDocument] = useState(false);
  
  // Document upload affiliation state
  const [affiliationType, setAffiliationType] = useState<'general' | 'equipment' | 'sensor'>('general');
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string>('');
  const [selectedSensorType, setSelectedSensorType] = useState<string>('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);

  // Alert management
  const [alertThresholds, setAlertThresholds] = useState<AlertThreshold[]>([]);
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);

  // Edit threshold state
  const [editingThreshold, setEditingThreshold] = useState<AlertThreshold | null>(null);
  const [editMinValue, setEditMinValue] = useState('');
  const [editMaxValue, setEditMaxValue] = useState('');

  // Add threshold state
  const [newTopicName, setNewTopicName] = useState('');
  const [newMinValue, setNewMinValue] = useState('');
  const [newMaxValue, setNewMaxValue] = useState('');

  const handleConfigChange = (field: keyof MQTTConfig, value: string | number) => {
    setConfig(prev => ({
      ...prev,
      [field]: value
    }));
  };

  // Load project if not loaded or different project
  useEffect(() => {
    const loadProject = async () => {
      if (projectId && (!project || project.id !== projectId)) {
        try {
          const loadedProject = await ProjectService.getProject(projectId);
          if (loadedProject) {
            setProject(loadedProject);
          } else {
            // Project not found, redirect to projects page
            navigate('/');
          }
        } catch (error) {
          console.error('Failed to load project:', error);
          navigate('/');
        }
      }
    };

    loadProject();
  }, [projectId, project, setProject, navigate]);

  // Load documents and alerts when project changes
  useEffect(() => {
    if (project?.id) {
      loadDocuments();
      loadAlertThresholds();
    }
  }, [project?.id]);

  const loadDocuments = async () => {
    if (!project?.id) return;

    try {
      const response = await fetch(
        getApiUrl(API_ENDPOINTS.DOCUMENTS_LIST).replace('{project_id}', project.id)
      );
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      }
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  };

  const loadAlertThresholds = async () => {
    if (!project?.id) return;

    try {
      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG).replace('{project_id}', project.id)
      );
      if (response.ok) {
        const data = await response.json();
        setAlertThresholds(data.alert_thresholds || []);
      }
    } catch (error) {
      console.error('Failed to load alert thresholds:', error);
    }
  };

  const handleFileSelect = (file: File) => {
    setPendingFile(file);
  };

  const handleUploadWithAffiliation = async () => {
    if (!project?.id || !pendingFile) return;

    setIsUploadingDocument(true);

    try {
      const formData = new FormData();
      formData.append('file', pendingFile);
      
      // Add affiliation based on type
      if (affiliationType === 'equipment' || affiliationType === 'sensor') {
        if (selectedEquipmentId) {
          formData.append('equipment_id', selectedEquipmentId);
        }
      }
      if (affiliationType === 'sensor') {
        if (selectedSensorType) {
          formData.append('sensor_type', selectedSensorType);
        }
      }

      const response = await fetch(
        getApiUrl(API_ENDPOINTS.DOCUMENTS_UPLOAD).replace('{project_id}', project.id),
        {
          method: 'POST',
          body: formData
        }
      );

      if (response.ok) {
        const result = await response.json();
        await loadDocuments(); // Refresh document list
        console.log('Document uploaded successfully:', result);
        
        // Reset form
        setPendingFile(null);
        setAffiliationType('general');
        setSelectedEquipmentId('');
        setSelectedSensorType('');
      } else {
        throw new Error(`Upload failed: ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to upload document:', error);
      alert(`Failed to upload document: ${error}`);
    } finally {
      setIsUploadingDocument(false);
    }
  };

  const cancelUpload = () => {
    setPendingFile(null);
    setAffiliationType('general');
    setSelectedEquipmentId('');
    setSelectedSensorType('');
  };

  // Get unique equipment IDs from discovered nodes
  const getEquipmentOptions = (): string[] => {
    if (!project?.discovered_nodes) return [];
    const equipmentIds = new Set<string>();
    project.discovered_nodes.forEach(node => {
      if (node.equipment_id) {
        equipmentIds.add(node.equipment_id);
      }
    });
    return Array.from(equipmentIds).sort();
  };

  // Get sensor types from discovered nodes for selected equipment
  const getSensorOptions = (): string[] => {
    if (!project?.discovered_nodes || !selectedEquipmentId) return [];
    const sensorTypes = new Set<string>();
    project.discovered_nodes.forEach(node => {
      if (node.equipment_id === selectedEquipmentId && node.topics) {
        node.topics.forEach(topic => {
          // Extract sensor name from topic (last part)
          const parts = topic.split('/');
          if (parts.length > 0) {
            sensorTypes.add(parts[parts.length - 1]);
          }
        });
      }
    });
    return Array.from(sensorTypes).sort();
  };

  const deleteDocument = async (docId: string) => {
    if (!project?.id) return;

    try {
      const response = await fetch(
        getApiUrl(API_ENDPOINTS.DOCUMENTS_DELETE)
          .replace('{project_id}', project.id)
          .replace('{doc_id}', docId),
        { method: 'DELETE' }
      );

      if (response.ok) {
        await loadDocuments(); // Refresh document list
        console.log('Document deleted successfully');
      } else {
        throw new Error(`Delete failed: ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to delete document:', error);
      alert(`Failed to delete document: ${error}`);
    }
  };

  const uploadCsvThresholds = async (file: File) => {
    if (!project?.id) return;

    setIsUploadingCsv(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG).replace('{project_id}', project.id),
        {
          method: 'POST',
          body: formData
        }
      );

      if (response.ok) {
        const result = await response.json();
        await loadAlertThresholds(); // Refresh thresholds list
        console.log('CSV uploaded successfully:', result);
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || `Upload failed: ${response.status}`);
      }
    } catch (error) {
      console.error('Failed to upload CSV:', error);
      alert(`Failed to upload CSV: ${error}`);
    } finally {
      setIsUploadingCsv(false);
    }
  };

  // Threshold editing functions
  const startEditing = (threshold: AlertThreshold) => {
    setEditingThreshold(threshold);
    setEditMinValue(threshold.min_value?.toString() || '');
    setEditMaxValue(threshold.max_value?.toString() || '');
  };

  const cancelEditing = () => {
    setEditingThreshold(null);
    setEditMinValue('');
    setEditMaxValue('');
  };

  const saveThresholdEdit = async () => {
    if (!project?.id || !editingThreshold) return;

    try {
      const minValue = editMinValue.trim() ? parseFloat(editMinValue) : null;
      const maxValue = editMaxValue.trim() ? parseFloat(editMaxValue) : null;

      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG).replace('{project_id}', project.id).replace('/config', `/config/${editingThreshold.id}`),
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            min_value: minValue,
            max_value: maxValue
          })
        }
      );

      if (response.ok) {
        // Update local state
        setAlertThresholds(prev => prev.map(t =>
          t.id === editingThreshold.id
            ? { ...t, min_value: minValue, max_value: maxValue }
            : t
        ));
        cancelEditing();
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to update threshold');
      }
    } catch (error) {
      console.error('Failed to update threshold:', error);
      alert(`Failed to update threshold: ${error}`);
    }
  };

  const deleteThreshold = async (thresholdId: string) => {
    if (!project?.id) return;

    if (!confirm('Are you sure you want to delete this alert threshold?')) {
      return;
    }

    try {
      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG).replace('{project_id}', project.id).replace('/config', `/config/${thresholdId}`),
        { method: 'DELETE' }
      );

      if (response.ok) {
        // Update local state
        setAlertThresholds(prev => prev.filter(t => t.id !== thresholdId));
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete threshold');
      }
    } catch (error) {
      console.error('Failed to delete threshold:', error);
      alert(`Failed to delete threshold: ${error}`);
    }
  };

  const toggleThreshold = async (thresholdId: string) => {
    if (!project?.id) return;

    try {
      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG).replace('{project_id}', project.id).replace('/config', `/config/${thresholdId}/toggle`),
        { method: 'PATCH' }
      );

      if (response.ok) {
        // Update local state
        setAlertThresholds(prev => prev.map(t =>
          t.id === thresholdId ? { ...t, enabled: !t.enabled } : t
        ));
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to toggle threshold');
      }
    } catch (error) {
      console.error('Failed to toggle threshold:', error);
      alert(`Failed to toggle threshold: ${error}`);
    }
  };

  const addThreshold = async () => {
    if (!project?.id || !newTopicName.trim()) {
      alert('Please enter a topic name');
      return;
    }

    try {
      const minValue = newMinValue.trim() ? parseFloat(newMinValue) : null;
      const maxValue = newMaxValue.trim() ? parseFloat(newMaxValue) : null;

      const response = await fetch(
        getApiUrl(API_ENDPOINTS.ALERTS_CONFIG_THRESHOLD).replace('{project_id}', project.id),
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            topic_name: newTopicName.trim(),
            min_value: minValue,
            max_value: maxValue
          })
        }
      );

      if (response.ok) {
        const result = await response.json();
        // Update local state
        const newThreshold: AlertThreshold = {
          id: result.id || Date.now().toString(),
          project_id: project.id,
          topic_name: newTopicName.trim(),
          sensor_type: newTopicName.split('/').pop() || 'unknown',
          min_value: minValue,
          max_value: maxValue,
          enabled: true
        };
        setAlertThresholds(prev => [...prev, newThreshold]);

        // Clear form
        setNewTopicName('');
        setNewMinValue('');
        setNewMaxValue('');
      } else {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to add threshold');
      }
    } catch (error) {
      console.error('Failed to add threshold:', error);
      alert(`Failed to add threshold: ${error}`);
    }
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
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto py-8 px-4">
        <div className="bg-white rounded-lg shadow">
          <div className="flex items-center justify-between p-6 border-b">
            <div className="flex items-center">
              <button
                onClick={() => navigate(`/monitor/${projectId}`)}
                className="mr-4 p-2 hover:bg-gray-100 rounded-lg"
              >
                ← Back to Monitoring
              </button>
              <h1 className="text-2xl font-bold text-gray-900">Project Configuration</h1>
              {project && (
                <span className="ml-3 text-sm text-gray-600">
                  {project.name}
                </span>
              )}
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b">
            <nav className="flex">
              <button
                onClick={() => setActiveTab('mqtt')}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === 'mqtt'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Server className="w-4 h-4 inline mr-2" />
                MQTT Configuration
              </button>
              <button
                onClick={() => setActiveTab('documents')}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === 'documents'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <FileText className="w-4 h-4 inline mr-2" />
                Domain Knowledge ({documents.length})
              </button>
              <button
                onClick={() => setActiveTab('alerts')}
                className={`px-6 py-3 text-sm font-medium border-b-2 ${
                  activeTab === 'alerts'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <AlertTriangle className="w-4 h-4 inline mr-2" />
                Alert Thresholds ({alertThresholds.length})
              </button>
            </nav>
          </div>

          <div className="p-6">
            {/* MQTT Configuration Tab */}
            {activeTab === 'mqtt' && (
              <div>
                <div className="mb-6">
                  <h2 className="text-lg font-semibold text-gray-900 mb-2">MQTT Connection Settings</h2>
                  <p className="text-sm text-gray-600">Configure your MQTT broker connection and discovery settings.</p>
                </div>

                {/* MQTT Configuration Form */}
                <div className="minimal-card p-6 mb-6">
                  <div className="flex items-center mb-4">
                    <Server className="w-5 h-5 text-gray-600 mr-2" />
                    <h3 className="text-lg font-semibold text-gray-900">MQTT Broker Configuration</h3>
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
                  <CheckCircle className="w-5 h-5 text-green-600" />
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
    )}

    {/* Documents Tab */}
    {activeTab === 'documents' && (
      <div>
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Domain Knowledge Documents</h2>
          <p className="text-sm text-gray-600">Upload and manage documents that CrewAI agents can search for domain knowledge.</p>
        </div>

        {/* Document Upload */}
        <div className="minimal-card p-6 mb-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Upload Documents</h3>
          
          {!pendingFile ? (
            /* File Selection */
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
              <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 mb-2">Drag and drop files here, or click to select</p>
              <p className="text-sm text-gray-500 mb-4">Supported formats: PDF, DOCX, TXT, MD (max 10MB)</p>
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) handleFileSelect(file);
                }}
                className="hidden"
                id="document-upload"
                disabled={isUploadingDocument}
              />
              <label
                htmlFor="document-upload"
                className="minimal-button-primary cursor-pointer inline-block"
              >
                Select File
              </label>
            </div>
          ) : (
            /* Affiliation Selection */
            <div className="space-y-4">
              {/* Selected File Info */}
              <div className="flex items-center justify-between p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center gap-2">
                  <FileText className="w-5 h-5 text-blue-600" />
                  <span className="font-medium text-blue-900">{pendingFile.name}</span>
                  <span className="text-sm text-blue-600">
                    ({(pendingFile.size / 1024 / 1024).toFixed(2)} MB)
                  </span>
                </div>
                <button
                  onClick={cancelUpload}
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  Change file
                </button>
              </div>

              {/* Affiliation Type Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Document Affiliation
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  Choose what this document is about. This helps the AI find relevant information.
                </p>
                <select
                  value={affiliationType}
                  onChange={(e) => {
                    setAffiliationType(e.target.value as 'general' | 'equipment' | 'sensor');
                    setSelectedEquipmentId('');
                    setSelectedSensorType('');
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="general">General (applies to entire system)</option>
                  <option value="equipment">Equipment-specific (applies to one subsystem)</option>
                  <option value="sensor">Sensor-specific (applies to one sensor)</option>
                </select>
              </div>

              {/* Equipment Selector (for equipment and sensor types) */}
              {(affiliationType === 'equipment' || affiliationType === 'sensor') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Equipment / Subsystem
                  </label>
                  <select
                    value={selectedEquipmentId}
                    onChange={(e) => {
                      setSelectedEquipmentId(e.target.value);
                      setSelectedSensorType('');
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">Select equipment...</option>
                    {getEquipmentOptions().map(equipmentId => (
                      <option key={equipmentId} value={equipmentId}>
                        {equipmentId}
                      </option>
                    ))}
                  </select>
                  {getEquipmentOptions().length === 0 && (
                    <p className="text-xs text-amber-600 mt-1">
                      No equipment discovered yet. Run MQTT discovery first, or type equipment ID manually.
                    </p>
                  )}
                  {/* Manual input fallback */}
                  {getEquipmentOptions().length === 0 && (
                    <input
                      type="text"
                      value={selectedEquipmentId}
                      onChange={(e) => setSelectedEquipmentId(e.target.value)}
                      placeholder="Enter equipment ID manually"
                      className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              )}

              {/* Sensor Selector (only for sensor type) */}
              {affiliationType === 'sensor' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Sensor Type
                  </label>
                  <select
                    value={selectedSensorType}
                    onChange={(e) => setSelectedSensorType(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    disabled={!selectedEquipmentId}
                  >
                    <option value="">Select sensor...</option>
                    {getSensorOptions().map(sensorType => (
                      <option key={sensorType} value={sensorType}>
                        {sensorType}
                      </option>
                    ))}
                  </select>
                  {!selectedEquipmentId && (
                    <p className="text-xs text-gray-500 mt-1">
                      Select equipment first to see available sensors
                    </p>
                  )}
                  {selectedEquipmentId && getSensorOptions().length === 0 && (
                    <input
                      type="text"
                      value={selectedSensorType}
                      onChange={(e) => setSelectedSensorType(e.target.value)}
                      placeholder="Enter sensor type manually"
                      className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                  )}
                </div>
              )}

              {/* Upload Button */}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  onClick={cancelUpload}
                  className="px-4 py-2 text-gray-600 hover:text-gray-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleUploadWithAffiliation}
                  disabled={isUploadingDocument || 
                    (affiliationType === 'equipment' && !selectedEquipmentId) ||
                    (affiliationType === 'sensor' && (!selectedEquipmentId || !selectedSensorType))
                  }
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors disabled:bg-gray-400 disabled:cursor-not-allowed"
                >
                  {isUploadingDocument ? 'Uploading...' : 'Upload Document'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Documents List */}
        <div className="minimal-card p-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Uploaded Documents ({documents.length})</h3>
          {documents.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No documents uploaded yet</p>
              <p className="text-sm">Upload documents to enable CrewAI domain knowledge search</p>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => {
                // Determine affiliation level for badge
                const getAffiliationBadge = () => {
                  if (doc.sensor_type && doc.equipment_id) {
                    return { label: 'Sensor', color: 'bg-purple-100 text-purple-800' };
                  } else if (doc.equipment_id) {
                    return { label: 'Equipment', color: 'bg-blue-100 text-blue-800' };
                  }
                  return { label: 'General', color: 'bg-green-100 text-green-800' };
                };
                const badge = getAffiliationBadge();

                return (
                  <div key={doc.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <FileText className="w-4 h-4 text-gray-400" />
                        <span className="font-medium text-gray-900">{doc.filename}</span>
                        <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                          {doc.file_type?.toUpperCase()}
                        </span>
                        <span className={`text-xs px-2 py-1 rounded ${badge.color}`}>
                          {badge.label}
                        </span>
                      </div>
                      <div className="text-sm text-gray-600 mt-1">
                        {doc.equipment_id && (
                          <span className="inline-flex items-center mr-2">
                            <span className="text-gray-500">Equipment:</span>
                            <span className="ml-1 font-medium">{doc.equipment_id}</span>
                          </span>
                        )}
                        {doc.sensor_type && (
                          <span className="inline-flex items-center mr-2">
                            <span className="text-gray-500">Sensor:</span>
                            <span className="ml-1 font-medium">{doc.sensor_type}</span>
                          </span>
                        )}
                        <span className="text-gray-400">•</span>
                        <span className="ml-2">{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                        <span className="text-gray-400 mx-1">•</span>
                        <span>{(doc.file_size / 1024 / 1024).toFixed(2)} MB</span>
                      </div>
                    </div>
                    <button
                      onClick={() => deleteDocument(doc.id)}
                      className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                      title="Delete document"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    )}

    {/* Alerts Tab */}
    {activeTab === 'alerts' && (
      <div>
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Alert Thresholds</h2>
          <p className="text-sm text-gray-600">Configure sensor value thresholds that trigger alerts during monitoring.</p>
        </div>

        {/* CSV Upload */}
        <div className="minimal-card p-6 mb-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Upload Alert Thresholds</h3>
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
            <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 mb-2">Upload CSV file with alert thresholds</p>
            <p className="text-sm text-gray-500 mb-4">
              CSV should have columns: topic_name, min_value, max_value<br/>
              Example: cell/1/temperature, 20.0, 80.0
            </p>
            <input
              type="file"
              accept=".csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadCsvThresholds(file);
              }}
              className="hidden"
              id="csv-upload"
              disabled={isUploadingCsv}
            />
            <label
              htmlFor="csv-upload"
              className="minimal-button-primary cursor-pointer inline-block"
            >
              {isUploadingCsv ? 'Uploading...' : 'Select CSV File'}
            </label>
          </div>
        </div>

        {/* Add New Threshold */}
        <div className="minimal-card p-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Add New Threshold</h3>
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Topic Name
                </label>
                <input
                  type="text"
                  value={newTopicName}
                  onChange={(e) => setNewTopicName(e.target.value)}
                  placeholder="e.g., smr/compressor/temperature"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Minimum Value
                </label>
                <input
                  type="number"
                  step="any"
                  value={newMinValue}
                  onChange={(e) => setNewMinValue(e.target.value)}
                  placeholder="Optional"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Maximum Value
                </label>
                <input
                  type="number"
                  step="any"
                  value={newMaxValue}
                  onChange={(e) => setNewMaxValue(e.target.value)}
                  placeholder="Optional"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={addThreshold}
                className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Add Threshold
              </button>
            </div>
          </div>
        </div>

        {/* Thresholds List */}
        <div className="minimal-card p-6">
          <h3 className="text-md font-semibold text-gray-900 mb-4">Alert Thresholds ({alertThresholds.length})</h3>
          {alertThresholds.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <AlertTriangle className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No alert thresholds configured</p>
              <p className="text-sm">Upload a CSV file to configure sensor alert thresholds</p>
            </div>
          ) : (
            <div className="space-y-3">
              {alertThresholds.map((threshold) => (
                <div key={threshold.id} className="p-4 border border-gray-200 rounded-lg">
                  {editingThreshold?.id === threshold.id ? (
                    // Edit mode
                    <div className="space-y-3">
                      <div className="font-medium text-gray-900">{threshold.topic_name}</div>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Minimum Value
                          </label>
                          <input
                            type="number"
                            step="any"
                            value={editMinValue}
                            onChange={(e) => setEditMinValue(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="Leave empty for no minimum"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Maximum Value
                          </label>
                          <input
                            type="number"
                            step="any"
                            value={editMaxValue}
                            onChange={(e) => setEditMaxValue(e.target.value)}
                            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                            placeholder="Leave empty for no maximum"
                          />
                        </div>
                      </div>
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={cancelEditing}
                          className="px-3 py-1 text-sm text-gray-600 hover:text-gray-800 transition-colors"
                        >
                          Cancel
                        </button>
                        <button
                          onClick={saveThresholdEdit}
                          className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                  ) : (
                    // Display mode
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-900">{threshold.topic_name}</div>
                        <div className="text-sm text-gray-600">
                          Sensor: {threshold.sensor_type}
                          {threshold.min_value !== null && ` • Min: ${threshold.min_value}`}
                          {threshold.max_value !== null && ` • Max: ${threshold.max_value}`}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => toggleThreshold(threshold.id)}
                          className={`px-2 py-1 text-xs rounded-full cursor-pointer transition-colors ${
                            threshold.enabled ? 'bg-green-100 text-green-800 hover:bg-green-200' : 'bg-gray-100 text-gray-800 hover:bg-gray-200'
                          }`}
                          title={threshold.enabled ? 'Disable threshold' : 'Enable threshold'}
                        >
                          {threshold.enabled ? 'Enabled' : 'Disabled'}
                        </button>
                        <button
                          onClick={() => startEditing(threshold)}
                          className="p-1 text-gray-400 hover:text-blue-600 transition-colors"
                          title="Edit threshold"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => deleteThreshold(threshold.id)}
                          className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                          title="Delete threshold"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )}
  </div>
</div>
</div>
</div>
);

};

export default ConfigurationPage; 