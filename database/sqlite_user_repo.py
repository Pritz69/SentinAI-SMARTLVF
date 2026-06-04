import sqlite3
import datetime
import uuid
from typing import List, Dict, Any, Optional
from config.settings import settings

class UserRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Seed default users
        self.seed_default_users()

    def seed_default_users(self):
        # We import hash_password here to avoid circular imports on startup
        from core.auth import hash_password

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. Seed Admin user
        cursor.execute("SELECT id FROM users WHERE username = ?", ("admin",))
        if not cursor.fetchone():
            admin_id = f"user_{uuid.uuid4().hex[:12]}"
            hashed = hash_password("admin123")
            cursor.execute("""
                INSERT INTO users (id, username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (admin_id, "admin", hashed, "admin", datetime.datetime.now(datetime.UTC).isoformat()))
            
        # 2. Seed User user
        cursor.execute("SELECT id FROM users WHERE username = ?", ("user",))
        if not cursor.fetchone():
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            hashed = hash_password("user123")
            cursor.execute("""
                INSERT INTO users (id, username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, "user", hashed, "user", datetime.datetime.now(datetime.UTC).isoformat()))
            
        conn.commit()
        conn.close()

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def create_user(self, username: str, plain_password: str, role: str) -> Dict[str, Any]:
        from core.auth import hash_password
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        hashed = hash_password(plain_password)
        created_at = datetime.datetime.now(datetime.UTC).isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO users (id, username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, hashed, role, created_at))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            raise ValueError(f"Username '{username}' already exists.")
        finally:
            if conn:
                conn.close()
                
        return {
            "id": user_id,
            "username": username,
            "role": role,
            "created_at": created_at
        }

    def list_users(self) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

# Global singleton instance
user_repo = UserRepository(settings.SQLITE_DB_PATH)
