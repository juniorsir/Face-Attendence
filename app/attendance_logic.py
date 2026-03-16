from datetime import datetime, timedelta, time
import pytz

TZ = pytz.timezone('Asia/Kolkata')

# Strict Shift Definitions
SHIFTS = {
    'Day': {'start': time(10, 0), 'end': time(18, 0)},
    'Night': {'start': time(20, 30), 'end': time(4, 30)}
}

def evaluate_entry(assigned_shift: str):
    """Evaluates strict entry rules, early check-ins, and wrong shifts."""
    now = datetime.now(TZ)
    current_time = now.time()

    if assigned_shift not in SHIFTS:
        raise ValueError(f"Invalid shift assignment: {assigned_shift}")

    # 1. Define Dates and Shift Boundaries
    if assigned_shift == 'Night':
        # If checking in early morning (12am-12pm), it belongs to yesterday's night shift
        if current_time.hour < 12:
            logical_date = (now - timedelta(days=1)).date()
            expected_start = now.replace(year=logical_date.year, month=logical_date.month, day=logical_date.day, hour=19, minute=30, second=0, microsecond=0)
        else:
            logical_date = now.date()
            expected_start = now.replace(hour=19, minute=30, second=0, microsecond=0)
    else: # Day
        logical_date = now.date()
        expected_start = now.replace(hour=10, minute=0, second=0, microsecond=0)

    # 2. Check for WRONG SHIFT (Attempting to check in during the opposite shift's window)
    if assigned_shift == 'Day':
        # Night window is roughly 7:20 PM to 4:30 AM
        if current_time >= time(19, 20) or current_time <= time(4, 30):
            raise Exception(f"WRONG_SHIFT|{logical_date}|Attempted to check in during Night Shift window. Marked as absent.")
    elif assigned_shift == 'Night':
        # Day window is roughly 9:50 AM to 6:00 PM
        if time(9, 50) <= current_time <= time(18, 0):
            raise Exception(f"WRONG_SHIFT|{logical_date}|Attempted to check in during Day Shift window. Marked as absent.")

    # 3. Calculate Minutes Difference (Negative = Early, Positive = Late)
    minutes_diff = (now - expected_start).total_seconds() / 60.0

    # 4. Check EARLY CHECK-IN Rule (More than 10 mins early)
    if minutes_diff < -2:
        early_time_str = (expected_start - timedelta(minutes=10)).strftime("%I:%M %p")
        raise Exception(f"TOO_EARLY|Too early. Please come after {early_time_str} to mark attendance.")

    # 5. Determine Check-In Status
    if minutes_diff <= 0:
        shift_status = "on_time"
    elif minutes_diff <= 15:
        shift_status = "late_but_full_shift"
    else:
        shift_status = "half_shift"

    return now.replace(tzinfo=None), logical_date, shift_status


def calculate_overtime(assigned_shift: str, logical_date, exit_dt: datetime):
    """Calculates overtime after the official shift ends."""
    if assigned_shift == 'Night':
        expected_start = datetime(logical_date.year, logical_date.month, logical_date.day, 19, 30)
        expected_end = expected_start + timedelta(hours=9) # 4:30 AM next day
    else:
        expected_end = datetime(logical_date.year, logical_date.month, logical_date.day, 18, 0)
        
    expected_end = TZ.localize(expected_end)
    
    overtime_minutes = 0
    overtime_hours_str = "0h 0m"
    
    # Calculate OT only if exit is after expected end time
    if exit_dt > expected_end:
        diff = exit_dt - expected_end
        overtime_minutes = int(diff.total_seconds() / 60)
        
        # Convert to Hours and Minutes
        h, m = divmod(overtime_minutes, 60)
        overtime_hours_str = f"{h}h {m}m"
        
    return overtime_minutes, overtime_hours_str
