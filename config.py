import os
from pathlib import Path
from dotenv import load_dotenv

# Automatically look for a .env file in the current project directory
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

class Config:
    # SMTP Configuration
    SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
    SMTP_USER = os.getenv('SMTP_USER', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')

    # Mailgun Configuration
    MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY', '')
    MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN', '')

    # LinkedIn Configuration
    LINKEDIN_USERNAME = os.getenv('LINKEDIN_USERNAME', '')
    LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD', '')

    # Hunter.io Configuration
    HUNTER_API_KEY = os.getenv('HUNTER_API_KEY', '')

    # Tracking Configuration
    TRACKING_SERVER_URL = os.getenv('TRACKING_SERVER_URL', 'http://localhost:5000')

    # General Directories
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR / 'data'
    DB_PATH = DATA_DIR / 'sent_log.db'
    LEADS_CSV_PATH = DATA_DIR / 'leads.csv'

    @classmethod
    def initialize_dirs(cls):
        """Creates the data/ directory structure if it doesn't exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
