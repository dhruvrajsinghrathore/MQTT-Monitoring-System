import React, { createContext, useContext, useState, ReactNode } from 'react';
import { Project, MQTTConfig, DiscoveredNode } from '../types';

interface ProjectContextType {
  project: Project | null;
  setProject: (project: Project) => void;
  updateMQTTConfig: (config: MQTTConfig) => void;
  setDiscoveredNodes: (nodes: DiscoveredNode[]) => void;
  updateGraphLayout: (nodes: any[], edges: any[]) => void;
}

const ProjectContext = createContext<ProjectContextType | undefined>(undefined);

export const useProject = () => {
  const context = useContext(ProjectContext);
  if (!context) {
    throw new Error('useProject must be used within a ProjectProvider');
  }
  return context;
};

interface ProjectProviderProps {
  children: ReactNode;
}

export const ProjectProvider: React.FC<ProjectProviderProps> = ({ children }) => {
  const [project, setProject] = useState<Project | null>(null);

  const updateMQTTConfig = (config: MQTTConfig) => {
    if (project) {
      setProject({
        ...project,
        mqtt_config: config,
        updated_at: new Date().toISOString()
      });
    }
  };

  const setDiscoveredNodes = (nodes: DiscoveredNode[]) => {
    if (project) {
      setProject({
        ...project,
        discovered_nodes: nodes,
        updated_at: new Date().toISOString()
      });
    }
  };

  const updateGraphLayout = (nodes: any[], edges: any[]) => {
    if (project) {
      setProject({
        ...project,
        graph_layout: { nodes, edges },
        updated_at: new Date().toISOString()
      });
    }
  };

  return (
    <ProjectContext.Provider value={{
      project,
      setProject,
      updateMQTTConfig,
      setDiscoveredNodes,
      updateGraphLayout
    }}>
      {children}
    </ProjectContext.Provider>
  );
}; 