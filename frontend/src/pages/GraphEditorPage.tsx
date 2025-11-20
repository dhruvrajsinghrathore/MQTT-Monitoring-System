import React, { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  ReactFlow,
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Node,
  Edge,
  Connection,
  ReactFlowProvider,
  ReactFlowInstance,
  BackgroundVariant
} from 'reactflow';
import { Save, Play, ArrowLeft, Plus, Grid, RefreshCw } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { DiscoveredNode, Project } from '../types';
import { ProjectService } from '../services/ProjectService';
import { getApiUrl, API_ENDPOINTS } from '../config/api';

import 'reactflow/dist/style.css';

const GraphEditorPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { project: contextProject, updateGraphLayout } = useProject();
  
  // Get project from location state or context
  const project: Project | null = (location.state as any)?.project || contextProject;
  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const [reactFlowInstance, setReactFlowInstance] = useState<ReactFlowInstance | null>(null);

  // Initialize nodes and edges from project
  const [nodes, setNodes, onNodesChange] = useNodesState(project?.graph_layout?.nodes || []);
  const [edges, setEdges, onEdgesChange] = useEdgesState(project?.graph_layout?.edges || []);
  const [isRediscovering, setIsRediscovering] = useState(false);
  
  // Initialize discovered nodes from project, but also fetch fresh data on mount
  const [discoveredNodes, setDiscoveredNodes] = useState<DiscoveredNode[]>([]);
  
  // Fetch discovered nodes on component mount
  useEffect(() => {
    const fetchDiscoveredNodes = async () => {
      if (!project) return;
      
      try {
        const response = await fetch(getApiUrl(API_ENDPOINTS.MQTT_DISCOVERY_STATUS));
        if (response.ok) {
          const data = await response.json();
          const freshDiscoveredNodes = data.discovered_nodes || [];
          setDiscoveredNodes(freshDiscoveredNodes);
          
          // Update project with fresh discovered nodes if they're different
          if (JSON.stringify(freshDiscoveredNodes) !== JSON.stringify(project.discovered_nodes)) {
            const updatedProject = {
              ...project,
              discovered_nodes: freshDiscoveredNodes,
              updated_at: new Date().toISOString()
            };
            ProjectService.saveProject(updatedProject);
          }
        } else {
          // Fallback to project's discovered nodes
          setDiscoveredNodes(project.discovered_nodes || []);
        }
      } catch (error) {
        console.error('Failed to fetch discovered nodes:', error);
        // Fallback to project's discovered nodes
        setDiscoveredNodes(project.discovered_nodes || []);
      }
    };
    
    fetchDiscoveredNodes();
  }, [project]);

  // Create a combined list of available nodes (discovered + nodes on canvas)
  const availableNodes = React.useMemo(() => {
    const discoveredSet = new Set(discoveredNodes.map(node => node.equipment_id));
    
    // Start with discovered nodes
    const combined = [...discoveredNodes];
    
    // Add nodes from canvas that aren't in discovered nodes
    nodes.forEach(node => {
      if (!discoveredSet.has(node.data.equipment_id)) {
        // Create a DiscoveredNode-like object for canvas nodes
        combined.push({
          id: node.data.equipment_id,
          equipment_id: node.data.equipment_id,
          equipment_type: node.data.equipment_type || 'unknown',
          topics: [],
          sample_data: {},
          message_count: 0,
          first_seen: new Date().toISOString(),
          last_seen: new Date().toISOString()
        });
      }
    });
    
    return combined;
  }, [discoveredNodes, nodes]);

  const onConnect = useCallback((params: Edge | Connection) => {
    setEdges((eds) => addEdge(params, eds));
  }, [setEdges]);

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();

      const type = event.dataTransfer.getData('application/reactflow');
      const nodeData = JSON.parse(event.dataTransfer.getData('application/json'));

      if (typeof type === 'undefined' || !type || !reactFlowInstance) {
        return;
      }

      const position = reactFlowInstance.screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      const newNode: Node = {
        id: `${nodeData.equipment_id}_${Date.now()}`,
        type: 'default',
        position,
        data: {
          label: nodeData.equipment_id,
          equipment_id: nodeData.equipment_id,
          equipment_type: nodeData.equipment_type,
          topics: nodeData.topics,
          sample_data: nodeData.sample_data,
          status: 'idle',
          sensors: []
        },
        style: {
          background: '#f9fafb',
          border: '2px solid #e5e7eb',
          borderRadius: '8px',
          padding: '10px',
          minWidth: '120px'
        }
      };

      setNodes((nds) => nds.concat(newNode));
    },
    [reactFlowInstance, setNodes]
  );

  const saveGraph = () => {
    if (project) {
      // Update project with new graph layout
      const updatedProject = {
        ...project,
        graph_layout: { nodes, edges },
        updated_at: new Date().toISOString()
      };
      
      // Save to localStorage
      ProjectService.saveProject(updatedProject);
      
      // Update context
      updateGraphLayout(nodes, edges);
      
      alert('Graph layout saved!');
    }
  };

  const startMonitoring = () => {
    if (project) {
      // Save graph first
      const updatedProject = {
        ...project,
        graph_layout: { nodes, edges },
        updated_at: new Date().toISOString()
      };
      
      ProjectService.saveProject(updatedProject);
      updateGraphLayout(nodes, edges);
      
      navigate('/monitor', { state: { project: updatedProject } });
    }
  };

  const addAllNodes = () => {
    if (!availableNodes.length) return;
    
    // Calculate grid dimensions for spacing
    const nodeCount = availableNodes.length;
    const gridSize = Math.ceil(Math.sqrt(nodeCount));
    const nodeSpacing = 250; // pixels between nodes
    
    const newNodes = availableNodes.map((discoveredNode, index) => {
      // Calculate grid position
      const row = Math.floor(index / gridSize);
      const col = index % gridSize;
      
      return {
        id: `${discoveredNode.equipment_id}_${Date.now()}_${index}`,
        type: 'default',
        position: { 
          x: col * nodeSpacing + 100, 
          y: row * nodeSpacing + 100 
        },
        data: {
          label: discoveredNode.equipment_id,
          equipment_id: discoveredNode.equipment_id,
          equipment_type: discoveredNode.equipment_type,
          sensors: [],
          status: 'idle',
          last_updated: new Date().toISOString()
        }
      };
    });
    
    // Add new nodes to existing ones (avoiding duplicates by equipment_id)
    setNodes((currentNodes) => {
      const existingEquipmentIds = new Set(currentNodes.map(node => node.data.equipment_id));
      const nodesToAdd = newNodes.filter(node => !existingEquipmentIds.has(node.data.equipment_id));
      return [...currentNodes, ...nodesToAdd];
    });
    
    // Fit view to show all nodes
    setTimeout(() => {
      if (reactFlowInstance) {
        reactFlowInstance.fitView({ padding: 0.1 });
      }
    }, 100);
  };

  const arrangeInGrid = () => {
    if (!nodes.length) return;
    
    const nodeCount = nodes.length;
    // Calculate grid dimensions: for n nodes, use ceil(sqrt(n)) columns
    // This creates a nearly square grid (e.g., 9 nodes = 3x3, 10 nodes = 4x3)
    const gridCols = Math.ceil(Math.sqrt(nodeCount));
    const nodeSpacing = 250; // pixels between nodes
    
    const updatedNodes = nodes.map((node, index) => {
      const row = Math.floor(index / gridCols);
      const col = index % gridCols;
      
      return {
        ...node,
        position: {
          x: col * nodeSpacing + 100,
          y: row * nodeSpacing + 100
        }
      };
    });
    
    setNodes(updatedNodes);
    
    // Fit view to show all nodes
    setTimeout(() => {
      if (reactFlowInstance) {
        reactFlowInstance.fitView({ padding: 0.1 });
      }
    }, 100);
  };

  const reRunDiscovery = async () => {
    if (!project) return;
    
    setIsRediscovering(true);
    
    try {
      // Start discovery
      const discoverResponse = await fetch(getApiUrl(API_ENDPOINTS.MQTT_DISCOVER), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(project.mqtt_config)
      });
      
      if (!discoverResponse.ok) {
        throw new Error('Failed to start discovery');
      }
      
      // Wait a bit for discovery to run
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Get discovery status
      const statusResponse = await fetch(getApiUrl(API_ENDPOINTS.MQTT_DISCOVERY_STATUS));
      if (!statusResponse.ok) {
        throw new Error('Failed to get discovery status');
      }
      
      const statusData = await statusResponse.json();
      const newDiscoveredNodes = statusData.discovered_nodes || [];
      
      // Update project with new discovered nodes
      const updatedProject = {
        ...project,
        discovered_nodes: newDiscoveredNodes,
        updated_at: new Date().toISOString()
      };
      
      // Save updated project
      ProjectService.saveProject(updatedProject);
      
      // Update local state
      setDiscoveredNodes(newDiscoveredNodes);
      
      // Update context
      updateGraphLayout(updatedProject.graph_layout.nodes, updatedProject.graph_layout.edges);
      
      // Remove inactive nodes from canvas
      const activeEquipmentIds = new Set(newDiscoveredNodes.map((node: DiscoveredNode) => node.equipment_id));
      setNodes(currentNodes => 
        currentNodes.filter(node => activeEquipmentIds.has(node.data.equipment_id))
      );
      
      alert(`Discovery completed! Found ${newDiscoveredNodes.length} active cells. Inactive cells have been removed from the canvas.`);
      
    } catch (error) {
      console.error('Error during re-discovery:', error);
      alert('Failed to re-run discovery. Please check your MQTT connection.');
    } finally {
      setIsRediscovering(false);
    }
  };

  if (!project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600 mb-4">No project found. Please select a project first.</p>
          <button
            onClick={() => navigate('/')}
            className="minimal-button-primary"
          >
            Go to Projects
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen bg-gray-50 flex">
      {/* Sidebar with discovered nodes */}
      <div className="w-80 bg-white border-r border-gray-200 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center mb-2">
            <button
              onClick={() => navigate('/')}
              className="mr-2 p-1 hover:bg-gray-100 rounded"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
            <h1 className="text-lg font-semibold text-gray-900">Graph Editor</h1>
            {project && (
              <span className="ml-3 text-sm text-gray-600">
                {project.name}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-600">Drag nodes to the canvas and connect them</p>
        </div>

        {/* Available Nodes */}
        <div className="flex-1 p-4 overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-700">Available Nodes</h2>
            <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
              {availableNodes.length} available
            </span>
          </div>
          <div className="space-y-2">
            {availableNodes.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-gray-500 mb-2">No nodes available</p>
                <p className="text-xs text-gray-400">Run discovery in project settings to find equipment</p>
              </div>
            ) : (
              availableNodes.map((node: DiscoveredNode) => (
              <div
                key={node.equipment_id}
                className="p-3 bg-gray-50 rounded-lg border border-gray-200 cursor-move hover:bg-gray-100 transition-colors"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.setData('application/reactflow', 'default');
                  event.dataTransfer.setData('application/json', JSON.stringify(node));
                }}
              >
                <div className="flex items-center mb-1">
                  <Plus className="w-4 h-4 text-gray-400 mr-2" />
                  <h3 className="font-medium text-gray-900 text-sm">{node.equipment_id}</h3>
                </div>
                <p className="text-xs text-gray-600 mb-1">{node.equipment_type}</p>
                <p className="text-xs text-gray-500">{node.message_count} messages</p>
                <div className="text-xs text-gray-400 mt-1">
                  {node.topics.slice(0, 2).map(topic => topic.split('/').pop()).join(', ')}
                  {node.topics.length > 2 && '...'}
                </div>
              </div>
              ))
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="p-4 border-t border-gray-200 space-y-2">
          <button
            onClick={saveGraph}
            className="w-full minimal-button flex items-center justify-center"
          >
            <Save className="w-4 h-4 mr-2" />
            Save Layout
          </button>
          <button
            onClick={startMonitoring}
            className="w-full minimal-button-primary flex items-center justify-center"
            disabled={nodes.length === 0}
          >
            <Play className="w-4 h-4 mr-2" />
            Start Monitoring
          </button>
                     <button
             onClick={addAllNodes}
             className="w-full minimal-button flex items-center justify-center"
             disabled={availableNodes.length === 0}
             title="Add all discovered nodes to the graph at once"
           >
             <Plus className="w-4 h-4 mr-2" />
             Add All Nodes ({availableNodes.length})
           </button>
           <button
             onClick={arrangeInGrid}
             className="w-full minimal-button flex items-center justify-center"
             disabled={nodes.length === 0}
             title="Arrange all nodes in an equi-spaced grid layout"
           >
             <Grid className="w-4 h-4 mr-2" />
             Arrange in Grid ({nodes.length} nodes)
           </button>
           <button
             onClick={reRunDiscovery}
             className="w-full minimal-button flex items-center justify-center"
             disabled={isRediscovering || !project?.mqtt_config}
             title="Re-run cell discovery to find active cells and remove inactive ones"
           >
             <RefreshCw className={`w-4 h-4 mr-2 ${isRediscovering ? 'animate-spin' : ''}`} />
             {isRediscovering ? 'Re-discovering...' : 'Re-run Discovery'}
           </button>
        </div>
      </div>

      {/* Main Graph Canvas */}
      <div className="flex-1 relative">
        <ReactFlowProvider>
          <div className="w-full h-full" ref={reactFlowWrapper}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onInit={setReactFlowInstance}
              onDrop={onDrop}
              onDragOver={onDragOver}
              className="bg-gray-50"
              fitView
              snapToGrid
              snapGrid={[15, 15]}
            >
              <Controls className="bg-white border border-gray-200" />
              <MiniMap 
                className="bg-white border border-gray-200"
                nodeColor="#e5e7eb"
                maskColor="rgba(0, 0, 0, 0.1)"
              />
              <Background variant={BackgroundVariant.Dots} gap={15} size={1} color="#e5e7eb" />
            </ReactFlow>
          </div>
        </ReactFlowProvider>

        {/* Instructions overlay */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-white p-6 rounded-lg shadow-lg border border-gray-200 text-center">
              <h3 className="text-lg font-medium text-gray-900 mb-2">Build Your Workflow</h3>
              <p className="text-gray-600 mb-4">Drag nodes from the sidebar to create your workflow graph</p>
              <div className="text-sm text-gray-500">
                <p>• Drag nodes onto the canvas</p>
                <p>• Connect nodes by dragging from one to another</p>
                <p>• Use the controls to zoom and pan</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default GraphEditorPage; 