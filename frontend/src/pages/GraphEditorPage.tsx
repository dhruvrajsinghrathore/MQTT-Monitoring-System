import React, { useState, useCallback, useRef } from 'react';
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
import { Save, Play, ArrowLeft, Plus } from 'lucide-react';
import { useProject } from '../contexts/ProjectContext';
import { DiscoveredNode, Project } from '../types';
import { ProjectService } from '../services/ProjectService';

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
          <h2 className="text-sm font-medium text-gray-700 mb-3">Available Nodes</h2>
          <div className="space-y-2">
            {project.discovered_nodes.map((node: DiscoveredNode) => (
              <div
                key={node.id}
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
            ))}
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