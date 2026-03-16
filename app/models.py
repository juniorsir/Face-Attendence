from sqlalchemy import Column, Integer, String, Text, DateTime, Date, Time
from datetime import datetime
from app.database import Base

class Employee(Base):
    __tablename__ = "employees"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    employee_name = Column(String(100), nullable=False)
    face_encoding = Column(Text, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow)

class Attendance(Base):
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False) 
    entry_time = Column(DateTime, nullable=False)
    exit_time = Column(DateTime, nullable=True)
    shift_type = Column(String(50), nullable=False)   
    shift_status = Column(String(50), nullable=False) 


class FaceRegistration(Base):
    __tablename__ = "face_registrations" # The new, safe table name

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)
    employee_name = Column(String(100), nullable=False)
    face_encoding = Column(Text, nullable=False) 
    created_at = Column(DateTime, default=datetime.utcnow)
    
# NEW: Dynamic Shift Configurations Table
class ShiftConfig(Base):
    __tablename__ = "shift_configs"
    id = Column(Integer, primary_key=True, index=True)
    shift_name = Column(String(50), unique=True, nullable=False) # "Day", "Night", "Custom"
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    half_day_late_minutes = Column(Integer, default=15) # Late by 15 mins = Half Shift
    absent_late_minutes = Column(Integer, default=120)  # Late by 120 mins (2 hrs) = Absent
