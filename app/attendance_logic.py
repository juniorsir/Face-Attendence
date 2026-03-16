from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import ShiftConfig

TZ = pytz.timezone('Asia/Kolkata')

def get_current_time_and_shift(db: Session):
    """Dynamically finds the correct shift from the DB and calculates Full/Half/Absent status."""
    now = datetime.now(TZ)
    current_time = now.time()
    logical_date = now.date()
    
    # Fetch all shift rules from the database
    shifts = db.query(ShiftConfig).all()
    
    if not shifts:
        # Fallback just in case DB is empty
        return now.replace(tzinfo=None), logical_date, "Unknown", "Full Shift"

    best_shift = None
    smallest_diff = float('inf')
    expected_start_dt = None
    actual_logical_date = logical_date

    # 1. Find which shift the employee is checking in for
    for shift in shifts:
        # Create a datetime object for today at this shift's start time
        shift_dt_today = now.replace(hour=shift.start_time.hour, minute=shift.start_time.minute, second=0, microsecond=0)
        
        # Handle Night Shifts (Checking in past midnight belongs to yesterday's night shift)
        if shift.start_time.hour >= 18 and current_time.hour < 12:
            shift_dt_yesterday = shift_dt_today - timedelta(days=1)
            diff = abs((now - shift_dt_yesterday).total_seconds())
            if diff < smallest_diff:
                smallest_diff = diff
                best_shift = shift
                expected_start_dt = shift_dt_yesterday
                actual_logical_date = (now - timedelta(days=1)).date()
        else:
            diff = abs((now - shift_dt_today).total_seconds())
            if diff < smallest_diff:
                smallest_diff = diff
                best_shift = shift
                expected_start_dt = shift_dt_today
                actual_logical_date = now.date()

    # 2. Calculate exactly how many minutes late they are
    minutes_late = (now - expected_start_dt).total_seconds() / 60.0
    
    # 3. Apply the dynamic rules from the Database!
    shift_status = "Full Shift"
    
    if minutes_late >= best_shift.absent_late_minutes: # e.g., 120 mins (2 hours)
        shift_status = "Absent"
    elif minutes_late >= best_shift.half_day_late_minutes: # e.g., 15 mins
        shift_status = "Half Shift"

    # Strip timezone for MySQL saving
    db_ready_now = now.replace(tzinfo=None)

    return db_ready_now, actual_logical_date, best_shift.shift_name, shift_status
