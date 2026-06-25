"""Yoachi Configuration"""
import os

class Config:
    """Base configuration"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'yoachi-dev-secret-key-change-in-production')
    DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'yoachi.db')
    DIZICAL_DATABASE_PATH = os.path.expanduser('~/dev/dizical/data/dizi.db')
    
    # Flask settings
    HOST = '0.0.0.0'
    PORT = 5001
    DEBUG = True
    
    # Sync settings
    SYNC_INTERVAL_SECONDS = 300  # 5 minutes


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')  # Must be set in production
