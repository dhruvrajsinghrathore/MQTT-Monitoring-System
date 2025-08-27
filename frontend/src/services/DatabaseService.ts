import { API_BASE_URL } from '../config/api';

export interface StoredMessage {
  id: string;
  timestamp: string;
  equipment_id: string;
  sensor_type: string;
  value: number | string | object;
  unit: string;
  status: string;
  topic: string;
  raw_payload: any;
  project_id: string;
}

export interface MessageSession {
  session_id: string;
  project_id: string;
  project_name: string;
  start_time: string;
  end_time?: string;
  total_messages: number;
  equipment_ids: string[];
  sensor_types: string[];
}

export class DatabaseService {
  private static readonly BASE_URL = `${API_BASE_URL}/api/database`;

  /**
   * Start a new message recording session
   */
  static async startSession(projectId: string, projectName: string): Promise<string> {
    try {
      const response = await fetch(`${this.BASE_URL}/session/start`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          project_name: projectName
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to start session: ${response.statusText}`);
      }

      const data = await response.json();
      console.log(`📹 Started recording session: ${data.session_id}`);
      return data.session_id;
    } catch (error) {
      console.error('Error starting session:', error);
      throw error;
    }
  }

  /**
   * Stop a recording session
   */
  static async stopSession(projectId: string, sessionId: string): Promise<void> {
    try {
      const response = await fetch(`${this.BASE_URL}/session/stop`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          session_id: sessionId
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to stop session: ${response.statusText}`);
      }

      console.log(`⏹️ Stopped recording session: ${sessionId}`);
    } catch (error) {
      console.error('Error stopping session:', error);
      throw error;
    }
  }

  /**
   * Store a new MQTT message (Note: This is typically done by the backend automatically)
   */
  static async storeMessage(projectId: string, sessionId: string, messageData: any): Promise<void> {
    try {
      const response = await fetch(`${this.BASE_URL}/message/store`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_id: projectId,
          session_id: sessionId,
          message_data: messageData
        })
      });

      if (!response.ok) {
        throw new Error(`Failed to store message: ${response.statusText}`);
      }
    } catch (error) {
      console.error('Error storing message:', error);
      throw error;
    }
  }

  /**
   * Get all messages for a project
   */
  static async getMessagesForProject(projectId: string, limit?: number): Promise<StoredMessage[]> {
    try {
      const url = new URL(`${this.BASE_URL}/messages/${projectId}`);
      if (limit) {
        url.searchParams.append('limit', limit.toString());
      }

      const response = await fetch(url.toString());
      
      if (!response.ok) {
        throw new Error(`Failed to get messages: ${response.statusText}`);
      }

      const data = await response.json();
      return data.messages || [];
    } catch (error) {
      console.error('Error getting project messages:', error);
      return [];
    }
  }

  /**
   * Get messages for a specific equipment
   */
  static async getMessagesForEquipment(projectId: string, equipmentId: string, limit?: number): Promise<StoredMessage[]> {
    try {
      const url = new URL(`${this.BASE_URL}/messages/${projectId}/${equipmentId}`);
      if (limit) {
        url.searchParams.append('limit', limit.toString());
      }

      const response = await fetch(url.toString());
      
      if (!response.ok) {
        throw new Error(`Failed to get equipment messages: ${response.statusText}`);
      }

      const data = await response.json();
      return data.messages || [];
    } catch (error) {
      console.error('Error getting equipment messages:', error);
      return [];
    }
  }

  /**
   * Get all sessions for a project
   */
  static async getSessionsForProject(projectId: string): Promise<MessageSession[]> {
    try {
      const response = await fetch(`${this.BASE_URL}/sessions/${projectId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to get sessions: ${response.statusText}`);
      }

      const data = await response.json();
      return data.sessions || [];
    } catch (error) {
      console.error('Error getting project sessions:', error);
      return [];
    }
  }

  /**
   * Export project data as JSON
   */
  static async exportProject(projectId: string): Promise<any> {
    try {
      const response = await fetch(`${this.BASE_URL}/export/${projectId}`);
      
      if (!response.ok) {
        throw new Error(`Failed to export project: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error exporting project:', error);
      throw error;
    }
  }

  /**
   * Import project data from JSON
   */
  static async importProject(data: any): Promise<string> {
    try {
      const response = await fetch(`${this.BASE_URL}/import`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ data })
      });

      if (!response.ok) {
        throw new Error(`Failed to import project: ${response.statusText}`);
      }

      const result = await response.json();
      console.log(`📥 Imported project: ${result.project_id}`);
      return result.project_id;
    } catch (error) {
      console.error('Error importing project:', error);
      throw error;
    }
  }

  /**
   * Delete all data for a project
   */
  static async deleteProject(projectId: string): Promise<void> {
    try {
      const response = await fetch(`${this.BASE_URL}/project/${projectId}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`Failed to delete project: ${response.statusText}`);
      }

      console.log(`🗑️ Deleted project data: ${projectId}`);
    } catch (error) {
      console.error('Error deleting project:', error);
      throw error;
    }
  }

  /**
   * Get storage usage statistics
   */
  static async getStorageStats(): Promise<any> {
    try {
      const response = await fetch(`${this.BASE_URL}/stats`);
      
      if (!response.ok) {
        throw new Error(`Failed to get storage stats: ${response.statusText}`);
      }

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Error getting storage stats:', error);
      return {
        total_projects: 0,
        total_storage_mb: 0,
        projects: {}
      };
    }
  }

  /**
   * Download project data as JSON file
   */
  static async downloadProjectData(projectId: string, projectName: string): Promise<void> {
    try {
      const data = await this.exportProject(projectId);
      
      const blob = new Blob([JSON.stringify(data, null, 2)], { 
        type: 'application/json' 
      });
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${projectName}_data_${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      console.log(`💾 Downloaded project data: ${projectName}`);
    } catch (error) {
      console.error('Error downloading project data:', error);
      throw error;
    }
  }

  /**
   * Upload and import project data from file
   */
  static async uploadProjectData(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      
      reader.onload = async (e) => {
        try {
          const content = e.target?.result as string;
          const data = JSON.parse(content);
          
          const projectId = await this.importProject(data);
          resolve(projectId);
        } catch (error) {
          reject(new Error(`Failed to parse or import file: ${error}`));
        }
      };
      
      reader.onerror = () => {
        reject(new Error('Failed to read file'));
      };
      
      reader.readAsText(file);
    });
  }
} 