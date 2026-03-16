from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import ShiftConfig

TZ = pytz.timezone('Asia/Kolkata')

def get_current_time_and_shift(db: Session):
    """Dynamically finds the correct shift and safely calculates Full/Half/Absent status."""
    now = datetime.now(TZ)
    current_time = now.time()
    
    shifts = db.query(ShiftConfig).all()
    
    if not shifts:
        raise ValueError("No shift configurations found in the database.")

    best_shift = None
    smallest_diff = float('inf')
    expected_start_dt = None
    actual_logical_date = now.date()

    # 1. Find the closest shift to the current time
    for shift in shifts:
        shift_dt_today = now.replace(hour=shift.start_time.hour, minute=shift.start_time.minute, second=0, microsecond=0)
        
        if shift.start_time.hour >= 18 and current_time.hour < 12: # Night Shift Logic
            shift_dt_yesterday = shift_dt_today - timedelta(days=1)
            diff = abs((now - shift_dt_yesterday).total_seconds())
            if diff < smallest_diff:
                smallest_diff = diff
                best_shift = shift
                expected_start_dt = shift_dt_yesterday
                actual_logical_date = (now - timedelta(days=1)).date()
        else: # Day/Custom Shift Logic
            diff = abs((now - shift_dt_today).total_seconds())
            if diff < smallest_diff:
                smallest_diff = diff
                best_shift = shift
                expected_start_dt = shift_dt_today
                actual_logical_date = now.date()

    if not best_shift:
        raise ValueError("Could not determine a suitable shift for the current time.")

    minutes_late = (now - expected_start_dt).total_seconds() / 60.0
    
    # ------------------ THE BULLETPROOF FIX IS HERE ------------------
    # This logic now safely handles if the database columns are NULL (empty)
    shift_status = "Full Shift"

    # Rule 1: Check for Absent (only if the rule is a valid number)
    if isinstance(best_shift.absent_late_minutes, int) and minutes_late >= best_shift.absent_late_minutes:
        shift_status = "Absent"
    # Rule 2: Check for Half Shift (only if the rule is a valid number)
    elif isinstance(best_shift.half_day_late_minutes, int) and minutes_late >= best_shift.half_day_late_minutes:
        shift_status = "Half Shift"
    # -----------------------------------------------------------------

    db_ready_now = now.replace(tzinfo=None)

    return db_ready_now, actual_logical_date, best_shift.shift_name, shift_status
