"""Migration to add multi-assignment cache fields to AIExtractionCache

Revision ID: 002_add_multi_assignment_cache_fields
Create Date: 2026-05-09
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from database.models import async_engine


async def upgrade():
    """Add cache_data and cache_type columns to ai_extraction_cache table"""
    import sqlite3
    from config.settings import settings

    conn = sqlite3.connect(str(settings.DATABASE_PATH))
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(ai_extraction_cache)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        if 'cache_data' not in existing_columns:
            cursor.execute("ALTER TABLE ai_extraction_cache ADD COLUMN cache_data TEXT")
            print("[OK] Added column 'cache_data'")
        else:
            print("[INFO] Column 'cache_data' already exists, skipping")

        if 'cache_type' not in existing_columns:
            cursor.execute("ALTER TABLE ai_extraction_cache ADD COLUMN cache_type VARCHAR(20) DEFAULT 'single'")
            print("[OK] Added column 'cache_type'")
        else:
            print("[INFO] Column 'cache_type' already exists, skipping")

        conn.commit()
        print("Migration 002: Added multi-assignment cache fields successfully")
    finally:
        conn.close()


async def downgrade():
    """Remove cache_data and cache_type columns"""
    async with async_engine.begin() as conn:
        # SQLite doesn't support DROP COLUMN directly, would need to recreate table
        # For now, we'll just leave the columns in place
        print("Migration 002: Downgrade not supported for SQLite (columns left in place)")


if __name__ == "__main__":
    asyncio.run(upgrade())
