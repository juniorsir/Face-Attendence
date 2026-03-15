import json
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from app.database import engine, Base, get_db
from app.models import Employee, Attendance
from fastapi.middleware.cors import CORSMiddleware
from app.schemas import AttendanceResponse, SuccessResponse
from app.face_utils import (
    process_image_and_get_encoding, 
    recognize_face, 
    load_encodings_to_cache,
    add_to_cache
)
from app.attendance_logic import get_current_time_and_shift

# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Face Recognition Attendance API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows any HTML file to test the API
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
@app.on_event("startup")
def on_startup():
    # Load all face encodings into RAM on startup for fast matching
    load_encodings_to_cache()

@app.post("/register-face", response_model=SuccessResponse)
async def register_face(
    employee_id: str = Form(...),
    employee_name: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    try:
        # Check if employee already exists
        existing_emp = db.query(Employee).filter(Employee.employee_id == employee_id).first()
        if existing_emp:
            raise HTTPException(status_code=400, detail="Employee ID already registered.")

        # Process image and get encoding
        image_bytes = await image.read()
        encoding = process_image_and_get_encoding(image_bytes)
        
        # Save to DB (Store as JSON string)
        encoding_list = encoding.tolist()
        encoding_json = json.dumps(encoding_list)

        new_employee = Employee(
            employee_id=employee_id,
            employee_name=employee_name,
            face_encoding=encoding_json
        )
        db.add(new_employee)
        db.commit()

        # Update cache dynamically
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

        # Determine Shift and Late logic
        now, logical_date, shift_type, shift_status = get_current_time_and_shift()

        # Check if already checked in for this logical date
        existing_attendance = db.query(Attendance).filter(
            Attendance.employee_id == matched_employee_id,
            Attendance.date == logical_date
        ).first()

        if existing_attendance:
            raise HTTPException(status_code=400, detail=f"Entry already marked for {matched_employee_id} today.")

        # Mark Attendance
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

        # Get Current time logic
        now, logical_date, _, _ = get_current_time_and_shift()

        # Find today's entry record
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
