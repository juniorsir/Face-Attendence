from datetime import datetime, timedelta, time
import pytz
from app.logger import log_debug # <-- Import the logger

TZ = pytz.timezone('Asia/Kolkata')

SHIFTS = {
    'Day': {'start': time(10, 0), 'end': time(18, 0)},
    'Night': {'start': time(19, 30), 'end': time(4, 30)}
}

def evaluate_entry(assigned_shift: str):
    now = datetime.now(TZ)
    current_time = now.time()
    
    log_debug("Attendance_Logic", f"Evaluating entry at {current_time} for shift: {assigned_shift}")

    if assigned_shift not in SHIFTS:
        raise ValueError(f"Invalid shift assignment: {assigned_shift}")

    if assigned_shift == 'Night':
        if current_time.hour < 12:
            logical_date = (now - timedelta(days=1)).date()
            expected_start = now.replace(year=logical_date.year, month=logical_date.month, day=logical_date.day, hour=19, minute=30, second=0, microsecond=0)
        else:
            logical_date = now.date()
            expected_start = now.replace(hour=19, minute=30, second=0, microsecond=0)
    else: 
        logical_date = now.date()
        expected_start = now.replace(hour=10, minute=0, second=0, microsecond=0)

    log_debug("Attendance_Logic", f"Logical Date: {logical_date}, Expected Start: {expected_start.strftime('%I:%M %p')}")

    if assigned_shift == 'Day':
        if current_time >= time(19, 20) or current_time <= time(4, 30):
            log_debug("Attendance_Logic", "Rejected: Day shift employee attempting to log in during Night shift.")
            raise Exception(f"WRONG_SHIFT|{logical_date}|Attempted to check in during Night Shift window. Marked as absent.")
    elif assigned_shift == 'Night':
        if time(9, 50) <= current_time <= time(18, 0):
            log_debug("Attendance_Logic", "Rejected: Night shift employee attempting to log in during Day shift.")
            raise Exception(f"WRONG_SHIFT|{logical_date}|Attempted to check in during Day Shift window. Marked as absent.")

    minutes_diff = (now - expected_start).total_seconds() / 60.0
    log_debug("Attendance_Logic", f"Time difference from expected start: {minutes_diff:.2f} minutes")

    if minutes_diff < -10:
        early_time_str = (expected_start - timedelta(minutes=10)).strftime("%I:%M %p")
        log_debug("Attendance_Logic", f"Rejected: Too early (<-10 mins).")
        raise Exception(f"TOO_EARLY|Too early. Please come after {early_time_str} to mark attendance.")

    if minutes_diff <= 0:
        shift_status = "on_time"
    elif minutes_diff <= 15:
        shift_status = "late_but_full_shift"
    else:
        shift_status = "half_shift"

    log_debug("Attendance_Logic", f"Final determined status: {shift_status}")
    return now.replace(tzinfo=None), logical_date, shift_status


def calculate_overtime(assigned_shift: str, logical_date, exit_dt: datetime):
    log_debug("Attendance_Logic", f"Calculating overtime for exit at {exit_dt.strftime('%I:%M %p')}")
    
    if assigned_shift == 'Night':
        expected_end = datetime(logical_date.year, logical_date.month, logical_date.day, 19, 30) + timedelta(hours=9)
    else:
        expected_end = datetime(logical_date.year, logical_date.month, logical_date.day, 18, 0)
        
    expected_end = TZ.localize(expected_end)
    log_debug("Attendance_Logic", f"Official Shift End Time: {expected_end.strftime('%I:%M %p')}")
    
    overtime_minutes = 0
    overtime_hours_str = "0h 0m"
    
    if exit_dt > expected_end:
        diff = exit_dt - expected_end
        overtime_minutes = int(diff.total_seconds() / 60)
        h, m = divmod(overtime_minutes, 60)
        overtime_hours_str = f"{h}h {m}m"
        log_debug("Attendance_Logic", f"Overtime qualified: {overtime_minutes} total minutes ({overtime_hours_str})")
    else:
        log_debug("Attendance_Logic", "Exit time is before or exactly at shift end. No overtime.")
        
    return overtime_minutes, overtime_hours_str
