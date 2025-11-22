// Project Storage Service
import { Project, ProjectSummary, ProjectExport } from '../types';

const STORAGE_KEY = 'mqtt_workflow_projects';
const STORAGE_VERSION = '1.0';
const API_BASE_URL = 'http://localhost:8001/api';

export class ProjectService {
  
  static async saveProject(project: Project): Promise<void> {
    try {
      project.updated_at = new Date().toISOString();

      // Save to backend
      const isExisting = await this.projectExistsOnBackend(project.id);
      const method = isExisting ? 'PUT' : 'POST';
      const url = isExisting
        ? `${API_BASE_URL}/projects/${project.id}`
        : `${API_BASE_URL}/projects`;

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(project),
      });

      if (!response.ok) {
        throw new Error(`Failed to save project: ${response.statusText}`);
      }

      console.log(`💾 ${isExisting ? 'Updated' : 'Created'} project on backend: ${project.name}`);

      // Also save to localStorage as cache
      this.saveProjectLocally(project);
    } catch (error) {
      console.error('Failed to save to backend, saving locally only:', error);
      // Fallback to localStorage only
      this.saveProjectLocally(project);
    }
  }

  static saveProjectLocally(project: Project): void {
    const projects = this.getAllProjectsSync();
    const existingIndex = projects.findIndex(p => p.id === project.id);

    if (existingIndex >= 0) {
      projects[existingIndex] = project;
    } else {
      projects.push(project);
    }

    localStorage.setItem(STORAGE_KEY, JSON.stringify(projects));
  }

  static async projectExistsOnBackend(projectId: string): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE_URL}/projects/${projectId}`);
      return response.ok;
    } catch {
      return false;
    }
  }
  
  static async getAllProjects(): Promise<Project[]> {
    try {
      // Try to load from backend first
      const response = await fetch(`${API_BASE_URL}/projects`);
      if (response.ok) {
        const data = await response.json();
        const backendProjects = data.projects || [];

        // Update localStorage cache with backend data
        localStorage.setItem(STORAGE_KEY, JSON.stringify(backendProjects));
        console.log(`📥 Loaded ${backendProjects.length} projects from backend`);

        return backendProjects;
      }
    } catch (error) {
      console.error('Failed to load from backend, using localStorage:', error);
    }

    // Fallback to localStorage
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading projects:', error);
      return [];
    }
  }

  static getAllProjectsSync(): Project[] {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading projects:', error);
      return [];
    }
  }
  
  static async getProjectSummaries(): Promise<ProjectSummary[]> {
    const projects = await this.getAllProjects();
    return projects.map(project => ({
      id: project.id,
      name: project.name,
      description: project.description,
      created_at: project.created_at,
      updated_at: project.updated_at,
      last_accessed: project.last_accessed,
      is_favorite: project.is_favorite || false,
      node_count: (project.graph_layout?.nodes || []).length,
      equipment_types: [...new Set((project.discovered_nodes || []).map(n => n.equipment_type))],
      broker_host: project.mqtt_config.broker_host
    }));
  }
  
  static async getProject(id: string): Promise<Project | null> {
    try {
      // Try to load from backend first
      const response = await fetch(`${API_BASE_URL}/projects/${id}`);
      if (response.ok) {
        const project = await response.json();
        console.log(`📥 Loaded project from backend: ${project.name}`);

        // Update last accessed and save locally as cache
        project.last_accessed = new Date().toISOString();
        this.saveProjectLocally(project);

        return project;
      }
    } catch (error) {
      console.error('Failed to load from backend, trying localStorage:', error);
    }

    // Fallback to localStorage
    const projects = this.getAllProjectsSync();
    const project = projects.find(p => p.id === id);

    if (project) {
      // Update last accessed
      project.last_accessed = new Date().toISOString();
      this.saveProjectLocally(project);
    }

    return project || null;
  }
  
  static async deleteProject(id: string): Promise<boolean> {
    try {
      // Delete from backend first
      const response = await fetch(`${API_BASE_URL}/projects/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        console.log(`🗑️ Deleted project from backend: ${id}`);
      } else if (response.status !== 404) {
        // 404 is ok (project doesn't exist), other errors are problems
        throw new Error(`Failed to delete from backend: ${response.statusText}`);
      }

      // Also delete from localStorage
      const projects = this.getAllProjectsSync();
      const filteredProjects = projects.filter(p => p.id !== id);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filteredProjects));
      return true;
    } catch (error) {
      console.error('Error deleting project:', error);
      return false;
    }
  }
  
  static async toggleFavorite(id: string): Promise<boolean> {
    try {
      const projects = await this.getAllProjects();
      const project = projects.find(p => p.id === id);

      if (project) {
        project.is_favorite = !project.is_favorite;
        project.updated_at = new Date().toISOString();
        await this.saveProject(project);
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