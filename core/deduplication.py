from datetime import datetime
from database.operations import db
from core.version_manager import version_manager
from mail.imap_client import imap_client_inbox
from mail.smtp_client import smtp_client
from config.settings import settings

class DeduplicationHandler:
    """Handle duplicate submissions - create new versions instead of replacing"""

    def __init__(self):
        self.db = db
        self.version_manager = version_manager

    async def is_duplicate(self, student_id: str, student_name: str,
                          assignment_name: str) -> bool:
        """Check if submission already exists"""
        existing = self.db.get_latest_submission(student_id, assignment_name)
        return existing is not None

    async def handle_duplicate(
        self,
        new_email_uid: str,
        student_id: str,
        student_name: str,
        assignment_name: str,
        sender_email: str,
        attachments: list
    ) -> dict:
        """
        Handle duplicate submission by creating new version

        Flow:
        1. Get next version number
        2. Create new version folder (v2/, v3/, etc.)
        3. Save new attachments
        4. Update database (mark old as not latest)
        5. Move new email to target folder
        6. Send update confirmation email
        """
        try:
            # 1. Get next version
            next_version = self.version_manager.get_next_version(
                student_id, student_name, assignment_name
            )

            # 2. Create version folder
            version_folder = self.version_manager.create_version_folder(
                student_id, student_name, assignment_name, next_version
            )

            # 3. Save attachments
            if attachments:
                for attachment in attachments:
                    filename = attachment['filename']
                    content = attachment['content']
                    file_path = version_folder / filename
                    with open(file_path, 'wb') as f:
                        f.write(content)

            # 4. Update database
            # Mark old versions as not latest
            self.db.mark_old_versions_as_not_latest(
                student_id, assignment_name, next_version
            )

            # Create new submission record
            submission = self.db.create_submission(
                student_id=student_id,
                assignment_name=assignment_name,
                email_uid=new_email_uid,
                email_subject=f"{student_id}{student_name}-{assignment_name}",
                sender_email=sender_email,
                sender_name=student_name,
                submission_time=datetime.now(),
                local_path=str(version_folder),
                version=next_version,
                is_latest=True
            )

            if not submission:
                return {'success': False, 'error': 'Failed to update database'}

            # 5. Move new email to target folder
            imap_client_inbox.move_email(new_email_uid, settings.TARGET_FOLDER)

            # 6. Send update confirmation email
            smtp_client.send_reply(
                to_email=sender_email,
                student_name=student_name,
                assignment_name=assignment_name,
                custom_message="你的作业已更新为最新版本。"
            )

            # 7. Log action
            self.db.log_email_action(
                email_uid=new_email_uid,
                action='updated',
                folder=settings.TARGET_FOLDER,
                details=f"Updated to version {next_version} for {student_id} - {assignment_name}"
            )

            return {
                'success': True,
                'message': f'Duplicate submission updated to version {next_version}',
                'version': next_version,
                'local_path': str(version_folder)
            }

        except Exception as e:
            print(f"Error handling duplicate: {e}")
            return {'success': False, 'error': str(e)}

    async def check_and_handle_duplicate(
        self,
        student_id: str,
        student_name: str,
        assignment_name: str,
        email_uid: str,
        sender_email: str,
        email_subject: str,
        attachments: list
    ) -> tuple:
        """
        Check and handle duplicate submission

        Returns:
            (is_duplicate, result_dict)
        """
        is_dup = await self.is_duplicate(student_id, student_name, assignment_name)

        if is_dup:
            result = await self.handle_duplicate(
                new_email_uid=email_uid,
                student_id=student_id,
                student_name=student_name,
                assignment_name=assignment_name,
                sender_email=sender_email,
                attachments=attachments
            )
            return True, result
        else:
            return False, None

# Global instance
deduplication_handler = DeduplicationHandler()