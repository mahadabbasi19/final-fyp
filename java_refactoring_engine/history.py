"""
History and Logging Module
==========================
Provides comprehensive logging and history tracking for refactoring operations.
Includes undo/redo functionality and session management.
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
import hashlib


@dataclass
class LogEntry:
    """Represents a single log entry."""
    timestamp: str
    level: str  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'
    category: str  # 'PARSE', 'REFACTOR', 'METRICS', 'GUI', 'FILE'
    message: str
    details: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def format(self) -> str:
        """Format log entry as string."""
        base = f"[{self.timestamp}] [{self.level}] [{self.category}] {self.message}"
        if self.details:
            base += f"\n  Details: {json.dumps(self.details, indent=2)}"
        return base


@dataclass
class RefactoringHistoryEntry:
    """Represents a single refactoring in history."""
    id: str
    timestamp: str
    file_path: Optional[str]
    refactoring_type: str
    description: str
    original_code: str
    refactored_code: str
    metrics_before: Dict
    metrics_after: Dict
    actions: List[Dict]
    can_undo: bool = True
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'RefactoringHistoryEntry':
        return cls(**data)


class Logger:
    """
    Centralized logging system for the refactoring engine.
    """
    
    def __init__(self, log_file: Optional[str] = None, 
                 console_output: bool = True,
                 min_level: str = 'INFO'):
        """
        Initialize the logger.
        
        Args:
            log_file: Path to log file (None for in-memory only)
            console_output: Whether to print to console
            min_level: Minimum log level to record
        """
        self.log_file = log_file
        self.console_output = console_output
        self.entries: List[LogEntry] = []
        
        self.level_priority = {
            'DEBUG': 0,
            'INFO': 1,
            'WARNING': 2,
            'ERROR': 3
        }
        self.min_level = min_level
        
        # Callbacks for GUI updates
        self.callbacks: List[callable] = []
    
    def add_callback(self, callback: callable):
        """Add a callback function to be called on new log entries."""
        self.callbacks.append(callback)
    
    def remove_callback(self, callback: callable):
        """Remove a callback function."""
        if callback in self.callbacks:
            self.callbacks.remove(callback)
    
    def _should_log(self, level: str) -> bool:
        """Check if a level should be logged based on min_level."""
        return self.level_priority.get(level, 0) >= self.level_priority.get(self.min_level, 0)
    
    def log(self, level: str, category: str, message: str, 
            details: Optional[Dict] = None):
        """
        Add a log entry.
        
        Args:
            level: Log level
            category: Log category
            message: Log message
            details: Optional additional details
        """
        if not self._should_log(level):
            return
        
        entry = LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            category=category,
            message=message,
            details=details
        )
        
        self.entries.append(entry)
        
        # Console output
        if self.console_output:
            print(entry.format())
        
        # File output
        if self.log_file:
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(entry.format() + '\n')
            except Exception as e:
                print(f"Failed to write to log file: {e}")
        
        # Notify callbacks
        for callback in self.callbacks:
            try:
                callback(entry)
            except Exception:
                pass
    
    def debug(self, category: str, message: str, details: Optional[Dict] = None):
        """Log a debug message."""
        self.log('DEBUG', category, message, details)
    
    def info(self, category: str, message: str, details: Optional[Dict] = None):
        """Log an info message."""
        self.log('INFO', category, message, details)
    
    def warning(self, category: str, message: str, details: Optional[Dict] = None):
        """Log a warning message."""
        self.log('WARNING', category, message, details)
    
    def error(self, category: str, message: str, details: Optional[Dict] = None):
        """Log an error message."""
        self.log('ERROR', category, message, details)
    
    def get_entries(self, level: Optional[str] = None, 
                    category: Optional[str] = None,
                    limit: int = 100) -> List[LogEntry]:
        """
        Get filtered log entries.
        
        Args:
            level: Filter by level
            category: Filter by category
            limit: Maximum number of entries to return
            
        Returns:
            List of matching log entries
        """
        entries = self.entries
        
        if level:
            entries = [e for e in entries if e.level == level]
        if category:
            entries = [e for e in entries if e.category == category]
        
        return entries[-limit:]
    
    def get_formatted_log(self, limit: int = 100) -> str:
        """Get formatted log string."""
        entries = self.entries[-limit:]
        return '\n'.join(entry.format() for entry in entries)
    
    def clear(self):
        """Clear all log entries."""
        self.entries.clear()
    
    def export(self) -> str:
        """Export log as JSON string."""
        return json.dumps([e.to_dict() for e in self.entries], indent=2)


class RefactoringHistory:
    """
    Manages history of refactoring operations with undo/redo support.
    """
    
    def __init__(self, max_history: int = 50, 
                 storage_path: Optional[str] = None):
        """
        Initialize the history manager.
        
        Args:
            max_history: Maximum number of history entries to keep
            storage_path: Path to persist history (None for in-memory only)
        """
        self.max_history = max_history
        self.storage_path = storage_path
        self.entries: List[RefactoringHistoryEntry] = []
        self.undo_stack: List[RefactoringHistoryEntry] = []
        self.redo_stack: List[RefactoringHistoryEntry] = []
        
        # Load existing history
        if storage_path and os.path.exists(storage_path):
            self._load_history()
    
    def _generate_id(self) -> str:
        """Generate a unique ID for a history entry."""
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    def add_entry(self, file_path: Optional[str],
                  refactoring_type: str,
                  description: str,
                  original_code: str,
                  refactored_code: str,
                  metrics_before: Dict,
                  metrics_after: Dict,
                  actions: List[Dict]) -> RefactoringHistoryEntry:
        """
        Add a new refactoring to history.
        
        Args:
            file_path: Path to the refactored file
            refactoring_type: Type of refactoring performed
            description: Description of the refactoring
            original_code: Code before refactoring
            refactored_code: Code after refactoring
            metrics_before: Metrics before refactoring
            metrics_after: Metrics after refactoring
            actions: List of specific actions performed
            
        Returns:
            The created history entry
        """
        entry = RefactoringHistoryEntry(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            file_path=file_path,
            refactoring_type=refactoring_type,
            description=description,
            original_code=original_code,
            refactored_code=refactored_code,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            actions=actions
        )
        
        self.entries.append(entry)
        self.undo_stack.append(entry)
        
        # Clear redo stack when new action is performed
        self.redo_stack.clear()
        
        # Trim history if needed
        while len(self.entries) > self.max_history:
            removed = self.entries.pop(0)
            if removed in self.undo_stack:
                self.undo_stack.remove(removed)
        
        # Persist if storage path is set
        if self.storage_path:
            self._save_history()
        
        return entry
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def undo(self) -> Optional[RefactoringHistoryEntry]:
        """
        Undo the last refactoring.
        
        Returns:
            The undone entry or None if nothing to undo
        """
        if not self.can_undo():
            return None
        
        entry = self.undo_stack.pop()
        self.redo_stack.append(entry)
        
        return entry
    
    def redo(self) -> Optional[RefactoringHistoryEntry]:
        """
        Redo the last undone refactoring.
        
        Returns:
            The redone entry or None if nothing to redo
        """
        if not self.can_redo():
            return None
        
        entry = self.redo_stack.pop()
        self.undo_stack.append(entry)
        
        return entry
    
    def get_entry(self, entry_id: str) -> Optional[RefactoringHistoryEntry]:
        """Get a specific history entry by ID."""
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        return None
    
    def get_entries(self, limit: int = 50, 
                    file_path: Optional[str] = None) -> List[RefactoringHistoryEntry]:
        """
        Get history entries.
        
        Args:
            limit: Maximum number of entries to return
            file_path: Optional filter by file path
            
        Returns:
            List of history entries (newest first)
        """
        entries = self.entries
        
        if file_path:
            entries = [e for e in entries if e.file_path == file_path]
        
        return list(reversed(entries[-limit:]))
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the history."""
        if not self.entries:
            return {
                'total_refactorings': 0,
                'by_type': {},
                'files_refactored': 0,
                'can_undo': False,
                'can_redo': False
            }
        
        by_type = {}
        files = set()
        
        for entry in self.entries:
            by_type[entry.refactoring_type] = by_type.get(entry.refactoring_type, 0) + 1
            if entry.file_path:
                files.add(entry.file_path)
        
        return {
            'total_refactorings': len(self.entries),
            'by_type': by_type,
            'files_refactored': len(files),
            'can_undo': self.can_undo(),
            'can_redo': self.can_redo(),
            'latest': self.entries[-1].timestamp if self.entries else None
        }
    
    def _save_history(self):
        """Save history to storage file."""
        if not self.storage_path:
            return
        
        try:
            # Create directory if needed
            Path(self.storage_path).parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                'entries': [e.to_dict() for e in self.entries],
                'saved_at': datetime.now().isoformat()
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save history: {e}")
    
    def _load_history(self):
        """Load history from storage file."""
        if not self.storage_path or not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.entries = [
                RefactoringHistoryEntry.from_dict(e) 
                for e in data.get('entries', [])
            ]
            
            # Rebuild undo stack from loaded entries
            self.undo_stack = [e for e in self.entries if e.can_undo]
        except Exception as e:
            print(f"Failed to load history: {e}")
    
    def clear(self):
        """Clear all history."""
        self.entries.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        
        if self.storage_path and os.path.exists(self.storage_path):
            try:
                os.remove(self.storage_path)
            except Exception:
                pass
    
    def export(self) -> str:
        """Export history as JSON string."""
        return json.dumps([e.to_dict() for e in self.entries], indent=2)
    
    def format_entry(self, entry: RefactoringHistoryEntry) -> str:
        """Format a history entry for display."""
        lines = [
            f"═══════════════════════════════════════════════════════════",
            f"📝 Refactoring: {entry.refactoring_type}",
            f"🕐 Time: {entry.timestamp}",
            f"📁 File: {entry.file_path or 'N/A'}",
            f"───────────────────────────────────────────────────────────",
            f"📋 Description: {entry.description}",
            f"───────────────────────────────────────────────────────────",
            f"📊 Metrics Change:",
            f"   LOC: {entry.metrics_before.get('code_lines', 0)} → {entry.metrics_after.get('code_lines', 0)}",
            f"   Methods: {entry.metrics_before.get('total_methods', 0)} → {entry.metrics_after.get('total_methods', 0)}",
            f"   Complexity: {entry.metrics_before.get('avg_complexity', 0):.1f} → {entry.metrics_after.get('avg_complexity', 0):.1f}",
            f"───────────────────────────────────────────────────────────",
            f"🔧 Actions ({len(entry.actions)}):"
        ]
        
        for i, action in enumerate(entry.actions[:5], 1):
            lines.append(f"   {i}. {action.get('action_type', 'Unknown')}: {action.get('description', '')[:50]}...")
        
        if len(entry.actions) > 5:
            lines.append(f"   ... and {len(entry.actions) - 5} more")
        
        lines.append(f"═══════════════════════════════════════════════════════════")
        
        return '\n'.join(lines)


