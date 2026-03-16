from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Time
from datetime import datetime
from app.database import Base

# 1. Official HR Employees Table (Read-Only)
class ExistingEmployee(Base):
    __tablename__ = 'employees'
    __table_args__ = {'info': dict(is_existing=True)} 

    id = Column(Integer, primary_key=True)
    employee_id = Column(String(255), unique=True)
    first_name = Column(String(255))
    last_name = Column(String(255))
    shift = Column(String(50))
    employee_status = Column(String(50)) # Added for validation
    is_approved = Column(Integer)        # Added for validation (tinyint)

# 2. Our Face Recognition Table
class FaceRegistration(Base):
    __tablename__ = "face_registrations"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    employee_name = Column(String(100), nullable=False)
    face_encoding = Column(Text, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow)

# 3. NEW: Attendance Logs Table (Replacing the old basic attendance table)
class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False) 
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    shift_type = Column(String(50), nullable=False)   
    shift_status = Column(String(50), nullable=False) 
    # New Overtime Fields
    overtime_minutes = Column(Integer, default=0)
    overtime_hours = Column(String(50), default="0h 0m")
