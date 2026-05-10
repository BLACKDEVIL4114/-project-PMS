"""
PMS 2.0 - Input Validation Module
All user input validation in one place. Prevents injection, bad data, and crashes.
"""

import re
import sqlite3
from datetime import datetime
from config import (
    PASSWORD_MIN_LENGTH, PASSWORD_REQUIRE_UPPER,
    PASSWORD_REQUIRE_LOWER, PASSWORD_REQUIRE_DIGIT,
    PASSWORD_REQUIRE_SYMBOL
)

# ─────────────────────────────────────────────
# Result Helper
# ─────────────────────────────────────────────
class ValidationResult:
    """Carries validation outcome and human-readable errors."""
    def __init__(self, valid: bool, errors: list = None):
        self.valid  = valid
        self.errors = errors or []

    def __bool__(self):
        return self.valid

    def first_error(self) -> str:
        return self.errors[0] if self.errors else ""

    def all_errors(self) -> str:
        return "\n".join(self.errors)


# ─────────────────────────────────────────────
# Password
# ─────────────────────────────────────────────
def validate_password(password: str) -> ValidationResult:
    """
    Enforces password policy from config.py.
    Returns ValidationResult with list of failing rules.
    """
    errors = []
    if not password:
        return ValidationResult(False, ["Password cannot be empty."])
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Must be at least {PASSWORD_MIN_LENGTH} characters long.")
    if PASSWORD_REQUIRE_UPPER and not re.search(r"[A-Z]", password):
        errors.append("Must contain at least one uppercase letter.")
    if PASSWORD_REQUIRE_LOWER and not re.search(r"[a-z]", password):
        errors.append("Must contain at least one lowercase letter.")
    if PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        errors.append("Must contain at least one digit (0-9).")
    if PASSWORD_REQUIRE_SYMBOL and not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        errors.append("Must contain at least one special character (!@#$%^&* etc.).")
    return ValidationResult(len(errors) == 0, errors)


# ─────────────────────────────────────────────
# Name / Username
# ─────────────────────────────────────────────
def validate_name(name: str, field_label: str = "Name") -> ValidationResult:
    """Validates a human name or username field."""
    errors = []
    if not name or not name.strip():
        errors.append(f"{field_label} cannot be empty.")
        return ValidationResult(False, errors)
    name = name.strip()
    if len(name) < 2:
        errors.append(f"{field_label} must be at least 2 characters.")
    if len(name) > 100:
        errors.append(f"{field_label} cannot exceed 100 characters.")
    if re.search(r"[<>\"';\\]", name):
        errors.append(f"{field_label} contains invalid characters.")
    return ValidationResult(len(errors) == 0, errors)


# ─────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────
def validate_email(email: str) -> ValidationResult:
    """Validates email address format."""
    if not email or not email.strip():
        return ValidationResult(False, ["Email cannot be empty."])
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email.strip()):
        return ValidationResult(False, ["Invalid email address format."])
    if len(email) > 254:
        return ValidationResult(False, ["Email address is too long."])
    return ValidationResult(True)


# ─────────────────────────────────────────────
# Phone / Mobile
# ─────────────────────────────────────────────
def validate_phone(phone: str) -> ValidationResult:
    """Validates Indian mobile or international phone number."""
    if not phone or not phone.strip():
        return ValidationResult(False, ["Phone number cannot be empty."])
    digits_only = re.sub(r"[\s\-\+\(\)]", "", phone)
    if not digits_only.isdigit():
        return ValidationResult(False, ["Phone number must contain only digits (spaces/dashes allowed)."])
    if not (7 <= len(digits_only) <= 15):
        return ValidationResult(False, ["Phone number must be 7–15 digits long."])
    return ValidationResult(True)


# ─────────────────────────────────────────────
# Date
# ─────────────────────────────────────────────
def validate_date(date_str: str, field_label: str = "Date") -> ValidationResult:
    """Validates date string in YYYY-MM-DD format."""
    if not date_str or not date_str.strip():
        return ValidationResult(False, [f"{field_label} cannot be empty."])
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            datetime.strptime(date_str.strip(), fmt)
            return ValidationResult(True)
        except ValueError:
            continue
    return ValidationResult(False, [f"{field_label} must be in YYYY-MM-DD format."])


def validate_date_range(start_str: str, end_str: str) -> ValidationResult:
    """Ensures start date is before end date."""
    start_result = validate_date(start_str, "Start Date")
    end_result   = validate_date(end_str, "End Date")
    errors = start_result.errors + end_result.errors
    if errors:
        return ValidationResult(False, errors)
    try:
        start = datetime.strptime(start_str.strip(), "%Y-%m-%d")
        end   = datetime.strptime(end_str.strip(), "%Y-%m-%d")
        if end < start:
            return ValidationResult(False, ["End date must be after start date."])
    except Exception:
        pass
    return ValidationResult(True)


# ─────────────────────────────────────────────
# Project Fields
# ─────────────────────────────────────────────
def validate_project(name: str, start_date: str, end_date: str,
                     description: str = "") -> ValidationResult:
    """Full project form validation."""
    errors = []
    name_result = validate_name(name, "Project Name")
    if not name_result:
        errors.extend(name_result.errors)
    date_result = validate_date_range(start_date, end_date)
    if not date_result:
        errors.extend(date_result.errors)
    if description and len(description) > 2000:
        errors.append("Description cannot exceed 2000 characters.")
    return ValidationResult(len(errors) == 0, errors)


# ─────────────────────────────────────────────
# Task Fields
# ─────────────────────────────────────────────
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_STATUSES   = {"Pending", "In Progress", "Completed", "Delayed", "On Hold"}

def validate_task(title: str, due_date: str = None,
                  priority: str = "Medium", status: str = "Pending") -> ValidationResult:
    """Full task form validation."""
    errors = []
    if not title or not title.strip():
        errors.append("Task title cannot be empty.")
    elif len(title.strip()) < 3:
        errors.append("Task title must be at least 3 characters.")
    elif len(title.strip()) > 200:
        errors.append("Task title cannot exceed 200 characters.")

    if due_date:
        date_result = validate_date(due_date, "Due Date")
        if not date_result:
            errors.extend(date_result.errors)

    if priority not in VALID_PRIORITIES:
        errors.append(f"Priority must be one of: {', '.join(sorted(VALID_PRIORITIES))}.")

    if status not in VALID_STATUSES:
        errors.append(f"Status must be one of: {', '.join(sorted(VALID_STATUSES))}.")

    return ValidationResult(len(errors) == 0, errors)


# ─────────────────────────────────────────────
# SQL Injection Guard
# ─────────────────────────────────────────────
SQL_INJECTION_PATTERNS = re.compile(
    r"(--|;|/\*|\*/|xp_|union\s+select|drop\s+table|insert\s+into"
    r"|delete\s+from|update\s+\w+\s+set|exec\s*\(|execute\s*\()",
    re.IGNORECASE
)

def is_safe_input(value: str) -> bool:
    """Returns False if the input looks like an SQL injection attempt."""
    if not value:
        return True
    return not bool(SQL_INJECTION_PATTERNS.search(str(value)))


def sanitize_string(value: str, max_length: int = 255) -> str:
    """Strip dangerous characters and truncate to max_length."""
    if not value:
        return ""
    # Remove null bytes and control chars
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", str(value))
    return sanitized.strip()[:max_length]


# ─────────────────────────────────────────────
# API Request Validation
# ─────────────────────────────────────────────
def validate_api_key(key: str, expected: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    if not key or not expected:
        return False
    import hmac
    return hmac.compare_digest(key.encode(), expected.encode())
