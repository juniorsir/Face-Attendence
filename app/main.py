import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, Column, String, Integer
from datetime import datetime, time

from app.database import engine, Base, get_db, SessionLocal
from app.models import FaceRegistration, Attendance, ShiftConfig
from app.schemas import AttendanceResponse, SuccessResponse
from app.face_utils import (
    process_image_and_get_encoding, 
    recognize_face, 
    load_encodings_to_cache,
    add_to_cache,
    check_duplicate_face
)
from app.attendance_logic import get_current_time_and_shift

# Automatically create tables if they DO NOT exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Face Recognition Attendance API")

# Enable CORS for HTML testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Replace your current ExistingEmployee class with this one:
# --- CHANGE THIS ---
class ExistingEmployee(Base):
    __tablename__ = 'employees'
    __table_args__ = {'info': dict(is_existing=True)}

    id = Column(Integer, primary_key=True)
    employee_id = Column(String(255), unique=True)
    first_name = Column(String(255)) # CHANGED: Pull first_name from DB
    last_name = Column(String(255))  # CHANGED: Pull last_name from DB
    shift = Column(String(50))       # Pull assigned shift from DB
    
def auto_upgrade_database():
    """Automatically patches the database if older tables are missing new columns."""
    inspector = inspect(engine)
    
    # Check if the employees table exists
    if inspector.has_table("employees"):
        columns = [col['name'] for col in inspector.get_columns("employees")]
        
        with engine.connect() as conn:
            # 1. Check for missing employee_name
            if "employee_name" not in columns:
                conn.execute(text("ALTER TABLE employees ADD COLUMN employee_name VARCHAR(100) DEFAULT 'Unknown' AFTER employee_id"))
                conn.commit()
                print("✅ Automatically added missing 'employee_name' column to database.")
            
            # 2. Check for missing face_encoding
            if "face_encoding" not in columns:
                # We use TEXT because the face encoding is a long JSON array of 128 numbers
                conn.execute(text("ALTER TABLE employees ADD COLUMN face_encoding TEXT"))
                conn.commit()
                print("✅ Automatically added missing 'face_encoding' column to database.")

@app.on_event("startup")
def on_startup():
    # 1. Automatically fix database schemas if needed (No manual DB changes required)
    auto_upgrade_database()

    # 2. Insert default Shifts if they don't exist
    db = SessionLocal()
    try:
        if db.query(ShiftConfig).count() == 0:
            default_shifts = [
                ShiftConfig(shift_name="Day", start_time=time(10, 0), end_time=time(18, 0), half_day_late_minutes=15, absent_late_minutes=120),
                ShiftConfig(shift_name="Night", start_time=time(19, 30), end_time=time(4, 30), half_day_late_minutes=15, absent_late_minutes=120),
                ShiftConfig(shift_name="Custom", start_time=time(14, 0), end_time=time(22, 0), half_day_late_minutes=15, absent_late_minutes=120)
            ]
            db.add_all(default_shifts)
            db.commit()
            print("✅ Successfully inserted Day, Night, and Custom shifts into database.")
    except Exception as e:
        print(f"Error checking shifts: {e}")
    finally:
        db.close()

    # 3. Load faces into memory
    load_encodings_to_cache()


