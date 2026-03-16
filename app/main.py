import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text, Column, String, Integer
from datetime import datetime, time
from app.logger import log_debug
from app.database import engine, Base, get_db, SessionLocal
from app.models import ExistingEmployee, FaceRegistration, AttendanceLog, ShiftConfig
from app.schemas import AttendanceResponse, SuccessResponse
from app.face_utils import (
    process_image_and_get_encoding, 
    recognize_face, 
    load_encodings_to_cache,
    add_to_cache,
    check_duplicate_face,
    remove_face_cache
)
from app.attendance_logic import evaluate_entry, calculate_overtime, TZ
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
    
def auto_upgrade_database():
    """Automatically patches the database if older tables are missing new columns."""
    inspector = inspect(engine)
    
    # Check if the face_registrations table exists (NOT employees)
    if inspector.has_table("face_registrations"):
        columns = [col['name'] for col in inspector.get_columns("face_registrations")]
        
        with engine.connect() as conn:
            # 1. Check for missing employee_name
            if "employee_name" not in columns:
                conn.execute(text("ALTER TABLE face_registrations ADD COLUMN employee_name VARCHAR(100) DEFAULT 'Unknown'"))
                conn.commit()
                print("✅ Automatically added missing 'employee_name' column to database.")
            
            # 2. Check for missing face_encoding
            if "face_encoding" not in columns:
                conn.execute(text("ALTER TABLE face_registrations ADD COLUMN face_encoding TEXT"))
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
        # 1. Check if employee exists in HR Database
        hr_employee = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == employee_id).first()
        if not hr_employee:
            raise HTTPException(status_code=404, detail=f"Employee ID '{employee_id}' not found in HR system.")
        
        f_name = hr_employee.first_name or "Unknown"
        l_name = hr_employee.last_name or ""
        fetched_full_name = f"{f_name} {l_name}".strip() 
            
        # 2. Check if THIS ID already has a face in the database
        existing_face = db.query(FaceRegistration).filter(FaceRegistration.employee_id == employee_id).first()
        if existing_face:
            raise HTTPException(status_code=400, detail="A face has already been registered for this Employee ID.")
        
        # Process new image
        image_bytes = await image.read()
        encoding = process_image_and_get_encoding(image_bytes)

        # 3. Check for Duplicate Physical Faces in the Cache
        duplicate_id = check_duplicate_face(encoding)
        if duplicate_id:
            # CROSS-CHECK: Did an admin delete this ID from phpMyAdmin?
            still_in_db = db.query(FaceRegistration).filter(FaceRegistration.employee_id == duplicate_id).first()
            if not still_in_db:
                # Yes, it was deleted from DB but stuck in RAM. Clean it up!
                remove_from_cache(duplicate_id)
                log_debug("API_Register", f"Cleared stale cache for manually deleted ID: {duplicate_id}")
            else:
                # Truly a duplicate! Block them.
                raise HTTPException(
                    status_code=400, 
                    detail=f"Security Alert: This physical face is already registered in the system under Employee ID '{duplicate_id}'. Registration denied."
                )
            
        # 4. Save to Database
        encoding_list = encoding.tolist()
        encoding_json = json.dumps(encoding_list)

        new_face_record = FaceRegistration(
            employee_id=employee_id,
            employee_name=fetched_full_name,
            face_encoding=encoding_json
        )
        db.add(new_face_record)
        db.commit()

        # 5. Add to Cache
        add_to_cache(employee_id, encoding)

        return {"status": "success", "message": f"Employee {fetched_full_name} registered successfully."}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        print(f"CRASH IN /register-face: {str(e)}") 
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")
        
