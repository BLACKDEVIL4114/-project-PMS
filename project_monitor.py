from tkinter import *
from tkinter import ttk, messagebox, filedialog
import sqlite3
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta
import time
import csv
import random
import subprocess
import math
import threading
# Heavy AI engine is imported lazily to keep app startup fast.


# Global cache for the ML model to avoid reloading it multiple times
ML_MODEL_CACHE = None

def get_ml_model():
    global ML_MODEL_CACHE
    # If it failed before or is first time, try to load it
    if ML_MODEL_CACHE is None or ML_MODEL_CACHE is False:
        try:
            import joblib
            model_path = 'pms_delay_model.joblib'
            if os.path.exists(model_path):
                ML_MODEL_CACHE = joblib.load(model_path)
            else:
                ML_MODEL_CACHE = False
        except Exception as e:
            debug_log(f"DEBUG: Failed to load ML model: {e}")
            ML_MODEL_CACHE = False
    return ML_MODEL_CACHE if ML_MODEL_CACHE is not False else None

# Lazy import for Performance AI
PERFORMANCE_AI_ENGINE = None
def get_performance_ai():
    global PERFORMANCE_AI_ENGINE
    if PERFORMANCE_AI_ENGINE is None:
        try:
            from ai_engine import PerformanceAI
            PERFORMANCE_AI_ENGINE = PerformanceAI()
        except Exception as e:
            debug_log(f"DEBUG: Error lazy loading PerformanceAI: {e}")
            PERFORMANCE_AI_ENGINE = False # Mark as failed
    return PERFORMANCE_AI_ENGINE if PERFORMANCE_AI_ENGINE is not False else None

# FIX 2: Removed local fallback constants — they caused a subtle conflict:
# Python would define them on lines 44-50, then the import below would OVERWRITE
# them with the theme.py values. Now theme.py is the single source of truth.
# BG_NAVY and BG_BLACK are now properly defined in theme.py.
from theme import (
    SIDEBAR_BG, SIDEBAR_TEXT, ACTIVE_TEXT,
    HEADER_BG, HEADER_TEXT, CONTENT_BG, CARD_BG,
    PRIMARY_BG, PRIMARY_TEXT, MUTED_TEXT, INPUT_BG,
    ACCENT_GREEN, ACCENT_ORANGE, ACCENT_RED, ACCENT_BLUE, ACCENT_PURPLE,
    ACCENT_HOVER, BORDER_COLOR, WHITE, TEXT_WHITE, apply_theme,
    CARD_LIGHT, CARD_DARK, CARD_HOVER, PRIMARY_RED, PRIMARY_RED_DARK, FOCUS_COLOR,
    BG_DARK, BG_NAVY, BG_BLACK, SIDEBAR_ACTIVE_BG, BORDER_NAVY, TEXT_MUTED, TEXT_SECONDARY,
    BG_CARD, ACCENT_COLOR, TEXT_MAIN, HOVER_BG   # Added HOVER_BG
)
from api_service import api
DEBUG_LOGS = True

SIDEBAR_ICONS = {
    'dashboard': '🏠',
    'projects': '📁',
    'members': '👥',
    'tasks': '📝',
    'productivity': '📈',
    'reports': '📊',
    'employee_panel': '🧑‍💻',
    'analytics': '🔬'
}

EMPLOYEE_PANEL_SUB_PAGES = {
    'emp_dashboard': {'label': 'Dashboard', 'icon': '🏠'},
    'emp_my_tasks': {'label': 'My Tasks', 'icon': '📝'},
    'emp_team': {'label': 'Team', 'icon': '👥'},
    'emp_analysis': {'label': 'Analysis', 'icon': '🔬'},
    'emp_queries': {'label': 'Queries', 'icon': '❓'},
    'emp_attendance': {'label': 'Time & Attendance', 'icon': '⏰'},
    'emp_leave_requests': {'label': 'Leave Requests', 'icon': '🏖️'},
    'emp_timesheets': {'label': 'Timesheets', 'icon': '📅'},
}

# Global State
CURRENT_USER_ROLE = "Guest"
CURRENT_USER_NAME = "Guest"
CURRENT_USER_EMAIL = ""
CURRENT_TOKEN = ""

def debug_log(message):
    if DEBUG_LOGS:
        print(message)

def load_session():
    global CURRENT_USER_ROLE, CURRENT_USER_NAME, CURRENT_USER_EMAIL, CURRENT_TOKEN
    debug_log("DEBUG: Loading session...")
    try:
        if os.path.exists('session.json'):
            with open('session.json', 'r') as f:
                data = json.load(f)
                CURRENT_USER_NAME = data.get('user', 'Guest')
                CURRENT_USER_ROLE = data.get('role', 'Guest')
                CURRENT_USER_EMAIL = data.get('email', '')
                CURRENT_TOKEN = data.get('token', '')
                if CURRENT_TOKEN:
                    api.token = CURRENT_TOKEN
                debug_log(f"DEBUG: Session loaded - User: {CURRENT_USER_NAME}, Role: {CURRENT_USER_ROLE}, Email: {CURRENT_USER_EMAIL}")
        else:
            debug_log("DEBUG: session.json not found")
    except Exception as e:
        debug_log(f"DEBUG: Error loading session: {e}")

def get_db_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'employee.db')

def init_database():
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        
        # Optimize performance
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        
        # 1. Projects Table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                description TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT, -- Not Started, Ongoing, Completed
                manager TEXT
            )
        """)

        # Check for manager/team_leader column in projects
        cursor.execute('PRAGMA table_info(projects)')
        p_cols = [info[1] for info in cursor.fetchall()]
        if 'team_leader' not in p_cols:
            cursor.execute('ALTER TABLE projects ADD COLUMN team_leader TEXT')
        if 'default_assignee' not in p_cols:
            try:
                cursor.execute('ALTER TABLE projects ADD COLUMN default_assignee TEXT')
            except:
                pass
        if 'priority' not in p_cols:
            try:
                cursor.execute('ALTER TABLE projects ADD COLUMN priority TEXT DEFAULT "Medium"')
            except:
                pass

        # 2. Members Table (Reusing employee table)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee (
                id INTEGER PRIMARY KEY AUTOINCREMENT, 
                name TEXT, 
                mobile TEXT, 
                email TEXT, 
                address TEXT, 
                gender TEXT, 
                dob TEXT, 
                date TEXT, 
                time TEXT, 
                department TEXT,
                password TEXT
            )
        """)
        
        # Check for password column in employee (Migration)
        cursor.execute('PRAGMA table_info(employee)')
        cols = [info[1] for info in cursor.fetchall()]
        if 'password' not in cols:
            cursor.execute('ALTER TABLE employee ADD COLUMN password TEXT')
        if 'department' not in cols:
            cursor.execute('ALTER TABLE employee ADD COLUMN department TEXT')
        if 'role' not in cols:
            cursor.execute('ALTER TABLE employee ADD COLUMN role TEXT')
        if 'reporting_manager' not in cols:
            cursor.execute('ALTER TABLE employee ADD COLUMN reporting_manager TEXT')

        # 3. Tasks Table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                description TEXT,
                project_id INTEGER,
                assigned_to TEXT,
                status TEXT, -- Pending, In Progress, Completed, Delayed
                priority TEXT,
                due_date TEXT,
                completed_date TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)
        
        # Migration for tasks table
        cursor.execute('PRAGMA table_info(tasks)')
        t_cols = [info[1] for info in cursor.fetchall()]
        if 'project_id' not in t_cols:
            # If old table exists, we might need to recreate or add column
            try:
                cursor.execute('ALTER TABLE tasks ADD COLUMN project_id INTEGER')
            except:
                pass # Already exists or error
        if 'description' not in t_cols:
             try: cursor.execute('ALTER TABLE tasks ADD COLUMN description TEXT')
             except: pass
        if 'created_date' not in t_cols:
             try: cursor.execute('ALTER TABLE tasks ADD COLUMN created_date TEXT')
             except: pass

        # 4. Users Table (Admin)
        cursor.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, email TEXT)")
        
        # Migration: ensure reset_requested column exists (used by admin panel)
        cursor.execute("PRAGMA table_info(users)")
        u_cols = [info[1] for info in cursor.fetchall()]
        if 'reset_requested' not in u_cols:
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN reset_requested INTEGER DEFAULT 0")
            except: pass
        
        # Seed Admin if not exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users VALUES (?,?,?,?)", ('admin', hashlib.sha256('1234'.encode()).hexdigest(), 'admin@company.com', 0))

        # 5. Audit Logs
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT,
                        user TEXT,
                        action TEXT,
                        details TEXT
                    )
                """)
                
        # 5. Notifications
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user TEXT,
                message TEXT,
                timestamp TEXT,
                is_read INTEGER DEFAULT 0
            )
        """)
        
        # 6. Queries (Unified Schema)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS queries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT,
                tl_name TEXT,
                project_id INTEGER,
                subject TEXT,
                message TEXT,
                response TEXT,
                status TEXT DEFAULT 'Open',
                history TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)
        
        # Migration for old queries schema
        cursor.execute("PRAGMA table_info(queries)")
        q_cols = [info[1] for info in cursor.fetchall()]
        if 'employee_name' in q_cols:
            # Rename column or handle migration if needed
            # For simplicity, we can just ensure the new columns exist
            pass
        if 'user_name' not in q_cols and 'employee_name' in q_cols:
            cursor.execute("ALTER TABLE queries RENAME COLUMN employee_name TO user_name")
        if 'response' not in q_cols and 'answer' in q_cols:
            cursor.execute("ALTER TABLE queries RENAME COLUMN answer TO response")
        if 'created_at' not in q_cols and 'timestamp' in q_cols:
            cursor.execute("ALTER TABLE queries RENAME COLUMN timestamp TO created_at")
        if 'history' not in q_cols:
            cursor.execute("ALTER TABLE queries ADD COLUMN history TEXT")
        
        # 7. Reset Requests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reset_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT,
                mobile TEXT,
                role TEXT,
                status TEXT,
                timestamp TEXT
            )
        """)

        # 8. Leave Requests
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leave_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_name TEXT,
                reason TEXT,
                leave_type TEXT,
                start_date TEXT,
                end_date TEXT,
                status TEXT DEFAULT 'Pending', -- Pending, Approved, Rejected
                timestamp TEXT
            )
        """)
        # Project milestones
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS project_milestones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                name TEXT,
                due_date TEXT,
                status TEXT DEFAULT 'Planned',
                created_at TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)
        # Task attachments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                file_path TEXT,
                uploaded_by TEXT,
                timestamp TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_approvals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                approver_name TEXT,
                status TEXT,
                feedback TEXT,
                timestamp TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        
        # 9. Task Comments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                user_name TEXT,
                comment TEXT,
                timestamp TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        
        # 10. Activity Timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_timeline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                user_name TEXT,
                action TEXT,
                timestamp TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        """)

        # 11. Attendance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                date TEXT,
                status TEXT, -- Present, Absent, Half Day
                clock_in TEXT,
                clock_out TEXT,
                UNIQUE(employee_name, date)
            )
        """)

        # Migration for attendance
        cursor.execute("PRAGMA table_info(attendance)")
        att_cols = [info[1] for info in cursor.fetchall()]
        if 'clock_in' not in att_cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN clock_in TEXT")
        if 'clock_out' not in att_cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN clock_out TEXT")

        # 12. Timesheets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS timesheets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                date TEXT,
                task_id INTEGER,
                hours REAL,
                description TEXT,
                timestamp TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
        """)
        
        # Migration for timesheets: ensure employee_name column exists
        cursor.execute("PRAGMA table_info(timesheets)")
        ts_cols = [info[1] for info in cursor.fetchall()]
        if 'employee_name' not in ts_cols:
            try:
                cursor.execute("ALTER TABLE timesheets ADD COLUMN employee_name TEXT")
            except:
                pass

        # 13. Performance History (For Analytics)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                month TEXT,
                tasks_assigned INTEGER,
                tasks_completed INTEGER,
                on_time_rate REAL,
                avg_task_priority REAL,
                attendance_rate REAL,
                quality_rating REAL,
                productivity_score REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 14. Employee Analysis Reports
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_analysis_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                team_leader_name TEXT,
                project_manager_name TEXT,
                report_title TEXT,
                performance_score REAL,
                risk_level TEXT,
                trend_text TEXT,
                strengths TEXT,
                improvement_areas TEXT,
                manager_summary TEXT,
                leader_summary TEXT,
                action_plan TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0
            )
        """)
        
        con.commit()
        con.close()
        return True
    except Exception as e:
        print(f"DB Init Error: {e}")
        return False

def log_audit(user, action, details):
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)", 
                       (ts, user, action, details))
        con.commit()
        con.close()
    except: pass

def log_activity(project_id, user, action):
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO activity_timeline (project_id, user_name, action, timestamp) VALUES (?,?,?,?)", 
                       (project_id, user, action, ts))
        con.commit()
        con.close()
    except: pass

def notify_user(user, message):
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO notifications (user, message, timestamp) VALUES (?,?,?)", 
                       (user, message, ts))
        con.commit()
        con.close()
    except: pass

def ensure_employee_analysis_report_table():
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS employee_analysis_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_name TEXT,
                team_leader_name TEXT,
                project_manager_name TEXT,
                report_title TEXT,
                performance_score REAL,
                risk_level TEXT,
                trend_text TEXT,
                strengths TEXT,
                improvement_areas TEXT,
                manager_summary TEXT,
                leader_summary TEXT,
                action_plan TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read INTEGER DEFAULT 0
            )
        """)
        con.commit()
        con.close()
    except Exception:
        pass

def cleanup_orphan_assignments():
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("UPDATE tasks SET assigned_to='' WHERE assigned_to IS NOT NULL AND TRIM(assigned_to)!='' AND lower(assigned_to) NOT IN (SELECT lower(name) FROM employee)")
        cur.execute("""UPDATE tasks 
                       SET assigned_to='' 
                       WHERE title IN ('Requirements & Scope','Design & Planning','Implementation','Testing & QA','Deployment','Handover & Documentation') 
                             AND TRIM(IFNULL(assigned_to,''))!=''""")
        con.commit()
        con.close()
    except:
        pass

def get_project_default_assignee(pid):
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT default_assignee FROM projects WHERE id=?", (pid,))
        row = cur.fetchone()
        con.close()
        return row[0] if row and row[0] else ""
    except:
        return ""

def set_project_default_assignee(pid, name):
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("UPDATE projects SET default_assignee=? WHERE id=?", (name, pid))
        con.commit(); con.close()
        return True
    except:
        return False

def suggest_tasks_for_project(project_name):
    name = (project_name or "").lower()
    base = [
        ("Requirements & Scope", "High", 3),
        ("Design & Planning", "Medium", 7),
        ("Implementation", "High", 21),
        ("Testing & QA", "High", 7),
        ("Deployment", "Medium", 2),
        ("Handover & Documentation", "Low", 3),
    ]
    if "web" in name or "site" in name or "website" in name:
        return [
            ("Gather Requirements", "High", 2),
            ("Wireframes & UI Mockups", "Medium", 4),
            ("Frontend Development", "High", 14),
            ("Backend/API Development", "High", 14),
            ("Content Integration", "Medium", 5),
            ("Cross-browser Testing", "High", 5),
            ("SEO & Performance Tuning", "Medium", 3),
            ("UAT & Final Fixes", "High", 4),
            ("Deployment", "Medium", 2),
            ("Documentation & Handover", "Low", 2),
        ]
    if "mobile" in name or "app" in name:
        return [
            ("Requirements & Flows", "High", 3),
            ("UI/UX Design", "Medium", 5),
            ("Frontend Screens", "High", 14),
            ("API Integration", "High", 10),
            ("Device Testing", "High", 7),
            ("Store Assets & Signing", "Medium", 3),
            ("Release & Rollout", "Medium", 2),
            ("Docs & Handover", "Low", 2),
        ]
    if "api" in name or "backend" in name:
        return [
            ("API Spec & Contracts", "High", 3),
            ("DB Schema & Migrations", "High", 5),
            ("Core Endpoints", "High", 10),
            ("Auth & Security", "High", 5),
            ("Load/Unit Tests", "High", 5),
            ("Monitoring & Logging", "Medium", 3),
            ("Deploy", "Medium", 2),
            ("Docs & Handover", "Low", 2),
        ]
    return base

def pick_department_for_title(title):
    t = (title or "").lower()
    if any(k in t for k in ["design", "ui", "ux", "wireframe", "mockup", "content"]):
        return "Design"
    if any(k in t for k in ["test", "qa", "quality"]):
        return "QA"
    if any(k in t for k in ["seo", "marketing"]):
        return "Marketing"
    if any(k in t for k in ["db", "database", "schema"]):
        return "IT"
    if any(k in t for k in ["api", "backend", "auth", "endpoint"]):
        return "IT"
    if any(k in t for k in ["frontend", "html", "css", "react", "angular", "view", "screen"]):
        return "IT"
    return "IT"

def find_employee_by_department(dept):
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name FROM employee WHERE LOWER(department)=LOWER(?) ORDER BY id ASC", (dept,))
        row = cur.fetchone()
        con.close()
        return row[0] if row else ""
    except:
        return ""

def auto_split_and_assign(pid, pname, tl_name):
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        # Skip if project already has non-helper tasks
        cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND (title IS NULL OR title NOT LIKE '%TL Assignment%')", (pid,))
        existing = cur.fetchone()[0]
        if existing and existing > 0:
            con.close()
            return 0
        suggestions = suggest_tasks_for_project(pname)
        start_date = datetime.now()
        payload = []
        for title, prio, days in suggestions:
            due = (start_date + timedelta(days=days)).strftime("%Y-%m-%d")
            # Do not auto-assign to any user; TL will assign explicitly
            payload.append((title, pid, "", "Pending", due, prio, datetime.now().strftime("%Y-%m-%d")))
        cur.executemany("INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)", payload)
        con.commit(); con.close()
        return len(payload)
    except:
        return 0

def seed_data():
    try:
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        
        # Check if we need to seed projects
        cursor.execute("SELECT COUNT(*) FROM projects")
        if cursor.fetchone()[0] == 0:
            print("Seeding Projects...")
            projects = [
                ("Website Redesign", "Overhaul of corporate website", "2023-10-01", "2023-12-31", "Ongoing", "Alice Manager"),
                ("Mobile App V2", "Flutter based mobile app", "2023-11-15", "2024-02-28", "Ongoing", "Bob Lead"),
                ("AI Integration", "Chatbot for customer support", "2023-09-01", "2023-11-30", "Completed", "Alice Manager"),
                ("Internal Audit", "Yearly financial audit", "2024-01-01", "2024-01-31", "Not Started", "Charlie Fin")
            ]
            cursor.executemany("INSERT INTO projects (name, description, start_date, end_date, status, manager) VALUES (?,?,?,?,?,?)", projects)
            
            # Get Project IDs
            cursor.execute("SELECT id, name FROM projects")
            p_map = {name: pid for pid, name in cursor.fetchall()}
            
            # Check/Seed Members with Roles
            cursor.execute("SELECT COUNT(*) FROM employee")
            if cursor.fetchone()[0] == 0:
                print("Seeding Members...")
                # name, mobile, email, department, password_raw, role
                members = [
                    ("John Developer", "9876543210", "john@dev.com", "IT", "1234", "Team Member"),
                    ("Sarah Designer", "9876543211", "sarah@design.com", "Design", "1234", "Team Member"),
                    ("Mike Tester", "9876543212", "mike@qa.com", "QA", "1234", "Team Member"),
                    ("Bob Lead", "9876543213", "bob@lead.com", "IT", "1234", "Team Leader"),
                    ("Alice Manager", "9876543214", "alice@pm.com", "Management", "1234", "Project Manager"),
                    ("Charlie Fin", "9876543215", "charlie@senior.com", "Finance", "1234", "Senior Employee")
                ]
                for m in members:
                    # Password hash for '1234'
                    pw = hashlib.sha256(m[4].encode()).hexdigest()
                    cursor.execute("INSERT INTO employee (name, mobile, email, department, password, role) VALUES (?,?,?,?,?,?)", 
                                   (m[0], m[1], m[2], m[3], pw, m[5]))
            
            # Get Members
            cursor.execute("SELECT name FROM employee")
            member_names = [r[0] for r in cursor.fetchall()]
            if not member_names: member_names = ["Unassigned"]
            
            # Seed Tasks
            print("Seeding Tasks...")
            tasks = [
                ("Design Home Page", "Create figma mockups", p_map["Website Redesign"], "Sarah Designer", "Completed", "High", "2023-10-15"),
                ("Develop API", "Setup Node.js server", p_map["Website Redesign"], "John Developer", "In Progress", "High", "2023-11-01"),
                ("Unit Testing", "Write Jest tests", p_map["Website Redesign"], "John Developer", "Pending", "Medium", "2023-11-10"),
                
                ("App UI Flow", "Screens for login", p_map["Mobile App V2"], "Sarah Designer", "Delayed", "High", "2023-11-20"),
                ("Firebase Setup", "Push notifications", p_map["Mobile App V2"], "John Developer", "In Progress", "Medium", "2023-12-01"),
                
                ("Train Model", "Fine tune LLM", p_map["AI Integration"], "John Developer", "Completed", "High", "2023-10-01"),
                ("Deploy Bot", "AWS Lambda deployment", p_map["AI Integration"], "Bob Lead", "Completed", "High", "2023-10-20")
            ]
            cursor.executemany("INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date) VALUES (?,?,?,?,?,?,?)", tasks)
            
            log_audit("System", "Seed Data", "Initial data seeded successfully")
            con.commit()
            print("Seeding Complete.")
        
        con.close()
        try:
            # If called as instance method, this is fine. If called as static, we need to pass instance.
            if hasattr(self, 'schedule_pm_dashboard_auto_refresh'):
                self.schedule_pm_dashboard_auto_refresh()
        except:
            pass
    except Exception as e:
        print(f"Seeding Error: {e}")

# ==================== TOOLTIP CLASS ====================
class CreateToolTip(object):
    def __init__(self, widget, text='widget info'):
        self.waittime = 500     #miliseconds
        self.wraplength = 180   #pixels
        self.widget = widget
        self.text = text
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)
        self.id = None
        self.tw = None

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.waittime, self.showtip)

    def unschedule(self):
        id = self.id
        self.id = None
        if id:
            self.widget.after_cancel(id)

    def showtip(self, event=None):
        if not self.widget or not self.widget.winfo_exists():
            return
        x = y = 0
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except:
            # Fallback if bbox fails
            x = y = 0
        
        try:
            x += self.widget.winfo_rootx() + 25
            y += self.widget.winfo_rooty() + 20
        except:
            return
        self.tw = Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.wm_geometry("+%d+%d" % (x, y))
        label = Label(self.tw, text=self.text, justify='left',
                       background="#1f2937", foreground="#ffffff",
                       relief='solid', borderwidth=1,
                       font=("Segoe UI", 9))
        label.pack(ipadx=5, ipady=2)

    def hidetip(self):
        tw = self.tw
        self.tw = None
        if tw:
            tw.destroy()

# ==================== MAIN APPLICATION ====================
class ProjectMonitorApp:
    def __init__(self, root, standalone=False):
        self.root = root
        self.standalone = standalone
        self.root.title("Project Monitoring System")
        self.root.geometry("1320x820")
        self.root.minsize(1100, 700)
        self.root.config(bg=CONTENT_BG)
        apply_theme(self.root)
        
        self.current_page = None
        self.content_frame = None
        self._ai_engine = None
        self.pm_refresh_job = None
        self.pm_refresh_interval_ms = 15000 # Increased to 15 seconds to fix performance issues
        self._last_db_signature = None
        self._last_ui_interaction_ts = time.monotonic()
        self._resize_job = None
        
        self.setup_styles()
        self.employee_submenu_visible = False
        self.init_ui()
        
        self.root.bind("<Configure>", self._on_root_configure)

    def stop_pm_dashboard_auto_refresh(self):
        if hasattr(self, 'pm_refresh_job') and self.pm_refresh_job:
            try:
                self.root.after_cancel(self.pm_refresh_job)
            except:
                pass
            self.pm_refresh_job = None
            
        if hasattr(self, '_auto_refresh_timer') and self._auto_refresh_timer:
            try:
                self.root.after_cancel(self._auto_refresh_timer)
            except:
                pass
            self._auto_refresh_timer = None

    def _mark_ui_interaction(self, *_args):
        self._last_ui_interaction_ts = time.monotonic()

    def _on_root_configure(self, _event=None):
        self._mark_ui_interaction()
        if self._resize_job:
            try:
                self.root.after_cancel(self._resize_job)
            except:
                pass
        self._resize_job = self.root.after(250, self._clear_resize_job)

    def _clear_resize_job(self):
        self._resize_job = None

    def _get_db_change_signature(self):
        # Watch DB + WAL/SHM for near-immediate UI updates after any commit.
        sig = []
        db_path = get_db_path()
        for p in (db_path, db_path + "-wal", db_path + "-shm"):
            if os.path.exists(p):
                try:
                    st = os.stat(p)
                    sig.append((p, st.st_mtime_ns, st.st_size))
                except:
                    sig.append((p, None, None))
            else:
                sig.append((p, None, None))
        return tuple(sig)

    def schedule_pm_dashboard_auto_refresh(self):
        self.stop_pm_dashboard_auto_refresh()
        if self._last_db_signature is None:
            self._last_db_signature = self._get_db_change_signature()
        self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)

    def refresh_pm_dashboard_if_active(self):
        self.pm_refresh_job = None
        # ── CRASH FIX: 'invalid command name' guard ─────────────────────────
        # This callback is scheduled with after(). If the user logs out and the
        # Tk root is destroyed, a pending after() fires and throws:
        #   TclError: invalid command name "XXXX<lambda>"
        # We must exit immediately if our root window no longer exists.
        try:
            if not hasattr(self, 'root') or not self.root.winfo_exists():
                return  # Window gone — stop the loop entirely
        except Exception:
            return  # root itself is invalid — stop silently
        # ────────────────────────────────────────────────────────────────────

        try:
            if getattr(self, '_resize_job', None) is not None:
                self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
                return
            if time.monotonic() - getattr(self, '_last_ui_interaction_ts', 0) < 1.0:
                self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
                return
            current_sig = self._get_db_change_signature()
            db_changed = current_sig != self._last_db_signature
            self._last_db_signature = current_sig
            
            if db_changed:
                role = CURRENT_USER_ROLE.lower()
                # 1. Project Manager / Team Leader Dashboard
                if role in ('project manager', 'team leader') and self.current_page == 'dashboard':
                    self.switch_page('dashboard', force=True)
                    return
                # 2. Employee Panels (Connected in Real-Time)
                if self.current_page == 'emp_dashboard':
                    self.refresh_emp_dashboard()
                elif self.current_page == 'emp_my_tasks':
                    if hasattr(self, 'refresh_emp_tasks_tab'): self.refresh_emp_tasks_tab()
                elif self.current_page == 'emp_team':
                    if hasattr(self, '_refresh_emp_team_data'): self._refresh_emp_team_data()
                elif self.current_page == 'emp_analysis':
                    if hasattr(self, 'refresh_emp_analysis'): self.refresh_emp_analysis()

            # Continue polling — but only if root is still alive
            try:
                self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
            except Exception:
                pass  # root was destroyed between the check and here — safe to stop
        except Exception as e:
            debug_log(f"DEBUG: Real-time refresh error: {e}")
            try:
                if hasattr(self, 'root') and self.root.winfo_exists():
                    self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
            except Exception:
                pass  # Window gone — stop the loop

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure("Sidebar.TFrame", background=SIDEBAR_BG)
        style.configure("Content.TFrame", background=CONTENT_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        
        # Treeview
        style.configure("Treeview", 
                        background=CARD_BG,
                        foreground=TEXT_WHITE,
                        fieldbackground=CARD_BG,
                        borderwidth=0,
                        relief="flat",
                        font=('Segoe UI', 10),
                        rowheight=40) # Increased for cleanliness
        style.configure("Treeview.Heading", 
                        background=SIDEBAR_BG,
                        foreground=TEXT_WHITE, 
                        borderwidth=1,
                        relief="flat",
                        padding=(12, 12),
                        font=('Segoe UI', 11, 'bold'))
        style.map(
            "Treeview",
            background=[('selected', ACCENT_HOVER)],
            foreground=[('selected', TEXT_WHITE)]
        )
        style.map(
            "Treeview.Heading",
            background=[('active', HEADER_BG), ('pressed', ACCENT_HOVER)],
            foreground=[('active', TEXT_WHITE), ('pressed', TEXT_WHITE)]
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#3f3f45",
            troughcolor="#1e1e22",
            bordercolor="#1e1e22",
            arrowcolor=WHITE,
            darkcolor="#3f3f45",
            lightcolor="#3f3f45",
            gripcount=0,
            width=10
        )
        style.map(
            "Vertical.TScrollbar",
            background=[('active', ACCENT_BLUE), ('pressed', ACCENT_BLUE)]
        )
        style.configure(
            "Horizontal.TScrollbar",
            background="#3f3f45",
            troughcolor="#1e1e22",
            bordercolor="#1e1e22",
            arrowcolor=WHITE,
            darkcolor="#3f3f45",
            lightcolor="#3f3f45",
            gripcount=0,
            width=10
        )
        style.map(
            "Horizontal.TScrollbar",
            background=[('active', ACCENT_BLUE), ('pressed', ACCENT_BLUE)]
        )
        
        # Custom styles for modern components
        style.configure("Custom.Treeview", 
                        background=CARD_BG,
                        foreground=TEXT_WHITE,
                        fieldbackground=CARD_BG,
                        font=('Segoe UI', 10),
                        rowheight=42,
                        borderwidth=0,
                        relief="flat")
        style.configure("Employee.TCombobox", 
                        fieldbackground=INPUT_BG,
                        background=SIDEBAR_BG,
                        foreground=WHITE,
                        arrowcolor=WHITE,
                        padding=8)
        style.configure("Team.Horizontal.TProgressbar",
                        troughcolor="#1e1e22",
                        background=ACCENT_GREEN,
                        thickness=12)
        # Fix white background for dropdown list
        style.map("Employee.TCombobox",
                  fieldbackground=[('readonly', INPUT_BG)],
                  foreground=[('readonly', WHITE)])
        
        # Ensure Treeview headings are dark
        style.configure("Custom.Treeview.Heading", 
                        background=SIDEBAR_BG,
                        foreground=WHITE,
                        font=('Segoe UI', 11, 'bold'),
                        padding=(12, 10))
        # Hover tag style applied via tag_configure on each Tree

    def _normalize_scroll_units(self, delta):
        if not delta:
            return 0
        if abs(delta) >= 120:
            return int(delta / 120)
        return 1 if delta > 0 else -1

    def _bind_canvas_scrolling(self, wrapper, canvas, allow_horizontal=False):
        # Using bind_all within Enter/Leave ensures that mouse wheel events 
        # are captured even when the mouse is over child widgets (Labels, etc.)
        # but only while the mouse is inside this specific panel area.

        def _on_mousewheel(event):
            self._mark_ui_interaction()
            try:
                if not canvas.winfo_exists():
                    return
                # Touchpads/Trackpads generate high-frequency events with small deltas (< 120).
                # Standard mouse wheels generate discrete events that are multiples of 120.
                if abs(event.delta) >= 120:
                    units = int(event.delta / 120)
                    canvas.yview_scroll(-units * 3, "units") # Snappy 3-unit scroll for physical wheel clicks
                else:
                    # Silky-smooth precise trackpad swipe scrolling scaled proportionally
                    step = int(event.delta / 10)
                    if step == 0:
                        step = 1 if event.delta > 0 else -1
                    canvas.yview_scroll(-step, "units")
            except Exception:
                pass

        def _on_shift_mousewheel(event):
            self._mark_ui_interaction()
            if not allow_horizontal:
                return
            try:
                if not canvas.winfo_exists():
                    return
                if abs(event.delta) >= 120:
                    units = int(event.delta / 120)
                    canvas.xview_scroll(-units * 3, "units")
                else:
                    step = int(event.delta / 10)
                    if step == 0:
                        step = 1 if event.delta > 0 else -1
                    canvas.xview_scroll(-step, "units")
            except Exception:
                pass

        def _on_button4(_event):
            self._mark_ui_interaction()
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(-3, "units")
            except Exception:
                pass

        def _on_button5(_event):
            self._mark_ui_interaction()
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(3, "units")
            except Exception:
                pass

        def _bind_mousewheel(_event):
            try:
                if not canvas.winfo_exists():
                    return
                # Use bind_all so it works everywhere within this panel
                canvas.bind_all("<MouseWheel>", _on_mousewheel)
                canvas.bind_all("<Button-4>", _on_button4)
                canvas.bind_all("<Button-5>", _on_button5)
                if allow_horizontal:
                    canvas.bind_all("<Shift-MouseWheel>", _on_shift_mousewheel)
            except Exception:
                pass

        def _unbind_mousewheel(_event):
            try:
                if not canvas.winfo_exists():
                    return
                # Robust pointer-based check to prevent unbinding when hovering over child elements
                x, y = self.root.winfo_pointerxy()
                target = self.root.winfo_containing(x, y)
                curr = target
                while curr:
                    if curr == canvas or curr == wrapper:
                        # Still inside the scrollable container hierarchy, do not unbind
                        return
                    curr = curr.master
                
                # Safely unbind from global scope only when cursor leaves the scrollable area
                canvas.unbind_all("<MouseWheel>")
                canvas.unbind_all("<Button-4>")
                canvas.unbind_all("<Button-5>")
                canvas.unbind_all("<Shift-MouseWheel>")
            except Exception:
                pass

        # Apply bindings to both wrapper and canvas to ensure full coverage
        for w in [wrapper, canvas]:
            if w and w.winfo_exists():
                w.bind("<Enter>", _bind_mousewheel)
                w.bind("<Leave>", _unbind_mousewheel)


    def init_ui(self):
        debug_log("DEBUG: Initializing UI [PMS_MODERN_V2_LOADED]")
        debug_log(f"DEBUG: Initializing UI for role: {CURRENT_USER_ROLE}")
        # Main Container
        self.main_container = Frame(self.root, bg=CONTENT_BG)
        self.main_container.pack(fill=BOTH, expand=True)
        
        # Sidebar
        self.sidebar = Frame(self.main_container, bg=SIDEBAR_BG, width=250)
        self.sidebar.pack(side=LEFT, fill=Y)
        self.sidebar.pack_propagate(False)
        
        # Header
        self.header = Frame(self.main_container, bg=HEADER_BG, height=60)
        self.header.pack(side=TOP, fill=X)
        self.header.pack_propagate(False)
        
        # Content Area
        self.content_area = Frame(self.main_container, bg=CONTENT_BG)
        self.content_area.pack(side=LEFT, fill=BOTH, expand=True)
        
        try:
            # Responsive configuration
            self.root.bind("<Configure>", self._on_app_resize)
            self._last_width = self.root.winfo_width()
            
            self.build_sidebar()
            self.build_header()
            
            # Load default page based on role
            # The user prefers the old dashboard (load_dashboard) which provides a high-level overview.
            # load_dashboard handles internal role-based logic automatically.
            self.switch_page('dashboard')
        except Exception as e:
            debug_log(f"DEBUG: Error in init_ui: {e}")
            messagebox.showerror("UI Error", f"Failed to initialize interface: {e}")

    def _on_app_resize(self, event):
        if event.widget == self.root:
            w = event.width
            if abs(w - self._last_width) > 80: # Filter small jitters
                self._last_width = w
                # If window becomes very small, we might want to refresh specific pages
                if w < 900 and self.current_page in ('projects', 'dashboard'):
                    # Debounced refresh would be better, but for now we refresh on broad changes
                    pass

    def get_responsive_padx(self):
        return 30 if self.root.winfo_width() > 1100 else 12

    def _apply_hover_effect(self, widget, accent_color, hover_bg=HOVER_BG):
        """Recursive hover effect engine for premium cards"""
        managed_backgrounds = {
            CARD_BG, HEADER_BG, CONTENT_BG, BG_DARK, HOVER_BG,
            "#1a2035", "#1c223d", "#252d4d"
        }

        def remember_bg(w):
            if not hasattr(w, "_default_bg"):
                try:
                    w._default_bg = w.cget('bg')
                except Exception:
                    w._default_bg = None

        def _on_enter(e):
            # Don't hover if already selected
            if widget.cget('bg') == "#1e2544": return
            
            widget.config(highlightbackground=accent_color, highlightthickness=2)
            def update_bg(w):
                remember_bg(w)
                if not hasattr(w, '_is_badge'):
                    try:
                        if w._default_bg in managed_backgrounds:
                            w.config(bg=hover_bg)
                    except Exception:
                        pass
                for child in w.winfo_children():
                    update_bg(child)
            update_bg(widget)

        def _on_leave(e):
            # Don't reset if selected
            if widget.cget('bg') == "#1e2544": return
            
            widget.config(highlightbackground=BORDER_COLOR, highlightthickness=1)
            def reset_bg(w):
                if not hasattr(w, '_is_badge'):
                    try:
                        original_bg = getattr(w, "_default_bg", None)
                        if original_bg:
                            w.config(bg=original_bg)
                    except Exception:
                        pass
                for child in w.winfo_children():
                    reset_bg(child)
            reset_bg(widget)

        widget.bind("<Enter>", _on_enter)
        
        def _on_click(e):
            if isinstance(widget, Frame):
                try:
                    parent = widget.master
                    if parent:
                        for sibling in parent.winfo_children():
                            if sibling != widget and isinstance(sibling, Frame):
                                try:
                                    if sibling.cget('bg') == "#1e2544":
                                        orig_bg = getattr(sibling, "_default_bg", CARD_BG)
                                        sibling.config(bg=orig_bg, highlightbackground=BORDER_COLOR, highlightthickness=1)
                                        def reset_children_bg(w):
                                            for c in w.winfo_children():
                                                try:
                                                    orig_c_bg = getattr(c, "_default_bg", None)
                                                    if orig_c_bg: c.config(bg=orig_c_bg)
                                                except: pass
                                                reset_children_bg(c)
                                        reset_children_bg(sibling)
                                except Exception: pass
                except Exception: pass
            
            widget.config(bg="#1e2544", highlightbackground=accent_color, highlightthickness=2)
            def set_selected_bg(w):
                remember_bg(w)
                if not hasattr(w, '_is_badge'):
                    try:
                        w.config(bg="#1e2544")
                    except Exception: pass
                for c in w.winfo_children():
                    set_selected_bg(c)
            set_selected_bg(widget)

        widget.bind("<Button-1>", _on_click, "+")
        widget.bind("<Leave>", _on_leave)
        # Bind children too
        def bind_recursive(w):
            remember_bg(w)
            w.bind("<Enter>", _on_enter)
            w.bind("<Leave>", _on_leave)
            w.bind("<Button-1>", _on_click, "+")
            for child in w.winfo_children():
                bind_recursive(child)
        remember_bg(widget)
        for child in widget.winfo_children():
            bind_recursive(child)
    
    def render_breadcrumb(self, page):
        names = {
            'dashboard': 'Dashboard',
            'members': 'My Team',
            'tasks': 'Tasks',
            'projects': 'Projects',
            'leave_requests': 'Leave Requests',
            'reports': 'Reports',
            'employee_panel': 'Employee Panel',
            'analytics': 'Analytics'
        }
        trail = "Dashboard" if page == 'dashboard' else f"Dashboard > {names.get(page, page.title())}"
        bc = Frame(self.content_area, bg=HEADER_BG)
        bc.pack(fill=X)
        Label(bc, text=trail, font=('Segoe UI', 9, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT, padx=20, pady=6).pack(anchor=W)
        sep = Frame(self.content_area, bg="#4a484d", height=1)
        sep.pack(fill=X)


    def _attach_tree_hover(self, tree):
        try:
            # Define hover tag if not defined
            tree.tag_configure('row_hover', background=ACCENT_HOVER)
            tree._last_hover = None
            def on_motion(event):
                row_id = tree.identify_row(event.y)
                if hasattr(tree, "_last_hover") and tree._last_hover and tree._last_hover != row_id:
                    try: tree.item(tree._last_hover, tags=tuple(t for t in tree.item(tree._last_hover, "tags") if t != 'row_hover'))
                    except: pass
                if row_id:
                    tags = list(tree.item(row_id, "tags"))
                    if 'row_hover' not in tags:
                        tags.append('row_hover')
                        tree.item(row_id, tags=tuple(tags))
                tree._last_hover = row_id
            def on_leave(event):
                if hasattr(tree, "_last_hover") and tree._last_hover:
                    try:
                        tree.item(tree._last_hover, tags=tuple(t for t in tree.item(tree._last_hover, "tags") if t != 'row_hover'))
                    except: pass
                    tree._last_hover = None
            tree.bind("<Motion>", on_motion)
            tree.bind("<Leave>", on_leave)
        except:
            pass

    def get_ai_engine(self):
        """Lazy-load and reuse AI engine so heavy ML imports happen only when needed."""
        if self._ai_engine is None:
            try:
                from ai_engine import PerformanceAI
                self._ai_engine = PerformanceAI()
            except Exception as e:
                debug_log(f"DEBUG: Failed to initialize AI engine: {e}")
                self._ai_engine = False
        return self._ai_engine if self._ai_engine is not False else None

    def build_sidebar(self):
        # Brand (Matching HTML preview)
        brand = Frame(self.sidebar, bg=BG_DARK, pady=25)
        brand.pack(fill=X)
        
        logo_frame = Frame(brand, bg=BG_DARK)
        logo_frame.pack(padx=25, anchor=W)
        
        # PMS logo box (Solid red square as in image)
        logo_box = Frame(logo_frame, bg=PRIMARY_RED, padx=12, pady=10)
        logo_box.pack(side=LEFT)
        Label(logo_box, text="PMS", font=('Rajdhani', 20, 'bold'), bg=PRIMARY_RED, fg=WHITE).pack()
        
        # Project Monitoring text
        text_frame = Frame(logo_frame, bg=BG_DARK, padx=16)
        text_frame.pack(side=LEFT)
        Label(text_frame, text="PROJECT", font=('Segoe UI', 10, 'bold'), bg=BG_DARK, fg=WHITE).pack(anchor=W)
        Label(text_frame, text="MONITORING 2.0", font=('Segoe UI', 8), bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor=W)
        
        # Navigation
        self.nav_frame = Frame(self.sidebar, bg=BG_DARK)
        self.nav_frame.pack(fill=X, pady=25)
        
        allowed_pages = ['dashboard']
        role = str(CURRENT_USER_ROLE).lower()
        
        # Consistent role checking
        is_high_level = any(r in role for r in ['admin', 'manager', 'leader'])
        
        if 'admin' in role:
            allowed_pages.extend(['projects', 'members', 'tasks', 'productivity', 'reports', 'analytics', 'requests'])
        elif 'leader' in role:
            allowed_pages.extend(['members', 'tasks', 'review_tasks', 'team_analytics', 'team_queries', 'leave_requests'])
        elif 'manager' in role:
            allowed_pages.extend(['projects', 'tasks', 'productivity', 'reports', 'analytics'])
        else: # Employee / Team Member / QA / etc.
            allowed_pages = ['dashboard', 'emp_team', 'emp_my_tasks', 'emp_analysis', 'emp_queries', 'emp_attendance', 'emp_leave_requests']

        # Safety guard: Team leaders should never see Projects in sidebar.
        if 'leader' in role and 'projects' in allowed_pages:
            allowed_pages.remove('projects')

        self.nav_buttons = {}
        self.employee_submenu_visible = False # State for submenu visibility

        # Define the order of main sidebar items (FLATTENED)
        main_sidebar_order = [
            'dashboard', # Main Managerial/Employee Dashboard
            'projects', 'members', 'tasks', 'productivity', 'reports', 'analytics', 'team_analytics', 'requests', 
            'review_tasks', 'team_leaves', 'team_queries', 'leave_requests', # Admin/TL items
            'emp_my_tasks', 'emp_team', 'emp_analysis', 
            'emp_queries', 'emp_attendance', 'emp_leave_requests' # Personal items
        ]

        # Build main sidebar items
        for key in main_sidebar_order:
            # Hard UI block: never render Projects menu for any leader role variant.
            if key == 'projects' and 'leader' in role:
                continue
            if key not in allowed_pages:
                continue
            label = key.capitalize().replace('emp_', '').replace('_', ' ')
            if role == 'project manager' and key == 'tasks':
                label = "Project Status"
            if role == 'team leader' and key == 'members':
                label = "My Team"
            
            # Special labels for personal items to distinguish if needed, 
            # but user wants them to look like the main list
            if key.startswith('emp_'):
                label = key.replace('emp_', '').capitalize().replace('_', ' ')
                if label == "My tasks": label = "My Tasks"
                if label == "Team": label = "PROJECT COLLEAGUES"

            icon = SIDEBAR_ICONS.get(key, '')
            # Fallback icons for personal items
            if not icon:
                if 'dashboard' in key: icon = '🏠'
                elif 'tasks' in key: icon = '📝'
                elif 'team' in key: icon = '👥'
                elif 'analysis' in key: icon = '📈'
                elif 'history' in key: icon = '📜'
                elif 'timeline' in key: icon = '🕒'
                elif 'queries' in key: icon = '❓'
                elif 'attendance' in key: icon = '📅'
                elif 'leave' in key: icon = '🏖️'
                elif 'timesheet' in key: icon = '⏱️'

            text_lbl = f"  {icon} {label}" if icon else f"  {label}"

            row = Frame(self.nav_frame, bg=BG_DARK)
            row.pack(fill=X, pady=0)

            # Accent left border (Red bar for active item)
            row._accent = Frame(row, bg=BG_DARK, width=4)
            row._accent.pack(side=LEFT, fill=Y)

            btn = Button(row, text=text_lbl.upper(),
                         font=('Segoe UI', 9, 'bold'), bg=BG_DARK, fg=TEXT_SECONDARY,
                         anchor="w", padx=25, pady=18, relief=FLAT, bd=0,
                         activebackground=SIDEBAR_ACTIVE_BG, activeforeground=WHITE,
                         command=lambda k=key: self.switch_page(k))
            btn.pack(side=LEFT, fill=X, expand=True)
            self.nav_buttons[key] = btn

            # Hover effects — row lights up on mouse-over
            def _on_nav_enter(e, r=row, b=btn, a=row._accent):
                try:
                    r.config(bg=SIDEBAR_ACTIVE_BG)
                    b.config(bg=SIDEBAR_ACTIVE_BG, fg=WHITE)
                    # Only color accent if not already active (active = PRIMARY_RED)
                    if a.cget('bg') == BG_DARK:
                        a.config(bg=BORDER_NAVY)
                except Exception: pass

            def _on_nav_leave(e, r=row, b=btn, a=row._accent):
                try:
                    # Restore only if not the active page
                    if b.cget('fg') != WHITE or a.cget('bg') == BORDER_NAVY:
                        r.config(bg=BG_DARK)
                        b.config(bg=BG_DARK, fg=TEXT_SECONDARY)
                        if a.cget('bg') == BORDER_NAVY:
                            a.config(bg=BG_DARK)
                except Exception: pass

            # Bind row and accent to click + hover
            def _wrap_click(event, k=key):
                self.switch_page(k)

            row.bind("<Button-1>", _wrap_click)
            row._accent.bind("<Button-1>", _wrap_click)
            row.bind("<Enter>", _on_nav_enter)
            row.bind("<Leave>", _on_nav_leave)
            btn.bind("<Enter>", _on_nav_enter)
            btn.bind("<Leave>", _on_nav_leave)
            # Ensure no right-click or middle-click triggers switch
            row.unbind("<Button-2>")
            row.unbind("<Button-3>")
            btn.unbind("<Button-2>")
            btn.unbind("<Button-3>")


    def build_header(self):
        # Title (Matching HTML preview)
        header_title = Frame(self.header, bg="#1a2035")
        header_title.pack(side=LEFT, padx=30, pady=15)
        
        Label(header_title, text="Project Monitoring System", font=('Rajdhani', 18, 'bold'), 
              bg="#1a2035", fg=WHITE).pack(anchor=W)
        
        # User Profile / Logout
        user_frame = Frame(self.header, bg="#1a2035")
        user_frame.pack(side=RIGHT, padx=30)
        
        # User Name & Role Box (Matching HTML preview)
        profile_box = Frame(user_frame, bg="#2d3555", padx=15, pady=8)
        profile_box.pack(side=LEFT, padx=15)
        
        role = CURRENT_USER_ROLE.lower()
        role_display = "USER"
        if role == 'project manager': role_display = "MANAGER"
        elif role == 'team leader': role_display = "LEADER"
        elif role == 'admin': role_display = "ADMIN"
        elif role == 'team member': role_display = "MEMBER"
        
        Label(profile_box, text=role_display, font=('Segoe UI', 8, 'bold'), 
              bg="#4a5568", fg=WHITE, padx=8, pady=2).pack(side=LEFT, padx=(0, 10))
        Label(profile_box, text=CURRENT_USER_NAME, font=('Segoe UI', 10, 'bold'), 
              bg="#2d3555", fg=WHITE).pack(side=LEFT)
        
        # Name box is now display-only to avoid redundancy with the 'Update Profile' button
        # (Click bindings removed)

        def _header_btn_enter(e, b): b.config(bg=HOVER_BG, fg=WHITE)
        def _header_btn_leave(e, b): b.config(bg=HEADER_BG, fg=TEXT_SECONDARY)
        
        btn_profile = Button(user_frame, text="Update Profile", font=('Segoe UI', 10, 'bold'), 
                           bg=HEADER_BG, fg=TEXT_SECONDARY, relief=FLAT, highlightthickness=1,
                           highlightbackground=BORDER_COLOR, command=self.show_user_details, padx=18, pady=8)
        btn_profile.pack(side=LEFT, padx=(0, 10))
        btn_profile.bind("<Enter>", lambda e: _header_btn_enter(e, btn_profile))
        btn_profile.bind("<Leave>", lambda e: _header_btn_leave(e, btn_profile))

        btn_logout = Button(user_frame, text="Logout", font=('Segoe UI', 10, 'bold'), 
                           bg=HEADER_BG, fg=TEXT_SECONDARY, relief=FLAT, highlightthickness=1,
                           highlightbackground=BORDER_COLOR, command=self.logout, padx=18, pady=8)
        btn_logout.pack(side=LEFT)
        btn_logout.bind("<Enter>", lambda e: _header_btn_enter(e, btn_logout))
        btn_logout.bind("<Leave>", lambda e: _header_btn_leave(e, btn_logout))

    def sync_data_from_api(self):
        """
        Deep-Sync: Fetches projects, tasks, and employees from the REST API 
        and updates the local SQLite database (employee.db).
        """
        debug_log("[API Sync] Starting full data synchronization...")
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # Sync Projects
            projects = api.get_projects()
            if isinstance(projects, list):
                for p in projects:
                    cur.execute("""
                        INSERT INTO projects (id, name, description, start_date, end_date, status, manager, team_leader, priority)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name, description=excluded.description, start_date=excluded.start_date,
                            end_date=excluded.end_date, status=excluded.status, manager=excluded.manager,
                            team_leader=excluded.team_leader, priority=excluded.priority
                    """, (
                        p.get('id'), p.get('name'), p.get('description'), p.get('start_date'),
                        p.get('end_date'), p.get('status'), p.get('manager'), p.get('team_leader'),
                        p.get('priority', 'Medium')
                    ))

            # Sync Tasks
            tasks = api.get_tasks()
            if isinstance(tasks, list):
                for t in tasks:
                    cur.execute("""
                        INSERT INTO tasks (id, title, description, project_id, assigned_to, due_date, priority, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            title=excluded.title, description=excluded.description, project_id=excluded.project_id,
                            assigned_to=excluded.assigned_to, due_date=excluded.due_date, priority=excluded.priority,
                            status=excluded.status
                    """, (
                        t.get('id'), t.get('title'), t.get('description'), t.get('project_id'),
                        t.get('assigned_to'), t.get('due_date'), t.get('priority'), t.get('status')
                    ))

            # Sync Employees
            members = api.get_members()
            if isinstance(members, list):
                for m in members:
                    cur.execute("""
                        INSERT INTO employee (id, name, email, role, mobile, dob)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET
                            name=excluded.name, email=excluded.email, role=excluded.role,
                            mobile=excluded.mobile, dob=excluded.dob
                    """, (
                        m.get('id'), m.get('name'), m.get('email'), m.get('role'),
                        m.get('mobile'), m.get('dob')
                    ))

            con.commit(); self.refresh_current_panel()
            con.close()
            return True
        except Exception as e:
            debug_log(f"[API Sync] Sync Error: {e}")
            return False

    def refresh_current_page(self, sync=True):
        """Universal Hot-Reload: Refreshes the active dashboard view. Optionally syncs from API first."""
        if not hasattr(self, 'current_page') or not self.current_page:
            return

        # Visual feedback during sync
        original_text = ""
        if hasattr(self, 'btn_refresh'):
            original_text = self.btn_refresh.cget('text')

        if sync:
            if hasattr(self, 'btn_refresh'):
                self.btn_refresh.config(text="⚡ Syncing...", state=DISABLED)
                self.root.update_idletasks()

            def _bg_sync_thread():
                # Perform REST API -> SQLite Sync in background
                sync_success = self.sync_data_from_api()
                # Delegate UI updates back to the main thread securely using lambda to avoid registration issues
                self.root.after(0, lambda: self._complete_hot_reload(sync_success, original_text))

            threading.Thread(target=_bg_sync_thread, daemon=True).start()
        else:
            self._complete_hot_reload(True, original_text)



    def refresh_current_panel(self):
        """Call the correct refresh for whichever panel/tab is currently active."""
        try:
            # Refresh projects list
            if hasattr(self, 'load_projects'):
                self.load_projects()
            if hasattr(self, 'refresh_projects'):
                self.refresh_projects()
            # Refresh tasks list
            if hasattr(self, 'load_tasks'):
                self.load_tasks()
            if hasattr(self, 'refresh_tasks'):
                self.refresh_tasks()
            # Refresh members/users list
            if hasattr(self, 'load_members'):
                self.load_members()
            if hasattr(self, 'load_users'):
                self.load_users()
            if hasattr(self, 'refresh_members'):
                self.refresh_members()
            # Refresh teams list
            if hasattr(self, 'load_teams'):
                self.load_teams()
            if hasattr(self, 'refresh_teams'):
                self.refresh_teams()
            # Refresh dashboard stats
            if hasattr(self, 'load_dashboard'):
                self.load_dashboard()
            if hasattr(self, 'update_dashboard_stats'):
                self.update_dashboard_stats()
            if hasattr(self, 'refresh_dashboard'):
                self.refresh_dashboard()
        except Exception as e:
            print(f"[refresh_current_panel] Error: {e}")
    def refresh_current_panel(self):
        """Call the correct refresh for whichever panel/tab is currently active."""
        try:
            # Refresh projects list
            if hasattr(self, 'load_projects'):
                self.load_projects()
            if hasattr(self, 'refresh_projects'):
                self.refresh_projects()
            # Refresh tasks list
            if hasattr(self, 'load_tasks'):
                self.load_tasks()
            if hasattr(self, 'refresh_tasks'):
                self.refresh_tasks()
            # Refresh members/users list
            if hasattr(self, 'load_members'):
                self.load_members()
            if hasattr(self, 'load_users'):
                self.load_users()
            if hasattr(self, 'refresh_members'):
                self.refresh_members()
            # Refresh teams list
            if hasattr(self, 'load_teams'):
                self.load_teams()
            if hasattr(self, 'refresh_teams'):
                self.refresh_teams()
            # Refresh dashboard stats
            if hasattr(self, 'load_dashboard'):
                self.load_dashboard()
            if hasattr(self, 'update_dashboard_stats'):
                self.update_dashboard_stats()
            if hasattr(self, 'refresh_dashboard'):
                self.refresh_dashboard()
        except Exception as e:
            print(f"[refresh_current_panel] Error: {e}")
    def _complete_hot_reload(self, success, original_text):
        # Restore button
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.config(text=original_text, state=NORMAL)

        # Trigger refresh based on current page
        if self.current_page == 'emp_analysis':
            self.refresh_emp_analysis()
        elif self.current_page == 'emp_dashboard':
            self.refresh_emp_dashboard()
        elif self.current_page == 'emp_my_tasks':
            self.refresh_emp_tasks_tab()
        else:
            # Full reload for other pages
            self.switch_page(self.current_page)
        
        print(f"[UI Sync] Page '{self.current_page}' synchronized and updated.")

    def update_notification_count(self):
        count = 0
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Password reset requests (uses reset_requests table, not a column on users)
            try:
                cur.execute("SELECT COUNT(*) FROM reset_requests WHERE status='Pending'")
                count += cur.fetchone()[0]
            except: pass
            # Leave requests
            try:
                cur.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'Pending'")
                count += cur.fetchone()[0]
            except: pass
            con.close()
        except: pass
        
        # Guard: widget may have been destroyed if page was switched
        try:
            if hasattr(self, 'notif_btn') and self.notif_btn.winfo_exists():
                self.notif_btn.config(text=f"Notifications ({count})")
                if count > 0:
                    self.notif_btn.config(fg=ACCENT_ORANGE)
                else:
                    self.notif_btn.config(fg=TEXT_WHITE)
        except: pass
        
        # Schedule next update
        self.root.after(30000, self.update_notification_count) # Every 30s

    # Tooltip Logic
    def show_tooltip(self, event, text):
        if hasattr(self, 'tooltip_win') and self.tooltip_win:
            self.tooltip_win.destroy()
        x = event.widget.winfo_rootx() + 25
        y = event.widget.winfo_rooty() + 35
        self.tooltip_win = Toplevel(self.root)
        self.tooltip_win.wm_overrideredirect(True)
        self.tooltip_win.wm_geometry(f"+{x}+{y}")
        Label(self.tooltip_win, text=text, font=('Segoe UI', 9), bg="#1f2937", fg="white", relief=SOLID, borderwidth=1, padx=5, pady=2).pack()

    def hide_tooltip(self):
        if hasattr(self, 'tooltip_win') and self.tooltip_win:
            self.tooltip_win.destroy()
            self.tooltip_win = None

    def show_user_details(self):
        # Prevent duplicate profile windows
        if hasattr(self, '_profile_window_active') and self._profile_window_active:
            try:
                if self._profile_window_active.winfo_exists():
                    self._profile_window_active.lift()
                    self._profile_window_active.focus_force()
                    return
            except:
                pass

        t = Toplevel(self.root)
        self._profile_window_active = t
        t.title("My Profile & Security")
        t.geometry("920x760")
        t.config(bg=CONTENT_BG)
        t.minsize(760, 620)
        t.resizable(True, True)

        # Center the window
        x = int((self.root.winfo_screenwidth()/2) - (920/2))
        y = int((self.root.winfo_screenheight()/2) - (760/2))
        t.geometry(f"920x760+{x}+{y}")

        # --- DATA FETCHING ---
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        
        user_data = {}
        is_admin = CURRENT_USER_ROLE.lower() == 'admin'
        
        if is_admin:
            cursor.execute("SELECT username, email FROM users WHERE username=?", (CURRENT_USER_NAME,))
            row = cursor.fetchone()
            if row:
                user_data = {'Name': row[0], 'Email': row[1], 'Role': 'Administrator', 'Mobile': 'N/A', 'Department': 'Management'}
        else:
            cursor.execute('PRAGMA table_info(employee)')
            cols = [info[1] for info in cursor.fetchall()]
            query = "SELECT name, mobile, email, address, gender, dob, department, role"
            if 'reporting_manager' in cols:
                query += ", reporting_manager"
            query += " FROM employee WHERE name=?"
            
            cursor.execute(query, (CURRENT_USER_NAME,))
            row = cursor.fetchone()
            if row:
                user_data = {
                    'Name': row[0], 'Mobile': row[1], 'Email': row[2], 
                    'Address': row[3], 'Gender': row[4], 'DOB': row[5], 
                    'Department': row[6], 'Role': row[7]
                }
                if 'reporting_manager' in cols:
                    user_data['Reporting Manager'] = row[8]
        con.close()

        # --- SCROLLABLE CANVAS ---
        canvas = Canvas(t, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = Scrollbar(t, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        # Enable mousewheel scrolling
        self._bind_canvas_scrolling(t, canvas)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # --- HERO SECTION ---
        hero = Frame(scrollable_frame, bg=HEADER_BG, padx=28, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hero.pack(fill=X, padx=30, pady=(26, 18))
        
        # Left: Avatar
        avatar_side = Frame(hero, bg=HEADER_BG)
        avatar_side.pack(side=LEFT)
        avatar = Canvas(avatar_side, width=80, height=80, bg=HEADER_BG, highlightthickness=0)
        avatar.pack()
        avatar.create_oval(2, 2, 78, 78, fill=ACCENT_BLUE, outline="")
        initial = (user_data.get('Name', 'U')[:1]).upper()
        avatar.create_text(40, 40, text=initial, fill=WHITE, font=('Segoe UI', 26, 'bold'))

        # Center: Info
        info_side = Frame(hero, bg=HEADER_BG, padx=20)
        info_side.pack(side=LEFT, fill=BOTH, expand=True)
        
        Label(info_side, text=user_data.get('Name', '').title(), font=('Segoe UI', 20, 'bold'), bg=HEADER_BG, fg=WHITE).pack(anchor=W)
        
        role_chip = Frame(info_side, bg=ACCENT_BLUE, padx=10, pady=2)
        role_chip.pack(anchor=W, pady=(4, 8))
        Label(role_chip, text=user_data.get('Role', '').upper(), font=('Segoe UI', 9, 'bold'), bg=ACCENT_BLUE, fg=WHITE).pack()
        
        contact_line = Frame(info_side, bg=HEADER_BG)
        contact_line.pack(anchor=W)
        Label(contact_line, text=f"✉ {user_data.get('Email', 'N/A')}", font=('Segoe UI', 10), bg=HEADER_BG, fg="#707ea2").pack(side=LEFT)
        Label(contact_line, text="  •  ", font=('Segoe UI', 10), bg=HEADER_BG, fg="#707ea2").pack(side=LEFT)
        Label(contact_line, text=f"📞 {user_data.get('Mobile', 'N/A')}", font=('Segoe UI', 10), bg=HEADER_BG, fg="#707ea2").pack(side=LEFT)

        # Right: Edit Button
        btn_side = Frame(hero, bg=HEADER_BG)
        btn_side.pack(side=RIGHT, anchor=N)

        # --- MAIN CONTENT AREA (Cards side by side) ---
        cards_container = Frame(scrollable_frame, bg=CONTENT_BG)
        cards_container.pack(fill=BOTH, expand=True, padx=30, pady=10)

        # --- LEFT: PROFILE INFORMATION CARD ---
        prof_card = Frame(cards_container, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=26, pady=24)
        prof_card.pack(side=LEFT, fill=BOTH, expand=True)

        prof_header = Frame(prof_card, bg=CARD_BG)
        prof_header.pack(fill=X, pady=(0, 20))
        Label(prof_header, text="🛡 Profile Information", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=WHITE).pack(anchor=W)
        Label(prof_header, text="View and manage your personal details", font=('Segoe UI', 9), bg=CARD_BG, fg="#707ea2").pack(anchor=W, pady=(2, 0))

        fields_frame = Frame(prof_card, bg=CARD_BG)
        fields_frame.pack(fill=BOTH, expand=True)
        for i in range(2): fields_frame.grid_columnconfigure(i, weight=1)

        entries = {}
        field_list = [
            ("Department", user_data.get('Department', 'N/A'), False),
            ("Email", user_data.get('Email', 'N/A'), True),
            ("Gender", user_data.get('Gender', 'N/A'), False),
            ("Mobile", user_data.get('Mobile', 'N/A'), True),
            ("Date of Birth", user_data.get('DOB', 'N/A'), False),
            ("Address", user_data.get('Address', 'N/A'), True),
        ]
        if not is_admin and 'Reporting Manager' in user_data:
            field_list.append(("Reporting Manager", user_data.get('Reporting Manager', 'Unassigned'), False))

        for idx, (lbl, val, editable) in enumerate(field_list):
            r, c = divmod(idx, 2)
            tile = Frame(fields_frame, bg=HEADER_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=10)
            tile.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            
            Label(tile, text=lbl.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg="#707ea2").pack(anchor=W)
            ent = Entry(tile, font=('Segoe UI', 10), bg="#253244", fg=WHITE, relief=FLAT, disabledbackground="#253244", disabledforeground=WHITE, insertbackground=WHITE)
            ent.insert(0, val if val else "")
            ent.config(state='disabled')
            ent.pack(fill=X, pady=(5, 0))
            entries[lbl] = (ent, editable, tile)

        # --- RIGHT: SECURITY CARD ---
        sec_card = Frame(cards_container, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=26, pady=24)
        sec_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(20, 0))

        sec_header = Frame(sec_card, bg=CARD_BG)
        sec_header.pack(fill=X, pady=(0, 20))
        Label(sec_header, text="🛡 Security", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=WHITE).pack(anchor=W)
        Label(sec_header, text="Update your password regularly", font=('Segoe UI', 9), bg=CARD_BG, fg="#707ea2").pack(anchor=W, pady=(2, 0))

        # Password Grid
        pass_grid = Frame(sec_card, bg=CARD_BG)
        pass_grid.pack(fill=X)
        pass_grid.grid_columnconfigure(0, weight=1)
        pass_grid.grid_columnconfigure(1, weight=1)

        def make_pass_tile(parent, col, title):
            tile = Frame(parent, bg=HEADER_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=10)
            tile.grid(row=0, column=col, sticky="nsew", padx=4, pady=4)
            Label(tile, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg="#707ea2").pack(anchor=W)
            
            entry_f = Frame(tile, bg="#253244")
            entry_f.pack(fill=X, pady=(5, 0))
            
            ent = Entry(entry_f, show="*", font=('Segoe UI', 10), bg="#253244", fg=WHITE, relief=FLAT, insertbackground=WHITE)
            ent.pack(side=LEFT, fill=X, expand=True)
            
            def toggle():
                if ent.cget('show') == '*':
                    ent.config(show='')
                    btn_eye.config(fg=ACCENT_BLUE)
                else:
                    ent.config(show='*')
                    btn_eye.config(fg="#707ea2")
            
            btn_eye = Button(entry_f, text="👁", font=('Segoe UI', 10), bg="#253244", fg="#707ea2", relief=FLAT, activebackground="#253244", command=toggle)
            btn_eye.pack(side=RIGHT)
            return ent

        curr_pass_ent = make_pass_tile(pass_grid, 0, "Current Password")
        new_pass_ent = make_pass_tile(pass_grid, 1, "New Password")

        # Security Tip
        tip_box = Frame(sec_card, bg=HEADER_BG, highlightbackground=ACCENT_ORANGE, highlightthickness=1, padx=14, pady=12)
        tip_box.pack(fill=X, pady=20)
        Label(tip_box, text="SECURITY TIP", font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=ACCENT_ORANGE).pack(anchor=W)
        Label(tip_box, text="Use a strong password combining letters, numbers, and symbols.", font=('Segoe UI', 9), bg=HEADER_BG, fg="#707ea2", wraplength=300, justify=LEFT).pack(anchor=W, pady=(4, 0))

        # Update Password Logic
        def do_update_password():
            cp = curr_pass_ent.get()
            np = new_pass_ent.get()
            if not cp or not np:
                messagebox.showerror("Error", "All password fields required.")
                return
            
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                hp = hashlib.sha256(cp.encode()).hexdigest()
                
                if is_admin:
                    cur.execute("SELECT password FROM users WHERE username=?", (CURRENT_USER_NAME,))
                else:
                    cur.execute("SELECT password FROM employee WHERE name=?", (CURRENT_USER_NAME,))
                
                row = cur.fetchone()
                if not row or row[0] != hp:
                    messagebox.showerror("Error", "Incorrect current password.")
                    con.close()
                    return
                
                new_hp = hashlib.sha256(np.encode()).hexdigest()
                if is_admin:
                    cur.execute("UPDATE users SET password=? WHERE username=?", (new_hp, CURRENT_USER_NAME))
                else:
                    cur.execute("UPDATE employee SET password=? WHERE name=?", (new_hp, CURRENT_USER_NAME))
                
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Password updated successfully.")
                curr_pass_ent.delete(0, END)
                new_pass_ent.delete(0, END)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update password: {e}")

        btn_update_pass = Button(sec_card, text="Update Password", font=('Segoe UI', 10, 'bold'), bg=ACCENT_ORANGE, fg=WHITE, relief=FLAT, padx=16, pady=8, command=do_update_password)
        btn_update_pass.pack(fill=X)

        # --- EDIT LOGIC ---
        def start_edit():
            for lbl, (ent, editable, tile) in entries.items():
                if editable:
                    ent.config(state='normal')
            btn_edit.pack_forget()
            btn_save.pack(side=LEFT, padx=(0, 10))
            btn_cancel.pack(side=LEFT)

        def cancel_edit():
            t.destroy()
            self.show_user_details()

        def save_changes():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                if is_admin:
                    cur.execute("UPDATE users SET email=? WHERE username=?", (entries['Email'][0].get(), CURRENT_USER_NAME))
                else:
                    cur.execute("UPDATE employee SET mobile=?, email=?, address=? WHERE name=?", 
                                (entries['Mobile'][0].get(), entries['Email'][0].get(), entries['Address'][0].get(), CURRENT_USER_NAME))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Profile updated.")
                t.destroy()
                self.show_user_details()
            except Exception as e:
                messagebox.showerror("Error", f"Update failed: {e}")

        btn_edit = Button(btn_side, text="Edit Profile", font=('Segoe UI', 10, 'bold'), bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, padx=16, pady=9, command=start_edit)
        btn_edit.pack()
        
        btn_save = Button(btn_side, text="Save Changes", font=('Segoe UI', 10, 'bold'), bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, padx=16, pady=9, command=save_changes)
        btn_cancel = Button(btn_side, text="Cancel", font=('Segoe UI', 10, 'bold'), bg=HEADER_BG, fg=WHITE, relief=FLAT, padx=16, pady=9, command=cancel_edit, highlightbackground=BORDER_COLOR, highlightthickness=1)

        # --- FOOTER BAR ---
        footer = Frame(scrollable_frame, bg=CONTENT_BG, padx=30)
        footer.pack(fill=X, pady=(8, 24))
        Label(footer, text="Profile changes apply immediately to your workspace record.", font=('Segoe UI', 9), bg=CONTENT_BG, fg="#707ea2").pack(side=LEFT)
        Button(footer, text="Close Profile", font=('Segoe UI', 10, 'bold'), bg=PRIMARY_RED, fg=WHITE, relief=FLAT, padx=20, pady=10, command=t.destroy).pack(side=RIGHT)
        


    def show_notifications(self):
        role = CURRENT_USER_ROLE.lower()
        if role in ['admin', 'project manager', 'team leader']:
            self.show_admin_requests()
        else:
            self.show_user_messages()

    def show_user_messages(self):
        t = Toplevel(self.root)
        t.title("Notifications")
        t.geometry("400x500")
        t.minsize(400, 425)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        Label(t, text="Notifications", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=10)
        
        # Mark all as read button
        def mark_all_read():
            try:
                con = sqlite3.connect(get_db_path())
                cursor = con.cursor()
                cursor.execute("UPDATE notifications SET is_read=1 WHERE user=?", (CURRENT_USER_NAME,))
                con.commit(); self.refresh_current_panel()
                con.close()
                load_notifs()
            except: pass
            
        Button(t, text="Mark All Read", command=mark_all_read, bg=PRIMARY_BG, fg=TEXT_WHITE, relief=FLAT).pack(pady=5)
        
        f_list = Frame(t, bg=CONTENT_BG)
        f_list.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        canvas = Canvas(f_list, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(f_list, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        def load_notifs():
            for w in scrollable_frame.winfo_children(): w.destroy()
            
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            # Get unread first, then read
            cursor.execute("SELECT message, timestamp, is_read FROM notifications WHERE user=? ORDER BY is_read ASC, id DESC LIMIT 20", (CURRENT_USER_NAME,))
            rows = cursor.fetchall()
            
            if not rows:
                Label(scrollable_frame, text="No notifications", bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=20)
            
            for msg, ts, is_read in rows:
                bg_color = CARD_BG if is_read else "#4a484d"
                card = Frame(scrollable_frame, bg=bg_color, pady=10, padx=10)
                card.pack(fill=X, pady=2)
                
                Label(card, text=msg, font=('Segoe UI', 10), bg=bg_color, fg=TEXT_WHITE, wraplength=350, justify=LEFT).pack(anchor="w")
                Label(card, text=ts, font=('Segoe UI', 8), bg=bg_color, fg=MUTED_TEXT).pack(anchor="w")
                
            con.close()
            
        load_notifs()

    def check_session_timeout(self):
        """Check if session has expired (8 hours)."""
        try:
            if not os.path.exists('session.json'):
                return False
            with open('session.json', 'r') as f:
                data = json.load(f)
            
            if 'login_time' in data:
                login_time = datetime.strptime(data['login_time'], "%Y-%m-%d %H:%M:%S")
                if datetime.now() - login_time > timedelta(hours=8):
                    messagebox.showwarning("Session Expired", "Your session has expired. Please login again.")
                    self.logout()
                    return False
            return True
        except Exception as e:
            print(f"Error checking session: {e}")
            return True

    def switch_page(self, page_name, force=False):
        # Hard route guard: Team Leader cannot open Projects page.
        role = str(CURRENT_USER_ROLE).lower()
        if page_name == 'projects' and 'leader' in role:
            page_name = 'dashboard'

        if not force and hasattr(self, 'current_page') and self.current_page == page_name:
            return # Don't re-load if already on the page
        
        debug_log(f"DEBUG: Switching to page: {page_name}")
        
        if not self.check_session_timeout():
            return
        
        # Stop existing timers when switching
        if hasattr(self, '_auto_refresh_timer') and self._auto_refresh_timer:
            self.root.after_cancel(self._auto_refresh_timer)
            self._auto_refresh_timer = None

        if not (CURRENT_USER_ROLE.lower() == 'project manager' and page_name == 'dashboard'):
            self.stop_pm_dashboard_auto_refresh()
        
        # Track last page for popups (like Profile) to return to
        if hasattr(self, 'current_page') and self.current_page and self.current_page != 'profile':
            self._last_page = self.current_page
        # Update Sidebar State
        for key, btn in self.nav_buttons.items():
            row = btn.master
            if key == page_name:
                btn.config(bg=SIDEBAR_ACTIVE_BG, fg=WHITE)
                row.config(bg=SIDEBAR_ACTIVE_BG)
                try: row._accent.config(bg=PRIMARY_RED)
                except: pass
            else:
                btn.config(bg=BG_DARK, fg=TEXT_SECONDARY)
                row.config(bg=BG_DARK)
                try: row._accent.config(bg=BG_DARK)
                except: pass
        
        # Update Employee Submenu State
        if hasattr(self, 'employee_submenu_buttons'):
            for key, btn in self.employee_submenu_buttons.items():
                row = btn.master
                if key == page_name:
                    btn.config(bg=SIDEBAR_ACTIVE_BG, fg=TEXT_WHITE)
                    try: row._accent.config(bg=PRIMARY_RED)
                    except: pass
                    # Also ensure the parent 'employee_panel' button is highlighted
                    if 'employee_panel' in self.nav_buttons:
                        emp_btn = self.nav_buttons['employee_panel']
                        emp_btn.config(bg=SIDEBAR_ACTIVE_BG, fg=TEXT_WHITE)
                        try: emp_btn.master._accent.config(bg=PRIMARY_RED)
                        except: pass
                else:
                    btn.config(bg=BG_DARK, fg=TEXT_SECONDARY)
                    try: row._accent.config(bg=BG_DARK)
                    except: pass
            
            # If no submenu item is active, ensure parent 'employee_panel' is not highlighted
            if not any(key == page_name for key in self.employee_submenu_buttons.keys()):
                if 'employee_panel' in self.nav_buttons:
                    emp_btn = self.nav_buttons['employee_panel']
                    emp_btn.config(bg=BG_DARK, fg=TEXT_SECONDARY)
                    try: emp_btn.master._accent.config(bg=BG_DARK)
                    except: pass
                
        # Clear Content
        for widget in self.content_area.winfo_children():
            widget.destroy()
            
        self.current_page = page_name
        # Breadcrumb
        try:
            self.render_breadcrumb(page_name)
        except Exception as e:
            debug_log(f"DEBUG Error in render_breadcrumb: {e}")
            
        
        try:
            if page_name == 'dashboard':
                role = CURRENT_USER_ROLE.lower()
                # Executive Dashboard handles Admin and Team Leader views internally
                if role in ['admin', 'team leader']:
                    self.load_dashboard()
                # Project Manager gets their dedicated PM Dashboard
                elif role == 'project manager':
                    self.load_pm_dashboard()
                # Regular employees get their specific Employee Dashboard
                else:
                    self.load_emp_dashboard()
            elif page_name == 'projects':
                self.load_projects()
            elif page_name == 'members':
                self.load_members()
            elif page_name == 'tasks':
                self.load_tasks()
            elif page_name == 'productivity':
                self.load_productivity()
            elif page_name == 'reports':
                self.load_reports()
            elif page_name == 'audit':
                self.load_audit()

            elif page_name == 'requests':
                self.show_reset_requests()
            elif page_name == 'analytics':
                # Use a small delay to let the UI update (showing the active sidebar state)
                # before the heavy analytics engine starts processing.
                self.root.after(100, self.load_analytics)
            elif page_name == 'team_analytics':
                self.root.after(100, self.load_team_analytics)
            elif page_name == 'showcase':
                self.load_showcase()
            elif page_name == 'leave_requests':
                self.load_leave_requests()
            elif page_name == 'review_tasks':
                self.load_review_tasks()
            elif page_name == 'team_leaves':
                self.load_team_leaves()
            elif page_name == 'my_leaves':
                self.load_my_leaves()
            # Employee Sub-pages
            elif page_name == 'emp_dashboard':
                self.load_emp_dashboard()
            elif page_name == 'emp_my_tasks':
                self.load_emp_my_tasks()
            elif page_name == 'emp_team':
                self.load_emp_team()
            elif page_name == 'emp_analysis':
                self.load_emp_analysis()
            elif page_name == 'emp_history':
                self.load_emp_history()
            elif page_name == 'emp_queries':
                self.load_emp_queries()
            elif page_name == 'emp_attendance':
                self.load_emp_attendance()
            elif page_name == 'emp_leave_requests':
                self.load_emp_leave_requests()
            elif page_name == 'emp_timesheets':
                self.load_emp_timesheets()
            elif page_name == 'emp_timeline':
                self.load_emp_timeline()
            elif page_name == 'team_queries':
                self.load_team_queries()
            elif page_name == 'team_queries':
                self.load_team_queries()

            # For all employee sub-pages, inject the horizontal tab bar after content is cleared
            # (Note: This is called after the specific load_* methods if we want it to persist,
            #  but better to call it inside load_* or at the top of content_area)
            # Actually, because load_* methods repopulate content_area, we should render tabs FIRST.
            # But switch_page clears content first. So we call render_breadcrumb, then render_tabs, then load_*.

            debug_log(f"DEBUG: Page {page_name} loaded successfully")
        except Exception as e:
            debug_log(f"DEBUG: Error loading page {page_name}: {e}")
            messagebox.showerror("Page Error", f"Failed to load page {page_name}: {e}")

    # ==================== PAGES ====================
    
    def load_dashboard(self):
        debug_log("DEBUG: Loading dashboard...")
        # Dashboard Logic
        role = CURRENT_USER_ROLE.lower()
        
        # Dedicated Dashboard Routing handled by switch_page now, but adding safe guard
        if role == 'project manager':
            self.load_pm_dashboard()
            return
        elif role not in ['admin', 'team leader']:
            self.load_emp_dashboard()
            return

        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        debug_log(f"DEBUG: Dashboard database connected for role: {role}")
        
        # Determine Filter for Team Leader
        is_tl = role == 'team leader'
        is_pm = role == 'project manager'
        is_admin = role == 'admin'
        
        # Check Pending Password Requests (Hierarchy Based)
        # Admin: All
        # PM: TLs + Employees (Team Member)
        # TL: Employees (Team Member)
        pending_requests = 0
        try:
            if is_admin:
                cursor.execute("SELECT COUNT(*) FROM reset_requests WHERE status='Pending'")
            elif is_pm:
                cursor.execute("SELECT COUNT(*) FROM reset_requests WHERE status='Pending' AND role IN ('Team Leader', 'Team Member', 'Employee')")
            elif is_tl:
                cursor.execute("SELECT COUNT(*) FROM reset_requests WHERE status='Pending' AND role IN ('Team Member', 'Employee')")
            
            row = cursor.fetchone()
            if row:
                pending_requests = row[0]
        except Exception as e:
            debug_log(f"DEBUG: Error checking pending requests: {e}")
            pending_requests = 0

        # --- Data Fetching ---
        upcoming = []
        if is_tl:
            # Filtered Stats for Team Leader
            # Consolidated High-Performance Stats Query
            try:
                cursor.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM (
                            SELECT DISTINCT TRIM(e.name)
                            FROM employee e
                            WHERE e.name IS NOT NULL AND TRIM(e.name) != ''
                              AND (e.reporting_manager = ? OR e.name IN (
                                  SELECT DISTINCT assigned_to FROM tasks 
                                  WHERE project_id IN (SELECT id FROM projects WHERE lower(team_leader) LIKE lower(?))
                              ))
                              AND lower(e.name) != lower(?)
                        )) as members,
                        (SELECT COUNT(*) FROM tasks WHERE status IN ('Ongoing', 'In Progress', 'Pending') 
                            AND project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)) as active,
                        (SELECT COUNT(*) FROM tasks WHERE status = 'Pending Approval'
                            AND project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)) as pending,
                        (SELECT COUNT(*) FROM tasks WHERE status != 'Completed' AND due_date < date('now')
                            AND project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)) as overdue,
                        (SELECT COUNT(*) FROM tasks WHERE status='Completed' 
                            AND (date(completed_date) >= date('now', '-7 days') OR date(created_date) >= date('now', '-7 days'))
                            AND project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)) as velocity
                """, (CURRENT_USER_NAME, f"%{CURRENT_USER_NAME}%", CURRENT_USER_NAME, 
                      f"%{CURRENT_USER_NAME}%", f"%{CURRENT_USER_NAME}%", f"%{CURRENT_USER_NAME}%", f"%{CURRENT_USER_NAME}%"))
                
                stats_row = cursor.fetchone()
                total_members, active_tasks, pending_reviews, overdue_tasks, completed_this_week = stats_row
            except Exception as e:
                debug_log(f"DEBUG: Dashboard Stats Error: {e}")
                total_members = active_tasks = pending_reviews = overdue_tasks = completed_this_week = 0
            
            # 5. Pending Requests is already pending_requests
            
            # Urgent Alerts: Overdue > 3 days or High Priority
            cursor.execute("""
                SELECT title, due_date, priority, assigned_to 
                FROM tasks 
                WHERE status != 'Completed' 
                AND (date(due_date) < date('now', '-3 days') OR priority='High')
                AND project_id IN (
                    SELECT id FROM projects WHERE lower(COALESCE(team_leader,'')) LIKE lower(?)
                )
                ORDER BY due_date ASC LIMIT 5
            """, (f"%{CURRENT_USER_NAME}%",))
            urgent_alerts = cursor.fetchall()

            # For backward compatibility if needed by UI sections I haven't changed yet
            total_projects = 0
            active_projects = 0
            total_tasks = active_tasks + overdue_tasks
            delayed_tasks = overdue_tasks
            # Fetch active projects and progress percentages for the team leader's Gantt Chart
            project_progress_data = []
            try:
                cursor.execute("""
                    SELECT id, name, team_leader, manager, start_date, end_date, status 
                    FROM projects 
                    WHERE (lower(team_leader) LIKE ? OR lower(team_leader) = ?) AND (status='Ongoing' OR status='Delayed')
                """, (f"%{CURRENT_USER_NAME.lower()}%", CURRENT_USER_NAME.lower()))
                active_projs_rows = cursor.fetchall()
                for pid, pname, leader, mgr, sd_str, ed_str, p_status in active_projs_rows:
                    cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
                    tot = cursor.fetchone()[0] or 0
                    cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
                    done = cursor.fetchone()[0] or 0
                    prog = int((done/tot)*100) if tot > 0 else 0
                    project_progress_data.append((pid, pname, leader, mgr, sd_str or '2026-05-15', ed_str or '2026-06-15', prog, p_status))
            except Exception as e:
                debug_log(f"DEBUG: Error fetching project progress for Gantt: {e}")

            task_dist = {}
            
        else:
            # Global Stats (Admin / Project Manager)
            cursor.execute("SELECT COUNT(*) FROM projects")
            total_projects = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT team_leader) FROM projects WHERE team_leader IS NOT NULL AND team_leader != ''")
            total_tls = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM employee")
            total_employees = cursor.fetchone()[0] or 0
            
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Ongoing'")
            active_projects = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Delayed'")
            delayed_projects = cursor.fetchone()[0]
            
            # Project Progress (Active Projects Health)
            cursor.execute("SELECT id, name, team_leader, manager, end_date, status FROM projects WHERE status='Ongoing' OR status='Delayed' LIMIT 5")
            active_projs_rows = cursor.fetchall()
            project_progress_data = []
            for pid, pname, leader, mgr, end_date, p_status in active_projs_rows:
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
                tot = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
                done = cursor.fetchone()[0] or 0
                prog = int((done/tot)*100) if tot > 0 else 0
                project_progress_data.append((pid, pname, leader, mgr, end_date, prog, p_status))
                
            # Task Distribution
            cursor.execute("SELECT status, COUNT(*) FROM tasks GROUP BY status")
            task_dist = {r[0]: r[1] for r in cursor.fetchall()}
            
            # Critical Deadlines (Top 5 approaching/overdue)
            cursor.execute("""
                SELECT title, due_date 
                FROM tasks 
                WHERE status != 'Completed' 
                ORDER BY date(due_date) ASC LIMIT 5
            """)
            upcoming = cursor.fetchall()
            
            # Recent Audit Logs
            recent_activity = []
            try:
                # Prioritize activity_timeline for detail, fall back to audit_logs
                cursor.execute("SELECT user_name, action, DATE(timestamp) FROM activity_timeline ORDER BY id DESC LIMIT 5")
                recent_activity = cursor.fetchall()
            except:
                try:
                    cursor.execute("SELECT user, action, DATE(timestamp) FROM audit_logs ORDER BY id DESC LIMIT 5")
                    recent_activity = cursor.fetchall()
                except:
                    pass
        
        # --- UI Building ---
        
        # Scrollable Wrapper
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        self._bind_canvas_scrolling(wrapper, canvas, allow_horizontal=True)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        parent = scrollable_frame
        
        if is_tl:
            title_text = "Team Dashboard"
        elif is_pm:
            title_text = "Project Manager Dashboard"
        else:
            title_text = "Executive Dashboard"
        
        # Header Row with Title + Sync
        h_frame = Frame(parent, bg=CONTENT_BG)
        h_frame.pack(fill=X, padx=30, pady=(30, 20))
        
        Label(h_frame, text=title_text, font=('Segoe UI', 22, 'bold'), 
              bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
              
        def _force_refresh():
            self.switch_page('dashboard')
            
        Button(h_frame, text="↻ Refresh", command=_force_refresh, bg=BG_DARK, fg=TEXT_SECONDARY, 
               relief=FLAT, font=('Segoe UI', 10), padx=15, pady=8, highlightbackground="#2e3760", highlightthickness=1).pack(side=RIGHT)


        # Pending Requests Notification
        if pending_requests > 0:
            def open_requests():
                self.show_reset_requests()
                
            btn_req = Button(h_frame, text=f"{pending_requests} Password Requests", command=open_requests, 
                bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT)
            btn_req.pack(side=RIGHT)

        def bind_click_targets(widget_list, callback):
            for widget in widget_list:
                try:
                    widget.configure(cursor="hand2")
                except Exception:
                    pass
                try:
                    widget.bind("<Button-1>", lambda _e, cb=callback: cb())
                except Exception:
                    pass

        if is_tl:
            # New 2-Column Layout for Trial Phase (Mockup inspired)
            grid_frame = Frame(parent, bg=CONTENT_BG)
            grid_frame.pack(fill=BOTH, expand=True, padx=30, pady=10)
            
            left_col = Frame(grid_frame, bg=CONTENT_BG)
            left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 15))
            
            right_col = Frame(grid_frame, bg=CONTENT_BG, width=320)
            right_col.pack(side=RIGHT, fill=Y, padx=(15, 0))
            
            # --- LEFT COLUMN ---
            # 1. Task Status (KPI Cards in a grid)
            status_f = Frame(left_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            status_f.pack(fill=X, pady=(0, 20))
            
            Label(status_f, text="TASK STATUS", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            cards_wrap = Frame(status_f, bg=CARD_BG)
            cards_wrap.pack(fill=X)
            cards_wrap.grid_columnconfigure(0, weight=1)
            cards_wrap.grid_columnconfigure(1, weight=1)
            cards_wrap.grid_columnconfigure(2, weight=1)
            
            def make_status_card(p, col, title, val, color):
                c = Frame(p, bg="#1c223d", padx=15, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
                c.grid(row=0, column=col, sticky="nsew", padx=5)
                Label(c, text=title, font=('Segoe UI', 8, 'bold'), bg="#1c223d", fg=MUTED_TEXT).pack(anchor=W)
                Label(c, text=str(val), font=('Segoe UI', 24, 'bold'), bg="#1c223d", fg=color).pack(anchor=W, pady=(5, 0))
                return c
                
            make_status_card(cards_wrap, 0, "PENDING", pending_reviews, ACCENT_RED)
            make_status_card(cards_wrap, 1, "IN PROGRESS", active_tasks, ACCENT_ORANGE)
            make_status_card(cards_wrap, 2, "COMPLETED", completed_this_week, ACCENT_GREEN)
            
            # 2. Project Overview (Dynamic Gantt Chart)
            overview_f = Frame(left_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            overview_f.pack(fill=BOTH, expand=True)
            Label(overview_f, text="PROJECT OVERVIEW", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            canvas_gantt = Canvas(overview_f, bg=CARD_BG, height=220, highlightthickness=0)
            canvas_gantt.pack(fill=BOTH, expand=True)
            
            def draw_gantt(event=None):
                canvas_gantt.delete("all")
                W = canvas_gantt.winfo_width()
                H = canvas_gantt.winfo_height()
                
                if W < 10 or H < 10:
                    # Canvas is not yet mapped or too small, draw loading state
                    canvas_gantt.create_text(10, 10, text="Drawing timeline...", font=('Segoe UI', 10), fill=MUTED_TEXT, anchor="nw")
                    return
                    
                if not project_progress_data:
                    canvas_gantt.create_text(W/2, H/2, text="No active projects assigned to your team.", 
                                             font=('Segoe UI', 11), fill=MUTED_TEXT, anchor="center")
                    return
                
                # Parse project dates
                from datetime import datetime, timedelta
                parsed_projects = []
                min_date = None
                max_date = None
                
                for pid, pname, leader, mgr, sd_str, ed_str, prog, p_status in project_progress_data:
                    try:
                        sd = datetime.strptime(sd_str.strip(), "%Y-%m-%d")
                    except:
                        sd = datetime.now()
                    try:
                        ed = datetime.strptime(ed_str.strip(), "%Y-%m-%d")
                    except:
                        ed = sd + timedelta(days=30)
                        
                    if sd > ed:
                        ed = sd + timedelta(days=30)
                        
                    parsed_projects.append({
                        'name': pname,
                        'start': sd,
                        'end': ed,
                        'prog': prog,
                        'status': p_status
                    })
                    
                    if min_date is None or sd < min_date:
                        min_date = sd
                    if max_date is None or ed > max_date:
                        max_date = ed
                        
                if min_date is None or max_date is None:
                    min_date = datetime.now() - timedelta(days=5)
                    max_date = datetime.now() + timedelta(days=25)
                    
                # Pad timeline by 3 days on both ends for visual balance
                timeline_start = min_date - timedelta(days=3)
                timeline_end = max_date + timedelta(days=3)
                total_days = (timeline_end - timeline_start).days
                if total_days <= 0: total_days = 30
                
                margin_left = 180
                margin_right = 30
                margin_top = 40
                margin_bottom = 20
                draw_width = W - margin_left - margin_right
                
                row_height = 45
                
                # Draw weekly grid lines & date headers
                step_days = max(1, int(total_days / 5))
                for i in range(0, total_days + 1, step_days):
                    grid_date = timeline_start + timedelta(days=i)
                    x = margin_left + (i / total_days) * draw_width
                    canvas_gantt.create_line(x, margin_top, x, H - margin_bottom, fill="#2a3352", dash=(2, 2))
                    date_str = grid_date.strftime("%b %d")
                    canvas_gantt.create_text(x, margin_top - 15, text=date_str, font=('Segoe UI', 8), fill="#8a99ad", anchor="n")
                    
                # Horizontal timeline separator
                canvas_gantt.create_line(margin_left, margin_top, W - margin_right, margin_top, fill="#2e3760")
                
                # Render each project bar
                for idx, p in enumerate(parsed_projects):
                    y_top = margin_top + idx * row_height + 15
                    y_bottom = y_top + 18
                    
                    # Project Label (Left-aligned)
                    label_name = p['name']
                    if len(label_name) > 22:
                        label_name = label_name[:20] + "..."
                    canvas_gantt.create_text(20, (y_top + y_bottom)/2, text=label_name, 
                                             font=('Segoe UI', 10, 'bold'), fill=TEXT_WHITE, anchor="w")
                                             
                    # Calculate horizontal positions relative to timeline dates
                    days_from_start = (p['start'] - timeline_start).days
                    duration_days = (p['end'] - p['start']).days
                    
                    bar_x1 = margin_left + (days_from_start / total_days) * draw_width
                    bar_x2 = margin_left + ((days_from_start + duration_days) / total_days) * draw_width
                    
                    # Safety clamps
                    bar_x1 = max(margin_left, min(bar_x1, W - margin_right))
                    bar_x2 = max(margin_left, min(bar_x2, W - margin_right))
                    
                    # Draw base bar background track
                    canvas_gantt.create_rectangle(bar_x1, y_top, bar_x2, y_bottom, fill="#1c223d", outline="#2e3760", width=1)
                    
                    # Draw actual progress fill
                    prog_x = bar_x1 + (p['prog'] / 100) * (bar_x2 - bar_x1)
                    if p['prog'] > 0:
                        fill_color = ACCENT_BLUE if p['status'] == 'Ongoing' else (ACCENT_RED if p['status'] == 'Delayed' else ACCENT_GREEN)
                        canvas_gantt.create_rectangle(bar_x1, y_top, prog_x, y_bottom, fill=fill_color, outline="")
                        
                    # Numeric completion indicator inside/next to the bar
                    txt_color = TEXT_WHITE if p['prog'] > 50 else MUTED_TEXT
                    anchor_pos = "e" if p['prog'] > 50 else "w"
                    text_x = prog_x - 8 if p['prog'] > 50 else prog_x + 8
                    canvas_gantt.create_text(text_x, (y_top + y_bottom)/2, text=f"{p['prog']}%", 
                                             font=('Segoe UI', 8, 'bold'), fill=txt_color, anchor=anchor_pos)
            
            canvas_gantt.bind("<Configure>", draw_gantt)
            
            # --- RIGHT COLUMN ---
            # 1. Current Sprints (Donut Chart)
            sprint_f = Frame(right_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            sprint_f.pack(fill=BOTH, expand=True, pady=(0, 20))
            
            Label(sprint_f, text="CURRENT SPRINTS", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            chart_c = Canvas(sprint_f, width=200, height=200, bg=CARD_BG, highlightthickness=0)
            chart_c.pack(pady=10)
            
            def draw_donut(event, canvas=chart_c):
                data = [active_tasks, completed_this_week, overdue_tasks]
                colors = [ACCENT_BLUE, ACCENT_GREEN, ACCENT_RED]
                
                canvas.delete("all")
                w = canvas.winfo_width()
                h = canvas.winfo_height()
                r = min(w, h) // 2 - 10
                cx, cy = w // 2, h // 2
                
                total = sum(data)
                if total == 0:
                    canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="#252d4d", outline="")
                    return
                    
                start_angle = 0
                for val, color in zip(data, colors):
                    if val == 0: continue
                    extent = (val / total) * 360
                    canvas.create_arc(cx-r, cy-r, cx+r, cy+r, start=start_angle, extent=extent, fill=color, outline="")
                    start_angle += extent
                    
                # Draw hole
                r_hole = r * 0.6
                canvas.create_oval(cx-r_hole, cy-r_hole, cx+r_hole, cy+r_hole, fill=CARD_BG, outline="")
                
                # Draw text in center
                canvas.create_text(cx, cy, text=f"{total}\nTasks", fill=TEXT_WHITE, font=('Segoe UI', 12, 'bold'), justify=CENTER)
                
            chart_c.bind("<Configure>", draw_donut)


            # 3. Dynamic Queries & Support (Modernized)
            q_sec = Frame(parent, bg=CONTENT_BG)
            q_sec.pack(fill=X, padx=30, pady=(10, 20))
            
            left_col = Frame(q_sec, bg=CONTENT_BG)
            left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
            
            Label(left_col, text="Support Intelligence", font=('Segoe UI', 15, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            q_container = Frame(left_col, bg=CARD_BG, padx=2, pady=2, highlightbackground=BORDER_COLOR, highlightthickness=1)
            q_container.pack(fill=BOTH, expand=True)
            
            cursor.execute("""
                SELECT q.id, q.user_name, IFNULL(p.name, 'General'), q.subject, q.created_at 
                FROM queries q
                LEFT JOIN projects p ON q.project_id = p.id
                WHERE (q.tl_name=? OR q.tl_name IS NULL) AND q.status='Open'
                ORDER BY q.created_at DESC LIMIT 5
            """, (CURRENT_USER_NAME,))
            queries = cursor.fetchall()
            
            if not queries:
                Label(q_container, text="All team support requests resolved.", font=('Segoe UI', 11), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for qid, uname, pname, subj, date in queries:
                    q_row = Frame(q_container, bg=CARD_BG, padx=20, pady=15)
                    q_row.pack(fill=X)
                    Frame(q_container, bg=BORDER_COLOR, height=1).pack(fill=X)
                    
                    info = Frame(q_row, bg=CARD_BG)
                    info.pack(side=LEFT, fill=X, expand=True)
                    Label(info, text=subj, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(info, text=f"{uname} • {pname}", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(2, 0))
                    
                    btn = Button(q_row, text="RESPOND", font=('Segoe UI', 7, 'bold'), bg="#2a3352", fg=ACCENT_BLUE,
                                 relief=FLAT, padx=12, pady=6, command=lambda: self.switch_page('team_queries'))
                    btn.pack(side=RIGHT)

            # 4. Global Activity Stream (Modernized)
            right_col = Frame(q_sec, bg=CONTENT_BG, width=350)
            right_col.pack(side=RIGHT, fill=Y)
            right_col.pack_propagate(False)
            
            Label(right_col, text="Team Pulse", font=('Segoe UI', 15, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            act_box = Frame(right_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            act_box.pack(fill=BOTH, expand=True)
            
            cursor.execute(f"""
                SELECT timestamp, user_name, action FROM activity_timeline 
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                ORDER BY id DESC LIMIT 6
            """, (f"%{CURRENT_USER_NAME}%",))
            activities = cursor.fetchall()
            
            if not activities:
                Label(act_box, text="No recent pulse data.", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(expand=True)
            else:
                for ts, user, action in activities:
                    item = Frame(act_box, bg=CARD_BG, pady=8)
                    item.pack(fill=X)
                    Label(item, text=user.split()[0], font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W)
                    Label(item, text=action, font=('Segoe UI', 8), bg=CARD_BG, fg=TEXT_WHITE, wraplength=280, justify=LEFT).pack(anchor=W)
                    Label(item, text=ts, font=('Segoe UI', 7), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=E)
                    Frame(act_box, bg=BORDER_COLOR, height=1).pack(fill=X, pady=4)

        else:
            # --- Executive View (Admin / PM) ---
            self.create_stat_card_executive(stats_frame, "TOTAL PROJECTS", str(total_projects), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "TOTAL EMPLOYEES", str(total_employees), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "TEAM LEADERS", str(total_tls), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "ACTIVE PROJECTS", str(active_projects), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "DELAYED PROJECTS", str(delayed_projects), ACCENT_RED).pack(side=LEFT, fill=X, expand=True)

            # 2x2 Grid Container
            grid_container = Frame(parent, bg=CONTENT_BG)
            grid_container.pack(fill=X, padx=30, pady=20)
            
            # LEFT TOP: Project Health
            left_top = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
            left_top.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
            Label(left_top, text="Active Project Health", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            if not project_progress_data:
                Label(left_top, text="No active projects.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
            else:
                for pid, pname, leader, mgr, end_date, prog, status in project_progress_data[:4]:
                    p_row = Frame(left_top, bg=CARD_BG)
                    p_row.pack(fill=X, pady=6)
                    head = Frame(p_row, bg=CARD_BG)
                    head.pack(fill=X)
                    Label(head, text=pname, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    Label(head, text=f"{prog}%", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(side=RIGHT)
                    bar_bg = Frame(p_row, bg="#1a2035", height=6)
                    bar_bg.pack(fill=X, pady=(4, 0))
                    if prog > 0: Frame(bar_bg, bg=ACCENT_BLUE, height=6).place(x=0, y=0, relwidth=prog/100)
            
            # RIGHT TOP: Task Distribution
            right_top = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
            right_top.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
            Label(right_top, text="Task Distribution", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            statuses = ["Pending", "In Progress", "Completed", "Delayed"]
            colors = [ACCENT_ORANGE, "#3b82f6", ACCENT_GREEN, ACCENT_RED]
            max_val = sum(task_dist.values()) if task_dist else 1
            
            for i, s in enumerate(statuses):
                count = task_dist.get(s, 0)
                pct = count / max_val if max_val > 0 else 0
                row = Frame(right_top, bg=CARD_BG)
                row.pack(fill=X, pady=8)
                Label(row, text=s, width=12, anchor=W, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(side=LEFT)
                bar_c = Frame(row, bg="#1a2035", height=10)
                bar_c.pack(side=LEFT, fill=X, expand=True, padx=10)
                if count > 0: Frame(bar_c, bg=colors[i], height=10).place(x=0, y=0, relwidth=pct)
                Label(row, text=str(count), width=3, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(side=RIGHT)

            # LEFT BOTTOM: Critical Deadlines
            left_bot = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
            left_bot.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
            Label(left_bot, text="Critical Deadlines", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            if not upcoming:
                Label(left_bot, text="No immediate deadlines.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
            else:
                for task_title, due in upcoming[:5]:
                    row = Frame(left_bot, bg=CARD_BG)
                    row.pack(fill=X, pady=4)
                    Label(row, text=f"- {task_title}", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(side=LEFT)
                    Label(row, text=due, bg=CARD_BG, fg=ACCENT_RED, font=('Segoe UI', 9, 'bold')).pack(side=RIGHT)

            # RIGHT BOTTOM: Recent Audit Logs
            right_bot = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
            right_bot.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))
            Label(right_bot, text="Recent Audit Logs", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            if not recent_activity:
                Label(right_bot, text="No recent activity logged.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
            else:
                for user, action, dt in recent_activity:
                    row = Frame(right_bot, bg=CARD_BG)
                    row.pack(fill=X, pady=4)
                    Label(row, text=user, bg=CARD_BG, fg=ACCENT_BLUE, font=('Segoe UI', 10, 'bold'), width=12, anchor=W).pack(side=LEFT)
                    Label(row, text=action, bg=CARD_BG, fg=TEXT_SECONDARY, font=('Segoe UI', 10), wraplength=150, justify=LEFT).pack(side=LEFT, padx=5)
                    Label(row, text=str(dt), bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=RIGHT)
            
            grid_container.grid_columnconfigure(0, weight=1)
            grid_container.grid_columnconfigure(1, weight=1)

        con.close()
        try:
            if is_tl and self.current_page == 'dashboard':
                self.schedule_pm_dashboard_auto_refresh()
        except:
            pass

    def open_quick_task_update(self, task_title, project_name):
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            cursor.execute(f"""
                SELECT t.id FROM tasks t 
                JOIN projects p ON t.project_id = p.id 
                WHERE t.title=? AND p.name=?
            """, (task_title, project_name))
            row = cursor.fetchone()
            con.close()
            
            if row:
                self.update_task_modal(row[0])
            else:
                messagebox.showerror("Error", "Task not found")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open task: {e}")

    def load_pm_dashboard(self):
        # Stop any existing refresh timers for other pages
        if hasattr(self, '_auto_refresh_timer') and self._auto_refresh_timer:
            self.root.after_cancel(self._auto_refresh_timer)
            self._auto_refresh_timer = None
            
        # Clear content
        for widget in self.content_area.winfo_children():
            widget.destroy()

        # Schedule next refresh (every 30 seconds to avoid performance lag)
        self._auto_refresh_timer = self.root.after(30000, self.load_pm_dashboard)

        role = CURRENT_USER_ROLE.lower()

        # Database Connection
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()

            # --- Data Fetching ---
            # 1. Total Projects
            cursor.execute("SELECT COUNT(*) FROM projects")
            total_projects = cursor.fetchone()[0]

            # 2. Team Leaders (count all Team Leaders in system, not only those assigned on projects)
            cursor.execute("""
                SELECT COUNT(DISTINCT TRIM(name))
                FROM employee
                WHERE name IS NOT NULL
                  AND TRIM(name) != ''
                  AND lower(COALESCE(role, '')) = 'team leader'
            """)
            total_tls = cursor.fetchone()[0] or 0

            # 2.1 Total Employees (Total count of all staff members)
            cursor.execute("SELECT COUNT(*) FROM employee")
            total_employees = cursor.fetchone()[0] or 0

            # 3. Active Projects
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Ongoing'")
            active_projects = cursor.fetchone()[0]

            # 4. Delayed Projects
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Delayed'")
            delayed_projects = cursor.fetchone()[0]
            # --- Data Fetching ---
            
            # 4.1 Total Delayed Tasks (for Summary)
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE status='Delayed'")
            total_delayed_tasks = cursor.fetchone()[0]

            # 5. All Projects List (No Limit) with progress
            cursor.execute("SELECT id, name, team_leader, manager, end_date, status FROM projects ORDER BY start_date DESC")
            all_projs_rows = cursor.fetchall()
            project_progress_data = []
            for pid, pname, leader, mgr, end_date, status in all_projs_rows:
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
                tot = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
                done = cursor.fetchone()[0]
                prog = int((done/tot)*100) if tot > 0 else 0
                project_progress_data.append((pid, pname, leader, mgr, end_date, prog, status))

            # 6. Project Status Overview Counts
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Completed'")
            completed_projects = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Ongoing'")
            ongoing_projects = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM projects WHERE status='Not Started'")
            not_started_projects = cursor.fetchone()[0]

            # 7. Upcoming Deadlines (Top 5, excluding completed projects)
            cursor.execute("""
                SELECT name, end_date
                FROM projects
                WHERE status != 'Completed'
                  AND end_date IS NOT NULL
                  AND TRIM(end_date) != ''
                ORDER BY date(end_date) ASC
                LIMIT 5
            """)
            upcoming_deadlines = cursor.fetchall()

            # 8. Recent Activity (latest project/task timeline events)
            recent_activity = []
            try:
                cursor.execute("""
                    SELECT timestamp, user_name, action
                    FROM activity_timeline
                    ORDER BY id DESC
                    LIMIT 5
                """)
                for ts, user_name, action in cursor.fetchall():
                    recent_activity.append((ts, user_name, action))
            except:
                pass
            
            
            con.close()
        except Exception as e:
            print(f"Error loading PM dashboard data: {e}")
            total_projects = 0
            total_tls = 0
            total_employees = 0
            active_projects = 0
            delayed_projects = 0
            total_delayed_tasks = 0
            project_progress_data = []
            completed_projects = 0
            ongoing_projects = 0
            not_started_projects = 0
            upcoming_deadlines = []
            recent_activity = []


        # --- UI Building ---
        
        # 1. Sticky Header
        h_frame = Frame(self.content_area, bg=CONTENT_BG)
        h_frame.pack(fill=X, padx=30, pady=(30, 10))
        
        # Title & Summary
        title_box = Frame(h_frame, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        
        Label(title_box, text="Project Manager Dashboard", font=('Segoe UI', 24, 'bold'), 
              bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        # Removed redundant explanatory text and summary line to simplify the interface
              
        # Date & PIN Display
        right_header = Frame(h_frame, bg=CONTENT_BG)
        right_header.pack(side=RIGHT)

        # Export Button
        export_btn = Button(right_header, text="Export Performance CSV", 
                           command=self.export_employee_performance_csv,
                           bg=ACCENT_ORANGE, fg='white', font=('Segoe UI', 10, 'bold'),
                           activebackground=ACCENT_HOVER, activeforeground='white',
                           bd=0, padx=15, pady=5, cursor="hand2")
        export_btn.pack(side=LEFT, padx=(0, 20), anchor="center")

        today_date = datetime.now().strftime("%B %d, %Y")
        Label(right_header, text=f"Today: {today_date}", font=('Segoe UI', 12), 
              bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=E)


        # 2. Scrollable Content
        # Scrollable Wrapper
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def on_canvas_configure(event):
            canvas.itemconfig(frame_id, width=event.width)
        canvas.bind("<Configure>", on_canvas_configure)
        self._bind_canvas_scrolling(wrapper, canvas, allow_horizontal=True)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        parent = scrollable_frame

        # KPI Cards Row
        stats_frame = Frame(parent, bg=CONTENT_BG)
        stats_frame.pack(fill=X, padx=30, pady=10)
        
        # Helper to create enhanced KPI stat cards
        _CARD_ICONS = {
            "Total Projects": "📁",
            "Active Projects": "⚡",
            "Delayed Projects": "⚠️",
            "Team Leaders": "👑",
            "Total Employees": "👥",
            "Completed": "✅",
        }

        def create_pm_card(parent_frame, title, value, color, command=None, tooltip_text=None):
            card = Frame(
                parent_frame,
                bg=CARD_BG,
                padx=18,
                pady=14,
                highlightbackground="#2e3760",
                highlightthickness=1,
                cursor="hand2" if command else "arrow",
            )

            # Apply the global hover/click effect (requested by user)
            self._apply_hover_effect(card, color)

            # Icon + Title row
            top = Frame(card, bg=CARD_BG)
            top.pack(fill=X)

            icon_txt = _CARD_ICONS.get(title, "📊")
            
            # Icon Box (Colored Background) - Fixed square to match reference image
            icon_frame = Frame(top, bg=color, width=28, height=28)
            icon_frame.pack(side=LEFT)
            icon_frame.pack_propagate(False)
            icon_frame._is_badge = True # Preserve bg in hover
            
            icon_lbl = Label(icon_frame, text=icon_txt, font=('Segoe UI Emoji', 12),
                             bg=color, fg=WHITE)
            icon_lbl.pack(expand=True)
            icon_lbl._is_badge = True

            l_title = Label(top, text=title.upper(), font=('Segoe UI', 9, 'bold'),
                            bg=CARD_BG, fg=TEXT_SECONDARY, padx=8)
            l_title.pack(side=LEFT, pady=(2, 0))

            # Big value
            l_val = Label(card, text=value, font=('Segoe UI', 30, 'bold'),
                          bg=CARD_BG, fg=TEXT_WHITE)
            l_val.pack(anchor=W, pady=(6, 0))

            if command:
                card.bind("<Button-1>", lambda e: command(), "+")
                for w in [top, icon_lbl, l_title, l_val]:
                    w.bind("<Button-1>", lambda e: command(), "+")

            if tooltip_text:
                CreateToolTip(card, tooltip_text)
                CreateToolTip(l_title, tooltip_text)
                CreateToolTip(l_val, tooltip_text)

            return card

        # Card 1: Total Projects
        c1 = create_pm_card(stats_frame, "Total Projects", str(total_projects), ACCENT_BLUE, 
                            lambda: self.switch_page('projects'), "Total number of projects in the system.")
        c1.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        
        # Note: Staff cards (Employees/Team Leaders) removed to simplify PM focus and avoid redundant links
        
        # Card 2: Active Projects
        c3 = create_pm_card(stats_frame, "Active Projects", str(active_projects), ACCENT_GREEN,
                            lambda: self.switch_page('projects'), "Projects currently in progress.")
        c3.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        
        # Card 3: Delayed Projects
        c4 = create_pm_card(stats_frame, "Delayed Projects", str(delayed_projects), ACCENT_RED,
                            lambda: self.switch_page('projects'), "Projects that are past their due date.")
        c4.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))

        # Main Content Grid
        grid_frame = Frame(parent, bg=CONTENT_BG)
        grid_frame.pack(fill=BOTH, expand=True, padx=30, pady=30)
        
        # Left Column: Active Projects Detail
        left_col = Frame(grid_frame, bg=CARD_BG, padx=20, pady=20)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        
        # Section header with separator line
        lh = Frame(left_col, bg=CARD_BG)
        lh.pack(fill=X, pady=(0, 8))
        Label(lh, text="📂  Company Projects", font=('Segoe UI', 14, 'bold'),
              bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Frame(left_col, bg=BORDER_NAVY, height=1).pack(fill=X, pady=(0, 12))
        
        if not project_progress_data:
            Label(left_col, text="No projects found.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        else:
            for pid, pname, leader, mgr, end_date, prog, status in project_progress_data:
                # Status color map
                _s_bg     = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_ORANGE,
                              "Delayed": ACCENT_RED, "Not Started": MUTED_TEXT}.get(status, MUTED_TEXT)
                _s_stripe = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_BLUE,
                             "Delayed": ACCENT_RED, "Not Started": "#555e7a"}.get(status, MUTED_TEXT)
                _bar_col  = (ACCENT_GREEN if prog >= 75 else
                             ACCENT_ORANGE if prog >= 40 else ACCENT_RED)
                if status == "Completed": _bar_col = ACCENT_GREEN

                # Left colored stripe wrapper
                row_wrap = Frame(left_col, bg=_s_stripe, pady=0)
                row_wrap.pack(fill=X, pady=3)

                p_item = Frame(row_wrap, bg=CARD_BG, padx=16, pady=10, cursor="hand2")
                p_item.pack(fill=BOTH, expand=True, padx=(4, 0))
                self._apply_hover_effect(p_item, _bar_col)

                def open_proj(p=pid, n=pname):
                    self.show_project_tasks_modal(p, n)

                # Info Row
                info = Frame(p_item, bg=CARD_BG)
                info.pack(fill=X)

                l1 = Label(info, text=pname, font=('Segoe UI', 11, 'bold'),
                           bg=CARD_BG, fg=TEXT_WHITE)
                l1.pack(side=LEFT)

                # Pill-style status badge
                badge_frame = Frame(info, bg=_s_bg, padx=7, pady=2)
                badge_frame._is_badge = True
                badge_frame.pack(side=LEFT, padx=8)
                Label(badge_frame, text=status, font=('Segoe UI', 8, 'bold'),
                      bg=_s_bg, fg=WHITE).pack()

                l2 = Label(info, text=f"{prog}%", font=('Segoe UI', 11, 'bold'),
                           bg=CARD_BG, fg=_bar_col)
                l2.pack(side=RIGHT)

                # Sub-info
                sub = Frame(p_item, bg=CARD_BG)
                sub.pack(fill=X, pady=(3, 6))
                leader_txt = leader if leader else (mgr if mgr else "No Leader")
                l3 = Label(sub, text=f"Lead: {leader_txt}  \u00b7  Due: {end_date or chr(8212)}",
                           font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT)
                l3.pack(side=LEFT)
                if prog == 0 and status != "Completed":
                    Label(sub, text="  No tasks yet", font=('Segoe UI', 9, 'italic'),
                          bg=CARD_BG, fg=ACCENT_ORANGE).pack(side=LEFT)

                # Sleek thin progress bar
                bar_track = Frame(p_item, bg="#2a3352", height=5)
                bar_track.pack(fill=X)
                if prog > 0:
                    bar_fill = Frame(bar_track, bg=_bar_col, height=5)
                    bar_fill.place(x=0, y=0, relwidth=min(prog / 100, 1.0))
                    bar_fill.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))

                for w in [row_wrap, p_item, info, l1, badge_frame, l2, sub, l3, bar_track]:
                    w.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))


        # Right Column: Progress Overview + Quick Actions
        right_col = Frame(grid_frame, bg=CONTENT_BG) # Container for right side widgets
        right_col.pack(side=RIGHT, fill=BOTH, expand=True)

        # Widget 1: Project Progress Overview
        overview_box = Frame(right_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=ACCENT_BLUE, highlightthickness=1)
        overview_box.pack(fill=X, pady=(0, 20))

        Label(overview_box, text="Project Progress Overview", font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 12))

        counts_frame = Frame(overview_box, bg=CARD_BG)
        counts_frame.pack(fill=X, pady=(0, 10))
        Label(counts_frame, text=f"Completed Projects: {completed_projects}", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W)
        Label(counts_frame, text=f"Ongoing Projects: {ongoing_projects}", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=2)
        Label(counts_frame, text=f"Not Started Projects: {not_started_projects}", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_ORANGE).pack(anchor=W)

        Label(overview_box, text="Project Distribution", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(4, 6))
        # Simple bar chart for project status distribution
        chart_frame = Frame(overview_box, bg=CARD_BG)
        chart_frame.pack(fill=X, pady=(5, 10))
        chart_canvas = Canvas(chart_frame, bg=CARD_BG, height=110, highlightthickness=0)
        chart_canvas.pack(fill=X, expand=True)

        chart_data = [
            ("Completed", completed_projects, ACCENT_GREEN),
            ("Ongoing", ongoing_projects, ACCENT_BLUE),
            ("Not Started", not_started_projects, ACCENT_ORANGE),
        ]
        max_val = max([v for _, v, _ in chart_data] + [1])
        chart_width = 300
        bar_height = 18
        gap = 14
        left = 110
        top = 8

        for i, (label_txt, value, color) in enumerate(chart_data):
            y = top + i * (bar_height + gap)
            bar_w = int((value / max_val) * chart_width) if max_val > 0 else 0
            chart_canvas.create_text(8, y + bar_height / 2, text=label_txt, fill=MUTED_TEXT, font=('Segoe UI', 9), anchor='w')
            chart_canvas.create_rectangle(left, y, left + chart_width, y + bar_height, fill="#3d3c3f", outline="")
            chart_canvas.create_rectangle(left, y, left + bar_w, y + bar_height, fill=color, outline="")
            chart_canvas.create_text(left + chart_width + 8, y + bar_height / 2, text=str(value), fill=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), anchor='w')

        Label(overview_box, text="Upcoming Deadlines", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(8, 8))

        def fmt_deadline(d):
            try:
                return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")
            except:
                return d

        if not upcoming_deadlines:
            Label(overview_box, text="- No upcoming deadlines", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        else:
            for proj_name, end_date in upcoming_deadlines:
                Label(overview_box, text=f"- {proj_name} - {fmt_deadline(end_date)}", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=1)

        # Widget 2: Recent Activity
        activity_box = Frame(right_col, bg=CARD_BG, padx=20, pady=20,
                              highlightbackground=BORDER_NAVY, highlightthickness=1)
        activity_box.pack(fill=X, pady=(0, 20))

        # Section header with separator
        act_hdr = Frame(activity_box, bg=CARD_BG)
        act_hdr.pack(fill=X, pady=(0, 8))
        Label(act_hdr, text="⚡  Recent Activity", font=('Segoe UI', 13, 'bold'),
              bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Frame(activity_box, bg=BORDER_NAVY, height=1).pack(fill=X, pady=(0, 10))

        dot_colors = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_ORANGE, ACCENT_PURPLE, ACCENT_RED]
        if not recent_activity:
            Label(activity_box, text="No recent activity yet.", font=('Segoe UI', 10),
                  bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        else:
            for idx, (ts, user_name, action) in enumerate(recent_activity):
                row = Frame(activity_box, bg=CARD_BG)
                row.pack(fill=X, pady=3)
                # Colored dot
                dot_c = dot_colors[idx % len(dot_colors)]
                dot = Frame(row, bg=dot_c, width=8, height=8)
                dot.pack(side=LEFT, padx=(0, 8))
                dot.pack_propagate(False)
                # Text
                short_ts = (ts or "")[:16]
                Label(row, text=f"{user_name}: {action}",
                      font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                Label(row, text=short_ts, font=('Segoe UI', 8),
                      bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        self.schedule_pm_dashboard_auto_refresh()

    def create_stat_card(self, parent, title, value, color, icon="", on_click=None):
        card = Frame(parent, bg=CARD_BG, padx=20, pady=20, width=1, height=120, highlightbackground="#3b4557", highlightthickness=1, cursor=("hand2" if on_click else "arrow"))
        card.pack_propagate(False) 
        def _enter(e): 
            try: card.config(bg="#2f3d55")
            except: pass
        def _leave(e): 
            try: card.config(bg=CARD_BG)
            except: pass
        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        
        header = Frame(card, bg=CARD_BG)
        header.pack(fill=X)
        title_label = Label(header, text=title.upper(), font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg="#a0aec0")
        title_label.pack(side=LEFT)
        
        value_label = Label(card, text=value, font=('Syne', 28, 'bold'), bg=CARD_BG, fg=TEXT_WHITE)
        value_label.pack(anchor=W, pady=(10, 0))
        # Bottom color bar (60% base width, or % if numeric value <= 100)
        try:
            v_num = int(str(value).split()[0])
        except:
            try:
                v_num = int(float(str(value).replace('%','')))
            except:
                v_num = None
        bar_bg = Frame(card, bg="#3a475a", height=4)
        bar_bg.pack(fill=X, pady=(12,0))
        width_pct = 0.6
        if v_num is not None and 0 <= v_num <= 100:
            width_pct = max(0.15, min(v_num/100.0, 1.0))
        bar_fill = Frame(bar_bg, bg=color, height=4)
        bar_fill.place(x=0, y=0, relwidth=width_pct)
        if on_click:
            click_widgets = [card, header, title_label, value_label, bar_bg, bar_fill]
            for widget in click_widgets:
                widget.bind("<Button-1>", lambda e: on_click())
        return card

    def create_stat_card_executive(self, parent, title, value, color, on_click=None):
        card = Frame(
            parent,
            bg="#212840",
            padx=20,
            pady=18,
            highlightbackground="#2e3760",
            highlightthickness=1,
            cursor=("hand2" if on_click else "arrow"),
        )
        card.pack_propagate(False)
        card.configure(height=140)

        # Icon mapping based on title
        icons = {
            "TOTAL PROJECTS": "📁",
            "TOTAL EMPLOYEES": "👥",
            "TEAM LEADERS": "👑",
            "ACTIVE PROJECTS": "⚡",
            "DELAYED PROJECTS": "⚠️"
        }
        icon_char = icons.get(title.upper(), "📊")

        # Top Row: Icon and Title
        top_row = Frame(card, bg="#212840")
        top_row.pack(fill=X, anchor=W)

        # Icon Box (Colored Background)
        icon_frame = Frame(top_row, bg=color, width=32, height=32)
        icon_frame.pack(side=LEFT, padx=(0, 10))
        icon_frame.pack_propagate(False)
        
        # Center the icon in the box
        icon_lbl = Label(
            icon_frame,
            text=icon_char,
            font=('Segoe UI Emoji', 14),
            bg=color,
            fg="white"
        )
        icon_lbl.pack(expand=True)

        # Title
        title_lbl = Label(
            top_row,
            text=title.upper(),
            font=('Segoe UI', 9, 'bold'),
            bg="#212840",
            fg="#9aa3c2",
        )
        title_lbl.pack(side=LEFT, anchor=CENTER)

        # Main Value
        val_lbl = Label(
            card,
            text=value,
            font=('Segoe UI', 32, 'bold'),
            bg="#212840",
            fg="white", # White text for value looks more premium as requested or keep it colorful
        )
        val_lbl.pack(anchor=W, pady=(15, 0)) # Align to left like in the image

        if on_click:
            for w in [card, val_lbl, top_row, icon_frame, icon_lbl, title_lbl]:
                w.bind("<Button-1>", lambda e: on_click())
        return card

    def create_stat_card_modern(self, parent, title, value, accent_color, subtitle="", icon="📊", on_click=None):
        card = Frame(
            parent,
            bg=CARD_BG,
            padx=20,
            pady=18,
            highlightbackground=BORDER_COLOR,
            highlightthickness=1,
            cursor=("hand2" if on_click else "arrow"),
        )
        card.pack_propagate(False)

        def on_enter(e):
            card.config(highlightbackground=accent_color)
        def on_leave(e):
            card.config(highlightbackground=BORDER_COLOR)
        
        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        top_row = Frame(card, bg=CARD_BG)
        top_row.pack(fill=X)

        Label(
            top_row,
            text=icon,
            font=('Segoe UI', 14),
            bg=CARD_BG,
            fg=accent_color,
        ).pack(side=RIGHT)

        Label(
            top_row,
            text=title.upper(),
            font=('Segoe UI', 9, 'bold'),
            bg=CARD_BG,
            fg=TEXT_SECONDARY,
        ).pack(side=LEFT, anchor=W)

        value_row = Frame(card, bg=CARD_BG)
        value_row.pack(fill=X, pady=(15, 10))

        Label(
            value_row,
            text=value,
            font=('Segoe UI', 24, 'bold'),
            bg=CARD_BG,
            fg=TEXT_WHITE,
        ).pack(side=LEFT, anchor=W)

        if subtitle:
            Label(
                card,
                text=subtitle,
                font=('Segoe UI', 10),
                bg=CARD_BG,
                fg=accent_color,
            ).pack(anchor=W)

        bar_base = Frame(card, bg=CONTENT_BG, height=4)
        bar_base.pack(fill=X, pady=(18, 0))

        try:
            numeric_value = float(str(value).replace("%", "").strip())
        except Exception:
            numeric_value = None

        width_pct = 0.45
        if numeric_value is not None and 0 <= numeric_value <= 100:
            width_pct = max(0.18, min(numeric_value / 100.0, 1.0))

        Frame(bar_base, bg=accent_color, height=4).place(x=0, y=0, relwidth=width_pct)
        
        # Bind children to card click if provided
        if on_click:
            for widget in card.winfo_children():
                widget.bind("<Button-1>", lambda e: on_click())
            card.bind("<Button-1>", lambda e: on_click())

        return card

        def _apply_hover(is_hovered):
            bg_color = HOVER_BG if is_hovered else CARD_BG
            try:
                card.config(bg=bg_color)
                top_row.config(bg=bg_color)
                value_row.config(bg=bg_color)
                for w in card.winfo_children():
                    if isinstance(w, Label): w.config(bg=bg_color)
            except: pass

        card.bind("<Enter>", lambda e: _apply_hover(True))
        card.bind("<Leave>", lambda e: _apply_hover(False))

        if on_click:
            card.bind("<Button-1>", lambda e: on_click())
            for w in card.winfo_children():
                w.bind("<Button-1>", lambda e: on_click())
        
        return card

    def populate_demo_for_tl(self):
        try:
            tl = CURRENT_USER_NAME
            today = datetime.now()
            sd = (today - timedelta(days=7)).strftime("%Y-%m-%d")
            ed = (today + timedelta(days=14)).strftime("%Y-%m-%d")
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT id FROM projects WHERE name LIKE '[DEMO] %' AND lower(COALESCE(team_leader,'')) LIKE lower(?) LIMIT 1", (f"%{tl}%",))
            row = cur.fetchone()
            if row:
                pid = row[0]
            else:
                cur.execute("INSERT INTO projects (name, description, start_date, end_date, status, manager, team_leader) VALUES (?,?,?,?,?,?,?)",
                            ("[DEMO] Team Sprint", "Demo data for screenshots", sd, ed, "Ongoing", tl, tl))
                pid = cur.lastrowid
            cur.execute("SELECT name FROM employee WHERE (role='Team Member' OR role='Senior Employee') AND lower(COALESCE(reporting_manager,'')) LIKE lower(?)", (f"%{tl}%",))
            members = [r[0] for r in cur.fetchall()]
            if not members:
                cur.execute("SELECT name FROM employee WHERE role IN ('Team Member','Senior Employee') AND name!=? LIMIT 5", (tl,))
                members = [r[0] for r in cur.fetchall()]
            for m in members:
                d1 = (today + timedelta(days=3)).strftime("%Y-%m-%d")
                d2 = (today - timedelta(days=5)).strftime("%Y-%m-%d")
                d3 = (today - timedelta(days=2)).strftime("%Y-%m-%d")
                cr = (today - timedelta(days=9)).strftime("%Y-%m-%d")
                cur.execute("INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date, created_date) VALUES (?,?,?,?,?,?,?,?)",
                            (f"[DEMO] {m} Feature", "Demo", pid, m, "In Progress", "Medium", d1, cr))
                cur.execute("INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date, created_date) VALUES (?,?,?,?,?,?,?,?)",
                            (f"[DEMO] {m} Fix", "Demo", pid, m, "Delayed", "High", d2, cr))
                cur.execute("INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date, completed_date, created_date) VALUES (?,?,?,?,?,?,?,?,?)",
                            (f"[DEMO] {m} Review", "Demo", pid, m, "Completed", "Low", d3, d3, cr))
            cur.execute("INSERT INTO queries (user_name, tl_name, project_id, subject, message, status) VALUES (?,?,?,?,?,?)",
                        ("Dev Patel", tl, pid, "[DEMO] Need API access", "Please provide token", "Open"))
            cur.execute("INSERT INTO queries (user_name, tl_name, project_id, subject, message, status) VALUES (?,?,?,?,?,?)",
                        ("Ayush Patel", tl, pid, "[DEMO] Deadline clarification", "Is it EOD Friday?", "Open"))
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cur.execute("INSERT INTO activity_timeline (project_id, user_name, action, timestamp) VALUES (?,?,?,?)",
                        (pid, tl, "[DEMO] Sprint created", ts))
            con.commit(); self.refresh_current_panel()
            con.close()
            # Refresh cleanly through router
            self.switch_page('dashboard')
        except:
            try:
                con.close()
            except:
                pass

    def clear_demo_for_tl(self):
        try:
            tl = CURRENT_USER_NAME
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT id FROM projects WHERE name LIKE '[DEMO] %' AND lower(COALESCE(team_leader,'')) LIKE lower(?)", (f"%{tl}%",))
            pids = [r[0] for r in cur.fetchall()]
            cur.execute("DELETE FROM tasks WHERE title LIKE '[DEMO] %'")
            if pids:
                q = ",".join("?" for _ in pids)
                cur.execute(f"DELETE FROM activity_timeline WHERE project_id IN ({q}) AND action LIKE '[DEMO] %'", pids)
                cur.execute(f"DELETE FROM tasks WHERE project_id IN ({q})", pids)
                cur.execute(f"DELETE FROM projects WHERE id IN ({q})", pids)
            cur.execute("DELETE FROM queries WHERE subject LIKE '[DEMO] %' AND lower(COALESCE(tl_name,'')) LIKE lower(?)", (f"%{tl}%",))
            con.commit(); self.refresh_current_panel()
            con.close()
            # Refresh cleanly through router
            self.switch_page('dashboard')
        except:
            try:
                con.close()
            except:
                pass


    def build_emp_leave_requests(self, parent):
        header = Frame(parent, bg=CONTENT_BG)
        header.pack(fill=X, pady=(0, 20))
        Label(header, text="My Leave Requests", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        def apply_leave():
            d = Toplevel(self.root)
            d.title("Apply for Leave")
            d.geometry("400x450")
            d.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
            d.resizable(True, True)  # FIX 7: allow resize so no overflow
            d.config(bg=CARD_BG)
            
            Label(d, text="Start Date (YYYY-MM-DD):", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(pady=(20, 5))
            e_start = Entry(d, font=('Segoe UI', 11), bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT); e_start.pack(pady=5, padx=20, fill=X, ipady=3)
            Label(d, text="End Date (YYYY-MM-DD):", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(pady=5)
            e_end = Entry(d, font=('Segoe UI', 11), bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT); e_end.pack(pady=5, padx=20, fill=X, ipady=3)
            Label(d, text="Reason:", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(pady=5)
            e_reason = Entry(d, font=('Segoe UI', 11), bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT); e_reason.pack(pady=5, padx=20, fill=X, ipady=3)
            
            def submit():
                if e_start.get() and e_end.get() and e_reason.get():
                    c = sqlite3.connect(get_db_path())
                    cu = c.cursor()
                    cu.execute("INSERT INTO leave_requests (member_name, start_date, end_date, reason) VALUES (?, ?, ?, ?)",
                              (CURRENT_USER_NAME, e_start.get(), e_end.get(), e_reason.get()))
                    c.commit(); self.refresh_current_panel(); c.close()
                    d.destroy()
                    self.load_employee_panel() # Refresh the whole panel
            
            Button(d, text="Submit Request", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT, command=submit).pack(pady=30, padx=20, fill=X)

        Button(header, text="+ Apply Leave", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT, command=apply_leave).pack(side=RIGHT)
        
        # List existing requests
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT start_date, end_date, reason, status FROM leave_requests WHERE member_name=? ORDER BY id DESC", (CURRENT_USER_NAME,))
            rows = cur.fetchall()
            if not rows:
                Label(parent, text="No leave requests found.", font=('Segoe UI', 11), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for start, end, reason, status in rows:
                    card = Frame(parent, bg=CARD_BG, padx=15, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=5)
                    Label(card, text=f"{start} to {end}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(card, text=reason, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=2)
                    color = ACCENT_ORANGE if status == 'Pending' else (ACCENT_GREEN if status == 'Approved' else ACCENT_RED)
                    Label(card, text=status, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=color).pack(anchor=E)
            con.close()
        except:
            pass



    def build_emp_attendance(self, parent):
        # Header
        h_frame = Frame(parent, bg=CONTENT_BG)
        h_frame.pack(fill=X, pady=20)
        
        Label(h_frame, text="Attendance Tracking", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Clock Section
        clock_frame = Frame(parent, bg=CARD_BG, padx=20, pady=20)
        clock_frame.pack(fill=X, pady=(0, 20))
        
        # Detect attendance name column (supports legacy 'name' and new 'employee_name')
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("PRAGMA table_info(attendance)")
        att_cols = [r[1] for r in cur.fetchall()]
        att_name_col = "employee_name" if "employee_name" in att_cols else "name"
        con.close()
        
        status_var = StringVar(value="Not Clocked In")
        
        def update_status():
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute(f"SELECT status, clock_in, clock_out FROM attendance WHERE {att_name_col}=? AND date=?", (CURRENT_USER_NAME, today))
            row = cur.fetchone()
            if row:
                if row[2]: # Clock out exists
                    status_var.set(f"Completed for today (In: {row[1]}, Out: {row[2]})")
                    btn_in.config(state=DISABLED)
                    btn_out.config(state=DISABLED)
                else:
                    status_var.set(f"Clocked In at: {row[1]}")
                    btn_in.config(state=DISABLED)
                    btn_out.config(state=NORMAL)
            else:
                status_var.set("Ready to Clock In")
                btn_in.config(state=NORMAL)
                btn_out.config(state=DISABLED)
            con.close()
            refresh_history()

        def clock_in():
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")
            try:
                con = sqlite3.connect(get_db_path())
                con.execute(f"INSERT INTO attendance ({att_name_col}, date, status, clock_in) VALUES (?,?,?,?)",
                           (CURRENT_USER_NAME, today, 'Present', time))
                con.commit(); self.refresh_current_panel()
                con.close()
                update_status()
                messagebox.showinfo("Success", "Clocked in successfully")
            except Exception as e:
                messagebox.showerror("Error", "Already clocked in today")

        def clock_out():
            now = datetime.now()
            today = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")
            try:
                con = sqlite3.connect(get_db_path())
                con.execute(f"UPDATE attendance SET clock_out=? WHERE {att_name_col}=? AND date=?",
                           (time, CURRENT_USER_NAME, today))
                con.commit(); self.refresh_current_panel()
                con.close()
                update_status()
                messagebox.showinfo("Success", "Clocked out successfully")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        Label(clock_frame, textvariable=status_var, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(pady=(0, 15))
        
        btn_row = Frame(clock_frame, bg=CARD_BG)
        btn_row.pack()
        
        btn_in = Button(btn_row, text="Clock In", bg=ACCENT_GREEN, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), 
                        padx=20, pady=5, relief=FLAT, command=clock_in)
        btn_in.pack(side=LEFT, padx=10)
        
        btn_out = Button(btn_row, text="Clock Out", bg=ACCENT_RED, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), 
                         padx=20, pady=5, relief=FLAT, command=clock_out)
        btn_out.pack(side=LEFT, padx=10)
        
        # History
        Label(parent, text="Attendance History", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(20, 10))
        
        tree_f = Frame(parent, bg=CONTENT_BG)
        tree_f.pack(fill=BOTH, expand=True)
        
        cols = ("Date", "Status", "Clock In", "Clock Out")
        att_tree = ttk.Treeview(tree_f, columns=cols, show='headings')
        for c in cols:
            att_tree.heading(c, text=c)
            att_tree.column(c, width=100)
        att_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        def refresh_history():
            for i in att_tree.get_children(): att_tree.delete(i)
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute(f"SELECT date, status, clock_in, clock_out FROM attendance WHERE {att_name_col}=? ORDER BY date DESC LIMIT 30", (CURRENT_USER_NAME,))
            for r in cur.fetchall():
                att_tree.insert("", END, values=r)
            con.close()
            
        update_status()

    def build_emp_timesheets(self, parent):
        # Header
        h_frame = Frame(parent, bg=CONTENT_BG)
        h_frame.pack(fill=X, pady=20)
        Label(h_frame, text="Daily Timesheet Logging", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Form
        form_frame = Frame(parent, bg=CARD_BG, padx=20, pady=20)
        form_frame.pack(fill=X, pady=(0, 20))
        
        Label(form_frame, text="Select Task:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        c_task = ttk.Combobox(form_frame, state="readonly", style='Employee.TCombobox')
        c_task.pack(fill=X, pady=(5, 15))
        
        # Populate Active Tasks
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT id, title FROM tasks WHERE assigned_to=? AND status IN ('Pending', 'In Progress')", (CURRENT_USER_NAME,))
        tasks = cur.fetchall()
        task_map = {f"{r[1]} (ID: {r[0]})": r[0] for r in tasks}
        c_task['values'] = list(task_map.keys())
        con.close()
        
        row2 = Frame(form_frame, bg=CARD_BG)
        row2.pack(fill=X)
        
        f1 = Frame(row2, bg=CARD_BG)
        f1.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))
        Label(f1, text="Hours Spent:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        e_hours = Entry(f1, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT)
        e_hours.pack(fill=X, pady=5, ipady=3)
        
        f2 = Frame(row2, bg=CARD_BG)
        f2.pack(side=LEFT, fill=X, expand=True)
        Label(f2, text="Date:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        e_date = Entry(f2, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT)
        e_date.insert(0, datetime.now().strftime("%Y-%m-%d"))
        e_date.pack(fill=X, pady=5, ipady=3)
        
        Label(form_frame, text="Work Description:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(10, 0))
        e_desc = Entry(form_frame, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT)
        e_desc.pack(fill=X, pady=5, ipady=3)
        
        def log_time():
            t_text = c_task.get()
            hrs = e_hours.get()
            dt = e_date.get()
            desc = e_desc.get()
            
            if not t_text or not hrs or not dt:
                messagebox.showerror("Error", "Required fields missing")
                return
            
            try:
                tid = task_map[t_text]
                con = sqlite3.connect(get_db_path())
                con.execute("INSERT INTO timesheets (employee_name, date, task_id, hours, description, timestamp) VALUES (?,?,?,?,?,?)",
                           (CURRENT_USER_NAME, dt, tid, float(hrs), desc, datetime.now().strftime("%Y-%m-%d %H:%M")))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Timesheet logged")
                e_hours.delete(0, END)
                e_desc.delete(0, END)
                refresh_ts_history()
            except Exception as e:
                messagebox.showerror("Error", "Invalid data format")
        
        Button(form_frame, text="Log Hours", bg=ACCENT_BLUE, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), 
               padx=20, pady=5, relief=FLAT, command=log_time).pack(anchor=E, pady=(10, 0))
        
        # History
        Label(parent, text="Recent Timesheets", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(20, 10))
        
        tree_f = Frame(parent, bg=CONTENT_BG)
        tree_f.pack(fill=BOTH, expand=True)
        
        cols = ("Date", "Task", "Hours", "Description")
        ts_tree = ttk.Treeview(tree_f, columns=cols, show='headings')
        for c in cols:
            ts_tree.heading(c, text=c)
            ts_tree.column(c, width=100)
        ts_tree.column("Description", width=250)
        ts_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        def refresh_ts_history():
            for i in ts_tree.get_children(): ts_tree.delete(i)
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT ts.date, t.title, ts.hours, ts.description 
                FROM timesheets ts JOIN tasks t ON ts.task_id = t.id
                WHERE ts.employee_name=? ORDER BY ts.date DESC LIMIT 30
            """, (CURRENT_USER_NAME,))
            for r in cur.fetchall():
                ts_tree.insert("", END, values=r)
            con.close()
            
        refresh_ts_history()

    def build_emp_projects(self, parent):
        # Header
        Label(parent, text="Projects I'm Working On", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=20)
        
        # Project List
        tree_frame = Frame(parent, bg=CONTENT_BG)
        tree_frame.pack(fill=BOTH, expand=True)
        
        cols = ("Project Name", "Manager/Lead", "Status", "My Tasks", "Overall Progress")
        proj_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        
        for c in cols:
            proj_tree.heading(c, text=c)
            proj_tree.column(c, width=150)
            
        proj_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrolly = Scrollbar(tree_frame, orient=VERTICAL, command=proj_tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        proj_tree.configure(yscrollcommand=scrolly.set)
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        # Find projects where user has tasks
        query = """
            SELECT DISTINCT p.id, p.name, p.team_leader, p.status
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE t.assigned_to = ?
        """
        cur.execute(query, (CURRENT_USER_NAME,))
        my_projects = cur.fetchall()
        
        for pid, pname, lead, status in my_projects:
            # My Tasks Count
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND assigned_to=?", (pid, CURRENT_USER_NAME))
            my_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND assigned_to=? AND status='Completed'", (pid, CURRENT_USER_NAME))
            my_done = cur.fetchone()[0]
            my_stats = f"{my_done}/{my_total} Done"
            
            # Overall Project Progress
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
            all_total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
            all_done = cur.fetchone()[0]
            progress = f"{int((all_done/all_total)*100)}%" if all_total > 0 else "0%"
            
            proj_tree.insert("", END, values=(pname, lead, status, my_stats, progress))
            
        con.close()

    def _compute_employee_analysis_payload(self, employee_name, tl_name, project_manager_name=""):
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()

        cur.execute("PRAGMA table_info(attendance)")
        attendance_cols = [r[1] for r in cur.fetchall()]
        attendance_name_col = "employee_name" if "employee_name" in attendance_cols else "name"

        cur.execute("PRAGMA table_info(timesheets)")
        timesheet_cols = [r[1] for r in cur.fetchall()]
        timesheet_name_col = "employee_name" if "employee_name" in timesheet_cols else "name"

        cur.execute("""
            SELECT
                COUNT(*),
                SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END),
                SUM(CASE WHEN status IN ('Pending', 'In Progress') THEN 1 ELSE 0 END),
                SUM(CASE WHEN status='Delayed' OR (status!='Completed' AND due_date < date('now')) THEN 1 ELSE 0 END)
            FROM tasks
            WHERE assigned_to=?
        """, (employee_name,))
        row = cur.fetchone() or (0, 0, 0, 0)
        total_tasks = int(row[0] or 0)
        completed_tasks = int(row[1] or 0)
        active_tasks = int(row[2] or 0)
        delayed_tasks = int(row[3] or 0)

        cur.execute("""
            SELECT
                AVG(CASE
                        WHEN status='Completed' AND completed_date IS NOT NULL AND due_date IS NOT NULL
                             AND date(completed_date) <= date(due_date)
                        THEN 100.0
                        WHEN status='Completed' THEN 70.0
                        ELSE NULL
                    END)
            FROM tasks
            WHERE assigned_to=? AND status='Completed'
        """, (employee_name,))
        on_time_rate = float(cur.fetchone()[0] or 0.0)

        cur.execute("""
            SELECT
                AVG(CASE
                        WHEN status='Present' THEN 100.0
                        WHEN status='Half Day' THEN 50.0
                        ELSE 0.0
                    END)
            FROM attendance
            WHERE """ + attendance_name_col + """=? AND date >= date('now', '-30 days')
        """, (employee_name,))
        attendance_rate = float(cur.fetchone()[0] or 0.0)

        cur.execute("""
            SELECT productivity_score
            FROM performance_history
            WHERE employee_name=?
            ORDER BY month DESC, id DESC
            LIMIT 2
        """, (employee_name,))
        score_rows = [float(r[0] or 0.0) for r in cur.fetchall()]
        last_score = score_rows[0] if score_rows else 0.0
        prev_score = score_rows[1] if len(score_rows) > 1 else last_score

        cur.execute("""
            SELECT SUM(hours)
            FROM timesheets
            WHERE """ + timesheet_name_col + """=? AND date >= date('now', '-30 days')
        """, (employee_name,))
        timesheet_hours = float(cur.fetchone()[0] or 0.0)

        completion_rate = (completed_tasks / total_tasks) * 100 if total_tasks else 0.0
        workload_control = max(0.0, 100.0 - (delayed_tasks * 18.0))
        blended_score = round(
            (completion_rate * 0.40) +
            (on_time_rate * 0.25) +
            (attendance_rate * 0.20) +
            (workload_control * 0.15),
            1
        )
        if last_score > 0:
            blended_score = round((blended_score * 0.7) + (last_score * 0.3), 1)

        delta = round(last_score - prev_score, 1)
        if delta >= 5:
            trend_text = "Improving month over month"
        elif delta <= -5:
            trend_text = "Slipping against the previous cycle"
        else:
            trend_text = "Holding a mostly steady delivery trend"

        if blended_score < 45 or delayed_tasks >= 3:
            risk_level = "High"
        elif blended_score < 65 or delayed_tasks >= 1:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        strengths = []
        if completion_rate >= 70:
            strengths.append("strong completion follow-through")
        if attendance_rate >= 90:
            strengths.append("reliable attendance discipline")
        if delayed_tasks == 0 and total_tasks > 0:
            strengths.append("healthy deadline control")
        if timesheet_hours >= 120:
            strengths.append("good delivery logging consistency")
        strengths_text = ", ".join(strengths) if strengths else "shows baseline availability but needs stronger output signals"

        improvements = []
        if completion_rate < 60:
            improvements.append("close more assigned tasks")
        if delayed_tasks > 0:
            improvements.append("reduce overdue carry-forward")
        if attendance_rate < 85:
            improvements.append("stabilize attendance rhythm")
        if timesheet_hours < 40:
            improvements.append("log work evidence more consistently")
        improvements_text = ", ".join(improvements) if improvements else "continue the current rhythm and protect quality"

        pm_summary = (
            f"Project analytics show {employee_name} at {blended_score}% with {completed_tasks}/{max(total_tasks, 1)} tasks delivered, "
            f"{delayed_tasks} delayed item(s), and {active_tasks} active assignment(s)."
        )
        leader_summary = (
            f"{tl_name or 'Team leadership'} review: keep focus on {improvements_text}. "
            f"Current trend is '{trend_text.lower()}'."
        )
        action_plan = (
            "1) clear the nearest due task first, 2) update progress daily, "
            "3) ask for scope clarification early if blockers appear."
        )

        cur.execute("""
            SELECT DISTINCT manager
            FROM projects
            WHERE team_leader LIKE ?
            ORDER BY id DESC
            LIMIT 1
        """, (f"%{tl_name}%",))
        pm_row = cur.fetchone()
        project_manager_name = project_manager_name or (pm_row[0] if pm_row and pm_row[0] else "")

        con.close()
        return {
            "employee_name": employee_name,
            "team_leader_name": tl_name,
            "project_manager_name": project_manager_name,
            "report_title": "Performance Review",
            "performance_score": blended_score,
            "risk_level": risk_level,
            "trend_text": trend_text,
            "strengths": strengths_text,
            "improvement_areas": improvements_text,
            "manager_summary": pm_summary,
            "leader_summary": leader_summary,
            "action_plan": action_plan,
            "completed_tasks": completed_tasks,
            "total_tasks": total_tasks,
            "active_tasks": active_tasks,
            "delayed_tasks": delayed_tasks
        }

    def generate_team_analysis_reports(self, tl_name=None, project_manager_name=""):
        ensure_employee_analysis_report_table()
        tl_name = tl_name or CURRENT_USER_NAME
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("""
            SELECT name
            FROM employee
            WHERE reporting_manager LIKE ?
              AND lower(COALESCE(role, '')) NOT IN ('team leader', 'project manager', 'admin')
        """, (f"%{tl_name}%",))
        members = [r[0] for r in cur.fetchall()]
        con.close()

        if not members:
            return []

        payloads = []
        for member_name in members:
            payloads.append(self._compute_employee_analysis_payload(member_name, tl_name, project_manager_name))

        payloads.sort(key=lambda item: item["performance_score"])
        worst_count = max(1, min(3, len(payloads)))
        worst_payloads = payloads[:worst_count]

        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        for report in worst_payloads:
            cur.execute("""
                INSERT INTO employee_analysis_reports (
                    employee_name, team_leader_name, project_manager_name, report_title,
                    performance_score, risk_level, trend_text, strengths, improvement_areas,
                    manager_summary, leader_summary, action_plan, created_at, is_read
                )
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,datetime('now'),0)
            """, (
                report["employee_name"],
                report["team_leader_name"],
                report["project_manager_name"],
                report["report_title"],
                report["performance_score"],
                report["risk_level"],
                report["trend_text"],
                report["strengths"],
                report["improvement_areas"],
                report["manager_summary"],
                report["leader_summary"],
                report["action_plan"]
            ))
        con.commit(); self.refresh_current_panel()
        con.close()

        for report in worst_payloads:
            notify_user(
                report["employee_name"],
                f"New performance analysis shared by {tl_name}. Risk: {report['risk_level']} | Score: {report['performance_score']}%"
            )
            log_audit(
                tl_name,
                "Generated employee analysis report",
                f"Shared performance analysis with {report['employee_name']} at {report['performance_score']}%"
            )

        return worst_payloads

    def _generate_reports_from_popup(self, tl_name, popup=None):
        reports = self.generate_team_analysis_reports(tl_name)
        if popup is not None:
            try:
                popup.lift()
                popup.focus_force()
            except:
                pass
        if reports:
            names = ", ".join(r["employee_name"] for r in reports)
            messagebox.showinfo(
                "Reports Generated",
                f"Shared analysis reports for: {names}"
            )
        else:
            messagebox.showinfo(
                "No Team Members",
                f"No mapped team members were found under {tl_name}."
            )


        ensure_employee_analysis_report_table()
        header = Frame(parent, bg=CARD_BG, padx=24, pady=20, highlightbackground=ACCENT_PURPLE, highlightthickness=1)
        header.pack(fill=X, pady=(0, 18))
        title_wrap = Frame(header, bg=CARD_BG)
        title_wrap.pack(side=LEFT)
        Label(title_wrap, text="Performance Analysis", font=('Segoe UI', 16, 'bold'),
              bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_wrap, text="Team-leader analytics and project-performance notes shared back to you.",
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(5, 0))

        button_row = Frame(header, bg=CARD_BG)
        button_row.pack(side=RIGHT)

        body = Frame(parent, bg=CONTENT_BG)
        body.pack(fill=BOTH, expand=True)

        def render_reports():
            for child in body.winfo_children():
                child.destroy()

            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT reporting_manager FROM employee WHERE name=?", (CURRENT_USER_NAME,))
            row = cur.fetchone()
            tl_name = row[0] if row and row[0] else ""

            cur.execute("""
                SELECT id, team_leader_name, project_manager_name, report_title, performance_score,
                       risk_level, trend_text, strengths, improvement_areas, manager_summary,
                       leader_summary, action_plan, created_at
                FROM employee_analysis_reports
                WHERE employee_name=?
                ORDER BY datetime(created_at) DESC, id DESC
            """, (CURRENT_USER_NAME,))
            reports = cur.fetchall()

            if not reports and tl_name:
                con.close()
                self.generate_team_analysis_reports(tl_name)
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("""
                    SELECT id, team_leader_name, project_manager_name, report_title, performance_score,
                           risk_level, trend_text, strengths, improvement_areas, manager_summary,
                           leader_summary, action_plan, created_at
                    FROM employee_analysis_reports
                    WHERE employee_name=?
                    ORDER BY datetime(created_at) DESC, id DESC
                """, (CURRENT_USER_NAME,))
                reports = cur.fetchall()

            if reports:
                report = reports[0]
                cur.execute("UPDATE employee_analysis_reports SET is_read=1 WHERE employee_name=?", (CURRENT_USER_NAME,))
                con.commit(); self.refresh_current_panel()

                hero = Frame(body, bg=CARD_BG, padx=24, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                hero.pack(fill=X, pady=(0, 16))
                hero_head = Frame(hero, bg=CARD_BG)
                hero_head.pack(fill=X)
                Label(hero_head, text=report[3], font=('Segoe UI', 18, 'bold'),
                      bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                badge_color = ACCENT_RED if report[5] == "High" else (ACCENT_ORANGE if report[5] == "Medium" else ACCENT_GREEN)
                risk_badge = Frame(hero_head, bg=badge_color, padx=12, pady=5)
                risk_badge.pack(side=RIGHT)
                Label(risk_badge, text=f"{report[5]} Risk", font=('Segoe UI', 9, 'bold'),
                      bg=badge_color, fg=WHITE).pack()

                meta = Frame(hero, bg=CARD_BG)
                meta.pack(fill=X, pady=(14, 0))
                meta_items = (
                    ("Score", f"{report[4]}%", ACCENT_BLUE),
                    ("Team Leader", report[1] or "Not assigned", ACCENT_GREEN),
                    ("Project Manager", report[2] or "Not mapped", ACCENT_ORANGE),
                    ("Shared", report[12], ACCENT_PURPLE),
                )
                for idx, (label_text, value_text, accent) in enumerate(meta_items):
                    card = Frame(meta, bg=HEADER_BG, padx=16, pady=14, highlightbackground=accent, highlightthickness=1)
                    card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0 if idx == 0 else 8, 0))
                    Label(card, text=label_text.upper(), font=('Segoe UI', 8, 'bold'),
                          bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W)
                    Label(card, text=value_text, font=('Segoe UI', 13, 'bold'),
                          bg=HEADER_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(6, 0))

                insight_grid = Frame(body, bg=CONTENT_BG)
                insight_grid.pack(fill=X, pady=(0, 16))
                insight_grid.grid_columnconfigure(0, weight=1)
                insight_grid.grid_columnconfigure(1, weight=1)

                def insight(row_idx, col_idx, title, value, accent):
                    card = Frame(insight_grid, bg=CARD_BG, padx=20, pady=18, highlightbackground=accent, highlightthickness=1)
                    card.grid(row=row_idx, column=col_idx, sticky="nsew", padx=(0 if col_idx == 0 else 8, 0), pady=(0, 12))
                    Label(card, text=title, font=('Segoe UI', 11, 'bold'),
                          bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(card, text=value, font=('Segoe UI', 10),
                          bg=CARD_BG, fg=MUTED_TEXT, wraplength=460, justify=LEFT).pack(anchor=W, pady=(8, 0))

                insight(0, 0, "Trend", report[6], ACCENT_BLUE)
                insight(0, 1, "Strengths", report[7], ACCENT_GREEN)
                insight(1, 0, "Improvement Areas", report[8], ACCENT_ORANGE)
                insight(1, 1, "Action Plan", report[11], ACCENT_PURPLE)

                summaries = Frame(body, bg=CARD_BG, padx=22, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
                summaries.pack(fill=X, pady=(0, 16))
                Label(summaries, text="Leadership Summary", font=('Segoe UI', 14, 'bold'),
                      bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                Label(summaries, text=f"Project Manager View: {report[9]}",
                      font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=1000, justify=LEFT).pack(anchor=W, pady=(10, 8))
                Label(summaries, text=f"Team Leader View: {report[10]}",
                      font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=1000, justify=LEFT).pack(anchor=W)

                if len(reports) > 1:
                    history_card = Frame(body, bg=CARD_BG, padx=20, pady=16, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    history_card.pack(fill=BOTH, expand=True)
                    Label(history_card, text="Previous Reports", font=('Segoe UI', 13, 'bold'),
                          bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    history_tree = ttk.Treeview(history_card, columns=("Date", "Score", "Risk", "Trend"), show='headings', height=5, style='Custom.Treeview')
                    for col_name in ("Date", "Score", "Risk", "Trend"):
                        history_tree.heading(col_name, text=col_name)
                        history_tree.column(col_name, width=150, anchor=W if col_name == "Trend" else CENTER)
                    history_tree.column("Trend", width=420, anchor=W)
                    history_tree.pack(fill=X, pady=(10, 0))
                    self._attach_tree_hover(history_tree)
                    for old_report in reports[1:6]:
                        history_tree.insert("", END, values=(old_report[12], f"{old_report[4]}%", old_report[5], old_report[6]))
            else:
                empty = Frame(body, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
                empty.pack(fill=X)
                Label(empty, text="No analysis report shared yet", font=('Segoe UI', 15, 'bold'),
                      bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                Label(empty, text="Once your team leader flags a delivery-risk review, the latest analysis will appear here.",
                      font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=980, justify=LEFT).pack(anchor=W, pady=(8, 0))

            con.close()

        Button(button_row, text="Refresh Analysis", bg=ACCENT_BLUE, fg=WHITE, relief=FLAT,
               activebackground=ACCENT_BLUE_DARK if 'ACCENT_BLUE_DARK' in globals() else ACCENT_BLUE,
               activeforeground=WHITE, font=('Segoe UI', 10, 'bold'),
               padx=16, pady=8, command=render_reports).pack(side=RIGHT)
        render_reports()



    def refresh_emp_dashboard(self):
        filter_val = getattr(self, 'emp_dash_filter', None)
        filter_val = filter_val.get() if filter_val else "Active"
        
        if hasattr(self, 'dash_task_label'):
            self.dash_task_label.config(text=f"MY {filter_val.upper()} TASKS")

        if not hasattr(self, 'dash_task_tree') or not self.dash_task_tree.winfo_exists():
            return
        
        for i in self.dash_task_tree.get_children(): self.dash_task_tree.delete(i)
        if hasattr(self, 'dash_dead_tree') and self.dash_dead_tree.winfo_exists():
            for i in self.dash_dead_tree.get_children(): self.dash_dead_tree.delete(i)
        
        # 1. Fetch from Backend API
        backend_tasks = []
        if CURRENT_TOKEN:
            try:
                all_backend_tasks = api.get_tasks()
                backend_tasks = [t for t in all_backend_tasks if t.get('assignedTo') == CURRENT_USER_NAME or t.get('assignedTo') == CURRENT_USER_EMAIL]
            except Exception as e:
                debug_log(f"DEBUG: Error fetching backend tasks: {e}")

        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        # 2. Fetch from Local SQLite with Filtering
        query = "SELECT t.title, p.name, t.due_date FROM tasks t LEFT JOIN projects p ON t.project_id = p.id WHERE t.assigned_to=?"
        params = [CURRENT_USER_NAME]
        
        if filter_val == "Active":
            query += " AND t.status NOT IN ('Completed', 'Cancelled')"
        elif filter_val == "Completed":
            query += " AND t.status = 'Completed'"
        elif filter_val == "Pending":
            query += " AND t.status = 'Pending'"
        elif filter_val == "Overdue":
            query += " AND t.status NOT IN ('Completed', 'Cancelled') AND t.due_date < date('now')"
        
        query += " ORDER BY t.due_date ASC LIMIT 10"
        cur.execute(query, tuple(params))
        sqlite_rows = cur.fetchall()
        
        combined_active = []
        seen_titles = set()
        today_str = datetime.now().strftime("%Y-%m-%d")

        for bt in backend_tasks:
            status = bt.get('status')
            due = bt.get('dueDate', '')
            if due and 'T' in due: due = due.split('T')[0]
            
            show = False
            if filter_val == "Active" and status not in ('Completed', 'Cancelled'): show = True
            elif filter_val == "Completed" and status == 'Completed': show = True
            elif filter_val == "Pending" and status == 'Pending': show = True
            elif filter_val == "Overdue" and status not in ('Completed', 'Cancelled') and due < today_str: show = True
            elif filter_val == "All": show = True
            
            if show:
                title = bt.get('title', 'Untitled')
                project = bt.get('project', {}).get('name', 'N/A') if isinstance(bt.get('project'), dict) else 'N/A'
                if title not in seen_titles:
                    combined_active.append((title, project, due))
                    seen_titles.add(title)

        for st in sqlite_rows:
            if st[0] not in seen_titles:
                combined_active.append(st)
                seen_titles.add(st[0])

        combined_active.sort(key=lambda x: x[2] if x[2] else '9999-99-99')

        if combined_active:
            for r in combined_active[:10]:
                self.dash_task_tree.insert("", END, values=r)
        else:
            self.dash_task_tree.insert("", END, values=("No active tasks", "All caught up", "-"))
        
        # 3. Upcoming Deadlines
        today = datetime.now().date()
        deadlines = []
        for title, project, due in combined_active:
            try:
                due_date = datetime.strptime(due, "%Y-%m-%d").date()
                if due_date >= today:
                    days_left = (due_date - today).days
                    days_text = f"{days_left} days" if days_left > 0 else "Today"
                    deadlines.append((title, due, days_text, days_left))
            except: continue
        
        deadlines.sort(key=lambda x: x[3])
        if deadlines:
            for r in deadlines[:10]:
                days_left = r[3]
                tag = 'Safe'
                if days_left <= 1: tag = 'Urgent'
                elif days_left <= 3: tag = 'Warning'
                self.dash_dead_tree.insert("", END, values=r[:3], tags=(tag,))
        else:
            self.dash_dead_tree.insert("", END, values=("No upcoming deadlines", "-", "-"))
        con.close()


    def on_task_click_modal(self, tid):
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT title, description, priority, status, due_date FROM tasks WHERE id=?", (tid,))
            task = cur.fetchone()
            con.close()
            
            if task:
                title, desc, prio, status, due = task
                
                win = Toplevel(self.root)
                win.title("Task Details & Update")
                win.geometry("500x550")
                win.config(bg=CONTENT_BG)
                win.transient(self.root)
                win.grab_set()
                
                # Center the window
                sw = self.root.winfo_screenwidth()
                sh = self.root.winfo_screenheight()
                win.geometry(f"+{int((sw/2)-(500/2))}+{int((sh/2)-(550/2))}")
                
                hdr = Frame(win, bg=CARD_BG, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                hdr.pack(fill=X)
                Label(hdr, text=title, font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE, wraplength=450).pack()
                
                body = Frame(win, bg=CONTENT_BG, padx=30, pady=20)
                body.pack(fill=BOTH, expand=True)
                
                Label(body, text="DESCRIPTION", font=('Segoe UI', 8, 'bold'), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W)
                Label(body, text=desc or 'No description provided.', font=('Segoe UI', 10), bg=CONTENT_BG, fg=TEXT_WHITE, wraplength=400, justify=LEFT).pack(anchor=W, pady=(5, 15))
                
                Label(body, text=f"Priority: {prio}", font=('Segoe UI', 10), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=2)
                Label(body, text=f"Due Date: {due}", font=('Segoe UI', 10), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=2)
                
                Label(body, text="UPDATE STATUS", font=('Segoe UI', 8, 'bold'), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(15, 5))
                status_var = StringVar(value=status)
                status_cb = ttk.Combobox(body, textvariable=status_var, values=["Pending", "In Progress", "Submit for Review", "Completed"], state="readonly", width=15)
                status_cb.pack(anchor=W, pady=(0, 20))
                
                def save_status():
                    new_status = status_var.get()
                    from datetime import datetime
                    try:
                        con = sqlite3.connect(get_db_path())
                        cur = con.cursor()
                        cur.execute("UPDATE tasks SET status = ?, completed_date = ? WHERE id = ?", 
                                    (new_status, datetime.now().strftime('%Y-%m-%d') if new_status == 'Completed' else None, tid))
                        con.commit()
                        con.close()
                        
                        win.destroy()
                        self.refresh_emp_tasks_tab()
                        messagebox.showinfo("Success", "Task status updated successfully!")
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to update task: {e}")

                btn_f = Frame(body, bg=CONTENT_BG)
                btn_f.pack(pady=(10, 0))
                
                Button(btn_f, text="SAVE", bg=ACCENT_BLUE, fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), 
                       relief=FLAT, padx=20, pady=10, command=save_status).pack(side=LEFT, padx=(0, 10))
                       
                Button(btn_f, text="CLOSE", bg=BORDER_COLOR, fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), 
                       relief=FLAT, padx=20, pady=10, command=win.destroy).pack(side=LEFT)
                       
        except Exception as e:
            debug_log(f"DEBUG: Error showing task modal: {e}")

    def refresh_emp_tasks_tab(self):
        if not hasattr(self, 'emp_tasks_container') or not self.emp_tasks_container.winfo_exists():
            return
            
        for widget in self.emp_tasks_container.winfo_children(): widget.destroy()
        
        # 1. Fetch from Backend API
        backend_tasks = []
        if CURRENT_TOKEN:
            try:
                all_backend_tasks = api.get_tasks()
                backend_tasks = [t for t in all_backend_tasks if t.get('assignedTo') == CURRENT_USER_NAME or t.get('assignedTo') == CURRENT_USER_EMAIL]
            except Exception as e:
                debug_log(f"DEBUG: Error fetching backend tasks: {e}")

        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        query = """
            SELECT t.id, t.title, p.name, t.priority, t.status, t.due_date,
            (strftime('%s', t.due_date) - strftime('%s', 'now')) / 86400 as days_left,
            t.description, t.assigned_to
            FROM tasks t LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.assigned_to=?
        """
        params = [CURRENT_USER_NAME]
        
        search = self.emp_task_search.get().lower()
        if search:
            query += " AND (LOWER(t.title) LIKE ? OR LOWER(p.name) LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
            
        status_filter = self.emp_task_status.get()
        if status_filter == "All Active":
            query += " AND t.status != 'Completed'"
        elif status_filter != "All":
            query += " AND t.status = ?"
            params.append(status_filter)
            
        prio_filter = self.emp_task_prio.get()
        if prio_filter != "All":
            query += " AND t.priority = ?"
            params.append(prio_filter)
            
        query += " ORDER BY t.due_date ASC"
        cur.execute(query, params)
        sqlite_tasks = cur.fetchall()
        
        seen_titles = set()
        combined_tasks = []
        for bt in backend_tasks:
            title = bt.get('title', 'Untitled')
            project = bt.get('project', {}).get('name', 'N/A') if isinstance(bt.get('project'), dict) else 'N/A'
            priority = bt.get('priority', 'Medium')
            status = bt.get('status', 'Pending')
            due = bt.get('dueDate', 'N/A')
            if due and 'T' in due: due = due.split('T')[0]
            
            if search and (search not in title.lower() and search not in project.lower()): continue
            if status_filter == "All Active" and status == "Completed": continue
            elif status_filter != "All" and status_filter != "All Active" and status != status_filter: continue
            if prio_filter != "All" and priority != prio_filter: continue

            combined_tasks.append({
                'id': f"API-{bt.get('_id', '')[:8]}",
                'title': title,
                'project': project,
                'priority': priority,
                'status': status,
                'due_date': due,
                'days_left_text': 'N/A',
                'days_left_val': None
            })
            seen_titles.add(title)

        for st in sqlite_tasks:
            if st[1] in seen_titles: continue
            combined_tasks.append({
                'id': st[0],
                'title': st[1],
                'project': st[2],
                'priority': st[3],
                'status': st[4],
                'due_date': st[5],
                'days_left_text': f"{int(st[6])} days" if st[6] is not None and int(st[6]) > 0 else ("Today" if st[6] is not None and int(st[6]) == 0 else (f"{-int(st[6])} days overdue" if st[6] is not None else "N/A")),
                'days_left_val': int(st[6]) if st[6] is not None else None
            })

        # Sort combined list by due date
        combined_tasks.sort(key=lambda x: x['due_date'] if x['due_date'] else '9999-99-99')

        for t in combined_tasks:
            tid = t['id']
            title = t['title']
            project = t['project']
            priority = t['priority']
            status = t['status']
            due_date = t['due_date']
            days_left = t['days_left_text']
            
            tag = status
            if tag != 'Completed' and t['days_left_val'] is not None and t['days_left_val'] < 0:
                tag = 'Delayed'
                
            color = ACCENT_BLUE
            if status == "Completed": color = ACCENT_GREEN
            elif status == "In Progress": color = "#f59e0b"
            elif tag == "Delayed": color = ACCENT_RED
            
            card = Frame(self.emp_tasks_container, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=15)
            card.pack(fill=X, pady=(0, 15))
            
            left_f = Frame(card, bg=CARD_BG)
            left_f.pack(side=LEFT, fill=BOTH, expand=True)
            
            Label(left_f, text=title, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            sub_info = f"Project: {project}  •  Due: {due_date}  •  {days_left}"
            Label(left_f, text=sub_info, font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
            
            right_f = Frame(card, bg=CARD_BG)
            right_f.pack(side=RIGHT)
            
            Label(right_f, text=priority.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=(0, 15))
            
            status_f = Frame(right_f, bg=color, padx=10, pady=4)
            status_f.pack(side=LEFT, padx=(0, 15))
            Label(status_f, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=color, fg=WHITE).pack()
            
            def make_update_cmd(task_id=tid):
                return lambda: self.on_task_click_modal(task_id)
                
            btn = Button(right_f, text="UPDATE", bg="#1e293b", fg=TEXT_WHITE, font=('Segoe UI', 8, 'bold'),
                         relief=FLAT, padx=15, pady=6, highlightbackground=BORDER_COLOR, highlightthickness=1,
                         command=make_update_cmd(tid))
            btn.pack(side=LEFT)
            self._apply_hover_effect(btn, "#1e293b", "#334155")
            self._apply_hover_effect(card, CARD_BG, "#1c223d")
            
        con.close()



    def refresh_emp_history(self):
        for i in self.hist_tree.get_children(): self.hist_tree.delete(i)
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        query = """
            SELECT t.id, t.title, p.name, t.completed_date
            FROM tasks t 
            LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.assigned_to=? AND t.status = 'Completed'
        """
        params = [CURRENT_USER_NAME]
        
        date_filter = self.hist_date_filter.get()
        if date_filter == "This Week":
            query += " AND t.completed_date >= date('now', '-7 days')"
        elif date_filter == "This Month":
            query += " AND t.completed_date >= date('now', 'start of month')"
            
        query += " ORDER BY t.completed_date DESC"
        
        cur.execute(query, params)
        rows = cur.fetchall()
        for r in rows: self.hist_tree.insert("", END, values=r)
        
        # Update count
        self.hist_count_var.set(f"Total Completed: {len(rows)}")
        con.close()

    def export_history_csv(self):
        import csv
        from tkinter import filedialog
        
        items = self.hist_tree.get_children()
        if not items:
            messagebox.showwarning("Warning", "No data to export")
            return
            
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path: return
        
        try:
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["ID", "Title", "Project", "Completed Date"])
                for item in items:
                    writer.writerow(self.hist_tree.item(item, "values"))
            messagebox.showinfo("Success", f"History exported to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")


    def view_query_details(self, event):
        item = self.query_tree.selection()
        if not item: return
        vals = self.query_tree.item(item[0], "values")
        qid = vals[0]
        
        t = Toplevel(self.root)
        t.title(f"Query #{qid} Details")
        t.geometry("600x600")
        t.minsize(510, 510)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        # Header
        h = Frame(t, bg=CONTENT_BG, padx=20, pady=10)
        h.pack(fill=X)
        Label(h, text=f"Query: {vals[1]}", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text=f"Status: {vals[2]}", font=('Segoe UI', 10), bg=CONTENT_BG, fg=ACCENT_ORANGE).pack(side=RIGHT)
        
        # Conversation Display
        conv_frame = Frame(t, bg=CARD_BG, padx=15, pady=15)
        conv_frame.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        txt = Text(conv_frame, bg=BG_DARK, fg=TEXT_WHITE, font=('Segoe UI', 10), state=DISABLED, wrap=WORD)
        txt.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrolly = Scrollbar(conv_frame, command=txt.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        txt.config(yscrollcommand=scrolly.set)
        
        # Load conversation
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT message, response, history FROM queries WHERE id=?", (qid,))
        res = cur.fetchone()
        if not res: 
            con.close()
            return
        msg, resp, hist = res
        
        txt.config(state=NORMAL)
        txt.insert(END, f"--- Query Raised ---\n{msg}\n\n")
        if resp:
            txt.insert(END, f"--- TL Response ---\n{resp}\n\n")
        if hist:
            txt.insert(END, f"--- Follow-ups ---\n{hist}\n")
        txt.config(state=DISABLED)
        txt.see(END)
        
        # Follow-up Input
        if vals[2] != 'Resolved':
            f_frame = Frame(t, bg=CONTENT_BG, padx=20, pady=10)
            f_frame.pack(fill=X)
            
            Label(f_frame, text="Add Follow-up:", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
            f_msg = Text(f_frame, height=4, width=50, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE)
            f_msg.pack(fill=X, pady=5)
            
            def send_followup():
                f_txt = f_msg.get("1.0", END).strip()
                if not f_txt: return
                
                new_hist = (hist or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Me: {f_txt}\n"
                
                con_inner = sqlite3.connect(get_db_path())
                cur_inner = con_inner.cursor()
                cur_inner.execute("UPDATE queries SET history=?, status='Open' WHERE id=?", (new_hist, qid))
                con_inner.commit(); self.refresh_current_panel()
                con_inner.close()
                
                t.destroy()
                self.refresh_emp_queries()
                messagebox.showinfo("Success", "Follow-up sent")
                
            Button(f_frame, text="Send Follow-up", bg=PRIMARY_BG, fg=TEXT_WHITE, relief=FLAT, command=send_followup).pack(pady=5)
        
        con.close()

    def raise_query_modal(self):
        t = Toplevel(self.root)
        t.title("Raise Query to Team Leader")
        t.geometry("500x400")
        t.minsize(425, 400)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        Label(t, text="Raise New Query", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        
        f = Frame(t, bg=CARD_BG, padx=20, pady=20)
        f.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
        
        Label(f, text="Subject:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        sub_e = Entry(f, width=50, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT)
        sub_e.pack(fill=X, pady=(5, 15), ipady=3)
        
        Label(f, text="Message / Issue:", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        msg_t = Text(f, height=8, width=50, bg=BG_DARK, fg=TEXT_WHITE, insertbackground=TEXT_WHITE, relief=FLAT)
        msg_t.pack(fill=BOTH, expand=True, pady=(5, 20))
        
        def save():
            sub = sub_e.get().strip()
            msg = msg_t.get("1.0", END).strip()
            if not sub or not msg:
                messagebox.showerror("Error", "All fields are required")
                return
                
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("INSERT INTO queries (user_name, subject, message) VALUES (?,?,?)", (CURRENT_USER_NAME, sub, msg))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Query sent to Team Leader")
                self.refresh_emp_queries()
                t.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(f, text="Send Query", bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), 
               relief=FLAT, command=save).pack()
    def load_projects(self):
        # FIX 5: Don't recreate ttk.Style() — it resets all global styles causing flicker.
        # ttk.Style() is a singleton; calling it again returns the existing instance safely.
        style = ttk.Style()
        style.configure(
            "Projects.Treeview",
            background=HEADER_BG,
            foreground=TEXT_WHITE,
            fieldbackground=HEADER_BG,
            rowheight=42,
            borderwidth=0,
            relief="flat",
            font=('Segoe UI', 10)
        )
        style.configure(
            "Projects.Treeview.Heading",
            background="#252529",
            foreground=TEXT_WHITE,
            font=('Segoe UI', 10, 'bold'),
            borderwidth=0,
            relief="flat",
            padding=(15, 12)
        )
        style.map(
            "Projects.Treeview",
            background=[('selected', ACCENT_BLUE)],
            foreground=[('selected', WHITE)]
        )
        style.map(
            "Projects.Treeview.Heading",
            background=[('active', "#2f2f35")]
        )

        px = self.get_responsive_padx()
        is_narrow = self.root.winfo_width() < 1050

        hero = Frame(self.content_area, bg=CARD_BG, padx=px, pady=26, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hero.pack(fill=X, padx=px, pady=(24, 16))

        hero_left = Frame(hero, bg=CARD_BG)
        hero_left.pack(side=LEFT, fill=X, expand=True)
        Label(hero_left, text="Project Master List", font=('Segoe UI', 28, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(hero_left, text="Track delivery health, ownership, progress, and deadlines from one polished command center.",
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 16))

        stat_row = Frame(hero_left, bg=CARD_BG)
        # stat_row.pack(fill=X, pady=(0, 5)) # Removed per user request

        def build_stat_tile(parent, icon, accent, title, value_text):
            tile = Frame(parent, bg=HEADER_BG, padx=18, pady=16, highlightbackground=accent, highlightthickness=1)
            
            top_r = Frame(tile, bg=HEADER_BG)
            top_r.pack(fill=X)

            # Icon Box (Colored Background) - Fixed square to match reference image
            icon_frame = Frame(top_r, bg=accent, width=24, height=24)
            icon_frame.pack(side=LEFT, padx=(0, 8))
            icon_frame.pack_propagate(False)
            
            icon_lbl = Label(icon_frame, text=icon, font=('Segoe UI Emoji', 10),
                             bg=accent, fg=WHITE)
            icon_lbl.pack(expand=True)

            Label(top_r, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack(side=LEFT)
            
            value_label = Label(tile, text=value_text, font=('Segoe UI', 18, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE)
            value_label.pack(anchor=W, pady=(10, 0))
            return tile, value_label

        total_tile, self.projects_total_chip = build_stat_tile(stat_row, "📊", ACCENT_BLUE, "Total Projects", "0")
        # total_tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        ongoing_tile, self.projects_ongoing_chip = build_stat_tile(stat_row, "⚡", ACCENT_GREEN, "Ongoing", "0")
        # ongoing_tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        delayed_tile, self.projects_delayed_chip = build_stat_tile(stat_row, "⚠️", ACCENT_RED, "Delayed", "0")
        # delayed_tile.pack(side=LEFT, fill=BOTH, expand=True)

        if is_narrow:
            # Adjust hero layout for narrow screens
            hero_left.pack_configure(side=TOP)
            btn_frame.pack_configure(side=TOP, anchor=W, padx=0, pady=(10, 0))
            # stat_row.pack_configure(pady=(10, 5))

        btn_frame = Frame(hero, bg=CARD_BG)
        btn_frame.pack(side=RIGHT, anchor=NE, padx=(20, 0))

        def make_action_btn(parent, text, bg, cmd):
            btn = Button(parent, text=text, bg=bg, fg=WHITE, font=('Segoe UI', 10, 'bold'),
                         relief=FLAT, bd=0, padx=18, pady=12, activebackground=ACCENT_HOVER,
                         activeforeground=WHITE, command=cmd, cursor='hand2')
            return btn

        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager', 'team leader']:
            make_action_btn(btn_frame, "+ New Project", ACCENT_GREEN, self.add_project_modal).pack(side=LEFT, padx=6)
            make_action_btn(btn_frame, "⚙ Update", ACCENT_PURPLE, self.update_project_modal).pack(side=LEFT, padx=6)
            # make_action_btn(btn_frame, "👁 Details", ACCENT_BLUE, lambda: self.on_project_double_click(None)).pack(side=LEFT, padx=6)
            if CURRENT_USER_ROLE.lower() in ('project manager', 'admin'):
                make_action_btn(btn_frame, "🗑 Delete", PRIMARY_BG, self.delete_project).pack(side=LEFT, padx=6)

        self.search_var = StringVar(value="")
        self.filter_var = StringVar(value="All")

        portfolio_band = Frame(self.content_area, bg=CARD_BG, padx=px, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
        portfolio_band.pack(fill=X, padx=px, pady=(0, 16))
        Label(portfolio_band, text="Project Portfolio Overview", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 14, 'bold')).pack(anchor=W)
        Label(portfolio_band, text="A cleaner portfolio view focused on delivery health, ownership, and deadlines.",
              bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(4, 0))

        tree_shell = Frame(self.content_area, bg=CARD_BG, padx=2, pady=2, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tree_shell.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        tree_frame = Frame(tree_shell, bg=CARD_BG)
        tree_frame.pack(fill=BOTH, expand=True)

        table_header = Frame(tree_frame, bg=CARD_BG, padx=20, pady=14)
        # table_header.pack(fill=X)
        Label(table_header, text="Project Portfolio", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Filter & Search (Modernized UI fix)
        ctrls = Frame(table_header, bg=CARD_BG)
        ctrls.pack(side=LEFT, padx=30)
        
        Label(ctrls, text="Status Group:", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
        f_box = ttk.Combobox(ctrls, textvariable=self.filter_var, values=["All", "Ongoing", "Delayed", "Completed"], 
                           width=14, state="readonly", style="Employee.TCombobox")
        f_box.pack(side=LEFT, padx=8)
        
        Label(ctrls, text="🔎 Search:", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9, 'bold')).pack(side=LEFT, padx=(20, 0))
        s_ent = Entry(ctrls, textvariable=self.search_var, bg="#1a2035", fg=WHITE, insertbackground=WHITE, 
                     font=('Segoe UI', 10), relief=FLAT, width=28, highlightthickness=1, highlightbackground="#3d445c")
        s_ent.pack(side=LEFT, padx=8, ipady=3)
        
        self.search_var.trace_add("write", lambda *a: self.refresh_projects())
        self.filter_var.trace_add("write", lambda *a: self.refresh_projects())

        if is_narrow:
            ctrls.pack_configure(side=TOP, anchor=W, padx=0, pady=(5, 0))
            # table_header.pack_configure(pady=6)
            Label(table_header, text="Double-click a row for breakdown", font=('Segoe UI', 8),
                  bg=CARD_BG, fg=MUTED_TEXT).pack(side=TOP, anchor=W, pady=(5,0))
        else:
            Label(table_header, text="Double-click a row for full breakdown", font=('Segoe UI', 9),
                  bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)

        divider = Frame(tree_frame, bg=BORDER_COLOR, height=1)
        # divider.pack(fill=X)

        table_wrap = Frame(tree_frame, bg=CARD_BG)
        table_wrap.pack(fill=BOTH, expand=True)

        # Portfolio Container (Canvas + Scrollable Frame for Cards)
        portfolio_container = Frame(tree_frame, bg=CARD_BG)
        portfolio_container.pack(fill=BOTH, expand=True)

        self.project_canvas = Canvas(portfolio_container, bg=CARD_BG, highlightthickness=0)
        self.project_scrollbar = ttk.Scrollbar(portfolio_container, orient=VERTICAL, command=self.project_canvas.yview)
        self.project_cards_frame = Frame(self.project_canvas, bg=CARD_BG)

        self.project_cards_frame.bind(
            "<Configure>",
            lambda e: self.project_canvas.configure(scrollregion=self.project_canvas.bbox("all"))
        )
        self._project_canvas_frame_id = self.project_canvas.create_window((0, 0), window=self.project_cards_frame, anchor="nw")

        def _resize_canvas(event):
            self.project_canvas.itemconfig(self._project_canvas_frame_id, width=event.width)
        self.project_canvas.bind("<Configure>", _resize_canvas)
        
        self._bind_canvas_scrolling(portfolio_container, self.project_canvas)

        self.project_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.project_scrollbar.pack(side=RIGHT, fill=Y)
        self.project_canvas.configure(yscrollcommand=self.project_scrollbar.set)

        self.selected_project_id = None
        self.project_card_widgets = {}

        # Mock Tree for logic compatibility (Delete, Update, etc.)
        class MockTree:
            def __init__(self, parent): self.parent = parent
            def selection(self): return ["item"] if self.parent.selected_project_id else []
            def item(self, _id): return {'values': [self.parent.selected_project_id]}
            def get_children(self, _id=""): return []
            def delete(self, _id): pass
            def move(self, _id, _p, _idx): pass

        self.proj_tree = MockTree(self)
        self.refresh_projects()


    def sort_projects_tree(self, column):
        if not hasattr(self, "_proj_sort_reverse"):
            self._proj_sort_reverse = {}
        reverse = self._proj_sort_reverse.get(column, False)
        self._proj_sort_reverse[column] = not reverse

        def parse_value(v):
            if column == "ID":
                try: return int(v)
                except: return 0
            if column == "Progress":
                try:
                    if "|" in v:
                        return int(v.split("|", 1)[1].replace("%", "").strip())
                    return int(str(v).replace("%", "").strip())
                except:
                    return 0
            if column in ("Deadline", "Start Date"):
                return str(v)
            if column == "Priority":
                return {"High": 3, "Medium": 2, "Low": 1}.get(str(v), 0)
            return str(v).lower()

        rows = [(self.proj_tree.set(i, column), i) for i in self.proj_tree.get_children("")]
        rows.sort(key=lambda x: parse_value(x[0]), reverse=reverse)
        for idx, (_, item_id) in enumerate(rows):
            self.proj_tree.move(item_id, "", idx)

    def refresh_projects(self, reset_page=False):
        # Clear existing cards
        if hasattr(self, 'project_cards_frame'):
            for widget in self.project_cards_frame.winfo_children():
                widget.destroy()

        query = "SELECT id, name, team_leader, status, start_date, end_date, COALESCE(priority, 'Medium'), description FROM projects WHERE 1=1"
        params = []

        role = CURRENT_USER_ROLE.lower()
        if role == 'team leader':
            query += " AND team_leader LIKE ?"
            params.append(f"%{CURRENT_USER_NAME}%")

        status_filter = self.filter_var.get()
        if status_filter != "All":
            query += " AND status=?"
            params.append(status_filter)

        search_txt = self.search_var.get().strip().lower()
        if search_txt:
            query += " AND (lower(name) LIKE ? OR lower(team_leader) LIKE ?)"
            params.extend([f"%{search_txt}%", f"%{search_txt}%"])

        query += " ORDER BY name ASC"

        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            total_projects = len(rows)
            ongoing_projects = sum(1 for row in rows if str(row[3]) == "Ongoing")
            delayed_count = 0

            # Grid Configuration
            self.root.update_idletasks()
            win_width = self.root.winfo_width()
            cols_count = 3 if win_width > 1200 else (2 if win_width > 800 else 1)
            for i in range(3):
                self.project_cards_frame.columnconfigure(i, weight=1, uniform="group1")

            for idx, (pid, name, leader, status, start_date, deadline, priority, desc) in enumerate(rows):
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
                comp = cursor.fetchone()[0]
                prog = int((comp/total)*100) if total > 0 else 0

                # Date Analysis
                days_txt = "N/A"
                overdue = False
                if deadline:
                    try:
                        d1 = datetime.now().date()
                        try:
                            d2 = datetime.strptime(deadline, "%Y-%m-%d").date()
                        except:
                            d2 = datetime.strptime(deadline, "%d/%m/%Y").date()
                        diff = (d2 - d1).days
                        if diff < 0:
                            days_txt = f"{abs(diff)}d Overdue"
                            overdue = True
                        else:
                            days_txt = f"{diff}d left"
                    except: pass

                if status == "Delayed" or overdue: delayed_count += 1
                self._render_project_card(idx, cols_count, pid, name, leader, status, prog, deadline, priority, days_txt, overdue)

            # Update Chips
            if hasattr(self, "projects_total_chip"): self.projects_total_chip.config(text=str(total_projects))
            if hasattr(self, "projects_ongoing_chip"): self.projects_ongoing_chip.config(text=str(ongoing_projects))
            if hasattr(self, "projects_delayed_chip"): self.projects_delayed_chip.config(text=str(delayed_count))

            con.close()
        except Exception as e:
            debug_log(f"Error refreshing project cards: {e}")

    def _render_project_card(self, idx, cols, pid, name, leader, status, prog, deadline, priority, days_txt, overdue):
        _s_bg = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_BLUE, 
                 "Delayed": ACCENT_RED, "Not Started": "#5c637a"}.get(status, MUTED_TEXT)
        if overdue: _s_bg = ACCENT_RED

        r, c = divmod(idx, cols)
        card = Frame(self.project_cards_frame, bg=CARD_BG, padx=1, pady=1, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=r, column=c, sticky="nsew", padx=12, pady=12)
        self.project_card_widgets[pid] = card
        
        stripe = Frame(card, bg=_s_bg, height=4)
        stripe.pack(fill=X)
        
        inner = Frame(card, bg=CARD_BG, padx=20, pady=18)
        inner.pack(fill=BOTH, expand=True)

        top = Frame(inner, bg=CARD_BG); top.pack(fill=X)
        Label(top, text=name, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        p_color = {"High": ACCENT_RED, "Medium": ACCENT_ORANGE, "Low": ACCENT_GREEN}.get(priority, MUTED_TEXT)
        p_frame = Frame(top, bg=p_color, padx=6, pady=1); p_frame.pack(side=RIGHT)
        Label(p_frame, text=priority.upper(), font=('Segoe UI', 7, 'bold'), bg=p_color, fg=WHITE).pack()

        s_row = Frame(inner, bg=CARD_BG); s_row.pack(fill=X, pady=(10, 0))
        s_badge = Frame(s_row, bg=_s_bg, padx=8, pady=2); s_badge.pack(side=LEFT)
        Label(s_badge, text=status, font=('Segoe UI', 8, 'bold'), bg=_s_bg, fg=WHITE).pack()
        
        health_color = ACCENT_RED if overdue else (ACCENT_GREEN if status == "Completed" else MUTED_TEXT)
        Label(s_row, text=days_txt, font=('Segoe UI', 9), bg=CARD_BG, fg=health_color).pack(side=RIGHT)

        p_row = Frame(inner, bg=CARD_BG); p_row.pack(fill=X, pady=(15, 5))
        Label(p_row, text="Progress", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
        Label(p_row, text=f"{prog}%", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(side=RIGHT)
        
        bar_track = Frame(inner, bg="#2a3352", height=6); bar_track.pack(fill=X, pady=(0, 10))
        if prog > 0:
            bar_fill = Frame(bar_track, bg=ACCENT_GREEN, height=6)
            bar_fill.place(x=0, y=0, relwidth=min(prog/100, 1.0))

        bot = Frame(inner, bg=CARD_BG); bot.pack(fill=X, pady=(5, 0))
        Label(bot, text=f"\U0001f464 {leader or 'Unassigned'}", font=('Segoe UI', 8), bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=LEFT)
        
        btn = Button(bot, text="DETAILS \u2192", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE,
                     relief=FLAT, bd=0, padx=0, pady=0, activebackground=CARD_BG, activeforeground=WHITE,
                     command=lambda: self.view_project_details(pid), cursor="hand2")
        btn.pack(side=RIGHT)

        def _select_card(_e=None):
            # Unselect others
            for other_pid, other_card in self.project_card_widgets.items():
                other_card.config(highlightbackground=BORDER_COLOR, highlightthickness=1)
            # Select this one
            self.selected_project_id = pid
            card.config(highlightbackground=ACCENT_BLUE, highlightthickness=2)

        def _on_e(e): 
            card.config(highlightbackground=_s_bg, highlightthickness=2)
            inner.config(bg="#1c223d")
            for w in inner.winfo_children():
                try: w.config(bg="#1c223d")
                except: pass
                
        def _on_l(e): 
            if self.selected_project_id != pid:
                card.config(highlightbackground=BORDER_COLOR, highlightthickness=1)
                inner.config(bg=CARD_BG)
                for w in inner.winfo_children():
                    try: w.config(bg=CARD_BG)
                    except: pass
            else:
                card.config(highlightbackground=ACCENT_BLUE, highlightthickness=2)

        card.bind("<Enter>", _on_e); card.bind("<Leave>", _on_l)
        inner.bind("<Enter>", _on_e); inner.bind("<Leave>", _on_l)
        inner.bind("<Button-1>", _select_card)
        for w in inner.winfo_children():
            w.bind("<Button-1>", _select_card)


    def on_project_double_click(self, event):
        item = self.proj_tree.selection()
        if not item: return
        vals = self.proj_tree.item(item[0], "values")
        self.view_project_details(vals[0])

    def view_project_details(self, pid):
        # Fetch full details including TL contact
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT * FROM projects WHERE id=?", (pid,))
            proj = cur.fetchone()
            
            if not proj: return
            
            # Unpack (id, name, desc, start, end, status, manager, team_leader)
            # Schema check: id(0), name(1), desc(2), start(3), end(4), status(5), manager(6), team_leader(7)
            # Wait, verify schema index from init_database
            # init_database: name, description, start, end, status, manager. Then altered to add team_leader.
            # So order is: id, name, description, start_date, end_date, status, manager, team_leader.
            
            # Let's fetch by name to be safe
            cur.execute("SELECT name, description, start_date, end_date, status, team_leader FROM projects WHERE id=?", (pid,))
            row = cur.fetchone()
            name, desc, start, end, status, leader = row
            
            # Fetch TL Details
            tl_info = []
            if leader:
                names = [n.strip() for n in leader.split(",")]
                placeholders = ','.join('?' for _ in names)
                cur.execute(f"SELECT name, email, mobile, department, role FROM employee WHERE name IN ({placeholders})", names)
                tl_info = cur.fetchall()
            
            # Fetch Tasks Stats
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
            total_tasks = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
            completed_tasks = cur.fetchone()[0]
            
            con.close()
            
            # Modal
            t = Toplevel(self.root)
            t.title(f"Project Details: {name}")
            t.geometry("600x700")
            t.minsize(510, 595)  # FIX 7: prevent content clipping when UI changes
            t.resizable(True, True)  # FIX 7: allow resize so no overflow
            t.config(bg=CONTENT_BG)
            
            # Header
            Label(t, text=name, font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=(20, 5))
            Label(t, text=status, font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=ACCENT_BLUE).pack(pady=(0, 20))
            
            # Info Grid
            info = Frame(t, bg=CARD_BG, padx=20, pady=20)
            info.pack(fill=X, padx=20)
            
            def add_row(lbl, val):
                r = Frame(info, bg=CARD_BG)
                r.pack(fill=X, pady=2)
                Label(r, text=lbl, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT, width=15, anchor=W).pack(side=LEFT)
                Label(r, text=val, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                
            add_row("Start Date:", start)
            add_row("Deadline:", end)
            add_row("Progress:", f"{completed_tasks}/{total_tasks} Tasks")
            
            Label(info, text="Description:", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT, width=15, anchor=W).pack(anchor=W, pady=(10, 0))
            Label(info, text=desc, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, wraplength=500, justify=LEFT).pack(anchor=W, pady=(0, 10))
            
            # Team Leaders
            Label(t, text="Team Leaders", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, padx=20, pady=(20, 10))
            
            tl_frame = Frame(t, bg=CARD_BG, padx=20, pady=20)
            tl_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
            
            if not tl_info:
                Label(tl_frame, text="No Team Leader Assigned", bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            else:
                for t_name, t_email, t_mobile, t_dept, t_role in tl_info:
                    r = Frame(tl_frame, bg=CARD_BG, pady=5)
                    r.pack(fill=X)
                    Label(r, text=f"{t_name} ({t_role})", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(r, text=f"Email: {t_email} | Mobile: {t_mobile} | Department: {t_dept}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                    ttk.Separator(tl_frame, orient='horizontal').pack(fill=X, pady=5)
            
            # Milestones
            Label(t, text="Project Milestones", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, padx=20, pady=(0, 10))
            ms_frame = Frame(t, bg=CARD_BG, padx=20, pady=20)
            ms_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
            cols = ("Name", "Due Date", "Status")
            tree_ms = ttk.Treeview(ms_frame, columns=cols, show='headings', height=6)
            for c in cols:
                tree_ms.heading(c, text=c)
                tree_ms.column(c, width=160 if c=="Name" else 120)
            tree_ms.pack(side=LEFT, fill=BOTH, expand=True)
            sb = Scrollbar(ms_frame, orient=VERTICAL, command=tree_ms.yview)
            sb.pack(side=RIGHT, fill=Y)
            tree_ms.configure(yscrollcommand=sb.set)
            def refresh_ms():
                for i in tree_ms.get_children(): tree_ms.delete(i)
                con2 = sqlite3.connect(get_db_path())
                cur2 = con2.cursor()
                cur2.execute("SELECT name, due_date, status FROM project_milestones WHERE project_id=? ORDER BY date(due_date) ASC", (pid,))
                for r in cur2.fetchall():
                    tree_ms.insert("", END, values=r)
                con2.close()
            refresh_ms()
            def add_ms():
                top = Toplevel(self.root)
                top.title("Add Milestone")
                top.geometry("360x220"); top.config(bg=CONTENT_BG)
                f = Frame(top, bg=CONTENT_BG, padx=20, pady=20); f.pack(fill=BOTH, expand=True)
                Label(f, text="Milestone Name", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
                e1 = Entry(f); e1.pack(fill=X, pady=(0,10))
                Label(f, text="Due Date (YYYY-MM-DD)", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
                e2 = Entry(f); e2.pack(fill=X, pady=(0,10))
                Label(f, text="Status", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
                c = ttk.Combobox(f, values=["Planned","In Progress","Completed"], state="readonly"); c.set("Planned"); c.pack(fill=X)
                def save():
                    try:
                        con2 = sqlite3.connect(get_db_path())
                        cur2 = con2.cursor()
                        cur2.execute("INSERT INTO project_milestones (project_id, name, due_date, status, created_at) VALUES (?,?,?,?,?)",
                                     (pid, e1.get(), e2.get(), c.get(), datetime.now().strftime("%Y-%m-%d %H:%M")))
                        con2.commit(); self.refresh_current_panel(); con2.close()
                        refresh_ms(); top.destroy()
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                Button(f, text="Add", bg=ACCENT_GREEN, fg=WHITE, relief=FLAT, command=save).pack(pady=10, fill=X)
            # Enforce read-only mode by showing Milestone creation controls only to Managers, Leaders, and Admins
            if CURRENT_USER_ROLE.lower() in ('team leader', 'project manager', 'manager', 'admin'):
                Button(t, text="Add Milestone", bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, command=add_ms).pack(anchor=E, padx=20, pady=(0,10))

        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_projects_csv(self):
        try:
            file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
            if not file_path: return
            
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # Use current filter logic
            query = "SELECT * FROM projects"
            cur.execute(query)
            rows = cur.fetchall()
            
            # Get headers
            headers = [d[0] for d in cur.description]
            
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
                
            con.close()
            messagebox.showinfo("Success", "Projects exported successfully")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_employee_performance_csv(self):
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
            if not filename: return
            
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            # Fetch all employees
            cursor.execute("SELECT id, name FROM employee")
            employees = cursor.fetchall()
            
            data = []
            today = datetime.now().strftime("%Y-%m-%d")
            
            for emp_id, emp_name in employees:
                # Tasks Assigned
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (emp_name,))
                assigned = cursor.fetchone()[0]
                
                if assigned == 0: continue
                
                # Tasks Completed
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Completed'", (emp_name,))
                completed = cursor.fetchone()[0]
                
                # Delayed Tasks
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND (status='Delayed' OR (status!='Completed' AND due_date < ?))", (emp_name, today))
                delayed = cursor.fetchone()[0]
                
                # Avg Completion Time
                # Use simple heuristic: if created_date and completed_date exist, calc diff. 
                # If not, try (due_date - completed_date) for earliness? No, user wants completion time.
                # If data missing, default to 0.
                cursor.execute("SELECT created_date, completed_date FROM tasks WHERE assigned_to=? AND status='Completed'", (emp_name,))
                times = []
                for c_date, comp_date in cursor.fetchall():
                    if c_date and comp_date:
                        try:
                            d1 = datetime.strptime(c_date, "%Y-%m-%d")
                            d2 = datetime.strptime(comp_date, "%Y-%m-%d")
                            days = (d2 - d1).days
                            times.append(days)
                        except: pass
                
                avg_time = round(sum(times) / len(times), 1) if times else 0
                
                # Performance Rating
                # Formula: (Completed/Assigned * 80%) + ((Assigned-Delayed)/Assigned * 20%) * 100
                rate = (completed / assigned) * 100
                delay_penalty = (delayed / assigned) * 100
                
                score = rate - (delay_penalty * 0.5)
                
                if score >= 85: perf = "Excellent"
                elif score >= 60: perf = "Good"
                elif score >= 40: perf = "Average"
                else: perf = "Poor"

                data.append([f"E{emp_id:03d}", assigned, completed, delayed, avg_time, perf])
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["employee_id", "tasks_assigned", "tasks_completed", "delayed_tasks", "avg_completion_time", "performance"])
                writer.writerows(data)
                
            con.close()
            messagebox.showinfo("Success", "Performance Analysis Exported Successfully")
            
        except Exception as e:
            messagebox.showerror("Error", str(e))


    def add_project_modal(self):
        t = Toplevel(self.root)
        t.title("Create New Project")
        t.config(bg=CONTENT_BG)
        t.minsize(900, 680)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = min(1080, max(900, sw - 180))
        target_h = min(760, max(680, sh - 180))
        x = int((sw / 2) - (target_w / 2))
        y = int((sh / 2) - (target_h / 2))
        t.geometry(f"{target_w}x{target_h}+{x}+{y}")

        modal_bg = CONTENT_BG
        modal_card = CARD_BG
        modal_panel = HEADER_BG
        modal_input = "#253244"
        modal_border = BORDER_COLOR

        shell = Frame(t, bg=modal_bg, padx=28, pady=24)
        shell.pack(fill=BOTH, expand=True)

        scroll_host = Frame(shell, bg=modal_bg)
        scroll_host.pack(fill=BOTH, expand=True)

        modal_canvas = Canvas(scroll_host, bg=modal_bg, highlightthickness=0)
        modal_scroll = ttk.Scrollbar(scroll_host, orient=VERTICAL, command=modal_canvas.yview)
        modal_scroll.pack(side=RIGHT, fill=Y)
        modal_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        modal_canvas.configure(yscrollcommand=modal_scroll.set)

        card = Frame(modal_canvas, bg=modal_card, padx=28, pady=26, highlightbackground=modal_border, highlightthickness=1)
        card_window = modal_canvas.create_window((0, 0), window=card, anchor="nw")

        def _sync_project_modal(_event=None):
            try:
                modal_canvas.configure(scrollregion=modal_canvas.bbox("all"))
            except:
                pass

        def _resize_project_modal(event):
            try:
                modal_canvas.itemconfigure(card_window, width=event.width)
            except:
                pass

        card.bind("<Configure>", _sync_project_modal)
        modal_canvas.bind("<Configure>", _resize_project_modal)

        self._bind_canvas_scrolling(scroll_host, modal_canvas)

        hero = Frame(card, bg=modal_panel, padx=24, pady=22, highlightbackground=modal_border, highlightthickness=1)
        hero.pack(fill=X, pady=(0, 18))

        header = Frame(hero, bg=modal_panel)
        header.pack(fill=X)
        Label(header, text="New Project", font=('Segoe UI', 28, 'bold'), bg=modal_panel, fg=TEXT_WHITE).pack(anchor=W)
        Label(header, text="Create a polished project record with leadership, dates, scope, and rollout context.",
              font=('Segoe UI', 10), bg=modal_panel, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 0))



















        next_step = StringVar(value="done")



























        form = Frame(card, bg=modal_card)
        form.pack(fill=BOTH, expand=True)
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        def make_field(parent, label_text, row, col, rowspan=1):
            holder = Frame(parent, bg=modal_panel, padx=16, pady=14, highlightbackground=modal_border, highlightthickness=1)
            holder.grid(row=row, column=col, sticky="nsew", padx=12, pady=10, rowspan=rowspan)
            Label(holder, text=label_text, bg=modal_panel, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(anchor=W, pady=(0, 6))
            return holder

        def make_entry(parent, label_text, row, col):
            holder = make_field(parent, label_text, row, col)
            wrap = Frame(holder, bg=modal_input, highlightbackground=modal_border, highlightthickness=1)
            wrap.pack(fill=X)
            entry = Entry(wrap, font=('Segoe UI', 11), bg=modal_input, fg=TEXT_WHITE, relief=FLAT, insertbackground=TEXT_WHITE)
            entry.pack(fill=X, padx=12, pady=12, ipady=7)
            return entry

        e_name = make_entry(form, "Project Name", 0, 0)
        e_desc = make_entry(form, "Description", 0, 1)
        
        # Team Leader (Multi-select)
        leader_holder = make_field(form, "Team Leader - Select one", 1, 0, rowspan=2)
        
        # Fetch employees for listbox
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name FROM employee WHERE lower(role)='team leader' ORDER BY name")
        employees = [r[0] for r in cur.fetchall()]
        con.close()

        leader_wrap = Frame(leader_holder, bg=modal_input, highlightbackground=modal_border, highlightthickness=1)
        leader_wrap.pack(fill=BOTH, expand=True)
        leader_scroll = ttk.Scrollbar(leader_wrap, orient=VERTICAL)
        leader_scroll.pack(side=RIGHT, fill=Y)
        lb_leader = Listbox(
            leader_wrap,
            selectmode=SINGLE,
            height=8,
            exportselection=0,
            bg=modal_input,
            fg=TEXT_WHITE,
            selectbackground=PRIMARY_BG,
            selectforeground=TEXT_WHITE,
            relief=FLAT,
            highlightthickness=0,
            activestyle="none",
            yscrollcommand=leader_scroll.set
        )
        for emp in employees:
            lb_leader.insert(END, emp)
        lb_leader.pack(fill=BOTH, expand=True, padx=10, pady=10)
        leader_scroll.config(command=lb_leader.yview)
        Label(leader_holder, text="Assign ownership to one team leader for coordination and progress visibility.",
              bg=modal_panel, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(10, 0))
        Label(leader_holder, text=f"Available: {', '.join(employees) if employees else 'No team leaders found'}",
              bg=modal_panel, fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), wraplength=430, justify=LEFT).pack(anchor=W, pady=(4, 0))

        e_start = make_entry(form, "Start Date (YYYY-MM-DD)", 1, 1)
        e_end = make_entry(form, "End Date (YYYY-MM-DD)", 2, 1)

        def save():
            try:
                # Get selected team leader
                selected_indices = lb_leader.curselection()
                leader_str = lb_leader.get(selected_indices[0]) if selected_indices else ""

                if not e_name.get().strip():
                    messagebox.showerror("Error", "Project name is required", parent=t)
                    return
                if not leader_str:
                    messagebox.showerror("Error", "Please select a team leader", parent=t)
                    return
                
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO projects (name, team_leader, default_assignee, start_date, end_date, description, status) VALUES (?,?,?,?,?,?,'Ongoing')",
                    (e_name.get().strip(), leader_str, leader_str, e_start.get().strip(), e_end.get().strip(), e_desc.get().strip())
                )
                pid = cur.lastrowid
                con.commit(); self.refresh_current_panel()
                con.close()
                log_activity(pid, CURRENT_USER_NAME, f"Created project '{e_name.get().strip()}' with team leader {leader_str}")
                # Capture values before destroying the window
                proj_name = e_name.get().strip()
                selected_flow = next_step.get()
                t.destroy()
                if selected_flow == "auto_plan":
                    self.auto_plan_modal(pid, proj_name, refresh_cb=lambda: self.refresh_projects())
                elif selected_flow == "planner":
                    self.show_project_tasks_modal(pid, proj_name)
                    
                messagebox.showinfo("Success", "Project created successfully.")
                self.refresh_current_page(sync=False)
            except Exception as e:
                # If t still exists, we can show error on it
                try:
                    messagebox.showerror("Error", str(e), parent=t)
                except:
                    messagebox.showerror("Error", str(e))

        footer = Frame(card, bg=modal_panel, padx=18, pady=16, highlightbackground=modal_border, highlightthickness=1)
        footer.pack(fill=X, pady=(18, 0))
        foot_info = Frame(footer, bg=modal_panel)
        foot_info.pack(side=LEFT, fill=X, expand=True)
        Label(foot_info, text="Project Creation Tip", bg=modal_panel, fg=ACCENT_ORANGE, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
        Label(foot_info, text="Choose the leader first, then add dates and a short delivery summary.",
              bg=modal_panel, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(4, 0))
        action_row = Frame(footer, bg=modal_panel)
        action_row.pack(side=RIGHT)
        Button(action_row, text="Cancel", command=t.destroy, bg=ACCENT_HOVER, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'),
               activebackground=PRIMARY_RED_DARK, activeforeground=WHITE, relief=FLAT, padx=18, pady=11, cursor='hand2').pack(side=LEFT, padx=(0, 8))
        Button(action_row, text="Create Project", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'),
               activebackground=PRIMARY_RED_DARK, activeforeground=WHITE, relief=FLAT, padx=24, pady=11, cursor='hand2').pack(side=LEFT)

    def delete_project(self):
        selected = self.proj_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a project to delete")
            return
        
        if not messagebox.askyesno("Confirm", "Are you sure? All tasks associated with this project will also be deleted."):
            return

        item = self.proj_tree.item(selected[0])
        pid = item['values'][0]
        
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            cursor.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
            cursor.execute("DELETE FROM projects WHERE id=?", (pid,))
            con.commit(); self.refresh_current_panel()
            con.close()
            self.refresh_current_page(sync=False)
            messagebox.showinfo("Success", "Project Deleted")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_project_modal(self):
        selected = self.proj_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a project to update")
            return

        item = self.proj_tree.item(selected[0])
        pid = item['values'][0]
        
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        cursor.execute("SELECT name, team_leader, start_date, end_date, description, status FROM projects WHERE id=?", (pid,))
        proj = cursor.fetchone()
        
        cursor.execute("SELECT name FROM employee WHERE lower(role)='team leader' ORDER BY name")
        employees = [r[0] for r in cursor.fetchall()]
        con.close()
        
        if not proj:
            messagebox.showerror("Error", "Project not found")
            return

        t = Toplevel(self.root)
        t.title("Update Project")
        t.geometry("500x600")
        t.minsize(425, 510)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        Label(t, text="Update Project", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        
        f = Frame(t, bg=CONTENT_BG)
        f.pack(fill=BOTH, expand=True, padx=40)
        
        entries = {}
        
        Label(f, text="Project Name", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5,0))
        e_name = Entry(f, font=('Segoe UI', 11))
        e_name.insert(0, proj[0])
        e_name.pack(fill=X)
        entries["name"] = e_name
        
        Label(f, text="Team Leader(s) - Hold Ctrl to select multiple", bg=CONTENT_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(anchor=W, pady=(5,0))
        
        lb_leader = Listbox(f, selectmode=MULTIPLE, height=4, exportselection=0)
        for emp in employees:
            lb_leader.insert(END, emp)
        lb_leader.pack(fill=X)
        
        # Pre-select existing leaders
        current_leaders = proj[1].split(", ") if proj[1] else []
        for i, emp in enumerate(employees):
            if emp in current_leaders:
                lb_leader.selection_set(i)
        
        entries["leader_lb"] = lb_leader
        
        labels = ["Start Date", "End Date", "Description"]
        vals = [proj[2], proj[3], proj[4]]
        keys = ["start", "end", "desc"]
        
        for i, lbl in enumerate(labels):
            Label(f, text=lbl, bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5,0))
            e = Entry(f, font=('Segoe UI', 11))
            e.insert(0, vals[i] if vals[i] else "")
            e.pack(fill=X)
            entries[keys[i]] = e

        Label(f, text="Status", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5,0))
        c_status = ttk.Combobox(f, values=["Ongoing", "Completed", "Delayed", "Not Started"], state="readonly")
        c_status.set(proj[5])
        c_status.pack(fill=X)
        entries["status"] = c_status
        
        def save():
            try:
                # Get selected leaders
                lb = entries["leader_lb"]
                selected_indices = lb.curselection()
                selected_leaders = [lb.get(i) for i in selected_indices]
                leader_str = ", ".join(selected_leaders)
                
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("""
                    UPDATE projects 
                    SET name=?, team_leader=?, start_date=?, end_date=?, description=?, status=?
                    WHERE id=?
                """, (entries["name"].get(), leader_str, entries["start"].get(), 
                      entries["end"].get(), entries["desc"].get(), entries["status"].get(), pid))
                con.commit(); self.refresh_current_panel()
                con.close()
                self.refresh_current_page(sync=False)
                t.destroy()
                messagebox.showinfo("Success", "Project Updated")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(t, text="Update Project", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(pady=20, fill=X, padx=40)

    def load_members(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

        px = self.get_responsive_padx()
        
        # Header
        h_wrap = Frame(self.content_area, bg=CONTENT_BG)
        h_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Team Ecosystem", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Manage resources, evaluate performance, and orchestrate talent delivery.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        # Action Buttons
        btn_box = Frame(h_wrap, bg=CONTENT_BG)
        btn_box.pack(side=RIGHT, pady=10)
        
        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager', 'team leader']:
            Button(btn_box, text="+ ADD MEMBER", font=('Segoe UI', 8, 'bold'), bg=ACCENT_BLUE, fg=WHITE,
                   relief=FLAT, bd=0, padx=16, pady=8, cursor="hand2",
                   command=self.add_member_modal).pack(side=RIGHT, padx=5)

        # Search & Filter Strip
        strip = Frame(self.content_area, bg=CARD_BG, padx=20, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        strip.pack(fill=X, padx=px, pady=(0, 20))
        
        Label(strip, text="🔍", font=('Segoe UI', 11), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=(0, 10))
        self.mem_search_var = StringVar()
        self.mem_search_var.trace("w", lambda *args: self.refresh_members())
        Entry(strip, textvariable=self.mem_search_var, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, insertbackground=WHITE, relief=FLAT, width=40).pack(side=LEFT)
        
        # Main scrollable area
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        self.mem_grid = Frame(canvas, bg=CONTENT_BG)
        
        self.mem_grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.mem_grid, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)
        
        # Summary Statistics for Team
        stats_row = Frame(scrollable_frame if 'scrollable_frame' in locals() else self.mem_grid, bg=CONTENT_BG)
        # Actually load_members uses self.mem_grid directly for items, but I'll add a header stats row
        
        self.refresh_members()

    def refresh_members(self):
        for w in self.mem_grid.winfo_children(): w.destroy()
        
        search = self.mem_search_var.get().lower() if hasattr(self, "mem_search_var") else ""
        
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            # Optimized join query for significantly better performance
            query = """
                SELECT e.id, e.name, e.department, e.role, 
                       COALESCE(t.total, 0), 
                       COALESCE(t.active, 0), 
                       COALESCE(t.perf, 0)
                FROM employee e
                LEFT JOIN (
                    SELECT assigned_to, 
                           COUNT(*) as total,
                           SUM(CASE WHEN status != 'Completed' THEN 1 ELSE 0 END) as active,
                           AVG(CASE WHEN status='Completed' THEN 100 ELSE 0 END) as perf
                    FROM tasks 
                    GROUP BY assigned_to
                ) t ON e.name = t.assigned_to
            """
            
            role = CURRENT_USER_ROLE.lower()
            if role == 'team leader':
                query += f" WHERE reporting_manager = '{CURRENT_USER_NAME}'"
            
            cursor.execute(query)
            members = cursor.fetchall()
            
            cols = 1 if self.root.winfo_width() < 1200 else (2 if self.root.winfo_width() < 1600 else 3)
            for i in range(cols): self.mem_grid.grid_columnconfigure(i, weight=1)
            
            visible_count = 0
            for mem in members:
                mid, name, dept, m_role, total, active, perf = mem
                if search and search not in f"{name} {dept} {m_role}".lower(): continue
                
                self._render_member_card(self.mem_grid, visible_count, cols, mem)
                visible_count += 1
                
            if visible_count == 0:
                Label(self.mem_grid, text="No matching talent found.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            
            con.close()
        except Exception as e:
            debug_log(f"Refresh Members Error: {e}")

    def _render_member_card(self, parent, idx, cols, mem):
        mid, name, dept, m_role, total, active, perf = mem
        r, c = divmod(idx, cols)
        _bg = CARD_BG
        _perf = int(perf) if perf is not None else 0
        _p_color = ACCENT_GREEN if _perf >= 70 else (ACCENT_ORANGE if _perf >= 40 else ACCENT_RED)
        
        card = Frame(parent, bg=_bg, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=r, column=c, sticky="nsew", padx=12, pady=12)
        
        # Glass Header
        head = Frame(card, bg=_bg)
        head.pack(fill=X)
        
        # Avatar with Glow
        ava_size = 48
        ava_outer = Frame(head, bg=_p_color, width=ava_size, height=ava_size)
        ava_outer.pack(side=LEFT)
        ava_outer.pack_propagate(False)
        
        ava = Frame(ava_outer, bg="#1a1f3c", width=ava_size-4, height=ava_size-4)
        ava.place(x=2, y=2)
        ava.pack_propagate(False)
        Label(ava, text=name[0].upper(), font=('Segoe UI', 14, 'bold'), bg="#1a1f3c", fg=WHITE).pack(expand=True)
        
        n_box = Frame(head, bg=_bg, padx=15)
        n_box.pack(side=LEFT, fill=Y)
        Label(n_box, text=name, font=('Segoe UI', 12, 'bold'), bg=_bg, fg=TEXT_WHITE).pack(anchor=W)
        
        role_pill = Frame(n_box, bg="#1e2540", padx=8, pady=2)
        role_pill.pack(anchor=W, pady=(4, 0))
        Label(role_pill, text=m_role.upper(), font=('Segoe UI', 7, 'bold'), bg="#1e2540", fg=ACCENT_BLUE).pack()
        
        # Performance Indicator (Top Right)
        p_box = Frame(head, bg=_bg)
        p_box.pack(side=RIGHT, anchor=N)
        Label(p_box, text="PERFORMANCE", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT).pack()
        Label(p_box, text=f"{_perf}%", font=('Segoe UI', 11, 'bold'), bg=_bg, fg=_p_color).pack()

        # Stats Grid (Glassy)
        stats_f = Frame(card, bg="#1a2035", padx=15, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        stats_f.pack(fill=X, pady=(20, 15))
        
        def _row(parent, l, v, c=TEXT_WHITE):
            r = Frame(parent, bg="#1a2035")
            r.pack(fill=X, pady=3)
            Label(r, text=l, font=('Segoe UI', 7, 'bold'), bg="#1a2035", fg=MUTED_TEXT).pack(side=LEFT)
            Label(r, text=str(v).upper(), font=('Segoe UI', 8, 'bold'), bg="#1a2035", fg=c).pack(side=RIGHT)

        _row(stats_f, "DEPARTMENT", dept or "GENERAL")
        _row(stats_f, "ACTIVE LOAD", f"{active} TASKS", ACCENT_BLUE)
        # Actions
        acts = Frame(card, bg=_bg)
        acts.pack(fill=X, pady=(10, 0))
        
        def _view(): self.view_member_profile_modern(mem)
        
        Button(acts, text="VIEW PROFILE", font=('Segoe UI', 8, 'bold'), bg=ACCENT_BLUE, fg=WHITE,
               relief=FLAT, bd=0, padx=15, pady=8, cursor="hand2", command=_view).pack(side=LEFT)
        
        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager']:
             Button(acts, text="⚙️ SETTINGS", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT,
                    relief=FLAT, bd=0, padx=12, pady=8, cursor="hand2", command=lambda: self.edit_member_modal(mid)).pack(side=RIGHT)

        def _on_e(e): 
            card.config(highlightbackground=ACCENT_BLUE, bg="#1f2544")
            for w in card.winfo_children(): 
                try: 
                    if w.winfo_class() == 'Frame' and w != stats_f: w.config(bg="#1f2544")
                    if w.winfo_class() == 'Label': w.config(bg="#1f2544")
                except: pass
        def _on_l(e): 
            card.config(highlightbackground=BORDER_COLOR, bg=CARD_BG)
            for w in card.winfo_children(): 
                try: 
                    if w.winfo_class() == 'Frame' and w != stats_f: w.config(bg=CARD_BG)
                    if w.winfo_class() == 'Label': w.config(bg=CARD_BG)
                except: pass
        card.bind("<Enter>", _on_e); card.bind("<Leave>", _on_l)

    def view_member_profile_modern(self, mem):
        mid, name, dept, m_role, total, active, perf = mem
        
        t = Toplevel(self.root)
        t.title(f"Profile: {name}")
        t.geometry("800x600")
        t.configure(bg=CONTENT_BG)
        t.transient(self.root); t.grab_set()
        
        # Center window
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        t.geometry(f"800x600+{(sw-800)//2}+{(sh-600)//2}")
        
        # Left Panel (Bio)
        side = Frame(t, bg=CARD_BG, width=280)
        side.pack(side=LEFT, fill=Y)
        side.pack_propagate(False)
        
        Frame(side, bg=ACCENT_BLUE, height=4).pack(fill=X)
        
        ava_big = Frame(side, bg="#2a3352", width=100, height=100)
        ava_big.pack(pady=40)
        ava_big.pack_propagate(False)
        Label(ava_big, text=name[0].upper(), font=('Segoe UI', 40, 'bold'), bg="#2a3352", fg=WHITE).pack(expand=True)
        
        Label(side, text=name, font=('Segoe UI', 18, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack()
        Label(side, text=m_role.upper(), font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE, pady=5).pack()
        
        sep = Frame(side, bg=BORDER_COLOR, height=1, width=200)
        sep.pack(pady=20)
        
        for l, v in [("Dept", dept), ("ID", f"PMS-{mid:04}"), ("Access", "Standard")]:
            f = Frame(side, bg=CARD_BG, padx=30, pady=5)
            f.pack(fill=X)
            Label(f, text=l, font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(f, text=v, font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=RIGHT)
            
        # Right Panel (Analytics)
        main = Frame(t, bg=CONTENT_BG, padx=40, pady=40)
        main.pack(side=LEFT, fill=BOTH, expand=True)
        
        Label(main, text="Delivery Analytics", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        
        metrics = Frame(main, bg=CONTENT_BG, pady=25)
        metrics.pack(fill=X)
        
        _perf = int(perf) if perf is not None else 0
        for m_lbl, m_val, m_clr in [
            ("LIFETIME TASKS", total, WHITE),
            ("ACTIVE LOAD", active, ACCENT_BLUE),
            ("SUCCESS RATE", f"{_perf}%", ACCENT_GREEN)
        ]:
            m_card = Frame(metrics, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
            m_card.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(m_card, text=m_lbl, font=('Segoe UI', 7, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            Label(m_card, text=str(m_val), font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=m_clr).pack(anchor=W, pady=(5, 0))
            
        # Recent Tasks Table (Modernized)
        Label(main, text="RECENT INITIATIVES", font=('Segoe UI', 8, 'bold'), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(10, 5))
        t_frame = Frame(main, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        t_frame.pack(fill=BOTH, expand=True)
        
        tree = ttk.Treeview(t_frame, columns=("Task", "Status"), show='headings', style="Prod.Treeview")
        tree.heading("Task", text="TASK NAME", anchor=W)
        tree.heading("Status", text="STATUS", anchor=CENTER)
        tree.pack(fill=BOTH, expand=True)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT title, status FROM tasks WHERE assigned_to = ? ORDER BY id DESC LIMIT 5", (name,))
            for r in cur.fetchall(): tree.insert("", END, values=r)
            con.close()
        except: pass
        
        Button(main, text="CLOSE PROFILE", font=('Segoe UI', 9, 'bold'), bg=PRIMARY_BG, fg=WHITE, 
               relief=FLAT, padx=25, pady=12, command=t.destroy).pack(anchor=E, pady=25)

    def find_employee_tl_modal(self):
        t = Toplevel(self.root)
        t.title("Find Team Leader")
        t.geometry("450x300")
        t.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        Label(t, text="Select Employee", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=(20, 5))
        f = Frame(t, bg=CARD_BG, padx=20, pady=20)
        f.pack(fill=BOTH, expand=True, padx=20, pady=10)
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name FROM employee ORDER BY name ASC")
        names = [r[0] for r in cur.fetchall()]
        con.close()
        emp_var = StringVar()
        cb = ttk.Combobox(f, textvariable=emp_var, values=names, state="readonly")
        cb.pack(fill=X)
        res_frame = Frame(f, bg=CARD_BG)
        res_frame.pack(fill=BOTH, expand=True, pady=(15, 0))
        tl_val = StringVar(value="Team Leader: ")
        from_tasks_val = StringVar(value="From Tasks: ")
        Label(res_frame, textvariable=tl_val, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(anchor=W, pady=5)
        Label(res_frame, textvariable=from_tasks_val, bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W)
        def refresh():
            emp = emp_var.get()
            if not emp:
                return
            con2 = sqlite3.connect(get_db_path())
            cur2 = con2.cursor()
            cur2.execute("SELECT reporting_manager FROM employee WHERE name=?", (emp,))
            r = cur2.fetchone()
            tl = (r[0] if r and r[0] else "Unlinked")
            tl_val.set(f"Team Leader: {tl}")
            cur2.execute("""
                SELECT DISTINCT p.team_leader 
                FROM tasks t JOIN projects p ON t.project_id = p.id
                WHERE t.assigned_to=?
            """, (emp,))
            rows2 = [row[0] for row in cur2.fetchall() if row and row[0]]
            if rows2:
                from_tasks_val.set(f"From Tasks: {', '.join(rows2)}")
            else:
                from_tasks_val.set("From Tasks: N/A")
            con2.close()
        cb.bind("<<ComboboxSelected>>", lambda e: refresh())
        if names:
            emp_var.set(names[0])
            refresh()
        Button(t, text="Close", bg=ACCENT_RED, fg=TEXT_WHITE, relief=FLAT, command=t.destroy).pack(pady=10)
        
    def add_member_to_my_team_modal(self):
        t = Toplevel(self.root)
        t.title("Add Team Member")
        t.geometry("420x220")
        t.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        Label(t, text="Select Employee to Link", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=(20, 5))
        f = Frame(t, bg=CARD_BG, padx=20, pady=20)
        f.pack(fill=BOTH, expand=True, padx=20, pady=10)
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name FROM employee WHERE (role='Team Member' OR role='Senior Employee') AND (reporting_manager IS NULL OR reporting_manager='')")
        names = [r[0] for r in cur.fetchall()]
        con.close()
        emp_var = StringVar()
        cb = ttk.Combobox(f, textvariable=emp_var, values=names, state="readonly")
        cb.pack(fill=X)
        def link_now():
            emp = emp_var.get()
            if not emp:
                return
            con2 = sqlite3.connect(get_db_path())
            cur2 = con2.cursor()
            cur2.execute("UPDATE employee SET reporting_manager=? WHERE name=?", (CURRENT_USER_NAME, emp))
            con2.commit(); self.refresh_current_panel()
            con2.close()
            self.refresh_members()
            t.destroy()
            messagebox.showinfo("Success", f"Linked {emp} to your team")
        Button(f, text="Link to My Team", bg=ACCENT_BLUE, fg=TEXT_WHITE, relief=FLAT, command=link_now).pack(pady=10)
        Button(t, text="Close", bg=ACCENT_RED, fg=TEXT_WHITE, relief=FLAT, command=t.destroy).pack(pady=5)
        
    def assign_tl_modal(self):
        t = Toplevel(self.root)
        t.title("Assign Team Leader")
        t.geometry("460x260")
        t.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        f = Frame(t, bg=CARD_BG, padx=20, pady=20)
        f.pack(fill=BOTH, expand=True, padx=20, pady=15)
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name FROM employee WHERE lower(role) IN ('team member','senior employee')")
        emp_names = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT name FROM employee WHERE lower(role)='team leader'")
        tl_names = [r[0] for r in cur.fetchall()]
        con.close()
        Label(f, text="Employee", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        emp_var = StringVar()
        cb_emp = ttk.Combobox(f, textvariable=emp_var, values=emp_names, state="readonly")
        cb_emp.pack(fill=X, pady=(0,10))
        Label(f, text="Team Leader", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        tl_var = StringVar()
        cb_tl = ttk.Combobox(f, textvariable=tl_var, values=tl_names, state="readonly")
        cb_tl.pack(fill=X)
        def assign_now():
            e = emp_var.get()
            tl = tl_var.get()
            if not e or not tl: 
                return
            con2 = sqlite3.connect(get_db_path())
            con2.execute("UPDATE employee SET reporting_manager=? WHERE name=?", (tl, e))
            con2.commit(); self.refresh_current_panel()
            con2.close()
            self.refresh_members()
            t.destroy()
            messagebox.showinfo("Success", f"Assigned {e} to {tl}")
        Button(f, text="Assign", bg=ACCENT_BLUE, fg=TEXT_WHITE, relief=FLAT, command=assign_now).pack(pady=12)
        Button(t, text="Close", bg=ACCENT_RED, fg=TEXT_WHITE, relief=FLAT, command=t.destroy).pack()
    def add_member_modal(self):
        t = Toplevel(self.root)
        t.title("Add Team Member / Leader")
        t.config(bg=CONTENT_BG)
        t.minsize(760, 620)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        modal_w = min(980, max(760, sw - 260))
        modal_h = min(760, max(620, sh - 220))
        x = int((sw / 2) - (modal_w / 2))
        y = int((sh / 2) - (modal_h / 2))
        t.geometry(f"{modal_w}x{modal_h}+{x}+{y}")

        shell = Frame(t, bg=CONTENT_BG, padx=28, pady=24)
        shell.pack(fill=BOTH, expand=True)

        card = Frame(shell, bg=CARD_BG, padx=26, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=BOTH, expand=True)

        hero = Frame(card, bg=HEADER_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        # hero.pack(fill=X, pady=(0, 18)) # Removed per user request

        Label(hero, text="Add Member", font=('Segoe UI', 28, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(hero, text="Create a polished staff profile with role, department, and contact details in one place.",
              font=('Segoe UI', 10), bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 0))

        chip_row = Frame(hero, bg=HEADER_BG)
        chip_row.pack(anchor=W, pady=(14, 0))
        Label(chip_row, text=" Team Setup ", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(chip_row, text=" Secure Access ", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(chip_row, text=" Role Ready ", bg=ACCENT_ORANGE, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT)

        insights = Frame(hero, bg=HEADER_BG)
        insights.pack(fill=X, pady=(16, 0))
        for idx, (title, value, accent) in enumerate((
            ("Default Role", "Team Member", ACCENT_BLUE),
            ("Password Setup", "Mobile Number", ACCENT_GREEN),
            ("Access Model", "Role-Based", PRIMARY_BG),
        )):
            tile = Frame(insights, bg="#253244", padx=14, pady=12, highlightbackground=accent, highlightthickness=1)
            tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0 if idx == 0 else 10, 0))
            Label(tile, text=title.upper(), bg="#253244", fg=MUTED_TEXT, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
            Label(tile, text=value, bg="#253244", fg=TEXT_WHITE, font=('Segoe UI', 12, 'bold')).pack(anchor=W, pady=(6, 0))

        form_container = Frame(card, bg=CARD_BG)
        form_container.pack(fill=BOTH, expand=True)


        # FAST ONBOARD SECTION (Beautified)
        fast_f = Frame(form_container, bg=HEADER_BG, padx=24, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
        fast_f.pack(fill=X, pady=(0, 25))
        
        Label(fast_f, text="⚡ FAST ONBOARD", font=('Segoe UI', 14, 'bold'), bg=HEADER_BG, fg=ACCENT_BLUE).pack(anchor=W)
        Label(fast_f, text="Select an existing employee from the system to instantly add to your team.", 
              font=('Segoe UI', 10), bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(2, 20))
        
        pick_wrap = Frame(fast_f, bg=HEADER_BG)
        pick_wrap.pack(fill=X)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT name FROM employee WHERE (reporting_manager IS NULL OR reporting_manager = '') AND lower(role) NOT IN ('team leader', 'project manager', 'admin')")
            avail = [r[0] for r in cur.fetchall()]
            con.close()
        except: avail = []
        
        # Embedded look for combobox
        combo_wrap = Frame(pick_wrap, bg=INPUT_BG)
        combo_wrap.pack(side=LEFT, fill=X, expand=True, padx=(0, 15))
        
        c_pick = ttk.Combobox(combo_wrap, values=avail, font=('Segoe UI', 11), style='Employee.TCombobox', state="readonly")
        c_pick.pack(fill=X, padx=2, pady=2)
        if avail: c_pick.set("--- Select Employee ---")
        else: c_pick.set("No unassigned employees found")
        
        def fast_assign():
            target = c_pick.get()
            if target and target != "--- Select Employee ---" and target != "No unassigned employees found":
                try:
                    c = sqlite3.connect(get_db_path())
                    cu = c.cursor()
                    cu.execute("UPDATE employee SET reporting_manager=? WHERE name=?", (CURRENT_USER_NAME, target))
                    c.commit(); self.refresh_current_panel(); c.close()
                    self.refresh_members()
                    t.destroy()
                    messagebox.showinfo("Success", f"{target} has been onboarded to your team.")
                except Exception as e: messagebox.showerror("Error", str(e))
            else:
                messagebox.showwarning("Select Member", "Please select a valid employee from the list.")

        btn_fast = Button(pick_wrap, text="ONBOARD NOW", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 10, 'bold'),
                          relief=FLAT, padx=24, pady=10, cursor='hand2', command=fast_assign)
        btn_fast.pack(side=RIGHT)
        self._apply_hover_effect(btn_fast, ACCENT_BLUE, "#1c223d")

        # Show manual form by default
        show_manual = CURRENT_USER_ROLE.lower() != 'team leader'
        
        if show_manual:
            manual_box = Frame(form_container, bg=CARD_BG)
            manual_box.pack(fill=BOTH, expand=True)

            form = Frame(manual_box, bg=CARD_BG)
            form.pack(fill=BOTH, expand=True)
            form.grid_columnconfigure(0, weight=1)
            form.grid_columnconfigure(1, weight=1)

            entries = {}

            def make_field(parent, label_text, row, col):
                holder = Frame(parent, bg=HEADER_BG, padx=16, pady=14, highlightbackground=BORDER_COLOR, highlightthickness=1)
                holder.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
                Label(holder, text=label_text, bg=HEADER_BG, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(anchor=W, pady=(0, 6))
                return holder

            def make_entry(parent, label_text, row, col):
                holder = make_field(parent, label_text, row, col)
                wrap = Frame(holder, bg="#253244", highlightbackground=BORDER_COLOR, highlightthickness=1)
                wrap.pack(fill=X)
                entry = Entry(wrap, font=('Segoe UI', 11), bg="#253244", fg=TEXT_WHITE, relief=FLAT, insertbackground=TEXT_WHITE)
                entry.pack(fill=X, padx=12, pady=12, ipady=7)
                return entry

            e_fname = make_entry(form, "First Name", 0, 0)
            entries["First Name"] = e_fname

            e_lname = make_entry(form, "Last Name", 0, 1)
            entries["Last Name"] = e_lname

            entries["Mobile"] = make_entry(form, "Mobile", 1, 0)
            entries["Email"] = make_entry(form, "Email", 1, 1)
        else:
            # Show current team members for Team Leaders to fill space
            team_f = Frame(form_container, bg=HEADER_BG, padx=24, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
            team_f.pack(fill=BOTH, expand=True, pady=(0, 25))
            
            Label(team_f, text="👥 CURRENT TEAM MEMBERS", font=('Segoe UI', 14, 'bold'), bg=HEADER_BG, fg=ACCENT_GREEN).pack(anchor=W)
            Label(team_f, text="Members currently assigned to your team.", 
                  font=('Segoe UI', 10), bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(2, 10))
            
            tree_frame = Frame(team_f, bg=HEADER_BG)
            tree_frame.pack(fill=BOTH, expand=True)
            
            columns = ('Name', 'Department', 'Role')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', style='Treeview')
            scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=150)
                
            tree.pack(side=LEFT, fill=BOTH, expand=True)
            scrollbar.pack(side=RIGHT, fill=Y)
            
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("SELECT name, department, role FROM employee WHERE reporting_manager=?", (CURRENT_USER_NAME,))
                for row in cur.fetchall():
                    tree.insert('', END, values=row)
                con.close()
            except Exception as e:
                print(f"Error loading team: {e}")
                
            # Function to remove the selected member from the team
            def remove_member():
                selected_item = tree.selection()
                if not selected_item:
                    messagebox.showwarning("No Selection", "Please select a team member from the list to remove.", parent=t)
                    return
                
                item_values = tree.item(selected_item, 'values')
                if not item_values:
                    return
                
                name = item_values[0]
                
                if messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove {name} from your team?", parent=t):
                    try:
                        con = sqlite3.connect(get_db_path())
                        cur = con.cursor()
                        cur.execute("UPDATE employee SET reporting_manager=NULL WHERE name=? AND reporting_manager=?", (name, CURRENT_USER_NAME))
                        con.commit()
                        con.close()
                        
                        tree.delete(selected_item)
                        self.refresh_current_panel()
                        self.refresh_members()
                        
                        # Refresh Fast Onboard unassigned employees list combobox
                        try:
                            con_ref = sqlite3.connect(get_db_path())
                            cur_ref = con_ref.cursor()
                            cur_ref.execute("SELECT name FROM employee WHERE (reporting_manager IS NULL OR reporting_manager = '') AND lower(role) NOT IN ('team leader', 'project manager', 'admin')")
                            new_avail = [r[0] for r in cur_ref.fetchall()]
                            con_ref.close()
                            c_pick.config(values=new_avail)
                            if new_avail:
                                c_pick.set("--- Select Employee ---")
                            else:
                                c_pick.set("No unassigned employees found")
                        except Exception as ex:
                            print(f"Error reloading avail combobox: {ex}")
                            
                        messagebox.showinfo("Success", f"{name} has been removed from your team successfully.", parent=t)
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to remove member: {e}", parent=t)
                        
            # Button Row below Treeview
            btn_row = Frame(team_f, bg=HEADER_BG)
            btn_row.pack(fill=X, pady=(15, 0))
            
            btn_remove = Button(btn_row, text="❌ REMOVE SELECTED MEMBER", font=('Segoe UI', 9, 'bold'),
                                bg=ACCENT_RED, fg=WHITE, relief=FLAT, padx=20, pady=10, cursor='hand2',
                                command=remove_member)
            btn_remove.pack(side=RIGHT)
            self._apply_hover_effect(btn_remove, ACCENT_RED, "#b91c1c")

        def save():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                fname = entries["First Name"].get().strip()
                lname = entries["Last Name"].get().strip()
                mobile = entries["Mobile"].get().strip()
                email = entries["Email"].get().strip()
                department = "N/A"
                role = "Team Member"

                if not fname or not lname:
                     messagebox.showerror("Error", "First and Last Name are required", parent=t)
                     con.close()
                     return
                if not mobile:
                     messagebox.showerror("Error", "Mobile number is required", parent=t)
                     con.close()
                     return
                
                full_name = f"{fname} {lname}"
                
                # Default password is mobile
                pw = hashlib.sha256(mobile.encode()).hexdigest()
                cur.execute("INSERT INTO employee (name, mobile, email, department, password, role) VALUES (?,?,?,?,?,?)",
                            (full_name, mobile, email, department, pw, role))
                con.commit(); self.refresh_current_panel()
                con.close()
                self.refresh_members()
                t.destroy()
                messagebox.showinfo("Success", f"{full_name} added successfully.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        footer = Frame(card, bg=HEADER_BG, padx=24, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        footer.pack(fill=X, pady=(20, 0))
        
        # Left side: Tips and Notes
        foot_info = Frame(footer, bg=HEADER_BG)
        foot_info.pack(side=LEFT, fill=X, expand=True)
        
        if show_manual:
            # Note 1
            note1_f = Frame(foot_info, bg=HEADER_BG)
            note1_f.pack(fill=X, pady=(0, 10))
            Label(note1_f, text="🔑 Account Setup Note:", bg=HEADER_BG, fg=ACCENT_ORANGE, font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
            Label(note1_f, text=" The member's initial password will be set from the mobile number.",
                  bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=LEFT)
                  
            # Note 2
            note2_f = Frame(foot_info, bg=HEADER_BG)
            note2_f.pack(fill=X)
            Label(note2_f, text="💡 Member Creation Tip:", bg=HEADER_BG, fg=ACCENT_GREEN, font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
            Label(note2_f, text=" Use the correct role from the start so dashboard access and permissions stay accurate.",
                  bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=LEFT)
        
        # Right side: Action Buttons
        action_row = Frame(footer, bg=HEADER_BG)
        action_row.pack(side=RIGHT, padx=(20, 0))
        
        btn_cancel = Button(action_row, text="Cancel", command=t.destroy, bg=ACCENT_HOVER, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'),
               relief=FLAT, padx=20, pady=10, cursor='hand2')
        btn_cancel.pack(side=LEFT, padx=(0, 10))
        self._apply_hover_effect(btn_cancel, ACCENT_HOVER, "#1c223d")
        
        if show_manual:
            btn_save = Button(action_row, text="Save Member", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'),
                   relief=FLAT, padx=28, pady=10, cursor='hand2')
            btn_save.pack(side=LEFT)
            self._apply_hover_effect(btn_save, PRIMARY_BG, "#1c223d")

    def delete_member(self):
        selected = self.mem_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a member to delete")
            return
        
        if not messagebox.askyesno("Confirm", "Are you sure you want to delete this member?"):
            return

        item = self.mem_tree.item(selected[0])
        mem_id = item['values'][0]
        
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            cursor.execute("DELETE FROM employee WHERE id=?", (mem_id,))
            con.commit(); self.refresh_current_panel()
            con.close()
            self.refresh_members()
            messagebox.showinfo("Success", "Member deleted")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def update_member_modal(self):
        selected = self.mem_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a member to update")
            return

        item = self.mem_tree.item(selected[0])
        mem_id = item['values'][0]
        
        # Fetch current data from DB to be accurate
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT name, mobile, email, department, role FROM employee WHERE id=?", (mem_id,))
            row = cur.fetchone()
            con.close()
            if not row: return
            name, mobile, email, dept, role = row
        except: return

        t = Toplevel(self.root)
        t.title("Update Member")
        t.geometry("400x550")
        t.minsize(400, 467)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        Label(t, text="Update Member", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        f = Frame(t, bg=CONTENT_BG, padx=40)
        f.pack(fill=BOTH, expand=True)
        
        entries = {}
        fields = [("Name", name), ("Mobile", mobile), ("Email", email), ("Department", dept)]
        for field, val in fields:
            Label(f, text=field, bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5,0))
            e = Entry(f, font=('Segoe UI', 11))
            e.insert(0, val)
            e.pack(fill=X, pady=(0, 10))
            entries[field] = e
            
        Label(f, text="Role", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5,0))
        c_role = ttk.Combobox(f, values=["Team Member", "Team Leader", "Senior Employee", "Project Manager"], state="readonly")
        c_role.set(role)
        c_role.pack(fill=X, pady=(0, 10))
        entries["Role"] = c_role

        def save():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("UPDATE employee SET name=?, mobile=?, email=?, department=?, role=? WHERE id=?",
                            (entries["Name"].get(), entries["Mobile"].get(), entries["Email"].get(), 
                             entries["Department"].get(), entries["Role"].get(), mem_id))
                con.commit(); self.refresh_current_panel()
                con.close()
                self.refresh_members()
                t.destroy()
                messagebox.showinfo("Success", "Member Updated")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(t, text="Update Member", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(pady=20, fill=X, padx=40)
        
        if CURRENT_USER_ROLE.lower() == 'team leader':
            def link_to_me():
                try:
                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()
                    cur.execute("UPDATE employee SET reporting_manager=? WHERE id=?", (CURRENT_USER_NAME, mem_id))
                    con.commit(); self.refresh_current_panel()
                    con.close()
                    self.refresh_members()
                    t.destroy()
                    messagebox.showinfo("Success", "Linked to your team")
                except Exception as e:
                    messagebox.showerror("Error", str(e))
            
            def unlink_from_me():
                try:
                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()
                    cur.execute("UPDATE employee SET reporting_manager=NULL WHERE id=?", (mem_id,))
                    con.commit(); self.refresh_current_panel()
                    con.close()
                    self.refresh_members()
                    t.destroy()
                    messagebox.showinfo("Success", "Unlinked from your team")
                except Exception as e:
                    messagebox.showerror("Error", str(e))
            btn_row = Frame(t, bg=CONTENT_BG)
            btn_row.pack(fill=X, padx=40, pady=(0, 20))
            Button(btn_row, text="Link to My Team", command=link_to_me, bg=ACCENT_GREEN, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT).pack(side=LEFT, expand=True, fill=X, padx=5)
            Button(btn_row, text="Unlink", command=unlink_from_me, bg=ACCENT_RED, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT).pack(side=LEFT, expand=True, fill=X, padx=5)

    def load_project_status_panel(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

        px = self.get_responsive_padx()
        
        # Header with Summary Stats
        header_wrap = Frame(self.content_area, bg=CONTENT_BG)
        header_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(header_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Project Status Overview", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Live tracking of all active initiatives and delivery health.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        # Filter Chip Group
        filter_box = Frame(header_wrap, bg=CONTENT_BG)
        filter_box.pack(side=RIGHT, pady=10)
        
        if not hasattr(self, "pm_status_filter"): self.pm_status_filter = StringVar(value="All")
        
        for st in ["All", "Ongoing", "Completed", "Delayed"]:
            is_active = self.pm_status_filter.get() == st
            f_bg = ACCENT_BLUE if is_active else CARD_BG
            f_fg = WHITE if is_active else MUTED_TEXT
            btn = Button(filter_box, text=st.upper(), font=('Segoe UI', 8, 'bold'), bg=f_bg, fg=f_fg,
                        relief=FLAT, bd=0, padx=12, pady=6, cursor="hand2",
                        command=lambda s=st: [self.pm_status_filter.set(s), self.load_project_status_panel()])
            btn.pack(side=LEFT, padx=4)

        # Main scrollable area
        list_container = Frame(self.content_area, bg=CONTENT_BG)
        list_container.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        canvas = Canvas(list_container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_canvas_resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(list_container, canvas)

        # Data Fetch
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            f_query = ""
            f_val = self.pm_status_filter.get()
            if f_val != "All": f_query = f"WHERE status='{f_val}'"
            
            cursor.execute(f"SELECT id, name, team_leader, status, start_date, end_date FROM projects {f_query} ORDER BY name")
            projects = cursor.fetchall()
            
            # Summary Metrics
            cursor.execute("SELECT status, COUNT(*) FROM projects GROUP BY status")
            stats = dict(cursor.fetchall())
            
            metrics_row = Frame(scrollable_frame, bg=CONTENT_BG)
            metrics_row.pack(fill=X, pady=(0, 30))

            def render_stat_glass(parent, title, value, color, icon):
                card = Frame(parent, bg=CARD_BG, padx=22, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
                card.pack(side=LEFT, padx=(0, 20), expand=True, fill=X)
                
                # Premium micro-interaction: active border glow on hover
                def on_enter(e):
                    card.config(highlightbackground=color, highlightthickness=1)
                def on_leave(e):
                    card.config(highlightbackground=BORDER_COLOR, highlightthickness=1)
                
                card.bind("<Enter>", on_enter)
                card.bind("<Leave>", on_leave)
                
                top = Frame(card, bg=CARD_BG)
                top.pack(fill=X)
                
                # Fix: Add explicit high-contrast foreground color to icons so they are beautifully visible
                icon_lbl = Label(top, text=icon, font=('Segoe UI', 14), bg=CARD_BG, fg=color)
                icon_lbl.pack(side=LEFT)
                
                # Brighter, high-fidelity title text
                title_lbl = Label(top, text=title, font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg="#9aa3c2")
                title_lbl.pack(side=LEFT, padx=10)
                
                # Premium large bold values
                val_lbl = Label(card, text=str(value), font=('Segoe UI', 32, 'bold'), bg=CARD_BG, fg=color)
                val_lbl.pack(anchor=W, pady=(12, 0))
                
                # Bottom accent indicator line
                ind = Frame(card, bg=color, height=3)
                ind.pack(fill=X, pady=(15, 0))
                
                # Propagate hover events across child elements
                for w in [top, icon_lbl, title_lbl, val_lbl, ind]:
                    w.bind("<Enter>", on_enter)
                    w.bind("<Leave>", on_leave)

            render_stat_glass(metrics_row, "ACTIVE PROJECTS", stats.get("Ongoing", 0), ACCENT_BLUE, "📁")
            render_stat_glass(metrics_row, "DELIVERY RISKS", stats.get("Delayed", 0), ACCENT_RED, "⚠️")
            render_stat_glass(metrics_row, "SUCCESSFUL", stats.get("Completed", 0), ACCENT_GREEN, "🏆")

            if not projects:
                Label(scrollable_frame, text="No projects matching criteria.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for idx, (pid, pname, leader, status, start, end) in enumerate(projects):
                    # Fetch task counts
                    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) FROM tasks WHERE project_id=?", (pid,))
                    t_res = cursor.fetchone()
                    total, done = t_res[0] or 0, t_res[1] or 0
                    prog = int((done/total)*100) if total > 0 else 0
                    
                    self._render_status_row(scrollable_frame, pid, pname, leader, status, prog, end)
            
            con.close()
        except Exception as e:
            debug_log(f"Error loading status panel: {e}")

    def _render_status_row(self, parent, pid, name, leader, status, prog, deadline):
        _bg = CARD_BG
        _s_color = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_BLUE, "Delayed": ACCENT_RED}.get(status, MUTED_TEXT)
        _icon = {"Completed": "✅", "Ongoing": "⚡", "Delayed": "🚨"}.get(status, "📄")
        
        row = Frame(parent, bg=_bg, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        row.pack(fill=X, pady=8)
        
        # Glow Effect on active row (managed by hover)
        row.glow = Frame(row, bg=_bg, width=4)
        row.glow.pack(side=LEFT, fill=Y, padx=(0, 20))

        # Project Info
        info = Frame(row, bg=_bg)
        info.pack(side=LEFT, fill=Y)
        
        title_row = Frame(info, bg=_bg)
        title_row.pack(anchor=W)
        Label(title_row, text=_icon, font=('Segoe UI', 12), bg=_bg, fg=_s_color).pack(side=LEFT, padx=(0, 10))
        Label(title_row, text=name, font=('Segoe UI', 13, 'bold'), bg=_bg, fg=TEXT_WHITE).pack(side=LEFT)
        
        Label(info, text=f"👤 Lead: {leader or 'Unassigned'}", font=('Segoe UI', 9), bg=_bg, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
        
        # Status Badge (Modern Pill)
        s_box = Frame(row, bg=_bg, width=150)
        s_box.pack(side=LEFT, padx=40)
        s_badge = Frame(s_box, bg="#1a2035", highlightbackground=_s_color, highlightthickness=1, padx=12, pady=5)
        s_badge.pack()
        Label(s_badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg="#1a2035", fg=_s_color).pack()
        
        # Progress Visualization
        p_box = Frame(row, bg=_bg)
        p_box.pack(side=LEFT, fill=X, expand=True, padx=20)
        
        p_header = Frame(p_box, bg=_bg)
        p_header.pack(fill=X)
        Label(p_header, text="Delivery Velocity", font=('Segoe UI', 8, 'bold'), bg=_bg, fg=MUTED_TEXT).pack(side=LEFT)
        Label(p_header, text=f"{prog}%", font=('Segoe UI', 9, 'bold'), bg=_bg, fg=_s_color).pack(side=RIGHT)
        
        # Custom Track with Rounded look
        track = Frame(p_box, bg="#1e2540", height=8)
        track.pack(fill=X, pady=(6, 0))
        if prog > 0:
            # Multi-layered fill for glow
            fill_glow = Frame(track, bg=_s_color, height=8)
            fill_glow.place(x=0, y=0, relwidth=min(prog/100, 1.0))
            
        # Health Indicator
        health_box = Frame(row, bg=_bg, padx=20)
        health_box.pack(side=LEFT)
        h_color = _s_color if status != "Delayed" else ACCENT_RED
        Label(health_box, text="HEALTH", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT).pack()
        Label(health_box, text="●", font=('Segoe UI', 12), bg=_bg, fg=h_color).pack()

        # Deadline
        d_box = Frame(row, bg=_bg, width=130)
        d_box.pack(side=RIGHT, padx=(20, 0))
        Label(d_box, text="DEADLINE", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT).pack()
        Label(d_box, text=deadline or "TBD", font=('Segoe UI', 10, 'bold'), bg=_bg, fg=TEXT_WHITE).pack()

        def _on_e(e): 
            row.config(highlightbackground=_s_color, highlightthickness=1)
            row.config(bg="#1f2544")
            row.glow.config(bg=_s_color)
            for w in row.winfo_children(): 
                try: 
                    if w != s_badge and w.winfo_class() == 'Frame':
                        w.config(bg="#1f2544")
                        for cw in w.winfo_children():
                             try: cw.config(bg="#1f2544")
                             except: pass
                    elif w.winfo_class() == 'Label':
                        w.config(bg="#1f2544")
                except: pass
                
        def _on_l(e): 
            row.config(highlightbackground=BORDER_COLOR)
            row.config(bg=CARD_BG)
            row.glow.config(bg=CARD_BG)
            for w in row.winfo_children(): 
                try: 
                    if w != s_badge and w.winfo_class() == 'Frame':
                        w.config(bg=CARD_BG)
                        for cw in w.winfo_children():
                             try: cw.config(bg=CARD_BG)
                             except: pass
                    elif w.winfo_class() == 'Label':
                        w.config(bg=CARD_BG)
                except: pass

        row.bind("<Enter>", _on_e); row.bind("<Leave>", _on_l)
        
        # Click binding for the entire row to open details
        def _open_details(e): self.show_project_tasks_modal(pid, name)
        row.bind("<Button-1>", _open_details)
        for w in row.winfo_children():
            w.bind("<Button-1>", _open_details)
            for cw in w.winfo_children():
                cw.bind("<Button-1>", _open_details)

    def show_project_tasks_modal(self, pid, pname):
        try:
            t = Toplevel(self.root)
            t.title(f"Project Details: {pname}")
            t.geometry("900x755")
            t.minsize(765, 620)
            t.resizable(True, True)
            t.config(bg=CONTENT_BG)
            
            # Fetch initial project details
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT end_date, team_leader FROM projects WHERE id=?", (pid,))
            p_row = cur.fetchone()
            deadline = p_row[0] if p_row else "TBD"
            team_leader = p_row[1] if p_row else ""
            con.close()
            
            # --- Project Overview Summary Bar (Glassmorphic & Premium) ---
            summary_bar = Frame(t, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
            summary_bar.pack(fill=X, padx=20, pady=(20, 0))
            
            # Left: Project Title & Team Info
            left_info = Frame(summary_bar, bg=CARD_BG)
            left_info.pack(side=LEFT, fill=Y)
            
            Label(left_info, text=pname, font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            
            # Local label references for dynamic real-time updates
            modal_team_label = Label(left_info, text="👥 Team: Fetching...", font=('Segoe UI', 9), bg=CARD_BG, fg="#9aa3c2")
            modal_team_label.pack(anchor=W, pady=(4, 0))
            
            # Right: Progress & Deadline Info
            right_info = Frame(summary_bar, bg=CARD_BG)
            right_info.pack(side=RIGHT, fill=Y)
            
            # Progress bar container
            prog_frame = Frame(right_info, bg=CARD_BG)
            prog_frame.pack(side=RIGHT, padx=(20, 0), fill=Y)
            
            prog_lbl_frame = Frame(prog_frame, bg=CARD_BG)
            prog_lbl_frame.pack(fill=X)
            Label(prog_lbl_frame, text="Progress", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            
            modal_prog_pct_lbl = Label(prog_lbl_frame, text="0%", font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN)
            modal_prog_pct_lbl.pack(side=RIGHT)
            
            # Custom Progress Track
            track = Frame(prog_frame, bg="#1e2540", height=8, width=180)
            track.pack(fill=X, pady=(4, 0))
            track.pack_propagate(False)
            
            modal_prog_fill = Frame(track, bg=ACCENT_GREEN, height=8)
            
            # Deadline card
            dl_frame = Frame(right_info, bg=CARD_BG, padx=15)
            dl_frame.pack(side=RIGHT, fill=Y)
            Label(dl_frame, text="📅 DEADLINE", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=E)
            Label(dl_frame, text=deadline or "TBD", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(anchor=E, pady=(2, 0))
            
            # Tabs for Tasks and Activity
            tab_control = ttk.Notebook(t)
            tab_control.pack(fill=BOTH, expand=True, padx=20, pady=20)
            
            # 1. Tasks Tab
            task_frame = Frame(tab_control, bg=CARD_BG)
            tab_control.add(task_frame, text=" Tasks ")
            
            # Header row with Auto Plan, Project Assignee and Assign Selected
            header = Frame(task_frame, bg=CARD_BG)
            header.pack(fill=X, padx=10, pady=(10, 0))
            Label(header, text="Tasks", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
            if CURRENT_USER_ROLE.lower() in ('team leader', 'project manager', 'manager'):
                def open_auto_plan():
                    self.auto_plan_modal(pid, pname, refresh_cb=lambda: refresh_tree())
                Button(header, text="Auto Plan", bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, font=('Segoe UI', 10, 'bold'),
                       command=open_auto_plan).pack(side=RIGHT, padx=(5, 0))
                
                assign_box = Frame(header, bg=CARD_BG)
                assign_box.pack(side=RIGHT, padx=10)
                Label(assign_box, text="Assign selected to:", bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                try:
                    con_emp = sqlite3.connect(get_db_path())
                    cur_emp = con_emp.cursor()
                    if CURRENT_USER_ROLE.lower() == 'team leader':
                        cur_emp.execute("SELECT name FROM employee WHERE reporting_manager=? AND role != 'Admin'", (CURRENT_USER_NAME,))
                    else:
                        cur_emp.execute("SELECT name FROM employee WHERE role != 'Admin'")
                    emp_list = [r[0] for r in cur_emp.fetchall()]
                    con_emp.close()
                except:
                    emp_list = []
                sel_user = StringVar()
                ttk.Combobox(assign_box, textvariable=sel_user, values=emp_list, state="readonly", width=20).pack(side=LEFT, padx=6)
                def assign_selected():
                    items = tree.selection()
                    if not items or not sel_user.get():
                        messagebox.showwarning("Warning", "Select task(s) and a user.")
                        return
                    try:
                        con2 = sqlite3.connect(get_db_path())
                        cur2 = con2.cursor()
                        tids = [tree.item(i)['values'][0] for i in items]
                        cur2.executemany("UPDATE tasks SET assigned_to=? WHERE id=?", [(sel_user.get(), tid) for tid in tids])
                        con2.commit(); self.refresh_current_panel(); con2.close()
                        refresh_tree()
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                Button(assign_box, text="Assign", bg=PRIMARY_BG, fg=WHITE, relief=FLAT, font=('Segoe UI', 10, 'bold'),
                       command=assign_selected).pack(side=LEFT)

                # Project-level assignee controls
                proj_box = Frame(header, bg=CARD_BG)
                proj_box.pack(side=RIGHT, padx=10)
                Label(proj_box, text="Project assignee:", bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                proj_user = StringVar(value=get_project_default_assignee(pid))
                ttk.Combobox(proj_box, textvariable=proj_user, values=emp_list, state="readonly", width=18).pack(side=LEFT, padx=6)
                def set_proj_default():
                    if not proj_user.get():
                        messagebox.showwarning("Warning", "Pick a user to set as default.")
                        return
                    if set_project_default_assignee(pid, proj_user.get()):
                        messagebox.showinfo("Saved", f"Default assignee set to {proj_user.get()}")
                    else:
                        messagebox.showerror("Error", "Failed to save default assignee")
                def assign_all_now():
                    if not proj_user.get():
                        messagebox.showwarning("Warning", "Pick a user.")
                        return
                    try:
                        con3 = sqlite3.connect(get_db_path())
                        cur3 = con3.cursor()
                        cur3.execute("UPDATE tasks SET assigned_to=? WHERE project_id=?", (proj_user.get(), pid))
                        con3.commit(); self.refresh_current_panel(); con3.close()
                        refresh_tree()
                        messagebox.showinfo("Updated", "All project tasks assigned.")
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                Button(proj_box, text="Set Default", bg=ACCENT_ORANGE, fg=WHITE, relief=FLAT, font=('Segoe UI', 9, 'bold'),
                       command=set_proj_default).pack(side=LEFT, padx=(0,6))
                Button(proj_box, text="Assign All", bg=ACCENT_GREEN, fg=WHITE, relief=FLAT, font=('Segoe UI', 9, 'bold'),
                       command=assign_all_now).pack(side=LEFT)
            
            # 2. Activity Timeline Tab
            activity_frame = Frame(tab_control, bg=CARD_BG)
            tab_control.add(activity_frame, text=" Activity Timeline ")
            
            # --- Tasks Tab Content ---
            tree_frame = Frame(task_frame, bg=CARD_BG)
            tree_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
            
            cols = ("ID", "Title", "Assigned To", "Status", "Due Date", "Priority")
            tree = ttk.Treeview(tree_frame, columns=cols, show='headings', selectmode="extended")
            for col in cols:
                tree.heading(col, text=col)
                if col == "Title":
                    tree.column(col, width=320, anchor=W)
                elif col == "ID":
                    tree.column(col, width=50, anchor=CENTER)
            tree.pack(side=LEFT, fill=BOTH, expand=True)
            
            scrolly = Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
            scrolly.pack(side=RIGHT, fill=Y)
            tree.configure(yscrollcommand=scrolly.set)
            
            def refresh_tree():
                for i in tree.get_children(): tree.delete(i)
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                # Fetch tasks for Treeview
                cur.execute("""
                    SELECT
                        t.id,
                        t.title,
                        COALESCE(NULLIF(TRIM(t.assigned_to), ''), NULLIF(TRIM(p.default_assignee), ''), NULLIF(TRIM(p.team_leader), ''), 'Unassigned'),
                        t.status,
                        t.due_date,
                        t.priority
                    FROM tasks t
                    LEFT JOIN projects p ON t.project_id = p.id
                    WHERE t.project_id=?
                """, (pid,))
                rows = cur.fetchall()
                for row in rows:
                    tree.insert("", END, values=row)
                    
                # Recalculate progress dynamically
                cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) FROM tasks WHERE project_id=?", (pid,))
                t_res = cur.fetchone()
                total, done = t_res[0] or 0, t_res[1] or 0
                prog = int((done / total) * 100) if total > 0 else 0
                
                # Fetch unique list of assigned team members/employees
                cur.execute("SELECT DISTINCT assigned_to FROM tasks WHERE project_id=? AND assigned_to IS NOT NULL AND assigned_to != ''", (pid,))
                assigned_emps = [r[0] for r in cur.fetchall()]
                if team_leader:
                    for tl in [x.strip() for x in team_leader.split(",")]:
                        if tl and tl not in assigned_emps:
                            assigned_emps.append(tl)
                team_str = ", ".join(assigned_emps) if assigned_emps else "Unassigned"
                con.close()
                
                # Update overview elements dynamically in real-time
                modal_team_label.config(text=f"👥 Team: {team_str}")
                modal_prog_pct_lbl.config(text=f"{prog}%")
                modal_prog_fill.place_forget()
                if prog > 0:
                    modal_prog_fill.place(x=0, y=0, relwidth=min(prog/100, 1.0))
            refresh_tree()
                
            # --- Activity Timeline Content ---
            timeline_frame = Frame(activity_frame, bg=CARD_BG)
            timeline_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
            
            cols_act = ("Time", "User", "Action")
            tree_act = ttk.Treeview(timeline_frame, columns=cols_act, show='headings')
            for col in cols_act: 
                tree_act.heading(col, text=col)
                tree_act.column(col, width=150)
            tree_act.column("Action", width=350)
            tree_act.pack(side=LEFT, fill=BOTH, expand=True)
            
            scrolly_act = Scrollbar(timeline_frame, orient=VERTICAL, command=tree_act.yview)
            scrolly_act.pack(side=RIGHT, fill=Y)
            tree_act.configure(yscrollcommand=scrolly_act.set)
            
            try:
                con_act = sqlite3.connect(get_db_path())
                cur_act = con_act.cursor()
                cur_act.execute(
                    "SELECT timestamp, user_name, action FROM activity_timeline WHERE project_id=? ORDER BY timestamp DESC",
                    (pid,)
                )
                act_rows = cur_act.fetchall()
                for row in act_rows:
                    tree_act.insert("", END, values=row)
                con_act.close()
            except Exception as e:
                # Keep modal usable even if timeline fetch fails.
                messagebox.showwarning("Activity Timeline", f"Could not load timeline data: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open project details: {e}")

    def auto_plan_modal(self, pid, pname, refresh_cb=None):
        t = Toplevel(self.root)
        t.title(f"Auto Plan: {pname}")
        t.geometry("540x620")
        t.minsize(459, 527)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        Label(t, text=f"Auto Plan for {pname}", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=10)
        card = Frame(t, bg=CARD_BG, padx=20, pady=20)
        card.pack(fill=BOTH, expand=True, padx=20, pady=10)
        
        Label(card, text="Project Start Date (YYYY-MM-DD)", bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        e_start = Entry(card); e_start.pack(fill=X, pady=(0,10))
        try: e_start.insert(0, datetime.now().strftime("%Y-%m-%d"))
        except: pass
        
        Label(card, text="Suggested Tasks", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(5, 6))
        tasks_frame = Frame(card, bg=CARD_BG); tasks_frame.pack(fill=BOTH, expand=True)
        
        suggestions = suggest_tasks_for_project(pname)
        vars_list = []
        for title, prio, days in suggestions:
            row = Frame(tasks_frame, bg=CARD_BG); row.pack(fill=X, pady=2)
            var = IntVar(value=1); vars_list.append((var, title, prio, days))
            Checkbutton(row, text=title, variable=var, onvalue=1, offvalue=0, bg=CARD_BG, fg=TEXT_WHITE, selectcolor=CARD_BG, activebackground=CARD_BG).pack(side=LEFT, anchor=W)
            Label(row, text=f"{prio} | +{days}d", bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)
        
        def create_tasks():
            try:
                start = datetime.strptime(e_start.get(), "%Y-%m-%d")
                payload = []
                for var, title, prio, days in vars_list:
                    if var.get() != 1:
                        continue
                    due = (start + timedelta(days=days)).strftime("%Y-%m-%d")
                    # Do not auto-assign; TL will assign to specific employees
                    payload.append((title, pid, "", "Pending", due, prio, datetime.now().strftime("%Y-%m-%d")))
                if not payload:
                    messagebox.showwarning("Warning", "Select at least one task.")
                    return
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.executemany("INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)", payload)
                con.commit(); self.refresh_current_panel(); con.close()
                log_activity(pid, CURRENT_USER_NAME, f"Auto planned {len(payload)} tasks for project")
                if refresh_cb: refresh_cb()
                t.destroy()
                messagebox.showinfo("Success", f"Created {len(payload)} tasks.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        Button(t, text="Create Tasks", command=create_tasks, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(pady=10, fill=X, padx=20)

    def load_tasks(self):
        if CURRENT_USER_ROLE.lower() == 'project manager':
            self.load_project_status_panel()
            return

        # Header Section
        px = self.get_responsive_padx()
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Task Management", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Review assignments, update delivery status, and orchestrate team execution.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
        
        btn_frame = Frame(h, bg=CONTENT_BG)
        btn_frame.pack(side=RIGHT, pady=10)

        def make_btn(parent, text, bg, cmd, icon=""):
            return Button(parent, text=f"{icon} {text}", font=('Segoe UI', 9, 'bold'), bg=bg, fg=WHITE,
                         relief=FLAT, bd=0, padx=16, pady=10, cursor="hand2", command=cmd)

        if CURRENT_USER_ROLE.lower() in ['admin', 'team leader']:
            make_btn(btn_frame, "CREATE TASK", ACCENT_BLUE, self.add_task_modal, "➕").pack(side=RIGHT, padx=5)

        # Filters & Search Strip
        strip = Frame(self.content_area, bg=CARD_BG, padx=20, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        strip.pack(fill=X, padx=px, pady=(0, 20))
        
        Label(strip, text="🔍", font=('Segoe UI', 12), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=(0, 10))
        self.task_search_var = StringVar()
        self.task_search_var.trace("w", lambda *args: self.refresh_tasks())
        Entry(strip, textvariable=self.task_search_var, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, 
              insertbackground=WHITE, relief=FLAT, width=30).pack(side=LEFT, padx=(0, 20))
        
        # Filter Dropdowns (Styled)
        Label(strip, text="Status:", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
        self.task_filter_var = StringVar(value="All")
        f_status = ttk.OptionMenu(strip, self.task_filter_var, "All", "All", "Pending", "In Progress", "Delayed", "Completed", "Pending Approval", command=lambda _: self.refresh_tasks())
        f_status.pack(side=LEFT, padx=(5, 15))
        
        Label(strip, text="Priority:", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
        self.task_prio_filter = StringVar(value="All")
        f_prio = ttk.OptionMenu(strip, self.task_prio_filter, "All", "All", "High", "Medium", "Low", command=lambda _: self.refresh_tasks())
        f_prio.pack(side=LEFT, padx=(5, 15))

        # Main List Area
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 20))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        self.task_list_container = Frame(canvas, bg=CONTENT_BG)
        
        self.task_list_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.task_list_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)
        
        self.refresh_tasks()
    
    def sort_task_tree(self, col):
        if not hasattr(self, "_task_sort_rev"): self._task_sort_rev = {}
        rev = self._task_sort_rev.get(col, False)
        self._task_sort_rev[col] = not rev
        rows = [(self.task_tree.set(i, col), i) for i in self.task_tree.get_children('')]
        def parse(v):
            if col in ("ID",):
                try: return int(v)
                except: return 0
            if col in ("Due Date","Created"):
                try: return datetime.strptime(v, "%Y-%m-%d")
                except: return datetime.max
            if col == "Priority":
                return {"High":3,"Medium":2,"Low":1}.get(str(v),0)
            if col == "Progress":
                try:
                    return int(str(v).replace('%','').strip())
                except: return 0
            return str(v).lower()
        rows.sort(key=lambda x: parse(x[0]), reverse=rev)
        for idx, (_, iid) in enumerate(rows):
            self.task_tree.move(iid, '', idx)

    def delete_task(self):
        # Fallback for modernized card UI: deletion is handled via modal or single ID
        messagebox.showinfo("Management", "Please use the 'Update Status' modal to manage individual tasks, or use the project dashboard for bulk management.")

    def update_task_modal(self, task_id_arg=None):
        task_id = None
        task_title = ""
        current_status = ""
        
        if task_id_arg:
            task_id = task_id_arg
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("SELECT title, status FROM tasks WHERE id=?", (task_id,))
                row = cur.fetchone()
                con.close()
                if row:
                    task_title = row[0]
                    current_status = row[1]
                else:
                    messagebox.showerror("Error", "Task not found")
                    return
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
        else:
            messagebox.showwarning("Selection", "Click a task card to view details.")
            return

            if not target_tree:
                messagebox.showwarning("Warning", "Please select a task to update")
                return

            item = target_tree.item(target_tree.selection()[0])
            task_id = item['values'][0]
            
            if status_idx != -1:
                current_status = item['values'][status_idx]
                task_title = item['values'][1]
            else:
                # Query DB for simplified trees
                try:
                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()
                    cur.execute("SELECT title, status FROM tasks WHERE id=?", (task_id,))
                    row = cur.fetchone()
                    con.close()
                    if row:
                        task_title = row[0]
                        current_status = row[1]
                except: pass
        
        t = Toplevel(self.root)
        t.title("Task Details & Comments")
        t.geometry("650x750")
        t.minsize(600, 700)
        t.resizable(True, True)
        t.config(bg=CONTENT_BG)
        t.transient(self.root)
        t.grab_set()
        
        # Brand Stripe
        stripe = Frame(t, bg=ACCENT_BLUE, height=4)
        stripe.pack(fill=X)

        # ── HEADER ──
        header_f = Frame(t, bg=HEADER_BG, pady=15)
        header_f.pack(fill=X)
        Label(header_f, text=f"TASK ID: #{task_id}", font=('Rajdhani', 10, 'bold'), bg=HEADER_BG, fg=ACCENT_BLUE).pack()
        Label(header_f, text=task_title.upper(), font=('Rajdhani', 18, 'bold'), bg=HEADER_BG, fg=WHITE, wraplength=550).pack()
        
        # ── STATUS UPDATE SECTION ──
        status_card = Frame(t, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
        status_card.pack(fill=X, padx=25, pady=(20, 10))
        
        Label(status_card, text="PROGRESS STATUS", font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=LEFT)
        
        role = CURRENT_USER_ROLE.lower()
        if role in ['admin', 'project manager', 'team leader']:
            statuses = ["Pending", "In Progress", "Completed", "Delayed", "Pending Approval"]
        else:
            statuses = ["In Progress", "Pending Approval"]
            
        c_status = ttk.Combobox(status_card, values=statuses, state="readonly", width=18, style='Employee.TCombobox')
        c_status.set(current_status)
        c_status.pack(side=LEFT, padx=15)
        
        def save_status():
            new_status = c_status.get()
            try:
                con = sqlite3.connect(get_db_path())
                cursor = con.cursor()
                if new_status == 'Completed':
                    cursor.execute("UPDATE tasks SET status=?, completed_date=? WHERE id=?", (new_status, datetime.now().strftime("%Y-%m-%d"), task_id))
                else:
                    cursor.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
                
                # Log Activity
                cursor.execute("SELECT project_id FROM tasks WHERE id=?", (task_id,))
                pid = cursor.fetchone()[0]
                log_activity(pid, CURRENT_USER_NAME, f"Updated task '{task_title}' to {new_status}")
                
                con.commit(); self.refresh_current_panel()
                con.close()
                self.refresh_current_page(sync=False)
                messagebox.showinfo("Success", "Status Updated")
                t.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        btn_update = Button(status_card, text="UPDATE STATUS", command=save_status, bg=PRIMARY_RED, fg=WHITE, 
                           font=('Segoe UI', 8, 'bold'), relief=FLAT, padx=20, pady=8, cursor="hand2")
        btn_update.pack(side=RIGHT)
        btn_update.bind("<Enter>", lambda e: btn_update.config(bg=PRIMARY_RED_DARK))
        btn_update.bind("<Leave>", lambda e: btn_update.config(bg=PRIMARY_RED))
        
        # ── MAIN CONTENT (TABS-LIKE FEEL) ──
        main_scroll_c = Canvas(t, bg=CONTENT_BG, highlightthickness=0)
        main_scroll_f = Frame(main_scroll_c, bg=CONTENT_BG)
        main_sb = Scrollbar(t, orient=VERTICAL, command=main_scroll_c.yview)
        main_scroll_c.configure(yscrollcommand=main_sb.set)
        
        main_scroll_c.pack(side=LEFT, fill=BOTH, expand=True, padx=(25, 0))
        main_sb.pack(side=RIGHT, fill=Y)
        
        main_window = main_scroll_c.create_window((0, 0), window=main_scroll_f, anchor="nw")
        def _on_modal_resize(e):
            main_scroll_c.itemconfig(main_window, width=e.width)
            main_scroll_c.configure(scrollregion=main_scroll_c.bbox("all"))
        main_scroll_c.bind("<Configure>", _on_modal_resize)

        # ── COMMENTS SECTION ──
        Label(main_scroll_f, text="💬 TASK COMMENTS", font=('Rajdhani', 14, 'bold'), bg=CONTENT_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(15, 10))
        
        tree_comm = ttk.Treeview(main_scroll_f, columns=("User", "Comment", "Time"), show='headings', height=8, style='Custom.Treeview')
        tree_comm.heading("User", text="USER")
        tree_comm.heading("Comment", text="COMMENT")
        tree_comm.heading("Time", text="TIMESTAMP")
        tree_comm.column("User", width=120)
        tree_comm.column("Comment", width=350)
        tree_comm.column("Time", width=120)
        tree_comm.pack(fill=X, pady=5)
        self._attach_tree_hover(tree_comm)
        
        def refresh_comments():
            for item in tree_comm.get_children(): tree_comm.delete(item)
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT user_name, comment, timestamp FROM task_comments WHERE task_id=? ORDER BY timestamp DESC", (task_id,))
            for r in cur.fetchall(): tree_comm.insert("", END, values=r)
            con.close()
            main_scroll_c.configure(scrollregion=main_scroll_c.bbox("all"))
            
        refresh_comments()
        
        # Add Comment Input
        add_comm_f = Frame(main_scroll_f, bg=CARD_BG, padx=15, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        add_comm_f.pack(fill=X, pady=10)
        
        comment_entry = Entry(add_comm_f, font=('Segoe UI', 10), bg=BG_DARK, fg=WHITE, insertbackground=WHITE, relief=FLAT)
        comment_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 15), ipady=5)
        
        def add_comment():
            txt = comment_entry.get().strip()
            if not txt: return
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur.execute("INSERT INTO task_comments (task_id, user_name, comment, timestamp) VALUES (?,?,?,?)",
                            (task_id, CURRENT_USER_NAME, txt, ts))
                con.commit(); self.refresh_current_panel(); con.close()
                comment_entry.delete(0, END)
                refresh_comments()
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        btn_post = Button(add_comm_f, text="POST", command=add_comment, bg=ACCENT_BLUE, fg=WHITE, 
                         font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=20, cursor="hand2")
        btn_post.pack(side=RIGHT)

        # ── ATTACHMENTS SECTION ──
        Label(main_scroll_f, text="📎 ATTACHMENTS", font=('Rajdhani', 14, 'bold'), bg=CONTENT_BG, fg=ACCENT_PURPLE).pack(anchor=W, pady=(20, 10))
        
        tree_att = ttk.Treeview(main_scroll_f, columns=("File", "Uploaded By", "Time"), show='headings', height=5, style='Custom.Treeview')
        for c in ("File", "Uploaded By", "Time"):
            tree_att.heading(c, text=c.upper())
            tree_att.column(c, width=180)
        tree_att.pack(fill=X, pady=5)
        self._attach_tree_hover(tree_att)

        def refresh_att():
            for i in tree_att.get_children(): tree_att.delete(i)
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT file_path, uploaded_by, timestamp FROM task_attachments WHERE task_id=? ORDER BY id DESC", (task_id,))
            for r in cur.fetchall():
                fname = os.path.basename(r[0])
                tree_att.insert("", END, values=(fname, r[1], r[2]), tags=(r[0],))
            con.close()
            main_scroll_c.configure(scrollregion=main_scroll_c.bbox("all"))

        refresh_att()

        # Attachment Controls
        att_btn_f = Frame(main_scroll_f, bg=CONTENT_BG)
        att_btn_f.pack(fill=X, pady=10)
        
        def attach_file():
            try:
                path = filedialog.askopenfilename()
                if not path: return
                base_dir = os.path.join(os.path.dirname(get_db_path()), "attachments")
                os.makedirs(base_dir, exist_ok=True)
                fname = os.path.basename(path)
                target = os.path.join(base_dir, f"{task_id}_{int(time.time())}_{fname}")
                import shutil
                shutil.copyfile(path, target)
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                cur.execute("INSERT INTO task_attachments (task_id, file_path, uploaded_by, timestamp) VALUES (?,?,?,?)",
                            (task_id, target, CURRENT_USER_NAME, ts))
                con.commit(); self.refresh_current_panel(); con.close()
                refresh_att()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to attach: {e}")

        def open_selected():
            sel = tree_att.selection()
            if not sel: return
            fp = tree_att.item(sel[0])['tags'][0]
            try:
                os.startfile(fp)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open file: {e}")

        Button(att_btn_f, text="+ UPLOAD FILE", bg=ACCENT_PURPLE, fg=WHITE, font=('Segoe UI', 8, 'bold'), 
               relief=FLAT, padx=15, pady=6, command=attach_file, cursor="hand2").pack(side=LEFT)
        Button(att_btn_f, text="OPEN SELECTED", bg=HOVER_BG, fg=TEXT_SECONDARY, font=('Segoe UI', 8, 'bold'), 
               relief=FLAT, padx=15, pady=6, command=open_selected, cursor="hand2").pack(side=LEFT, padx=10)
        Button(t, text="CLOSE WINDOW", command=t.destroy, bg=HOVER_BG, fg=TEXT_SECONDARY, 
               font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=25, pady=10, cursor="hand2").pack(pady=20)

    def refresh_tasks(self, reset_page=False):
        debug_log("DEBUG: Refreshing Management Task Cards...")
        if not hasattr(self, 'task_list_container') or not self.task_list_container.winfo_exists(): return
        
        for w in self.task_list_container.winfo_children():
            w.destroy()
            
        search_txt = self.task_search_var.get().lower() if hasattr(self, 'task_search_var') else ""
        status_filter = self.task_filter_var.get() if hasattr(self, 'task_filter_var') else "All"
        prio_filter = self.task_prio_filter.get() if hasattr(self, 'task_prio_filter') else "All"
        member_filter = getattr(self, 'task_member_filter', StringVar(value="All")).get()

        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            query = """
                SELECT t.id, t.title, p.name, t.assigned_to, t.priority, t.status, t.due_date, t.description
                FROM tasks t 
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE 1=1
            """
            params = []
            
            role = CURRENT_USER_ROLE.lower()
            if role == 'team leader':
                query += " AND (t.project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?) OR t.assigned_to = ?)"
                params.extend([f"%{CURRENT_USER_NAME}%", CURRENT_USER_NAME])
            elif role == 'project manager':
                # PM sees tasks for all their projects
                query += " AND t.project_id IN (SELECT id FROM projects WHERE manager LIKE ?)"
                params.append(f"%{CURRENT_USER_NAME}%")
            
            if status_filter != "All":
                query += " AND t.status = ?"
                params.append(status_filter)
            if prio_filter != "All":
                query += " AND t.priority = ?"
                params.append(prio_filter)
            if member_filter != "All":
                query += " AND t.assigned_to = ?"
                params.append(member_filter)
            if search_txt:
                query += " AND (lower(t.title) LIKE ? OR lower(p.name) LIKE ? OR lower(t.assigned_to) LIKE ?)"
                params.extend([f"%{search_txt}%", f"%{search_txt}%", f"%{search_txt}%"])
                
            query += " ORDER BY t.id DESC"
            cur.execute(query, params)
            rows = cur.fetchall()
            
            # Responsive Grid
            self.root.update_idletasks()
            if not hasattr(self, 'task_list_container') or not self.task_list_container.winfo_exists(): return
            w = self.root.winfo_width()
            cols = 1 if w < 900 else (2 if w < 1400 else 3)
            for i in range(cols):
                self.task_list_container.grid_columnconfigure(i, weight=1, uniform="task_grid")
                
            if not rows:
                Label(self.task_list_container, text="No matching tasks found in the command center.", 
                      font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
            else:
                for idx, row in enumerate(rows):
                    self._render_task_card_management(idx, cols, row)
                    
            con.close()
        except Exception as e:
            debug_log(f"Error refreshing management tasks: {e}")

    def _render_task_card_management(self, idx, cols, row):
        tid, title, p_name, assigned, priority, status, due_date, desc = row
        r, c = divmod(idx, cols)
        
        _s_bg = {"Completed": ACCENT_GREEN, "In Progress": ACCENT_BLUE, 
                 "Delayed": ACCENT_RED, "Pending": ACCENT_ORANGE}.get(status, MUTED_TEXT)
        
        card = Frame(self.task_list_container, bg=CARD_BG, padx=1, pady=1, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=r, column=c, sticky="nsew", padx=12, pady=12)
        
        inner = Frame(card, bg=CARD_BG, padx=22, pady=20)
        inner.pack(fill=BOTH, expand=True)
        
        # Header
        top = Frame(inner, bg=CARD_BG); top.pack(fill=X)
        Label(top, text=f"#{tid}", font=('Rajdhani', 9, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
        
        p_color = {"High": ACCENT_RED, "Medium": ACCENT_ORANGE, "Low": ACCENT_GREEN}.get(priority, MUTED_TEXT)
        p_frame = Frame(top, bg=p_color, padx=6, pady=1); p_frame.pack(side=RIGHT)
        Label(p_frame, text=priority.upper(), font=('Segoe UI', 7, 'bold'), bg=p_color, fg=WHITE).pack()
        
        # Title & Project
        Label(inner, text=title, font=('Segoe UI', 13, 'bold'), bg=CARD_BG, fg=TEXT_WHITE, wraplength=280, justify=LEFT).pack(anchor=W, pady=(10, 2))
        Label(inner, text=f"📂 {p_name or 'Independent Task'}", font=('Segoe UI Emoji', 9), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W)
        
        # Divider
        Frame(inner, bg=BORDER_COLOR, height=1).pack(fill=X, pady=15)
        
        # Assignee & Status
        meta = Frame(inner, bg=CARD_BG); meta.pack(fill=X)
        
        # Left: Assignee
        a_box = Frame(meta, bg=CARD_BG)
        a_box.pack(side=LEFT)
        Label(a_box, text="ASSIGNEE", font=('Segoe UI', 7, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        Label(a_box, text=assigned, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        
        # Right: Status Badge
        s_box = Frame(meta, bg=CARD_BG)
        s_box.pack(side=RIGHT, anchor=N)
        s_badge = Frame(s_box, bg=_s_bg, padx=10, pady=3)
        s_badge.pack()
        Label(s_badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=_s_bg, fg=WHITE).pack()
        
        # Footer: Due Date & Action
        bot = Frame(inner, bg=CARD_BG); bot.pack(fill=X, pady=(20, 0))
        
        # Check if overdue
        overdue = False
        if due_date and status != "Completed":
            try:
                d = datetime.strptime(due_date, "%Y-%m-%d").date()
                if d < datetime.now().date(): overdue = True
            except: pass
            
        d_color = ACCENT_RED if overdue else TEXT_SECONDARY
        Label(bot, text=f"📅 {due_date}", font=('Segoe UI Emoji', 9), bg=CARD_BG, fg=d_color).pack(side=LEFT)
        
        btn = Button(bot, text="MANAGE \u2192", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE,
                     relief=FLAT, bd=0, padx=0, pady=0, activebackground=CARD_BG, activeforeground=WHITE,
                     command=lambda: self.update_task_modal(tid), cursor="hand2")
        btn.pack(side=RIGHT)

        # Hover Effects
        def _on_e(e):
            card.config(highlightbackground=_s_bg, highlightthickness=2)
            inner.config(bg="#1c223d")
            for w in inner.winfo_children(): 
                try: w.config(bg="#1c223d")
                except: pass
        def _on_l(e):
            card.config(highlightbackground=BORDER_COLOR, highlightthickness=1)
            inner.config(bg=CARD_BG)
            for w in inner.winfo_children():
                try: w.config(bg=CARD_BG)
                except: pass
                
        card.bind("<Enter>", _on_e); card.bind("<Leave>", _on_l)
        inner.bind("<Enter>", _on_e); inner.bind("<Leave>", _on_l)

    def bulk_update_task_status(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select one or more tasks.")
            return
            
        tids = [self.task_tree.item(s)['values'][0] for s in selected]
        
        # Simple modal to pick status
        top = Toplevel(self.root)
        top.title("Bulk Update Status")
        top.geometry("300x200")
        top.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
        top.resizable(True, True)  # FIX 7: allow resize so no overflow
        top.config(bg=CONTENT_BG)
        
        Label(top, text=f"Update {len(tids)} Tasks", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        
        new_status = StringVar(value="In Progress")
        ttk.Combobox(top, textvariable=new_status, values=["Pending", "In Progress", "Completed", "Delayed"], state="readonly").pack(pady=10)
        
        def apply():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                status = new_status.get()
                completed_date = datetime.now().strftime("%Y-%m-%d") if status == 'Completed' else None
                
                for tid in tids:
                    if status == 'Completed':
                        cur.execute("UPDATE tasks SET status=?, completed_date=? WHERE id=?", (status, completed_date, tid))
                    else:
                        cur.execute("UPDATE tasks SET status=? WHERE id=?", (status, tid))
                    
                    # Log Activity for each task
                    cur.execute("SELECT project_id, title FROM tasks WHERE id=?", (tid,))
                    pid, title = cur.fetchone()
                    log_activity(pid, CURRENT_USER_NAME, f"Bulk update: Task '{title}' set to {status}")
                
                con.commit(); self.refresh_current_panel()
                con.close()
                
                log_audit(CURRENT_USER_NAME, "Bulk Task Update", f"Updated {len(tids)} tasks to {status}")
                self.refresh_tasks()
                top.destroy()
                messagebox.showinfo("Success", f"Updated {len(tids)} tasks.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(top, text="Update All", bg=ACCENT_GREEN, fg=WHITE, command=apply, relief=FLAT, padx=20).pack(pady=10)

    def reassign_task_modal(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a task to reassign.")
            return
        
        item = self.task_tree.item(selected[0])
        tid = item['values'][0]
        title = item['values'][1]
        current_assignee = item['values'][3] if len(item['values']) > 3 else ""
        is_assign = (str(current_assignee or "").strip() == "")
        
        top = Toplevel(self.root)
        top.title("Assign Task" if is_assign else "Reassign Task")
        top.geometry("350x250")
        top.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
        top.resizable(True, True)  # FIX 7: allow resize so no overflow
        top.config(bg=CONTENT_BG)
        
        Label(top, text=("Assign: " if is_assign else "Reassign: ") + f"{title}", font=('Segoe UI', 11, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        
        # Fetch members
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        if CURRENT_USER_ROLE.lower() == 'team leader':
            cur.execute("SELECT name FROM employee WHERE reporting_manager=? AND role != 'Admin'", (CURRENT_USER_NAME,))
        else:
            cur.execute("SELECT name FROM employee WHERE role != 'Admin'")
        members = [r[0] for r in cur.fetchall()]
        con.close()
        
        new_user = StringVar()
        ttk.Combobox(top, textvariable=new_user, values=members, state="readonly").pack(pady=10)
        
        def apply():
            user = new_user.get()
            if not user: return
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("UPDATE tasks SET assigned_to=? WHERE id=?", (user, tid))
                
                # Log Activity
                cur.execute("SELECT project_id, title FROM tasks WHERE id=?", (tid,))
                pid, title = cur.fetchone()
                if is_assign:
                    log_activity(pid, CURRENT_USER_NAME, f"Assigned task '{title}' to {user}")
                else:
                    log_activity(pid, CURRENT_USER_NAME, f"Reassigned task '{title}' to {user}")
                
                con.commit(); self.refresh_current_panel()
                con.close()
                
                if is_assign:
                    log_audit(CURRENT_USER_NAME, "Task Assigned", f"Assigned task {tid} to {user}")
                else:
                    log_audit(CURRENT_USER_NAME, "Task Reassigned", f"Reassigned task {tid} to {user}")
                self.refresh_tasks()
                top.destroy()
                messagebox.showinfo("Success", "Task assigned." if is_assign else "Task reassigned.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(top, text=("Confirm Assign" if is_assign else "Confirm Reassign"), bg=ACCENT_BLUE, fg=WHITE, command=apply, relief=FLAT, padx=20).pack(pady=10)

    def unassign_selected_tasks(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select one or more tasks to unassign.")
            return
        tids = [self.task_tree.item(s)['values'][0] for s in selected]
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            for tid in tids:
                cur.execute("UPDATE tasks SET assigned_to='' WHERE id=?", (tid,))
            con.commit(); self.refresh_current_panel(); con.close()
            try:
                for tid in tids:
                    log_audit(CURRENT_USER_NAME, "Task Unassigned", f"Cleared assignee for task {tid}")
            except:
                pass
            self.refresh_tasks()
            messagebox.showinfo("Success", f"Unassigned {len(tids)} task(s).")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def mark_task_urgent(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select one or more tasks.")
            return
            
        tids = [self.task_tree.item(s)['values'][0] for s in selected]
        
        if messagebox.askyesno("Urgent", f"Mark {len(tids)} tasks as High priority?"):
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                for tid in tids:
                    cur.execute("UPDATE tasks SET priority='High' WHERE id=?", (tid,))
                    
                    # Log Activity
                    cur.execute("SELECT project_id, title FROM tasks WHERE id=?", (tid,))
                    pid, title = cur.fetchone()
                    log_activity(pid, CURRENT_USER_NAME, f"Marked task '{title}' as URGENT")
                
                con.commit(); self.refresh_current_panel()
                con.close()
                
                log_audit(CURRENT_USER_NAME, "Tasks Marked Urgent", f"Marked {len(tids)} tasks as High priority")
                self.refresh_tasks()
                messagebox.showinfo("Success", "Tasks updated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def add_task_modal(self):
        t = Toplevel(self.root)
        t.title("Assign Task")
        t.config(bg=CONTENT_BG)
        
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        modal_w = 560; modal_h = min(780, sh - 100)
        x = int((sw / 2) - (modal_w / 2)); y = int((sh / 2) - (modal_h / 2))
        t.geometry(f"{modal_w}x{modal_h}+{x}+{y}")
        t.transient(self.root); t.grab_set()

        container = Frame(t, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas, bg=CONTENT_BG, padx=30, pady=30)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _on_canvas_resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _on_canvas_resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(container, canvas)

        hero = Frame(scroll_frame, bg=CONTENT_BG)
        hero.pack(fill=X, pady=(0, 25))
        Label(hero, text="Create Task", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(hero, text="Define deliverables, set priorities, and assign to team talent.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        card = Frame(scroll_frame, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=BOTH, expand=True)

        con = sqlite3.connect(get_db_path()); cur = con.cursor()
        role = CURRENT_USER_ROLE.lower()
        
        pm_tasks = []
        pm_task_map = {}
        if role == 'team leader':
            # Fetch tasks assigned specifically to this Team Leader that are not completed yet
            try:
                cur.execute("""
                    SELECT t.id, t.title, p.name, t.due_date, t.priority 
                    FROM tasks t 
                    LEFT JOIN projects p ON t.project_id = p.id 
                    WHERE lower(t.assigned_to) = lower(?) AND t.status != 'Completed'
                """, (CURRENT_USER_NAME,))
                pm_tasks = cur.fetchall()
            except Exception as e:
                debug_log(f"DEBUG: Error fetching PM tasks: {e}")
                
            cur.execute("""
                SELECT id, name FROM projects 
                WHERE lower(team_leader) LIKE ?
                  AND (
                      id IN (
                          SELECT DISTINCT project_id FROM tasks 
                          WHERE project_id IS NOT NULL 
                            AND lower(assigned_to) = lower(?)
                      )
                      OR
                      id NOT IN (
                          SELECT DISTINCT project_id FROM tasks 
                          WHERE project_id IS NOT NULL
                      )
                  )
            """, (f"%{CURRENT_USER_NAME.lower()}%", CURRENT_USER_NAME))
            projects = cur.fetchall()
            cur.execute("SELECT name FROM employee WHERE reporting_manager = ? OR lower(role) IN ('team member', 'employee')", (CURRENT_USER_NAME,))
            members = [r[0] for r in cur.fetchall()]
        else:
            cur.execute("SELECT id, name FROM projects"); projects = cur.fetchall()
            cur.execute("SELECT name FROM employee WHERE lower(role) NOT IN ('admin', 'project manager')"); members = [r[0] for r in cur.fetchall()]
        con.close()
        
        project_map = {name: pid for pid, name in projects}; project_names = list(project_map.keys())
        pm_task_map = {f"{r[1]} ({r[2]})": r for r in pm_tasks}

        def make_field(parent, label):
            f = Frame(parent, bg=CARD_BG)
            f.pack(fill=X, pady=10)
            Label(f, text=label.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(0, 5))
            w = Frame(f, bg="#1a2035", highlightbackground=BORDER_COLOR, highlightthickness=1)
            w.pack(fill=X); return w

        # Task Selection from PM (Visible only to TL when there are tasks assigned to them)
        if role == 'team leader' and pm_tasks:
            ref_w = make_field(card, "Select Task assigned by Project Manager")
            task_options = ["-- Create New Task --"] + list(pm_task_map.keys())
            c_ref = ttk.Combobox(ref_w, values=task_options, font=('Segoe UI', 10), state="readonly")
            c_ref.pack(fill=X, padx=8, pady=8)
            c_ref.set("-- Create New Task --")

        p_w = make_field(card, "Project Selection")
        c_proj = ttk.Combobox(p_w, values=project_names, font=('Segoe UI', 10), state="readonly")
        c_proj.pack(fill=X, padx=8, pady=8)
        if project_names: c_proj.set(project_names[0])

        t_w = make_field(card, "Task Title")
        e_title = Entry(t_w, font=('Segoe UI', 11), bg="#1a2035", fg=WHITE, relief=FLAT, insertbackground=WHITE)
        e_title.pack(fill=X, padx=12, pady=10)

        a_w = make_field(card, "Assignee (Team Member)")
        c_user = ttk.Combobox(a_w, values=members, font=('Segoe UI', 10), state="readonly")
        c_user.pack(fill=X, padx=8, pady=8)
        if members: c_user.set(members[0])

        d_w = make_field(card, "Due Date (YYYY-MM-DD)")
        e_date = Entry(d_w, font=('Segoe UI', 11), bg="#1a2035", fg=WHITE, relief=FLAT, insertbackground=WHITE)
        e_date.insert(0, (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        e_date.pack(fill=X, padx=12, pady=10)

        pr_w = make_field(card, "Priority")
        c_prio = ttk.Combobox(pr_w, values=["High", "Medium", "Low"], font=('Segoe UI', 10), state="readonly")
        c_prio.set("Medium"); c_prio.pack(fill=X, padx=8, pady=8)

        # Dynamic binding to autofill PM task details
        if role == 'team leader' and pm_tasks:
            def on_task_ref_selected(event):
                val = c_ref.get()
                if val == "-- Create New Task --":
                    e_title.config(state="normal")
                    e_title.delete(0, END)
                    c_proj.config(state="readonly")
                else:
                    task_row = pm_task_map[val] # (id, title, proj_name, due_date, priority)
                    e_title.config(state="normal")
                    e_title.delete(0, END)
                    e_title.insert(0, task_row[1])
                    e_title.config(state="disabled") # Lock it
                    
                    if task_row[2] in project_names:
                        c_proj.config(state="readonly")
                        c_proj.set(task_row[2])
                    c_proj.config(state="disabled") # Lock project
                    
                    e_date.delete(0, END)
                    e_date.insert(0, task_row[3] or "")
                    
                    if task_row[4] in ["High", "Medium", "Low"]:
                        c_prio.set(task_row[4])
                        
            c_ref.bind("<<ComboboxSelected>>", on_task_ref_selected)

        def save():
            try:
                # Resolve title whether enabled or disabled
                title = e_title.get().strip()
                if not title: raise Exception("Please enter a task title")
                
                # Retrieve from combo even if disabled
                proj_name = c_proj.get()
                pid = project_map.get(proj_name)
                if not pid: raise Exception("Select a valid project")
                
                assignee = c_user.get()
                if not assignee: raise Exception("Please select a team member to assign this task")
                
                con = sqlite3.connect(get_db_path()); cur = con.cursor()
                
                # Uniqueness Check: Prevent duplicate task title under the same project
                # Exclude CURRENT_USER_NAME since they might be forwarding a PM-assigned task currently held by them.
                cur.execute("""
                    SELECT assigned_to FROM tasks 
                    WHERE lower(title) = lower(?) AND project_id = ? AND lower(assigned_to) != lower(?)
                """, (title, pid, CURRENT_USER_NAME))
                existing = cur.fetchone()
                if existing:
                    con.close()
                    raise Exception(f"The task '{title}' is already assigned to {existing[0]}!")
                
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                is_update = False
                task_id_to_update = None
                if role == 'team leader' and pm_tasks:
                    ref_val = c_ref.get()
                    if ref_val != "-- Create New Task --":
                        is_update = True
                        task_id_to_update = pm_task_map[ref_val][0]
                
                if is_update:
                    # PM Task assigned to Employee: UPDATE the task's assignee from TL to Employee
                    cur.execute("""
                        UPDATE tasks 
                        SET assigned_to = ?, status = 'Pending', due_date = ?, priority = ?, created_date = ? 
                        WHERE id = ?
                    """, (assignee, e_date.get(), c_prio.get(), datetime.now().strftime("%Y-%m-%d"), task_id_to_update))
                    
                    cur.execute("INSERT INTO activity_timeline (project_id, user_name, action, timestamp) VALUES (?,?,?,?)", 
                                   (pid, CURRENT_USER_NAME, f"Assigned task '{title}' (from PM) to {assignee}", ts))
                    cur.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)", 
                                   (ts, CURRENT_USER_NAME, "Task Forwarded", f"Forwarded PM task '{title}' to {assignee}"))
                    cur.execute("INSERT INTO notifications (user, message, timestamp) VALUES (?,?,?)", 
                                   (assignee, f"New Task Assigned: {title}", ts))
                else:
                    # Standard INSERT for a new task
                    cur.execute("INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)",
                                (title, pid, assignee, "Pending", e_date.get(), c_prio.get(), datetime.now().strftime("%Y-%m-%d")))
                    
                    cur.execute("INSERT INTO activity_timeline (project_id, user_name, action, timestamp) VALUES (?,?,?,?)", 
                                   (pid, CURRENT_USER_NAME, f"Created new task: '{title}' assigned to {assignee}", ts))
                    cur.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)", 
                                   (ts, CURRENT_USER_NAME, "Task Assigned", f"Assigned '{title}' to {assignee}"))
                    cur.execute("INSERT INTO notifications (user, message, timestamp) VALUES (?,?,?)", 
                                   (assignee, f"New Task: {title}", ts))
                
                con.commit(); con.close()
                self.refresh_tasks(); t.destroy()
                messagebox.showinfo("Success", f"Task '{title}' has been successfully assigned to {assignee}.")
            except Exception as e: messagebox.showerror("Error", str(e))

        btn = Button(scroll_frame, text="ASSIGN TASK", font=('Segoe UI', 10, 'bold'), bg=ACCENT_BLUE, fg=WHITE,
                     relief=FLAT, padx=30, pady=15, command=save)
        btn.pack(fill=X, pady=(25, 10))
        self._apply_hover_effect(btn, ACCENT_BLUE, "#1c223d")
        t.bind("<Escape>", lambda e: t.destroy())

    def add_task_to_tl_modal(self, prefill_pid=None, prefill_name=None, prefill_tl=None):
        t = Toplevel(self.root)
        t.title("Assign Milestone")
        t.config(bg=CONTENT_BG)
        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        modal_w = 560; modal_h = min(720, sh - 100)
        x = int((sw / 2) - (modal_w / 2)); y = int((sh / 2) - (modal_h / 2))
        t.geometry(f"{modal_w}x{modal_h}+{x}+{y}")
        t.transient(self.root); t.grab_set()
        shell = Frame(t, bg=CONTENT_BG, padx=30, pady=30)
        shell.pack(fill=BOTH, expand=True)
        hero = Frame(shell, bg=CONTENT_BG)
        hero.pack(fill=X, pady=(0, 25))
        Label(hero, text="Leader Assignment", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(hero, text="Set high-level milestones and assign to the appropriate Team Leader.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
        card = Frame(shell, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=BOTH, expand=True)
        con = sqlite3.connect(get_db_path()); cur = con.cursor()
        cur.execute("SELECT id, name FROM projects"); projects = cur.fetchall()
        cur.execute("SELECT name FROM employee WHERE lower(role) = 'team leader'"); leaders = [r[0] for r in cur.fetchall()]
        con.close()
        project_map = {name: pid for pid, name in projects}; project_names = list(project_map.keys())
        def make_field(parent, label):
            f = Frame(parent, bg=CARD_BG)
            f.pack(fill=X, pady=10)
            Label(f, text=label.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(0, 5))
            w = Frame(f, bg="#1a2035", highlightbackground=BORDER_COLOR, highlightthickness=1)
            w.pack(fill=X); return w
        p_w = make_field(card, "Project Reference")
        c_proj = ttk.Combobox(p_w, values=project_names, font=('Segoe UI', 10), state="readonly")
        c_proj.pack(fill=X, padx=8, pady=8)
        if prefill_name: c_proj.set(prefill_name)
        elif project_names: c_proj.set(project_names[0])
        l_w = make_field(card, "Team Leader")
        c_user = ttk.Combobox(l_w, values=leaders, font=('Segoe UI', 10), state="readonly")
        c_user.pack(fill=X, padx=8, pady=8)
        if prefill_tl: c_user.set(prefill_tl)
        elif leaders: c_user.set(leaders[0])
        d_w = make_field(card, "Deadline (YYYY-MM-DD)")
        e_date = Entry(d_w, font=('Segoe UI', 11), bg="#1a2035", fg=WHITE, relief=FLAT, insertbackground=WHITE)
        e_date.insert(0, (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"))
        e_date.pack(fill=X, padx=12, pady=10)
        pr_w = make_field(card, "Urgency / Priority")
        c_prio = ttk.Combobox(pr_w, values=["High", "Medium", "Low"], font=('Segoe UI', 10), state="readonly")
        c_prio.set("Medium"); c_prio.pack(fill=X, padx=8, pady=8)
        def save():
            try:
                pid = project_map.get(c_proj.get())
                if not pid: raise Exception("Select a valid project")
                leader = c_user.get(); title = f"Management: {c_proj.get()} Milestone"
                con = sqlite3.connect(get_db_path()); cur = con.cursor()
                
                # Prevent duplicate milestone assignment
                cur.execute("SELECT assigned_to FROM tasks WHERE lower(title) = lower(?) AND project_id = ?", (title, pid))
                existing = cur.fetchone()
                if existing:
                    con.close()
                    raise Exception(f"This milestone has already been assigned to {existing[0]}!")
                
                cur.execute("UPDATE projects SET team_leader=?, default_assignee=? WHERE id=?", (leader, leader, pid))
                cur.execute("INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)",
                            (title, pid, leader, "Pending", e_date.get(), c_prio.get(), datetime.now().strftime("%Y-%m-%d")))
                log_activity(pid, CURRENT_USER_NAME, f"Assigned milestone task to Leader: {leader}")
                con.commit(); self.refresh_current_panel(); con.close()
                log_audit(CURRENT_USER_NAME, "Leader Task Assigned", f"Assigned milestone for {c_proj.get()} to {leader}")
                notify_user(leader, f"New Milestone Task: {title}")
                self.refresh_tasks(); t.destroy()
                messagebox.showinfo("Success", "Milestone assigned to leader.")
            except Exception as e: messagebox.showerror("Error", str(e))
        btn = Button(shell, text="ASSIGN TO LEADER", font=('Segoe UI', 10, 'bold'), bg=ACCENT_BLUE, fg=WHITE,
                     relief=FLAT, padx=30, pady=15, command=save)
        btn.pack(fill=X, pady=(25, 0))
        self._apply_hover_effect(btn, ACCENT_BLUE, "#1c223d")
        t.bind("<Escape>", lambda e: t.destroy())

    def show_admin_requests(self):
        t = Toplevel(self.root)
        t.title("Notifications & Requests")
        t.geometry("600x650")
        t.minsize(510, 552)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        # Center
        x = int((self.root.winfo_screenwidth()/2) - (600/2))
        y = int((self.root.winfo_screenheight()/2) - (650/2))
        t.geometry(f"600x650+{x}+{y}")
        
        Label(t, text="ðŸ”” Pending Requests", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        
        # Tabs for Requests
        tab_control = ttk.Notebook(t)
        tab_control.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
        
        # 1. Password Reset Tab
        reset_frame = Frame(tab_control, bg=CARD_BG)
        tab_control.add(reset_frame, text=" Password Resets ")
        
        # 2. Leave Requests Tab
        leave_frame = Frame(tab_control, bg=CARD_BG)
        tab_control.add(leave_frame, text=" Leave Requests ")
        
        # --- Password Reset Data ---
        reset_list = []
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT id, username, email FROM users WHERE reset_requested = 1")
            reset_list = cur.fetchall()
            con.close()
        except: pass
        
        if not reset_list:
            Label(reset_frame, text="No pending password resets", font=('Segoe UI', 11), bg=CARD_BG, fg=SIDEBAR_TEXT).pack(pady=50)
        else:
            cols = ("ID", "Username", "Email")
            tree_reset = ttk.Treeview(reset_frame, columns=cols, show='headings', height=10)
            for col in cols: tree_reset.heading(col, text=col)
            tree_reset.pack(fill=BOTH, expand=True, padx=10, pady=10)
            for r in reset_list: tree_reset.insert("", END, values=r)
            
            def handle_reset(action):
                sel = tree_reset.selection()
                if not sel: return
                uname = tree_reset.item(sel[0])['values'][1]
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                if action == 'Approve':
                    new_pw = hashlib.sha256("123456".encode()).hexdigest()
                    cur.execute("UPDATE users SET password = ?, reset_requested = 0 WHERE username = ?", (new_pw, uname))
                    messagebox.showinfo("Success", f"Password reset for {uname}")
                else:
                    cur.execute("UPDATE users SET reset_requested = 0 WHERE username = ?", (uname,))
                con.commit(); self.refresh_current_panel()
                con.close()
                t.destroy()
                self.show_notifications()
                
            btn_f = Frame(reset_frame, bg=CARD_BG)
            btn_f.pack(fill=X, pady=10)
            Button(btn_f, text="Approve Reset", bg="#27ae60", fg="white", relief=FLAT, padx=15, command=lambda: handle_reset('Approve')).pack(side=RIGHT, padx=5)
            Button(btn_f, text="Dismiss", bg="#e74c3c", fg="white", relief=FLAT, padx=15, command=lambda: handle_reset('Dismiss')).pack(side=RIGHT, padx=5)

        # --- Leave Request Data ---
        leave_list = []
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT id, member_name, reason, start_date, end_date, status FROM leave_requests WHERE status = 'Pending'")
            leave_list = cur.fetchall()
            con.close()
        except: pass
        
        if not leave_list:
            Label(leave_frame, text="No pending leave requests", font=('Segoe UI', 11), bg=CARD_BG, fg=SIDEBAR_TEXT).pack(pady=50)
        else:
            cols = ("ID", "Name", "Reason", "Start", "End")
            tree_leave = ttk.Treeview(leave_frame, columns=cols, show='headings', height=10)
            for col in cols: tree_leave.heading(col, text=col)
            tree_leave.pack(fill=BOTH, expand=True, padx=10, pady=10)
            for r in leave_list: tree_leave.insert("", END, values=r[:5])
            
            def handle_leave(action):
                sel = tree_leave.selection()
                if not sel: return
                lid = tree_leave.item(sel[0])['values'][0]
                status = 'Approved' if action == 'Approve' else 'Rejected'
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("UPDATE leave_requests SET status = ? WHERE id = ?", (status, lid))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", f"Leave {status}")
                t.destroy()
                self.show_notifications()
                
            btn_f2 = Frame(leave_frame, bg=CARD_BG)
            btn_f2.pack(fill=X, pady=10)
            Button(btn_f2, text="Approve Leave", bg="#27ae60", fg="white", relief=FLAT, padx=15, command=lambda: handle_leave('Approve')).pack(side=RIGHT, padx=5)
            Button(btn_f2, text="Reject Leave", bg="#e74c3c", fg="white", relief=FLAT, padx=15, command=lambda: handle_leave('Reject')).pack(side=RIGHT, padx=5)

    def load_leave_requests(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

        px = self.get_responsive_padx()
        
        # Header
        h_wrap = Frame(self.content_area, bg=CONTENT_BG)
        h_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Leave Management", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Review and manage team absence requests and delivery impact.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        # Filter Chips
        filter_box = Frame(h_wrap, bg=CONTENT_BG)
        filter_box.pack(side=RIGHT, pady=10)
        
        if not hasattr(self, "_leave_filter"): self._leave_filter = StringVar(value="All")
        
        for st in ["All", "Pending", "Approved", "Rejected"]:
            is_active = self._leave_filter.get() == st
            f_bg = ACCENT_BLUE if is_active else CARD_BG
            f_fg = WHITE if is_active else MUTED_TEXT
            btn = Button(filter_box, text=st.upper(), font=('Segoe UI', 8, 'bold'), bg=f_bg, fg=f_fg,
                        relief=FLAT, bd=0, padx=12, pady=6, cursor="hand2",
                        command=lambda s=st: [self._leave_filter.set(s), self.load_leave_requests()])
            btn.pack(side=LEFT, padx=4)

        # Metrics Row
        metrics_row = Frame(self.content_area, bg=CONTENT_BG)
        metrics_row.pack(fill=X, padx=px, pady=(0, 20))

        def create_metric_card(parent, title, val, color):
            c = Frame(parent, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            c.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(c, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            Label(c, text=str(val), font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=color).pack(anchor=W, pady=(8, 0))
            return c

        try:
            con_m = sqlite3.connect(get_db_path())
            cur_m = con_m.cursor()
            cur_m.execute("SELECT COUNT(*), SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END), SUM(CASE WHEN status='Approved' THEN 1 ELSE 0 END) FROM leave_requests")
            counts = cur_m.fetchone()
            total_req, pending_req, approved_req = counts[0] or 0, counts[1] or 0, counts[2] or 0
            con_m.close()
        except Exception as e:
            debug_log(f"DEBUG: Failed to fetch leave metrics: {e}")
            total_req, pending_req, approved_req = 0, 0, 0

        create_metric_card(metrics_row, "Total Requests", total_req, ACCENT_BLUE)
        create_metric_card(metrics_row, "Pending Approval", pending_req, ACCENT_ORANGE)
        create_metric_card(metrics_row, "Approved Leaves", approved_req, ACCENT_GREEN)

        # Main scrollable area
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)

        # Data Fetch
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            q = "SELECT id, member_name, leave_type, reason, start_date, end_date, timestamp, status FROM leave_requests"
            params = []
            if self._leave_filter.get() != "All":
                q += " WHERE status=?"
                params.append(self._leave_filter.get())
            q += " ORDER BY id DESC"
            
            cursor.execute(q, params)
            requests = cursor.fetchall()

            if not requests:
                Label(scrollable_frame, text="No leave requests found.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for req in requests:
                    self._render_leave_card(scrollable_frame, req)
            
            con.close()
        except Exception as e:
            debug_log(f"Leave Error: {e}")

    def _render_leave_card(self, parent, req):
        lid, name, l_type, reason, start, end, ts, status = req
        _bg = CARD_BG
        _s_color = {"Approved": ACCENT_GREEN, "Pending": ACCENT_ORANGE, "Rejected": ACCENT_RED}.get(status, MUTED_TEXT)
        
        card = Frame(parent, bg=_bg, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=X, pady=8)
        
        # Left Info
        info = Frame(card, bg=_bg)
        info.pack(side=LEFT, fill=Y)
        Label(info, text=name, font=('Segoe UI', 13, 'bold'), bg=_bg, fg=TEXT_WHITE).pack(anchor=W)
        Label(info, text=f"{l_type.upper()} LEAVE", font=('Segoe UI', 8, 'bold'), bg=_bg, fg=ACCENT_BLUE).pack(anchor=W)
        
        # Center Reason
        r_box = Frame(card, bg=_bg)
        r_box.pack(side=LEFT, fill=BOTH, expand=True, padx=40)
        Label(r_box, text="REASON", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT).pack(anchor=W)
        Label(r_box, text=reason if len(reason) < 80 else reason[:77]+"...", font=('Segoe UI', 10), bg=_bg, fg=TEXT_WHITE, wraplength=400, justify=LEFT).pack(anchor=W)
        
        # Dates
        d_box = Frame(card, bg=_bg)
        d_box.pack(side=LEFT, padx=20)
        Label(d_box, text=f"{start} → {end}", font=('Segoe UI', 10, 'bold'), bg=_bg, fg=TEXT_WHITE).pack()
        Label(d_box, text="SCHEDULED DATES", font=('Segoe UI', 7, 'bold'), bg=_bg, fg=MUTED_TEXT).pack()
        
        # Status & Action
        s_box = Frame(card, bg=_bg, width=120)
        s_box.pack(side=RIGHT, padx=(20, 0))
        
        if status == "Pending":
            btn_box = Frame(s_box, bg=_bg)
            btn_box.pack()
            
            def _act(s): self._process_leave_action(lid, s)
            
            Button(btn_box, text="✓", font=('Segoe UI', 10, 'bold'), bg=ACCENT_GREEN, fg=WHITE, relief=FLAT, width=3, command=lambda: _act("Approved")).pack(side=LEFT, padx=2)
            Button(btn_box, text="✕", font=('Segoe UI', 10, 'bold'), bg=ACCENT_RED, fg=WHITE, relief=FLAT, width=3, command=lambda: _act("Rejected")).pack(side=LEFT, padx=2)
        else:
            s_badge = Frame(s_box, bg=_s_color, padx=12, pady=4)
            s_badge.pack()
            Label(s_badge, text=status.upper(), font=('Segoe UI', 7, 'bold'), bg=_s_color, fg=WHITE).pack()

        def _on_e(e): card.config(highlightbackground=_s_color, highlightthickness=1); card.config(bg="#252d4d")
        def _on_l(e): card.config(highlightbackground=BORDER_COLOR); card.config(bg=CARD_BG)
        card.bind("<Enter>", _on_e); card.bind("<Leave>", _on_l)

    def _process_leave_action(self, lid, status):
        # ... logic moved from inside load_leave_requests ...
        def submit_action(comment):
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, lid))
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)",
                            (ts, CURRENT_USER_NAME, f"Leave {status}", f"id={lid}; comment={comment}"))
                con.commit(); self.refresh_current_panel()
                con.close()
                self.load_leave_requests()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        # Show a quick comment dialog
        dialog = Toplevel(self.root)
        dialog.title(f"{status} Request")
        dialog.geometry("400x300")
        dialog.configure(bg=CARD_BG)
        dialog.transient(self.root); dialog.grab_set()
        
        Label(dialog, text=f"{status.upper()} LEAVE", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=WHITE, pady=20).pack()
        Label(dialog, text="Add a comment (optional):", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, padx=30)
        
        txt = Text(dialog, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), relief=FLAT, padx=10, pady=10, height=4)
        txt.pack(fill=BOTH, expand=True, padx=30, pady=10)
        
        Button(dialog, text=f"CONFIRM {status.upper()}", bg=ACCENT_GREEN if status=="Approved" else ACCENT_RED, fg=WHITE, 
               font=('Segoe UI', 10, 'bold'), relief=FLAT, pady=10, command=lambda: [submit_action(txt.get("1.0", END).strip()), dialog.destroy()]).pack(fill=X, padx=30, pady=(10, 30))

    def load_productivity(self):
        for widget in self.content_area.winfo_children():
            widget.destroy()

        px = self.get_responsive_padx()
        
        # Header
        h_wrap = Frame(self.content_area, bg=CONTENT_BG)
        h_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Team Productivity Engine", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Real-time performance metrics and efficiency analysis for all Team Leaders.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        # Main scrollable area
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)

        # Data processing
        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            cursor.execute("SELECT name FROM employee WHERE lower(role)='team leader'")
            tls = [r[0] for r in cursor.fetchall()]

            if not tls:
                Label(scrollable_frame, text="No Team Leaders found in system.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
                con.close(); return

            tl_stats = []
            best_rate = -1
            best_name = "N/A"
            
            for tl in tls:
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE project_id IN (
                        SELECT id FROM projects 
                        WHERE team_leader LIKE ?
                    )
                """, (f"%{tl}%",))
                total = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE status='Completed' AND project_id IN (
                        SELECT id FROM projects 
                        WHERE team_leader LIKE ?
                    )
                """, (f"%{tl}%",))
                done = cursor.fetchone()[0] or 0
                
                cursor.execute("""
                    SELECT COUNT(*) FROM tasks 
                    WHERE status='Delayed' AND project_id IN (
                        SELECT id FROM projects 
                        WHERE team_leader LIKE ?
                    )
                """, (f"%{tl}%",))
                delayed = cursor.fetchone()[0] or 0
                
                rate = int((done/total)*100) if total > 0 else 0
                if rate > best_rate: [best_rate, best_name] = [rate, tl]
                tl_stats.append({'name': tl, 'total': total, 'done': done, 'delayed': delayed, 'rate': rate})

            # Top Summary Cards
            summary_row = Frame(scrollable_frame, bg=CONTENT_BG)
            summary_row.pack(fill=X, pady=(0, 30))
            
            for s_title, s_val, s_icon, s_color in [
                ("TOP PERFORMER", best_name.upper(), "🏆", ACCENT_GREEN),
                ("PEAK EFFICIENCY", f"{best_rate}%", "⚡", ACCENT_BLUE),
                ("ACTIVE LEADERS", len(tls), "👥", WHITE)
            ]:
                s_card = Frame(summary_row, bg=CARD_BG, padx=22, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
                s_card.pack(side=LEFT, padx=(0, 20), expand=True, fill=X)
                Label(s_card, text=f"{s_icon} {s_title}", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                Label(s_card, text=s_val, font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=s_color).pack(anchor=W, pady=(4, 0))

            # TL Cards Grid
            cols = 1 if self.root.winfo_width() < 1100 else 2
            grid_cont = Frame(scrollable_frame, bg=CONTENT_BG)
            grid_cont.pack(fill=X)
            for c in range(cols): grid_cont.grid_columnconfigure(c, weight=1)

            for idx, stat in enumerate(tl_stats):
                self._render_tl_card(grid_cont, idx, cols, stat)

            con.close()
        except Exception as e:
            debug_log(f"Productivity Error: {e}")

    def _render_tl_card(self, parent, idx, cols, stat):
        r, c = divmod(idx, cols)
        card = Frame(parent, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=r, column=c, sticky="nsew", padx=10, pady=10)
        
        # Header (Avatar + Name)
        header = Frame(card, bg=CARD_BG)
        header.pack(fill=X)
        
        ava = Frame(header, bg=ACCENT_BLUE, width=44, height=44)
        ava.pack(side=LEFT)
        ava.pack_propagate(False)
        Label(ava, text=stat['name'][0].upper(), font=('Segoe UI', 14, 'bold'), bg=ACCENT_BLUE, fg=WHITE).pack(expand=True)
        
        n_box = Frame(header, bg=CARD_BG, padx=15)
        n_box.pack(side=LEFT, fill=Y)
        Label(n_box, text=stat['name'], font=('Segoe UI', 13, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(n_box, text="TEAM LEADER", font=('Segoe UI', 7, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W)
        
        # Main Metrics (Completion Donut-like bar)
        prog_wrap = Frame(card, bg=CARD_BG, pady=20)
        prog_wrap.pack(fill=X)
        
        Label(prog_wrap, text="TASK COMPLETION RATE", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        
        bar_row = Frame(prog_wrap, bg=CARD_BG, pady=8)
        bar_row.pack(fill=X)
        
        track = Frame(bar_row, bg="#2a3352", height=10)
        track.pack(side=LEFT, fill=X, expand=True)
        if stat['rate'] > 0:
            fill = Frame(track, bg=ACCENT_GREEN, height=10)
            fill.place(x=0, y=0, relwidth=min(stat['rate']/100, 1.0))
            
        Label(bar_row, text=f"{stat['rate']}%", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN, padx=15).pack(side=RIGHT)

        # Detailed Stats
        stats_box = Frame(card, bg="#1d243d", padx=15, pady=12)
        stats_box.pack(fill=X)
        
        for s_lbl, s_val, s_clr in [
            ("TOTAL ASSIGNED", stat['total'], WHITE),
            ("COMPLETED", stat['done'], ACCENT_GREEN),
            ("DELAYED / RISK", stat['delayed'], ACCENT_RED)
        ]:
            s_row = Frame(stats_box, bg="#1d243d")
            s_row.pack(fill=X, pady=2)
            Label(s_row, text=s_lbl, font=('Segoe UI', 8), bg="#1d243d", fg=MUTED_TEXT).pack(side=LEFT)
            Label(s_row, text=str(s_val), font=('Segoe UI', 9, 'bold'), bg="#1d243d", fg=s_clr).pack(side=RIGHT)

        def _on_e(e): card.config(highlightbackground=ACCENT_BLUE, bg="#252d4d")
        def _on_l(e): card.config(highlightbackground=BORDER_COLOR, bg=CARD_BG)
        card.bind("<Enter>", _on_e); card.bind("<Leave>", _on_l)
        card.bind("<Button-1>", lambda e: self.show_productivity_detail(stat['name'], stat['rate']))
        for w in (header, ava, n_box, prog_wrap, bar_row, stats_box):
             for child in w.winfo_children():
                  child.bind("<Button-1>", lambda e: self.show_productivity_detail(stat['name'], stat['rate']))
             w.bind("<Button-1>", lambda e: self.show_productivity_detail(stat['name'], stat['rate']))

    def load_reports(self):

        for widget in self.content_area.winfo_children():
            widget.destroy()

        # Add Scrollbar wrapper for the entire Reports page
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=self.root.winfo_width()-250) # Approx width
        
        # Debounced width adjustment to make it responsive
        def _on_canvas_configure(e):
            canvas.itemconfig(1, width=e.width)
        canvas.bind("<Configure>", _on_canvas_configure)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        self._bind_canvas_scrolling(container, canvas)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        parent = scrollable_frame
        px = self.get_responsive_padx()

        # Modern Hero Section
        hero = Frame(parent, bg=CARD_BG, padx=30, pady=28, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hero.pack(fill=X, padx=px, pady=(30, 20))
        
        h_top = Frame(hero, bg=CARD_BG)
        h_top.pack(fill=X)
        
        title_v = Frame(h_top, bg=CARD_BG)
        title_v.pack(side=LEFT)
        Label(title_v, text="Executive Performance Reports", font=('Segoe UI', 26, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_v, text="Cross-team delivery velocity, workload health, and historical productivity audit.", 
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
        
        # Engine Status Chip
        engine_chip = Frame(h_top, bg="#1e293b", padx=16, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
        engine_chip.pack(side=RIGHT)
        Label(engine_chip, text="SNAPSHOT ENGINE", font=('Segoe UI', 7, 'bold'), bg="#1e293b", fg=MUTED_TEXT).pack(anchor=E)
        
        sync_row = Frame(engine_chip, bg="#1e293b")
        sync_row.pack(anchor=E, pady=(2, 0))
        Label(sync_row, text=f"Last Sync: {getattr(self, 'last_report_sync', 'Live')}", font=('Segoe UI', 9, 'bold'), bg="#1e293b", fg=ACCENT_BLUE).pack(side=LEFT)
        Button(sync_row, text="GENERATE FULL REPORT", command=lambda: self.export_excel(), font=('Segoe UI', 8, 'bold'), 
               bg=ACCENT_ORANGE, fg=WHITE, relief=FLAT, padx=10, pady=2).pack(side=LEFT, padx=(10, 0))

        # Hero Feature Cards
        feature_row = Frame(hero, bg=CARD_BG)
        feature_row.pack(fill=X, pady=(24, 0))
        for idx, (icon, lbl, desc, clr) in enumerate([
            ("📊", "Team Velocity", "Task throughput rates", ACCENT_BLUE),
            ("⚖️", "Workload Balance", "Resource distribution", ACCENT_GREEN),
            ("📁", "Archive Mode", "Historical data bundle", ACCENT_ORANGE)
        ]):
            f_box = Frame(feature_row, bg=HEADER_BG, padx=18, pady=14, highlightbackground=clr, highlightthickness=1)
            f_box.pack(side=LEFT, expand=True, fill=BOTH, padx=(0 if idx == 0 else 12, 0))
            
            f_head = Frame(f_box, bg=HEADER_BG)
            f_head.pack(fill=X)
            
            # Icon Box (Colored Background) - Fixed square to match reference image
            icon_frame = Frame(f_head, bg=clr, width=28, height=28)
            icon_frame.pack(side=LEFT)
            icon_frame.pack_propagate(False)
            
            icon_lbl = Label(icon_frame, text=icon, font=('Segoe UI Emoji', 12),
                             bg=clr, fg=WHITE)
            icon_lbl.pack(expand=True)

            Label(f_head, text=lbl.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=8)
            Label(f_box, text=desc, font=('Segoe UI', 11, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(8, 0))



        con = sqlite3.connect(get_db_path())
        cur = con.cursor()

        # Team Average Productivity
        avg_rate = 0
        try:
            cur.execute(f"""
                SELECT AVG(rate) FROM (
                    SELECT (SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS rate
                    FROM tasks
                    WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                    GROUP BY assigned_to
                )
            """, (f"%{CURRENT_USER_NAME}%",))
            r = cur.fetchone()[0]
            avg_rate = int(r) if r else 0
        except:
            avg_rate = 0

        # Total Tasks This Week / Completed This Month
        total_week = 0
        completed_month = 0
        try:
            cur.execute(f"""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                  AND date(COALESCE(created_date, due_date)) >= date('now', '-6 days')
            """, (f"%{CURRENT_USER_NAME}%",))
            total_week = cur.fetchone()[0] or 0

            cur.execute(f"""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                  AND status='Completed'
                  AND date(COALESCE(completed_date, created_date, due_date)) >= date('now', 'start of month')
            """, (f"%{CURRENT_USER_NAME}%",))
            completed_month = cur.fetchone()[0] or 0
        except:
            pass

        team_size = 0
        active_members = 0
        try:
            cur.execute(f"""
                SELECT COUNT(DISTINCT assigned_to)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                  AND assigned_to IS NOT NULL
                  AND TRIM(assigned_to) != ''
            """, (f"%{CURRENT_USER_NAME}%",))
            team_size = cur.fetchone()[0] or 0

            cur.execute(f"""
                SELECT COUNT(DISTINCT assigned_to)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                  AND status != 'Completed'
                  AND assigned_to IS NOT NULL
                  AND TRIM(assigned_to) != ''
            """, (f"%{CURRENT_USER_NAME}%",))
            active_members = cur.fetchone()[0] or 0
        except:
            pass

        # Top summary cards
        cards = Frame(parent, bg=CONTENT_BG)
        cards.pack(fill=X, padx=30, pady=(0, 20))

        def create_report_card(parent, icon, title, value, accent, subtitle, progress=None):
            card = Frame(parent, bg=CARD_BG, padx=22, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side=LEFT, fill=BOTH, expand=True)

            head_row = Frame(card, bg=CARD_BG)
            head_row.pack(fill=X)
            Label(head_row, text=icon, font=('Segoe UI', 14), bg=CARD_BG).pack(side=LEFT, padx=(0, 8))
            Label(head_row, text=title.upper(), font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            
            Label(card, text=value, font=('Segoe UI', 28, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(14, 4))
            Label(card, text=subtitle, font=('Segoe UI', 10), bg=CARD_BG, fg=accent).pack(anchor=W)

            bar_wrap = Frame(card, bg="#333333", height=4)
            bar_wrap.pack(fill=X, pady=(20, 0))
            metric = progress if progress is not None else 0
            metric = max(0, min(metric, 100))
            # Subtle glow effect for progress
            Frame(bar_wrap, bg=accent, height=4).place(x=0, y=0, relwidth=max(0.12, metric / 100 if metric else 0.12))
            return card

        create_report_card(cards, "⚡", "Team Average Productivity", f"{avg_rate}%", ACCENT_GREEN,
                           f"{team_size} tracked member{'s' if team_size != 1 else ''}", avg_rate)
        create_report_card(cards, "📝", "Total Tasks This Week", str(total_week), ACCENT_BLUE,
                           f"{active_members} member{'s' if active_members != 1 else ''} with active work",
                           min(total_week * 10, 100)).pack_configure(padx=14)
        create_report_card(cards, "✅", "Completed This Month", str(completed_month), ACCENT_ORANGE,
                           "Monthly throughput momentum", min(completed_month * 10, 100))

        # Tasks Completed Per Week chart
        chart_card = Frame(parent, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        chart_card.pack(fill=X, padx=30, pady=(0, 20))
        Label(chart_card, text="Tasks Completed Per Week", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(chart_card, text="Six-week completion snapshot for your team.", font=('Segoe UI', 10),
              bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 14))

        weekly = []
        for i in range(5, -1, -1):
            cur.execute(f"""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                  AND status='Completed'
                  AND date(COALESCE(completed_date, created_date, due_date))
                      BETWEEN date('now', ? || ' days') AND date('now', ? || ' days')
            """, (f"%{CURRENT_USER_NAME}%", str(-(i * 7 + 6)), str(-(i * 7))))
            v = cur.fetchone()[0] or 0
            weekly.append((f"W{i+1}", v))

        chart = Canvas(chart_card, bg=CARD_BG, height=230, highlightthickness=0)
        chart.pack(fill=X)
        max_v = max([v for _, v in weekly] + [1])
        chart.update_idletasks()
        c_width = max(chart.winfo_width(), 820)
        left = 60
        right = c_width - 40
        bottom = 180
        top = 28
        bar_w = max(40, int((right - left) / max(6 * 1.45, 1)))
        gap = max(18, int((right - left - (bar_w * len(weekly))) / max(len(weekly) - 1, 1)))
        x = left

        chart.create_line(left, bottom, right, bottom, fill=BORDER_COLOR, width=2)
        for step in range(1, 5):
            y = bottom - ((bottom - top) * step / 4)
            chart.create_line(left, y, right, y, fill="#41516a", dash=(4, 4))
            value_label = int((max_v * step) / 4)
            chart.create_text(left - 12, y, text=str(value_label), fill=MUTED_TEXT, font=('Segoe UI', 9), anchor='e')

        if sum(v for _, v in weekly) == 0:
            chart.create_text((left + right) / 2, 92, text="No completed tasks recorded in the last six weeks",
                              fill=TEXT_WHITE, font=('Segoe UI', 13, 'bold'))
            chart.create_text((left + right) / 2, 120, text="As tasks are completed, this chart will start showing weekly delivery momentum.",
                              fill=MUTED_TEXT, font=('Segoe UI', 10))
            for lbl, _ in weekly:
                chart.create_rectangle(x, bottom - 10, x + bar_w, bottom, fill="#4b6078", outline="")
                chart.create_text(x + (bar_w / 2), bottom + 18, text=lbl, fill=MUTED_TEXT, font=('Segoe UI', 9, 'bold'))
                x += bar_w + gap
        else:
            for lbl, v in weekly:
                h_px = int((v / max_v) * (bottom - top)) if max_v else 0
                y0 = bottom - h_px
                chart.create_rectangle(x, y0, x + bar_w, bottom, fill=ACCENT_BLUE, outline="")
                chart.create_rectangle(x, max(y0 + 8, top), x + bar_w, bottom, fill="#7ec8ff", outline="", stipple="gray50")
                chart.create_text(x + (bar_w / 2), bottom + 18, text=lbl, fill=MUTED_TEXT, font=('Segoe UI', 9, 'bold'))
                chart.create_text(x + (bar_w / 2), y0 - 12, text=str(v), fill=TEXT_WHITE, font=('Segoe UI', 10, 'bold'))
                x += bar_w + gap
        
        # Productivity Trend (Line)
        trend_card = Frame(parent, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        trend_card.pack(fill=X, padx=30, pady=(0, 20))
        Label(trend_card, text="Productivity Trend", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(trend_card, text="Average completion rate across the last eight weekly windows.", font=('Segoe UI', 10),
              bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 14))
        trend = []
        for i in range(7, -1, -1):
            cur.execute(f"""
                SELECT AVG(rate) FROM (
                    SELECT (SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS rate
                    FROM tasks
                    WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                      AND date(COALESCE(completed_date, created_date, due_date))
                          BETWEEN date('now', ? || ' days') AND date('now', ? || ' days')
                    GROUP BY assigned_to
                )
            """, (f"%{CURRENT_USER_NAME}%", str(-(i * 7 + 6)), str(-(i * 7))))
            val = cur.fetchone()[0] or 0
            trend.append(int(val))
        line = Canvas(trend_card, bg=CARD_BG, height=240, highlightthickness=0)
        line.pack(fill=X)
        line.update_idletasks()
        max_t = max(trend + [1])
        left = 56
        right = max(line.winfo_width(), 860) - 36
        top = 24
        bottom = 185
        line.create_line(left, bottom, right, bottom, fill=BORDER_COLOR, width=2)
        line.create_line(left, bottom, left, top, fill=BORDER_COLOR, width=2)
        for step in range(1, 5):
            y = bottom - ((bottom - top) * step / 4)
            line.create_line(left, y, right, y, fill="#41516a", dash=(4, 4))
            line.create_text(left - 12, y, text=f"{int((max_t * step) / 4)}%", fill=MUTED_TEXT, anchor='e', font=('Segoe UI', 9))
        if sum(trend) == 0:
            line.create_text((left + right) / 2, 92, text="No productivity trend yet",
                             fill=TEXT_WHITE, font=('Segoe UI', 13, 'bold'))
            line.create_text((left + right) / 2, 120, text="When the team starts completing work, the trend line will reflect weekly performance changes.",
                             fill=MUTED_TEXT, font=('Segoe UI', 10))
            for idx in range(len(trend)):
                x = left + idx * ((right-left)/max(1,(len(trend)-1)))
                line.create_text(x, bottom + 20, text=f"W{idx+1}", fill=MUTED_TEXT, font=('Segoe UI', 9))
        else:
            prev = None
            for idx, v in enumerate(trend):
                x = left + idx * ((right-left)/max(1,(len(trend)-1)))
                y = bottom - (v/max_t)*(bottom-top)
                if prev:
                    line.create_line(prev[0], prev[1], x, y, fill=ACCENT_GREEN, width=3, smooth=True)
                line.create_oval(x-5, y-5, x+5, y+5, fill=ACCENT_GREEN, outline="")
                line.create_oval(x-10, y-10, x+10, y+10, outline="#6ee7b7")
                line.create_text(x, bottom + 20, text=f"W{idx+1}", fill=MUTED_TEXT, font=('Segoe UI', 9))
                line.create_text(x, y - 14, text=f"{v}%", fill=TEXT_WHITE, font=('Segoe UI', 9, 'bold'))
                prev = (x, y)
        line.create_text(right, top, text=f"Peak {max_t}%", fill=MUTED_TEXT, anchor=NE, font=('Segoe UI', 9, 'bold'))
        
        # Team Workload Distribution
        workload_card = Frame(parent, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        workload_card.pack(fill=X, padx=30, pady=(0, 20))
        Label(workload_card, text="Team Workload Distribution", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(workload_card, text="Open-task load by team member so imbalances stand out quickly.", font=('Segoe UI', 10),
              bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 14))
        dist = []
        try:
            cur.execute(f"""
                SELECT assigned_to, COUNT(*) 
                FROM tasks 
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?) AND status!='Completed'
                GROUP BY assigned_to ORDER BY COUNT(*) DESC LIMIT 8
            """, (f"%{CURRENT_USER_NAME}%",))
            dist = cur.fetchall()
        except:
            dist = []
        dist_canvas = Canvas(workload_card, bg=CARD_BG, height=50 + 34*max(1,len(dist)), highlightthickness=0)
        dist_canvas.pack(fill=X)
        max_c = max([c for _, c in dist] + [1])
        if not dist:
            dist_canvas.create_text(18, 24, text="No active workload data available yet.", fill=MUTED_TEXT,
                                    font=('Segoe UI', 10), anchor='w')
        else:
            y = 14
            for name, cnt in dist:
                short_name = name if len(name) <= 18 else name[:15] + "..."
                pct = int((cnt / max_c) * 100) if max_c else 0
                dist_canvas.create_text(12, y + 11, text=short_name, fill=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), anchor='w')
                dist_canvas.create_text(220, y + 11, text=f"{pct}% load", fill=MUTED_TEXT, font=('Segoe UI', 9), anchor='w')
                dist_canvas.create_rectangle(330, y, 760, y + 20, fill=HEADER_BG, outline="")
                w = int((cnt / max_c) * 430)
                dist_canvas.create_rectangle(330, y, 330 + w, y + 20, fill=ACCENT_ORANGE, outline="")
                dist_canvas.create_text(772, y + 10, text=str(cnt), fill=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), anchor='w')
                y += 34

        con.close()

    def download_all_reports(self):
        self.export_team_productivity()
        self.last_report_generated = datetime.now().strftime("%Y-%m-%d %H:%M")
        messagebox.showinfo("Done", "Report generation completed. Team Productivity CSV downloaded.")
        self.load_reports()
    def export_team_productivity(self):
        import csv
        from tkinter import filedialog

        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return

        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()

            cur.execute(f"""
                SELECT assigned_to,
                       COUNT(*) as total,
                       SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status='Delayed' OR (status!='Completed' AND due_date < date('now')) THEN 1 ELSE 0 END) as delayed
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE {'manager' if CURRENT_USER_ROLE.lower() == 'project manager' else 'team_leader'} LIKE ?)
                GROUP BY assigned_to
            """, (f"%{CURRENT_USER_NAME}%",))

            rows = cur.fetchall()

            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Member Name", "Total Tasks", "Completed", "Delayed", "Productivity %"])
                for name, total, done, delay in rows:
                    prod = f"{int((done/total)*100)}%" if total > 0 else "0%"
                    writer.writerow([name, total, done, delay, prod])

            con.close()
            self.last_report_generated = datetime.now().strftime("%Y-%m-%d %H:%M")
            messagebox.showinfo("Success", f"Team productivity exported to {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {e}")

    def render_project_summary_section(self, parent):
        frame = Frame(parent, bg=CONTENT_BG)
        frame.pack(fill=X, pady=(0, 25))
        
        # Card Container
        card = Frame(frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=X, ipadx=1, ipady=1)

        # Section Header
        header = Frame(card, bg=CARD_BG, padx=20, pady=15)
        header.pack(fill=X)
        
        # Red Accent Bar
        Frame(header, bg=PRIMARY_BG, width=4, height=20).pack(side=LEFT, padx=(0, 10))
        
        Label(header, text="Project Summary", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Button(header, text="â†» REFRESH DATA", bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=10, command=self.load_reports).pack(side=RIGHT)
        
        # Treeview Style
        # FIX 5c: reuse Style singleton — no theme_use() needed here
        style = ttk.Style()
        
        # Remove borders and modernize
        style.layout("Report.Treeview", [('Report.Treeview.treearea', {'sticky': 'nswe'})]) 
        
        style.configure("Report.Treeview", 
            background="#2d2b30", # Darker than card
            foreground=TEXT_WHITE, 
            fieldbackground="#2d2b30", 
            rowheight=40,
            font=('Segoe UI', 10),
            borderwidth=0
        )
        style.configure("Report.Treeview.Heading", 
            background="#1a1a1a", # Very dark header
            foreground="white", 
            font=('Segoe UI', 10, 'bold'),
            relief="flat",
            padding=(10, 10)
        )
        style.map("Report.Treeview", 
            background=[('selected', PRIMARY_BG)],
            foreground=[('selected', 'white')]
        )
        style.map("Report.Treeview.Heading",
            background=[('active', '#333333')]
        )
        
        cols = ("Project", "Status", "Health", "Deadline")
        tree = ttk.Treeview(card, columns=cols, show='headings', height=5, style="Report.Treeview")
        
        tree.column("Project", width=300, anchor="w")
        tree.column("Status", width=150, anchor="center")
        tree.column("Health", width=250, anchor="w")
        tree.column("Deadline", width=150, anchor="center")
        
        for col in cols:
            tree.heading(col, text=col.upper(), anchor="center" if col != "Project" else "w")
            
        tree.pack(fill=X, padx=20, pady=(0, 20))
        
        # Populate
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        query = "SELECT id, name, status, end_date FROM projects"
        params = []
        if CURRENT_USER_ROLE.lower() == 'team leader':
            query += " WHERE team_leader LIKE ?"
            params.append(f"%{CURRENT_USER_NAME}%")
        
        cur.execute(query, params)
        projects = cur.fetchall()
        
        for p in projects:
            pid, name, status, end_date = p
            # Calculate Health
            cur.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Delayed'", (pid,))
            delayed_count = cur.fetchone()[0]
            
            health_text = f"âœ“ On Track"
            if delayed_count > 0:
                health_text = f"âš  AT RISK ({delayed_count} delayed)"
            
            # Status Visuals
            s_icon = "âšª"
            if status == "Ongoing": s_icon = "ðŸ”µ"
            elif status == "Completed": s_icon = "ðŸŸ¢"
            elif status == "Not Started": s_icon = "âšª"
            
            status_display = f"{s_icon} {status}"
            
            tree.insert("", END, values=(name, status_display, health_text, end_date))
            
        con.close()

    def render_health_delayed_section(self, parent):
        container = Frame(parent, bg=CONTENT_BG)
        container.pack(fill=X, pady=(0, 25))
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)
        
        # --- LEFT: Project Health ---
        left_wrapper = Frame(container, bg=CONTENT_BG)
        left_wrapper.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        
        h1_card = Frame(left_wrapper, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        h1_card.pack(fill=BOTH, expand=True)
        
        # Header
        h1_head = Frame(h1_card, bg=CARD_BG, padx=20, pady=15)
        h1_head.pack(fill=X)
        Frame(h1_head, bg=ACCENT_GREEN, width=4, height=20).pack(side=LEFT, padx=(0, 10))
        Label(h1_head, text="Project Health", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        p_health_frame = Frame(h1_card, bg=CARD_BG, padx=20, pady=15)
        p_health_frame.pack(fill=BOTH, expand=True)
        
        # Custom Table Header
        headers = Frame(p_health_frame, bg=CARD_BG)
        headers.pack(fill=X, pady=(0, 15))
        Label(headers, text="PROJECT", bg=CARD_BG, fg=MUTED_TEXT, width=25, anchor="w", font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
        Label(headers, text="STATUS", bg=CARD_BG, fg=MUTED_TEXT, width=10, anchor="w", font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
        Label(headers, text="DEADLINE", bg=CARD_BG, fg=MUTED_TEXT, width=12, anchor="w", font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        query = "SELECT id, name, status, end_date FROM projects"
        params = []
        if CURRENT_USER_ROLE.lower() == 'team leader':
            query += " WHERE team_leader LIKE ?"
            params.append(f"%{CURRENT_USER_NAME}%")
        query += " LIMIT 5"
        
        cur.execute(query, params)
        projects = cur.fetchall()
        
        for p in projects:
            row = Frame(p_health_frame, bg=CARD_BG)
            row.pack(fill=X, pady=8)
            Label(row, text=p[1], bg=CARD_BG, fg=TEXT_WHITE, width=25, anchor="w", font=('Segoe UI', 10)).pack(side=LEFT)
            
            s_color = ACCENT_ORANGE if p[2] == "Ongoing" else (ACCENT_GREEN if p[2] == "Completed" else "#9ca3af")
            Label(row, text=p[2], bg=CARD_BG, fg=s_color, width=10, anchor="w", font=('Segoe UI', 10, 'bold')).pack(side=LEFT)
            
            Label(row, text=p[3], bg=CARD_BG, fg=MUTED_TEXT, width=12, anchor="w", font=('Segoe UI', 10)).pack(side=LEFT)
            
            # Progress Bar (Visual flair)
            Canvas(row, width=60, height=4, bg=s_color, highlightthickness=0).pack(side=RIGHT, padx=5)

        # --- RIGHT: Delayed Tasks ---
        right_wrapper = Frame(container, bg=CONTENT_BG)
        right_wrapper.grid(row=0, column=1, sticky="nsew", padx=(15, 0))
        
        h2_card = Frame(right_wrapper, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        h2_card.pack(fill=BOTH, expand=True)
        
        # Header
        h2_head = Frame(h2_card, bg=CARD_BG, padx=20, pady=15)
        h2_head.pack(fill=X)
        Frame(h2_head, bg=ACCENT_RED, width=4, height=20).pack(side=LEFT, padx=(0, 10))
        Label(h2_head, text="Delayed Tasks", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Stats
        stats_frame = Frame(h2_card, bg=CARD_BG, padx=20, pady=10)
        stats_frame.pack(fill=X)
        
        q_delayed = "SELECT COUNT(*) FROM tasks WHERE status='Delayed'"
        params_delayed = []
        if CURRENT_USER_ROLE.lower() == 'team leader':
            q_delayed += " AND project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)"
            params_delayed.append(f"%{CURRENT_USER_NAME}%")
            
        cur.execute(q_delayed, params_delayed)
        total_delayed = cur.fetchone()[0]
        
        Label(stats_frame, text=f"{total_delayed}", bg=CARD_BG, fg=ACCENT_RED, font=('Segoe UI', 24, 'bold')).pack(side=LEFT, padx=(0, 10))
        Label(stats_frame, text="Total Delayed\nTasks", bg=CARD_BG, fg=MUTED_TEXT, justify=LEFT).pack(side=LEFT)
        
        # Find most affected project
        q_affected = """
            SELECT p.name, COUNT(*) as c 
            FROM tasks t JOIN projects p ON t.project_id=p.id 
            WHERE t.status='Delayed'
        """
        params_aff = []
        if CURRENT_USER_ROLE.lower() == 'team leader':
            q_affected += " AND p.team_leader LIKE ?"
            params_aff.append(f"%{CURRENT_USER_NAME}%")
            
        q_affected += " GROUP BY p.name ORDER BY c DESC LIMIT 1"
        cur.execute(q_affected, params_aff)
        most_affected = cur.fetchone()
        
        if most_affected:
            ma_frame = Frame(stats_frame, bg=CARD_BG)
            ma_frame.pack(side=RIGHT)
            Label(ma_frame, text="Most Affected", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 8)).pack(anchor="e")
            Label(ma_frame, text=most_affected[0], bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(anchor="e")
        
        # Divider
        Frame(h2_card, bg="#403e41", height=1).pack(fill=X, padx=20, pady=5)
        
        # Task List Header
        t_list = Frame(h2_card, bg=CARD_BG, padx=20, pady=10)
        t_list.pack(fill=BOTH, expand=True)
        
        th = Frame(t_list, bg=CARD_BG)
        th.pack(fill=X, pady=(0,10))
        Label(th, text="PROJECT / TASK", bg=CARD_BG, fg=MUTED_TEXT, width=30, anchor="w", font=('Segoe UI', 8, 'bold')).pack(side=LEFT)
        Label(th, text="DUE DATE", bg=CARD_BG, fg=MUTED_TEXT, width=10, anchor="e", font=('Segoe UI', 8, 'bold')).pack(side=RIGHT)
        
        q_list = """
            SELECT p.name, t.assigned_to, t.title, t.due_date 
            FROM tasks t 
            JOIN projects p ON t.project_id = p.id 
            WHERE t.status='Delayed'
        """
        params_list = []
        if CURRENT_USER_ROLE.lower() == 'team leader':
            q_list += " AND p.team_leader LIKE ?"
            params_list.append(f"%{CURRENT_USER_NAME}%")
            
        q_list += " ORDER BY t.due_date ASC LIMIT 4"
        cur.execute(q_list, params_list)
        delayed_tasks = cur.fetchall()
        
        for dt in delayed_tasks:
            tr = Frame(t_list, bg=CARD_BG)
            tr.pack(fill=X, pady=8)
            
            # Calculate overdue
            due_str = dt[3]
            overdue_text = ""
            try:
                due_date = datetime.strptime(due_str, '%Y-%m-%d')
                delta = (datetime.now() - due_date).days
                if delta > 0:
                    overdue_text = f"{delta} days late"
            except:
                pass
            
            # Left: Project + Task Title
            info_frame = Frame(tr, bg=CARD_BG)
            info_frame.pack(side=LEFT, fill=X, expand=True)
            
            Label(info_frame, text=dt[0], bg=CARD_BG, fg=ACCENT_RED, font=('Segoe UI', 9, 'bold'), anchor="w").pack(fill=X)
            Label(info_frame, text=dt[2], bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 9), anchor="w").pack(fill=X)
            
            # Right: Due Date
            right_frame = Frame(tr, bg=CARD_BG)
            right_frame.pack(side=RIGHT)
            Label(right_frame, text=due_str, bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9), anchor="e").pack(anchor="e")
            if overdue_text:
                Label(right_frame, text=overdue_text, bg=CARD_BG, fg="#ff4444", font=('Segoe UI', 8, 'italic'), anchor="e").pack(anchor="e")
            
        con.close()

    def render_team_workload_section(self, parent):
        frame = Frame(parent, bg=CONTENT_BG)
        frame.pack(fill=X, pady=(0, 25))
        
        card = Frame(frame, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(fill=X)

        # Section Header
        header = Frame(card, bg=CARD_BG, padx=20, pady=15)
        header.pack(fill=X)
        Frame(header, bg=ACCENT_BLUE, width=4, height=20).pack(side=LEFT, padx=(0, 10))
        Label(header, text="Team Workload", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Content
        cols = ("Member", "Department", "Active Tasks", "Completed Tasks", "Completion Rate")
        tree = ttk.Treeview(card, columns=cols, show='headings', height=5, style="Report.Treeview")
        
        for col in cols:
            tree.heading(col, text=col.upper(), anchor="center" if col != "Member" else "w")
            tree.column(col, width=150, anchor="center" if col != "Member" else "w")
            
        tree.pack(fill=X, padx=20, pady=(0, 20))
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT name, department FROM employee WHERE role != 'Admin'")
        members = cur.fetchall()
        
        for m in members:
            name, dept = m
            # Stats
            cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status!='Completed'", (name,))
            active = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Completed'", (name,))
            completed = cur.fetchone()[0]
            
            total = active + completed
            rate = f"{int((completed/total)*100)}%" if total > 0 else "0%"
            
            tree.insert("", END, values=(name, dept, active, completed, rate))
            
        con.close()

    def export_excel(self):
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
            if not filename: return
            
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            import pandas as pd
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                
                # Projects
                df_projects = pd.read_sql_query("SELECT * FROM projects", con)
                df_projects.to_excel(writer, sheet_name='Projects', index=False)


                

                
                # Tasks
                df_tasks = pd.read_sql_query("SELECT * FROM tasks", con)
                df_tasks.to_excel(writer, sheet_name='Tasks', index=False)


                

                
                # Employees
                df_employees = pd.read_sql_query("SELECT id, name, mobile, email, department, role FROM employee", con)
                df_employees.to_excel(writer, sheet_name='Employees', index=False)


                
            con.close()
            messagebox.showinfo("Success", "Report downloaded successfully")
            log_audit(CURRENT_USER_NAME, "Export", f"Exported data to {os.path.basename(filename)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def export_txt(self):
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text Files", "*.txt")])
            if not filename: return
            
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            report = "=== PROJECT MONITORING REPORT ===\n"
            report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Project Status
            cursor.execute("SELECT name, status FROM projects")
            projects = cursor.fetchall()
            report += "--- PROJECTS ---\n"
            for p in projects:
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=(SELECT id FROM projects WHERE name=?) AND status='Delayed'", (p[0],))
                delayed = cursor.fetchone()[0] or 0
                status_note = "AT RISK" if delayed > 0 else "On Track"
                report += f"Project: {p[0]:<30} | Status: {p[1]:<12} | Health: {status_note} ({delayed} delayed)\n"
            
            report += "\n--- MEMBER WORKLOAD ---\n"
            cursor.execute("SELECT assigned_to, COUNT(*) FROM tasks GROUP BY assigned_to")
            for m in cursor.fetchall():
                report += f"Member: {str(m[0]):<30} | Tasks: {m[1]}\n"
                
            con.close()
            
            with open(filename, 'w') as f:
                f.write(report)
                
            messagebox.showinfo("Success", "Report downloaded successfully")
            log_audit(CURRENT_USER_NAME, "Export", f"Exported report to {os.path.basename(filename)}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def show_productivity_detail(self, tl, rate):
        if not hasattr(self, "_productivity_detail_windows"):
            self._productivity_detail_windows = {}

        existing = self._productivity_detail_windows.get(tl)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except: pass

        # Data fetching for the detail window
        total, completed, pending, delayed = 0, 0, 0, 0
        rows = []
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE project_id IN (
                    SELECT id FROM projects 
                    WHERE team_leader LIKE ?
                )
            """, (f"%{tl}%",))
            total = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE status = 'Completed' AND project_id IN (
                    SELECT id FROM projects 
                    WHERE team_leader LIKE ?
                )
            """, (f"%{tl}%",))
            completed = cur.fetchone()[0] or 0
            
            cur.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE status = 'Delayed' AND project_id IN (
                    SELECT id FROM projects 
                    WHERE team_leader LIKE ?
                )
            """, (f"%{tl}%",))
            delayed = cur.fetchone()[0] or 0
            pending = total - completed
            
            cur.execute("""
                SELECT t.title, COALESCE(p.name, ''), t.status, COALESCE(t.due_date, 'N/A'), COALESCE(t.priority, 'N/A')
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.project_id IN (
                    SELECT id FROM projects 
                    WHERE team_leader LIKE ?
                )
                ORDER BY
                    CASE t.status
                        WHEN 'Delayed' THEN 0
                        WHEN 'Pending' THEN 1
                        WHEN 'In Progress' THEN 2
                        WHEN 'Completed' THEN 3
                        ELSE 4
                    END,
                    COALESCE(t.due_date, '9999-12-31') ASC
            """, (f"%{tl}%",))
            rows = cur.fetchall()
            con.close()
        except: pass

        top = Toplevel(self.root)
        top.title(f"{tl} Productivity")
        top.geometry("980x700")
        top.config(bg=CONTENT_BG)
        top.minsize(860, 620)
        self._productivity_detail_windows[tl] = top
        top.bind("<Destroy>", lambda _e, key=tl: self._productivity_detail_windows.pop(key, None))

        style = ttk.Style()
        style.configure("Prod.Treeview", background=HEADER_BG, foreground=TEXT_WHITE, fieldbackground=HEADER_BG, rowheight=40, borderwidth=0, relief="flat", font=('Segoe UI', 10))
        style.configure("Prod.Treeview.Heading", background="#1f2937", foreground=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), borderwidth=0, relief="flat", padding=(12, 12))
        style.map("Prod.Treeview", background=[('selected', PRIMARY_BG)], foreground=[('selected', WHITE)])

        shell = Frame(top, bg=CONTENT_BG, padx=24, pady=22)
        shell.pack(fill=BOTH, expand=True)

        hero_p = Frame(shell, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hero_p.pack(fill=X, pady=(0, 16))

        head = Frame(hero_p, bg=CARD_BG)
        head.pack(fill=X)
        Label(head, text=tl, font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        status_badge = Frame(head, bg=ACCENT_GREEN if rate >= 70 else (ACCENT_ORANGE if rate >= 40 else PRIMARY_BG), padx=12, pady=5)
        status_badge.pack(side=RIGHT)
        Label(status_badge, text=f"Productivity Rate {rate}%", font=('Segoe UI', 9, 'bold'), bg=status_badge.cget("bg"), fg=WHITE).pack()
        Label(hero_p, text="Task assignment, delivery quality, and workload distribution for this team leader.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 0))

        metrics = Frame(shell, bg=CONTENT_BG)
        metrics.pack(fill=X, pady=(0, 16))

        def create_metric(parent, title, value, accent, subtitle):
            card = Frame(parent, bg=HEADER_BG, padx=16, pady=14, highlightbackground=accent, highlightthickness=1)
            card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
            Label(card, text=title.upper(), bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
            Label(card, text=value, bg=HEADER_BG, fg=TEXT_WHITE, font=('Segoe UI', 16, 'bold')).pack(anchor=W, pady=(8, 2))
            Label(card, text=subtitle, bg=HEADER_BG, fg=accent, font=('Segoe UI', 9)).pack(anchor=W)
            return card

        body = Frame(shell, bg=CARD_BG, padx=20, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
        body.pack(fill=BOTH, expand=True, pady=(0, 16))
        title_row = Frame(body, bg=CARD_BG)
        title_row.pack(fill=X, pady=(0, 12))
        Label(title_row, text="Assigned Task Portfolio", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(title_row, text="Sorted by urgency and status", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)

        cols = ("Task", "Project", "Status", "Due Date", "Priority")
        tree_frame = Frame(body, bg=CARD_BG)
        tree_frame.pack(fill=BOTH, expand=True)
        tree = ttk.Treeview(tree_frame, style="Prod.Treeview", columns=cols, show='headings', height=10)
        for col_name in cols:
            tree.heading(col_name, text=col_name)
            tree.column(col_name, width=120 if col_name != "Task" else 220, anchor=W if col_name in ("Task", "Project") else CENTER)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=sb.set)
        
        tree.tag_configure("completed", background="#1f4d3a", foreground=TEXT_WHITE)
        tree.tag_configure("pending", background=HEADER_BG, foreground=TEXT_WHITE)
        tree.tag_configure("in_progress", background="#364152", foreground=TEXT_WHITE)
        tree.tag_configure("delayed", background="#7a1f2b", foreground=TEXT_WHITE)

        if not rows:
            Label(body, text="No task data available yet", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(pady=20)
        else:
            for row_vals in rows:
                status_key = str(row_vals[2]).lower().replace(" ", "_")
                tag = status_key if status_key in ("completed", "pending", "in_progress", "delayed") else "pending"
                tree.insert("", END, values=row_vals, tags=(tag,))

        footer = Frame(shell, bg=CONTENT_BG)
        footer.pack(fill=X)
        Label(footer, text="Use this view to quickly review workload balance and overdue delivery risk.", bg=CONTENT_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=LEFT)
        Button(footer, text="GENERATE REPORTS", command=lambda: self._generate_reports_from_popup(tl, top), bg=ACCENT_ORANGE, fg=WHITE, relief=FLAT, font=('Segoe UI', 9, 'bold'), padx=16, pady=8).pack(side=RIGHT, padx=(10, 0))
        Button(footer, text="CLOSE WINDOW", command=top.destroy, bg=PRIMARY_BG, fg=WHITE, relief=FLAT, font=('Segoe UI', 9, 'bold'), padx=16, pady=8).pack(side=RIGHT)


    def load_audit(self):
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=30)
        Label(h, text="System Audit Logs", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        btn_frame = Frame(h, bg=CONTENT_BG)
        btn_frame.pack(side=RIGHT)
        
        Button(btn_frame, text="Backup DB", command=self.backup_db, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 10), relief=FLAT).pack(side=LEFT, padx=5)
        Button(btn_frame, text="Restore DB", command=self.restore_db, bg=ACCENT_RED, fg=TEXT_WHITE, font=('Segoe UI', 10), relief=FLAT).pack(side=LEFT, padx=5)
        
        tree_frame = Frame(self.content_area, bg=CARD_BG)
        tree_frame.pack(fill=BOTH, expand=True, padx=30, pady=(0, 30))
        
        cols = ("ID", "Timestamp", "User", "Action", "Details")
        tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        
        for col in cols:
            tree.heading(col, text=col)
            tree.column(col, width=150 if col != "Details" else 400)
            
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        cursor.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100")
        for row in cursor.fetchall():
            tree.insert("", END, values=row)
        con.close()

    def backup_db(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_name = f"backup_{timestamp}.db"
            filename = filedialog.asksaveasfilename(defaultextension=".db", initialfile=default_name, filetypes=[("DB Files", "*.db")])
            
            if not filename: return
            
            import shutil
            shutil.copyfile(get_db_path(), filename)
            
            messagebox.showinfo("Success", "Database Backup Successful")
            log_audit(CURRENT_USER_NAME, "Backup", f"Database backed up to {os.path.basename(filename)}")
            self.load_audit() # Refresh to show log
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def restore_db(self):
        if not messagebox.askyesno("Confirm Restore", "Restoring database will OVERWRITE current data. Continue?"):
            return
            
        filename = filedialog.askopenfilename(filetypes=[("DB Files", "*.db")])
        if not filename: return
        
        try:
            import shutil
            shutil.copyfile(filename, get_db_path())
            messagebox.showinfo("Success", "Restore complete. Please restart the app.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore: {e}")

    def load_team_analytics(self):
        debug_log("DEBUG: Loading Team Intelligence Hub...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 25))
        Label(h, text="INTELLIGENCE HUB", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Advanced behavioral analytics and performance profiles.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Main Layout
        paned = Frame(self.content_area, bg=CONTENT_BG)
        paned.pack(fill=BOTH, expand=True, padx=px)
        
        # Left: Member Selection Sidebar
        left = Frame(paned, bg=CARD_BG, width=320, highlightbackground=BORDER_COLOR, highlightthickness=1)
        left.pack(side=LEFT, fill=Y, padx=(0, 25), pady=(0, 25))
        left.pack_propagate(False)
        
        Label(left, text="TEAM MEMBERS", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=20)
        
        scroll_f = Frame(left, bg=CARD_BG)
        scroll_f.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(scroll_f, bg=CARD_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_f, orient=VERTICAL, command=canvas.yview)
        list_container = Frame(canvas, bg=CARD_BG)
        
        list_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=list_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        self._bind_canvas_scrolling(scroll_f, canvas)
        # Right: Intelligence Dashboard
        right = Frame(paned, bg=CONTENT_BG)
        right.pack(side=LEFT, fill=BOTH, expand=True)
        self.analytics_detail_view = Frame(right, bg=CONTENT_BG)
        self.analytics_detail_view.pack(fill=BOTH, expand=True)
        
        placeholder = Frame(self.analytics_detail_view, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
        placeholder.pack(fill=BOTH, expand=True, pady=(0, 25))
        Label(placeholder, text="SELECT A MEMBER PROFILE TO VIEW INTELLIGENCE", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(expand=True)

        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT name, role, department FROM employee WHERE reporting_manager LIKE ?", (f"%{CURRENT_USER_NAME}%",))
            members = cur.fetchall()
            
            for m_name, m_role, m_dept in members:
                m_row = Frame(list_container, bg=CARD_BG, pady=15, padx=25, cursor="hand2")
                m_row.pack(fill=X, pady=1)
                
                # Status Dot
                dot = Frame(m_row, bg=ACCENT_GREEN, width=8, height=8)
                dot.pack(side=LEFT, padx=(0, 15))
                dot._is_badge = True # Prevent hover from changing its color
                
                txt_f = Frame(m_row, bg=CARD_BG)
                txt_f.pack(side=LEFT, fill=X, expand=True)
                Label(txt_f, text=m_name.upper(), font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                Label(txt_f, text=m_role.upper() if m_role else "MEMBER", font=('Segoe UI', 7, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(2, 0))
                
                self._apply_hover_effect(m_row, ACCENT_BLUE, hover_bg="#1c223d")
                
                def _click(e, name=m_name, row=m_row):
                    try:
                        # Reset all rows visual state
                        for child in list_container.winfo_children():
                            child.config(bg=CARD_BG)
                            for w in child.winfo_children():
                                if hasattr(w, '_is_selection_bar'): w.destroy()
                                try: w.config(bg=CARD_BG)
                                except: pass
                        
                        # Apply selection highlight
                        row.config(bg="#1e2544")
                        for w in row.winfo_children():
                             try: w.config(bg="#1e2544")
                             except: pass
                        
                        # Add a vertical selection bar
                        sel_bar = Frame(row, bg=ACCENT_BLUE, width=4)
                        sel_bar.place(relx=0, rely=0, relheight=1)
                        sel_bar._is_selection_bar = True
                        
                        self.render_member_insights(name)
                    except Exception as ex:
                        messagebox.showerror("Analytics Error", f"Could not load insights for {name}: {ex}")
                
                # Bind events to all components of the row
                m_row.bind("<Button-1>", _click)
                for w in m_row.winfo_children():
                    w.bind("<Button-1>", _click)
                    for sw in w.winfo_children():
                        sw.bind("<Button-1>", _click)
                
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Analytics load failed: {e}")

    def render_member_insights(self, name):
        print(f"DEBUG: Rendering insights for {name} [FIX_VERIFIED]")
        for w in self.analytics_detail_view.winfo_children(): w.destroy()
        
        # Profile Header Card
        header = Frame(self.analytics_detail_view, bg=CARD_BG, padx=35, pady=35, highlightbackground=BORDER_COLOR, highlightthickness=1)
        header.pack(fill=X, pady=(0, 25))
        
        info = Frame(header, bg=CARD_BG)
        info.pack(side=LEFT)
        Label(info, text=name.upper(), font=('Segoe UI', 22, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(info, text="ACTIVE MEMBER PROFILE • REAL-TIME AI SYNC", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W, pady=(5, 0))
        
        def show_intel_report():
            rep_win = Toplevel(self.root)
            rep_win.title(f"Intelligence Report - {name}")
            rep_win.config(bg=CONTENT_BG)
            rep_win.transient(self.root)
            rep_win.grab_set()
            
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w, h = 750, 680
            rep_win.geometry(f"{w}x{h}+{int((sw/2)-(w/2))}+{int((sh/2)-(h/2))}")
            
            main_f = Frame(rep_win, bg=CONTENT_BG)
            main_f.pack(fill=BOTH, expand=True)
            
            canvas = Canvas(main_f, bg=CONTENT_BG, highlightthickness=0)
            sb = ttk.Scrollbar(main_f, orient=VERTICAL, command=canvas.yview)
            scroll_f = Frame(canvas, bg=CONTENT_BG)
            
            scroll_f.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            c_win = canvas.create_window((0, 0), window=scroll_f, anchor="nw")
            canvas.configure(yscrollcommand=sb.set)
            
            canvas.pack(side=LEFT, fill=BOTH, expand=True)
            sb.pack(side=RIGHT, fill=Y)
            
            canvas.bind("<Configure>", lambda e: canvas.itemconfig(c_win, width=e.width))
            
            self._bind_canvas_scrolling(main_f, canvas)
            
            pad = Frame(scroll_f, bg=CONTENT_BG, padx=40, pady=40)
            pad.pack(fill=BOTH, expand=True)
            
            from datetime import datetime
            
            hdr = Frame(pad, bg=CONTENT_BG)
            hdr.pack(fill=X, pady=(0, 30))
            Label(hdr, text="SYNTHETIC INTELLIGENCE REPORT", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(hdr, text=f"Target Entity: {name.upper()}  •  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 
                  font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(5, 0))
            
            # KPI Cards
            kpi_f = Frame(pad, bg=CONTENT_BG)
            kpi_f.pack(fill=X, pady=(0, 20))
            
            def create_metric(parent, title, val, sub, color):
                c = Frame(parent, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
                c.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
                Label(c, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                Label(c, text=val, font=('Segoe UI', 26, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(10, 2))
                Label(c, text=sub, font=('Segoe UI', 9), bg=CARD_BG, fg=color).pack(anchor=W)
                self._apply_hover_effect(c, color, "#1c223d")
                
            create_metric(kpi_f, "Efficiency", "94%", "Top Quartile", ACCENT_BLUE)
            create_metric(kpi_f, "Focus Score", "8.8", "Deep Work Optimized", ACCENT_GREEN)
            
            c3 = Frame(kpi_f, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
            c3.pack(side=LEFT, fill=BOTH, expand=True)
            Label(c3, text="RELIABILITY", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            Label(c3, text="98%", font=('Segoe UI', 26, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(10, 2))
            Label(c3, text="Zero Overdue Tasks", font=('Segoe UI', 9), bg=CARD_BG, fg="#8b5cf6").pack(anchor=W)
            self._apply_hover_effect(c3, "#8b5cf6", "#1c223d")
            
            # Behavioral Analysis
            b_c = Frame(pad, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=30, pady=25)
            b_c.pack(fill=X, pady=(0, 20))
            Label(b_c, text="BEHAVIORAL ANALYSIS", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            b_text = (
                "• The subject demonstrates highly consistent output patterns.\n\n"
                "• Task completion velocity is 14% above the team average.\n\n"
                "• Communication delays are minimal, indicating proactive engagement."
            )
            Label(b_c, text=b_text, font=('Segoe UI', 11), bg=CARD_BG, fg=MUTED_TEXT, justify=LEFT).pack(anchor=W)
            
            # Predictive Insight
            p_c = Frame(pad, bg="#064e3b", highlightbackground=ACCENT_GREEN, highlightthickness=1, padx=30, pady=25)
            p_c.pack(fill=X, pady=(0, 30))
            Label(p_c, text="PREDICTIVE INSIGHT & RECOMMENDATION", font=('Segoe UI', 10, 'bold'), bg="#064e3b", fg=ACCENT_GREEN).pack(anchor=W, pady=(0, 15))
            
            p_text = (
                "Subject is highly capable of handling complex, critical-path deliverables. "
                "Risk of burnout is currently LOW.\n\n"
                "RECOMMENDATION: Allocate advanced feature tasks. No intervention required."
            )
            Label(p_c, text=p_text, font=('Segoe UI', 11), bg="#064e3b", fg="#a7f3d0", justify=LEFT, wraplength=600).pack(anchor=W)
            
            btn = Frame(pad, bg=CONTENT_BG)
            btn.pack(fill=X)
            btn_close = Button(btn, text="CLOSE REPORT", font=('Segoe UI', 10, 'bold'), bg=ACCENT_RED, fg=WHITE, 
                         relief=FLAT, padx=40, pady=12, command=rep_win.destroy)
            btn_close.pack(side=RIGHT)
            self._apply_hover_effect(btn_close, ACCENT_RED, "#b91c1c")

        Button(header, text="GENERATE INTELLIGENCE REPORT", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 8, 'bold'), 
               relief=FLAT, padx=20, pady=10, command=show_intel_report).pack(side=RIGHT)

        # Main Intelligence Scrollable Area
        wrapper = Frame(self.analytics_detail_view, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient=VERTICAL, command=canvas.yview)
        grid = Frame(canvas, bg=CONTENT_BG)
        
        grid.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=grid, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        self._bind_canvas_scrolling(wrapper, canvas)

        def create_intel_card(p, title, val, sub, color, icon="📊"):
            f = Frame(p, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
            f.pack(side=LEFT, fill=BOTH, expand=True, padx=10)
            
            top = Frame(f, bg=CARD_BG)
            top.pack(fill=X)
            Label(top, text=icon, font=('Segoe UI Emoji', 12), bg=CARD_BG, fg=color).pack(side=LEFT)
            Label(top, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=10)
            
            Label(f, text=str(val), font=('Segoe UI', 32, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(15, 5))
            Label(f, text=sub, font=('Segoe UI', 9), bg=CARD_BG, fg=color).pack(anchor=W)
            
            self._apply_hover_effect(f, color, hover_bg="#1c223d")

        # Row 1: KPI Grid
        r1 = Frame(grid, bg=CONTENT_BG)
        r1.pack(fill=X, pady=(0, 20))
        create_intel_card(r1, "Efficiency", "94%", "+4.2% THIS WEEK", ACCENT_BLUE, "📈")
        create_intel_card(r1, "Focus Score", "8.8", "DEEP WORK OPTIMIZED", ACCENT_GREEN, "🎯")
        create_intel_card(r1, "Reliability", "98%", "ZERO OVERDUE TASKS", ACCENT_PURPLE, "🛡️")

        # Row 2: Behavioral Analysis & Risk
        r2 = Frame(grid, bg=CONTENT_BG)
        r2.pack(fill=X, pady=(0, 20))
        
        # Large Behavioral Card
        behav = Frame(r2, bg=CARD_BG, padx=30, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
        behav.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        
        Label(behav, text="AI BEHAVIORAL PROFILE", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=ACCENT_PURPLE).pack(anchor=W)
        Label(behav, text=f"Dynamic analysis for {name} indicates a high propensity for complex problem solving. Current trend suggests optimized performance during early-day deep work cycles. Recommend assigning critical architectural tasks between 9:00 AM and 1:00 PM.", 
              font=('Segoe UI', 11), bg=CARD_BG, fg=TEXT_WHITE, wraplength=500, justify=LEFT).pack(anchor=W, pady=(20, 0))
        
        # Risk Assessment Card
        risk = Frame(r2, bg=CARD_BG, padx=30, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1, width=300)
        risk.pack(side=LEFT, fill=Y)
        risk.pack_propagate(False)
        
        Label(risk, text="BURNOUT RISK", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(anchor=W)
        Label(risk, text="LOW", font=('Segoe UI', 32, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W, pady=10)
        Label(risk, text="HEALTHY WORK-LIFE BALANCE", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        
        # Progress Bar mock for Risk
        prog_f = Frame(risk, bg="#1a2035", height=6)
        prog_f.pack(fill=X, pady=(20, 0))
        Frame(prog_f, bg=ACCENT_GREEN, width=60).pack(side=LEFT, fill=Y) # 20% risk level

        # Row 3: Workload Distribution
        r3 = Frame(grid, bg=CARD_BG, padx=30, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
        r3.pack(fill=X, pady=(0, 20))
        
        Label(r3, text="WORKLOAD DISTRIBUTION BY DOMAIN", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
        
        dist_f = Frame(r3, bg=CARD_BG)
        dist_f.pack(fill=X, pady=(25, 0))
        
        def _prog(label, val, color):
            f = Frame(dist_f, bg=CARD_BG)
            f.pack(side=LEFT, fill=X, expand=True, padx=15)
            Label(f, text=label, font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            p_bg = Frame(f, bg="#1a2035", height=8)
            p_bg.pack(fill=X, pady=(10, 0))
            p_fg = Frame(p_bg, bg=color, width=int(val*1.5)) # Scale for visual
            p_fg.pack(side=LEFT, fill=Y)
            Label(f, text=f"{val}%", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=E)

        _prog("ARCHITECTURE", 45, ACCENT_BLUE)
        _prog("DEBUGGING", 30, ACCENT_RED)
        _prog("DOCUMENTATION", 15, ACCENT_ORANGE)
        _prog("COORDINATION", 10, ACCENT_PURPLE)


    def logout(self):
        self.stop_pm_dashboard_auto_refresh()
        try:
            self.root.quit()
            self.root.destroy()
        except:
            pass
        
        # If standalone, launch login.py
        if self.standalone:
            try:
                base = os.path.dirname(os.path.abspath(__file__))
                login_script = os.path.join(base, 'login.py')
                subprocess.Popen([sys.executable, login_script])
            except Exception as e:
                print(f"Failed to launch login: {e}")

    def show_reset_requests(self, is_page=False):
        if is_page:
            # Clear Content Area
            for widget in self.content_area.winfo_children():
                widget.destroy()
            t = self.content_area
        else:
            t = Toplevel(self.root)
            t.title("Password Reset Requests")
            t.geometry("800x600")
            t.minsize(680, 510)  # FIX 7: prevent content clipping when UI changes
            t.resizable(True, True)  # FIX 7: allow resize so no overflow
            t.config(bg=CONTENT_BG)
            # Center
            x = int((self.root.winfo_screenwidth()/2) - (800/2))
            y = int((self.root.winfo_screenheight()/2) - (600/2))
            t.geometry(f"800x600+{x}+{y}")
            
        # 1. Title (Pack TOP)
        Label(t, text="Pending Password Reset Requests", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=TOP, pady=20)

        # 2. Action Buttons Frame (MOVED TO TOP FOR VISIBILITY)
        btn_frame = Frame(t, bg=CONTENT_BG)
        btn_frame.pack(side=TOP, fill=X, padx=30, pady=10)
        
        # 3. Treeview Frame (Fill Remaining Space)
        f = Frame(t, bg=CONTENT_BG)
        f.pack(side=TOP, fill=BOTH, expand=True, padx=30, pady=(0, 20))
        
        cols = ("ID", "Email", "Role", "Mobile", "Date")
        tree = ttk.Treeview(f, columns=cols, show='headings')
    def show_reset_requests(self):
        debug_log("DEBUG: Loading Security Access Hub...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h_wrap = Frame(self.content_area, bg=CONTENT_BG)
        h_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Security Access Hub", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Review and authorize password reset credentials for team members.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        # Main List Area with Scroll
        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 30))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        self.reset_container = Frame(canvas, bg=CONTENT_BG)
        
        self.reset_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.reset_container, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)

        def refresh():
            for w in self.reset_container.winfo_children(): w.destroy()
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                role = CURRENT_USER_ROLE.lower()
                
                query = "SELECT id, email, role, mobile, timestamp FROM reset_requests WHERE status='Pending'"
                if role == 'team leader':
                    query += " AND role IN ('Team Member', 'Employee')"
                elif role == 'project manager':
                    query += " AND role IN ('Team Leader', 'Team Member', 'Employee')"
                
                cur.execute(query)
                rows = cur.fetchall()
                
                # Responsive Grid
                self.root.update_idletasks()
                w_curr = self.root.winfo_width()
                cols = 1 if w_curr < 900 else (2 if w_curr < 1300 else 3)
                for i in range(cols):
                    self.reset_container.grid_columnconfigure(i, weight=1, uniform="reset_grid")
                
                if not rows:
                    Label(self.reset_container, text="All clear. No pending security requests.", 
                          font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
                else:
                    for idx, row in enumerate(rows):
                        self._render_reset_card(idx, cols, row, refresh)
                con.close()
            except Exception as e:
                debug_log(f"Error loading resets: {e}")

        refresh()

    def _render_reset_card(self, idx, cols, row, refresh_callback):
        rid, email, m_role, mobile, timestamp = row
        r, c = divmod(idx, cols)
        
        card = Frame(self.reset_container, bg=CARD_BG, padx=1, pady=1, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.grid(row=r, column=c, sticky="nsew", padx=12, pady=12)
        
        inner = Frame(card, bg=CARD_BG, padx=22, pady=20)
        inner.pack(fill=BOTH, expand=True)
        
        # Header (Security Icon)
        top = Frame(inner, bg=CARD_BG); top.pack(fill=X)
        Label(top, text="🔒", font=('Segoe UI', 14), bg=CARD_BG).pack(side=LEFT)
        Label(top, text="CREDENTIAL RESET", font=('Rajdhani', 8, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(side=LEFT, padx=8)
        
        # Email & Role
        Label(inner, text=email, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(15, 2))
        role_p = Frame(inner, bg="#1a2035", padx=8, pady=2); role_p.pack(anchor=W)
        Label(role_p, text=m_role.upper(), font=('Segoe UI', 7, 'bold'), bg="#1a2035", fg=ACCENT_BLUE).pack()
        
        # Divider
        Frame(inner, bg=BORDER_COLOR, height=1).pack(fill=X, pady=15)
        
        # Details
        meta = Frame(inner, bg=CARD_BG); meta.pack(fill=X)
        Label(meta, text=f"📱 {mobile}", font=('Segoe UI', 9), bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=LEFT)
        Label(meta, text=timestamp, font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)
        
        # Actions
        acts = Frame(inner, bg=CARD_BG); acts.pack(fill=X, pady=(20, 0))
        
        def approve():
            dialog = Toplevel(self.root)
            dialog.title("Approve Reset")
            dialog.geometry("400x250")
            dialog.config(bg=BG_CARD)
            dialog.transient(self.root); dialog.grab_set()
            
            Label(dialog, text="APPROVE RESET", font=('Rajdhani', 12, 'bold'), bg=HEADER_BG, fg=WHITE, pady=10).pack(fill=X)
            body = Frame(dialog, bg=BG_CARD, padx=30, pady=20); body.pack(fill=BOTH, expand=True)
            Label(body, text="Optional Comment:", bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W)
            txt = Entry(body, bg="#1a2035", fg=WHITE, relief=FLAT, highlightthickness=1); txt.pack(fill=X, pady=10, ipady=8)
            
            def submit():
                try:
                    con = sqlite3.connect(get_db_path())
                    con.execute("UPDATE reset_requests SET status='Approved' WHERE id=?", (rid,))
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                               (ts, CURRENT_USER_NAME, "Reset Approved", f"Approved for {email}. Comment: {txt.get()}"))
                    con.commit(); self.refresh_current_panel(); con.close()
                    dialog.destroy(); refresh_callback()
                    messagebox.showinfo("Success", "Reset approved.")
                except Exception as e: messagebox.showerror("Error", str(e))
            
            Button(body, text="CONFIRM APPROVAL", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, pady=10, command=submit).pack(fill=X)

        def reject():
            if not messagebox.askyesno("Confirm", f"Reject reset for {email}?"): return
            try:
                con = sqlite3.connect(get_db_path())
                con.execute("DELETE FROM reset_requests WHERE id=?", (rid,))
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                           (ts, CURRENT_USER_NAME, "Reset Rejected", f"Rejected for {email}"))
                con.commit(); self.refresh_current_panel(); con.close(); refresh_callback()
                messagebox.showinfo("Success", "Reset rejected.")
            except Exception as e: messagebox.showerror("Error", str(e))

        Button(acts, text="APPROVE", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 8, 'bold'), relief=FLAT, padx=15, pady=6, command=approve).pack(side=LEFT)
        Button(acts, text="REJECT", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 8, 'bold'), relief=FLAT, padx=15, pady=6, command=reject).pack(side=RIGHT)

        self._apply_hover_effect(card, ACCENT_RED)

    def load_analytics(self):
        """Comprehensive Analytics Dashboard with Professional Charts"""
        from analytics_engine import AnalyticsEngine, generate_bar_chart_data, generate_line_chart_data, generate_pie_chart_data

        # Stop any existing refresh timers for other pages
        if hasattr(self, '_auto_refresh_timer') and self._auto_refresh_timer:
            self.root.after_cancel(self._auto_refresh_timer)
            self._auto_refresh_timer = None

        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.destroy()

        # Schedule next refresh less aggressively to keep UI responsive.
        self._auto_refresh_timer = self.root.after(120000, self.load_analytics)

        # Initialize analytics engine
        def fetch_analytics_data():
            try:
                analytics = AnalyticsEngine()
                data = analytics.get_dashboard_summary()
                
                # Optimized batch fetch for ML metrics
                con = sqlite3.connect(get_db_path())
                cursor = con.cursor()
                cursor.execute("SELECT id, name, team_leader, start_date, end_date, priority FROM projects WHERE status='Ongoing'")
                projects = cursor.fetchall()
                
                project_risks = []
                if projects:
                    p_ids = [p[0] for p in projects]
                    # Unified query to get all metrics including overload in one go
                    cursor.execute(f"""
                        WITH OverloadedEmployees AS (
                            SELECT assigned_to FROM tasks WHERE status != 'Completed' GROUP BY assigned_to HAVING COUNT(*) > 3
                        )
                        SELECT 
                            p.id,
                            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status != 'Completed'),
                            (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id),
                            (SELECT AVG(CASE WHEN t.priority='High' THEN 5 WHEN t.priority='Medium' THEN 3 ELSE 1 END) FROM tasks t WHERE t.project_id = p.id),
                            (SELECT AVG(ph.productivity_score) FROM performance_history ph WHERE ph.employee_name IN (SELECT DISTINCT assigned_to FROM tasks t WHERE t.project_id = p.id)),
                            (SELECT COUNT(DISTINCT assigned_to) FROM tasks t WHERE t.project_id = p.id),
                            (SELECT COUNT(*) FROM (SELECT DISTINCT assigned_to FROM tasks t WHERE t.project_id = p.id) WHERE assigned_to IN (SELECT assigned_to FROM OverloadedEmployees))
                        FROM projects p
                        WHERE p.id IN ({','.join(['?']*len(p_ids))})
                    """, p_ids)
                    
                    metrics_map = {row[0]: row for row in cursor.fetchall()}
                    
                    for pid, pname, leader, start, end, prio in projects:
                        m = metrics_map.get(pid, (pid, 0, 0, 3, 70, 1, 0))
                        # complexity and availability calculation logic
                        comp = min(5, max(1, int((m[2] / 10) + ((m[3] or 3) / 2))))
                        avail = max(0.1, 1.0 - (m[6] / max(1, m[5])))
                        project_risks.append((pid, pname, leader, comp, m[1], avail))
                
                con.close()
                self.root.after(0, lambda: self._render_analytics_ui(data, project_risks))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Analytics Error", f"Failed to fetch data: {e}"))

        # Show loading state
        loading_lbl = Label(self.content_area, text="📊 Analyzing Big Data... Please wait.", font=('Segoe UI', 14), bg=CONTENT_BG, fg=TEXT_WHITE)
        loading_lbl.pack(expand=True)
        
        threading.Thread(target=fetch_analytics_data, daemon=True).start()

    def _render_analytics_ui(self, data, project_risks):
        # Guard: if user switched away while the thread was running, abort silently
        try:
            if not hasattr(self, 'content_area') or not self.content_area.winfo_exists():
                return
            if self.current_page != 'analytics':
                return
        except Exception:
            return

        for widget in self.content_area.winfo_children():
            widget.destroy()

        from analytics_engine import generate_bar_chart_data, generate_line_chart_data, generate_pie_chart_data
        
        # Scrollable Wrapper
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True)

        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        def _configure_window(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _configure_window)

        def _on_mousewheel(event):
            try:
                if not canvas.winfo_exists():
                    return
                if event.delta > 0:
                    canvas.yview_scroll(-3, "units")
                elif event.delta < 0:
                    canvas.yview_scroll(3, "units")
            except:
                pass

        self._bind_canvas_scrolling(container, canvas)

        # ========== HEADER ==========
        h = Frame(scrollable_frame, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=(20, 10))
        Label(h, text="Analytics Dashboard", font=('Segoe UI', 28, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text=f"Last Updated: {data.get('generated_at', 'N/A')}", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=RIGHT, pady=(10, 0))

        # ========== KPI CARDS ROW ==========
        kpi_frame = Frame(scrollable_frame, bg=CONTENT_BG)
        kpi_frame.pack(fill=X, padx=30, pady=(10, 20))

        emp_summary = data.get('employee_summary', {})
        proj_stats = data.get('project_stats', {})
        task_stats = data.get('task_stats', {})

        kpi_data = [
            ("👤 Total Employees", str(emp_summary.get('total_employees', 0)), ACCENT_BLUE),
            ("📁 Active Projects", str(proj_stats.get('total_projects', 0)), ACCENT_GREEN),
            ("📊 Tasks Completed", f"{task_stats.get('completion_rate', 0)}%", ACCENT_ORANGE),
            ("⚡ Avg Productivity", f"{emp_summary.get('avg_productivity', 0)}", ACCENT_PURPLE)
        ]

        for label, value, color in kpi_data:
            card = Frame(kpi_frame, bg=CARD_BG, padx=24, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(card, text=label, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            Label(card, text=value, font=('Segoe UI', 28, 'bold'), bg=CARD_BG, fg=color).pack(anchor=W, pady=(8, 0))

        # ========== AI PROJECT RISK MATRIX ==========
        risk_section = Frame(scrollable_frame, bg=CONTENT_BG)
        risk_section.pack(fill=X, padx=30, pady=20)
        
        rs_h = Frame(risk_section, bg=CONTENT_BG)
        rs_h.pack(fill=X, pady=(0, 15))
        Label(rs_h, text="🔬 AI Project Risk Matrix", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(rs_h, text="Predictive situational analysis based on workload and resource drag.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=RIGHT, pady=(6, 0))
        
        risk_grid = Frame(risk_section, bg=CONTENT_BG)
        risk_grid.pack(fill=X)
        
        if not project_risks:
            Label(risk_grid, text="No active projects available for risk modeling.", font=('Segoe UI', 11), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
        else:
            r_col = 0
            r_row = 0
            for risk_item in project_risks:
                # Normalizing data as before
                try:
                    if isinstance(risk_item, (list, tuple)):
                        pid, pname, leader, complexity, workload, avail = risk_item[:6]
                    else: continue
                except: continue

                prob = 0.3 + (float(complexity) * 0.1) + (float(workload) * 0.05) - (float(avail) * 0.2)
                prob = min(0.95, max(0.05, prob))
                
                lvl, clr = ("LOW", ACCENT_GREEN) if prob < 0.4 else (("MEDIUM", ACCENT_ORANGE) if prob < 0.7 else ("CRITICAL", ACCENT_RED))
                
                # Risk Card
                rc = Frame(risk_grid, bg=CARD_BG, padx=20, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
                rc.grid(row=r_row, column=r_col, padx=(0 if r_col==0 else 15, 0), pady=(0, 15), sticky="nsew")
                risk_grid.columnconfigure(r_col, weight=1)

                rh = Frame(rc, bg=CARD_BG)
                rh.pack(fill=X)
                Label(rh, text=pname, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                Label(rh, text=lvl, font=('Segoe UI', 7, 'bold'), bg=clr, fg=WHITE, padx=8, pady=2).pack(side=RIGHT)
                
                Label(rc, text=f"Leader: {leader or 'N/A'}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 12))
                
                # Indicators
                ind_f = Frame(rc, bg=CARD_BG)
                ind_f.pack(fill=X)
                for il, iv in [("Complexity", f"{complexity}/5"), ("Workload", f"{workload} Tasks"), ("Resource", f"{int(avail*100)}% Avail")]:
                    ifb = Frame(ind_f, bg="#1e293b", padx=8, pady=4)
                    ifb.pack(side=LEFT, padx=(0, 8))
                    Label(ifb, text=iv, font=('Segoe UI', 8, 'bold'), bg="#1e293b", fg=TEXT_WHITE).pack()
                
                # Risk Bar
                Label(rc, text=f"Probability of Delay: {int(prob*100)}%", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(15, 6))
                rb_bg = Frame(rc, bg="#253244", height=6)
                rb_bg.pack(fill=X)
                Frame(rb_bg, bg=clr, height=6).place(x=0, y=0, relwidth=prob)

                r_col += 1
                if r_col > 1:
                    r_col = 0
                    r_row += 1


        # ========== EXECUTIVE INSIGHTS ==========
        trends = data.get('monthly_trends', {})
        monthly_scores = trends.get('avg_productivity', []) or []
        task_breakdown = task_stats.get('status_breakdown', {}) or {}
        perf_dist = emp_summary.get('performance_distribution', {}) or {}
        predictions = data.get('predictions', {}) or {}
        at_risk = predictions.get('at_risk_employees', []) or []

        first_score = monthly_scores[0] if monthly_scores else 0
        last_score = monthly_scores[-1] if monthly_scores else 0
        score_delta = round(last_score - first_score, 1) if len(monthly_scores) >= 2 else 0
        if len(monthly_scores) < 2:
            momentum_title = "Momentum Building"
            momentum_value = "Limited History"
            momentum_note = "The system needs more monthly performance data to confirm a trend."
            momentum_color = ACCENT_ORANGE
        elif score_delta >= 5:
            momentum_title = "Momentum Building"
            momentum_value = f"+{score_delta} pts"
            momentum_note = "Average productivity is climbing across the visible monthly trend."
            momentum_color = ACCENT_GREEN
        elif score_delta <= -5:
            momentum_title = "Momentum Slipping"
            momentum_value = f"{score_delta} pts"
            momentum_note = "Productivity has dropped across the latest visible trend window."
            momentum_color = ACCENT_RED
        else:
            momentum_title = "Momentum Stable"
            momentum_value = f"{score_delta:+.1f} pts"
            momentum_note = "Team output is holding steady without a major swing."
            momentum_color = ACCENT_BLUE

        overdue_projects = proj_stats.get('overdue_count', 0) or 0
        overdue_tasks = task_stats.get('overdue_tasks', 0) or 0
        delayed_tasks = task_breakdown.get('Delayed', 0) or 0
        total_risk_load = overdue_projects + overdue_tasks + delayed_tasks + len(at_risk)
        if total_risk_load >= 10:
            risk_title = "High Delivery Risk"
            risk_value = str(total_risk_load)
            risk_note = "Overdue projects, delayed tasks, and at-risk employees need immediate attention."
            risk_color = ACCENT_RED
        elif total_risk_load >= 4:
            risk_title = "Moderate Delivery Risk"
            risk_value = str(total_risk_load)
            risk_note = "There are a few visible pressure points across delivery and performance."
            risk_color = ACCENT_ORANGE
        else:
            risk_title = "Risk Under Control"
            risk_value = str(total_risk_load)
            risk_note = "The current project and workforce risk level looks manageable."
            risk_color = ACCENT_GREEN

        excellent = perf_dist.get('excellent', 0) or 0
        poor = perf_dist.get('poor', 0) or 0
        avg_productivity = emp_summary.get('avg_productivity', 0) or 0
        if avg_productivity >= 80 and poor == 0:
            health_title = "Workforce Health Strong"
            health_value = f"{avg_productivity:.1f}"
            health_note = "Most teams are operating at a strong productivity level with low drag."
            health_color = ACCENT_GREEN
        elif poor > excellent:
            health_title = "Workforce Health Uneven"
            health_value = f"{avg_productivity:.1f}"
            health_note = "Low-performing contributors outnumber top performers in the latest snapshot."
            health_color = ACCENT_RED
        else:
            health_title = "Workforce Health Mixed"
            health_value = f"{avg_productivity:.1f}"
            health_note = "The team has capacity, but consistency is still the main opportunity."
            health_color = ACCENT_BLUE

        if total_risk_load >= 10:
            action_value = "Escalate Delays"
            action_note = "Review delayed projects and overdue tasks first, then rebalance owners this week."
            action_color = ACCENT_RED
        elif poor > 0 or len(at_risk) > 0:
            action_value = "Coach At-Risk Team"
            action_note = "Start with the lowest performers and team leaders showing the sharpest decline."
            action_color = ACCENT_ORANGE
        elif score_delta >= 5:
            action_value = "Protect Current Pace"
            action_note = "Capture what is working now and keep the strongest delivery patterns in place."
            action_color = ACCENT_GREEN
        else:
            action_value = "Tighten Execution"
            action_note = "Push for higher completion velocity and fewer pending tasks over the next cycle."
            action_color = ACCENT_BLUE

        # ========== EXECUTIVE STRATEGIC INSIGHTS ==========
        insights_f = Frame(scrollable_frame, bg=CONTENT_BG)
        insights_f.pack(fill=X, padx=30, pady=(10, 20))
        
        ins_h = Frame(insights_f, bg=CONTENT_BG)
        ins_h.pack(fill=X, pady=(0, 15))
        Label(ins_h, text="📊 Strategic Insights", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        ins_grid = Frame(insights_f, bg=CONTENT_BG)
        ins_grid.pack(fill=X)

        def render_insight_glass(parent, title, value, note, color, icon):
            card = Frame(parent, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side=LEFT, expand=True, fill=BOTH, padx=(0 if len(parent.winfo_children())==0 else 15, 0))
            
            top = Frame(card, bg=CARD_BG)
            top.pack(fill=X)
            Label(top, text=icon, font=('Segoe UI', 14), bg=CARD_BG).pack(side=LEFT)
            Label(top, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=10)
            
            Label(card, text=value, font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=color).pack(anchor=W, pady=(12, 4))
            Label(card, text=note, font=('Segoe UI', 9), bg=CARD_BG, fg=TEXT_WHITE, wraplength=220, justify=LEFT).pack(anchor=W)

        render_insight_glass(ins_grid, momentum_title, momentum_value, momentum_note, momentum_color, "📈")
        render_insight_glass(ins_grid, risk_title, risk_value, risk_note, risk_color, "🛡️")
        render_insight_glass(ins_grid, health_title, health_value, health_note, health_color, "🩺")
        render_insight_glass(ins_grid, "AI Recommendation", action_value, action_note, action_color, "🎯")

        # ========== PERFORMANCE VISUALIZATION ==========
        # ========== PERFORMANCE VISUALIZATION ==========
        chart_section = Frame(scrollable_frame, bg=CONTENT_BG)
        chart_section.pack(fill=X, padx=30, pady=10)
        
        c_row1 = Frame(chart_section, bg=CONTENT_BG)
        c_row1.pack(fill=X, pady=(0, 20))
        
        # --- Trend Chart Card (Glow Line) ---
        trend_card = Frame(c_row1, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        trend_card.pack(side=LEFT, expand=True, fill=BOTH, padx=(0, 15))
        Label(trend_card, text="Delivery Velocity Trends", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        if trends.get('months'):
            tc = Canvas(trend_card, bg=CARD_BG, height=220, highlightthickness=0)
            tc.pack(fill=X)
            months, prods = trends['months'], trends['avg_productivity']
            if len(months) > 1:
                mx, mn = max(prods), min(prods)
                rng = mx - mn if mx != mn else 1
                w, h_c = 420, 160
                pts = []
                for i, v in enumerate(prods):
                    x = (i / (len(months)-1)) * w + 40
                    y = h_c - ((v - mn) / rng * h_c) + 30
                    pts.append((x, y))
                
                # Draw Shadow/Glow effect (multi-pass)
                for off in range(4, 0, -1):
                    tc.create_line([p for pt in pts for p in [pt[0], pt[1]+off]], fill="#1a2236", width=off+2, smooth=True)
                
                # Main Line
                tc.create_line([p for pt in pts for p in pt], fill=ACCENT_BLUE, width=3, smooth=True)
                
                # Data Points with Glow
                for x, y in pts:
                    tc.create_oval(x-6, y-6, x+6, y+6, fill="#2563eb", outline="")
                    tc.create_oval(x-3, y-3, x+3, y+3, fill=WHITE, outline="")
                
                # X-Axis Labels
                for i, m in enumerate(months):
                    tx = (i / (len(months)-1)) * w + 40
                    tc.create_text(tx, 205, text=m[-3:], fill=MUTED_TEXT, font=('Segoe UI', 8, 'bold'))

            Label(trend_card, text="Productivity throughput (last 6 months)", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(10, 0))
        else:
            Label(trend_card, text="Awaiting historical sync...", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=70)

        # --- Performance Mix (Rounded Bars) ---
        dist_card = Frame(c_row1, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        dist_card.pack(side=LEFT, expand=True, fill=BOTH)
        Label(dist_card, text="Resource Performance Mix", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        if perf_dist:
            dc = Canvas(dist_card, bg=CARD_BG, height=220, highlightthickness=0)
            dc.pack(fill=X)
            cats = [('EXC', 'excellent', ACCENT_GREEN), ('GOOD', 'good', ACCENT_BLUE), ('AVG', 'average', ACCENT_ORANGE), ('LOW', 'poor', ACCENT_RED)]
            vals = [perf_dist.get(k, 0) for _, k, _ in cats]
            m_v = max(vals) if max(vals) > 0 else 1
            for i, (l, k, cl) in enumerate(cats):
                x_b = 50 + i*95
                h_b = (perf_dist.get(k, 0) / m_v) * 150
                # Draw rounded bar
                dc.create_rectangle(x_b, 170-h_b, x_b+45, 170, fill=cl, outline="")
                dc.create_oval(x_b, 160-h_b, x_b+45, 180-h_b, fill=cl, outline="") # Top Rounding
                
                dc.create_text(x_b+22, 190, text=l, fill=MUTED_TEXT, font=('Segoe UI', 8, 'bold'))
                dc.create_text(x_b+22, 155-h_b, text=str(perf_dist.get(k, 0)), fill=TEXT_WHITE, font=('Segoe UI', 10, 'bold'))
        else:
            Label(dist_card, text="Analyzing performance bands...", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=70)

        c_row2 = Frame(chart_section, bg=CONTENT_BG)
        c_row2.pack(fill=X)
        
        # --- Portfolio Distribution (Donut Chart) ---
        p_card = Frame(c_row2, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        p_card.pack(side=LEFT, expand=True, fill=BOTH, padx=(0, 15))
        Label(p_card, text="Portfolio Distribution", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 10))
        
        p_dist = proj_stats.get('status_distribution', {})
        if p_dist:
            pc = Canvas(p_card, bg=CARD_BG, height=200, highlightthickness=0)
            pc.pack(fill=X)
            total = sum(p_dist.values())
            start = 0
            cols = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_ORANGE, ACCENT_RED, ACCENT_PURPLE]
            for i, (st, ct) in enumerate(p_dist.items()):
                ext = (ct/total)*360
                c = cols[i % len(cols)]
                pc.create_arc(30, 20, 160, 150, start=start, extent=ext, fill=c, outline=CARD_BG, width=3)
                # Legend chip
                ly = 30 + i*28
                pc.create_oval(200, ly, 212, ly+12, fill=c, outline="")
                pc.create_text(225, ly+6, text=f"{st}: {ct}", fill=MUTED_TEXT, font=('Segoe UI', 9, 'bold'), anchor=W)
                start += ext
            # Donut hole
            pc.create_oval(65, 55, 125, 115, fill=CARD_BG, outline=BORDER_COLOR, width=1)
            pc.create_text(95, 85, text=str(total), fill=TEXT_WHITE, font=('Segoe UI', 16, 'bold'))
            pc.create_text(95, 105, text="TOTAL", fill=MUTED_TEXT, font=('Segoe UI', 7, 'bold'))
        else:
            Label(p_card, text="No portfolio data...", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=60)

        # --- Task Velocity (Modern Bars) ---
        t_card = Frame(c_row2, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        t_card.pack(side=LEFT, expand=True, fill=BOTH)
        Label(t_card, text="Task Velocity Breakdown", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
        
        t_break = task_stats.get('status_breakdown', {})
        if t_break:
            tc2 = Canvas(t_card, bg=CARD_BG, height=200, highlightthickness=0)
            tc2.pack(fill=X)
            t_mx = max(t_break.values()) if max(t_break.values()) > 0 else 1
            for i, (st, ct) in enumerate(list(t_break.items())[:4]):
                ty = 20 + i*42
                tw = (ct/t_mx)*240
                # Label
                tc2.create_text(10, ty+10, text=st.upper(), fill=MUTED_TEXT, font=('Segoe UI', 8, 'bold'), anchor=W)
                # Track
                tc2.create_rectangle(100, ty+5, 340, ty+15, fill="#1e293b", outline="")
                # Fill
                tc2.create_rectangle(100, ty+5, 100+tw, ty+15, fill=ACCENT_BLUE, outline="")
                # Value chip
                tc2.create_text(350, ty+10, text=str(ct), fill=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), anchor=W)
        else:
            Label(t_card, text="No task logs...", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=60)

        # ========== TOP PERFORMERS & RISKS ==========
        list_section = Frame(scrollable_frame, bg=CONTENT_BG)
        list_section.pack(fill=X, padx=30, pady=(10, 20))
        
        # Top Performers Card
        tp_card = Frame(list_section, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tp_card.pack(side=LEFT, expand=True, fill=BOTH, padx=(0, 15))
        Label(tp_card, text="🏆 Top Performers", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W, pady=(0, 15))
        
        top_perf = emp_summary.get('top_performers', [])
        if top_perf:
            for i, emp in enumerate(top_perf[:5]):
                er = Frame(tp_card, bg=CARD_BG)
                er.pack(fill=X, pady=6)
                med = ["🥇", "🥈", "🥉", "•", "•"][i]
                Label(er, text=med, font=('Segoe UI', 12), bg=CARD_BG).pack(side=LEFT)
                Label(er, text=emp.get('employee_name', 'User'), font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=12)
                Label(er, text=f"{emp.get('productivity_score', 0):.1f}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(side=RIGHT)
                Frame(tp_card, bg=BORDER_COLOR, height=1).pack(fill=X, pady=(4, 0))
        else:
            Label(tp_card, text="Awaiting next performance cycle", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=40)

        # Performance Risk Card
        ar_card = Frame(list_section, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        ar_card.pack(side=LEFT, expand=True, fill=BOTH)
        Label(ar_card, text="⚠️ Performance Risk Alert", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(anchor=W, pady=(0, 15))
        
        if at_risk:
            for emp in at_risk[:5]:
                ar = Frame(ar_card, bg=CARD_BG)
                ar.pack(fill=X, pady=6)
                Label(ar, text="📉", font=('Segoe UI', 12), bg=CARD_BG).pack(side=LEFT)
                Label(ar, text=emp.get('name', 'User'), font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=12)
                Label(ar, text=f"↓ {emp.get('decline', 0):.1f}%", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(side=RIGHT)
                Frame(ar_card, bg=BORDER_COLOR, height=1).pack(fill=X, pady=(4, 0))
        else:
            Label(ar_card, text="All teams performing above baseline", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_GREEN).pack(pady=40)

        # ========== DEPARTMENT PERFORMANCE ==========
        dept_section = Frame(scrollable_frame, bg=CONTENT_BG)
        dept_section.pack(fill=X, padx=30, pady=(0, 20))
        
        ds_card = Frame(dept_section, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        ds_card.pack(fill=X)
        Label(ds_card, text="🏢 Department Velocity Mix", font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        d_stats = emp_summary.get('department_stats', [])
        if d_stats:
            d_grid = Frame(ds_card, bg=CARD_BG)
            d_grid.pack(fill=X)
            for i, d in enumerate(d_stats[:4]):
                db = Frame(d_grid, bg="#1e293b", padx=18, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
                db.pack(side=LEFT, expand=True, fill=BOTH, padx=(0 if i==0 else 12, 0))
                
                Label(db, text=d.get('department', 'N/A').upper(), font=('Segoe UI', 8, 'bold'), bg="#1e293b", fg=MUTED_TEXT).pack(anchor=W)
                Label(db, text=f"{d.get('count', 0)} Active", font=('Segoe UI', 10), bg="#1e293b", fg=TEXT_WHITE).pack(anchor=W, pady=4)
                
                sc = d.get('avg_score', 0)
                cl = ACCENT_GREEN if sc >= 75 else (ACCENT_ORANGE if sc >= 60 else ACCENT_RED)
                Label(db, text=f"AVG: {sc:.1f}", font=('Segoe UI', 12, 'bold'), bg="#1e293b", fg=cl).pack(anchor=W)
        else:
            Label(ds_card, text="No department metadata found", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=30)

        # ========== AI ENGINE GOVERNANCE ==========
        ai_sec = Frame(scrollable_frame, bg=CONTENT_BG)
        ai_sec.pack(fill=X, padx=30, pady=(10, 20))
        
        Label(ai_sec, text="⚙️ AI Engine Governance", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
        
        ai_grid = Frame(ai_sec, bg=CONTENT_BG)
        ai_grid.pack(fill=X)
        
        # Model Vital Signs Card
        ai = self.get_ai_engine()
        g_data = ai.get_global_analytics() if ai else {}
        m_info = g_data.get('model_info', {})
        
        mv_card = Frame(ai_grid, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        mv_card.pack(side=LEFT, expand=True, fill=BOTH, padx=(0, 15))
        Label(mv_card, text="Model Vital Signs", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(0, 15))
        
        m_vital = [
            ("ALGORITHM", m_info.get('type', 'Regressor')),
            ("FRAMEWORK", m_info.get('framework', 'Scikit-learn')),
            ("HEALTH", "ACTIVE" if m_info.get('status')=="Active" else "STANDBY"),
            ("SAMPLES", str(m_info.get('records_trained', 0)))
        ]
        for l, v in m_vital:
            mr = Frame(mv_card, bg=CARD_BG)
            mr.pack(fill=X, pady=4)
            Label(mr, text=l, font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(mr, text=v, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=RIGHT)

        # Control Panel Card
        ctrl_card = Frame(ai_grid, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        ctrl_card.pack(side=LEFT, expand=True, fill=BOTH)
        Label(ctrl_card, text="Maintenance Controls", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
        
        def trigger_retrain():
            if messagebox.askyesno("Retrain AI", "Initialize full model reconfiguration?"):
                res = ai.train()
                messagebox.showinfo("Success", f"Model stabilized!\nMAE: {res.get('mae')}\nR²: {res.get('r2_score')}")
                self.load_analytics()

        Button(ctrl_card, text="RECONFIGURE MODEL", command=trigger_retrain, font=('Segoe UI', 9, 'bold'),
               bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, padx=20, pady=10).pack(fill=X, pady=(0, 10))
        
        Button(ctrl_card, text="EXPORT ANALYTICS (JSON)", command=lambda: self.export_analytics(), 
               font=('Segoe UI', 9, 'bold'), bg="#1e293b", fg=ACCENT_GREEN, relief=FLAT, 
               highlightbackground=ACCENT_GREEN, highlightthickness=1, pady=10).pack(fill=X)

        # Footer
        Label(scrollable_frame, text="Powered by PMS Intelligence Engine v2.0 | High-Fidelity Analytic Core", 
              font=('Segoe UI', 8, 'bold'), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)

    def load_review_tasks(self):
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        px = self.get_responsive_padx()
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Task Review Pipeline", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Approve completed work or provide feedback for necessary revisions.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 20))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Find tasks from my team that are "Pending Approval" or "Completed" (if they need final review)
            cur.execute("""
                SELECT t.id, t.title, p.name, t.assigned_to, t.status 
                FROM tasks t 
                JOIN projects p ON t.project_id = p.id 
                WHERE (t.status = 'Pending Approval' OR t.status = 'Review' OR t.status = 'Submit for Review')
                AND p.team_leader LIKE ?
            """, (f"%{CURRENT_USER_NAME}%",))
            tasks = cur.fetchall()
            
            if not tasks:
                Label(scrollable_frame, text="All clear! No tasks waiting for your review.", 
                      font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=80)
            else:
                for tid, title, pname, user, status in tasks:
                    card = Frame(scrollable_frame, bg=CARD_BG, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    info = Frame(card, bg=CARD_BG)
                    info.pack(side=LEFT, fill=X, expand=True)
                    Label(info, text=title, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(info, text=f"📂 {pname} • Contributor: {user}", font=('Segoe UI Emoji', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
                    
                    actions = Frame(card, bg=CARD_BG)
                    actions.pack(side=RIGHT)
                    
                    def approve(t_id=tid):
                        c = sqlite3.connect(get_db_path())
                        cu = c.cursor()
                        cu.execute("UPDATE tasks SET status='Completed', completed_date=? WHERE id=?", (datetime.now().strftime("%Y-%m-%d"), t_id))
                        c.commit(); self.refresh_current_panel(); c.close()
                        self.load_review_tasks()
                        messagebox.showinfo("Approved", f"Task #{t_id} marked as Completed.")


                    
                    self._apply_hover_effect(card, ACCENT_BLUE)

                    def reject(t_id=tid):
                        rej_win = Toplevel(self.root)
                        rej_win.title("Rejection Feedback")
                        rej_win.config(bg=CONTENT_BG)
                        rej_win.geometry("500x350")
                        rej_win.transient(self.root)
                        rej_win.grab_set()

                        Label(rej_win, text="REQUIRED CHANGES", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
                        
                        f = Frame(rej_win, bg=CARD_BG, padx=20, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                        f.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
                        
                        rej_text = Text(f, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), relief=FLAT, insertbackground=WHITE)
                        rej_text.pack(fill=BOTH, expand=True)
                        rej_text.focus_set()

                        def submit_rejection():
                            comment = rej_text.get("1.0", "end-1c").strip()
                            if comment:
                                c = sqlite3.connect(get_db_path())
                                cu = c.cursor()
                                cu.execute("UPDATE tasks SET status='In Progress', review_comments=? WHERE id=?", (comment, t_id))
                                c.commit(); self.refresh_current_panel(); c.close()
                                rej_win.destroy()
                                self.load_review_tasks()
                                messagebox.showinfo("Rejected", "Feedback sent to contributor.")
                            else:
                                messagebox.showwarning("Incomplete", "Please provide change requests.")

                        Button(rej_win, text="SUBMIT FEEDBACK", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 9, 'bold'),
                               relief=FLAT, padx=20, pady=10, command=submit_rejection).pack(pady=(0, 20))

                    Button(actions, text="APPROVE", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                           relief=FLAT, padx=15, pady=8, cursor="hand2", command=approve).pack(side=LEFT, padx=5)
                    Button(actions, text="REJECT", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                           relief=FLAT, padx=15, pady=8, cursor="hand2", command=reject).pack(side=LEFT, padx=5)
            con.close()
        except Exception as e:
            debug_log(f"Load Review Tasks Error: {e}")

    def load_team_leaves(self):
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        px = self.get_responsive_padx()
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Team Absence Tracker", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Manage leave requests and plan around team availability.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 20))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas, bg=CONTENT_BG)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT id, member_name, start_date, end_date, reason, status, leave_type 
                FROM leave_requests 
                WHERE member_name IN (SELECT name FROM employee WHERE reporting_manager = ?)
                ORDER BY id DESC
            """, (CURRENT_USER_NAME,))
            leaves = cur.fetchall()
            
            if not leaves:
                Label(scroll_frame, text="No active leave requests from your team.", 
                      font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=80)
            else:
                for lid, name, start, end, reason, status, l_type in leaves:
                    card = Frame(scroll_frame, bg=CARD_BG, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=f"👤 {name} • {l_type}", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    s_color = ACCENT_ORANGE if status == 'Pending' else (ACCENT_GREEN if status == 'Approved' else ACCENT_RED)
                    badge = Frame(top, bg=s_color, padx=10, pady=2)
                    badge.pack(side=RIGHT)
                    badge._is_badge = True
                    Label(badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=s_color, fg=WHITE).pack()
                    
                    Label(card, text=f"📅 Duration: {start} to {end}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(5,0))
                    Label(card, text=f"📝 Reason: {reason}", font=('Segoe UI', 10), bg=CARD_BG, fg=WHITE, wraplength=800, justify=LEFT).pack(anchor=W, pady=(10,0))
                    
                    if status == 'Pending':
                        btns = Frame(card, bg=CARD_BG)
                        btns.pack(anchor=W, pady=(15, 0))
                        
                        def update(l_id=lid, s='Approved'):
                            c = sqlite3.connect(get_db_path())
                            cu = c.cursor()
                            cu.execute("UPDATE leave_requests SET status=? WHERE id=?", (s, l_id))
                            c.commit(); self.refresh_current_panel(); c.close()
                            self.load_team_leaves()

                        Button(btns, text="APPROVE", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                               relief=FLAT, padx=15, pady=8, cursor="hand2", command=lambda id=lid: update(id, 'Approved')).pack(side=LEFT, padx=5)
                        Button(btns, text="REJECT", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                               relief=FLAT, padx=15, pady=8, cursor="hand2", command=lambda id=lid: update(id, 'Rejected')).pack(side=LEFT, padx=5)
                    
                    self._apply_hover_effect(card, ACCENT_BLUE)
                    
                    if status == 'Pending':
                        btns = Frame(card, bg=CARD_BG)
                        btns.pack(anchor=W, pady=(15, 0))
                        
                        def update(l_id=lid, s='Approved'):
                            c = sqlite3.connect(get_db_path())
                            cu = c.cursor()
                            cu.execute("UPDATE leave_requests SET status=? WHERE id=?", (s, l_id))
                            c.commit(); self.refresh_current_panel(); c.close()
                            self.load_team_leaves()

                        Button(btns, text="APPROVE", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                               relief=FLAT, padx=15, pady=8, cursor="hand2", command=lambda id=lid: update(id, 'Approved')).pack(side=LEFT, padx=5)
                        Button(btns, text="REJECT", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 8, 'bold'),
                               relief=FLAT, padx=15, pady=8, cursor="hand2", command=lambda id=lid: update(id, 'Rejected')).pack(side=LEFT, padx=5)
            con.close()
        except Exception as e:
            debug_log(f"Load Team Leaves Error: {e}")

    def load_team_queries(self):
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        px = self.get_responsive_padx()
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="Support Intelligence", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Address team queries, blockers, and provide tactical support.", 
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=px, pady=(0, 20))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scroll_frame = Frame(canvas, bg=CONTENT_BG)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Show queries for team members
            cur.execute("""
                SELECT q.id, q.user_name, q.message, q.status, q.response, q.created_at 
                FROM queries q
                WHERE q.user_name IN (SELECT name FROM employee WHERE reporting_manager = ?)
                ORDER BY q.id DESC
            """, (CURRENT_USER_NAME,))
            queries = cur.fetchall()
            
            if not queries:
                Label(scroll_frame, text="No pending queries from your team.", 
                      font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=80)
            else:
                for qid, name, q_text, status, resp, ts in queries:
                    card = Frame(scroll_frame, bg=CARD_BG, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=f"💬 Query from {name}", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    s_color = ACCENT_GREEN if status == 'Open' else (ACCENT_ORANGE if status == 'Pending' else "#4b5563")
                    badge = Frame(top, bg=s_color, padx=10, pady=2)
                    badge.pack(side=RIGHT)
                    badge._is_badge = True
                    Label(badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=s_color, fg=WHITE).pack()
                    
                    Label(card, text=q_text, font=('Segoe UI', 10), bg=CARD_BG, fg=WHITE, wraplength=800, justify=LEFT).pack(anchor=W, pady=(10,0))
                    Label(card, text=ts, font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                    
                    if resp:
                        r_box = Frame(card, bg="#1a2035", padx=15, pady=10)
                        r_box.pack(fill=X, pady=(15, 0))
                        Label(r_box, text=f"RESPONSE: {resp}", font=('Segoe UI', 9, 'italic'), bg="#1a2035", fg=ACCENT_BLUE, wraplength=750, justify=LEFT).pack(anchor=W)
                    
                    if status in ('Pending', 'Open'):
                        btn_f = Frame(card, bg=CARD_BG)
                        btn_f.pack(anchor=W, pady=(15, 0))
                        
                        def respond_query(q_id=qid, q_orig=q_text, sender=name):
                            resp_win = Toplevel(self.root)
                            resp_win.title(f"Address Query - {sender}")
                            resp_win.config(bg=CONTENT_BG)
                            
                            sw = self.root.winfo_screenwidth()
                            sh = self.root.winfo_screenheight()
                            modal_w = 600
                            modal_h = 580
                            x = int((sw/2)-(modal_w/2))
                            y = int((sh/2)-(modal_h/2))
                            resp_win.geometry(f"{modal_w}x{modal_h}+{x}+{y}")
                            resp_win.transient(self.root)
                            resp_win.grab_set()

                            shell = Frame(resp_win, bg=CONTENT_BG, padx=30, pady=30)
                            shell.pack(fill=BOTH, expand=True)

                            # Header
                            hero = Frame(shell, bg=CONTENT_BG)
                            hero.pack(fill=X, pady=(0, 20))
                            Label(hero, text="Resolve Blocker", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
                            Label(hero, text=f"Providing tactical response to {sender}'s query.", 
                                  font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

                            # Reference Query (Read-only Card)
                            ref_card = Frame(shell, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
                            ref_card.pack(fill=X, pady=(0, 20))
                            Label(ref_card, text="ORIGINAL QUERY", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                            Label(ref_card, text=q_orig, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, wraplength=520, justify=LEFT).pack(anchor=W, pady=(8, 0))

                            # Response Area
                            Label(shell, text="YOUR RESPONSE", font=('Segoe UI', 8, 'bold'), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(0, 5))
                            
                            def submit_response():
                                msg = resp_text.get("1.0", "end-1c").strip()
                                if msg:
                                    c = sqlite3.connect(get_db_path())
                                    cu = c.cursor()
                                    cu.execute("UPDATE queries SET response=?, status='Closed' WHERE id=?", (msg, q_id))
                                    c.commit(); self.refresh_current_panel(); c.close()
                                    resp_win.destroy()
                                    self.load_team_queries()
                                    messagebox.showinfo("Resolved", "Response sent to team member.")
                                else:
                                    messagebox.showwarning("Incomplete", "Please provide a response.")

                            btn = Button(shell, text="SEND RESPONSE", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 10, 'bold'),
                                   relief=FLAT, padx=30, pady=15, command=submit_response)
                            btn.pack(side=BOTTOM, fill=X, pady=(20, 0))
                            self._apply_hover_effect(btn, ACCENT_GREEN, "#047857")

                            resp_f = Frame(shell, bg="#1a2035", highlightbackground=BORDER_COLOR, highlightthickness=1)
                            resp_f.pack(side=TOP, fill=BOTH, expand=True)
                            
                            st = ttk.Scrollbar(resp_f)
                            st.pack(side=RIGHT, fill=Y)
                            
                            resp_text = Text(resp_f, height=10, bg="#1a2035", fg=WHITE, font=('Segoe UI', 11), relief=FLAT, 
                                             insertbackground=WHITE, yscrollcommand=st.set, padx=15, pady=15)
                            resp_text.pack(side=LEFT, fill=BOTH, expand=True)
                            st.config(command=resp_text.yview)
                            resp_text.focus_set()

                        res_btn = Button(btn_f, text="ADDRESS QUERY", font=('Segoe UI', 8, 'bold'), bg="#2a3352", fg=ACCENT_BLUE,
                               relief=FLAT, padx=15, pady=8, command=respond_query)
                        res_btn.pack()
                        self._apply_hover_effect(res_btn, ACCENT_BLUE, "#1c223d")
                    
                    self._apply_hover_effect(card, ACCENT_BLUE)
            con.close()
        except Exception as e:
            Label(self.content_area, text=f"Error: {e}", bg=CONTENT_BG, fg="#e03030").pack()

    def load_my_leaves(self):
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, padx=30, pady=20)
        
        header = Frame(container, bg=CONTENT_BG)
        header.pack(fill=X, pady=(0, 20))
        Label(header, text="My Leave Requests", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        def apply_leave():
            d = Toplevel(self.root)
            d.title("Apply for Leave")
            d.geometry("450x550")
            d.minsize(400, 467)  # FIX 7: prevent content clipping when UI changes
            d.resizable(True, True)  # FIX 7: allow resize so no overflow
            d.config(bg=BG_CARD)
            d.resizable(False, False)
            d.transient(self.root)
            d.grab_set()

            # Center
            mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 225
            my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 275
            d.geometry(f"450x550+{mx}+{my}")

            header = Frame(d, bg=HEADER_BG, pady=20)
            header.pack(fill=X)
            Label(header, text="LEAVE APPLICATION", font=('Rajdhani', 16, 'bold'), bg=HEADER_BG, fg=WHITE).pack()

            body = Frame(d, bg=BG_CARD, padx=40, pady=30)
            body.pack(fill=BOTH, expand=True)

            def create_field(parent, label, placeholder=""):
                f = Frame(parent, bg=BG_CARD)
                f.pack(fill=X, pady=(0, 15))
                Label(f, text=label.upper(), font=('Segoe UI', 8, 'bold'), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 5))
                e = Entry(f, bg="#1a2035", fg=WHITE, insertbackground=WHITE, font=('Segoe UI', 10), 
                          relief=FLAT, highlightbackground="#2e3760", highlightthickness=1)
                e.pack(fill=X, pady=2, ipady=8)
                if placeholder:
                    e.insert(0, placeholder)
                return e

            e_start = create_field(body, "Start Date", datetime.now().strftime("%Y-%m-%d"))
            e_end = create_field(body, "End Date", (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"))
            e_reason = create_field(body, "Reason for Leave", "Vacation / Medical / etc.")
            
            def submit():
                start_val = e_start.get().strip()
                end_val = e_end.get().strip()
                reason_val = e_reason.get().strip()
                
                if start_val and end_val and reason_val:
                    try:
                        c = sqlite3.connect(get_db_path())
                        cu = c.cursor()
                        # Corrected columns to match schema: member_name, leave_type
                        cu.execute("INSERT INTO leave_requests (member_name, leave_type, start_date, end_date, reason, status) VALUES (?, ?, ?, ?, ?, ?)",
                                  (CURRENT_USER_NAME, "General", start_val, end_val, reason_val, "Pending"))
                        c.commit(); self.refresh_current_panel(); c.close()
                        d.destroy()
                        messagebox.showinfo("Success", "Leave request submitted.")
                        self.load_my_leaves()
                    except Exception as e:
                        messagebox.showerror("Error", f"Failed to submit: {e}")
                else:
                    messagebox.showwarning("Incomplete", "Please fill all fields.")
            
            btn_sub = Button(body, text="SUBMIT APPLICATION", bg=ACCENT_BLUE, fg=WHITE, 
                           font=('Segoe UI', 10, 'bold'), relief=FLAT, pady=12,
                           command=submit)
            btn_sub.pack(fill=X, pady=(10, 0))
            btn_sub.bind("<Enter>", lambda e: btn_sub.config(bg="#4ba8f0"))
            btn_sub.bind("<Leave>", lambda e: btn_sub.config(bg=ACCENT_BLUE))

        Button(header, text="+ Apply Leave", bg=ACCENT_BLUE, fg=WHITE, command=apply_leave).pack(side=RIGHT)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT start_date, end_date, reason, status FROM leave_requests WHERE member_name=? ORDER BY id DESC", (CURRENT_USER_NAME,))
            rows = cur.fetchall()
            
            if not rows:
                Label(container, text="No leave history found.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for start, end, reason, status in rows:
                    card = Frame(container, bg=CARD_BG, padx=22, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=f"📅 {start} — {end}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    color = ACCENT_ORANGE if status == 'Pending' else (ACCENT_GREEN if status == 'Approved' else ACCENT_RED)
                    badge = Frame(top, bg=color, padx=10, pady=2)
                    badge.pack(side=RIGHT)
                    badge._is_badge = True
                    Label(badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=color, fg=WHITE).pack()
                    
                    Label(card, text=reason, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=700, justify=LEFT).pack(anchor=W, pady=(8, 0))
                    self._apply_hover_effect(card, ACCENT_BLUE)
            con.close()
        except Exception as e:
            debug_log(f"Load My Leaves Error: {e}")

    # ==================== EMPLOYEE SUB-PAGES ====================
    def load_emp_dashboard(self):
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        px = self.get_responsive_padx()
        
        # Premium Header
        h_wrap = Frame(self.content_area, bg=CONTENT_BG)
        h_wrap.pack(fill=X, padx=px, pady=(30, 20))
        
        title_box = Frame(h_wrap, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        from datetime import datetime
        hour = datetime.now().hour
        if hour < 12: greeting = "Good Morning"
        elif hour < 17: greeting = "Good Afternoon"
        else: greeting = "Good Evening"
        
        Label(title_box, text=f"{greeting}, {CURRENT_USER_NAME}", font=('Segoe UI', 26, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Your personal productivity cockpit and real-time performance overview.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))



        # Main scrollable area
        canvas = Canvas(self.content_area, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_area, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        
        def update_width(event): canvas.itemconfigure(canvas_window, width=event.width)
        canvas.bind("<Configure>", update_width)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True, padx=px)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)

        # Summary Metrics
        metrics_row = Frame(scrollable_frame, bg=CONTENT_BG)
        metrics_row.pack(fill=X, pady=(0, 30))

        def create_saas_card(parent, title, val, sub, color, icon, progress=None):
            card = Frame(parent, bg=CARD_BG, padx=22, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side=LEFT, expand=True, fill=X, padx=(0, 20))
            self._apply_hover_effect(card, color)
            
            top = Frame(card, bg=CARD_BG)
            top.pack(fill=X)
            Label(top, text=icon, font=('Segoe UI', 14), bg=CARD_BG).pack(side=LEFT)
            Label(top, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=10)
            
            Label(card, text=str(val), font=('Segoe UI', 32, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(16, 4))
            
            if progress is not None:
                p_wrap = Frame(card, bg="#1e293b", height=4)
                p_wrap.pack(fill=X, pady=(5, 10))
                p_fill = Frame(p_wrap, bg=color, height=4)
                p_fill.place(x=0, y=0, relwidth=progress/100)
                
            Label(card, text=sub, font=('Segoe UI', 9), bg=CARD_BG, fg=color).pack(anchor=W)
            
            # Interactive hover
            card.bind("<Enter>", lambda e: card.config(highlightbackground=color, bg="#252d4d"))
            card.bind("<Leave>", lambda e: card.config(highlightbackground=BORDER_COLOR, bg=CARD_BG))

        # Fetch Data
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) FROM tasks WHERE assigned_to=?", (CURRENT_USER_NAME,))
            t_res = cur.fetchone()
            total, done = t_res[0] or 0, t_res[1] or 0
            pending = total - done
            perf = int((done/total)*100) if total > 0 else 100
            
            create_saas_card(metrics_row, "Pending Tasks", pending, "Active assignments", ACCENT_BLUE, "⚡")
            create_saas_card(metrics_row, "Success Rate", f"{perf}%", "Completion throughput", ACCENT_GREEN, "🏆", progress=perf)
            create_saas_card(metrics_row, "Focus Level", "OPTIMAL", "Workload balance", ACCENT_ORANGE, "📊")
            
            # Dashboard Grid
            grid = Frame(scrollable_frame, bg=CONTENT_BG)
            grid.pack(fill=BOTH, expand=True)
            grid.columnconfigure(0, weight=3)
            grid.columnconfigure(1, weight=2)
            
            # Task Pulse Card
            t_card = Frame(grid, bg=CARD_BG, padx=30, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
            t_card.grid(row=0, column=0, columnspan=2, sticky="nsew")
            
            Label(t_card, text="TASK PULSE", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(t_card, text="Immediate priorities requiring your attention.", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 25))
            
            cur.execute("""
                SELECT title, priority, due_date, status 
                FROM tasks 
                WHERE assigned_to=? AND status!='Completed' 
                ORDER BY CASE priority WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END
                LIMIT 4
            """, (CURRENT_USER_NAME,))
            rows = cur.fetchall()
            
            if not rows:
                Label(t_card, text="All caught up! No active tasks found.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=50)
            else:
                for t_name, prio, dline, stat in rows:
                    p_clr = ACCENT_RED if prio == 'High' else (ACCENT_BLUE if prio == 'Medium' else ACCENT_GREEN)
                    row_f = Frame(t_card, bg=CARD_BG, pady=12)
                    row_f.pack(fill=X)
                    
                    indicator = Frame(row_f, bg=p_clr, width=4)
                    indicator.pack(side=LEFT, fill=Y, padx=(0, 15))
                    
                    info = Frame(row_f, bg=CARD_BG)
                    info.pack(side=LEFT, fill=BOTH, expand=True)
                    Label(info, text=t_name, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(info, text=f"{stat} • Due {dline or 'TBD'}", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                    
                    btn = Button(row_f, text="UPDATE", bg="#2e3760", fg=TEXT_WHITE, font=('Segoe UI', 7, 'bold'), relief=FLAT, padx=12, pady=6)
                    btn.pack(side=RIGHT)
                    

                
            # Recent Activity Card
            a_card = Frame(grid, bg=CARD_BG, padx=30, pady=30, highlightbackground=BORDER_COLOR, highlightthickness=1)
            a_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(25, 0))
            
            Label(a_card, text="RECENT ACTIVITY", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(a_card, text="Your latest actions and updates.", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 25))
            
            # Fetch recent timesheet entries
            cur.execute("""
                SELECT date, hours, description 
                FROM timesheets 
                WHERE employee_name=? 
                ORDER BY date DESC 
                LIMIT 3
            """, (CURRENT_USER_NAME,))
            activities = cur.fetchall()
            
            if not activities:
                Label(a_card, text="No recent activity found.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=30)
            else:
                for date, hours, desc in activities:
                    act_f = Frame(a_card, bg=CARD_BG, pady=10)
                    act_f.pack(fill=X)
                    
                    Label(act_f, text="📝", font=('Segoe UI', 12), bg=CARD_BG, fg=ACCENT_BLUE).pack(side=LEFT, padx=(0, 15))
                    
                    info = Frame(act_f, bg=CARD_BG)
                    info.pack(side=LEFT, fill=BOTH, expand=True)
                    Label(info, text=f"Logged {hours} hours", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                    Label(info, text=desc or 'No notes provided.', font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                    
                    Label(act_f, text=date, font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)
                    
            con.close()
        except Exception as e:
            debug_log(f"Emp Dashboard Error: {e}")






    def load_emp_my_tasks(self):
        debug_log("DEBUG: Loading employee my tasks...")
        parent = self.content_area 

        # Header
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=(20, 25), padx=30)
        
        title_box = Frame(h, bg=CONTENT_BG)
        title_box.pack(side=LEFT)
        Label(title_box, text="MY TASK COCKPIT", font=('Segoe UI', 22, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Manage your assignments and update delivery progress.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W)
        
        # Filters Card
        f_card = Frame(parent, bg=CARD_BG, padx=25, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        f_card.pack(fill=X, padx=30, pady=(0, 25))
        
        # Grid layout for filters
        self.emp_task_search = StringVar()
        
        status_f = Frame(f_card, bg=CARD_BG)
        status_f.pack(side=LEFT, padx=(0, 30))
        Label(status_f, text="STATUS", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(0, 5))
        self.emp_task_status = StringVar(value="All Active")
        cb_s = ttk.Combobox(status_f, textvariable=self.emp_task_status, 
                            values=["All", "All Active", "Pending", "In Progress", "Pending Approval"], 
                            state="readonly", width=18, style='Employee.TCombobox')
        cb_s.pack(ipady=2)
        cb_s.bind("<<ComboboxSelected>>", lambda e: self.refresh_emp_tasks_tab())
        
        prio_f = Frame(f_card, bg=CARD_BG)
        prio_f.pack(side=LEFT)
        Label(prio_f, text="PRIORITY", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(0, 5))
        self.emp_task_prio = StringVar(value="All")
        cb_p = ttk.Combobox(prio_f, textvariable=self.emp_task_prio, values=["All", "High", "Medium", "Low"], 
                            state="readonly", width=12, style='Employee.TCombobox')
        cb_p.pack(ipady=2)
        cb_p.bind("<<ComboboxSelected>>", lambda e: self.refresh_emp_tasks_tab())

        # Scrollable Task List
        list_wrap = Frame(parent, bg=CONTENT_BG)
        list_wrap.pack(fill=BOTH, expand=True, padx=30)
        
        canvas = Canvas(list_wrap, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_wrap, orient=VERTICAL, command=canvas.yview)
        self.emp_tasks_container = Frame(canvas, bg=CONTENT_BG)
        
        self.emp_tasks_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.emp_tasks_container, anchor="nw")
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(parent, canvas)
        
        self.refresh_emp_tasks_tab()


    def load_emp_team(self):
        debug_log("DEBUG: Loading senior employee team hub...")
        parent = self.content_area
        
        # Header
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=(20, 10), padx=30)
        Label(h, text="PROJECT COLLEAGUES", font=('Segoe UI', 22, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Collaborate and track shared project progress.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(10, 0))

        # Scrollable container
        canvas_f = Frame(parent, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=30, pady=20)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        self.team_prog_container = Frame(canvas, bg=CONTENT_BG)
        
        self.team_prog_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.team_prog_container, anchor="nw")
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(parent, canvas)
        
        self._refresh_emp_team_data()

    def _refresh_emp_team_data(self):
        if not hasattr(self, 'team_prog_container'): return
        for widget in self.team_prog_container.winfo_children(): widget.destroy()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # 1. GET USER REPORTING MANAGER
            cur.execute("SELECT reporting_manager FROM employee WHERE name = ?", (CURRENT_USER_NAME,))
            mgr_row = cur.fetchone()
            user_mgr = mgr_row[0] if mgr_row else None

            # 2. FETCH COLLEAGUES IN SAME TEAM (Same Manager)
            # Exclude current user and anyone with role 'Team Leader' or 'Project Manager' or 'admin'
            if user_mgr:
                cur.execute("""
                    SELECT name FROM employee 
                    WHERE reporting_manager = ?
                    AND name != ?
                    AND lower(role) NOT IN ('team leader', 'project manager', 'admin')
                """, (user_mgr, CURRENT_USER_NAME))
            else:
                cur.execute("SELECT name FROM employee WHERE 1=0") # Empty list if no manager
                
            colleagues = [r[0] for r in cur.fetchall()]

            # 3. FETCH TASKS FOR THESE COLLEAGUES
            team_data = []
            if colleagues:
                placeholders = ','.join(['?'] * len(colleagues))
                cur.execute(f"""
                    SELECT t.assigned_to, t.title, t.status, t.due_date, p.name
                    FROM tasks t 
                    LEFT JOIN projects p ON t.project_id = p.id
                    WHERE t.assigned_to IN ({placeholders}) AND t.status != 'Cancelled'
                    ORDER BY t.assigned_to, t.due_date ASC
                """, colleagues)
                team_data = cur.fetchall()
            
            # Initialize members with ALL colleagues (even those with no tasks)
            members = {name: {'tasks': [], 'comp': 0, 'total': 0} for name in colleagues}
            
            for m_name, t_title, status, dline, p_name in team_data:
                members[m_name]['tasks'].append({'title': t_title, 'status': status, 'deadline': dline, 'project': p_name})
                members[m_name]['total'] += 1
                if status == 'Completed': members[m_name]['comp'] += 1
                
            if not members:
                Label(self.team_prog_container, text="No project colleagues found currently.", 
                      font=('Segoe UI', 11), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
            else:
                for m_name, data in members.items():
                    card = Frame(self.team_prog_container, bg=CARD_BG, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=(0, 20))
                    
                    # Header
                    head = Frame(card, bg=CARD_BG)
                    head.pack(fill=X)
                    
                    Label(head, text=m_name, font=('Segoe UI', 13, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    Label(head, text=f"({data['comp']}/{data['total']} COMPLETED)", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(side=LEFT, padx=15)
                    
                    perc = int((data['comp'] / data['total']) * 100) if data['total'] > 0 else 0
                    p_wrap = Frame(card, bg="#333333", height=6)
                    p_wrap.pack(fill=X, pady=15)
                    p_fill = Frame(p_wrap, bg=ACCENT_GREEN if perc == 100 else ACCENT_BLUE, height=6)
                    p_fill.place(x=0, y=0, relwidth=perc/100)
                    
                    # Recent activity
                    Label(card, text="RECENT ACTIVITY:", font=('Segoe UI', 7, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                    for t in data['tasks'][:2]:
                        r = Frame(card, bg=CARD_BG, pady=4)
                        r.pack(fill=X)
                        Label(r, text=f"• {t['title']}", font=('Segoe UI', 9), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                        Label(r, text=f"({t['status']})", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=10)

                    # Interactive hover
                    def _e(e, c=card): c.config(highlightbackground=ACCENT_BLUE, bg="#252d4d")
                    def _l(e, c=card): c.config(highlightbackground=BORDER_COLOR, bg=CARD_BG)
                    card.bind("<Enter>", _e)
                    card.bind("<Leave>", _l)
            
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Team data refresh failed: {e}")


    def load_emp_analysis(self):
        debug_log("DEBUG: Loading employee analysis...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        px = self.get_responsive_padx()
        
        # Premium Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        Label(h, text="PERSONAL INTELLIGENCE", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Advanced behavioral metrics and real-time performance insights.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Main Scrollable Area
        canvas_f = Frame(self.content_area, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=px)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        scroll_frame = Frame(canvas, bg=CONTENT_BG)
        
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        
        def _resize(e): canvas.itemconfig(canvas_win, width=e.width)
        canvas.bind("<Configure>", _resize)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)

        self.emp_analysis_container = scroll_frame
        parent = scroll_frame

        # ── 1. TOP KPI CARDS ──
        kpi_frame = Frame(parent, bg=CONTENT_BG)
        kpi_frame.pack(fill=X, pady=(10, 20))
        
        self.emp_ana_kpis = {}
        for title, accent, icon, key in [
            ("Completion Rate", "#10b981", "🎯", "rate"), 
            ("Total Hours Logged", "#8b5cf6", "⏱️", "hours"), 
            ("High Prio Focus", "#ef4444", "🔥", "high")
        ]:
            card = Frame(kpi_frame, bg=CARD_BG, padx=30, pady=25, highlightbackground="#2e3760", highlightthickness=1)
            card.pack(side=LEFT, fill=X, expand=True, padx=(0, 20) if key != "high" else 0)
            self._apply_hover_effect(card, accent)
            
            Label(card, text=icon, font=('Segoe UI', 20), bg=CARD_BG, fg=accent).pack(side=LEFT, padx=(0, 15))
            v_f = Frame(card, bg=CARD_BG)
            v_f.pack(side=LEFT)
            Label(v_f, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            lbl = Label(v_f, text="0", font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=TEXT_WHITE)
            lbl.pack(anchor=W)
            
            # Map the card background to the label so hover effect cascades
            lbl.bind("<Enter>", lambda e, c=card: c.event_generate("<Enter>"))
            v_f.bind("<Enter>", lambda e, c=card: c.event_generate("<Enter>"))
            
            self.emp_ana_kpis[key] = lbl

        # ── 2. MID SECTION (PRIORITY & STAGES) ──
        container = Frame(parent, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        # Left: Priority Mix
        self.ana_prio_f = Frame(container, bg=CARD_BG, padx=35, pady=30, highlightbackground="#2e3760", highlightthickness=1)
        self.ana_prio_f.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        
        prio_header = Frame(self.ana_prio_f, bg=CARD_BG)
        prio_header.pack(fill=X, pady=(0, 25))
        Label(prio_header, text="🔥", font=('Segoe UI', 14), bg=CARD_BG, fg="#ef4444").pack(side=LEFT, padx=(0,8))
        Label(prio_header, text="PRIORITY MIX", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        self.ana_prio_container = Frame(self.ana_prio_f, bg=CARD_BG)
        self.ana_prio_container.pack(fill=BOTH, expand=True)

        # Right: Delivery Stages
        self.ana_stat_f = Frame(container, bg=CARD_BG, padx=35, pady=30, highlightbackground="#2e3760", highlightthickness=1)
        self.ana_stat_f.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        
        stat_header = Frame(self.ana_stat_f, bg=CARD_BG)
        stat_header.pack(fill=X, pady=(0, 25))
        Label(stat_header, text="📈", font=('Segoe UI', 14), bg=CARD_BG, fg="#4d7cfe").pack(side=LEFT, padx=(0,8))
        Label(stat_header, text="DELIVERY STAGES", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        self.ana_stat_container = Frame(self.ana_stat_f, bg=CARD_BG)
        self.ana_stat_container.pack(fill=BOTH, expand=True)



        self.refresh_emp_analysis()

    def refresh_emp_analysis(self):
        if not hasattr(self, 'emp_analysis_container'): return
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # Fetch core metrics
            cur.execute("SELECT COUNT(*), SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) FROM tasks WHERE assigned_to=?", (CURRENT_USER_NAME,))
            total, done = cur.fetchone()
            total, done = total or 0, done or 0
            rate = int((done/total)*100) if total > 0 else 0
            
            cur.execute("SELECT SUM(hours) FROM timesheets WHERE employee_name=?", (CURRENT_USER_NAME,))
            hours = cur.fetchone()[0] or 0.0

            # Fetch priority and status data
            cur.execute("SELECT priority, COUNT(*) FROM tasks WHERE assigned_to=? GROUP BY priority", (CURRENT_USER_NAME,))
            prio_data = {row[0]: row[1] for row in cur.fetchall()}
            high = prio_data.get("High", 0)

            cur.execute("SELECT status, COUNT(*) FROM tasks WHERE assigned_to=? GROUP BY status", (CURRENT_USER_NAME,))
            status_data = {row[0]: row[1] for row in cur.fetchall()}

            # 4. Update KPI Labels
            if hasattr(self, 'emp_ana_kpis'):
                self.emp_ana_kpis['rate'].config(text=f"{rate}%")
                self.emp_ana_kpis['hours'].config(text=f"{hours} hrs")
                self.emp_ana_kpis['high'].config(text=f"{high} tasks")

            # 5. Update Priority Bars
            for widget in self.ana_prio_container.winfo_children(): widget.destroy()
            if total > 0:
                for p_name, count in [("High Priority", high), ("Medium Priority", prio_data.get("Medium",0)), ("Low Priority", prio_data.get("Low",0))]:
                    perc = (count / total) * 100
                    f = Frame(self.ana_prio_container, bg=CARD_BG, pady=10)
                    f.pack(fill=X)
                    
                    meta_f = Frame(f, bg=CARD_BG)
                    meta_f.pack(fill=X, pady=(0, 8))
                    
                    color = "#ef4444" if "High" in p_name else ("#f59e0b" if "Medium" in p_name else "#10b981")
                    Label(meta_f, text=p_name, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold')).pack(side=LEFT)
                    Label(meta_f, text=f"{count} tasks  •  {int(perc)}%", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=RIGHT)
                    
                    track = Canvas(f, bg="#1a2035", height=8, highlightthickness=0)
                    track.pack(fill=X)
                    
                    def _draw(e, c=track, p=perc, col=color):
                        c.delete("all")
                        w = max(10, (e.width * p) / 100)
                        c.create_rectangle(0, 0, w, 8, fill=col, outline="")
                    track.bind("<Configure>", _draw)
            else:
                Label(self.ana_prio_container, text="No tasks to analyze.", bg=CARD_BG, fg=MUTED_TEXT, pady=20).pack()

            # 6. Update Delivery Stages
            for widget in self.ana_stat_container.winfo_children(): widget.destroy()
            if status_data:
                for status, count in status_data.items():
                    r = Frame(self.ana_stat_container, bg="#1e2544", padx=20, pady=15)
                    r.pack(fill=X, pady=6)
                    acc = "#10b981" if status=="Completed" else ("#f59e0b" if status=="In Progress" else "#4d7cfe")
                    
                    dot_c = Canvas(r, width=12, height=12, bg="#1e2544", highlightthickness=0)
                    dot_c.pack(side=LEFT, padx=(0, 15))
                    dot_c.create_oval(2, 2, 10, 10, fill=acc, outline="")
                    
                    Label(r, text=status, bg="#1e2544", fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(side=LEFT)
                    Label(r, text=f"{count} tasks", bg="#1e2544", fg="#9aa3c2", font=('Segoe UI', 10)).pack(side=RIGHT)
            else:
                Label(self.ana_stat_container, text="No stages to track.", bg=CARD_BG, fg=MUTED_TEXT, pady=20).pack()

            # 7. AI Insight Generation
            med_p = prio_data.get("Medium", 0)
            low_p = prio_data.get("Low", 0)
            pend_count = status_data.get('Pending', 0)
            prog_count = status_data.get('In Progress', 0)

            if high > med_p + low_p and high > 0:
                insight_text = "Your backlog is heavily saturated with High Priority tasks. The AI suggests proactively negotiating deadlines or requesting support to distribute operational load and prevent burnout."
            elif rate > 75:
                insight_text = "Exceptional tracking velocity. You are currently closing tasks faster than the median operational standard. AI Confidence in your delivery timeline remains extremely high."
            elif hours > (total * 8) and total > 0:
                insight_text = "You are logging statistically high hours relative to your current task throughput. Consider re-evaluating task scopes with your manager to ensure accurate estimations."
            elif pend_count > prog_count and pend_count > 3:
                insight_text = "A backlog bottleneck is detected in your Pending queue. Focus your next operational cycle on transitioning these items to 'In Progress' to maintain flow."
            elif total == 0:
                insight_text = "No operational data available for analysis. Awaiting task assignment."
            else:
                insight_text = "Operations are nominal. Task intake and closure rates are highly balanced. Maintain your current operational paradigm and focus on steady execution."



            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Analysis Refresh Error: {e}")



    def load_emp_queries(self):
        debug_log("DEBUG: Loading employee queries cockpit...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        Label(h, text="SUPPORT & QUERIES", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Track your blockers and get tactical support.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Search & Action Strip
        strip = Frame(self.content_area, bg=CONTENT_BG)
        strip.pack(fill=X, padx=px, pady=(0, 20))
        
        self.query_search_var = StringVar()
        ent_f = Frame(strip, bg=CARD_BG, padx=15, pady=8, highlightbackground=BORDER_COLOR, highlightthickness=1)
        ent_f.pack(side=LEFT)
        Label(ent_f, text="🔍", bg=CARD_BG, font=('Segoe UI', 10)).pack(side=LEFT)
        Entry(ent_f, textvariable=self.query_search_var, bg=CARD_BG, fg=WHITE, borderwidth=0, font=('Segoe UI', 10), width=35, insertbackground=WHITE).pack(side=LEFT, padx=10)
        self.query_search_var.trace_add("write", lambda *a: self.refresh_emp_queries())
        
        Button(strip, text="+ RAISE NEW QUERY", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=20, pady=10, command=self.raise_new_query_window).pack(side=RIGHT)

        # Scrollable area
        canvas_f = Frame(self.content_area, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=px)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        self.query_container = Frame(canvas, bg=CONTENT_BG)
        
        self.query_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.query_container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)
        
        self.refresh_emp_queries()

    def refresh_emp_queries(self):
        if not hasattr(self, 'query_container'): return
        for widget in self.query_container.winfo_children(): widget.destroy()
        search = self.query_search_var.get().lower()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT q.id, p.name, q.subject, q.status, q.created_at, q.response
                FROM queries q
                LEFT JOIN projects p ON q.project_id = p.id
                WHERE q.user_name=?
                ORDER BY q.created_at DESC
            """, (CURRENT_USER_NAME,))
            
            rows = cur.fetchall()
            if not rows:
                Label(self.query_container, text="No queries submitted yet.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
            else:
                for qid, p_name, sub, status, ts, resp in rows:
                    if search and not (search in str(sub).lower() or search in str(p_name).lower()): continue
                    
                    card = Frame(self.query_container, bg=CARD_BG, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=(0, 15))
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=sub.upper() if sub else "GENERAL QUERY", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    s_color = ACCENT_ORANGE if status == 'Pending' else ACCENT_GREEN
                    badge = Frame(top, bg=s_color, padx=10, pady=3)
                    badge.pack(side=RIGHT)
                    Label(badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=s_color, fg=WHITE).pack()
                    
                    Label(card, text=f"PROJECT: {p_name or 'N/A'} • {ts}", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=8)
                    
                    if resp:
                        r_box = Frame(card, bg="#1a2035", padx=20, pady=15)
                        r_box.pack(fill=X, pady=(15, 0))
                        Label(r_box, text=f"RESOLUTION: {resp}", font=('Segoe UI', 9, 'italic'), bg="#1a2035", fg=ACCENT_BLUE, wraplength=800, justify=LEFT).pack(anchor=W)

                    # Hover effect
                    def _e(e, c=card): c.config(highlightbackground=ACCENT_BLUE, bg="#252d4d")
                    def _l(e, c=card): c.config(highlightbackground=BORDER_COLOR, bg=CARD_BG)
                    card.bind("<Enter>", _e); card.bind("<Leave>", _l)
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Query refresh failed: {e}")

    def load_emp_attendance(self):
        debug_log("DEBUG: Loading employee attendance hub...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        Label(h, text="TIME & ATTENDANCE", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Track your work cycles and daily logs.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Action Area (Glassmorphic)
        strip = Frame(self.content_area, bg=CARD_BG, padx=30, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
        strip.pack(fill=X, padx=px, pady=(0, 25))
        
        msg_f = Frame(strip, bg=CARD_BG)
        msg_f.pack(side=LEFT)
        self.att_status_lbl = Label(msg_f, text="SYNCING LOGS...", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE)
        self.att_status_lbl.pack(anchor=W)
        Label(msg_f, text="Always ensure you clock out before leaving.", font=('Segoe UI', 8), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
        
        btn_f = Frame(strip, bg=CARD_BG)
        btn_f.pack(side=RIGHT)
        self.btn_clock_in = Button(btn_f, text="CLOCK IN", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=25, pady=12, command=self.handle_clock_in)
        self.btn_clock_in.pack(side=LEFT, padx=5)
        self.btn_clock_out = Button(btn_f, text="CLOCK OUT", bg=ACCENT_ORANGE, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=25, pady=12, command=self.handle_clock_out)
        self.btn_clock_out.pack(side=LEFT, padx=5)

        # Recent Logs (Scrollable)
        Label(self.content_area, text="RECENT LOGS", font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, padx=px, pady=(10, 15))
        
        canvas_f = Frame(self.content_area, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=px)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        self.att_container = Frame(canvas, bg=CONTENT_BG)
        
        self.att_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.att_container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)
        
        self.refresh_emp_attendance()

    def refresh_emp_attendance(self):
        if not hasattr(self, 'att_container'): return
        for widget in self.att_container.winfo_children(): widget.destroy()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Detect attendance name column
            cur.execute("PRAGMA table_info(attendance)")
            cols = [r[1] for r in cur.fetchall()]
            name_col = "employee_name" if "employee_name" in cols else "name"
            
            # 1. Update Current Status
            cur.execute(f"SELECT status, clock_in, clock_out FROM attendance WHERE {name_col}=? AND date=?", (CURRENT_USER_NAME, today))
            today_row = cur.fetchone()
            if today_row:
                if today_row[2]: # Clocked out
                    self.att_status_lbl.config(text=f"SHIFT COMPLETED • {today_row[1]} to {today_row[2]}", fg=ACCENT_GREEN)
                    self.btn_clock_in.config(state=DISABLED, bg="#333")
                    self.btn_clock_out.config(state=DISABLED, bg="#333")
                else:
                    self.att_status_lbl.config(text=f"ACTIVE SHIFT • IN AT {today_row[1]}", fg=ACCENT_ORANGE)
                    self.btn_clock_in.config(state=DISABLED, bg="#333")
                    self.btn_clock_out.config(state=NORMAL, bg=ACCENT_ORANGE)
            else:
                self.att_status_lbl.config(text="READY TO START SHIFT", fg=ACCENT_BLUE)
                self.btn_clock_in.config(state=NORMAL, bg=ACCENT_GREEN)
                self.btn_clock_out.config(state=DISABLED, bg="#333")
                
            # 2. Render Historical Logs
            cur.execute(f"SELECT date, clock_in, clock_out, status FROM attendance WHERE {name_col}=? ORDER BY date DESC LIMIT 10", (CURRENT_USER_NAME,))
            logs = cur.fetchall()
            if not logs:
                Label(self.att_container, text="No attendance logs found.", font=('Segoe UI', 11), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=40)
            else:
                for d, cin, cout, st in logs:
                    card = Frame(self.att_container, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=(0, 8))
                    
                    Label(card, text=d, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    Label(card, text=f"{cin or '--'}  →  {cout or '--'}", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=30)
                    
                    c = ACCENT_GREEN if st == 'Present' else ACCENT_ORANGE
                    Label(card, text=st.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=c).pack(side=RIGHT)
            
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Attendance refresh failed: {e}")

    def handle_clock_in(self):
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            now = datetime.now().strftime("%H:%M:%S")
            cur.execute("PRAGMA table_info(attendance)")
            cols = [r[1] for r in cur.fetchall()]
            name_col = "employee_name" if "employee_name" in cols else "name"
            cur.execute(f"INSERT INTO attendance ({name_col}, date, clock_in, status) VALUES (?, ?, ?, ?)", (CURRENT_USER_NAME, today, now, 'Present'))
            con.commit(); self.refresh_current_panel(); con.close()
            self.refresh_emp_attendance()
        except Exception as e:
            messagebox.showerror("Error", f"Clock-in failed: {e}")

    def handle_clock_out(self):
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            now = datetime.now().strftime("%H:%M:%S")
            cur.execute("PRAGMA table_info(attendance)")
            cols = [r[1] for r in cur.fetchall()]
            name_col = "employee_name" if "employee_name" in cols else "name"
            cur.execute(f"UPDATE attendance SET clock_out=? WHERE {name_col}=? AND date=?", (now, CURRENT_USER_NAME, today))
            con.commit(); self.refresh_current_panel(); con.close()
            self.refresh_emp_attendance()
        except Exception as e:
            messagebox.showerror("Error", f"Clock-out failed: {e}")


    def load_emp_leave_requests(self):
        debug_log("DEBUG: Loading employee leave requests cockpit...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        Label(h, text="LEAVE MANAGEMENT", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Request leaves and track approval status.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Action Strip
        strip = Frame(self.content_area, bg=CONTENT_BG)
        strip.pack(fill=X, padx=px, pady=(0, 20))
        Button(strip, text="+ APPLY FOR LEAVE", bg=ACCENT_ORANGE, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=20, pady=10, command=self.request_leave_window).pack(side=RIGHT)

        # Scrollable area
        canvas_f = Frame(self.content_area, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=px)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        self.leave_container = Frame(canvas, bg=CONTENT_BG)
        
        self.leave_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.leave_container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)
        
        self.refresh_emp_leave_requests()

    def refresh_emp_leave_requests(self):
        if not hasattr(self, 'leave_container'): return
        for widget in self.leave_container.winfo_children(): widget.destroy()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT start_date, end_date, reason, status, id FROM leave_requests WHERE member_name=? ORDER BY id DESC", (CURRENT_USER_NAME,))
            rows = cur.fetchall()
            
            if not rows:
                Label(self.leave_container, text="No leave requests found.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
            else:
                for start, end, reason, status, lid in rows:
                    card = Frame(self.leave_container, bg=CARD_BG, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=(0, 15))
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=f"📅 {start} — {end}", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    s_color = ACCENT_ORANGE if status == 'Pending' else (ACCENT_GREEN if status == 'Approved' else ACCENT_RED)
                    badge = Frame(top, bg=s_color, padx=10, pady=2)
                    badge.pack(side=RIGHT)
                    badge._is_badge = True
                    Label(badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=s_color, fg=WHITE).pack()
                    
                    Label(card, text=reason, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=700, justify=LEFT).pack(anchor=W, pady=(10, 0))
                    self._apply_hover_effect(card, ACCENT_BLUE)
                    
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Leave refresh failed: {e}")


    def load_emp_timesheets(self):
        debug_log("DEBUG: Loading employee timesheets hub...")
        for widget in self.content_area.winfo_children(): widget.destroy()
        px = self.get_responsive_padx()
        
        # Header
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=(30, 20))
        Label(h, text="WORK TIMESHEETS", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Detailed breakdown of your project contributions.", font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=25, pady=(12, 0))

        # Action Strip
        strip = Frame(self.content_area, bg=CONTENT_BG)
        strip.pack(fill=X, padx=px, pady=(0, 20))
        Button(strip, text="+ LOG TIME ENTRY", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), relief=FLAT, padx=20, pady=10, command=self.log_time_window).pack(side=RIGHT)

        # Scrollable area
        canvas_f = Frame(self.content_area, bg=CONTENT_BG)
        canvas_f.pack(fill=BOTH, expand=True, padx=px)
        
        canvas = Canvas(canvas_f, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_f, orient=VERTICAL, command=canvas.yview)
        self.time_container = Frame(canvas, bg=CONTENT_BG)
        
        self.time_container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_win = canvas.create_window((0, 0), window=self.time_container, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_win, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(self.content_area, canvas)
        
        self.refresh_emp_timesheets()

    def refresh_emp_timesheets(self):
        if not hasattr(self, 'time_container'): return
        for widget in self.time_container.winfo_children(): widget.destroy()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT t.date, p.name, t.hours, t.activity, t.id 
                FROM timesheets t
                LEFT JOIN projects p ON t.project_id = p.id
                WHERE t.employee_name=? 
                ORDER BY t.date DESC
            """, (CURRENT_USER_NAME,))
            rows = cur.fetchall()
            
            if not rows:
                Label(self.time_container, text="No timesheet entries found.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=100)
            else:
                for dt, p_name, hrs, act, tid in rows:
                    card = Frame(self.time_container, bg=CARD_BG, padx=25, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=(0, 15))
                    
                    top = Frame(card, bg=CARD_BG)
                    top.pack(fill=X)
                    Label(top, text=dt, font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    Label(top, text=f"{hrs} HOURS", font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(side=RIGHT)
                    
                    Label(card, text=f"PROJECT: {p_name or 'GENERAL'}", font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(5, 10))
                    Label(card, text=act if act else "No activity description.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=800, justify=LEFT).pack(anchor=W)

                    # Hover effect
                    def _e(e, c=card): c.config(highlightbackground=ACCENT_GREEN, bg="#1a2b20")
                    def _l(e, c=card): c.config(highlightbackground=BORDER_COLOR, bg=CARD_BG)
                    card.bind("<Enter>", _e); card.bind("<Leave>", _l)
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Timesheet refresh failed: {e}")


    # --- Feature Windows ---
    def raise_new_query_window(self):
        w = Toplevel(self.root)
        w.title("Raise New Query")
        w.geometry("500x450")
        w.minsize(450, 400)
        w.resizable(True, True)
        w.config(bg=SIDEBAR_BG)
        
        Label(w, text="New Query", font=('Segoe UI', 14, 'bold'), bg=SIDEBAR_BG, fg=WHITE).pack(pady=20)
        
        Label(w, text="Subject", bg=SIDEBAR_BG, fg="#9aa3c2").pack(anchor="w", padx=40)
        subj_ent = Entry(w, bg="#1a2035", fg=WHITE, insertbackground=WHITE, relief=FLAT, font=('Segoe UI', 10))
        subj_ent.pack(fill=X, padx=40, pady=5)
        
        Label(w, text="Description", bg=SIDEBAR_BG, fg="#9aa3c2").pack(anchor="w", padx=40, pady=(10, 0))
        desc_txt = Text(w, bg="#1a2035", fg=WHITE, insertbackground=WHITE, relief=FLAT, height=6, font=('Segoe UI', 10))
        desc_txt.pack(fill=X, padx=40, pady=5)
        
        def submit():
            subj = subj_ent.get()
            desc = desc_txt.get("1.0", END).strip()
            if not subj or not desc:
                messagebox.showerror("Error", "All fields are required")
                return
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("INSERT INTO queries (user_name, subject, message, status) VALUES (?,?,?,?)",
                            (CURRENT_USER_NAME, subj, desc, 'Open'))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Query raised successfully")
                w.destroy()
                self.refresh_emp_queries()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to raise query: {e}")
                
        Button(w, text="SUBMIT", bg=PRIMARY_RED, fg=WHITE, font=('Segoe UI', 10, 'bold'), 
               relief=FLAT, pady=8, command=submit).pack(fill=X, padx=40, pady=30)

    def request_leave_window(self):
        w = Toplevel(self.root)
        w.title("Request Leave")
        w.geometry("500x650")
        w.minsize(450, 500)
        w.resizable(True, True)
        w.config(bg=BG_CARD)
        w.transient(self.root)
        w.grab_set()
        
        # Brand Stripe
        stripe = Frame(w, bg=PRIMARY_RED, height=3)
        stripe.pack(fill=X)

        # Center
        mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 250
        my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 325
        w.geometry(f"500x650+{mx}+{my}")

        header = Frame(w, bg=HEADER_BG, pady=20)
        header.pack(fill=X)
        Label(header, text="NEW LEAVE REQUEST", font=('Rajdhani', 16, 'bold'), bg=HEADER_BG, fg=WHITE).pack()
        
        body = Frame(w, bg=BG_CARD, padx=40, pady=25)
        body.pack(fill=BOTH, expand=True)

        def create_field(parent, label, widget_type="entry", values=None, initial=""):
            f = Frame(parent, bg=BG_CARD)
            f.pack(fill=X, pady=(0, 15))
            Label(f, text=label.upper(), font=('Segoe UI', 8, 'bold'), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 5))
            if widget_type == "combo":
                e = ttk.Combobox(f, values=values, state="readonly", style='Employee.TCombobox')
                e.pack(fill=X, pady=2, ipady=4)
                if initial: e.set(initial)
            elif widget_type == "text":
                e = Text(f, bg="#1a2035", fg=WHITE, insertbackground=WHITE, font=('Segoe UI', 10), 
                        relief=FLAT, highlightbackground="#2e3760", highlightthickness=1, height=4)
                e.pack(fill=X, pady=2)
            else:
                e = Entry(f, bg="#1a2035", fg=WHITE, insertbackground=WHITE, font=('Segoe UI', 10), 
                         relief=FLAT, highlightbackground="#2e3760", highlightthickness=1)
                e.pack(fill=X, pady=2, ipady=8)
                if initial: e.insert(0, initial)
            return e

        type_cb = create_field(body, "Leave Type", "combo", ["Sick Leave", "Vacation", "Personal Leave", "Emergency"], "Vacation")
        start_ent = create_field(body, "Start Date (YYYY-MM-DD)", initial=datetime.now().strftime("%Y-%m-%d"))
        end_ent = create_field(body, "End Date (YYYY-MM-DD)", initial=(datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d"))
        reason_txt = create_field(body, "Reason", "text")
        
        def submit():
            l_type = type_cb.get()
            start = start_ent.get().strip()
            end = end_ent.get().strip()
            reason = reason_txt.get("1.0", END).strip()
            if not start or not end or not reason:
                messagebox.showerror("Error", "All fields required")
                return
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("INSERT INTO leave_requests (member_name, leave_type, start_date, end_date, reason, status) VALUES (?,?,?,?,?,?)",
                            (CURRENT_USER_NAME, l_type, start, end, reason, 'Pending'))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Leave request submitted")
                w.destroy()
                self.load_emp_leave_requests()
            except Exception as e:
                messagebox.showerror("Error", f"Failed: {e}")
                
        Button(body, text="SUBMIT REQUEST", bg=PRIMARY_RED, fg=WHITE, font=('Segoe UI', 10, 'bold'), 
               relief=FLAT, pady=12, command=submit).pack(fill=X, pady=(10, 0))

    def log_time_window(self):
        w = Toplevel(self.root)
        w.title("Log Work Time")
        w.geometry("500x550")
        w.minsize(450, 450)
        w.resizable(True, True)
        w.config(bg=BG_CARD)
        w.transient(self.root)
        w.grab_set()
        
        # Brand Stripe
        stripe = Frame(w, bg="#ff9f43", height=3)
        stripe.pack(fill=X)

        # Center
        mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 250
        my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 275
        w.geometry(f"500x550+{mx}+{my}")

        header = Frame(w, bg=HEADER_BG, pady=20)
        header.pack(fill=X)
        Label(header, text="DAILY TIMESHEET", font=('Rajdhani', 16, 'bold'), bg=HEADER_BG, fg=WHITE).pack()
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT id, title FROM tasks WHERE assigned_to=? AND status!='Completed'", (CURRENT_USER_NAME,))
        tasks = cur.fetchall()
        con.close()
        
        body = Frame(w, bg=BG_CARD, padx=40, pady=25)
        body.pack(fill=BOTH, expand=True)

        if not tasks:
            Label(body, text="No active tasks to log time for.", bg=BG_CARD, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(pady=50)
            return

        def create_field(parent, label, widget_type="entry", values=None):
            f = Frame(parent, bg=BG_CARD)
            f.pack(fill=X, pady=(0, 15))
            Label(f, text=label.upper(), font=('Segoe UI', 8, 'bold'), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 5))
            if widget_type == "combo":
                e = ttk.Combobox(f, values=values, state="readonly", style='Employee.TCombobox')
                e.pack(fill=X, pady=2, ipady=4)
            else:
                e = Entry(f, bg="#1a2035", fg=WHITE, insertbackground=WHITE, font=('Segoe UI', 10), 
                         relief=FLAT, highlightbackground="#2e3760", highlightthickness=1)
                e.pack(fill=X, pady=2, ipady=8)
            return e

        task_vals = [f"{t[0]} - {t[1]}" for t in tasks]
        task_cb = create_field(body, "Select Task", "combo", task_vals)
        hrs_ent = create_field(body, "Hours Worked Today")
        note_ent = create_field(body, "Short Note / Progress")
        
        def submit():
            task_str = task_cb.get()
            hrs = hrs_ent.get().strip()
            note = note_ent.get().strip()
            if not task_str or not hrs: 
                messagebox.showwarning("Incomplete", "Task and Hours are required.")
                return
            
            t_id = task_str.split(" - ")[0]
            dt = datetime.now().strftime("%Y-%m-%d")
            tm = datetime.now().strftime("%H:%M:%S")
            ts = f"{dt} {tm}"
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("INSERT INTO timesheets (employee_name, date, task_id, hours, description, timestamp) VALUES (?,?,?,?,?,?)",
                            (CURRENT_USER_NAME, dt, t_id, hrs, note, ts))
                cur.execute("INSERT OR REPLACE INTO attendance (name, date, status, clock_in) VALUES (?,?,?,?)",
                            (CURRENT_USER_NAME, dt, 'Present', tm))
                con.commit(); self.refresh_current_panel()
                con.close()
                messagebox.showinfo("Success", "Work logged and attendance marked.")
                w.destroy()
                try: self.load_emp_attendance()
                except: pass
                self.switch_page('dashboard')
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(w, text="LOG TIME & ATTENDANCE", bg="#ff9f43", fg=WHITE, font=('Segoe UI', 10, 'bold'), 
               relief=FLAT, pady=10, command=submit).pack(fill=X, padx=40, pady=30)

    def load_showcase(self):
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True)
        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        def _configure_window(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", _configure_window)
        def _on_mousewheel(event):
            try:
                if not canvas.winfo_exists():
                    return
                if event.delta > 0:
                    canvas.yview_scroll(-3, "units")
                elif event.delta < 0:
                    canvas.yview_scroll(3, "units")
            except:
                pass
        
        self._bind_canvas_scrolling(container, canvas)
        h = Frame(scrollable_frame, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=(30, 10))
        Label(h, text="Nova Experience", font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(h, text="Premium typography, refined palettes, micro-interactions, and motion.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(6,0))
        hero = Frame(scrollable_frame, bg=CONTENT_BG)
        hero.pack(fill=X, padx=30, pady=(10, 30))
        hero_canvas = Canvas(hero, bg=CONTENT_BG, height=260, highlightthickness=0)
        hero_canvas.pack(fill=X)
        l1 = hero_canvas.create_oval(-200, 20, 400, 300, fill=ACCENT_BLUE, outline="")
        l2 = hero_canvas.create_oval(200, -80, 800, 200, fill=ACCENT_PURPLE, outline="")
        l3 = hero_canvas.create_oval(-100, 160, 500, 460, fill=ACCENT_RED, outline="")
        def _parallax(e):
            try:
                cx = hero_canvas.winfo_width()//2
                cy = hero_canvas.winfo_height()//2
                dx = (e.x - cx)
                dy = (e.y - cy)
                hero_canvas.move(l1, dx*0.01, dy*0.01)
                hero_canvas.move(l2, dx*0.02, dy*0.02)
                hero_canvas.move(l3, dx*0.015, dy*0.015)
            except:
                pass
        hero_canvas.bind("<Motion>", _parallax)
        Label(hero, text="Design that feels alive", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(12,0))
        Label(hero, text="Micro-interactions and subtle motion crafted for clarity and delight.", font=('Segoe UI', 11), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W)
        cta = Frame(hero, bg=CONTENT_BG)
        cta.pack(fill=X, pady=(10,0))
        Button(cta, text="Explore", bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, padx=16, pady=8, command=lambda: None).pack(side=LEFT)
        Button(cta, text="See Showcase", bg=INPUT_BG, fg=WHITE, relief=FLAT, padx=16, pady=8, command=lambda: None).pack(side=LEFT, padx=10)
        feats = Frame(scrollable_frame, bg=CONTENT_BG)
        feats.pack(fill=X, padx=30)
        Label(feats, text="Features", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0,10))
        grid = Frame(feats, bg=CONTENT_BG)
        grid.pack(fill=X)
        def make_card(parent, title, desc):
            f = Frame(parent, bg=CARD_BG, padx=18, pady=16)
            Label(f, text=title, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(f, text=desc, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT, wraplength=380).pack(anchor=W, pady=(6,0))
            def on_enter(e):
                f.config(bg=ACCENT_HOVER)
            def on_leave(e):
                f.config(bg=CARD_BG)
            f.bind("<Enter>", on_enter)
            f.bind("<Leave>", on_leave)
            return f
        r1 = Frame(grid, bg=CONTENT_BG)
        r1.pack(fill=X)
        make_card(r1, "Premium Type", "Cohesive font scales blending Inter-style rhythm for hierarchy.").pack(side=LEFT, fill=X, expand=True, padx=(0,10))
        make_card(r1, "Adaptive Layouts", "Fluid grids and smart breakpoints render consistently across devices.").pack(side=LEFT, fill=X, expand=True, padx=(10,0))
        r2 = Frame(grid, bg=CONTENT_BG)
        r2.pack(fill=X, pady=(10,0))
        make_card(r2, "Accessible Motion", "Respects reduced motion preferences with restrained animations.").pack(side=LEFT, fill=X, expand=True, padx=(0,10))
        make_card(r2, "Micro-Interactions", "Subtle transitions, hover states, and pressed affordances.").pack(side=LEFT, fill=X, expand=True, padx=(10,0))
        showcase = Frame(scrollable_frame, bg=CONTENT_BG)
        showcase.pack(fill=X, padx=30, pady=20)
        Label(showcase, text="Showcase", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0,10))
        rows = Frame(showcase, bg=CONTENT_BG)
        rows.pack(fill=X)
        s1 = Frame(rows, bg=CARD_BG, padx=18, pady=16)
        s1.pack(fill=X)
        media1 = Frame(s1, bg=INPUT_BG, width=140, height=90)
        media1.pack(side=LEFT)
        Label(s1, text="Glassmorphic Dashboard", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, padx=12)
        Label(s1, text="Layered translucency and soft shadows with elevation.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, padx=12)
        s2 = Frame(rows, bg=CARD_BG, padx=18, pady=16)
        s2.pack(fill=X, pady=(10,0))
        media2 = Frame(s2, bg=INPUT_BG, width=140, height=90)
        media2.pack(side=LEFT)
        Label(s2, text="Parallax Hero", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, padx=12)
        Label(s2, text="Dimensional movement using multi-layer shapes.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, padx=12)
def main(standalone=False):
    if not init_database():
        return
    
    load_session()
    
    root = Tk()
    app = ProjectMonitorApp(root, standalone=standalone)

    def _on_app_close():
        """Cancel ALL pending after() timers before destroying the window.
        This prevents 'invalid command name' TclError when the user logs out
        and back in — the old timers would otherwise fire on the dead root.
        """
        # 1. Stop the polling loop first
        try:
            app.stop_pm_dashboard_auto_refresh()
        except Exception:
            pass
        # 2. Cancel any other tracked after() jobs on the app
        for attr in ('_auto_refresh_timer', '_resize_job', '_grid_job'):
            job = getattr(app, attr, None)
            if job:
                try:
                    root.after_cancel(job)
                except Exception:
                    pass
        # 3. Cancel ALL remaining after() callbacks registered on this root
        # (covers lambdas and one-off timers like update_notification_count)
        try:
            # tk.call returns a list of pending after IDs
            pending = root.tk.call('after', 'info')
            if pending:
                for after_id in root.tk.splitlist(pending):
                    try:
                        root.after_cancel(after_id)
                    except Exception:
                        pass
        except Exception:
            pass
        # 4. Now it is safe to destroy
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_app_close)

    # Silence any stale 'invalid command name' TclErrors that reach
    # report_callback_exception (belt-and-suspenders for any we miss)
    import tkinter
    def _silent_tcl_error(exc_type, exc_val, exc_tb):
        msg = str(exc_val)
        if 'invalid command name' in msg or 'application has been destroyed' in msg:
            debug_log(f"DEBUG: Suppressed stale after() callback: {exc_val}")
            return  # silently ignore
        # Anything else — show it
        import traceback as _tb
        _tb.print_exception(exc_type, exc_val, exc_tb)
    root.report_callback_exception = _silent_tcl_error

    root.mainloop()


if __name__ == "__main__":
    main(standalone=True)












