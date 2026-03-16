from datetime import datetime, timedelta
import pytz
from sqlalchemy.orm import Session
from app.models import ShiftConfig

TZ = pytz.timezone('Asia/Kolkata')

def get_current_time_and_shift(db: Session):
    """Dynamically finds the correct shift from the DB and calculates Full/Half/Absent status."""
    now = datetime.now(TZ)
    current_time = now.time()
    
    # Fetch all shift rules from the database
    shifts = db.query(ShiftConfig).all()
    
    if not shifts:
        # If the shift_configs table is empty, raise an error immediately.
        raise ValueError("No shift configurations found in the database. Please add shifts via phpMyAdmin or restart the app.")

    best_shift = None
    smallest_diff = float('inf')
    expected_start_dt = None
    actual_logical_date = now.date()

    # 1. Loop to find the closest shift to the current time
    for shift in shifts:
        shift_dt_today = now.replace(hour=shift.start_time.hour, minute=shift.start_time.minute, second=0, microsecond=0)
        
        # Handle Night Shifts (checking in early morning belongs to yesterday's shift)
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

    # ------------------ THE CRUCIAL FIX IS HERE ------------------
    # If after all that, we still didn't find a shift, it's a critical failure.
    if not best_shift:
        raise ValueError("Could not determine a suitable shift for the current time. Please check shift configurations.")
    # -------------------------------------------------------------

    # 2. Calculate exactly how many minutes late they are
    minutes_late = (now - expected_start_dt).total_seconds() / 60.0
    
    # 3. Apply the dynamic rules from the Database!
    shift_status = "Full Shift"
    
    if minutes_late >= best_shift.absent_late_minutes:
        shift_status = "Absent"
    elif minutes_late >= best_shift.half_day_late_minutes:
        shift_status = "Half Shift"

    # Strip timezone for MySQL saving
    db_ready_now = now.replace(tzinfo=None)

    return db_ready_now, actual_logical_date, best_shift.shift_name, shift_status
