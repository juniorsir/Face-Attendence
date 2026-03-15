import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Fetch database credentials from environment variables
# Supporting both your specific names (DB_USERNAME) and default ones
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USERNAME", os.getenv("DB_USER", "root"))
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_DATABASE", os.getenv("DB_NAME", "attendance_db"))
DB_PORT = os.getenv("DB_PORT", "3306")

# CRITICAL FIX: URL-encode the password so the '@' symbol doesn't break SQLAlchemy
encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

# MySQL Connection URL
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Engine setup
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # Automatically tests connection before using
    pool_recycle=3600    # Prevents connection timeouts on Render
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
