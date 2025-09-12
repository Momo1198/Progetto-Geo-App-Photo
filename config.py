

import os
from datetime import timedelta


class Config:
    """Base configuration with security-first approach."""
    
    # Security Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production-8f7d9s6a5d4f3g2h1j0k'
    
    # Upload Configuration
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'tiff', 'webp'}
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(hours=1)
    SESSION_COOKIE_SECURE = True  # Enable in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Application Configuration
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    TESTING = False
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        # Ensure upload folder exists
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)


class DevelopmentConfig(Config):
    """Development-specific configuration."""
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # Allow HTTP in development


class ProductionConfig(Config):
    """Production-specific configuration."""
    DEBUG = False
    # Override with environment variables in production
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable must be set in production")


# Configuration dictionary for easy access
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}