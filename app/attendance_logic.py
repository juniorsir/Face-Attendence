from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import ShiftConfig

TZ = pytz.timezone('Asia/Kolkata')

def get_current_time_and_shift(db: Session, assigned_shift_name: str):
    """Calculates attendance strictly based on the employee's HR-assigned shift."""
    now = datetime.now(TZ)
    current_time = now.time()
    
    # Fetch ONLY the shift assigned to this specific employee
    my_shift = db.query(ShiftConfig).filter(ShiftConfig.shift_name == assigned_shift_name).first()
    
    if not my_shift:
        raise ValueError(f"Shift rules for '{assigned_shift_name}' not found in the database. Please configure this shift.")

    shift_dt_today = now.replace(hour=my_shift.start_time.hour, minute=my_shift.start_time.minute, second=0, microsecond=0)
    
    # Night Shift Logic (Checking in after midnight belongs to yesterday's shift)
    if my_shift.start_time.hour >= 18 and current_time.hour < 12:
        expected_start_dt = shift_dt_today - timedelta(days=1)
        actual_logical_date = (now - timedelta(days=1)).date()
    else:
        # Day Shift (or checking into a Night shift in the evening)
        expected_start_dt = shift_dt_today
        actual_logical_date = now.date()

    # Calculate lateness based on their SPECIFIC shift start time
    minutes_late = (now - expected_start_dt).total_seconds() / 60.0
    
    shift_status = "Full Shift"

    # Apply Rules
    if isinstance(my_shift.absent_late_minutes, int) and minutes_late >= my_shift.absent_late_minutes:
        shift_status = "Absent"
    elif isinstance(my_shift.half_day_late_minutes, int) and minutes_late >= my_shift.half_day_late_minutes:
        shift_status = "Half Shift"

    db_ready_now = now.replace(tzinfo=None)

    return db_ready_now, actual_logical_date, my_shift.shift_name, shift_status
