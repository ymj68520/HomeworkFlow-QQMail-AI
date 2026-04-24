import json
from datetime import datetime
from typing import Optional, List, Dict
from database.models import SessionLocal, Student, Assignment, Submission, Attachment, EmailLog
from sqlalchemy import or_, and_
import sqlite3

class DatabaseOperations:
    def __init__(self):
        self.session = SessionLocal()

    def create_student(self, student_id: str, name: str, email: Optional[str] = None) -> Student:
        """Create or get existing student"""
        student = self.session.query(Student).filter_by(student_id=student_id).first()
        if not student:
            student = Student(student_id=student_id, name=name, email=email)
            self.session.add(student)
            self.session.commit()
            self.session.refresh(student)
        return student

    def get_student(self, student_id: str) -> Optional[Student]:
        """Get student by student_id"""
        return self.session.query(Student).filter_by(student_id=student_id).first()

    def create_assignment(self, name: str, deadline: Optional[datetime] = None) -> Assignment:
        """Create or get existing assignment"""
        assignment = self.session.query(Assignment).filter_by(name=name).first()
        if not assignment:
            assignment = Assignment(name=name, deadline=deadline)
            self.session.add(assignment)
            self.session.commit()
            self.session.refresh(assignment)
        return assignment

    def get_assignment(self, name: str) -> Optional[Assignment]:
        """Get assignment by name"""
        return self.session.query(Assignment).filter_by(name=name).first()

    def update_assignment_deadline(self, name: str, deadline: datetime) -> bool:
        """Update assignment deadline"""
        assignment = self.get_assignment(name)
        if assignment:
            assignment.deadline = deadline
            self.session.commit()
            return True
        return False

    def create_submission(
        self,
        student_id: str,
        assignment_name: str,
        email_uid: str,
        email_subject: str,
        sender_email: str,
        sender_name: str,
        submission_time: datetime,
        local_path: Optional[str] = None,
        version: int = 1,
        is_latest: bool = True
    ) -> Optional[Submission]:
        """Create a new submission"""
        try:
            # Get or create student
            student = self.create_student(student_id, sender_name, sender_email)

            # Get or create assignment
            assignment = self.create_assignment(assignment_name)

            # Check if submission already exists
            existing = self.session.query(Submission).filter_by(
                student_id=student.id,
                assignment_id=assignment.id
            ).first()

            if existing:
                # Update existing submission with new version info
                self.mark_old_versions_as_not_latest(student_id, assignment_name, version)

                existing.email_uid = email_uid
                existing.email_subject = email_subject
                existing.submission_time = submission_time
                existing.local_path = local_path
                existing.version = version
                existing.is_latest = is_latest
                existing.is_late = assignment.deadline and submission_time > assignment.deadline
                existing.updated_at = datetime.now()
                submission = existing
            else:
                # Create new submission with version info
                is_late = assignment.deadline and submission_time > assignment.deadline
                submission = Submission(
                    student_id=student.id,
                    assignment_id=assignment.id,
                    email_uid=email_uid,
                    email_subject=email_subject,
                    sender_email=sender_email,
                    sender_name=sender_name,
                    submission_time=submission_time,
                    is_late=is_late,
                    local_path=local_path,
                    version=version,
                    is_latest=is_latest
                )
                self.session.add(submission)

            self.session.commit()
            self.session.refresh(submission)
            return submission

        except Exception as e:
            self.session.rollback()
            print(f"Error creating submission: {e}")
            return None

    def get_submission(self, student_id: str, assignment_name: str) -> Optional[Submission]:
        """Get submission by student_id and assignment_name"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name
        ).first()

    def get_all_submissions(self) -> List[Dict]:
        """Get all submissions with student and assignment info"""
        submissions = self.session.query(Submission).all()
        result = []
        for s in submissions:
            result.append({
                'id': s.id,
                'student_id': s.student.student_id,
                'name': s.student.name,
                'email': s.student.email,
                'assignment_name': s.assignment.name,
                'email_uid': s.email_uid,
                'submission_time': s.submission_time,
                'is_late': s.is_late,
                'is_downloaded': s.is_downloaded,
                'is_replied': s.is_replied,
                'local_path': s.local_path
            })
        return result

    def get_submission_by_uid(self, email_uid: str) -> Optional[Submission]:
        """Get submission by email UID"""
        return self.session.query(Submission).filter_by(email_uid=email_uid).first()

    def update_submission_local_path(self, submission_id: int, local_path: str) -> bool:
        """Update submission local path"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.local_path = local_path
                submission.is_downloaded = True
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error updating local path: {e}")
            return False

    def mark_replied(self, submission_id: int) -> bool:
        """Mark submission as replied"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                submission.is_replied = True
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error marking replied: {e}")
            return False

    def mark_late_submissions(self, assignment_name: str) -> int:
        """Mark all submissions as late if past deadline"""
        try:
            assignment = self.get_assignment(assignment_name)
            if not assignment or not assignment.deadline:
                return 0

            count = self.session.query(Submission).filter(
                Submission.assignment_id == assignment.id,
                Submission.submission_time > assignment.deadline,
                Submission.is_late == False
            ).update({'is_late': True})

            self.session.commit()
            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error marking late submissions: {e}")
            return 0

    def delete_submission(self, submission_id: int) -> bool:
        """Delete submission by ID"""
        try:
            submission = self.session.query(Submission).filter_by(id=submission_id).first()
            if submission:
                self.session.delete(submission)
                self.session.commit()
                return True
            return False
        except Exception as e:
            self.session.rollback()
            print(f"Error deleting submission: {e}")
            return False

    def add_attachment(self, submission_id: int, filename: str, file_size: int, local_path: str) -> Optional[Attachment]:
        """Add attachment to submission"""
        try:
            attachment = Attachment(
                submission_id=submission_id,
                filename=filename,
                file_size=file_size,
                local_path=local_path
            )
            self.session.add(attachment)
            self.session.commit()
            self.session.refresh(attachment)
            return attachment
        except Exception as e:
            self.session.rollback()
            print(f"Error adding attachment: {e}")
            return None

    def get_attachments(self, submission_id: int) -> List[Attachment]:
        """Get all attachments for a submission"""
        return self.session.query(Attachment).filter_by(submission_id=submission_id).all()

    def log_email_action(self, email_uid: str, action: str, folder: str, details: str = None, error_message: str = None):
        """Log email action"""
        try:
            log = EmailLog(
                email_uid=email_uid,
                action=action,
                folder=folder,
                details=details,
                error_message=error_message
            )
            self.session.add(log)
            self.session.commit()
        except Exception as e:
            print(f"Error logging email action: {e}")

    def get_all_students(self) -> List[Student]:
        """Get all students"""
        return self.session.query(Student).all()

    def get_all_assignments(self) -> List[Assignment]:
        """Get all assignments"""
        return self.session.query(Assignment).all()

    def filter_submissions(
        self,
        student_id: Optional[str] = None,
        assignment_name: Optional[str] = None,
        is_late: Optional[bool] = None,
        is_replied: Optional[bool] = None
    ) -> List[Dict]:
        """Filter submissions by various criteria"""
        query = self.session.query(Submission)

        if student_id:
            query = query.join(Student).filter(Student.student_id == student_id)

        if assignment_name:
            query = query.join(Assignment).filter(Assignment.name == assignment_name)

        if is_late is not None:
            query = query.filter(Submission.is_late == is_late)

        if is_replied is not None:
            query = query.filter(Submission.is_replied == is_replied)

        submissions = query.all()
        result = []
        for s in submissions:
            result.append({
                'id': s.id,
                'student_id': s.student.student_id,
                'name': s.student.name,
                'email': s.student.email,
                'assignment_name': s.assignment.name,
                'email_uid': s.email_uid,
                'submission_time': s.submission_time,
                'is_late': s.is_late,
                'is_downloaded': s.is_downloaded,
                'is_replied': s.is_replied,
                'local_path': s.local_path
            })
        return result

    def get_all_submission_versions(
        self,
        student_id: str,
        assignment_name: str
    ) -> List[Submission]:
        """Get all versions of a submission (old and new)"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name
        ).order_by(Submission.version.desc()).all()

    def get_latest_submission(
        self,
        student_id: str,
        assignment_name: str
    ) -> Optional[Submission]:
        """Get only the latest version of a submission"""
        return self.session.query(Submission).join(Student).join(Assignment).filter(
            Student.student_id == student_id,
            Assignment.name == assignment_name,
            Submission.is_latest == True
        ).first()

    def mark_old_versions_as_not_latest(
        self,
        student_id: str,
        assignment_name: str,
        exclude_version: int
    ) -> int:
        """Mark all versions except the specified one as not latest"""
        try:
            # First find the student and assignment IDs
            student = self.session.query(Student).filter_by(student_id=student_id).first()
            assignment = self.session.query(Assignment).filter_by(name=assignment_name).first()

            if not student or not assignment:
                return 0

            # Update without JOIN - SQLAlchemy requires this
            count = self.session.query(Submission).filter(
                Submission.student_id == student.id,
                Submission.assignment_id == assignment.id,
                Submission.version != exclude_version
            ).update({'is_latest': False}, synchronize_session=False)

            self.session.commit()
            return count
        except Exception as e:
            self.session.rollback()
            print(f"Error marking old versions: {e}")
            return 0

    def get_connection(self):
        """Get raw sqlite3 connection for direct SQL operations"""
        from config.settings import settings
        return sqlite3.connect(str(settings.DATABASE_PATH))

    def save_email_body(self, submission_id: int, body_data: Dict) -> bool:
        """Save email body data to submission

        Args:
            submission_id: Submission ID
            body_data: Dict with keys: plain_text, html_markdown, format

        Returns:
            True on success, False on exception
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Serialize body_data to JSON
            json_data = json.dumps(body_data, ensure_ascii=False)

            cursor.execute(
                "UPDATE submissions SET email_body = ? WHERE id = ?",
                (json_data, submission_id)
            )

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error saving email body: {e}")
            return False

    def get_email_body(self, submission_id: int) -> Optional[Dict]:
        """Get email body data from submission

        Args:
            submission_id: Submission ID

        Returns:
            Dict with keys: plain_text, html_markdown, format
            None if not found or on exception
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT email_body FROM submissions WHERE id = ?",
                (submission_id,)
            )

            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                return json.loads(result[0])
            return None

        except Exception as e:
            print(f"Error getting email body: {e}")
            return None

    def close(self):
        """Close database session"""
        self.session.close()

    def get_ai_cache(self, email_uid: str) -> Optional[Dict]:
        """Get cached AI extraction result

        Args:
            email_uid: Email UID from IMAP

        Returns:
            Dict with keys: student_id, name, assignment_name, confidence, is_fallback
            or None if not found
        """
        from database.models import AIExtractionCache

        cache_entry = self.session.query(AIExtractionCache).filter_by(
            email_uid=email_uid
        ).first()

        if not cache_entry:
            return None

        return {
            'student_id': cache_entry.student_id,
            'name': cache_entry.name,
            'assignment_name': cache_entry.assignment_name,
            'confidence': cache_entry.confidence,
            'is_fallback': cache_entry.is_fallback
        }

    def save_ai_cache(self, email_uid: str, result: Dict, is_fallback: bool = False):
        """Save AI extraction result to cache

        Args:
            email_uid: Email UID from IMAP
            result: Dict with student_id, name, assignment_name, confidence
            is_fallback: True if result came from regex fallback
        """
        from database.models import AIExtractionCache

        cache_entry = self.session.query(AIExtractionCache).filter_by(
            email_uid=email_uid
        ).first()

        if cache_entry:
            # Update existing entry
            cache_entry.student_id = result.get('student_id')
            cache_entry.name = result.get('name')
            cache_entry.assignment_name = result.get('assignment_name')
            cache_entry.confidence = result.get('confidence')
            cache_entry.is_fallback = is_fallback
        else:
            # Create new entry
            cache_entry = AIExtractionCache(
                email_uid=email_uid,
                student_id=result.get('student_id'),
                name=result.get('name'),
                assignment_name=result.get('assignment_name'),
                confidence=result.get('confidence'),
                is_fallback=is_fallback
            )
            self.session.add(cache_entry)

        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            print(f"Failed to save AI cache: {e}")
            raise

# Global database operations instance
db = DatabaseOperations()
