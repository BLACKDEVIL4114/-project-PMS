"""
PMS 2.0 - Centralized Logging System
Provides consistent logging across all modules.
"""

import logging
import os
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, f"pms_{datetime.now().strftime('%Y-%m')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

def get_logger(name: str) -> logging.Logger:
    """Get a named logger for a module."""
    return logging.getLogger(name)

# Module-level loggers
auth_logger    = get_logger("pms.auth")
api_logger     = get_logger("pms.api")
db_logger      = get_logger("pms.database")
security_logger = get_logger("pms.security")
ui_logger      = get_logger("pms.ui")


def log_login_attempt(username: str, success: bool, role: str = None):
    """Log a login attempt."""
    if success:
        auth_logger.info(f"LOGIN SUCCESS | user='{username}' role='{role}'")
    else:
        security_logger.warning(f"LOGIN FAILED  | user='{username}'")


def log_api_request(endpoint: str, method: str, authenticated: bool, status: int):
    """Log an API request."""
    level = logging.INFO if authenticated else logging.WARNING
    api_logger.log(level, f"API {method} {endpoint} | auth={authenticated} | status={status}")


def log_db_error(operation: str, error: Exception):
    """Log a database error."""
    db_logger.error(f"DB ERROR in '{operation}': {error}", exc_info=True)


def log_security_event(event: str, details: str = ""):
    """Log a security-related event."""
    security_logger.warning(f"SECURITY EVENT: {event} | {details}")
