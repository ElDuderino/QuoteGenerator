import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional


class QuoteDatabase:
    def __init__(self, db_path: str = "quotes.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    quote_text TEXT NOT NULL,
                    date_generated TEXT NOT NULL,
                    seed TEXT,
                    raw_image_filename TEXT NOT NULL,
                    overlay_image_filename TEXT NOT NULL,
                    image_prompt TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _get_connection(self):
        """Get a database connection."""
        return sqlite3.connect(self.db_path)
    
    def insert_quote(
        self, 
        quote_text: str, 
        raw_image_filename: str, 
        overlay_image_filename: str,
        seed: Optional[str] = None,
        image_prompt: Optional[str] = None
    ) -> int:
        """Insert a new quote record and return the ID."""
        date_generated = datetime.now().strftime("%Y-%m-%d")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO quotes (quote_text, date_generated, seed, raw_image_filename, 
                                  overlay_image_filename, image_prompt)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (quote_text, date_generated, seed, raw_image_filename, 
                 overlay_image_filename, image_prompt))
            conn.commit()
            return cursor.lastrowid
    
    def get_recent_quotes(self, limit: int = 20) -> List[Dict]:
        """Get the most recent quotes for negative prompting."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT quote_text, date_generated, seed 
                FROM quotes 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_all_quotes(self) -> List[Dict]:
        """Get all quotes with their metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM quotes ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_quote_by_id(self, quote_id: int) -> Optional[Dict]:
        """Get a specific quote by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM quotes WHERE id = ?
            """, (quote_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def update_filenames(self, quote_id: int, raw_filename: str, overlay_filename: str):
        """Update the image filenames for a specific quote."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE quotes 
                SET raw_image_filename = ?, overlay_image_filename = ? 
                WHERE id = ?
            """, (raw_filename, overlay_filename, quote_id))
            conn.commit()