# -----------------------------------------
# NEW: Health Endpoint
# -----------------------------------------
@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Check if the API is running and connected to the database."""
    try:
        # Run a simple query to ensure the database is actively responding
        db.execute(text("SELECT 1"))
        return {
            "status": "online",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail="Database connection failed")


# -----------------------------------------
# Existing Endpoints
# -----------------------------------------
@app.post("/register-face", response_model=SuccessResponse)
async def register_face(
    employee_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        hr_employee = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == employee_id).first()
        if not hr_employee:
            raise HTTPException(status_code=404, detail=f"Employee ID '{employee_id}' not found in HR system.")
        # Get their real name from the database!
        f_name = hr_employee.first_name or "Unknown"
        l_name = hr_employee.last_name or ""
        fetched_full_name = f"{f_name} {l_name}".strip() # Combine them nicely
            
        existing_face = db.query(FaceRegistration).filter(FaceRegistration.employee_id == employee_id).first()
        if existing_face:
            raise HTTPException(status_code=400, detail="A face has already been registered for this Employee ID.")
        image_bytes = await image.read()
        encoding = process_image_and_get_encoding(image_bytes)

        duplicate_id = check_duplicate_face(encoding)
        if duplicate_id:
            raise HTTPException(
                status_code=400, 
                detail=f"Security Alert: This physical face is already registered in the system under Employee ID '{duplicate_id}'. Registration denied."
            )
            
        encoding_list = encoding.tolist()
        encoding_json = json.dumps(encoding_list)

        new_face_record = FaceRegistration(
            employee_id=employee_id,
            employee_name=fetched_full_name,
            face_encoding=encoding_json
        )
        db.add(new_face_record)
        db.commit()

        add_to_cache(employee_id, encoding)

        return {"status": "success", "message": f"Employee {fetched_full_name} registered successfully."}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        # Re-raise HTTPExceptions directly to preserve status code and detail
        raise
    except Exception as e:
        # RETURN THE EXACT ERROR DETAIL INSTEAD OF "Internal Server Error"
        print(f"CRASH IN /register-face: {str(e)}") # Also log it to Render console
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")

@app.post("/attendance/entry", response_model=SuccessResponse)
async def mark_entry(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)

        hr_employee = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == matched_employee_id).first()
        
        if not hr_employee or not hr_employee.shift:
            raise HTTPException(status_code=400, detail=f"HR Error: No shift assigned to employee {matched_employee_id} in the main database.")
        
        assigned_shift = hr_employee.shift # Gets 'Day' or 'Night'

        # Calculate time based on THEIR shift
        now, logical_date, shift_type, shift_status = get_current_time_and_shift(db, assigned_shift)
        
        existing_attendance = db.query(Attendance).filter(
            Attendance.employee_id == matched_employee_id,
            Attendance.date == logical_date
        ).first()

        if existing_attendance:
            raise HTTPException(status_code=400, detail=f"Entry already marked for {matched_employee_id} today.")

        new_attendance = Attendance(
            employee_id=matched_employee_id,
            date=logical_date,
            entry_time=now,
            shift_type=shift_type,
            shift_status=shift_status
        )
        db.add(new_attendance)
        db.commit()

        return {
            "status": "success", 
            "message": f"Entry marked for {matched_employee_id}",
            "data": {"shift": shift_type, "status": shift_status, "entry_time": str(now)}
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        # RETURN THE EXACT ERROR DETAIL INSTEAD OF "Internal Server Error"
        print(f"CRASH IN /attendance/entry: {str(e)}") # Also log it to Render console
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")

@app.post("/attendance/exit", response_model=SuccessResponse)
async def mark_exit(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)

        hr_employee = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == matched_employee_id).first()
        
        if not hr_employee or not hr_employee.shift:
            raise HTTPException(status_code=400, detail=f"HR Error: No shift assigned to employee {matched_employee_id} in the main database.")
        
        assigned_shift = hr_employee.shift # Gets 'Day' or 'Night'

        # Calculate time based on THEIR shift
        now, logical_date, shift_type, shift_status = get_current_time_and_shift(db, assigned_shift)

        attendance_record = db.query(Attendance).filter(
            Attendance.employee_id == matched_employee_id,
            Attendance.date == logical_date
        ).first()

        if not attendance_record:
            raise HTTPException(status_code=400, detail="No entry record found for today. Cannot mark exit.")

        attendance_record.exit_time = now
        db.commit()

        return {
            "status": "success", 
            "message": f"Exit marked for {matched_employee_id}",
            "data": {"exit_time": str(now)}
        }

    # ... inside mark_exit ...
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        # RETURN THE EXACT ERROR DETAIL INSTEAD OF "Internal Server Error"
        print(f"CRASH IN /attendance/exit: {str(e)}") # Also log it to Render console
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")

@app.get("/attendance", response_model=List[AttendanceResponse])
def get_attendance(
    employee_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Attendance)

    if employee_id:
        query = query.filter(Attendance.employee_id == employee_id)
    if start_date:
        query = query.filter(Attendance.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(Attendance.date <= datetime.strptime(end_date, "%Y-%m-%d").date())

    records = query.order_by(Attendance.date.desc()).all()
    response_data = []

    for r in records:
        work_time = None
        
        if r.entry_time and r.exit_time:
            duration = r.exit_time - r.entry_time
            total_seconds = int(duration.total_seconds())
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            work_time = f"{hours}h {minutes}m"
        elif r.entry_time and not r.exit_time:
            work_time = "Shift in progress (No exit marked)"

        response_data.append({
            "employee_id": r.employee_id,
            "date": r.date,
            "entry_time": r.entry_time,
            "exit_time": r.exit_time,
            "shift_type": r.shift_type,
            "shift_status": r.shift_status,
            "total_work_time": work_time
        })

    return response_data
