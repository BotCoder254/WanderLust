import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    MONGODB_URI = os.environ.get('MONGODB_URI') or 'mongodb://localhost:27017'
    DATABASE_NAME = os.environ.get('DATABASE_NAME') or 'travel_db'
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False
    MAIL_DEBUG = True
    
    # Upload Configuration
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Admin Configuration
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'admin@wanderlust.com')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

    @staticmethod
    def init_app(app):
        if not os.path.exists(os.path.join(app.root_path, Config.UPLOAD_FOLDER)):
            os.makedirs(os.path.join(app.root_path, Config.UPLOAD_FOLDER)) 