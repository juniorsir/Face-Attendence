from sqlalchemy import Column, Integer, String, Text, DateTime, Date
from datetime import datetime
from app.database import Base

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    employee_name = Column(String(100), nullable=False)
    face_encoding = Column(Text, nullable=False) # Stores JSON stringified numpy array
    created_at = Column(DateTime, default=datetime.utcnow)

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False) # Logical date for the shift
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    shift_type = Column(String(20), nullable=False)   # "Day" or "Night"
    shift_status = Column(String(20), nullable=False) # "Full Shift" or "Half Shift"
