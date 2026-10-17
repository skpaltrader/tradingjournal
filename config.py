import os

# Try loading .env if python-dotenv is installed
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Config:
    # Security & Sessions
    SECRET_KEY = os.environ.get('SECRET_KEY', 'quotex-secret-session-key-2026-prod')
    
    # Admin Credentials (can be set via environment variables or .env)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'skpaltrader')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'success*')
    
    # Uploads directory
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB max upload
    
    # Server port (defaults to 8000, compatible with Render / Railway PORT env)
    PORT = int(os.environ.get('PORT', 8000))
    HOST = '0.0.0.0'
