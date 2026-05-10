"""
PMS 2.0 - Configuration Management
Centralizes all app settings. Sensitive values can be overridden via environment variables.
"""

import os

# ─────────────────────────────────────────────
# API Security
# ─────────────────────────────────────────────
# Override in production: set env var PMS_API_KEY=your_secret
API_KEY = os.environ.get("PMS_API_KEY", "pms_secret_key_2026")

# ─────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────
DB_NAME       = os.environ.get("PMS_DB_NAME", "employee.db")
DB_WAL_MODE   = True   # Write-Ahead Logging for performance

# ─────────────────────────────────────────────
# Session
# ─────────────────────────────────────────────
SESSION_FILE            = "session.json"
SESSION_TIMEOUT_HOURS   = 8
LOGIN_MAX_ATTEMPTS      = 5          # lockout threshold
LOGIN_LOCKOUT_MINUTES   = 15         # lockout duration

# ─────────────────────────────────────────────
# Password Policy
# ─────────────────────────────────────────────
PASSWORD_MIN_LENGTH     = 8
PASSWORD_REQUIRE_UPPER  = True
PASSWORD_REQUIRE_LOWER  = True
PASSWORD_REQUIRE_DIGIT  = True
PASSWORD_REQUIRE_SYMBOL = True

# ─────────────────────────────────────────────
# Flask API
# ─────────────────────────────────────────────
API_HOST    = os.environ.get("PMS_API_HOST", "127.0.0.1")
API_PORT    = int(os.environ.get("PMS_API_PORT", "5000"))
API_DEBUG   = os.environ.get("PMS_API_DEBUG", "false").lower() == "true"

# ─────────────────────────────────────────────
# App Metadata
# ─────────────────────────────────────────────
APP_NAME    = "Project Monitoring System"
APP_VERSION = "2.0.0"
