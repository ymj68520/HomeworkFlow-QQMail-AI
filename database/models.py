import enum
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from datetime import datetime
from config.settings import settings

Base = declarative_base()

class SubmissionStatus(str, enum.Enum):
    PENDING = "pending"              # 未处理 (刚接收)
    AI_ERROR = "ai_error"            # 识别异常 (AI无法提取关键信息)
    DOWNLOAD_FAILED = "download_failed" # 下载失败
    UNREPLIED = "unreplied"          # 未回复 (提取并下载成功，未发送确认邮件)
    COMPLETED = "completed"          # 已完成 (全部处理完毕)
    IGNORED = "ignored"              # 已忽略 (非作业邮件等)

class RelationType(str, enum.Enum):
    VERSION = "version"              # 版本迭代关系 (同一学生的多次提交)
    POSSIBLE_DUP = "possible_dup"    # 可能重复 (需要人工确认)

# 新增：独立状态枚举
class ProcessingStatus(str, enum.Enum):
    """处理状态 - 追踪邮件整体处理进度"""
    RECEIVED = "received"            # 邮件已接收
    PROCESSING = "processing"        # 正在处理
    EXTRACTED = "extracted"          # AI提取成功
    DOWNLOADING = "downloading"      # 下载附件中
    DOWNLOADED = "downloaded"        # 下载完成
    REPLYING = "replying"            # 回复中
    REPLIED = "replied"              # 已回复
    FAILED = "failed"                # 处理失败
    IGNORED = "ignored"              # 已忽略

class AIExtractionStatus(str, enum.Enum):
    """AI提取状态 - 追踪信息提取的独立状态"""
    PENDING = "pending"              # 待提取
    EXTRACTING = "extracting"        # 提取中
    SUCCESS = "success"              # 提取成功
    FAILED = "failed"                # 提取失败
    FALLBACK = "fallback"            # 正则回退

class DownloadStatus(str, enum.Enum):
    """下载状态 - 追踪附件下载的独立状态"""
    PENDING = "pending"              # 待下载
    DOWNLOADING = "downloading"      # 下载中
    SUCCESS = "success"              # 下载成功
    FAILED = "failed"                # 下载失败

class ReplyStatus(str, enum.Enum):
    """回复状态 - 追踪回复邮件的独立状态"""
    PENDING = "pending"              # 待回复
    SENDING = "sending"              # 发送中
    SUCCESS = "success"              # 发送成功
    SKIPPED = "skipped"              # 跳过（功能未启用）
    FAILED = "failed"                # 发送失败

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
    message_id = Column(String(255), unique=True, nullable=True, index=True)
    email_uid = Column(String(100), unique=True, nullable=False)
    email_subject = Column(Text)
    sender_email = Column(String(100))
    sender_name = Column(String(100))
    body = Column(Text)
    submission_time = Column(DateTime, nullable=False)
    is_late = Column(Boolean, default=False)
    is_downloaded = Column(Boolean, default=False)
    is_replied = Column(Boolean, default=False)
    
    # 新增字段
    status = Column(String(20), default=SubmissionStatus.PENDING.value, nullable=False)
    error_message = Column(Text, nullable=True)
    
    local_path = Column(Text)
    version = Column(Integer, default=1, nullable=False)
    is_latest = Column(Boolean, default=True, nullable=True)

    # 新增字段：记录关系管理
    parent_id = Column(Integer, ForeignKey('submissions.id'), nullable=True, index=True)
    relation_type = Column(String(20), nullable=True, index=True)  # RelationType.VERSION | RelationType.POSSIBLE_DUP | None
    is_primary = Column(Boolean, default=True, nullable=False, index=True)

    # Multi-assignment group fields
    group_id = Column(Integer, ForeignKey('submission_groups.id'), nullable=True, index=True)
    group_order = Column(Integer, default=0, nullable=False)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    student = relationship('Student', back_populates='submissions')
    assignment = relationship('Assignment', back_populates='submissions')
    attachments = relationship('Attachment', back_populates='submission', cascade='all, delete-orphan')

    # 新增关系
    parent = relationship('Submission', remote_side=[id], backref='children')
    group = relationship('SubmissionGroup', back_populates='submissions', foreign_keys=[group_id])

