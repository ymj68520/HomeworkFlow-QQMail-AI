# database/migrations/002_add_attachment_rules.py
"""Add attachment_validation_rules table

Revision ID: 002
Create Date: 2026-05-11
"""
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Float, text
from sqlalchemy.ext.declarative import declarative_base
import os
from pathlib import Path

# Calculate database path relative to the migration file's location
BASE_DIR = Path(__file__).parent.parent.parent
DATABASE_PATH = BASE_DIR / 'assignment_submissions.db'

Base = declarative_base()

class AttachmentValidationRule(Base):
    __tablename__ = 'attachment_validation_rules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_name = Column(String(50), unique=True, nullable=False)
    allowed_extensions = Column(Text, nullable=False)
    extension_categories = Column(Text)
    max_file_size_mb = Column(Float, nullable=False)
    max_total_size_mb = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

def upgrade():
    """Create attachment_validation_rules table and insert default rule"""
    engine = create_engine(f'sqlite:///{DATABASE_PATH}')
    AttachmentValidationRule.__table__.create(engine, checkfirst=True)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if default rule already exists
    existing = session.query(AttachmentValidationRule).filter_by(rule_name='default').first()
    if not existing:
        # Insert default rule
        default_extensions = [
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt",
            ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
            ".zip", ".rar", ".7z", ".tar", ".gz"
        ]

        default_rule = AttachmentValidationRule(
            rule_name='default',
            allowed_extensions=json.dumps(default_extensions),
            max_file_size_mb=25.0,
            max_total_size_mb=100.0,
            is_active=True
        )
        session.add(default_rule)
        session.commit()
        print("[Migration] Default attachment validation rule created")
    else:
        print("[Migration] Default attachment validation rule already exists")

    session.close()

def downgrade():
    """Drop attachment_validation_rules table"""
    engine = create_engine(f'sqlite:///{DATABASE_PATH}')
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS attachment_validation_rules"))
    print("[Migration] Dropped attachment_validation_rules table")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'downgrade':
        downgrade()
    else:
        upgrade()