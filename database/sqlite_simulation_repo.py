import sqlite3
import datetime
from typing import List, Dict, Any, Optional
from config.settings import settings

class SimulationRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS simulations (
                simulation_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                objective TEXT,
                target_id TEXT,
                created_at TEXT,
                name TEXT
            )
        """)
        # Schema migration: check if name column exists, if not add it
        cursor.execute("PRAGMA table_info(simulations)")
        columns = [col[1] for col in cursor.fetchall()]
        if "name" not in columns:
            cursor.execute("ALTER TABLE simulations ADD COLUMN name TEXT")
        conn.commit()
        conn.close()

    def create_simulation(self, simulation_id: str, username: str, objective: str, target_id: str, name: Optional[str] = None) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        if not name:
            name = f"Simulation - {objective[:30]}..."
        cursor.execute("""
            INSERT INTO simulations (simulation_id, username, objective, target_id, created_at, name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            simulation_id,
            username.lower(),
            objective,
            target_id,
            datetime.datetime.now(datetime.UTC).isoformat(),
            name
        ))
        conn.commit()
        conn.close()

    def list_simulations(self, username: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        if username:
            cursor.execute("SELECT * FROM simulations WHERE username = ? ORDER BY created_at DESC", (username.lower(),))
        else:
            cursor.execute("SELECT * FROM simulations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM simulations WHERE simulation_id = ?", (simulation_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None

    def delete_simulation(self, simulation_id: str) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM simulations WHERE simulation_id = ?", (simulation_id,))
        conn.commit()
        conn.close()

# Global singleton
simulation_repo = SimulationRepository(settings.SQLITE_DB_PATH)
