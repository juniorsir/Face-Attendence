from datetime import datetime, timedelta
import pytz

# Set Timezone
TZ = pytz.timezone('Asia/Kolkata')

def get_current_time_and_shift():
    """Returns current localized time, logical date, shift_type, and shift_status."""
    now = datetime.now(TZ)
    
    current_time = now.time()
    
    # Defaults
    logical_date = now.date()
    shift_type = ""
    shift_status = "Full Shift"

    # Define Shift Logic
    # DAY SHIFT: 10:00 AM - 6:00 PM (Let's say check-ins between 5:00 AM and 3:00 PM are Day Shift)
    if 5 <= current_time.hour < 15:
        shift_type = "Day"
        expected_start = now.replace(hour=10, minute=0, second=0, microsecond=0)
        
        # 15 minutes grace period
        if now > expected_start + timedelta(minutes=15):
            shift_status = "Half Shift"

    # NIGHT SHIFT: 7:30 PM - 4:30 AM (Next Day)
    # Check-ins between 3:00 PM and 4:59 AM belong to Night Shift
    else:
        shift_type = "Night"
        
        # If logging in after midnight (e.g. 1 AM), it counts as YESTERDAY's night shift
        if current_time.hour < 5:
            logical_date = (now - timedelta(days=1)).date()
            # If arriving after midnight, they are definitely >15 mins late for a 7:30 PM shift
            shift_status = "Half Shift" 
        else:
            # Evening check-in
            expected_start = now.replace(hour=19, minute=30, second=0, microsecond=0)
            if now > expected_start + timedelta(minutes=15):
                shift_status = "Half Shift"

    # Strip timezone info before saving to DB to avoid SQLAlchemy warnings (MySQL DATETIME)
    db_ready_now = now.replace(tzinfo=None)

    return db_ready_now, logical_date, shift_type, shift_status
