// Project Storage Service
import { Project, ProjectSummary, ProjectExport } from '../types';

const STORAGE_KEY = 'mqtt_workflow_projects';
const STORAGE_VERSION = '1.0';

export class ProjectService {
  
  static saveProject(project: Project): void {
    const projects = this.getAllProjects();
    const existingIndex = projects.findIndex(p => p.id === project.id);
    
    project.updated_at = new Date().toISOString();
    
    if (existingIndex >= 0) {
      projects[existingIndex] = project;
    } else {
      projects.push(project);
    }
    
    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  }
  
  static getAllProjects(): Project[] {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading projects:', error);
      return [];
    }
  }
  
  static getProjectSummaries(): ProjectSummary[] {
    const projects = this.getAllProjects();
    return projects.map(project => ({
      id: project.id,
      name: project.name,
      description: project.description,
      created_at: project.created_at,
      updated_at: project.updated_at,
      last_accessed: project.last_accessed,
      is_favorite: project.is_favorite || false,
      node_count: project.graph_layout.nodes.length,
      equipment_types: [...new Set(project.discovered_nodes.map(n => n.equipment_type))],
      broker_host: project.mqtt_config.broker_host
    }));
  }
  
  static getProject(id: string): Project | null {
    const projects = this.getAllProjects();
    const project = projects.find(p => p.id === id);
    
    if (project) {
      // Update last accessed time
      project.last_accessed = new Date().toISOString();
      this.saveProject(project);
    }
    
    return project || null;
  }
  
  static deleteProject(id: string): boolean {
    try {
      const projects = this.getAllProjects();
      const filteredProjects = projects.filter(p => p.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filteredProjects));
      return true;
    } catch (error) {
      console.error('Error deleting project:', error);
      return false;
    }
  }
  
  static toggleFavorite(id: string): boolean {
    try {
      const projects = this.getAllProjects();
      const project = projects.find(p => p.id === id);
      
      if (project) {
        project.is_favorite = !project.is_favorite;
        project.updated_at = new Date().toISOString();
        this.saveProject(project);
        return true;
      }
      
      return false;
    } catch (error) {
      console.error('Error toggling favorite:', error);
      return false;
    }
  }
  
  static exportProject(id: string): ProjectExport | null {
    const project = this.getProject(id);
    
    if (!project) {
      return null;
    }
    
    return {
      project_info: {
        name: project.name,
        description: project.description,
        created_at: project.created_at,
        exported_at: new Date().toISOString(),
        version: STORAGE_VERSION
      },
      mqtt_config: project.mqtt_config,
      graph_schema: project.graph_layout,
      discovered_nodes: project.discovered_nodes
    };
  }
  
  static importProject(exportData: ProjectExport): Project {
    const now = new Date().toISOString();
    
    return {
      id: `imported-${Date.now()}`,
      name: `${exportData.project_info.name} (Imported)`,
      description: exportData.project_info.description,
      mqtt_config: exportData.mqtt_config,
      discovered_nodes: exportData.discovered_nodes,
      graph_layout: exportData.graph_schema,
      created_at: now,
      updated_at: now,
      is_favorite: false
    };
  }
  
  static downloadProjectFile(project: ProjectExport, filename?: string): void {
    const blob = new Blob([JSON.stringify(project, null, 2)], {
      type: 'application/json'
    });
    
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename || `${project.project_info.name.replace(/[^a-zA-Z0-9]/g, '_')}.json`;
    
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    URL.revokeObjectURL(url);
  }
  
  static async uploadProjectFile(file: File): Promise<Project> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = (e) => {
        try {
          const exportData: ProjectExport = JSON.parse(e.target?.result as string);
          const project = this.importProject(exportData);
          resolve(project);
        } catch (error) {
          reject(new Error('Invalid project file format'));
        }
      };
      
      reader.onerror = () => reject(new Error('Failed to read file'));
      reader.readAsText(file);
    });
  }
  
  static clearAllProjects(): void {
    localStorage.removeItem(STORAGE_KEY);
  }
  
  static getStorageUsage(): { used: number; percentage: number } {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) || '';
      const used = new Blob([stored]).size;
      const maxSize = 5 * 1024 * 1024; // Assume 5MB limit
      
      return {
        used,
        percentage: (used / maxSize) * 100
      };
    } catch (error) {
      return { used: 0, percentage: 0 };
    }
  }
} 