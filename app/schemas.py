from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime

# In schemas.py
class AttendanceResponse(BaseModel):
    employee_id: str
    date: date
    entry_time: datetime
    exit_time: Optional[datetime]
    shift_type: str
    shift_status: str
    total_work_time: Optional[str] = None
    overtime_minutes: Optional[int] = 0     # <-- Make Optional
    overtime_hours: Optional[str] = "0h 0m" # <-- Make Optional

    class Config:
        from_attributes = True

class SuccessResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None
