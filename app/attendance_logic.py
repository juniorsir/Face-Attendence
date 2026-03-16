from datetime import datetime, timedelta, time
import pytz
from app.logger import log_debug

TZ = pytz.timezone('Asia/Kolkata')

def evaluate_entry(assigned_shift: str, shift_start: time, shift_end: time, late_grace_period: int = 15):
    now = datetime.now(TZ)
    current_time = now.time()
    
    log_debug("Attendance_Logic", f"Evaluating entry at {current_time} for shift: {assigned_shift}")

    # Determine if it's a night shift (Start time is later than End time, crossing midnight)
    is_night_shift = shift_start > shift_end

    if is_night_shift:
        # If they log in past midnight but before noon, the logical date is "yesterday"
        if current_time.hour < 12:
            logical_date = (now - timedelta(days=1)).date()
            expected_start = now.replace(year=logical_date.year, month=logical_date.month, day=logical_date.day, hour=shift_start.hour, minute=shift_start.minute, second=0, microsecond=0)
        else:
            logical_date = now.date()
            expected_start = now.replace(hour=shift_start.hour, minute=shift_start.minute, second=0, microsecond=0)
    else: 
        logical_date = now.date()
        expected_start = now.replace(hour=shift_start.hour, minute=shift_start.minute, second=0, microsecond=0)

    log_debug("Attendance_Logic", f"Logical Date: {logical_date}, Expected Start: {expected_start.strftime('%I:%M %p')}")

    minutes_diff = (now - expected_start).total_seconds() / 60.0
    log_debug("Attendance_Logic", f"Time difference from expected start: {minutes_diff:.2f} minutes")

    # Dynamic wrong shift prevention: 
    # If they log in >6 hours BEFORE their shift or >12 hours AFTER, reject them.
    if minutes_diff < -360 or minutes_diff > 720:
        log_debug("Attendance_Logic", "Rejected: Attempting to log in completely outside shift window.")
        raise Exception(f"WRONG_SHIFT|{logical_date}|Attempted to check in outside of your Shift window. Marked as absent.")

    # Too Early Check (<-10 mins)
    if minutes_diff < -10:
        early_time_str = (expected_start - timedelta(minutes=10)).strftime("%I:%M %p")
        log_debug("Attendance_Logic", f"Rejected: Too early (<-10 mins).")
        raise Exception(f"TOO_EARLY|Too early. Please come after {early_time_str} to mark attendance.")

    if minutes_diff <= 0:
        shift_status = "on_time"
    elif minutes_diff <= late_grace_period:
        shift_status = "late_but_full_shift"
    else:
        shift_status = "half_shift"

    log_debug("Attendance_Logic", f"Final determined status: {shift_status}")
    return now.replace(tzinfo=None), logical_date, shift_status


def calculate_overtime(assigned_shift: str, logical_date, exit_dt: datetime, shift_start: time, shift_end: time):
    log_debug("Attendance_Logic", f"Calculating overtime for exit at {exit_dt.strftime('%I:%M %p')}")
    
    is_night_shift = shift_start > shift_end
    
    # Calculate official end datetime dynamically
    if is_night_shift:
        # Shift ends on the NEXT calendar day relative to the logical date
        expected_end = datetime(logical_date.year, logical_date.month, logical_date.day, shift_end.hour, shift_end.minute) + timedelta(days=1)
    else:
        expected_end = datetime(logical_date.year, logical_date.month, logical_date.day, shift_end.hour, shift_end.minute)
        
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
