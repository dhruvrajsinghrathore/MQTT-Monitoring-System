import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Server, Clock, CheckCircle, AlertCircle, FileText, AlertTriangle, Upload, Trash2 } from 'lucide-react';
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

  // Alert management
  const [alertThresholds, setAlertThresholds] = useState<AlertThreshold[]>([]);
  const [isUploadingCsv, setIsUploadingCsv] = useState(false);

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

  const uploadDocument = async (file: File, equipmentId?: string, sensorType?: string) => {
    if (!project?.id) return;

    setIsUploadingDocument(true);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (equipmentId) formData.append('equipment_id', equipmentId);
      if (sensorType) formData.append('sensor_type', sensorType);

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
                onClick={() => navigate('/')}
                className="mr-4 p-2 hover:bg-gray-100 rounded-lg"
              >
                ← Back to Projects
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
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:border-gray-400 transition-colors">
            <Upload className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 mb-2">Drag and drop files here, or click to select</p>
            <p className="text-sm text-gray-500 mb-4">Supported formats: PDF, DOCX, TXT, MD (max 10MB)</p>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) uploadDocument(file);
              }}
              className="hidden"
              id="document-upload"
              disabled={isUploadingDocument}
            />
            <label
              htmlFor="document-upload"
              className="minimal-button-primary cursor-pointer inline-block"
            >
              {isUploadingDocument ? 'Uploading...' : 'Select Files'}
            </label>
          </div>
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
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-gray-400" />
                      <span className="font-medium text-gray-900">{doc.filename}</span>
                      <span className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded">
                        {doc.file_type?.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-sm text-gray-600 mt-1">
                      {doc.equipment_id && <span>Equipment: {doc.equipment_id} • </span>}
                      {doc.sensor_type && <span>Sensor: {doc.sensor_type} • </span>}
                      {new Date(doc.uploaded_at).toLocaleDateString()} •
                      {(doc.file_size / 1024 / 1024).toFixed(2)} MB
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
              ))}
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
                      <span className={`px-2 py-1 text-xs rounded-full ${
                        threshold.enabled ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                      }`}>
                        {threshold.enabled ? 'Enabled' : 'Disabled'}
                      </span>
                    </div>
                  </div>
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