import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, time
from app.database import engine, Base, get_db, SessionLocal
from app.models import Employee, Attendance, ShiftConfig
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import AttendanceResponse, SuccessResponse
from app.face_utils import (
    process_image_and_get_encoding, 
    recognize_face, 
    load_encodings_to_cache,
    add_to_cache
)
from app.attendance_logic import get_current_time_and_shift

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Face Recognition Attendance API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def on_startup():
    load_encodings_to_cache()
    
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
            print("Successfully inserted Day, Night, and Custom shifts into database.")
    finally:
        db.close()

@app.post("/register-face", response_model=SuccessResponse)
async def register_face(
    employee_id: str = Form(...),
    employee_name: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
 
        existing_emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if existing_emp:
            raise HTTPException(status_code=400, detail="Employee ID already registered.")

        image_bytes = await image.read()
        encoding = process_image_and_get_encoding(image_bytes)
)
        encoding_list = encoding.tolist()
        encoding_json = json.dumps(encoding_list)

        new_employee = Employee(
            employee_id=employee_id,
            employee_name=employee_name,
            face_encoding=encoding_json
        )
        db.add(new_employee)
        db.commit()

        add_to_cache(employee_id, encoding)

        return {"status": "success", "message": f"Employee {employee_name} registered successfully."}

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/attendance/entry", response_model=SuccessResponse)
async def mark_entry(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Match Face
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)

        now, logical_date, shift_type, shift_status = get_current_time_and_shift()

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
            "data": {
                "shift": shift_type,
                "status": shift_status,
                "entry_time": str(now)
            }
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/attendance/exit", response_model=SuccessResponse)
async def mark_exit(
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Match Face
        image_bytes = await image.read()
        matched_employee_id = recognize_face(image_bytes, threshold=0.5)


        now, logical_date, _, _ = get_current_time_and_shift()

        attendance_record = db.query(Attendance).filter(
            Attendance.employee_id == matched_employee_id,
            Attendance.date == logical_date
        ).first()

        if not attendance_record:
            raise HTTPException(status_code=400, detail="No entry record found for today. Cannot mark exit.")

        # Update Exit Time
        attendance_record.exit_time = now
        db.commit()

        return {
            "status": "success", 
            "message": f"Exit marked for {matched_employee_id}",
            "data": {"exit_time": str(now)}
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal Server Error")


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

    return query.order_by(Attendance.date.desc()).all()

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

    # 1. Get records from DB (Notice we DO NOT return here!)
    records = query.order_by(Attendance.date.desc()).all()

    response_data = []

    # 2. Loop through and do the math for every record
    for r in records:
        work_time = None
        
        if r.entry_time and r.exit_time:
            # Math: Exit Time minus Entry Time
            duration = r.exit_time - r.entry_time
            total_seconds = int(duration.total_seconds())
            
            hours, remainder = divmod(total_seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            
            work_time = f"{hours}h {minutes}m"
            
        elif r.entry_time and not r.exit_time:
            work_time = "Shift in progress (No exit marked)"

        # 3. Add the calculated data to our list
        response_data.append({
            "employee_id": r.employee_id,
            "date": r.date,
            "entry_time": r.entry_time,
            "exit_time": r.exit_time,
            "shift_type": r.shift_type,
            "shift_status": r.shift_status,
            "total_work_time": work_time
        })

    # 4. Return the newly calculated list at the VERY END
    return response_data
