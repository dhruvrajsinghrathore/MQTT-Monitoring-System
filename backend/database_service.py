import os
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import threading
from dataclasses import dataclass, asdict
from fastapi import HTTPException

@dataclass
class StoredMessage:
    id: str
    timestamp: str
    equipment_id: str
    sensor_type: str
    value: Any  # Can be number, string, or object
    unit: str
    status: str
    topic: str
    raw_payload: Any
    project_id: str

@dataclass
class MessageSession:
    session_id: str
    project_id: str
    project_name: str
    start_time: str
    end_time: Optional[str] = None
    total_messages: int = 0
    equipment_ids: List[str] = None
    sensor_types: List[str] = None

    def __post_init__(self):
        if self.equipment_ids is None:
            self.equipment_ids = []
        if self.sensor_types is None:
            self.sensor_types = []

class DatabaseService:
    """
    Lightweight JSON file-based database for MQTT message storage.
    Organizes data by projects for efficient access.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.messages_dir = self.data_dir / "messages"
        self.sessions_dir = self.data_dir / "sessions"
        self.projects_dir = self.data_dir / "projects"
        
        # Create directories
        self.data_dir.mkdir(exist_ok=True)
        self.messages_dir.mkdir(exist_ok=True)
        self.sessions_dir.mkdir(exist_ok=True)
        self.projects_dir.mkdir(exist_ok=True)
        
        # Thread lock for file operations
        self._lock = threading.Lock()
        
        # Message limits per project to prevent excessive storage
        self.max_messages_per_project = 5000
        
        print(f"📂 Database initialized at: {self.data_dir.absolute()}")

    def _get_project_messages_file(self, project_id: str) -> Path:
        """Get the messages file path for a specific project"""
        return self.messages_dir / f"{project_id}_messages.json"

    def _get_project_sessions_file(self, project_id: str) -> Path:
        """Get the sessions file path for a specific project"""
        return self.sessions_dir / f"{project_id}_sessions.json"

    def _read_json_file(self, file_path: Path, default: Any = None) -> Any:
        """Safely read a JSON file"""
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return default if default is not None else []
        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ Error reading {file_path}: {e}")
            return default if default is not None else []

    def _write_json_file(self, file_path: Path, data: Any) -> None:
        """Safely write a JSON file"""
        try:
            # Create parent directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = file_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.rename(file_path)
        except IOError as e:
            print(f"❌ Error writing {file_path}: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to write data: {e}")

    def start_session(self, project_id: str, project_name: str) -> str:
        """Start a new message recording session"""
        with self._lock:
            session_id = f"session_{int(time.time() * 1000)}_{os.urandom(4).hex()}"
            
            session = MessageSession(
                session_id=session_id,
                project_id=project_id,
                project_name=project_name,
                start_time=datetime.now().isoformat()
            )
            
            # Read existing sessions for this project
            sessions_file = self._get_project_sessions_file(project_id)
            sessions_data = self._read_json_file(sessions_file, [])
            
            # Add new session
            sessions_data.append(asdict(session))
            self._write_json_file(sessions_file, sessions_data)
            
            print(f"📹 Started recording session: {session_id} for project: {project_name}")
            return session_id

    def stop_session(self, project_id: str, session_id: str) -> None:
        """Stop a recording session"""
        with self._lock:
            sessions_file = self._get_project_sessions_file(project_id)
            sessions_data = self._read_json_file(sessions_file, [])
            
            # Find and update the session
            for session in sessions_data:
                if session['session_id'] == session_id:
                    session['end_time'] = datetime.now().isoformat()
                    break
            
            self._write_json_file(sessions_file, sessions_data)
            print(f"⏹️ Stopped recording session: {session_id}")

    def store_message(self, project_id: str, session_id: str, message_data: Dict[str, Any]) -> None:
        """Store a new MQTT message"""
        with self._lock:
            # Create message record
            message = StoredMessage(
                id=f"msg_{int(time.time() * 1000)}_{os.urandom(4).hex()}",
                timestamp=message_data.get('timestamp', datetime.now().isoformat()),
                equipment_id=message_data['equipment_id'],
                sensor_type=message_data['sensor_type'],
                value=message_data['value'],
                unit=message_data.get('unit', ''),
                status=message_data.get('status', 'active'),
                topic=message_data.get('topic', ''),
                raw_payload=message_data.get('raw_payload', message_data),
                project_id=project_id
            )
            
            # Read existing messages for this project
            messages_file = self._get_project_messages_file(project_id)
            messages_data = self._read_json_file(messages_file, [])
            
            # Add new message
            messages_data.append(asdict(message))
            
            # Rotate messages if exceeding limit
            if len(messages_data) > self.max_messages_per_project:
                messages_data = messages_data[-self.max_messages_per_project:]
            
            self._write_json_file(messages_file, messages_data)
            
            # Update session statistics
            self._update_session_stats(project_id, session_id, message)

    def _update_session_stats(self, project_id: str, session_id: str, message: StoredMessage) -> None:
        """Update session statistics"""
        sessions_file = self._get_project_sessions_file(project_id)
        sessions_data = self._read_json_file(sessions_file, [])
        
        for session in sessions_data:
            if session['session_id'] == session_id:
                session['total_messages'] += 1
                
                # Update equipment IDs
                if message.equipment_id not in session['equipment_ids']:
                    session['equipment_ids'].append(message.equipment_id)
                
                # Update sensor types
                if message.sensor_type not in session['sensor_types']:
                    session['sensor_types'].append(message.sensor_type)
                
                break
        
        self._write_json_file(sessions_file, sessions_data)

    def get_messages_for_project(self, project_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get all messages for a specific project"""
        messages_file = self._get_project_messages_file(project_id)
        messages_data = self._read_json_file(messages_file, [])
        
        if limit:
            messages_data = messages_data[-limit:]
        
        return messages_data

    def get_messages_for_equipment(self, project_id: str, equipment_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get messages for a specific equipment in a project"""
        messages_data = self.get_messages_for_project(project_id)
        
        # Filter by equipment ID
        equipment_messages = [msg for msg in messages_data if msg['equipment_id'] == equipment_id]
        
        if limit:
            equipment_messages = equipment_messages[-limit:]
        
        return equipment_messages

    def get_sessions_for_project(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a specific project"""
        sessions_file = self._get_project_sessions_file(project_id)
        return self._read_json_file(sessions_file, [])

    def get_all_projects(self) -> List[str]:
        """Get list of all projects that have data"""
        projects = set()
        
        # Check messages directory
        for file_path in self.messages_dir.glob("*_messages.json"):
            project_id = file_path.stem.replace('_messages', '')
            projects.add(project_id)
        
        # Check sessions directory
        for file_path in self.sessions_dir.glob("*_sessions.json"):
            project_id = file_path.stem.replace('_sessions', '')
            projects.add(project_id)
        
        return list(projects)

    def export_project_data(self, project_id: str) -> Dict[str, Any]:
        """Export all data for a project"""
        return {
            'project_id': project_id,
            'messages': self.get_messages_for_project(project_id),
            'sessions': self.get_sessions_for_project(project_id),
            'exported_at': datetime.now().isoformat(),
            'total_messages': len(self.get_messages_for_project(project_id))
        }

    def import_project_data(self, data: Dict[str, Any]) -> str:
        """Import project data"""
        with self._lock:
            project_id = data['project_id']
            
            # Import messages
            if 'messages' in data:
                messages_file = self._get_project_messages_file(project_id)
                self._write_json_file(messages_file, data['messages'])
            
            # Import sessions
            if 'sessions' in data:
                sessions_file = self._get_project_sessions_file(project_id)
                self._write_json_file(sessions_file, data['sessions'])
            
            print(f"📥 Imported data for project: {project_id}")
            return project_id

    def delete_project_data(self, project_id: str) -> None:
        """Delete all data for a project"""
        with self._lock:
            messages_file = self._get_project_messages_file(project_id)
            sessions_file = self._get_project_sessions_file(project_id)
            
            # Remove files if they exist
            if messages_file.exists():
                messages_file.unlink()
            if sessions_file.exists():
                sessions_file.unlink()
            
            print(f"🗑️ Deleted data for project: {project_id}")

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        stats = {
            'total_projects': len(self.get_all_projects()),
            'total_storage_mb': 0,
            'projects': {}
        }
        
        total_size = 0
        for project_id in self.get_all_projects():
            messages_file = self._get_project_messages_file(project_id)
            sessions_file = self._get_project_sessions_file(project_id)
            
            project_size = 0
            if messages_file.exists():
                project_size += messages_file.stat().st_size
            if sessions_file.exists():
                project_size += sessions_file.stat().st_size
            
            total_size += project_size
            
            stats['projects'][project_id] = {
                'size_kb': round(project_size / 1024, 2),
                'message_count': len(self.get_messages_for_project(project_id)),
                'session_count': len(self.get_sessions_for_project(project_id))
            }
        
        stats['total_storage_mb'] = round(total_size / (1024 * 1024), 2)
        return stats

    def _get_project_file(self, project_id: str) -> Path:
        """Get the file path for a project"""
        return self.projects_dir / f"{project_id}.json"

    def load_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Load project data from file"""
        with self._lock:
            project_file = self._get_project_file(project_id)
            if project_file.exists():
                project = self._read_json_file(project_file)
                if project:
                    # Ensure project has all required fields
                    self._ensure_project_fields(project)
                return project
            return None

    def _ensure_project_fields(self, project: Dict[str, Any]) -> None:
        """Ensure project has all required fields with defaults"""
        project.setdefault('domain_documents', [])
        project.setdefault('alert_thresholds', [])
        project.setdefault('graph_layout', {'nodes': [], 'edges': []})
        project.setdefault('discovered_nodes', [])
        project.setdefault('description', None)
        project.setdefault('last_accessed', None)
        project.setdefault('is_favorite', False)

    def save_project(self, project: Dict[str, Any]) -> None:
        """Save project data to file"""
        with self._lock:
            project_id = project.get('id')
            if not project_id:
                raise ValueError("Project must have an 'id' field")

            project_file = self._get_project_file(project_id)
            self._write_json_file(project_file, project)
            print(f"💾 Saved project: {project_id}")

# Global database instance
db = DatabaseService() 