from typing import Optional, Dict, Any, List
import psycopg2
from internal.config.config import nested_config as config
from internal.adapters.log.logger import logger
from internal.domain.ports.db_port import DatabasePort
import json
from psycopg2.extras import RealDictCursor

class PostgresClient(DatabasePort):
    
    def __init__(self):
        self.config = config.get("database", {})
        self._connection = None
        self._cursor = None
    
    def _get_connection_string(self) -> str:
        dialect = self.config.get("dialect", "postgresql")
        username = self.config.get("username", "user")
        password = self.config.get("password", "password")
        address = self.config.get("address", "postgres")
        port = self.config.get("port", "5432")
        name = self.config.get("name", "interview")
        
        if address == "localhost":
            address = "postgres"
        
        return f"{dialect}://{username}:{password}@{address}:{port}/{name}"
    
    @property
    def connection(self):
        if self._connection is None or self._connection.closed:
            self.connect()
        return self._connection
    
    def connect(self) -> None:
        try:
            username = self.config.get("username", "user")
            password = self.config.get("password", "password")
            address = self.config.get("address", "postgres")
            port = self.config.get("port", "5432")
            name = self.config.get("name", "interview")
            
            if address == "localhost":
                address = "postgres"
            
            self._connection = psycopg2.connect(
                host=address,
                port=port,
                database=name,
                user=username,
                password=password,
                cursor_factory=RealDictCursor
            )
        except Exception as e:
            logger.error(f"[PostgresClient] Failed to connect to database: {e}")
            raise
    
    def disconnect(self) -> None:
        if self._cursor:
            self._cursor.close()
            self._cursor = None
        if self._connection:
            self._connection.close()
            self._connection = None
    
    async def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params or {})
            results = cursor.fetchall()
            cursor.close()
            
            return [dict(row) for row in results]
        except Exception as e:
            logger.error(f"[PostgresClient] Query execution failed: {e}")
            raise
    
    def execute_command(self, command: str, params: Optional[Dict[str, Any]] = None) -> None:
        try:
            cursor = self.connection.cursor()
            cursor.execute(command, params or {})
            self.connection.commit()
            cursor.close()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"[PostgresClient] Command execution failed: {e}")
            raise
    
    async def get_bias_prompt_by_session_id(self, session_id: str) -> Optional[str]:
        query = """
            SELECT bias_prompt
            FROM interview_sessions
            WHERE id = %(session_id)s
            AND (soft_delete = false OR soft_delete IS NULL)
            LIMIT 1
        """
        
        results = await self.execute_query(query, {"session_id": session_id})
        
        if not results or not results[0].get("bias_prompt"):
            return None
        
        return results[0]["bias_prompt"]
    
    async def get_resume_context_by_session_id(self, session_id: str) -> Dict[str, Any]:
        query = """
            SELECT resume_context
            FROM interview_sessions
            WHERE id = %(session_id)s
            AND (soft_delete = false OR soft_delete IS NULL)
            LIMIT 1
        """
        
        results = await self.execute_query(query, {"session_id": session_id})
        
        if not results or not results[0].get("resume_context"):
            return {}
        
        resume_context = results[0]["resume_context"]
        
        if isinstance(resume_context, str):
            try:
                resume_context = json.loads(resume_context)
            except json.JSONDecodeError:
                return {}
        
        return resume_context
    
    async def update_session_bias_and_context(
        self, 
        session_id: str, 
        bias_prompt: str, 
        resume_context: Dict[str, Any]
    ) -> None:
        command = """
            UPDATE interview_sessions
            SET 
                bias_prompt = %(bias_prompt)s,
                resume_context = %(resume_context)s,
                updated_at = NOW()
            WHERE id = %(session_id)s
            AND (soft_delete = false OR soft_delete IS NULL)
        """
        
        params = {
            "session_id": session_id,
            "bias_prompt": bias_prompt,
            "resume_context": json.dumps(resume_context, ensure_ascii=False)
        }
        
        try:
            self.execute_command(command, params)
        except Exception as e:
            logger.error(f"[PostgresClient] Failed to update session {session_id}: {e}")
            raise
    
    def close(self):
        self.disconnect()
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()


postgres_client = PostgresClient()

