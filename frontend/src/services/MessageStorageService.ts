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

export class MessageStorageService {
  private static readonly STORAGE_KEY = 'mqtt_stored_messages';
  private static readonly SESSIONS_KEY = 'mqtt_message_sessions';
  private static readonly MAX_MESSAGES = 10000; // Limit to prevent storage overflow

  /**
   * Start a new message recording session
   */
  static startSession(projectId: string, projectName: string): string {
    const sessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    const newSession: MessageSession = {
      session_id: sessionId,
      project_id: projectId,
      project_name: projectName,
      start_time: new Date().toISOString(),
      total_messages: 0,
      equipment_ids: [],
      sensor_types: []
    };

    const sessions = this.getAllSessions();
    sessions.push(newSession);
    localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(sessions));

    console.log(`📹 Started message recording session: ${sessionId}`);
    return sessionId;
  }

  /**
   * Stop a recording session
   */
  static stopSession(sessionId: string): void {
    const sessions = this.getAllSessions();
    const sessionIndex = sessions.findIndex(s => s.session_id === sessionId);
    
    if (sessionIndex !== -1) {
      sessions[sessionIndex].end_time = new Date().toISOString();
      localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(sessions));
      console.log(`⏹️ Stopped message recording session: ${sessionId}`);
    }
  }

  /**
   * Store a new MQTT message
   */
  static storeMessage(sessionId: string, messageData: any): void {
    const message: StoredMessage = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: messageData.timestamp || new Date().toISOString(),
      equipment_id: messageData.equipment_id,
      sensor_type: messageData.sensor_type,
      value: messageData.value,
      unit: messageData.unit || '',
      status: messageData.status || 'active',
      topic: messageData.topic || '',
      raw_payload: messageData.raw_payload || messageData,
      project_id: sessionId
    };

    // Get existing messages
    const allMessages = this.getAllMessages();
    
    // Add new message
    allMessages.push(message);
    
    // Keep only the latest MAX_MESSAGES to prevent storage overflow
    if (allMessages.length > this.MAX_MESSAGES) {
      allMessages.splice(0, allMessages.length - this.MAX_MESSAGES);
    }
    
    // Store back
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(allMessages));

    // Update session statistics
    this.updateSessionStats(sessionId, message);
  }

  /**
   * Update session statistics
   */
  private static updateSessionStats(sessionId: string, message: StoredMessage): void {
    const sessions = this.getAllSessions();
    const sessionIndex = sessions.findIndex(s => s.session_id === sessionId);
    
    if (sessionIndex !== -1) {
      const session = sessions[sessionIndex];
      session.total_messages += 1;
      
      // Update equipment IDs
      if (!session.equipment_ids.includes(message.equipment_id)) {
        session.equipment_ids.push(message.equipment_id);
      }
      
      // Update sensor types
      if (!session.sensor_types.includes(message.sensor_type)) {
        session.sensor_types.push(message.sensor_type);
      }
      
      localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(sessions));
    }
  }

  /**
   * Get all stored messages
   */
  static getAllMessages(): StoredMessage[] {
    try {
      const stored = localStorage.getItem(this.STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading stored messages:', error);
      return [];
    }
  }

  /**
   * Get messages for a specific session
   */
  static getMessagesForSession(sessionId: string): StoredMessage[] {
    const allMessages = this.getAllMessages();
    return allMessages.filter(message => message.project_id === sessionId);
  }

  /**
   * Get messages for a specific equipment
   */
  static getMessagesForEquipment(sessionId: string, equipmentId: string): StoredMessage[] {
    const sessionMessages = this.getMessagesForSession(sessionId);
    return sessionMessages.filter(message => message.equipment_id === equipmentId);
  }

  /**
   * Get all recording sessions
   */
  static getAllSessions(): MessageSession[] {
    try {
      const stored = localStorage.getItem(this.SESSIONS_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch (error) {
      console.error('Error loading sessions:', error);
      return [];
    }
  }

  /**
   * Get sessions for a specific project
   */
  static getSessionsForProject(projectId: string): MessageSession[] {
    const allSessions = this.getAllSessions();
    return allSessions.filter(session => session.project_id === projectId);
  }

  /**
   * Delete a session and its messages
   */
  static deleteSession(sessionId: string): void {
    // Remove messages
    const allMessages = this.getAllMessages();
    const filteredMessages = allMessages.filter(message => message.project_id !== sessionId);
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(filteredMessages));

    // Remove session
    const sessions = this.getAllSessions();
    const filteredSessions = sessions.filter(session => session.session_id !== sessionId);
    localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(filteredSessions));

    console.log(`🗑️ Deleted session: ${sessionId}`);
  }

  /**
   * Export session data as JSON
   */
  static exportSession(sessionId: string): any {
    const session = this.getAllSessions().find(s => s.session_id === sessionId);
    const messages = this.getMessagesForSession(sessionId);

    return {
      session: session,
      messages: messages,
      exported_at: new Date().toISOString(),
      total_messages: messages.length
    };
  }

  /**
   * Import session data from JSON
   */
  static importSession(data: any): string {
    if (!data.session || !data.messages) {
      throw new Error('Invalid session data format');
    }

    // Generate new session ID to avoid conflicts
    const newSessionId = `imported_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Update session with new ID
    const session: MessageSession = {
      ...data.session,
      session_id: newSessionId
    };

    // Update messages with new session ID
    const messages: StoredMessage[] = data.messages.map((msg: any) => ({
      ...msg,
      project_id: newSessionId,
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}` // New ID
    }));

    // Store session
    const sessions = this.getAllSessions();
    sessions.push(session);
    localStorage.setItem(this.SESSIONS_KEY, JSON.stringify(sessions));

    // Store messages
    const allMessages = this.getAllMessages();
    allMessages.push(...messages);
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(allMessages));

    console.log(`📥 Imported session: ${newSessionId}`);
    return newSessionId;
  }

  /**
   * Get storage usage statistics
   */
  static getStorageStats(): any {
    const messages = this.getAllMessages();
    const sessions = this.getAllSessions();
    
    const storageSize = (JSON.stringify(messages).length + JSON.stringify(sessions).length) / 1024; // KB
    
    return {
      total_messages: messages.length,
      total_sessions: sessions.length,
      storage_size_kb: Math.round(storageSize),
      max_messages: this.MAX_MESSAGES,
      usage_percentage: Math.round((messages.length / this.MAX_MESSAGES) * 100)
    };
  }

  /**
   * Clear all stored data
   */
  static clearAllData(): void {
    localStorage.removeItem(this.STORAGE_KEY);
    localStorage.removeItem(this.SESSIONS_KEY);
    console.log('🧹 Cleared all stored message data');
  }
} 