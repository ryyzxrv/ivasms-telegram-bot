"""
Storage manager for persisting OTP data and bot state.
Uses SQLite for reliable data persistence and state management.
"""

import asyncio
import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class StorageManager:
    """Manages SQLite database for OTP storage and bot state."""

    def __init__(self, db_path: str = "./data/state.db"):
        self.db_path = db_path
        self.db_dir = os.path.dirname(db_path)
        
        # Ensure database directory exists
        if self.db_dir:
            os.makedirs(self.db_dir, exist_ok=True)

    async def initialize(self):
        """Initialize the database and create tables if they don't exist."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Create OTPs table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS otps (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        from_number TEXT NOT NULL,
                        text TEXT NOT NULL,
                        service TEXT,
                        created_at TEXT NOT NULL,
                        processed_at TEXT
                    )
                """)
                
                # Create bot state table
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS bot_state (
                        key TEXT PRIMARY KEY,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                
                # Create indexes for better performance
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_otps_timestamp 
                    ON otps(timestamp DESC)
                """)
                
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_otps_created_at 
                    ON otps(created_at DESC)
                """)
                
                await db.commit()
                
            logger.info(f"Database initialized successfully: {self.db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def store_otp(self, otp: Dict[str, str]) -> bool:
        """
        Store an OTP in the database.
        
        Args:
            otp: Dictionary containing OTP data
            
        Returns:
            bool: True if stored successfully, False otherwise
        """
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO otps 
                    (id, timestamp, from_number, text, service, created_at, processed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    otp['id'],
                    otp['timestamp'],
                    otp['from_number'],
                    otp['text'],
                    otp.get('service', ''),
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                
                await db.commit()
                
            logger.debug(f"Stored OTP: {otp['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store OTP {otp.get('id', 'unknown')}: {e}")
            return False

    async def otp_exists(self, otp_id: str) -> bool:
        """Check if an OTP with the given ID already exists."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT 1 FROM otps WHERE id = ? LIMIT 1",
                    (otp_id,)
                )
                result = await cursor.fetchone()
                return result is not None
                
        except Exception as e:
            logger.error(f"Failed to check OTP existence for {otp_id}: {e}")
            return False

    async def get_recent_otps(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get recent OTPs ordered by creation time."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, timestamp, from_number, text, service, created_at
                    FROM otps 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
                
                rows = await cursor.fetchall()
                
                otps = []
                for row in rows:
                    otps.append({
                        'id': row[0],
                        'timestamp': row[1],
                        'from_number': row[2],
                        'text': row[3],
                        'service': row[4] or '',
                        'created_at': row[5]
                    })
                
                return otps
                
        except Exception as e:
            logger.error(f"Failed to get recent OTPs: {e}")
            return []

    async def get_last_otp(self) -> Optional[Dict[str, str]]:
        """Get the most recent OTP."""
        otps = await self.get_recent_otps(limit=1)
        return otps[0] if otps else None

    async def get_otp_count(self) -> int:
        """Get total number of stored OTPs."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("SELECT COUNT(*) FROM otps")
                result = await cursor.fetchone()
                return result[0] if result else 0
                
        except Exception as e:
            logger.error(f"Failed to get OTP count: {e}")
            return 0

    async def get_otps_by_date_range(
        self, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, str]]:
        """Get OTPs within a specific date range."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    SELECT id, timestamp, from_number, text, service, created_at
                    FROM otps 
                    WHERE created_at BETWEEN ? AND ?
                    ORDER BY created_at DESC
                """, (start_date.isoformat(), end_date.isoformat()))
                
                rows = await cursor.fetchall()
                
                otps = []
                for row in rows:
                    otps.append({
                        'id': row[0],
                        'timestamp': row[1],
                        'from_number': row[2],
                        'text': row[3],
                        'service': row[4] or '',
                        'created_at': row[5]
                    })
                
                return otps
                
        except Exception as e:
            logger.error(f"Failed to get OTPs by date range: {e}")
            return []

    async def delete_old_otps(self, days: int = 30) -> int:
        """Delete OTPs older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("""
                    DELETE FROM otps 
                    WHERE created_at < ?
                """, (cutoff_date.isoformat(),))
                
                await db.commit()
                deleted_count = cursor.rowcount
                
            logger.info(f"Deleted {deleted_count} old OTPs (older than {days} days)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete old OTPs: {e}")
            return 0

    async def set_state(self, key: str, value: str):
        """Set a bot state value."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO bot_state 
                    (key, value, updated_at)
                    VALUES (?, ?, ?)
                """, (key, value, datetime.now().isoformat()))
                
                await db.commit()
                
            logger.debug(f"Set state: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Failed to set state {key}: {e}")

    async def get_state(self, key: str, default: str = None) -> Optional[str]:
        """Get a bot state value."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT value FROM bot_state WHERE key = ?",
                    (key,)
                )
                result = await cursor.fetchone()
                
                if result:
                    return result[0]
                else:
                    return default
                    
        except Exception as e:
            logger.error(f"Failed to get state {key}: {e}")
            return default

    async def get_last_seen_otp_id(self) -> Optional[str]:
        """Get the ID of the last seen OTP."""
        return await self.get_state("last_seen_otp_id")

    async def set_last_seen_otp_id(self, otp_id: str):
        """Set the ID of the last seen OTP."""
        await self.set_state("last_seen_otp_id", otp_id)

    async def get_all_states(self) -> Dict[str, str]:
        """Get all bot state values."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "SELECT key, value FROM bot_state ORDER BY key"
                )
                rows = await cursor.fetchall()
                
                return {row[0]: row[1] for row in rows}
                
        except Exception as e:
            logger.error(f"Failed to get all states: {e}")
            return {}

    async def clear_state(self, key: str) -> bool:
        """Clear a specific state value."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM bot_state WHERE key = ?",
                    (key,)
                )
                await db.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Failed to clear state {key}: {e}")
            return False

    async def clear_all_states(self) -> int:
        """Clear all state values."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                cursor = await db.execute("DELETE FROM bot_state")
                await db.commit()
                
                cleared_count = cursor.rowcount
                logger.info(f"Cleared {cleared_count} state entries")
                return cleared_count
                
        except Exception as e:
            logger.error(f"Failed to clear all states: {e}")
            return 0

    async def get_database_info(self) -> Dict[str, any]:
        """Get database information and statistics."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Get OTP count
                cursor = await db.execute("SELECT COUNT(*) FROM otps")
                otp_count = (await cursor.fetchone())[0]
                
                # Get state count
                cursor = await db.execute("SELECT COUNT(*) FROM bot_state")
                state_count = (await cursor.fetchone())[0]
                
                # Get database size
                db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                
                # Get oldest and newest OTP
                cursor = await db.execute(
                    "SELECT MIN(created_at), MAX(created_at) FROM otps"
                )
                date_range = await cursor.fetchone()
                
                return {
                    "db_path": self.db_path,
                    "db_size_bytes": db_size,
                    "db_size_mb": round(db_size / (1024 * 1024), 2),
                    "otp_count": otp_count,
                    "state_count": state_count,
                    "oldest_otp": date_range[0] if date_range[0] else None,
                    "newest_otp": date_range[1] if date_range[1] else None,
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "db_path": self.db_path,
                "error": str(e)
            }

    async def backup_database(self, backup_path: str) -> bool:
        """Create a backup of the database."""
        try:
            import shutil
            
            # Ensure backup directory exists
            backup_dir = os.path.dirname(backup_path)
            if backup_dir:
                os.makedirs(backup_dir, exist_ok=True)
            
            # Copy database file
            shutil.copy2(self.db_path, backup_path)
            
            logger.info(f"Database backed up to: {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False

    async def vacuum_database(self) -> bool:
        """Vacuum the database to reclaim space."""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("VACUUM")
                await db.commit()
                
            logger.info("Database vacuumed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to vacuum database: {e}")
            return False

    async def close(self):
        """Close database connections (cleanup method)."""
        # aiosqlite doesn't maintain persistent connections,
        # so there's nothing to close explicitly
        logger.debug("Storage manager closed")

    def __del__(self):
        """Destructor to ensure cleanup."""
        # No cleanup needed for aiosqlite
        pass
