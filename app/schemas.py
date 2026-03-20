from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

# In schemas.py
class AttendanceResponse(BaseModel):
    employee_id: str
    date: date
    entry_time: str       # Changed to str
    exit_time: str        # Changed to str
    shift_type: str
    shift_status: str
    total_work_time: str  # Changed to str
    overtime_minutes: int
    overtime_hours: str

    class Config:
        from_attributes = True

class EmployeeListResponse(BaseModel):
    employee_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    shift: Optional[str] = None
    employee_status: Optional[str] = None
    is_face_registered: bool

    class Config:
        from_attributes = True
        
class SuccessResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
