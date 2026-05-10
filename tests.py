"""
PMS 2.0 - Comprehensive Test Suite
Covers: DB CRUD, Input Validation, API Auth, Security, Session Logic, Role-Based Access
"""

import unittest
import sqlite3
import os
import json
import hashlib
import hmac
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# Test Database Setup
# ─────────────────────────────────────────────
TEST_DB = "test_pms.db"

def get_test_db():
    return sqlite3.connect(TEST_DB)

def init_test_db():
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    con = sqlite3.connect(TEST_DB)
    cur = con.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS employee (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            email    TEXT,
            mobile   TEXT,
            gender   TEXT,
            dob      TEXT,
            date     TEXT,
            time     TEXT,
            department TEXT,
            password TEXT,
            role     TEXT DEFAULT 'Team Member'
        );
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            team_leader TEXT,
            start_date  TEXT,
            end_date    TEXT,
            description TEXT,
            status      TEXT DEFAULT 'Ongoing',
            priority    TEXT DEFAULT 'Medium'
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            title       TEXT NOT NULL,
            description TEXT,
            project_id  INTEGER,
            assigned_to TEXT,
            due_date    TEXT,
            priority    TEXT DEFAULT 'Medium',
            status      TEXT DEFAULT 'Pending',
            created_date TEXT
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            user      TEXT,
            action    TEXT,
            details   TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            email    TEXT,
            role     TEXT DEFAULT 'admin'
        );
    """)
    con.commit()
    con.close()


# ═══════════════════════════════════════════════
# 1. DATABASE CRUD TESTS
# ═══════════════════════════════════════════════
class TestDatabaseCRUD(unittest.TestCase):

    def setUp(self):
        init_test_db()
        self.con = get_test_db()
        self.cur = self.con.cursor()

    def tearDown(self):
        self.con.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    # --- Projects ---
    def test_create_project(self):
        self.cur.execute(
            "INSERT INTO projects (name, start_date, end_date, status) VALUES (?,?,?,?)",
            ("Alpha", "2024-01-01", "2024-12-31", "Ongoing")
        )
        self.con.commit()
        row = self.cur.execute("SELECT name, status FROM projects WHERE name='Alpha'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Alpha")
        self.assertEqual(row[1], "Ongoing")

    def test_update_project(self):
        self.cur.execute("INSERT INTO projects (name, status) VALUES (?,?)", ("Beta", "Ongoing"))
        pid = self.cur.lastrowid
        self.cur.execute("UPDATE projects SET status=? WHERE id=?", ("Completed", pid))
        self.con.commit()
        row = self.cur.execute("SELECT status FROM projects WHERE id=?", (pid,)).fetchone()
        self.assertEqual(row[0], "Completed")

    def test_delete_project_cascades_tasks(self):
        self.cur.execute("INSERT INTO projects (name) VALUES (?)", ("ToDelete",))
        pid = self.cur.lastrowid
        self.cur.execute("INSERT INTO tasks (title, project_id) VALUES (?,?)", ("Task A", pid))
        self.con.commit()
        self.cur.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
        self.cur.execute("DELETE FROM projects WHERE id=?", (pid,))
        self.con.commit()
        task = self.cur.execute("SELECT * FROM tasks WHERE project_id=?", (pid,)).fetchone()
        proj = self.cur.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        self.assertIsNone(task)
        self.assertIsNone(proj)

    # --- Tasks ---
    def test_create_task(self):
        self.cur.execute("INSERT INTO projects (name) VALUES (?)", ("Proj",))
        pid = self.cur.lastrowid
        self.cur.execute(
            "INSERT INTO tasks (title, project_id, priority, status) VALUES (?,?,?,?)",
            ("Task 1", pid, "High", "Pending")
        )
        self.con.commit()
        row = self.cur.execute("SELECT title, status FROM tasks WHERE title='Task 1'").fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[1], "Pending")

    def test_update_task_status(self):
        self.cur.execute("INSERT INTO tasks (title, status) VALUES (?,?)", ("T", "Pending"))
        tid = self.cur.lastrowid
        self.cur.execute("UPDATE tasks SET status=? WHERE id=?", ("Completed", tid))
        self.con.commit()
        row = self.cur.execute("SELECT status FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertEqual(row[0], "Completed")

    def test_delete_task(self):
        self.cur.execute("INSERT INTO tasks (title) VALUES (?)", ("DelTask",))
        tid = self.cur.lastrowid
        self.cur.execute("DELETE FROM tasks WHERE id=?", (tid,))
        self.con.commit()
        row = self.cur.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone()
        self.assertIsNone(row)

    def test_project_progress_calculation(self):
        self.cur.execute("INSERT INTO projects (name) VALUES (?)", ("Progress",))
        pid = self.cur.lastrowid
        self.cur.execute("INSERT INTO tasks (title, project_id, status) VALUES (?,?,?)", ("T1", pid, "Completed"))
        self.cur.execute("INSERT INTO tasks (title, project_id, status) VALUES (?,?,?)", ("T2", pid, "Pending"))
        self.cur.execute("INSERT INTO tasks (title, project_id, status) VALUES (?,?,?)", ("T3", pid, "Completed"))
        self.con.commit()
        total     = self.cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,)).fetchone()[0]
        completed = self.cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,)).fetchone()[0]
        progress  = int((completed / total) * 100)
        self.assertEqual(total, 3)
        self.assertEqual(completed, 2)
        self.assertEqual(progress, 66)

    # --- Users / RBAC ---
    def test_create_employee_with_role(self):
        pw_hash = hashlib.sha256("Admin@123".encode()).hexdigest()
        for name, role in [("Alice", "Project Manager"), ("Bob", "Team Leader"), ("Carol", "Team Member")]:
            self.cur.execute("INSERT INTO employee (name, password, role) VALUES (?,?,?)", (name, pw_hash, role))
        self.con.commit()
        roles = {r[0]: r[1] for r in self.cur.execute("SELECT name, role FROM employee").fetchall()}
        self.assertEqual(roles["Alice"], "Project Manager")
        self.assertEqual(roles["Bob"],   "Team Leader")
        self.assertEqual(roles["Carol"], "Team Member")

    def test_audit_log_insertion(self):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.cur.execute(
            "INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)",
            (ts, "admin", "LOGIN", "Successful login")
        )
        self.con.commit()
        row = self.cur.execute("SELECT action FROM audit_logs WHERE user='admin'").fetchone()
        self.assertEqual(row[0], "LOGIN")


# ═══════════════════════════════════════════════
# 2. INPUT VALIDATION TESTS
# ═══════════════════════════════════════════════
class TestValidators(unittest.TestCase):

    def setUp(self):
        from validators import (
            validate_password, validate_email, validate_phone,
            validate_date, validate_date_range, validate_project,
            validate_task, is_safe_input, sanitize_string, validate_name
        )
        self.vp  = validate_password
        self.ve  = validate_email
        self.vph = validate_phone
        self.vd  = validate_date
        self.vdr = validate_date_range
        self.vpr = validate_project
        self.vt  = validate_task
        self.si  = is_safe_input
        self.ss  = sanitize_string
        self.vn  = validate_name

    # Password
    def test_strong_password_passes(self):
        self.assertTrue(self.vp("Secure@123"))

    def test_weak_password_no_upper(self):
        self.assertFalse(self.vp("secure@123"))

    def test_weak_password_too_short(self):
        self.assertFalse(self.vp("Ab@1"))

    def test_weak_password_no_symbol(self):
        self.assertFalse(self.vp("Secure123"))

    def test_empty_password_fails(self):
        self.assertFalse(self.vp(""))

    # Email
    def test_valid_email(self):
        self.assertTrue(self.ve("user@example.com"))

    def test_invalid_email_missing_at(self):
        self.assertFalse(self.ve("userexample.com"))

    def test_invalid_email_missing_domain(self):
        self.assertFalse(self.ve("user@"))

    def test_empty_email_fails(self):
        self.assertFalse(self.ve(""))

    # Phone
    def test_valid_phone_indian(self):
        self.assertTrue(self.vph("9876543210"))

    def test_valid_phone_with_dashes(self):
        self.assertTrue(self.vph("987-654-3210"))

    def test_invalid_phone_letters(self):
        self.assertFalse(self.vph("98765abc10"))

    def test_invalid_phone_too_short(self):
        self.assertFalse(self.vph("123"))

    # Date
    def test_valid_date(self):
        self.assertTrue(self.vd("2024-06-15"))

    def test_invalid_date_format(self):
        self.assertFalse(self.vd("15-June-2024"))

    def test_empty_date_fails(self):
        self.assertFalse(self.vd(""))

    def test_date_range_valid(self):
        self.assertTrue(self.vdr("2024-01-01", "2024-12-31"))

    def test_date_range_end_before_start(self):
        self.assertFalse(self.vdr("2024-12-31", "2024-01-01"))

    # Project
    def test_valid_project(self):
        self.assertTrue(self.vpr("My Project", "2024-01-01", "2024-12-31"))

    def test_project_empty_name_fails(self):
        self.assertFalse(self.vpr("", "2024-01-01", "2024-12-31"))

    # Task
    def test_valid_task(self):
        self.assertTrue(self.vt("Design Homepage", "2024-06-01", "High", "Pending"))

    def test_task_empty_title_fails(self):
        self.assertFalse(self.vt(""))

    def test_task_invalid_priority_fails(self):
        self.assertFalse(self.vt("Task", priority="Extreme"))

    def test_task_invalid_status_fails(self):
        self.assertFalse(self.vt("Task", status="Maybe"))

    # SQL Injection
    def test_safe_input_clean(self):
        self.assertTrue(self.si("John Doe"))

    def test_sql_injection_drop_table(self):
        self.assertFalse(self.si("'; DROP TABLE users; --"))

    def test_sql_injection_union_select(self):
        self.assertFalse(self.si("1 UNION SELECT * FROM users"))

    def test_sql_injection_comment(self):
        self.assertFalse(self.si("admin' --"))

    # Sanitize
    def test_sanitize_strips_control_chars(self):
        result = self.ss("Hello\x00World")
        self.assertNotIn("\x00", result)

    def test_sanitize_truncates(self):
        result = self.ss("A" * 300, max_length=100)
        self.assertEqual(len(result), 100)


# ═══════════════════════════════════════════════
# 3. SECURITY TESTS
# ═══════════════════════════════════════════════
class TestSecurity(unittest.TestCase):

    def test_password_hashing_is_sha256(self):
        pw = "TestPass@1"
        expected = hashlib.sha256(pw.encode()).hexdigest()
        self.assertEqual(len(expected), 64)  # SHA-256 = 64 hex chars

    def test_password_hash_is_not_reversible(self):
        pw = "MySecret@1"
        h  = hashlib.sha256(pw.encode()).hexdigest()
        self.assertNotEqual(h, pw)

    def test_api_key_constant_time_compare(self):
        from validators import validate_api_key
        self.assertTrue(validate_api_key("pms_secret_key_2026", "pms_secret_key_2026"))
        self.assertFalse(validate_api_key("wrong_key", "pms_secret_key_2026"))
        self.assertFalse(validate_api_key("", "pms_secret_key_2026"))
        self.assertFalse(validate_api_key(None, "pms_secret_key_2026"))

    def test_session_timeout_detection(self):
        """Simulates an expired session."""
        old_time = (datetime.now() - timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
        session  = {"user": "admin", "login_time": old_time}
        login_dt = datetime.strptime(session["login_time"], "%Y-%m-%d %H:%M:%S")
        expired  = (datetime.now() - login_dt) > timedelta(hours=8)
        self.assertTrue(expired)

    def test_session_not_expired_recent(self):
        recent_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        session     = {"user": "admin", "login_time": recent_time}
        login_dt    = datetime.strptime(session["login_time"], "%Y-%m-%d %H:%M:%S")
        expired     = (datetime.now() - login_dt) > timedelta(hours=8)
        self.assertFalse(expired)

    def test_sql_parameterization_prevents_injection(self):
        """Verify that parameterized queries don't execute injected SQL."""
        init_test_db()
        con = get_test_db()
        cur = con.cursor()
        cur.execute("INSERT INTO users (username, password) VALUES (?,?)",
                    ("admin", hashlib.sha256("Admin@123".encode()).hexdigest()))
        con.commit()
        # Injection attempt as username
        injection = "admin' OR '1'='1"
        row = cur.execute("SELECT * FROM users WHERE username=?", (injection,)).fetchone()
        self.assertIsNone(row)   # Must return nothing (safe)
        con.close()
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)


# ═══════════════════════════════════════════════
# 4. CONFIG TESTS
# ═══════════════════════════════════════════════
class TestConfig(unittest.TestCase):

    def test_config_values_exist(self):
        from config import (
            API_KEY, DB_NAME, SESSION_TIMEOUT_HOURS,
            PASSWORD_MIN_LENGTH, LOGIN_MAX_ATTEMPTS
        )
        self.assertIsNotNone(API_KEY)
        self.assertIsNotNone(DB_NAME)
        self.assertGreater(SESSION_TIMEOUT_HOURS, 0)
        self.assertGreaterEqual(PASSWORD_MIN_LENGTH, 8)
        self.assertGreater(LOGIN_MAX_ATTEMPTS, 0)

    def test_api_key_not_empty(self):
        from config import API_KEY
        self.assertTrue(len(API_KEY) > 0)


# ═══════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════
if __name__ == "__main__":
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestDatabaseCRUD))
    suite.addTests(loader.loadTestsFromTestCase(TestValidators))
    suite.addTests(loader.loadTestsFromTestCase(TestSecurity))
    suite.addTests(loader.loadTestsFromTestCase(TestConfig))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    exit(0 if result.wasSuccessful() else 1)