class SessionManager:
    """
    Manages refactoring sessions with state persistence.
    """
    
    def __init__(self, session_dir: str = ".refactoring_sessions"):
        """
        Initialize session manager.
        
        Args:
            session_dir: Directory to store session data
        """
        self.session_dir = session_dir
        self.current_session_id: Optional[str] = None
        self.session_data: Dict[str, Any] = {}
        
        # Create session directory if needed
        Path(session_dir).mkdir(parents=True, exist_ok=True)
    
    def start_session(self, project_name: str = "Untitled") -> str:
        """
        Start a new refactoring session.
        
        Args:
            project_name: Name of the project being refactored
            
        Returns:
            Session ID
        """
        self.current_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        self.session_data = {
            'id': self.current_session_id,
            'project_name': project_name,
            'started_at': datetime.now().isoformat(),
            'files': [],
            'refactorings': [],
            'notes': []
        }
        
        self._save_session()
        return self.current_session_id
    
    def add_file(self, file_path: str):
        """Add a file to the current session."""
        if file_path not in self.session_data['files']:
            self.session_data['files'].append(file_path)
            self._save_session()
    
    def add_refactoring(self, refactoring_data: Dict):
        """Add a refactoring to the current session."""
        self.session_data['refactorings'].append({
            'timestamp': datetime.now().isoformat(),
            'data': refactoring_data
        })
        self._save_session()
    
    def add_note(self, note: str):
        """Add a note to the current session."""
        self.session_data['notes'].append({
            'timestamp': datetime.now().isoformat(),
            'note': note
        })
        self._save_session()
    
    def end_session(self):
        """End the current session."""
        if self.current_session_id:
            self.session_data['ended_at'] = datetime.now().isoformat()
            self._save_session()
            self.current_session_id = None
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Get summary of current session."""
        if not self.current_session_id:
            return {'active': False}
        
        return {
            'active': True,
            'id': self.current_session_id,
            'project': self.session_data.get('project_name'),
            'started': self.session_data.get('started_at'),
            'files_count': len(self.session_data.get('files', [])),
            'refactorings_count': len(self.session_data.get('refactorings', [])),
            'notes_count': len(self.session_data.get('notes', []))
        }
    
    def list_sessions(self) -> List[Dict]:
        """List all saved sessions."""
        sessions = []
        
        for filename in os.listdir(self.session_dir):
            if filename.endswith('.json'):
                try:
                    path = os.path.join(self.session_dir, filename)
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    sessions.append({
                        'id': data.get('id'),
                        'project': data.get('project_name'),
                        'started': data.get('started_at'),
                        'ended': data.get('ended_at'),
                        'files': len(data.get('files', [])),
                        'refactorings': len(data.get('refactorings', []))
                    })
                except Exception:
                    pass
        
        return sorted(sessions, key=lambda x: x.get('started', ''), reverse=True)
    
    def load_session(self, session_id: str) -> bool:
        """
        Load a saved session.
        
        Args:
            session_id: ID of the session to load
            
        Returns:
            True if successful
        """
        path = os.path.join(self.session_dir, f"{session_id}.json")
        
        if not os.path.exists(path):
            return False
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.session_data = json.load(f)
            self.current_session_id = session_id
            return True
        except Exception:
            return False
    
    def _save_session(self):
        """Save current session to file."""
        if not self.current_session_id:
            return
        
        path = os.path.join(self.session_dir, f"{self.current_session_id}.json")
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, indent=2)
        except Exception as e:
            print(f"Failed to save session: {e}")
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a saved session."""
        path = os.path.join(self.session_dir, f"{session_id}.json")
        
        try:
            if os.path.exists(path):
                os.remove(path)
                return True
        except Exception:
            pass
        
        return False
