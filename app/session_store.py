import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Any


class SessionStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path).expanduser()

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    summary TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_message_at TEXT
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    request_id TEXT,
                    status TEXT NOT NULL DEFAULT 'completed',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS execution_logs (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    message_id TEXT,
                    step_index INTEGER NOT NULL,
                    function_name TEXT,
                    parameters_json TEXT,
                    justification TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id),
                    FOREIGN KEY(message_id) REFERENCES messages(id)
                )
                '''
            )
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_sessions_updated_at ON sessions(updated_at DESC)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_messages_session_created_at ON messages(session_id, created_at)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_execution_logs_message_step ON execution_logs(message_id, step_index)'
            )
            cursor.execute(
                'CREATE INDEX IF NOT EXISTS idx_execution_logs_session_created_at ON execution_logs(session_id, created_at)'
            )
            connection.commit()
        finally:
            connection.close()

    def create_session(
        self,
        title: str,
        summary: Optional[str] = None,
        status: str = 'active',
    ) -> dict[str, Any]:
        session_id = self._generate_id()
        timestamp = self._timestamp()

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''
                INSERT INTO sessions (id, title, summary, status, created_at, updated_at, last_message_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (session_id, title, summary, status, timestamp, timestamp, None),
            )
            connection.commit()
        finally:
            connection.close()

        session = self.get_session(session_id)
        if session is None:
            raise RuntimeError('Failed to create session record.')
        return session

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
            row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None
        return self._row_to_dict(row)

    def list_sessions(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT * FROM sessions ORDER BY updated_at DESC')
            rows = cursor.fetchall()
        finally:
            connection.close()

        sessions: list[dict[str, Any]] = []
        for row in rows:
            sessions.append(self._row_to_dict(row))
        return sessions

    def get_most_recent_session(self) -> Optional[dict[str, Any]]:
        sessions = self.list_sessions()
        if len(sessions) == 0:
            return None
        return sessions[0]

    def get_metadata(self, key: str) -> Optional[str]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute('SELECT value FROM app_state WHERE key = ?', (key,))
            row = cursor.fetchone()
        finally:
            connection.close()

        if row is None:
            return None

        return row['value']

    def set_metadata(self, key: str, value: Optional[str]) -> None:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            if value is None:
                cursor.execute('DELETE FROM app_state WHERE key = ?', (key,))
            else:
                cursor.execute(
                    '''
                    INSERT INTO app_state (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        updated_at = excluded.updated_at
                    ''',
                    (key, value, self._timestamp()),
                )
            connection.commit()
        finally:
            connection.close()

    def get_last_active_session_id(self) -> Optional[str]:
        return self.get_metadata('last_active_session_id')

    def set_last_active_session_id(self, session_id: Optional[str]) -> None:
        self.set_metadata('last_active_session_id', session_id)

    def touch_session(
        self,
        session_id: str,
        updated_at: Optional[str] = None,
        last_message_at: Optional[str] = None,
    ) -> None:
        session_updated_at = updated_at or self._timestamp()

        connection = self._connect()
        try:
            cursor = connection.cursor()
            if last_message_at is None:
                cursor.execute(
                    'UPDATE sessions SET updated_at = ? WHERE id = ?',
                    (session_updated_at, session_id),
                )
            else:
                cursor.execute(
                    'UPDATE sessions SET updated_at = ?, last_message_at = ? WHERE id = ?',
                    (session_updated_at, last_message_at, session_id),
                )
            connection.commit()
        finally:
            connection.close()

    def create_message(
        self,
        session_id: str,
        role: str,
        content: str,
        request_id: Optional[str] = None,
        status: str = 'completed',
    ) -> dict[str, Any]:
        message_id = self._generate_id()
        created_at = self._timestamp()

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''
                INSERT INTO messages (id, session_id, role, content, request_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                (message_id, session_id, role, content, request_id, status, created_at),
            )
            cursor.execute(
                'UPDATE sessions SET updated_at = ?, last_message_at = ? WHERE id = ?',
                (created_at, created_at, session_id),
            )
            connection.commit()
        finally:
            connection.close()

        messages = self.list_messages(session_id)
        for message in messages:
            if message['id'] == message_id:
                return message

        raise RuntimeError('Failed to create message record.')

    def list_messages(self, session_id: str) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                'SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC',
                (session_id,),
            )
            rows = cursor.fetchall()
        finally:
            connection.close()

        messages: list[dict[str, Any]] = []
        for row in rows:
            messages.append(self._row_to_dict(row))
        return messages

    def append_execution_log(
        self,
        session_id: str,
        step_index: int,
        status: str,
        message_id: Optional[str] = None,
        justification: Optional[str] = None,
        function_name: Optional[str] = None,
        parameters_json: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> dict[str, Any]:
        log_id = self._generate_id()
        created_at = self._timestamp()

        connection = self._connect()
        try:
            cursor = connection.cursor()
            cursor.execute(
                '''
                INSERT INTO execution_logs (
                    id,
                    session_id,
                    message_id,
                    step_index,
                    function_name,
                    parameters_json,
                    justification,
                    status,
                    error_message,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    log_id,
                    session_id,
                    message_id,
                    step_index,
                    function_name,
                    parameters_json,
                    justification,
                    status,
                    error_message,
                    created_at,
                ),
            )
            cursor.execute(
                'UPDATE sessions SET updated_at = ? WHERE id = ?',
                (created_at, session_id),
            )
            connection.commit()
        finally:
            connection.close()

        logs = self.list_execution_logs(message_id=message_id, session_id=session_id)
        for log in logs:
            if log['id'] == log_id:
                return log

        raise RuntimeError('Failed to create execution log record.')

    def list_execution_logs(
        self,
        message_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            cursor = connection.cursor()
            if message_id is not None:
                cursor.execute(
                    'SELECT * FROM execution_logs WHERE message_id = ? ORDER BY step_index ASC, created_at ASC',
                    (message_id,),
                )
            elif session_id is not None:
                cursor.execute(
                    'SELECT * FROM execution_logs WHERE session_id = ? ORDER BY created_at ASC, step_index ASC',
                    (session_id,),
                )
            else:
                cursor.execute(
                    'SELECT * FROM execution_logs ORDER BY created_at ASC, step_index ASC'
                )
            rows = cursor.fetchall()
        finally:
            connection.close()

        logs: list[dict[str, Any]] = []
        for row in rows:
            logs.append(self._row_to_dict(row))
        return logs

    def list_timeline_entries(self, session_id: str) -> list[dict[str, Any]]:
        messages = self.list_messages(session_id)
        execution_logs = self.list_execution_logs(session_id=session_id)
        timeline_entries: list[dict[str, Any]] = []

        for message in messages:
            timeline_entry = dict(message)
            timeline_entry['timeline_type'] = 'message'
            timeline_entries.append(timeline_entry)

        for execution_log in execution_logs:
            timeline_entry = dict(execution_log)
            timeline_entry['timeline_type'] = 'execution_log'
            timeline_entries.append(timeline_entry)

        timeline_entries.sort(key=self._timeline_sort_key)
        return timeline_entries

    def _timeline_sort_key(self, item: dict[str, Any]) -> tuple[str, int, int]:
        created_at = item.get('created_at') or ''
        timeline_type = item.get('timeline_type') or 'message'
        type_order = 0 if timeline_type == 'message' else 1
        step_index = item.get('step_index')

        if step_index is None:
            return created_at, type_order, -1

        return created_at, type_order, int(step_index)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys = ON')
        return connection

    def _generate_id(self) -> str:
        return str(uuid.uuid4())

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return dict(row)
