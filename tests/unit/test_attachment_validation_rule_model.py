# tests/unit/test_attachment_validation_rule_model.py
import pytest
from datetime import datetime
from database.models import AttachmentValidationRule, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_attachment_validation_rule(db_session):
    """Test creating an attachment validation rule"""
    rule = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".pdf", ".doc", ".docx"]',
        max_file_size_mb=25.0,
        max_total_size_mb=100.0,
        is_active=True
    )
    db_session.add(rule)
    db_session.commit()

    retrieved = db_session.query(AttachmentValidationRule).filter_by(rule_name="default").first()
    assert retrieved is not None
    assert retrieved.max_file_size_mb == 25.0
    assert retrieved.max_total_size_mb == 100.0
    assert retrieved.is_active is True

def test_rule_unique_name(db_session):
    """Test that rule_name must be unique"""
    rule1 = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".pdf"]',
        max_file_size_mb=10.0,
        max_total_size_mb=50.0
    )
    db_session.add(rule1)
    db_session.commit()

    rule2 = AttachmentValidationRule(
        rule_name="default",
        allowed_extensions='[".doc"]',
        max_file_size_mb=20.0,
        max_total_size_mb=100.0
    )
    db_session.add(rule2)

    with pytest.raises(Exception):  # IntegrityError
        db_session.commit()