@app.post("/attendance/entry", response_model=SuccessResponse)
async def mark_entry(image: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)

        # 1. Fetch Employee from Database
        log_debug("API_Entry", f"Querying HR database for ID: {matched_employee_id}")
        hr_emp = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == matched_employee_id).first()
        
        # Validate Employee Status
        if not hr_emp:
            log_debug("API_Entry", "HR DB Lookup Failed: Employee not found.")
            raise HTTPException(status_code=400, detail="Employee not found in HR system.")
        if hr_emp.employee_status != 'active':
            raise HTTPException(status_code=400, detail="Attendance Denied: Employee status is not active.")
        if not hr_emp.is_approved:
            raise HTTPException(status_code=400, detail="Attendance Denied: Employee profile is not approved.")
        if not hr_emp.shift:
            raise HTTPException(status_code=400, detail="HR Error: No shift assigned to this employee.")

        log_debug("API_Entry", f"HR Data Found -> Status: {hr_emp.employee_status}, Approved: {hr_emp.is_approved}, Shift: {hr_emp.shift}")
        assigned_shift = hr_emp.shift

        # Fetch live shift timings from the database
        shift_config = db.query(ShiftConfig).filter(ShiftConfig.shift_name == assigned_shift).first()
        if not shift_config:
            raise HTTPException(status_code=400, detail=f"Shift configuration for '{assigned_shift}' not found in database.")

        # 2. Evaluate Strict Entry Rules using Database times
        try:
            now, logical_date, shift_status = evaluate_entry(
                assigned_shift, 
                shift_config.start_time, 
                shift_config.end_time,
                shift_config.half_day_late_minutes,
                shift_config.absent_late_minutes
            )
        except Exception as logic_e:
            error_msg = str(logic_e)
            
            # Catch "Too Early" (Reject completely)
            if error_msg.startswith("TOO_EARLY|"):
                raise HTTPException(status_code=400, detail=error_msg.split("|")[1])
            
            # Catch "Wrong Shift" (Log as absent, then reject)
            elif error_msg.startswith("WRONG_SHIFT|"):
                parts = error_msg.split("|")
                wrong_date = datetime.strptime(parts[1], "%Y-%m-%d").date()
                detail_msg = parts[2]
                
                # Prevent duplicate absent logs
                if not db.query(AttendanceLog).filter_by(employee_id=matched_employee_id, date=wrong_date).first():
                    absent_log = AttendanceLog(
                        employee_id=matched_employee_id, date=wrong_date, 
                        entry_time=datetime.now(TZ).replace(tzinfo=None),
                        shift_type=assigned_shift, shift_status="absent_wrong_shift"
                    )
                    db.add(absent_log)
                    db.commit()
                raise HTTPException(status_code=400, detail=detail_msg)
            else:
                raise logic_e

        # 3. Check for Duplicate Entry today
        existing_log = db.query(AttendanceLog).filter(
            AttendanceLog.employee_id == matched_employee_id, 
            AttendanceLog.date == logical_date
        ).first()
        
        if existing_log:
            raise HTTPException(status_code=400, detail=f"Entry already marked for {matched_employee_id} today.")

        # 4. Save Entry
        new_log = AttendanceLog(
            employee_id=matched_employee_id, 
            date=logical_date, 
            entry_time=now,
            shift_type=assigned_shift, 
            shift_status=shift_status
        )
        db.add(new_log)
        db.commit()

        return {"status": "success", "message": f"Entry marked: {shift_status}", "data": {"status": shift_status}}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        print(f"CRASH IN /entry: {str(e)}")
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")
        
@app.post("/attendance/exit", response_model=SuccessResponse)
async def mark_exit(image: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)

        # 1. Fetch Employee from Database
        hr_emp = db.query(ExistingEmployee).filter(ExistingEmployee.employee_id == matched_employee_id).first()
        if not hr_emp or not hr_emp.shift:
            raise HTTPException(status_code=400, detail="HR Error: No shift assigned.")

        # 2. Fetch live shift timings from the database
        shift_config = db.query(ShiftConfig).filter(ShiftConfig.shift_name == hr_emp.shift).first()
        if not shift_config:
            raise HTTPException(status_code=400, detail=f"HR Error: Shift configuration for '{hr_emp.shift}' not found.")

        # 3. Get logical date based on dynamic database shift
        now = datetime.now(TZ)
        is_night_shift = shift_config.start_time > shift_config.end_time
        
        # If the shift crosses midnight, anyone exiting before noon belongs to yesterday's logical shift
        if is_night_shift and now.time().hour < 12:
            logical_date = (now - timedelta(days=1)).date()
        else:
            logical_date = now.date()

        # 4. Find today's entry
        attendance_log = db.query(AttendanceLog).filter(
            AttendanceLog.employee_id == matched_employee_id, AttendanceLog.date == logical_date
        ).first()

        if not attendance_log:
            raise HTTPException(status_code=400, detail="No entry record found for today. Cannot mark exit.")
        if attendance_log.exit_time:
             raise HTTPException(status_code=400, detail="Exit already marked for today.")

        # 5. Overtime Calculation using database times
        ot_mins, ot_hours = calculate_overtime(
            hr_emp.shift, logical_date, now, 
            shift_config.start_time, shift_config.end_time
        )
        
        attendance_log.exit_time = now.replace(tzinfo=None)
        attendance_log.overtime_minutes = ot_mins
        attendance_log.overtime_hours = ot_hours
        
        # 6. Override status to "overtime" if they worked extra
        if ot_mins > 0:
            attendance_log.shift_status = "overtime"

        db.commit()

        return {"status": "success", "message": "Exit marked successfully. Overtime calculated if applicable.", "data": {"overtime": ot_hours}}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        print(f"CRASH IN /exit: {str(e)}")
        raise HTTPException(status_code=500, detail=f"System Crash: {str(e)}")

@app.get("/attendance", response_model=List[AttendanceResponse])
def get_attendance(employee_id: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(AttendanceLog)

    if employee_id:
        query = query.filter(AttendanceLog.employee_id == employee_id)
    if start_date:
        query = query.filter(AttendanceLog.date >= datetime.strptime(start_date, "%Y-%m-%d").date())
    if end_date:
        query = query.filter(AttendanceLog.date <= datetime.strptime(end_date, "%Y-%m-%d").date())

    records = query.order_by(AttendanceLog.date.desc()).all()
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
            work_time = "Shift in progress"

        response_data.append({
            "employee_id": r.employee_id,
            "date": r.date,
            "entry_time": r.entry_time,
            "exit_time": r.exit_time,
            "shift_type": r.shift_type,
            "shift_status": r.shift_status,
            "total_work_time": work_time,
            "overtime_minutes": r.overtime_minutes,
            "overtime_hours": r.overtime_hours
        })

    return response_data