class Attachment(Base):
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer)
    local_path = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    submission = relationship('Submission', back_populates='attachments')

class SubmissionGroup(Base):
    """Submission group - represents an email that may contain multiple assignment submissions"""
    __tablename__ = 'submission_groups'

    # Basic fields
    id = Column(Integer, primary_key=True, autoincrement=True)
    email_uid = Column(String(255), unique=True, nullable=False, index=True)
    message_id = Column(String(255), index=True)

    # Email information
    email_subject = Column(Text)
    sender_email = Column(String(100))
    sender_name = Column(String(100))
    submission_time = Column(DateTime, nullable=False)

    # Processing status
    status = Column(String(20), default='processing', nullable=False)  # processing, completed, failed, manual_review
    processing_mode = Column(String(20), nullable=False)  # 'single', 'multi'

    # Statistics
    total_assignments = Column(Integer, default=0)
    total_attachments = Column(Integer, default=0)

    # Multi-assignment specific fields
    detection_method = Column(String(50))  # 'subject', 'filename', 'body', 'unknown'
    ai_confidence = Column(Float)

    # Error information
    error_message = Column(Text)
    error_details = Column(Text)  # JSON format

    # Relationships
    submissions = relationship('Submission', back_populates='group', cascade='all, delete-orphan')

    # Timestamps
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<SubmissionGroup(id={self.id}, email_uid={self.email_uid}, mode={self.processing_mode})>"

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

class FileOperationsLog(Base):
    """文件操作事务日志 - 用于实现强一致性"""
    __tablename__ = 'file_operations_log'

    id = Column(Integer, primary_key=True)
    submission_id = Column(Integer, ForeignKey('submissions.id'), nullable=False)
    operation_type = Column(String(50), nullable=False)
    file_path = Column(String, nullable=False)
    status = Column(String(20), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime)
    error_message = Column(String)

    submission = relationship('Submission', backref='file_operations')

class StatusHistory(Base):
    """状态历史记录 - 追踪所有状态变化"""
    __tablename__ = 'status_history'

    id = Column(Integer, primary_key=True, autoincrement=True)
    submission_id = Column(Integer, ForeignKey('submissions.id', ondelete='CASCADE'), nullable=False, index=True)
    status_type = Column(String(50), nullable=False, index=True)  # 'processing', 'ai_extraction', 'download', 'reply'
    old_status = Column(String(50))
    new_status = Column(String(50), nullable=False)
    reason = Column(Text)
    extra_data = Column(Text)  # JSON格式的额外信息 (避免使用metadata保留字)
    created_at = Column(DateTime, default=datetime.now, index=True)

    submission = relationship('Submission', backref='status_history')

# Create engine and session (sync)
engine = create_engine(
    f'sqlite:///{settings.DATABASE_PATH}',
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine)
db_session = scoped_session(SessionLocal)

# Create async engine and session
async_engine = create_async_engine(
    f'sqlite+aiosqlite:///{settings.DATABASE_PATH}',
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=False
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Enable WAL mode for better concurrency
import asyncio
from sqlalchemy import text

async def enable_wal_mode():
    """Enable Write-Ahead Logging for better concurrency"""
    async with async_engine.begin() as conn:
        await conn.execute(text("PRAGMA journal_mode=WAL"))
        await conn.execute(text("PRAGMA synchronous=NORMAL"))
        await conn.execute(text("PRAGMA cache_size=-10000"))  # 10MB cache
        await conn.execute(text("PRAGMA busy_timeout=5000"))  # 5 second timeout
        print("SQLite WAL mode enabled for better concurrency")

def get_async_session():
    """Get async database session factory"""
    return AsyncSessionLocal

def get_session():
    """Get database session"""
    return db_session()
