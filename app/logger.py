import os
from datetime import datetime

# Read DEBUG_MODE from environment variables. Default is False.
# Accepts "true", "1", or "yes" to enable.
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes", "t")

def log_debug(module: str, message: str):
    """Prints detailed logs only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[DEBUG] [{timestamp}] [{module}] {message}")
