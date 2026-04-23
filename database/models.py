from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from config.settings import settings

Base = declarative_base()

class Student(Base):
    __tablename__ = 'students'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    email = Column(String(100))
    created_at = Column(DateTime, default=datetime.now)

    submissions = relationship('Submission', back_populates='student')

class Assignment(Base):
    __tablename__ = 'assignments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    deadline = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)

    submissions = relationship('Submission', back_populates='assignment')

class Submission(Base):
    __tablename__ = 'submissions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    student_id = Column(Integer, ForeignKey('students.id'), nullable=False)
    assignment_id = Column(Integer, ForeignKey('assignments.id'), nullable=False)
    email_uid = Column(String(100), unique=True, nullable=False)
    email_subject = Column(Text)
    sender_email = Column(String(100))
    sender_name = Column(String(100))
    submission_time = Column(DateTime, nullable=False)
    is_late = Column(Boolean, default=False)
    is_downloaded = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)
    local_path = Column(Text)
    version = Column(Integer, default=1, nullable=False)
    is_latest = Column(Boolean, default=True, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    student = relationship('Student', back_populates='submissions')
    assignment = relationship('Assignment', back_populates='submissions')
    attachments = relationship('Attachment', back_populates='submission', cascade='all, delete-orphan')

class Attachment(Base):
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer)
    local_path = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    submission = relationship('Submission', back_populates='attachments')

class EmailLog(Base):
    __tablename__ = 'email_log'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_uid = Column(String(100))
    action = Column(String(50))
    folder = Column(String(100))
    timestamp = Column(DateTime, default=datetime.now)
    details = Column(Text)
    error_message = Column(Text)

class AIExtractionCache(Base):
    """AI extraction cache table"""
    __tablename__ = 'ai_extraction_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_uid = Column(String(255), unique=True, nullable=False, index=True)
    student_id = Column(String(50))
    name = Column(String(100))
    assignment_name = Column(String(50))
    confidence = Column(Float)
    is_fallback = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

# Create engine and session
engine = create_engine(f'sqlite:///{settings.DATABASE_PATH}')
SessionLocal = sessionmaker(bind=engine)

def get_session():
    """Get database session"""
    return SessionLocal()
