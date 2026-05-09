import os
from dotenv import load_dotenv
from pathlib import Path

class Settings:
    def __init__(self, env_path=None):
        if env_path is None:
            env_path = Path(__file__).parent.parent / '.env'
        load_dotenv(env_path)

        self.QQ_EMAIL = os.getenv('QQ_EMAIL')
        self.QQ_PASSWORD = os.getenv('QQ_PASSWORD')
        self.TARGET_FOLDER = os.getenv('TARGET_FOLDER')
        self.LLM_BASE_URL = os.getenv('LLM_BASE_URL')
        self.API_KEY = os.getenv('API_KEY')
        self.LLM_MODEL = os.getenv('LLM_MODEL')
        self.ENABLE_REPLY = os.getenv('ENABLE_REPLY', 'true').lower() == 'true'

        # Multi-assignment submission support
        self.ENABLE_MULTI_ASSIGNMENT = os.getenv('ENABLE_MULTI_ASSIGNMENT', 'true').lower() == 'true'

        self.MULTI_ASSIGNMENT_CONFIG = {
            'enable_subject_detection': os.getenv('ENABLE_SUBJECT_DETECTION', 'true').lower() == 'true',
            'enable_filename_detection': os.getenv('ENABLE_FILENAME_DETECTION', 'true').lower() == 'true',
            'enable_body_detection': os.getenv('ENABLE_BODY_DETECTION', 'true').lower() == 'true',
            'min_confidence_threshold': self._safe_float_conversion(os.getenv('MIN_CONFIDENCE_THRESHOLD', '0.7'), 0.7),
            'strict_mode': os.getenv('STRICT_MODE', 'true').lower() == 'true',
            'max_attachments_per_group': self._safe_int_conversion(os.getenv('MAX_ATTACHMENTS_PER_GROUP', '10'), 10),
            'max_assignments_per_group': self._safe_int_conversion(os.getenv('MAX_ASSIGNMENTS_PER_GROUP', '5'), 5)
        }

        # Email server settings
        self.IMAP_SERVER = "imap.qq.com"
        self.IMAP_PORT = 993
        self.SMTP_SERVER = "smtp.qq.com"
        self.SMTP_PORT = 587

        # Storage paths
        self.BASE_DIR = Path(__file__).parent.parent
        self.SUBMISSIONS_DIR = self.BASE_DIR / 'submissions'
        self.DATABASE_PATH = self.BASE_DIR / 'assignment_submissions.db'

        # Create submissions directory if it doesn't exist
        self.SUBMISSIONS_DIR.mkdir(exist_ok=True)

    def _safe_float_conversion(self, value, default):
        """Safely convert a string value to float, returning default on failure."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _safe_int_conversion(self, value, default):
        """Safely convert a string value to int, returning default on failure."""
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def validate(self):
        required = [
            'QQ_EMAIL', 'QQ_PASSWORD', 'TARGET_FOLDER',
            'LLM_BASE_URL', 'API_KEY', 'LLM_MODEL'
        ]
        missing = [attr for attr in required if not getattr(self, attr)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        return True

# Global settings instance
settings = Settings()
