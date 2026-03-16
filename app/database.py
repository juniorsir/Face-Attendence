import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# The new "switch" environment variable
# Defaults to 'external' (MySQL) if not set
DATABASE_TYPE = os.getenv("DATABASE_TYPE", "external").lower()

if DATABASE_TYPE == "internal":
    # --- INTERNAL DATABASE (SQLite) ---
    # Creates a file named 'local_attendance.db' in the project root.
    # Perfect for testing without a real database server.
    
    print("✅ Initializing INTERNAL SQLite database...")
    
    SQLALCHEMY_DATABASE_URL = "sqlite:///./local_attendance.db"
    
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, 
        # This argument is required for SQLite to work with FastAPI
        connect_args={"check_same_thread": False}
    )

else:
    # --- EXTERNAL DATABASE (MySQL) ---
    # Reads all credentials from environment variables.
    # This is for your production Hostinger database.

    print("✅ Initializing EXTERNAL MySQL database...")

    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_USER = os.getenv("DB_USERNAME", os.getenv("DB_USER", "root"))
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_DATABASE", os.getenv("DB_NAME", "attendance_db"))
    DB_PORT = os.getenv("DB_PORT", "3306")

    # Safely encode the password for the connection URL
    encoded_password = urllib.parse.quote_plus(DB_PASSWORD)

    SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=3600
    )

# This part of the code is the same for both databases
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def log_debug(message):
    """Prints logs only if DEBUG_MODE is set to 'true'."""
    if os.getenv("DEBUG_MODE", "false").lower() == "true":
        print(f"DEBUG [ {datetime.now().strftime('%H:%M:%S')} ]: {message}")
