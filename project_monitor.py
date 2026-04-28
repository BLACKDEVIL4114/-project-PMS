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
    if ML_MODEL_CACHE is None:
        try:
            import joblib
            ML_MODEL_CACHE = joblib.load('pms_delay_model.joblib')
        except Exception as e:
            debug_log(f"DEBUG: Failed to load ML model: {e}")
            ML_MODEL_CACHE = False # Mark as failed
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
DEBUG_LOGS = False

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
        cursor.execute("""
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
        
        # Seed Admin if not exists
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO users VALUES (?,?,?)", ('admin', hashlib.sha256('1234'.encode()).hexdigest(), 'admin@company.com'))

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
        self.pm_refresh_interval_ms = 1500
        self._last_db_signature = None
        self._last_ui_interaction_ts = time.monotonic()
        self._resize_job = None
        
        self.setup_styles()
        self.employee_submenu_visible = False
        self.init_ui()
        
        self.root.bind("<Configure>", self._on_root_configure)
        self.schedule_pm_dashboard_auto_refresh()

    def stop_pm_dashboard_auto_refresh(self):
        if self.pm_refresh_job:
            try:
                self.root.after_cancel(self.pm_refresh_job)
            except:
                pass
            self.pm_refresh_job = None

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
        self.pm_refresh_interval_ms = 3000 # Increased for better performance
        self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)

    def refresh_pm_dashboard_if_active(self):
        self.pm_refresh_job = None
        try:
            if not self.root.winfo_exists():
                return
            if self._resize_job is not None:
                self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
                return
            # Smarter idle check: Only refresh if user is inactive for at least 2 seconds
            if time.monotonic() - self._last_ui_interaction_ts < 2.0:
                self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
                return
            current_sig = self._get_db_change_signature()
            db_changed = current_sig != self._last_db_signature
            self._last_db_signature = current_sig
            
            if db_changed:
                role = CURRENT_USER_ROLE.lower()
                # 1. Project Manager / Team Leader Dashboard
                if role in ('project manager','team leader') and self.current_page == 'dashboard':
                    # Only reload if we are not busy rendering
                    self.switch_page('dashboard')
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
                
                # Yield to UI after updates
                self.root.update_idletasks()
            
            # Continue polling
            self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)
        except Exception as e:
            debug_log(f"DEBUG: Real-time refresh error: {e}")
            self.pm_refresh_job = self.root.after(self.pm_refresh_interval_ms, self.refresh_pm_dashboard_if_active)

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
        # FIX 6: bind_all("<MouseWheel>") was binding scroll to EVERY widget in the
        # entire app, not just this panel. When multiple panels each call bind_all,
        # the last one registered wins and all others stop scrolling.
        # Fix: bind to `canvas` directly (scoped) instead of bind_all (global).
        # The Enter/Leave approach gates scroll activation to when the mouse is over
        # this specific canvas — no cross-panel interference.

        def _on_mousewheel(event):
            self._mark_ui_interaction()
            try:
                if not canvas.winfo_exists():
                    return
                units = self._normalize_scroll_units(event.delta)
                if units:
                    canvas.yview_scroll(-units, "units")
            except Exception:
                pass

        def _on_shift_mousewheel(event):
            self._mark_ui_interaction()
            if not allow_horizontal:
                return
            try:
                if not canvas.winfo_exists():
                    return
                units = self._normalize_scroll_units(event.delta)
                if units:
                    canvas.xview_scroll(-units, "units")
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
            # FIX: Bind only to this canvas widget — not bind_all which is global
            try:
                if not canvas.winfo_exists():
                    return
                canvas.bind("<MouseWheel>", _on_mousewheel)
                canvas.bind("<Button-4>", _on_button4)
                canvas.bind("<Button-5>", _on_button5)
                if allow_horizontal:
                    canvas.bind("<Shift-MouseWheel>", _on_shift_mousewheel)
            except Exception:
                pass

        def _unbind_mousewheel(_event):
            # FIX: Unbind only from this canvas — not unbind_all (which would kill
            # scroll on every other panel too!)
            try:
                canvas.unbind("<MouseWheel>")
                canvas.unbind("<Button-4>")
                canvas.unbind("<Button-5>")
                canvas.unbind("<Shift-MouseWheel>")
            except Exception:
                pass

        wrapper.bind("<Enter>", _bind_mousewheel)
        wrapper.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

    def init_ui(self):
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
            allowed_pages.extend(['members', 'tasks', 'review_tasks', 'team_analytics', 'team_queries'])
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
            'review_tasks', 'team_leaves', 'team_queries', # Admin/TL items
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

            # Bind row and accent to click as well for better UX
            def _wrap_click(event, k=key):
                self.switch_page(k)

            row.bind("<Button-1>", _wrap_click)
            row._accent.bind("<Button-1>", _wrap_click)
            # Ensure no right-clck or middle-click triggers switch
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

            con.commit()
            con.close()
            return True
        except Exception as e:
            debug_log(f"[API Sync] Sync Error: {e}")
            return False

    def refresh_current_page(self):
        """Universal Hot-Reload: Performs API sync then refreshes the active dashboard view"""
        if not hasattr(self, 'current_page') or not self.current_page:
            return

        # Visual feedback during sync
        original_text = ""
        if hasattr(self, 'btn_refresh'):
            original_text = self.btn_refresh.cget('text')
            self.btn_refresh.config(text="🔄 Syncing...", state=DISABLED)
            self.root.update_idletasks()

        def _bg_sync_thread():
            # Perform REST API -> SQLite Sync in background
            sync_success = self.sync_data_from_api()
            # Delegate UI updates back to the main thread securely
            self.root.after(0, lambda: self._complete_hot_reload(sync_success, original_text))

        threading.Thread(target=_bg_sync_thread, daemon=True).start()

    def _complete_hot_reload(self, success, original_text):
        # Restore button
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.config(text=original_text, state=NORMAL)

        role = str(CURRENT_USER_ROLE).lower()
        # Trigger refresh based on current page
        if self.current_page == 'dashboard':
            if role in ('admin', 'team leader'):
                self.load_dashboard() 
            elif role == 'project manager':
                self.load_pm_dashboard()
            else:
                self.load_emp_dashboard()
        elif self.current_page == 'emp_analysis':
            self.refresh_emp_analysis()
        elif self.current_page == 'emp_dashboard':
            self.refresh_emp_dashboard()
        elif self.current_page == 'emp_my_tasks':
            self.refresh_emp_tasks_tab()
        else:
            # Full reload for other pages
            p = self.current_page
            self.current_page = None # Force reload
            self.switch_page(p)
        
        self.root.update_idletasks()
        
        print(f"[UI Sync] Page '{self.current_page}' synchronized and updated.")

    def update_notification_count(self):
        count = 0
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Password requests
            cur.execute("SELECT COUNT(*) FROM users WHERE reset_requested = 1")
            count += cur.fetchone()[0]
            # Leave requests
            try:
                cur.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'Pending'")
                count += cur.fetchone()[0]
            except: pass
            con.close()
        except: pass
        
        self.notif_btn.config(text=f"Notifications ({count})")
        if count > 0:
            self.notif_btn.config(fg=ACCENT_ORANGE)
        else:
            self.notif_btn.config(fg=TEXT_WHITE)
        
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
                
                con.commit()
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
                con.commit()
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
        footer = Frame(scrollable_frame, bg=CONTENT_BG, padx=30, pady=(8, 24))
        footer.pack(fill=X)
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
                con.commit()
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

    def switch_page(self, page_name):
        # Hard route guard: Team Leader cannot open Projects page.
        role = str(CURRENT_USER_ROLE).lower()
        if page_name == 'projects' and 'leader' in role:
            page_name = 'dashboard'

        if hasattr(self, 'current_page') and self.current_page == page_name:
            # If it's a dashboard, we might want to refresh data only, not rebuild UI
            if page_name == 'dashboard':
                self.refresh_current_page() 
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
                btn.config(bg=SIDEBAR_ACTIVE_BG, fg=TEXT_WHITE)
                try: row._accent.config(bg=PRIMARY_RED)
                except: pass
            else:
                btn.config(bg=BG_DARK, fg=TEXT_SECONDARY)
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
                self.show_reset_requests(is_page=True)
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
            # Filtered Stats for Team Leader - Optimized
            try:
                # 1. Total Team Members (Optimized subquery)
                cursor.execute("""
                    SELECT COUNT(DISTINCT e.name)
                    FROM employee e
                    WHERE e.name IS NOT NULL AND e.name != ''
                      AND (
                           e.reporting_manager = ?
                           OR EXISTS (
                               SELECT 1 FROM tasks t 
                               JOIN projects p ON t.project_id = p.id
                               WHERE t.assigned_to = e.name 
                                 AND p.team_leader LIKE ?
                           )
                      )
                      AND lower(e.name) != lower(?)
                """, (CURRENT_USER_NAME, f"%{CURRENT_USER_NAME}%", CURRENT_USER_NAME))
                total_members = cursor.fetchone()[0] or 0
                
                # 2. Combined Status counts for tasks in TL projects (Single query for multiple stats)
                cursor.execute("""
                    SELECT 
                        SUM(CASE WHEN status IN ('Ongoing', 'In Progress', 'Pending') THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status = 'Pending Approval' THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status != 'Completed' AND due_date < date('now') THEN 1 ELSE 0 END),
                        SUM(CASE WHEN status = 'Completed' AND (date(completed_date) >= date('now', '-7 days') OR date(created_date) >= date('now', '-7 days')) THEN 1 ELSE 0 END)
                    FROM tasks 
                    WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                """, (f"%{CURRENT_USER_NAME}%",))
                
                stats_row = cursor.fetchone()
                active_tasks = stats_row[0] or 0
                pending_reviews = stats_row[1] or 0
                overdue_tasks = stats_row[2] or 0
                completed_this_week = stats_row[3] or 0
                
            except Exception as e:
                debug_log(f"DEBUG: TL Stats optimization error: {e}")
                total_members = 0
                active_tasks = 0
                pending_reviews = 0
                overdue_tasks = 0
                completed_this_week = 0
            
            # 3. Overdue Tasks
            cursor.execute("""
                SELECT COUNT(*) 
                FROM tasks 
                WHERE status != 'Completed' 
                AND due_date < date('now')
                AND project_id IN (
                    SELECT id FROM projects WHERE lower(COALESCE(team_leader,'')) LIKE lower(?)
                )
            """, (f"%{CURRENT_USER_NAME}%",))
            overdue_tasks = cursor.fetchone()[0]
            
            # 4. Completed This Week
            cursor.execute("""
                SELECT COUNT(*) 
                FROM tasks 
                WHERE status='Completed' 
                AND (date(completed_date) >= date('now', '-7 days') OR date(created_date) >= date('now', '-7 days'))
                AND project_id IN (
                    SELECT id FROM projects WHERE lower(COALESCE(team_leader,'')) LIKE lower(?)
                )
            """, (f"%{CURRENT_USER_NAME}%",))
            completed_this_week = cursor.fetchone()[0]
            
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
            project_progress_data = []
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
            # Project Progress (Active Projects Health) - Optimized single query
            cursor.execute("""
                SELECT p.id, p.name, p.team_leader, p.manager, p.end_date, p.status,
                       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) as total_tasks,
                       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'Completed') as completed_tasks
                FROM projects p
                WHERE p.status = 'Ongoing' OR p.status = 'Delayed'
                LIMIT 5
            """)
            proj_rows = cursor.fetchall()
            project_progress_data = []
            for pid, pname, leader, mgr, end_date, p_status, tot, done in proj_rows:
                prog = int((done/tot)*100) if tot > 0 else 0
                project_progress_data.append((pid, pname, leader, mgr, end_date, prog, p_status))
                # No inner queries = No lag
                
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

        # 1. KPI Cards
        stats_frame = Frame(parent, bg=CONTENT_BG)
        stats_frame.pack(fill=X, padx=30)
        
        if is_tl:
            # --- Team Leader View ---
            self.create_stat_card_executive(stats_frame, "TEAM MEMBERS", str(total_members), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "ACTIVE TASKS", str(active_tasks), ACCENT_BLUE).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            
            overdue_card = self.create_stat_card_executive(stats_frame, "OVERDUE", str(overdue_tasks), ACCENT_RED)
            overdue_card.pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            
            if int(overdue_tasks) > 0:
                def pulse_urgent(step=0):
                    try:
                        if not overdue_card.winfo_exists(): return
                        colors = [ACCENT_RED, "#ff6b6b", "#ff9b9b", "#ff6b6b"]
                        overdue_card.config(highlightbackground=colors[step % len(colors)])
                        self.root.after(800, lambda: pulse_urgent(step + 1))
                    except: pass
                pulse_urgent()

            self.create_stat_card_executive(stats_frame, "COMPLETED (WK)", str(completed_this_week), ACCENT_GREEN).pack(side=LEFT, padx=(0, 15), fill=X, expand=True)
            self.create_stat_card_executive(stats_frame, "PENDING REQ", str(pending_requests), ACCENT_ORANGE).pack(side=LEFT, fill=X, expand=True)

            # 2. Pending Queries (TL Scoped)
            q_frame = Frame(parent, bg=CONTENT_BG)
            q_frame.pack(fill=X, padx=30, pady=20)
            Label(q_frame, text="Pending Queries from Team", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 10))
            tree_container = Frame(q_frame, bg=CARD_BG)
            tree_container.pack(fill=X, expand=True)
            
            cursor.execute("""
                SELECT q.id, q.user_name, IFNULL(p.name, 'General'), q.subject, q.created_at 
                FROM queries q
                LEFT JOIN projects p ON q.project_id = p.id
                WHERE (q.tl_name=? OR q.tl_name IS NULL) AND q.status='Open'
            """, (CURRENT_USER_NAME,))
            query_rows = cursor.fetchall()
            
            if not query_rows:
                Label(tree_container, text="No pending requests available.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 12)).pack(pady=40)
            else:
                cols = ("ID", "Employee", "Project", "Subject", "Date")
                q_tree = ttk.Treeview(tree_container, columns=cols, show='headings', height=6)
                for c in cols:
                    q_tree.heading(c, text=c)
                    q_tree.column(c, width=100)
                q_tree.pack(side=LEFT, fill=X, expand=True)
                q_scroll = Scrollbar(tree_container, orient=VERTICAL, command=q_tree.yview)
                q_scroll.pack(side=RIGHT, fill=Y)
                q_tree.configure(yscrollcommand=q_scroll.set)
                for row in query_rows: q_tree.insert("", END, values=row)

            # 3. Team Task Overview
            task_overview_frame = Frame(parent, bg=CARD_BG, padx=20, pady=20)
            task_overview_frame.pack(fill=X, padx=30, pady=20)
            Label(task_overview_frame, text="Team Task Overview", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
            
            cursor.execute("""
                SELECT assigned_to, COUNT(*) as total,
                       SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status='Delayed' OR (status!='Completed' AND due_date < date('now')) THEN 1 ELSE 0 END) as delayed
                FROM tasks WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                GROUP BY assigned_to ORDER BY total DESC
            """, (f"%{CURRENT_USER_NAME}%",))
            team_stats = cursor.fetchall()
            
            if not team_stats: 
                Label(task_overview_frame, text="No team tasks found.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 11)).pack(anchor=W)
            else:
                grid_f = Frame(task_overview_frame, bg=CARD_BG); grid_f.pack(fill=X)
                headers = ["Member", "Total Tasks", "Completed", "Delayed", "Progress"]
                for i, h in enumerate(headers):
                    Label(grid_f, text=h, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT, width=15, anchor=W).grid(row=0, column=i, padx=5, pady=5)
                
                for idx, (name, total, done, delay) in enumerate(team_stats):
                    row_idx = idx + 1
                    prog_val = int((done/total)*100) if total > 0 else 0
                    Label(grid_f, text=name, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, width=15, anchor=W).grid(row=row_idx, column=0, padx=5, pady=2)
                    Label(grid_f, text=str(total), font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, width=15, anchor=W).grid(row=row_idx, column=1, padx=5, pady=2)
                    Label(grid_f, text=str(done), font=('Segoe UI', 10), bg=ACCENT_GREEN, fg=WHITE, width=10).grid(row=row_idx, column=2, padx=5, pady=2)
                    
                    delay_fg = ACCENT_RED if delay > 0 else TEXT_WHITE
                    Label(grid_f, text=str(delay), font=('Segoe UI', 10), bg=CARD_BG, fg=delay_fg, width=15, anchor=W).grid(row=row_idx, column=3, padx=5, pady=2)
                    
                    p_bar_bg = Frame(grid_f, bg="#404040", height=10, width=100)
                    p_bar_bg.grid(row=row_idx, column=4, padx=5, pady=2, sticky=W)
                    p_bar_bg.pack_propagate(False)
                    if prog_val > 0: 
                        Frame(p_bar_bg, bg=ACCENT_BLUE, height=10, width=prog_val).pack(side=LEFT)
                    Label(grid_f, text=f"{prog_val}%", font=('Segoe UI', 9), bg=CARD_BG, fg=ACCENT_BLUE).grid(row=row_idx, column=5, padx=5, pady=2, sticky=W)
            
            # 4. Recent Activity
            act_frame = Frame(parent, bg=CARD_BG, padx=20, pady=20)
            act_frame.pack(fill=X, padx=30, pady=10)
            Label(act_frame, text="Recent Activity", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 10))
            
            try:
                # Optimization: Join with project table for faster TL lookup
                cursor.execute("""
                    SELECT a.timestamp, a.user_name, a.action 
                    FROM activity_timeline a
                    JOIN projects p ON a.project_id = p.id
                    WHERE p.team_leader LIKE ?
                    ORDER BY a.id DESC LIMIT 10
                """, (f"%{CURRENT_USER_NAME}%",))
                rows = cursor.fetchall()
                if not rows: 
                    Label(act_frame, text="No recent activity by team.", bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                else:
                    for ts, user, action in rows:
                        r = Frame(act_frame, bg=CARD_BG)
                        r.pack(fill=X, pady=2)
                        Label(r, text=f"- {user}", bg=CARD_BG, fg=ACCENT_BLUE).pack(side=LEFT)
                        Label(r, text=f"{action}", bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=6)
                        Label(r, text=f"{ts}", bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)
            except: pass
            
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
            
            # --- Incremental UI Rendering (Lazy Load) ---
            def _load_lazy_dashboard():
                if not grid_container.winfo_exists(): return
                
                # 1. LEFT TOP: Project Health
                lt = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                lt.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 10))
                Label(lt, text="Active Project Health", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
                
                if not project_progress_data:
                    Label(lt, text="No active projects.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
                else:
                    for pid, pname, leader, mgr, end_date, prog, status in project_progress_data[:4]:
                        r = Frame(lt, bg=CARD_BG)
                        r.pack(fill=X, pady=6)
                        h = Frame(r, bg=CARD_BG)
                        h.pack(fill=X)
                        Label(h, text=pname, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                        Label(h, text=f"{prog}%", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(side=RIGHT)
                        bb = Frame(r, bg="#1a2035", height=6)
                        bb.pack(fill=X, pady=(4, 0))
                        if prog > 0: Frame(bb, bg=ACCENT_BLUE, height=6).place(x=0, y=0, relwidth=prog/100)
                
                # 2. RIGHT TOP: Task Distribution
                rt = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                rt.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=(0, 10))
                Label(rt, text="Task Distribution", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
                
                stats_list = ["Pending", "In Progress", "Completed", "Delayed"]
                cls = [ACCENT_ORANGE, "#3b82f6", ACCENT_GREEN, ACCENT_RED]
                m_val = sum(task_dist.values()) if task_dist else 1
                
                for i, s in enumerate(stats_list):
                    c = task_dist.get(s, 0)
                    p = c / m_val if m_val > 0 else 0
                    row_f = Frame(rt, bg=CARD_BG)
                    row_f.pack(fill=X, pady=8)
                    Label(row_f, text=s, width=12, anchor=W, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(side=LEFT)
                    bc = Frame(row_f, bg="#1a2035", height=10)
                    bc.pack(side=LEFT, fill=X, expand=True, padx=10)
                    if c > 0: Frame(bc, bg=cls[i], height=10).place(x=0, y=0, relwidth=p)
                    Label(row_f, text=str(c), width=3, bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(side=RIGHT)

                # 3. LEFT BOTTOM: Critical Deadlines
                lb = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                lb.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(10, 0))
                Label(lb, text="Critical Deadlines", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
                
                if not upcoming:
                    Label(lb, text="No immediate deadlines.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
                else:
                    for tt, du in upcoming[:5]:
                        row_f = Frame(lb, bg=CARD_BG)
                        row_f.pack(fill=X, pady=4)
                        Label(row_f, text=f"- {tt}", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).pack(side=LEFT)
                        Label(row_f, text=du, bg=CARD_BG, fg=ACCENT_RED, font=('Segoe UI', 9, 'bold')).pack(side=RIGHT)

                # 4. RIGHT BOTTOM: Recent Audit Logs
                rb = Frame(grid_container, bg=CARD_BG, padx=20, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                rb.grid(row=1, column=1, sticky="nsew", padx=(10, 0), pady=(10, 0))
                Label(rb, text="Recent Audit Logs", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))
                
                if not recent_activity:
                    Label(rb, text="No recent activity logged.", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).pack(anchor=CENTER, pady=20)
                else:
                    for u, a, d in recent_activity:
                        rf = Frame(rb, bg=CARD_BG)
                        rf.pack(fill=X, pady=4)
                        Label(rf, text=u, bg=CARD_BG, fg=ACCENT_BLUE, font=('Segoe UI', 10, 'bold'), width=12, anchor=W).pack(side=LEFT)
                        Label(rf, text=a, bg=CARD_BG, fg=TEXT_SECONDARY, font=('Segoe UI', 10), wraplength=150, justify=LEFT).pack(side=LEFT, padx=5)
                        Label(rf, text=str(d), bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=RIGHT)
                
                grid_container.grid_columnconfigure(0, weight=1)
                grid_container.grid_columnconfigure(1, weight=1)

            # Start lazy loading
            self.root.after(10, _load_lazy_dashboard)

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
            cursor.execute("""
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
            # 1. Combined Metadata Query (Total Projs, TLs, Employees, Active, Delayed) - Optimized single pass
            cursor.execute("""
                SELECT 
                    (SELECT COUNT(*) FROM projects),
                    (SELECT COUNT(DISTINCT team_leader) FROM projects WHERE team_leader IS NOT NULL AND team_leader != ''),
                    (SELECT COUNT(*) FROM employee),
                    (SELECT COUNT(*) FROM projects WHERE status='Ongoing'),
                    (SELECT COUNT(*) FROM projects WHERE status='Delayed'),
                    (SELECT COUNT(*) FROM tasks WHERE status='Delayed')
            """)
            meta_stats = cursor.fetchone()
            total_projects = meta_stats[0] or 0
            total_tls = meta_stats[1] or 0
            total_employees = meta_stats[2] or 0
            active_projects = meta_stats[3] or 0
            delayed_projects = meta_stats[4] or 0
            total_delayed_tasks = meta_stats[5] or 0

            # 5. All Projects List (No Limit) with progress
            # 5. All Projects List (No Limit) with progress - Optimized single query
            cursor.execute("""
                SELECT p.id, p.name, p.team_leader, p.manager, p.end_date, p.status,
                       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id) as total_tasks,
                       (SELECT COUNT(*) FROM tasks t WHERE t.project_id = p.id AND t.status = 'Completed') as completed_tasks
                FROM projects p
                ORDER BY p.start_date DESC
            """)
            all_projs_rows = cursor.fetchall()
            project_progress_data = []
            for pid, pname, leader, mgr, end_date, p_status, tot, done in all_projs_rows:
                prog = int((done/tot)*100) if tot > 0 else 0
                project_progress_data.append((pid, pname, leader, mgr, end_date, prog, p_status))
                
                if len(project_progress_data) % 10 == 0:
                    self.root.update_idletasks()

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
        
        # Helper to create styled cards with interactivity
        def create_pm_card(parent_frame, title, value, color, command=None, tooltip_text=None):
            card = Frame(parent_frame, bg=CARD_BG, padx=20, pady=20, cursor="hand2" if command else "arrow")
            
            def on_click(e):
                if command: command()
            
            # Top row: Title + Icon
            top = Frame(card, bg=CARD_BG)
            top.pack(fill=X)
            l_title = Label(top, text=title, font=('Segoe UI', 11), bg=CARD_BG, fg=MUTED_TEXT)
            l_title.pack(side=LEFT)
            
            # Value
            l_val = Label(card, text=value, font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=TEXT_WHITE)
            l_val.pack(anchor=W, pady=(10, 0))
            
            # Bottom bar
            bar = Frame(card, bg=color, height=4)
            bar.pack(fill=X, pady=(15, 0))
            
            # Bind clicks
            if command:
                for w in [card, top, l_title, l_val, bar]:
                    w.bind("<Button-1>", on_click)
            
            # 2. Add Help Tips
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
        
        # --- Incremental UI Rendering for PM Dashboard (Lazy Load) ---
        def _load_pm_lazy():
            if not grid_frame.winfo_exists(): return
            
            # Left Column: Active Projects Detail
            left_col = Frame(grid_frame, bg=CARD_BG, padx=20, pady=20)
            left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
            Label(left_col, text="Company Projects List", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
            
            if not project_progress_data:
                Label(left_col, text="No projects found.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            else:
                for pid, pname, leader, mgr, end_date, prog, status in project_progress_data[:10]: # Limit initial display
                    p_item = Frame(left_col, bg=CARD_BG, pady=10, cursor="hand2")
                    p_item.pack(fill=X)
                    
                    def open_p(p=pid, n=pname): self.show_project_tasks_modal(p, n)
                    
                    # Info Row
                    info = Frame(p_item, bg=CARD_BG); info.pack(fill=X)
                    Label(info, text=pname, font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    s_color = ACCENT_ORANGE
                    if status == "Delayed": s_color = ACCENT_RED
                    elif status == "Completed": s_color = ACCENT_GREEN
                    
                    Label(info, text=status, font=('Segoe UI', 9), bg=CARD_BG, fg=s_color).pack(side=LEFT, padx=10)
                    Label(info, text=f"{prog}%", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(side=RIGHT)
                    
                    sub = Frame(p_item, bg=CARD_BG); sub.pack(fill=X, pady=(2, 5))
                    lead_t = leader if leader else (mgr if mgr else "No Leader")
                    Label(sub, text=f"Lead: {lead_t} | Due: {end_date}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
                    
                    bar_bg = Frame(p_item, bg="#404040", height=8); bar_bg.pack(fill=X)
                    if prog > 0:
                        bar_fg = Frame(bar_bg, bg=ACCENT_GREEN, height=8)
                        bar_fg.place(x=0, y=0, relwidth=prog/100)
                        bar_fg.bind("<Button-1>", lambda e, p=pid, n=pname: open_p(p, n))
                        
                    ttk.Separator(left_col, orient='horizontal').pack(fill=X, pady=5)
                    for w in [p_item, info, sub, bar_bg]: w.bind("<Button-1>", lambda e, p=pid, n=pname: open_p(p, n))

            # Right Column
            right_col = Frame(grid_frame, bg=CONTENT_BG); right_col.pack(side=RIGHT, fill=BOTH, expand=True)
            
            # Overview
            overview_box = Frame(right_col, bg=CARD_BG, padx=20, pady=20, highlightbackground=ACCENT_BLUE, highlightthickness=1)
            overview_box.pack(fill=X, pady=(0, 20))
            Label(overview_box, text="Project Progress Overview", font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 12))
            
            c_frame = Frame(overview_box, bg=CARD_BG); c_frame.pack(fill=X)
            Label(c_frame, text=f"Completed: {completed_projects}", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W)
            Label(c_frame, text=f"Ongoing: {ongoing_projects}", font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=2)
            
            chart_canvas = Canvas(overview_box, bg=CARD_BG, height=110, highlightthickness=0); chart_canvas.pack(fill=X)
            # (Chart drawing code...)
            
            # Activity
            activity_box = Frame(right_col, bg=CARD_BG, padx=20, pady=20); activity_box.pack(fill=X)
            Label(activity_box, text="Recent Activity", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 10))
            for ts, user, action in recent_activity[:5]:
                Label(activity_box, text=f"- {ts} | {user}: {action}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT, wraplength=400).pack(anchor=W, pady=1)

        # Defer loading
        self.root.after(20, _load_pm_lazy)
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

        Label(
            card,
            text=title.upper(),
            font=('Segoe UI', 9, 'bold'),
            bg="#212840",
            fg="#9aa3c2",
        ).pack(anchor=W)

        # Main Value
        val_lbl = Label(
            card,
            text=value,
            font=('Segoe UI', 32, 'bold'),
            bg="#212840",
            fg=color,
        )
        val_lbl.pack(expand=True)

        if on_click:
            for w in [card, val_lbl]:
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
            con.commit()
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
            con.commit()
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
                    c.commit(); c.close()
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
                con.commit()
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
                con.commit()
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
                con.commit()
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
        con.commit()
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
                con.commit()

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

        # Clear existing
        for i in self.dash_task_tree.get_children(): self.dash_task_tree.delete(i)
        for i in self.dash_dead_tree.get_children(): self.dash_dead_tree.delete(i)
        
        # Show "Loading..." placeholder
        self.dash_task_tree.insert("", END, values=("Synchronizing data...", "Connecting to server...", "-"))
        
        def _fetch_and_update():
            # 1. Fetch from Backend (Background)
            backend_tasks = []
            if CURRENT_TOKEN:
                try:
                    all_backend_tasks = api.get_tasks()
                    backend_tasks = [t for t in all_backend_tasks if 
                                   (t.get('assignedTo') == CURRENT_USER_NAME or 
                                    t.get('assignedTo') == CURRENT_USER_EMAIL)]
                except: pass

            # 2. Update UI (Main Thread)
            if self.root.winfo_exists():
                self.root.after(0, lambda: self._complete_emp_refresh(backend_tasks, filter_val))

        threading.Thread(target=_fetch_and_update, daemon=True).start()

    def _complete_emp_refresh(self, backend_tasks, filter_val):
        """Final UI update for Employee Dashboard after background fetch."""
        if not self.dash_task_tree.winfo_exists(): return
        
        # Clear loading msg
        for i in self.dash_task_tree.get_children(): self.dash_task_tree.delete(i)
        
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        # Local SQLite Data
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
        
        query += " ORDER BY t.due_date ASC LIMIT 15"
        cur.execute(query, tuple(params))
        sqlite_rows = cur.fetchall()
        
        combined_active = []
        seen_titles = set()
        today_str = datetime.now().strftime("%Y-%m-%d")

        # Process Backend
        for bt in backend_tasks:
            status = bt.get('status')
            due = bt.get('dueDate', '').split('T')[0] if bt.get('dueDate') else ""
            
            show = False
            if filter_val == "Active" and status not in ('Completed', 'Cancelled'): show = True
            elif filter_val == "Completed" and status == 'Completed': show = True
            elif filter_val == "Pending" and status == 'Pending': show = True
            elif filter_val == "Overdue" and status not in ('Completed', 'Cancelled') and due < today_str: show = True
            elif filter_val == "All": show = True
            
            if show:
                title = bt.get('title', 'Untitled')
                if title not in seen_titles:
                    proj = bt.get('project', {}).get('name', 'N/A') if isinstance(bt.get('project'), dict) else 'N/A'
                    combined_active.append((title, proj, due))
                    seen_titles.add(title)

        # Merge SQLite
        for st in sqlite_rows:
            if st[0] not in seen_titles:
                combined_active.append(st)
                seen_titles.add(st[0])

        combined_active.sort(key=lambda x: x[2] if x[2] else '9999-99-99')

        if combined_active:
            for r in combined_active[:12]:
                self.dash_task_tree.insert("", END, values=r)
        else:
            self.dash_task_tree.insert("", END, values=("No active tasks", "All caught up", "-"))
        
        # Deadlines
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
                tag = 'Safe'
                if r[3] <= 1: tag = 'Urgent'
                elif r[3] <= 3: tag = 'Warning'
                self.dash_dead_tree.insert("", END, values=r[:3], tags=(tag,))
        else:
            self.dash_dead_tree.insert("", END, values=("No upcoming deadlines", "-", "-"))
        
        con.close()


    def sort_emp_tasks(self, col):
        # Store sort state
        if not hasattr(self, "_task_sort_reverse"): self._task_sort_reverse = {}
        rev = self._task_sort_reverse.get(col, False)
        self._task_sort_reverse[col] = not rev

    def sort_emp_tasks(self, col):
        # Store sort state
        if not hasattr(self, "_task_sort_reverse"): self._task_sort_reverse = {}
        rev = self._task_sort_reverse.get(col, False)
        self._task_sort_reverse[col] = not rev
        
        data = [(self.emp_tasks_tree.set(child, col), child) for child in self.emp_tasks_tree.get_children('')]
        
        # Numeric sort for ID and Days Left
        if col in ("ID", "Days Left"):
            def key_func(x):
                try:
                    # Extract number from "X days"
                    val = x[0].split()[0]
                    return int(val)
                except: return 0
            data.sort(key=key_func, reverse=rev)
        else:
            data.sort(reverse=rev)

        for index, (val, child) in enumerate(data):
            self.emp_tasks_tree.move(child, '', index)

    def on_task_click(self, event):
        item = self.emp_tasks_tree.identify_row(event.y)
        if not item: return
        
        # Get task ID from first column
        tid = self.emp_tasks_tree.item(item, "values")[0]
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT title, description, priority, status, due_date FROM tasks WHERE id=?", (tid,))
            task = cur.fetchone()
            con.close()
            
            if task:
                title, desc, prio, status, due = task
                msg = f"Task: {title}\n\nDescription: {desc or 'No description'}\n\nPriority: {prio}\nStatus: {status}\nDue Date: {due}"
                messagebox.showinfo("Task Details", msg)
        except: pass

    def refresh_emp_tasks_tab(self):
        for i in self.emp_tasks_tree.get_children(): self.emp_tasks_tree.delete(i)
        
        # 1. Fetch from Backend API
        backend_tasks = []
        if CURRENT_TOKEN:
            try:
                all_backend_tasks = api.get_tasks()
                # Filter tasks assigned to current user (by name or email)
                backend_tasks = [t for t in all_backend_tasks if t.get('assignedTo') == CURRENT_USER_NAME or t.get('assignedTo') == CURRENT_USER_EMAIL]
            except Exception as e:
                debug_log(f"DEBUG: Error fetching backend tasks: {e}")

        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        query = """
            SELECT t.id, t.title, p.name, t.priority, t.status, t.due_date,
            (strftime('%s', t.due_date) - strftime('%s', 'now')) / 86400 as days_left
            FROM tasks t LEFT JOIN projects p ON t.project_id = p.id
            WHERE t.assigned_to=?
        """
        params = [CURRENT_USER_NAME]
        
        # Filters for SQLite
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
        
        # Combine tasks
        combined_tasks = []
        seen_titles = set()
        
        # Add backend tasks with filters applied
        today = datetime.now().date()
        for bt in backend_tasks:
            title = bt.get('title', 'Untitled')
            project = bt.get('project', {}).get('name', 'N/A') if isinstance(bt.get('project'), dict) else 'N/A'
            priority = bt.get('priority', 'Medium')
            status = bt.get('status', 'Pending')
            due = bt.get('dueDate', 'N/A')
            if due and 'T' in due: due = due.split('T')[0]
            
            # Apply search filter
            if search and (search not in title.lower() and search not in project.lower()):
                continue
            
            # Apply status filter
            if status_filter == "All Active" and status == "Completed":
                continue
            elif status_filter != "All" and status_filter != "All Active" and status != status_filter:
                continue
            
            # Apply priority filter
            if prio_filter != "All" and priority != prio_filter:
                continue

            days_left_val = None
            days_left_text = "N/A"
            if due != 'N/A':
                try:
                    due_date = datetime.strptime(due, "%Y-%m-%d").date()
                    days_left_val = (due_date - today).days
                    days_left_text = f"{days_left_val} days" if days_left_val > 0 else ("Today" if days_left_val == 0 else f"{-days_left_val} days overdue")
                except: pass

            combined_tasks.append({
                'id': f"API-{bt.get('_id', '')[:8]}",
                'title': title,
                'project': project,
                'priority': priority,
                'status': status,
                'due_date': due,
                'days_left_text': days_left_text,
                'days_left_val': days_left_val
            })
            seen_titles.add(title)

        # Add SQLite tasks
        for st in sqlite_tasks:
            if st[1] not in seen_titles:
                combined_tasks.append({
                    'id': str(st[0]),
                    'title': st[1],
                    'project': st[2],
                    'priority': st[3],
                    'status': st[4],
                    'due_date': st[5],
                    'days_left_text': f"{int(st[6])} days" if st[6] is not None and int(st[6]) > 0 else ("Today" if st[6] is not None and int(st[6]) == 0 else (f"{-int(st[6])} days overdue" if st[6] is not None else "N/A")),
                    'days_left_val': int(st[6]) if st[6] is not None else None
                })
                seen_titles.add(st[1])

        # Sort combined list by due date
        combined_tasks.sort(key=lambda x: x['due_date'] if x['due_date'] else '9999-99-99')

        for t in combined_tasks:
            vals = (t['id'], t['title'], t['project'], t['priority'], t['status'], t['due_date'], t['days_left_text'])
            tag = t['status']
            if tag != 'Completed' and t['days_left_val'] is not None and t['days_left_val'] < 0:
                tag = 'Delayed'
            self.emp_tasks_tree.insert("", END, values=vals, tags=(tag,))
            
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



    def refresh_emp_queries(self):
        for i in self.query_tree.get_children(): self.query_tree.delete(i)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            cur.execute("SELECT id, subject, status, response, created_at FROM queries WHERE user_name=? ORDER BY created_at DESC", (CURRENT_USER_NAME,))
            for r in cur.fetchall(): self.query_tree.insert("", END, values=r)
            con.close()
        except: pass

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
                con_inner.commit()
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
                con.commit()
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
        stat_row.pack(fill=X, pady=(0, 5))

        def build_stat_tile(parent, icon, accent, title, value_text):
            tile = Frame(parent, bg=HEADER_BG, padx=18, pady=16, highlightbackground=accent, highlightthickness=1)
            
            top_r = Frame(tile, bg=HEADER_BG)
            top_r.pack(fill=X)
            Label(top_r, text=icon, font=('Segoe UI', 12), bg=HEADER_BG).pack(side=LEFT, padx=(0, 8))
            Label(top_r, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack(side=LEFT)
            
            value_label = Label(tile, text=value_text, font=('Segoe UI', 18, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE)
            value_label.pack(anchor=W, pady=(10, 0))
            return tile, value_label

        total_tile, self.projects_total_chip = build_stat_tile(stat_row, "📊", ACCENT_BLUE, "Total Projects", "0")
        total_tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        ongoing_tile, self.projects_ongoing_chip = build_stat_tile(stat_row, "🏗️", ACCENT_GREEN, "Ongoing", "0")
        ongoing_tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        delayed_tile, self.projects_delayed_chip = build_stat_tile(stat_row, "⚠️", ACCENT_RED, "Delayed", "0")
        delayed_tile.pack(side=LEFT, fill=BOTH, expand=True)

        if is_narrow:
            # Adjust hero layout for narrow screens
            hero_left.pack_configure(side=TOP)
            btn_frame.pack_configure(side=TOP, anchor=W, padx=0, pady=(10, 0))
            stat_row.pack_configure(pady=(10, 5))

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
            make_action_btn(btn_frame, "👁 Details", ACCENT_BLUE, lambda: self.on_project_double_click(None)).pack(side=LEFT, padx=6)
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
        table_header.pack(fill=X)
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
            table_header.pack_configure(pady=6)
            Label(table_header, text="Double-click a row for breakdown", font=('Segoe UI', 8),
                  bg=CARD_BG, fg=MUTED_TEXT).pack(side=TOP, anchor=W, pady=(5,0))
        else:
            Label(table_header, text="Double-click a row for full breakdown", font=('Segoe UI', 9),
                  bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)

        divider = Frame(tree_frame, bg=BORDER_COLOR, height=1)
        divider.pack(fill=X)

        table_wrap = Frame(tree_frame, bg=CARD_BG)
        table_wrap.pack(fill=BOTH, expand=True)

        scrolly = ttk.Scrollbar(table_wrap, orient=VERTICAL)
        scrolly.pack(side=RIGHT, fill=Y)

        cols = ("ID", "Project Name", "Team Leader", "Priority", "Status", "Health", "Progress", "Start Date", "Deadline", "Days Left")
        self.proj_tree = ttk.Treeview(table_wrap, style="Projects.Treeview", columns=cols, show='headings', yscrollcommand=scrolly.set, selectmode="browse")
        scrolly.config(command=self.proj_tree.yview)

        for col in cols:
            self.proj_tree.heading(col, text=col, command=lambda c=col: self.sort_projects_tree(c))

        self.proj_tree.column("ID", width=60, anchor=CENTER)
        self.proj_tree.column("Project Name", width=250)
        self.proj_tree.column("Team Leader", width=160)
        self.proj_tree.column("Priority", width=100, anchor=CENTER)
        self.proj_tree.column("Status", width=110, anchor=CENTER)
        self.proj_tree.column("Health", width=120, anchor=CENTER)
        self.proj_tree.column("Progress", width=160, anchor=CENTER)
        self.proj_tree.column("Start Date", width=110, anchor=CENTER)
        self.proj_tree.column("Deadline", width=110, anchor=CENTER)
        self.proj_tree.column("Days Left", width=110, anchor=CENTER)

        self.proj_tree.tag_configure("status_completed", background=HEADER_BG, foreground=ACCENT_GREEN)
        self.proj_tree.tag_configure("status_ongoing", background=HEADER_BG, foreground=ACCENT_BLUE)
        self.proj_tree.tag_configure("status_delayed", background=HEADER_BG, foreground=ACCENT_RED)
        self.proj_tree.tag_configure("status_default", background=HEADER_BG, foreground=TEXT_WHITE)

        self.proj_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.proj_tree.bind("<Double-1>", self.on_project_double_click)
        self.refresh_projects()
        self._attach_tree_hover(self.proj_tree)

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
                try:
                    return datetime.strptime(v, "%Y-%m-%d")
                except:
                    return datetime.max
            if column == "Priority":
                return {"High": 3, "Medium": 2, "Low": 1}.get(str(v), 0)
            return str(v).lower()

        rows = [(self.proj_tree.set(i, column), i) for i in self.proj_tree.get_children("")]
        rows.sort(key=lambda x: parse_value(x[0]), reverse=reverse)
        for idx, (_, item_id) in enumerate(rows):
            self.proj_tree.move(item_id, "", idx)

    def refresh_projects(self, reset_page=False):
        for i in self.proj_tree.get_children():
            self.proj_tree.delete(i)

        query = "SELECT id, name, team_leader, status, start_date, end_date, COALESCE(priority, 'Medium') FROM projects WHERE 1=1"
        params = []

        role = CURRENT_USER_ROLE.lower()
        if role == 'team leader':
            query += " AND team_leader LIKE ?"
            params.append(f"%{CURRENT_USER_NAME}%")

        status = self.filter_var.get()
        if status != "All":
            query += " AND status=?"
            params.append(status)

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
            delayed_projects = 0

            for pid, name, leader, status, start_date, deadline, priority in rows:
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=?", (pid,))
                total = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE project_id=? AND status='Completed'", (pid,))
                comp = cursor.fetchone()[0]
                prog = int((comp/total)*100) if total > 0 else 0
                
                # High-fidelity block progress bar
                bar_len = 10
                filled = int((prog / 100) * bar_len)
                progress_bar = f"{'▰' * filled}{'▱' * (bar_len - filled)} {prog}%"

                days_left = "N/A"
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
                            days_left = "Overdue"
                            overdue = True
                        elif diff <= 3:
                            days_left = "Due Soon"
                        else:
                            days_left = "On Track"
                    except:
                        pass

                health = "Healthy"
                health_icon = "🟢"
                tag = "status_default"
                
                status_display = status
                if status == "Delayed" or overdue:
                    health = "Delayed"
                    health_icon = "🔴"
                    status_display = f"⚡ {status}"
                    tag = "status_delayed"
                    delayed_projects += 1
                elif status == "Ongoing":
                    health = "At Risk" if days_left == "Due Soon" else "Healthy"
                    health_icon = "🟡" if days_left == "Due Soon" else "🟢"
                    status_display = f"🏗️ {status}"
                    tag = "status_ongoing"
                elif status == "Completed":
                    health = "Healthy"
                    health_icon = "✅"
                    status_display = f"✨ {status}"
                    tag = "status_completed"

                self.proj_tree.insert(
                    "", END,
                    values=(pid, name, leader or "Unassigned", priority, status_display, f"{health_icon} {health}", progress_bar, start_date or "N/A", deadline or "N/A", days_left),
                    tags=(tag,)
                )

            if hasattr(self, "projects_total_chip"):
                self.projects_total_chip.config(text=f" Total: {total_projects} ")
            if hasattr(self, "projects_ongoing_chip"):
                self.projects_ongoing_chip.config(text=f" Ongoing: {ongoing_projects} ")
            if hasattr(self, "projects_delayed_chip"):
                self.projects_delayed_chip.config(text=f" Delayed: {delayed_projects} ")

            con.close()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load projects: {e}")

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
                        con2.commit(); con2.close()
                        refresh_ms(); top.destroy()
                    except Exception as e:
                        messagebox.showerror("Error", str(e))
                Button(f, text="Add", bg=ACCENT_GREEN, fg=WHITE, relief=FLAT, command=save).pack(pady=10, fill=X)
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

        chip_row = Frame(hero, bg=modal_panel)
        chip_row.pack(anchor=W, pady=(14, 0))
        Label(chip_row, text=" Project Setup ", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(chip_row, text=" Delivery Ready ", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(chip_row, text=" Timeline Driven ", bg=ACCENT_ORANGE, fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT)

        insights = Frame(hero, bg=modal_panel)
        insights.pack(fill=X, pady=(16, 0))
        for idx, (title, value, accent) in enumerate((
            ("Lead Type", "Single Team Leader", ACCENT_BLUE),
            ("Default Status", "Ongoing", ACCENT_GREEN),
            ("Focus", "Clarity + Ownership", PRIMARY_BG),
        )):
            tile = Frame(insights, bg="#253244", padx=14, pady=12, highlightbackground=accent, highlightthickness=1)
            tile.pack(side=LEFT, fill=BOTH, expand=True, padx=(0 if idx == 0 else 10, 0))
            Label(tile, text=title.upper(), bg="#253244", fg=MUTED_TEXT, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
            Label(tile, text=value, bg="#253244", fg=TEXT_WHITE, font=('Segoe UI', 12, 'bold')).pack(anchor=W, pady=(6, 0))

        next_step = StringVar(value="planner")
        next_step_panel = Frame(card, bg=modal_panel, padx=18, pady=16, highlightbackground=modal_border, highlightthickness=1)
        next_step_panel.pack(fill=X, pady=(0, 18))
        Label(next_step_panel, text="After Create", bg=modal_panel, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W)
        Label(next_step_panel, text="Choose what should happen immediately after the project is created.",
              bg=modal_panel, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(4, 12))
        next_step_cards = Frame(next_step_panel, bg=modal_panel)
        next_step_cards.pack(fill=X)

        def add_next_step_card(parent, value, title, subtitle, accent):
            shell_card = Frame(parent, bg="#253244", padx=14, pady=12, highlightbackground=accent, highlightthickness=1, cursor="hand2")
            shell_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0 if not parent.winfo_children() else 8, 0))
            Label(shell_card, text=title.upper(), bg="#253244", fg=MUTED_TEXT, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
            Label(shell_card, text=title, bg="#253244", fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W, pady=(6, 2))
            Label(shell_card, text=subtitle, bg="#253244", fg=MUTED_TEXT, font=('Segoe UI', 9), wraplength=220, justify=LEFT).pack(anchor=W)

            def _pick(_e=None):
                next_step.set(value)

            shell_card.bind("<Button-1>", _pick)
            for child in shell_card.winfo_children():
                child.bind("<Button-1>", _pick)
            return shell_card

        add_next_step_card(next_step_cards, "planner", "Open Task Planner", "Review the project and assign tasks manually in the project task view.", ACCENT_BLUE)
        add_next_step_card(next_step_cards, "auto_plan", "Auto-Plan Starter Tasks", "Generate suggested starter tasks based on the project name and timeline.", ACCENT_GREEN)
        add_next_step_card(next_step_cards, "done", "Just Create Project", "Save the project now and assign tasks later from the Projects or Tasks page.", ACCENT_ORANGE)

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
                con.commit()
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
                self.refresh_current_page()
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
            con.commit()
            con.close()
            self.refresh_current_page()
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
        
        cursor.execute("SELECT name FROM employee")
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
                con.commit()
                con.close()
                self.refresh_projects()
                t.destroy()
                messagebox.showinfo("Success", "Project Updated")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(t, text="Update Project", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(pady=20, fill=X, padx=40)

    def load_members(self):
        # Header Frame
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=30)
        Label(h, text="Team Members", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Action Buttons
        btn_frame = Frame(h, bg=CONTENT_BG)
        btn_frame.pack(side=RIGHT)
        
        Button(btn_frame, text="View Profile", bg=PRIMARY_BG, fg=PRIMARY_TEXT, font=('Segoe UI', 10, 'bold'), 
               relief=FLAT, command=self.view_member_profile).pack(side=RIGHT, padx=5)
        if CURRENT_USER_ROLE.lower() == 'team leader':
            Button(btn_frame, text="+ Add Team Member", bg=ACCENT_GREEN, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'),
                   relief=FLAT, command=self.add_member_to_my_team_modal).pack(side=RIGHT, padx=5)
        
        # Only show Add Member if Admin or PM
        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager']:
            Button(btn_frame, text="+ Add Member", bg="#27ae60", fg="white", font=('Segoe UI', 10, 'bold'), 
                   relief=FLAT, command=self.add_member_modal).pack(side=RIGHT, padx=5)
            Button(btn_frame, text="Assign Team Leader", bg=ACCENT_PURPLE, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'),
                   relief=FLAT, command=self.assign_tl_modal).pack(side=RIGHT, padx=5)
        
        # --- Search & Filter ---
        search_frame = Frame(self.content_area, bg=CONTENT_BG)
        search_frame.pack(fill=X, padx=30, pady=(0, 10))
        
        Label(search_frame, text="Search Member:", bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=(0, 5))
        self.mem_search_var = StringVar()
        self.mem_search_var.trace("w", lambda *args: self.refresh_members())
        Entry(search_frame, textvariable=self.mem_search_var, width=30, font=('Segoe UI', 10)).pack(side=LEFT)
        
        Label(search_frame, text="Status:", bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=(20, 5))
        self.mem_status_filter = ttk.Combobox(search_frame, values=["All", "Active", "On Leave"], state="readonly", width=15)
        self.mem_status_filter.set("All")
        self.mem_status_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh_members())
        self.mem_status_filter.pack(side=LEFT)
        
        tree_frame = Frame(self.content_area, bg=CARD_BG)
        tree_frame.pack(fill=BOTH, expand=True, padx=30, pady=(0, 30))
        
        # Extended columns include Team Leader link
        cols = ("ID", "Name", "Department", "Role", "Team Leader", "Tasks", "Workload", "Performance", "Last Active", "Status", "Actions")
        self.mem_tree = ttk.Treeview(tree_frame, columns=cols, show='headings')
        for col in cols: 
            self.mem_tree.heading(col, text=col)
            self.mem_tree.column(col, width=100, anchor=CENTER)
        
        self.mem_tree.column("ID", width=50)
        self.mem_tree.column("Name", width=180, anchor=W)
        self.mem_tree.column("Team Leader", width=140, anchor=W)
        self.mem_tree.column("Tasks", width=80, anchor=CENTER)
        self.mem_tree.column("Workload", width=100)
        self.mem_tree.column("Performance", width=140)
        self.mem_tree.column("Last Active", width=110)
        self.mem_tree.column("Actions", width=100)
        
        self.mem_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrolly = Scrollbar(tree_frame, orient=VERTICAL, command=self.mem_tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        self.mem_tree.configure(yscrollcommand=scrolly.set)
        
        # Row-wise Actions
        self.mem_tree.bind("<Double-1>", lambda e: self.view_member_profile())
        self.mem_tree.bind("<ButtonRelease-1>", self.on_member_click)
        
        self.refresh_members()
        # Hover effect
        self._attach_tree_hover(self.mem_tree)

    def on_member_click(self, event):
        item_id = self.mem_tree.identify_row(event.y)
        column = self.mem_tree.identify_column(event.x)
        
        # Column #11 is the 'Actions' column in the extended members list
        if column == "#11" and item_id: 
            item = self.mem_tree.item(item_id)
            # The 'Name' is at index 1 in values
            name = str(item['values'][1]).replace("👤 ", "").strip()
            
            # Don't allow updating self via Member list to avoid redundancy with Header Profile button
            if name == CURRENT_USER_NAME:
                messagebox.showinfo("Info", "Please use the 'Update Profile' button in the top header to manage your own account.")
                return
            self.update_member_modal()

    def refresh_members(self):
        for item in self.mem_tree.get_children(): self.mem_tree.delete(item)
        
        search_txt = self.mem_search_var.get().lower() if hasattr(self, 'mem_search_var') else ""
        status_filter = self.mem_status_filter.get() if hasattr(self, 'mem_status_filter') else "All"
        
        def _fetch_and_render_members():
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # Optimized query: Single pass for tasks, completion rate, and last activity
            query = """
                SELECT 
                    e.id, 
                    e.name, 
                    e.department, 
                    e.role,
                    (SELECT COUNT(*) FROM tasks t WHERE t.assigned_to = e.name) as total_tasks,
                    (SELECT COUNT(*) FROM tasks t WHERE t.assigned_to = e.name AND t.status != 'Completed') as active_tasks,
                    (SELECT 
                        CASE 
                            WHEN COUNT(*) = 0 THEN '0%' 
                            ELSE ROUND((SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)), 0) || '%' 
                        END 
                     FROM tasks t WHERE t.assigned_to = e.name) as completion_rate,
                    e.reporting_manager,
                    (SELECT MAX(date) FROM attendance WHERE employee_name=e.name OR name=e.name) as last_att,
                    (SELECT MAX(date(COALESCE(completed_date, created_date, due_date))) FROM tasks WHERE assigned_to=e.name) as last_task
                FROM employee e
            """
            
            role = CURRENT_USER_ROLE.lower()
            if role == 'team leader':
                query += f""" WHERE (e.reporting_manager = '{CURRENT_USER_NAME}' OR e.name IN (
                    SELECT DISTINCT assigned_to FROM tasks 
                    WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE '%{CURRENT_USER_NAME}%')
                )) AND e.name != '{CURRENT_USER_NAME}' AND e.role NOT IN ('Team Leader', 'Project Manager', 'Admin') """
            
            cur.execute(query)
            rows = cur.fetchall()
            con.close()
            
            # Switch back to main thread for UI
            if self.root.winfo_exists():
                self.root.after(0, lambda: self._populate_members_tree(rows, search_txt, status_filter))

        threading.Thread(target=_fetch_and_render_members, daemon=True).start()

    def _populate_members_tree(self, rows, search_txt, status_filter):
        """UI completion for member list."""
        if not self.mem_tree.winfo_exists(): return
        
        for row in rows:
            name = row[1]; dept = row[2]; emp_role = row[3]
            total_tasks = row[4] or 0; workload_val = row[5] or 0
            completion = row[6]; tl_name = row[7] or "Unlinked"
            
            # Workload indicator
            if workload_val > 5: workload = f"High ({workload_val})"
            elif workload_val > 2: workload = f"Medium ({workload_val})"
            else: workload = f"Low ({workload_val})"
            
            try: pct = int(str(completion).replace('%',''))
            except: pct = 0
            filled = max(0, min(10, pct // 10))
            perf_str = f"{'█'*filled}{'░'*(10-filled)} {pct}%"
            
            # Last active (attendance or task) - using pre-fetched columns
            a = row[8]; b = row[9]
            cands = [d for d in [a, b] if d]
            last_active = max(cands) if cands else "N/A"
            
            status = "Active"
            if status_filter != "All" and status != status_filter: continue
                
            content = f"{name} {dept} {emp_role}".lower()
            if search_txt and search_txt not in content: continue
            
            display_name = f"👤 {name}"
            action_label = "Edit" if name != CURRENT_USER_NAME else ""
            self.mem_tree.insert("", END, values=(row[0], display_name, dept, emp_role, tl_name, total_tasks, workload, perf_str, last_active, status, action_label))

    def view_member_profile(self):
        selected = self.mem_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a member to view profile.")
            return
            
        item = self.mem_tree.item(selected[0])
        emp_id = item['values'][0]
        emp_name = item['values'][1]
        
        t = Toplevel(self.root)
        t.title(f"Member Profile - {emp_name}")
        t.geometry("600x700")
        t.minsize(510, 595)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        # Center
        x = int((self.root.winfo_screenwidth()/2) - (600/2))
        y = int((self.root.winfo_screenheight()/2) - (700/2))
        t.geometry(f"600x700+{x}+{y}")
        
        # Header
        header = Frame(t, bg=PRIMARY_BG, height=150)
        header.pack(fill=X)
        header.pack_propagate(False)
        
        Label(header, text=emp_name, font=('Segoe UI', 24, 'bold'), bg=PRIMARY_BG, fg=PRIMARY_TEXT).pack(pady=(40, 5))
        Label(header, text=item['values'][3], font=('Segoe UI', 12), bg=PRIMARY_BG, fg=PRIMARY_TEXT).pack()
        
        body = Frame(t, bg=CONTENT_BG, padx=30, pady=20)
        body.pack(fill=BOTH, expand=True)
        
        # Info Grid
        info_frame = LabelFrame(body, text=" Basic Information ", font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE, padx=20, pady=20)
        info_frame.pack(fill=X, pady=10)
        
        fields = [
            ("Department:", item['values'][2]),
            ("Workload:", f"{item['values'][4]} Active Tasks"),
            ("Performance:", item['values'][5]),
            ("Status:", item['values'][6])
        ]
        
        for i, (lbl, val) in enumerate(fields):
            Label(info_frame, text=lbl, font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).grid(row=i, column=0, sticky=W, pady=5)
            Label(info_frame, text=val, font=('Segoe UI', 10), bg=CONTENT_BG, fg=TEXT_WHITE).grid(row=i, column=1, sticky=W, padx=20, pady=5)
            
        # Recent Tasks
        task_frame = LabelFrame(body, text=" Recent Assigned Tasks ", font=('Segoe UI', 10, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE, padx=20, pady=20)
        task_frame.pack(fill=BOTH, expand=True, pady=10)
        
        task_tree = ttk.Treeview(task_frame, columns=("Task", "Status", "Deadline"), show='headings', height=8)
        task_tree.heading("Task", text="Task Name")
        task_tree.heading("Status", text="Status")
        task_tree.heading("Deadline", text="Deadline")
        task_tree.column("Task", width=200)
        task_tree.column("Status", width=100)
        task_tree.column("Deadline", width=100)
        task_tree.pack(fill=BOTH, expand=True)
        
        # Load tasks
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT title, status, deadline FROM tasks WHERE assigned_to = ? ORDER BY deadline ASC LIMIT 10", (emp_name,))
            for row in cur.fetchall():
                task_tree.insert("", END, values=row)
            con.close()
        except:
            pass
            
        Button(body, text="Close", command=t.destroy, bg=PRIMARY_BG, fg=PRIMARY_TEXT, font=('Segoe UI', 10, 'bold'), relief=FLAT).pack(pady=10)

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
            con2.commit()
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
        cur.execute("SELECT name FROM employee WHERE role IN ('Team Member','Senior Employee')")
        emp_names = [r[0] for r in cur.fetchall()]
        cur.execute("SELECT name FROM employee WHERE role='Team Leader'")
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
            con2.commit()
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
        hero.pack(fill=X, pady=(0, 18))

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

        form = Frame(card, bg=CARD_BG)
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
        entries["Department"] = make_entry(form, "Department", 2, 0)

        role_holder = make_field(form, "Role", 2, 1)
        role_wrap = Frame(role_holder, bg="#253244", highlightbackground=BORDER_COLOR, highlightthickness=1)
        role_wrap.pack(fill=X)
        c_role = ttk.Combobox(role_wrap, values=["Team Member", "Team Leader", "Senior Employee", "Project Manager"], state="readonly", font=('Segoe UI', 11))
        c_role.set("Team Member")
        c_role.pack(fill=X, padx=10, pady=10, ipady=6)
        entries["Role"] = c_role

        helper = Frame(card, bg=HEADER_BG, padx=18, pady=16, highlightbackground=BORDER_COLOR, highlightthickness=1)
        helper.pack(fill=X, pady=(18, 0))
        Label(helper, text="Account Setup Note", bg=HEADER_BG, fg=ACCENT_ORANGE, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
        Label(helper, text="The member's initial password will be set from the mobile number, so make sure it is entered correctly.",
              bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 9), wraplength=760, justify=LEFT).pack(anchor=W, pady=(4, 0))
            
        def save():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                fname = entries["First Name"].get().strip()
                lname = entries["Last Name"].get().strip()
                mobile = entries["Mobile"].get().strip()
                email = entries["Email"].get().strip()
                department = entries["Department"].get().strip()
                role = entries["Role"].get().strip()

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
                con.commit()
                con.close()
                self.refresh_members()
                t.destroy()
                messagebox.showinfo("Success", f"{full_name} added successfully.", parent=self.root)
            except Exception as e:
                messagebox.showerror("Error", str(e))

        footer = Frame(card, bg=HEADER_BG, padx=18, pady=16, highlightbackground=BORDER_COLOR, highlightthickness=1)
        footer.pack(fill=X, pady=(18, 0))
        foot_info = Frame(footer, bg=HEADER_BG)
        foot_info.pack(side=LEFT, fill=X, expand=True)
        Label(foot_info, text="Member Creation Tip", bg=HEADER_BG, fg=ACCENT_GREEN, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
        Label(foot_info, text="Use the correct role from the start so dashboard access and permissions stay accurate.",
              bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(4, 0))
        action_row = Frame(footer, bg=HEADER_BG)
        action_row.pack(side=RIGHT)
        Button(action_row, text="Cancel", command=t.destroy, bg=ACCENT_HOVER, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'),
               relief=FLAT, padx=18, pady=10, activebackground=PRIMARY_RED_DARK, activeforeground=WHITE, cursor='hand2').pack(side=LEFT, padx=(0, 8))
        Button(action_row, text="Save Member", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'),
               relief=FLAT, padx=24, pady=10, activebackground=PRIMARY_RED_DARK, activeforeground=WHITE, cursor='hand2').pack(side=LEFT)

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
            con.commit()
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
                con.commit()
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
                    con.commit()
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
                    con.commit()
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
        is_narrow = self.root.winfo_width() < 1000

        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=px, pady=30)
        Label(h, text="Project Status Overview", font=('Segoe UI', 22, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)

        # Status Filter
        filter_box = Frame(h, bg=CONTENT_BG)
        filter_box.pack(side=RIGHT)
        Label(filter_box, text="Filter:", bg=CONTENT_BG, fg=MUTED_TEXT, font=('Segoe UI', 10, 'bold')).pack(side=LEFT, padx=(0, 6))
        if not hasattr(self, "pm_status_filter"):
            self.pm_status_filter = StringVar(value="All")
        cb = ttk.Combobox(filter_box, textvariable=self.pm_status_filter, values=["All", "Ongoing", "Completed", "Delayed"], state="readonly", width=12)
        cb.pack(side=LEFT, padx=(0, 12))
        cb.bind("<<ComboboxSelected>>", lambda e: self.load_project_status_panel())

        list_container = Frame(self.content_area, bg=CONTENT_BG, padx=px)
        list_container.pack(fill=BOTH, expand=True, pady=(0, 30))

        canvas = Canvas(list_container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    canvas.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")
            except Exception:
                pass
        # FIX 6b: scoped bind to canvas only, not bind_all
        def _bind_mousewheel(event):
            try:
                canvas.bind("<MouseWheel>", _on_mousewheel)
            except Exception:
                pass
        def _unbind_mousewheel(event):
            try:
                canvas.unbind("<MouseWheel>")
            except Exception:
                pass

        list_container.bind("<Enter>", _bind_mousewheel)
        list_container.bind("<Leave>", _unbind_mousewheel)
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)

        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        q = "SELECT id, name, team_leader, status, start_date, end_date FROM projects"
        params = []
        if self.pm_status_filter.get() != "All":
            q += " WHERE status=?"
            params.append(self.pm_status_filter.get())
        cursor.execute(q, params)
        projects = cursor.fetchall()

        task_counts = {}
        try:
            cursor.execute("""
                SELECT project_id, COUNT(*), SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END)
                FROM tasks GROUP BY project_id
            """)
            for pid, total, completed in cursor.fetchall():
                task_counts[pid] = (total or 0, completed or 0)
        except:
            pass
        project_assignees = {}
        try:
            cursor.execute("""
                SELECT
                    t.project_id,
                    GROUP_CONCAT(
                        DISTINCT COALESCE(
                            NULLIF(TRIM(t.assigned_to), ''),
                            NULLIF(TRIM(p.default_assignee), ''),
                            NULLIF(TRIM(p.team_leader), ''),
                            'Unassigned'
                        )
                    )
                FROM tasks t
                LEFT JOIN projects p ON t.project_id = p.id
                GROUP BY t.project_id
            """)
            for project_id, assignees_csv in cursor.fetchall():
                names = [name.strip() for name in str(assignees_csv or "").split(",") if name and name.strip()]
                if names:
                    project_assignees[project_id] = names
        except:
            pass

        columns = 1 if is_narrow else 2
        for c in range(columns):
            scrollable_frame.grid_columnconfigure(c, weight=1)

        if not projects:
            Label(scrollable_frame, text="No projects found.", bg=CONTENT_BG, fg=MUTED_TEXT, font=('Segoe UI', 12)).grid(row=0, column=0, columnspan=2, pady=20, sticky="w")

        today = datetime.now().date()
        for idx, (pid, pname, leader, status, start_date, end_date) in enumerate(projects):
            total, completed = task_counts.get(pid, (0, 0))
            prog = int((completed / total) * 100) if total > 0 else 0
            assignees = project_assignees.get(pid, [])
            if len(assignees) == 1:
                assignee_text = f"Assigned To: {assignees[0]}"
            elif len(assignees) > 1:
                assignee_text = f"Assigned To: {assignees[0]} +{len(assignees) - 1} more"
            else:
                fallback_assignee = leader or "Unassigned"
                assignee_text = f"Assigned To: {fallback_assignee}"

            overdue = False
            days_text = "N/A"
            if end_date:
                try:
                    d = datetime.strptime(end_date, "%Y-%m-%d").date()
                    diff = (d - today).days
                    if diff < 0:
                        overdue = True
                        days_text = f"{abs(diff)} day(s) overdue"
                    else:
                        days_text = f"{diff} day(s) remaining"
                except:
                    days_text = "N/A"

            display_status = status
            status_color = ACCENT_ORANGE
            if display_status == 'Completed':
                status_color = ACCENT_GREEN
            elif display_status == 'Delayed' or overdue:
                status_color = ACCENT_RED
                display_status = 'Delayed'

            card = Frame(scrollable_frame, bg=CARD_BG, pady=20, padx=24, highlightbackground=status_color if overdue else BORDER_COLOR, highlightthickness=1)
            card.grid(row=idx // columns, column=idx % columns, padx=10, pady=10, sticky="nsew")

            def on_click(e, p=pid, n=pname):
                self.show_project_tasks_modal(p, n)

            def on_enter(e, c=card):
                c.configure(bg="#2a2a32")
                for w in c.winfo_children():
                    try: 
                        if w.cget('bg') == CARD_BG: w.configure(bg="#2a2a32")
                    except: pass
            
            def on_leave(e, c=card):
                c.configure(bg=CARD_BG)
                for w in c.winfo_children():
                    try:
                        if w.cget('bg') == "#2a2a32": w.configure(bg=CARD_BG)
                    except: pass

            card.bind("<Button-1>", on_click)
            card.bind("<Enter>", on_enter)
            card.bind("<Leave>", on_leave)

            top = Frame(card, bg=CARD_BG)
            top.pack(fill=X)
            top.bind("<Button-1>", on_click)

            Label(top, text=pname, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
            Label(top, text=display_status, font=('Segoe UI', 10, 'bold'), bg=status_color, fg=TEXT_WHITE, padx=8, pady=2).pack(side=RIGHT)

            mid = Frame(card, bg=CARD_BG)
            mid.pack(fill=X, pady=(6, 8))
            leader_txt = f"Leader: {leader}" if leader else "Leader: Unassigned"
            Label(mid, text=leader_txt, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(mid, text=f"Workload: {completed}/{total}", font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=RIGHT)

            assignee_row = Frame(card, bg=CARD_BG)
            assignee_row.pack(fill=X, pady=(0, 8))
            Label(assignee_row, text=assignee_text, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(side=LEFT)

            meta = Frame(card, bg=CARD_BG)
            meta.pack(fill=X, pady=(0, 8))
            Label(meta, text=f"Start: {start_date or 'N/A'}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(meta, text=f"Deadline: {end_date or 'N/A'}", font=('Segoe UI', 9), bg=CARD_BG, fg=ACCENT_RED if overdue else MUTED_TEXT).pack(side=LEFT, padx=16)
            Label(meta, text=days_text, font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=ACCENT_RED if overdue else ACCENT_GREEN).pack(side=RIGHT)

            bar_bg = Frame(card, bg="#404040", height=8)
            bar_bg.pack(fill=X)
            if prog > 0:
                f_prog = Frame(bar_bg, bg=ACCENT_BLUE, height=8)
                f_prog.place(x=0, y=0, relwidth=prog / 100)

            Label(card, text=f"Progress: {prog}%", font=('Segoe UI', 9), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=E, pady=(3, 0))

            for w in (top, mid, assignee_row, meta, bar_bg):
                w.bind("<Button-1>", on_click)

        con.close()

    def show_project_tasks_modal(self, pid, pname):
        try:
            t = Toplevel(self.root)
            t.title(f"Project Details: {pname}")
            t.geometry("900x700")
            t.minsize(765, 595)
            t.resizable(True, True)
            t.config(bg=CONTENT_BG)
            
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
                        con2.commit(); con2.close()
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
                        con3.commit(); con3.close()
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
                con.close()
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
                con.commit(); con.close()
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

        # FIX 5b: reuse Style singleton, remove theme_use() call (already set in apply_theme)
        style = ttk.Style()
        style.configure(
            "Task.Treeview",
            background=HEADER_BG,
            foreground=TEXT_WHITE,
            fieldbackground=HEADER_BG,
            rowheight=40,
            borderwidth=0,
            relief="flat",
            font=('Segoe UI', 10)
        )
        style.configure(
            "Task.Treeview.Heading",
            background="#1f2937",
            foreground=TEXT_WHITE,
            font=('Segoe UI', 10, 'bold'),
            borderwidth=0,
            relief="flat",
            padding=(12, 12)
        )
        style.map(
            "Task.Treeview",
            background=[('selected', PRIMARY_BG)],
            foreground=[('selected', WHITE)]
        )
        style.map(
            "Task.Treeview.Heading",
            background=[('active', "#273548")]
        )

        h = Frame(self.content_area, bg=CARD_BG, padx=28, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
        h.pack(fill=X, padx=30, pady=(24, 18))
        title_box = Frame(h, bg=CARD_BG)
        title_box.pack(side=LEFT, fill=X, expand=True)
        Label(title_box, text="Task Management", font=('Segoe UI', 28, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Review assignments, update delivery status, and keep work moving with fewer clicks.",
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 0))
        
        btn_frame = Frame(h, bg=CARD_BG)
        btn_frame.pack(side=RIGHT)

        def make_header_btn(parent, text, bg, cmd):
            return Button(
                parent,
                text=text,
                bg=bg,
                fg=TEXT_WHITE,
                font=('Segoe UI', 10, 'bold'),
                relief=FLAT,
                bd=0,
                padx=18,
                pady=12,
                activebackground=ACCENT_HOVER,
                activeforeground=WHITE,
                command=cmd,
                cursor='hand2'
            )
        
        make_header_btn(btn_frame, "Update Status", ACCENT_GREEN, self.update_task_modal).pack(side=LEFT, padx=6)
        
        # Allow TL to delete tasks
        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager', 'team leader']:
            make_header_btn(btn_frame, "Create New Task", ACCENT_BLUE, self.add_task_modal).pack(side=LEFT, padx=6)
            make_header_btn(btn_frame, "Delete Task", PRIMARY_BG, self.delete_task).pack(side=LEFT, padx=6)
        
        self.task_search_var = StringVar(value="")
        self.task_filter_var = StringVar(value="All")
        self.task_prio_filter = StringVar(value="All")
        self.task_member_filter = StringVar(value="All")

        action_band = Frame(self.content_area, bg=CARD_BG, padx=24, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
        action_band.pack(fill=X, padx=30, pady=(0, 16))
        band_info = Frame(action_band, bg=CARD_BG)
        band_info.pack(side=LEFT, fill=X, expand=True)
        Label(band_info, text="Task Actions", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(band_info, text="A simplified workspace focused on action instead of filters.",
              font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))

        if CURRENT_USER_ROLE.lower() in ['admin', 'project manager', 'team leader']:
            action_strip = Frame(action_band, bg=CARD_BG)
            action_strip.pack(side=RIGHT)
            def bulk_btn(text, bg, cmd):
                return Button(action_strip, text=text, bg=bg, fg=WHITE, font=('Segoe UI', 9, 'bold'),
                              relief=FLAT, bd=0, padx=14, pady=9, activebackground=ACCENT_HOVER,
                              activeforeground=WHITE, command=cmd, cursor='hand2')

            bulk_btn("Assign", ACCENT_BLUE, self.reassign_task_modal).pack(side=RIGHT, padx=5)
            bulk_btn("Unassign", "#475569", self.unassign_selected_tasks).pack(side=RIGHT, padx=5)
            bulk_btn("Mark Urgent", ACCENT_RED, self.mark_task_urgent).pack(side=RIGHT, padx=5)

        tree_frame = Frame(self.content_area, bg=CARD_BG, padx=2, pady=2, highlightbackground=BORDER_COLOR, highlightthickness=1)
        tree_frame.pack(fill=BOTH, expand=True, padx=30, pady=(0, 30))

        table_header = Frame(tree_frame, bg=CARD_BG, padx=20, pady=14)
        table_header.pack(fill=X)
        Label(table_header, text="Task Portfolio", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(table_header, text="Double-click a row to update status, comments, and attachments.",
              font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT).pack(side=RIGHT)

        divider = Frame(tree_frame, bg=BORDER_COLOR, height=1)
        divider.pack(fill=X)

        table_wrap = Frame(tree_frame, bg=CARD_BG)
        table_wrap.pack(fill=BOTH, expand=True)
        
        cols = ("ID", "Title", "Project", "Assigned To", "Priority", "Status", "Due Date", "Progress", "Created")
        self.task_tree = ttk.Treeview(table_wrap, style="Task.Treeview", columns=cols, show='headings', selectmode="extended")
        for col in cols: 
            self.task_tree.heading(col, text=col, command=lambda c=col: self.sort_task_tree(c))
            self.task_tree.column(col, width=100)
        
        self.task_tree.column("ID", width=40, anchor=CENTER)
        self.task_tree.column("Title", width=240)
        self.task_tree.column("Project", width=180)
        self.task_tree.column("Assigned To", width=160)
        self.task_tree.column("Priority", width=80, anchor=CENTER)
        self.task_tree.column("Status", width=100, anchor=CENTER)
        self.task_tree.column("Due Date", width=120, anchor=CENTER)
        self.task_tree.column("Progress", width=100, anchor=CENTER)
        self.task_tree.column("Created", width=120, anchor=CENTER)
        
        self.task_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrolly = ttk.Scrollbar(table_wrap, orient=VERTICAL, command=self.task_tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        self.task_tree.configure(yscrollcommand=scrolly.set)
        # Tag styles
        self.task_tree.tag_configure('overdue_row', foreground=TEXT_WHITE, background=HEADER_BG)
        
        self.task_tree.bind("<Double-1>", lambda e: self.update_task_modal())
        
        try:
            cleanup_orphan_assignments()
        except:
            pass
        self.refresh_tasks()
        self._attach_tree_hover(self.task_tree)
    
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
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select tasks to delete")
            return
        
        if not messagebox.askyesno("Confirm", f"Are you sure you want to delete {len(selected)} selected task(s)?"):
            return

        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            for item_id in selected:
                tid = self.task_tree.item(item_id)['values'][0]
                cursor.execute("DELETE FROM tasks WHERE id=?", (tid,))
                cursor.execute("DELETE FROM task_comments WHERE task_id=?", (tid,))
                cursor.execute("DELETE FROM task_attachments WHERE task_id=?", (tid,))
            con.commit()
            con.close()
            self.refresh_tasks()
            messagebox.showinfo("Success", "Task(s) Deleted Successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete tasks: {e}")

    def update_task_modal(self, task_id_arg=None):
        task_id = None
        task_title = ""
        current_status = ""
        
        # Mode 1: Task ID provided (Quick Action)
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
        
        # Mode 2: Selection from various Treeviews
        else:
            # Check for selection in order of priority/existence
            target_tree = None
            if hasattr(self, 'emp_tasks_tree') and self.emp_tasks_tree.winfo_exists() and self.emp_tasks_tree.selection():
                target_tree = self.emp_tasks_tree
                status_idx = 4 # Based on cols = ("ID", "Title", "Project", "Priority", "Status", "Due Date", "Days Left")
            elif hasattr(self, 'task_tree') and self.task_tree.winfo_exists() and self.task_tree.selection():
                target_tree = self.task_tree
                status_idx = 5 # Based on cols = ("ID", "Title", "Project", "Assigned To", "Priority", "Status", "Due Date")
            elif hasattr(self, 'dash_task_tree') and self.dash_task_tree.winfo_exists() and self.dash_task_tree.selection():
                target_tree = self.dash_task_tree
                status_idx = -1 # Need to query DB as dash trees are simplified
            elif hasattr(self, 'dash_dead_tree') and self.dash_dead_tree.winfo_exists() and self.dash_dead_tree.selection():
                target_tree = self.dash_dead_tree
                status_idx = -1

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
            
            def _bg_save():
                try:
                    con = sqlite3.connect(get_db_path())
                    cursor = con.cursor()
                    if new_status == 'Completed':
                        cursor.execute("UPDATE tasks SET status=?, completed_date=? WHERE id=?", (new_status, datetime.now().strftime("%Y-%m-%d"), task_id))
                    else:
                        cursor.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
                    
                    # Log Activity (Background)
                    cursor.execute("SELECT project_id FROM tasks WHERE id=?", (task_id,))
                    pid_row = cursor.fetchone()
                    if pid_row:
                        pid = pid_row[0]
                        log_activity(pid, CURRENT_USER_NAME, f"Updated task '{task_title}' to {new_status}")
                    
                    con.commit()
                    con.close()
                    
                    # Refresh UI on main thread
                    if self.root.winfo_exists():
                        self.root.after(0, lambda: self._on_status_save_complete(t))
                except Exception as e:
                    if self.root.winfo_exists():
                        self.root.after(0, lambda: messagebox.showerror("Error", str(e)))

            btn_update.config(state=DISABLED, text="Saving...")
            threading.Thread(target=_bg_save, daemon=True).start()

    def _on_status_save_complete(self, modal_window):
        """Callback after task status is saved in background."""
        self.refresh_current_page()
        messagebox.showinfo("Success", "Status Updated Successfully")
        try: modal_window.destroy()
        except: pass
                
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
                con.commit(); con.close()
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
                con.commit(); con.close()
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

    def refresh_tasks(self):
        try:
            for item in self.task_tree.get_children(): self.task_tree.delete(item)
            
            search_txt = self.task_search_var.get().lower() if hasattr(self, 'task_search_var') else ""
            status_filter = self.task_filter_var.get() if hasattr(self, 'task_filter_var') else "All"
            prio_filter = self.task_prio_filter.get() if hasattr(self, 'task_prio_filter') else "All"
            member_filter = self.task_member_filter.get() if hasattr(self, 'task_member_filter') else "All"
            
            def _bg_task_fetch():
                try:
                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()
                    
                    # Optimized query: Direct join filter for TLs
                    query = """
                        SELECT t.id, t.title, p.name, t.assigned_to, t.priority, t.status, t.due_date, t.created_date 
                        FROM tasks t 
                        LEFT JOIN projects p ON t.project_id = p.id
                        WHERE 1=1
                    """
                    params = []
                    
                    if CURRENT_USER_ROLE.lower() == 'team leader':
                        query += " AND (p.team_leader LIKE ? OR t.assigned_to = ?)"
                        params.extend([f"%{CURRENT_USER_NAME}%", CURRENT_USER_NAME])
                    
                    if status_filter != "All":
                        if status_filter == "Overdue":
                            query += " AND t.status != 'Completed' AND t.due_date < date('now')"
                        else:
                            query += " AND t.status=?"
                            params.append(status_filter)
                        
                    if prio_filter != "All":
                        query += " AND t.priority=?"
                        params.append(prio_filter)
                        
                    if member_filter != "All":
                        query += " AND t.assigned_to=?"
                        params.append(member_filter)
                        
                    if search_txt:
                        query += " AND (lower(t.title) LIKE ? OR lower(p.name) LIKE ? OR lower(t.assigned_to) LIKE ?)"
                        p_val = f"%{search_txt}%"
                        params.extend([p_val, p_val, p_val])
                        
                    query += " ORDER BY t.id DESC LIMIT 300" # Safety limit for ultra-smoothness
                    
                    cur.execute(query, params)
                    rows = cur.fetchall()
                    con.close()
                    
                    if self.root.winfo_exists():
                        self.root.after(0, lambda: self._render_tasks_batch(rows))
                except Exception as e:
                    debug_log(f"DEBUG: Error in bg task fetch: {e}")

            threading.Thread(target=_bg_task_fetch, daemon=True).start()
        except Exception as e:
            debug_log(f"DEBUG: Error refreshing tasks: {e}")

    def _render_tasks_batch(self, rows):
        """Thread-safe UI update for Task Treeview."""
        if not self.task_tree.winfo_exists(): return
        
        today = datetime.now().date()
        for row in rows:
            vals = list(row)
            s = str(vals[5])
            prog = 100 if s == 'Completed' else 50 if s == 'In Progress' else 25 if s == 'Delayed' else 0
            vals.insert(7, f"{prog}%")
            tags = ()
            try:
                if s != 'Completed' and vals[6]:
                    d = datetime.strptime(vals[6], "%Y-%m-%d").date()
                    if d < today: tags = ('overdue_row',)
            except: pass
            self.task_tree.insert("", END, values=vals, tags=tags)

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
                
                con.commit()
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
                
                con.commit()
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
            con.commit(); con.close()
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
                
                con.commit()
                con.close()
                
                log_audit(CURRENT_USER_NAME, "Tasks Marked Urgent", f"Marked {len(tids)} tasks as High priority")
                self.refresh_tasks()
                messagebox.showinfo("Success", "Tasks updated.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def add_task_modal(self):
        t = Toplevel(self.root)
        t.title("Assign Task")
        t.geometry("500x600")
        t.minsize(425, 510)  # FIX 7: prevent content clipping when UI changes
        t.resizable(True, True)  # FIX 7: allow resize so no overflow
        t.config(bg=CONTENT_BG)
        
        Label(t, text="New Task", font=('Segoe UI', 16, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=20)
        f = Frame(t, bg=CONTENT_BG, padx=40)
        f.pack(fill=BOTH, expand=True)
        
        # Get Projects and Members for Dropdowns
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        role = CURRENT_USER_ROLE.lower()
        if role == 'team leader':
            # TL only sees their projects
            cur.execute("SELECT id, name FROM projects WHERE team_leader LIKE ?", (f"%{CURRENT_USER_NAME}%",))
            projects = cur.fetchall()
            # TL only sees members in their projects
            cur.execute("""
                SELECT DISTINCT name FROM employee 
                WHERE name IN (
                    SELECT DISTINCT assigned_to FROM tasks 
                    WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                ) OR role IN ('Team Member', 'Employee')
            """, (f"%{CURRENT_USER_NAME}%",))
            members = [r[0] for r in cur.fetchall()]
        else:
            cur.execute("SELECT id, name FROM projects")
            projects = cur.fetchall()
            cur.execute("SELECT name FROM employee")
            members = [r[0] for r in cur.fetchall()]
        con.close()
        
        project_map = {name: pid for pid, name in projects}
        project_names = list(project_map.keys())
        
        Label(f, text="Project", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        c_proj = ttk.Combobox(f, values=project_names)
        c_proj.pack(fill=X, pady=(0, 10))
        
        Label(f, text="Task Title", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        e_title = Entry(f)
        e_title.pack(fill=X, pady=(0, 10))
        
        Label(f, text="Assign To", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        c_user = ttk.Combobox(f, values=members)
        c_user.pack(fill=X, pady=(0, 10))
        
        Label(f, text="Due Date", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        e_date = Entry(f)
        e_date.pack(fill=X, pady=(0, 10))
        
        Label(f, text="Priority", bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        c_prio = ttk.Combobox(f, values=["High", "Medium", "Low"])
        c_prio.pack(fill=X, pady=(0, 10))
        
        def save():
            try:
                pid = project_map.get(c_proj.get())
                if not pid: raise Exception("Select a valid project")
                
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                assignee = c_user.get() or get_project_default_assignee(pid)
                cur.execute("INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)",
                            (e_title.get(), pid, assignee, "Pending", e_date.get(), c_prio.get(), datetime.now().strftime("%Y-%m-%d")))
                
                # Log Activity
                log_activity(pid, CURRENT_USER_NAME, f"Created new task: '{e_title.get()}' assigned to {assignee or 'Unassigned'}")
                
                con.commit()
                con.close()
                
                if assignee:
                    log_audit(CURRENT_USER_NAME, "Task Assigned", f"Assigned '{e_title.get()}' to {assignee}")
                    notify_user(assignee, f"New Task: {e_title.get()} (Due: {e_date.get()})")
                
                self.refresh_tasks()
                t.destroy()
                messagebox.showinfo("Success", "Action completed successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                
        Button(t, text="Assign Task", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(pady=20, fill=X, padx=40)

    def add_task_to_tl_modal(self, prefill_pid=None, prefill_name=None, prefill_tl=None):
        t = Toplevel(self.root)
        t.title("Assign Task to Team Leader")
        # Responsive sizing (fit within screen)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        target_w = max(460, min(560, sw - 140))
        target_h = max(420, min(600, sh - 180))
        t.geometry(f"{target_w}x{target_h}")
        t.config(bg=CONTENT_BG)
        try:
            x = int((sw/2) - (target_w/2))
            y = int((sh/2) - (target_h/2))
            t.geometry(f"{target_w}x{target_h}+{x}+{y}")
        except:
            pass
        Label(t, text="New Task for Team Leader", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(pady=(14, 6))
        Label(t, text="Pick project, leader, deadline and priority. Title is auto-created.", font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack()
        # Scrollable card container (prevents overflow on small screens)
        container = Frame(t, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, padx=24, pady=(6, 12))
        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrolly = Scrollbar(container, orient=VERTICAL, command=canvas.yview)
        card = Frame(canvas, bg=CARD_BG, padx=24, pady=20, highlightbackground=ACCENT_BLUE, highlightthickness=1)
        canvas_window = canvas.create_window((0, 0), window=card, anchor="nw")
        def _on_canvas_configure(event):
            try:
                canvas.itemconfig(canvas_window, width=event.width)
                canvas.configure(scrollregion=canvas.bbox("all"))
            except:
                pass
        canvas.bind("<Configure>", _on_canvas_configure)
        canvas.configure(yscrollcommand=scrolly.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrolly.pack(side=RIGHT, fill=Y)
        f = Frame(card, bg=CARD_BG)
        f.pack(fill=BOTH, expand=True)
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        cur.execute("SELECT id, name FROM projects")
        projects = cur.fetchall()
        cur.execute("SELECT name FROM employee WHERE role = 'Team Leader'")
        leaders = [r[0] for r in cur.fetchall()]
        con.close()
        project_map = {name: pid for pid, name in projects}
        project_names = list(project_map.keys())
        # Chips row for quick context
        chip_row = Frame(f, bg=CARD_BG)
        chip_row.pack(fill=X, pady=(0, 10))
        chip_proj_var = StringVar(value="Project: â€”")
        chip_tl_var = StringVar(value="Leader: â€”")
        Label(chip_row, textvariable=chip_proj_var, bg="#40424a", fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0,6))
        Label(chip_row, textvariable=chip_tl_var, bg="#40424a", fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT)
        Label(f, text="Project", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W, pady=(0,2))
        c_proj = ttk.Combobox(f, values=project_names, state="readonly")
        c_proj.pack(fill=X, pady=(0, 14))
        Label(f, text="Assign To (Team Leader)", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W, pady=(0,2))
        c_leader = ttk.Combobox(f, values=leaders, state="readonly")
        c_leader.pack(fill=X, pady=(0, 14))
        Label(f, text="Due Date (YYYY-MM-DD)", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W, pady=(0,2))
        e_date = Entry(f)
        e_date.pack(fill=X, pady=(0, 14))
        Label(f, text="Priority", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 11, 'bold')).pack(anchor=W, pady=(0,2))
        c_prio = ttk.Combobox(f, values=["High", "Medium", "Low"], state="readonly")
        c_prio.pack(fill=X, pady=(0, 6))
        def _update_chips(*_):
            chip_proj_var.set(f"Project: {c_proj.get() or 'â€”'}")
            chip_tl_var.set(f"Leader: {c_leader.get() or 'â€”'}")
        c_proj.bind("<<ComboboxSelected>>", _update_chips)
        c_leader.bind("<<ComboboxSelected>>", _update_chips)
        try:
            if prefill_name and prefill_name in project_map:
                c_proj.set(prefill_name)
            if prefill_tl and prefill_tl in leaders:
                c_leader.set(prefill_tl)
            _update_chips()
        except:
            pass
        try:
            e_date.insert(0, (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"))
        except:
            pass
        try:
            c_prio.set("Medium")
        except:
            pass
        # Keyboard navigation
        try:
            c_proj.bind("<Down>", lambda e: (c_leader.focus_set(), 'break'))
            c_leader.bind("<Up>", lambda e: (c_proj.focus_set(), 'break'))
            c_leader.bind("<Down>", lambda e: (e_date.focus_set(), 'break'))
            e_date.bind("<Up>", lambda e: (c_leader.focus_set(), 'break'))
            e_date.bind("<Down>", lambda e: (c_prio.focus_set(), 'break'))
            c_prio.bind("<Up>", lambda e: (e_date.focus_set(), 'break'))
        except:
            pass
        def save():
            try:
                pid = project_map.get(c_proj.get())
                if not pid:
                    raise Exception("Select a valid project")
                leader_name = c_leader.get().strip()
                due_date = e_date.get().strip()
                priority = c_prio.get().strip() or "Medium"
                if not leader_name:
                    raise Exception("Select a valid team leader")
                if not due_date:
                    raise Exception("Enter a valid due date")
                task_title = f"{c_proj.get()} - TL Assignment"
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                cur.execute("UPDATE projects SET team_leader=?, default_assignee=? WHERE id=?", (leader_name, leader_name, pid))
                cur.execute("SELECT id, assigned_to FROM tasks WHERE project_id=? AND title=? ORDER BY id ASC", (pid, task_title))
                matches = cur.fetchall()
                if matches:
                    keep_id, keep_assignee = matches[0]
                    keep_assignee = (keep_assignee or "").strip()
                    if keep_assignee:
                        if keep_assignee.lower() == leader_name.lower():
                            raise Exception(f"This task is already assigned to {leader_name}.")
                        raise Exception(f"This task is already assigned to {keep_assignee}. One task can belong to only one Team Leader.")
                    cur.execute(
                        "UPDATE tasks SET assigned_to=?, due_date=?, priority=? WHERE id=?",
                        (leader_name, due_date, priority, keep_id)
                    )
                    if len(matches) > 1:
                        dup_ids = [(row_id,) for row_id, _ in matches[1:]]
                        cur.executemany("DELETE FROM tasks WHERE id=?", dup_ids)
                else:
                    cur.execute(
                        "INSERT INTO tasks (title, project_id, assigned_to, status, due_date, priority, created_date) VALUES (?,?,?,?,?,?,?)",
                        (task_title, pid, leader_name, "Pending", due_date, priority, datetime.now().strftime("%Y-%m-%d"))
                    )
                con.commit()
                con.close()
                t.destroy()
                try:
                    self.switch_page('tasks')
                except:
                    self.load_project_status_panel()
                messagebox.showinfo("Success", "Action completed successfully.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
        btn_row = Frame(t, bg=CONTENT_BG)
        btn_row.pack(fill=X, padx=24, pady=(4, 10))
        Button(btn_row, text="Cancel", command=t.destroy, bg=ACCENT_ORANGE, fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT).pack(side=LEFT, expand=True, fill=X, padx=(0,6))
        Button(btn_row, text="Assign Task", command=save, bg=PRIMARY_BG, fg=TEXT_WHITE, font=('Segoe UI', 12, 'bold'), relief=FLAT).pack(side=LEFT, expand=True, fill=X, padx=(6,0))
        t.bind("<Return>", lambda e: save())
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
                con.commit()
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
                con.commit()
                con.close()
                messagebox.showinfo("Success", f"Leave {status}")
                t.destroy()
                self.show_notifications()
                
            btn_f2 = Frame(leave_frame, bg=CARD_BG)
            btn_f2.pack(fill=X, pady=10)
            Button(btn_f2, text="Approve Leave", bg="#27ae60", fg="white", relief=FLAT, padx=15, command=lambda: handle_leave('Approve')).pack(side=RIGHT, padx=5)
            Button(btn_f2, text="Reject Leave", bg="#e74c3c", fg="white", relief=FLAT, padx=15, command=lambda: handle_leave('Reject')).pack(side=RIGHT, padx=5)

    def load_leave_requests(self):
        for w in self.content_area.winfo_children():
            w.destroy()
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=30)
        Label(h, text="Leave Requests", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        # Filter
        filter_box = Frame(h, bg=CONTENT_BG)
        filter_box.pack(side=RIGHT)
        Label(filter_box, text="Filter:", bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=LEFT, padx=(0,6))
        if not hasattr(self, "_leave_filter"): self._leave_filter = StringVar(value="All")
        cb = ttk.Combobox(filter_box, textvariable=self._leave_filter, values=["All","Approved","Rejected","Pending"], state="readonly", width=12)
        cb.pack(side=LEFT)
        cb.bind("<<ComboboxSelected>>", lambda e: self.load_leave_requests())
        body = Frame(self.content_area, bg=CARD_BG, padx=20, pady=20)
        body.pack(fill=BOTH, expand=True, padx=30, pady=(0, 30))
        cols = ("ID", "Name", "Type", "Reason", "Start", "End", "Total Days", "Submitted", "Status")
        tree = ttk.Treeview(body, columns=cols, show='headings')
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=110 if c not in ("Reason","Name") else 160)
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = Scrollbar(body, orient=VERTICAL, command=tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=sb.set)
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            q = "SELECT id, member_name, COALESCE(leave_type,'N/A'), reason, start_date, end_date, timestamp, status FROM leave_requests"
            params = []
            if self._leave_filter.get() != "All":
                q += " WHERE status=?"
                params.append(self._leave_filter.get())
            q += " ORDER BY id DESC"
            cur.execute(q, params)
            for r in cur.fetchall():
                try:
                    s = datetime.strptime(r[4], "%Y-%m-%d")
                    e = datetime.strptime(r[5], "%Y-%m-%d")
                    days = (e - s).days + 1
                    days = max(days, 1)
                except:
                    days = "N/A"
                tree.insert("", END, values=(r[0], r[1], r[2], r[3], r[4], r[5], days, r[6], r[7]))
            con.close()
        except:
            pass
        btns = Frame(self.content_area, bg=CONTENT_BG)
        btns.pack(fill=X, padx=30, pady=(0, 30))
        def act(status):
            sel = tree.selection()
            if not sel: return
            lid = tree.item(sel[0])['values'][0]
            def submit_action():
                comment = txt.get("1.0", END).strip()
                if not comment:
                    if status == "Rejected":
                        messagebox.showwarning("Required", "Reason is required for rejection.")
                        return
                    comment = "Approved by Admin"
                
                try:
                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()
                    cur.execute("UPDATE leave_requests SET status=? WHERE id=?", (status, lid))
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cur.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)",
                                (ts, CURRENT_USER_NAME, f"Leave {status}", f"id={lid}; comment={comment}"))
                    con.commit()
                    con.close()
                    dialog.destroy()
                    self.load_leave_requests()
                except Exception as e:
                    messagebox.showerror("Error", str(e))

            dialog = Toplevel(self.root)
            dialog.title(f"{status} Leave")
            dialog.geometry("450x350")
            dialog.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
            dialog.resizable(True, True)  # FIX 7: allow resize so no overflow
            dialog.configure(bg=BG_CARD)
            dialog.resizable(False, False)
            dialog.transient(self.root)
            dialog.grab_set()

            # Brand Stripe
            stripe = Frame(dialog, bg=ACCENT_GREEN if status == "Approved" else ACCENT_RED, height=3)
            stripe.pack(fill=X)

            # Center
            mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 225
            my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 175
            dialog.geometry(f"450x350+{mx}+{my}")

            header = Frame(dialog, bg=HEADER_BG, pady=15)
            header.pack(fill=X)
            Label(header, text=f"{status.upper()} REQUEST", font=('Rajdhani', 14, 'bold'), 
                  bg=HEADER_BG, fg=WHITE).pack()

            body = Frame(dialog, bg=BG_CARD, padx=30, pady=20)
            body.pack(fill=BOTH, expand=True)
            
            Label(body, text=f"Comment/Reason for {status}:", font=('Segoe UI', 10), 
                  bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 10))
            
            txt_frame = Frame(body, bg="#1a2035", highlightbackground="#2e3760", highlightthickness=1)
            txt_frame.pack(fill=BOTH, expand=True)
            txt = Text(txt_frame, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), 
                       relief=FLAT, padx=10, pady=10, insertbackground=WHITE, height=4)
            txt.pack(fill=BOTH, expand=True)
            txt.focus_set()

            btn_color = ACCENT_GREEN if status == "Approved" else ACCENT_RED
            Button(body, text=f"CONFIRM {status.upper()}", bg=btn_color, fg=WHITE, 
                   font=('Segoe UI', 10, 'bold'), relief=FLAT, pady=10, command=submit_action).pack(fill=X, pady=(20, 0))
            return # Skip the old logic
            con.commit()
            con.close()
            self.load_leave_requests()
        Button(btns, text="Approve", bg=ACCENT_GREEN, fg='white', relief=FLAT, padx=15, command=lambda: act('Approved')).pack(side=RIGHT, padx=10)
        Button(btns, text="Reject", bg=ACCENT_RED, fg='white', relief=FLAT, padx=15, command=lambda: act('Rejected')).pack(side=RIGHT)
        self._attach_tree_hover(tree)



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

        hero_band = Frame(parent, bg=CARD_BG, padx=28, pady=24, highlightbackground=BORDER_COLOR, highlightthickness=1)
        hero_band.pack(fill=X, padx=30, pady=(26, 18))

        h = Frame(hero_band, bg=CARD_BG)
        h.pack(fill=X)

        title_box = Frame(h, bg=CARD_BG) # Changed to match hero_band
        title_box.pack(side=LEFT, fill=X, expand=True)
        Label(title_box, text="Team Performance Reports", font=('Segoe UI', 26, 'bold'),
              bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="A clearer view of productivity, weekly output, workload balance, and export-ready reporting.",
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(6, 0))

        last_gen = getattr(self, "last_report_generated", "Never")
        status_chip = Frame(h, bg=BG_DARK, padx=16, pady=12, highlightbackground=BORDER_COLOR, highlightthickness=1)
        status_chip.pack(side=RIGHT)
        
        Label(status_chip, text="REPORT ENGINE", font=('Segoe UI', 8, 'bold'), anchor=E,
              bg=BG_DARK, fg=MUTED_TEXT).pack(anchor=E)
        
        chip_row = Frame(status_chip, bg=BG_DARK)
        chip_row.pack(anchor=E, pady=(4, 0))
        
        Label(chip_row, text=f"Last Sync: {last_gen}", font=('Segoe UI', 10, 'bold'),
              bg=BG_DARK, fg=TEXT_WHITE).pack(side=LEFT)
        
        Button(chip_row, text="Generate Snapshot", font=('Segoe UI', 9, 'bold'),
               bg=ACCENT_BLUE, fg=WHITE, relief=FLAT, padx=12, pady=2,
               command=lambda: messagebox.showinfo("Report", "Snapshot generated successfully.")).pack(side=LEFT, padx=(12, 0))

        hero_strip = Frame(hero_band, bg=CARD_BG)
        hero_strip.pack(fill=X, pady=(16, 0))
        for idx, (icon, title, value, accent) in enumerate((
            ("📡", "Visibility", "Live team reporting", ACCENT_BLUE),
            ("📉", "Trend Window", "6-8 week snapshots", ACCENT_GREEN),
            ("📦", "Export Mode", "PDF & CSV bundle", ACCENT_ORANGE),
        )):
            box = Frame(hero_strip, bg=HEADER_BG, padx=18, pady=14, highlightbackground=accent, highlightthickness=1)
            box.pack(side=LEFT, fill=BOTH, expand=True, padx=(0 if idx == 0 else 12, 0))
            
            top_row = Frame(box, bg=HEADER_BG)
            top_row.pack(fill=X)
            Label(top_row, text=icon, font=('Segoe UI', 12), bg=HEADER_BG).pack(side=LEFT, padx=(0, 8))
            Label(top_row, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack(side=LEFT)
            
            Label(box, text=value, font=('Segoe UI', 11, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(8, 0))

        con = sqlite3.connect(get_db_path())
        cur = con.cursor()

        # Team Average Productivity
        avg_rate = 0
        try:
            cur.execute("""
                SELECT AVG(rate) FROM (
                    SELECT (SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS rate
                    FROM tasks
                    WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
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
            cur.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                  AND date(COALESCE(created_date, due_date)) >= date('now', '-6 days')
            """, (f"%{CURRENT_USER_NAME}%",))
            total_week = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                  AND status='Completed'
                  AND date(COALESCE(completed_date, created_date, due_date)) >= date('now', 'start of month')
            """, (f"%{CURRENT_USER_NAME}%",))
            completed_month = cur.fetchone()[0] or 0
        except:
            pass

        team_size = 0
        active_members = 0
        try:
            cur.execute("""
                SELECT COUNT(DISTINCT assigned_to)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
                  AND assigned_to IS NOT NULL
                  AND TRIM(assigned_to) != ''
            """, (f"%{CURRENT_USER_NAME}%",))
            team_size = cur.fetchone()[0] or 0

            cur.execute("""
                SELECT COUNT(DISTINCT assigned_to)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
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
            cur.execute("""
                SELECT COUNT(*)
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
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
            cur.execute("""
                SELECT AVG(rate) FROM (
                    SELECT (SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*)) AS rate
                    FROM tasks
                    WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
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
            cur.execute("""
                SELECT assigned_to, COUNT(*) 
                FROM tasks 
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?) AND status!='Completed'
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

            cur.execute("""
                SELECT assigned_to,
                       COUNT(*) as total,
                       SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END) as completed,
                       SUM(CASE WHEN status='Delayed' OR (status!='Completed' AND due_date < date('now')) THEN 1 ELSE 0 END) as delayed
                FROM tasks
                WHERE project_id IN (SELECT id FROM projects WHERE team_leader LIKE ?)
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

    def export_csv(self):
        try:
            filename = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
            if not filename: return
            
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                
                # Projects
                writer.writerow(["--- PROJECTS ---"])
                writer.writerow(["ID", "Name", "Manager", "Start", "End", "Description", "Status"])
                cursor.execute("SELECT * FROM projects")
                writer.writerows(cursor.fetchall())
                
                writer.writerow([])
                
                # Tasks
                writer.writerow(["--- TASKS ---"])
                writer.writerow(["ID", "Title", "Project ID", "Assigned To", "Status", "Due Date", "Priority"])
                cursor.execute("SELECT * FROM tasks")
                writer.writerows(cursor.fetchall())
                
                writer.writerow([])
                
                # Employees
                writer.writerow(["--- EMPLOYEES ---"])
                writer.writerow(["ID", "Name", "Mobile", "Email", "Department", "Role"])
                cursor.execute("SELECT id, name, mobile, email, department, role FROM employee")
                writer.writerows(cursor.fetchall())
                
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
                delayed = cursor.fetchone()[0]
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
    def load_productivity(self):
        h = Frame(self.content_area, bg=CONTENT_BG)
        h.pack(fill=X, padx=30, pady=(26, 18))
        Label(h, text="Team Leader Productivity", font=('Segoe UI', 22, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)

        wrapper = Frame(self.content_area, bg=CONTENT_BG)
        wrapper.pack(fill=BOTH, expand=True, padx=30, pady=(0, 30))

        canvas = Canvas(wrapper, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        frame_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(frame_id, width=e.width))
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        self._bind_canvas_scrolling(wrapper, canvas, allow_horizontal=False)

        grid_frame = scrollable_frame
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        con = sqlite3.connect(get_db_path())
        cursor = con.cursor()
        cursor.execute("SELECT name FROM employee WHERE role='Team Leader'")
        tls = [r[0] for r in cursor.fetchall()]

        if not tls:
            Label(grid_frame, text="No Team Leaders Found.", bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=20)

        # Compute metrics and identify top performer
        tl_stats = []
        best_name = None
        best_rate = -1
        for tl in tls:
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (tl,))
            total = cursor.fetchone()[0] or 0
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Completed'", (tl,))
            completed = cursor.fetchone()[0] or 0
            pending = max(total - completed, 0)
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Delayed'", (tl,))
            delayed = cursor.fetchone()[0] or 0
            rate = int((completed / total) * 100) if total > 0 else 0

            avg_days = "N/A"
            try:
                cursor.execute("""
                    SELECT AVG(julianday(COALESCE(completed_date, date('now'))) - julianday(COALESCE(created_date, due_date)))
                    FROM tasks
                    WHERE assigned_to=? AND status='Completed'
                """, (tl,))
                d = cursor.fetchone()[0]
                if d is not None:
                    avg_days = f"{round(float(d), 1)} day(s)"
            except:
                pass

            tl_stats.append((tl, total, completed, pending, delayed, rate, avg_days))
            if rate > best_rate:
                best_rate = rate
                best_name = tl

        row = 0
        hero = Frame(grid_frame, bg=CARD_BG, padx=24, pady=22, highlightbackground="#5c5960", highlightthickness=1)
        hero.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 18))
        row += 1

        Label(hero, text="Active Team Leader Performance", font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(hero, text="Click any card to view task assignment, completed work, pending items, and team productivity details.", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(6, 10))
        hero_stats = Frame(hero, bg=CARD_BG)
        hero_stats.pack(anchor=W)
        Label(hero_stats, text=f" Total TLs: {len(tl_stats)} ", bg="#40424a", fg=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(hero_stats, text=f" Best Rate: {best_rate if best_rate >= 0 else 0}% ", bg="#244334", fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT, padx=(0, 8))
        Label(hero_stats, text=f" Top Performer: {best_name or 'N/A'} ", bg="#5a2326", fg=WHITE, font=('Segoe UI', 9, 'bold'), padx=10, pady=4).pack(side=LEFT)

        def open_tl_productivity_detail(tl, total, completed, pending, delayed, rate, avg_days):
            if not hasattr(self, "_productivity_detail_windows"):
                self._productivity_detail_windows = {}

            existing = self._productivity_detail_windows.get(tl)
            if existing is not None:
                try:
                    if existing.winfo_exists():
                        existing.lift()
                        existing.focus_force()
                        return
                except:
                    pass

            top = Toplevel(self.root)
            top.title(f"{tl} Productivity")
            top.geometry("980x700")
            top.config(bg=CONTENT_BG)
            top.minsize(860, 620)
            self._productivity_detail_windows[tl] = top
            top.bind("<Destroy>", lambda _e, key=tl: self._productivity_detail_windows.pop(key, None))

            # FIX 5d: reuse Style singleton — no theme_use() needed
            style = ttk.Style()
            style.configure(
                "Prod.Treeview",
                background=HEADER_BG,
                foreground=TEXT_WHITE,
                fieldbackground=HEADER_BG,
                rowheight=40,
                borderwidth=0,
                relief="flat",
                font=('Segoe UI', 10)
            )
            style.configure(
                "Prod.Treeview.Heading",
                background="#1f2937",
                foreground=TEXT_WHITE,
                font=('Segoe UI', 10, 'bold'),
                borderwidth=0,
                relief="flat",
                padding=(12, 12)
            )
            style.map(
                "Prod.Treeview",
                background=[('selected', PRIMARY_BG)],
                foreground=[('selected', WHITE)]
            )

            shell = Frame(top, bg=CONTENT_BG, padx=24, pady=22)
            shell.pack(fill=BOTH, expand=True)

            hero_p = Frame(shell, bg=CARD_BG, padx=24, pady=22, highlightbackground=BORDER_COLOR, highlightthickness=1)
            hero_p.pack(fill=X, pady=(0, 16))

            head = Frame(hero_p, bg=CARD_BG)
            head.pack(fill=X)
            Label(head, text=tl, font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
            status_badge = Frame(head, bg=ACCENT_GREEN if rate >= 70 else (ACCENT_ORANGE if rate >= 40 else PRIMARY_BG), padx=12, pady=5)
            status_badge.pack(side=RIGHT)
            Label(status_badge, text=f"Productivity Rate {rate}%", font=('Segoe UI', 9, 'bold'),
                  bg=status_badge.cget("bg"), fg=WHITE).pack()
            Label(hero_p, text="Task assignment, delivery quality, and workload distribution for this team leader.",
                  font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(8, 0))

            metrics = Frame(shell, bg=CONTENT_BG)
            metrics.pack(fill=X, pady=(0, 16))

            def create_metric(parent, title, value, accent, subtitle):
                card = Frame(parent, bg=HEADER_BG, padx=16, pady=14, highlightbackground=accent, highlightthickness=1)
                card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
                Label(card, text=title.upper(), bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 8, 'bold')).pack(anchor=W)
                Label(card, text=value, bg=HEADER_BG, fg=TEXT_WHITE, font=('Segoe UI', 16, 'bold')).pack(anchor=W, pady=(8, 2))
                Label(card, text=subtitle, bg=HEADER_BG, fg=accent, font=('Segoe UI', 9)).pack(anchor=W)
                return card

            create_metric(metrics, "Assigned", str(total), ACCENT_BLUE, "Current workload")
            create_metric(metrics, "Completed", str(completed), ACCENT_GREEN, "Delivered tasks")
            create_metric(metrics, "Pending", str(pending), ACCENT_ORANGE, "Still in queue")
            create_metric(metrics, "Delayed", str(delayed), PRIMARY_BG, "Needs attention")
            create_metric(metrics, "Rate", f"{rate}%", ACCENT_BLUE, "Completion percentage")

            summary = Frame(shell, bg=CARD_BG, padx=20, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1)
            summary.pack(fill=X, pady=(0, 16))
            Label(summary, text="Performance Snapshot", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(summary, text="Average Completion Time", font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(10, 2))
            Label(summary, text=avg_days, font=('Segoe UI', 15, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W)
            bar_bg = Frame(summary, bg="#253244", height=8)
            bar_bg.pack(fill=X, pady=(14, 0))
            Frame(bar_bg, bg=ACCENT_GREEN if rate >= 70 else (ACCENT_ORANGE if rate >= 40 else PRIMARY_BG),
                  height=8).place(x=0, y=0, relwidth=max(0.12, min(rate / 100 if rate else 0.12, 1.0)))

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
            tree.column("Task", width=300, anchor=W)
            tree.column("Project", width=220, anchor=W)
            tree.column("Status", width=130, anchor=CENTER)
            tree.column("Due Date", width=140, anchor=CENTER)
            tree.column("Priority", width=120, anchor=CENTER)
            tree.pack(side=LEFT, fill=BOTH, expand=True)
            sb = ttk.Scrollbar(tree_frame, orient=VERTICAL, command=tree.yview)
            sb.pack(side=RIGHT, fill=Y)
            tree.configure(yscrollcommand=sb.set)
            tree.tag_configure("completed", background="#1f4d3a", foreground=TEXT_WHITE)
            tree.tag_configure("pending", background=HEADER_BG, foreground=TEXT_WHITE)
            tree.tag_configure("in_progress", background="#364152", foreground=TEXT_WHITE)
            tree.tag_configure("delayed", background="#7a1f2b", foreground=TEXT_WHITE)

            try:
                con2 = sqlite3.connect(get_db_path())
                cur2 = con2.cursor()
                cur2.execute("""
                    SELECT t.title, COALESCE(p.name, ''), t.status, COALESCE(t.due_date, 'N/A'), COALESCE(t.priority, 'N/A')
                    FROM tasks t
                    LEFT JOIN projects p ON t.project_id = p.id
                    WHERE t.assigned_to=?
                    ORDER BY
                        CASE t.status
                            WHEN 'Delayed' THEN 0
                            WHEN 'Pending' THEN 1
                            WHEN 'In Progress' THEN 2
                            WHEN 'Completed' THEN 3
                            ELSE 4
                        END,
                        COALESCE(t.due_date, '9999-12-31') ASC
                """, (tl,))
                rows = cur2.fetchall()
                con2.close()
            except:
                rows = []

            if not rows:
                empty = Frame(body, bg=HEADER_BG, padx=18, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
                empty.pack(fill=X, pady=16)
                Label(empty, text="No task data available yet", bg=HEADER_BG, fg=TEXT_WHITE, font=('Segoe UI', 12, 'bold')).pack(anchor=W)
                Label(empty, text="Once work is assigned to this team leader, task performance details will appear here.",
                      bg=HEADER_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(anchor=W, pady=(6, 0))
            else:
                for row_vals in rows:
                    status_key = str(row_vals[2]).lower().replace(" ", "_")
                    tag = status_key if status_key in ("completed", "pending", "in_progress", "delayed") else "pending"
                    tree.insert("", END, values=row_vals, tags=(tag,))

            footer = Frame(shell, bg=CONTENT_BG)
            footer.pack(fill=X)
            Label(footer, text="Use this view to quickly review workload balance and overdue delivery risk.",
                  bg=CONTENT_BG, fg=MUTED_TEXT, font=('Segoe UI', 9)).pack(side=LEFT)
            Button(footer, text="Generate Team Reports",
                   command=lambda: self._generate_reports_from_popup(tl, top),
                   bg=ACCENT_ORANGE, fg=WHITE, relief=FLAT,
                   font=('Segoe UI', 10, 'bold'), padx=16, pady=10).pack(side=RIGHT, padx=(0, 10))
            Button(footer, text="Close", command=top.destroy, bg=PRIMARY_BG, fg=WHITE, relief=FLAT,
                   activebackground=PRIMARY_RED_DARK, activeforeground=WHITE,
                   font=('Segoe UI', 10, 'bold'), padx=20, pady=10).pack(side=RIGHT)

        # Interactive Team Leader Efficiency Cards
        tl_col = 0
        for tl_data in tl_stats:
            tl_n, t_tot, t_cmp, t_pnd, t_dly, t_rt, t_avg = tl_data
            
            c = Frame(grid_frame, bg=HEADER_BG, padx=20, pady=18, highlightbackground=BORDER_COLOR, highlightthickness=1, cursor="hand2")
            c.grid(row=row, column=tl_col, padx=10, pady=10, sticky="nsew")
            
            # Click to open deep-dive
            c.bind("<Button-1>", lambda e, d=tl_data: open_tl_productivity_detail(*d))

            ch = Frame(c, bg=HEADER_BG)
            ch.pack(fill=X)
            Label(ch, text="👤", font=('Segoe UI', 14), bg=HEADER_BG, fg=TEXT_WHITE).pack(side=LEFT)
            Label(ch, text=tl_n, font=('Segoe UI', 13, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=8)
            Label(ch, text="LEADER", font=('Segoe UI', 7, 'bold'), bg=ACCENT_BLUE, fg=WHITE, padx=6, pady=2).pack(side=RIGHT)
            
            Label(c, text=f"Performance Rating: {t_rt}%", font=('Segoe UI', 10), bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(12, 4))
            
            pb_bg = Frame(c, bg="#253244", height=6)
            pb_bg.pack(fill=X, pady=(0, 15))
            Frame(pb_bg, bg=ACCENT_GREEN if t_rt >= 70 else (ACCENT_ORANGE if t_rt >= 40 else PRIMARY_BG), height=6).place(x=0, y=0, relwidth=max(0.05, t_rt/100))
            
            st_f = Frame(c, bg=HEADER_BG)
            st_f.pack(fill=X)
            for sl, sv, sc in [("Total", t_tot, TEXT_WHITE), ("Done", t_cmp, ACCENT_GREEN), ("Late", t_dly, ACCENT_RED)]:
                sf = Frame(st_f, bg=HEADER_BG)
                sf.pack(side=LEFT, expand=True)
                Label(sf, text=sv, font=('Segoe UI', 12, 'bold'), bg=HEADER_BG, fg=sc).pack()
                Label(sf, text=sl, font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack()

            tl_col += 1
            if tl_col > 1:
                tl_col = 0
                row += 1
        
        if tl_col != 0: row += 1

        # Individual Member Analysis Section (Hide for Project Managers to simplify their view)
        if str(CURRENT_USER_ROLE).lower() != 'project manager':
            row += 1
            sep_f = Frame(grid_frame, bg=CONTENT_BG)
            sep_f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(40, 20))
            Label(sep_f, text="Individual Team Member Analysis", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
            Label(sep_f, text="Granular per-member performance metrics, workload distribution, and individual contribution rates.",
                  font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(4, 0))
            
            # Grid layout for individual member cards
            row += 1
            member_col = 0
            
            # Get all team members (not including TLs, Managers, or Admins)
            cursor.execute("SELECT name, role FROM employee WHERE lower(role) NOT LIKE '%leader%' AND lower(role) NOT LIKE '%manager%' AND lower(role) NOT LIKE '%admin%'")
            members_list = cursor.fetchall()
            
            for m_name, m_role in members_list:
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=?", (m_name,))
                m_total = cursor.fetchone()[0] or 0
                cursor.execute("SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status='Completed'", (m_name,))
                m_comp = cursor.fetchone()[0] or 0
                m_pend = max(m_total - m_comp, 0)
                m_rate = int((m_comp / m_total) * 100) if m_total > 0 else 0
                
                # Individual Card
                m_card = Frame(grid_frame, bg=HEADER_BG, padx=18, pady=16, highlightbackground=BORDER_COLOR, highlightthickness=1)
                m_card.grid(row=row, column=member_col, padx=10, pady=10, sticky="nsew")
                
                m_head = Frame(m_card, bg=HEADER_BG)
                m_head.pack(fill=X)
                Label(m_head, text="●", fg=ACCENT_GREEN if m_rate >= 70 else (ACCENT_ORANGE if m_rate >= 30 else ACCENT_RED), 
                      bg=HEADER_BG, font=('Segoe UI', 12)).pack(side=LEFT)
                Label(m_head, text=m_name, font=('Segoe UI', 12, 'bold'), bg=HEADER_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=6)
                Label(m_head, text=m_role, font=('Segoe UI', 8, 'bold'), bg=ACCENT_BLUE, fg=WHITE, padx=6, pady=2).pack(side=RIGHT)
                
                Label(m_card, text=f"Workload Balance: {m_rate}%", font=('Segoe UI', 10), bg=HEADER_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(12, 4))
                
                # Custom Progress Bar
                p_bg = Frame(m_card, bg="#253244", height=6)
                p_bg.pack(fill=X, pady=(0, 12))
                Frame(p_bg, bg=ACCENT_GREEN if m_rate >= 70 else ACCENT_BLUE, height=6).place(x=0, y=0, relwidth=max(0.05, m_rate/100 if m_rate else 0.05))
                
                m_stats = Frame(m_card, bg=HEADER_BG)
                m_stats.pack(fill=X)
                for s_label, s_val, s_color in [("Total", m_total, TEXT_WHITE), ("Done", m_comp, ACCENT_GREEN), ("Pending", m_pend, ACCENT_ORANGE)]:
                    sf = Frame(m_stats, bg=HEADER_BG)
                    sf.pack(side=LEFT, expand=True)
                    Label(sf, text=s_val, font=('Segoe UI', 13, 'bold'), bg=HEADER_BG, fg=s_color).pack()
                    Label(sf, text=s_label, font=('Segoe UI', 8, 'bold'), bg=HEADER_BG, fg=MUTED_TEXT).pack()
                    
                member_col += 1
                if member_col > 1:
                    member_col = 0
                    row += 1

        con.close()

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
            # Ensure no connections (this is tricky in a single thread app, but we close cons immediately)
            # Just copy over
            shutil.copyfile(filename, get_db_path())
            messagebox.showinfo("Success", "Restore complete. Please restart the app.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to restore: {e}")
            
    def load_team_analytics(self):
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()

            tl_name = CURRENT_USER_NAME
            cur.execute("SELECT name, role, department FROM employee WHERE reporting_manager LIKE ?", (f"%{tl_name}%",))
            team_rows = cur.fetchall()

            if not team_rows:
                cur.execute(
                    "SELECT name, role, department FROM employee WHERE lower(role) NOT LIKE '%manager%' AND lower(role) NOT LIKE '%admin%' AND lower(role) NOT LIKE '%leader%' LIMIT 10"
                )
                team_rows = cur.fetchall()

            # ── outer container ──────────────────────────────────────────
            outer = Frame(self.content_area, bg=BG_NAVY)
            outer.pack(fill=BOTH, expand=True)

            # ── page header ──────────────────────────────────────────────
            hdr = Frame(outer, bg=BG_NAVY)
            hdr.pack(fill=X, padx=28, pady=(20, 20))
            Label(hdr, text="Team Intelligence Analytics",
                  font=('Segoe UI', 18, 'bold'), bg=BG_NAVY, fg=TEXT_WHITE).pack(side=LEFT)
            Label(hdr, text=" Performance Deep-Dive Engine",
                  font=('Segoe UI', 10, 'bold'), bg=BG_NAVY, fg=ACCENT_BLUE).pack(side=LEFT, pady=(6, 0))
            
            # ── Analytics Panel (Bordered container) ──────────────────────────
            main_pad = Frame(outer, bg=BG_NAVY)
            main_pad.pack(fill=BOTH, expand=True, padx=28, pady=(0, 28))

            analytics_f = Frame(main_pad, bg=BG_CARD, highlightbackground=BORDER_NAVY, highlightthickness=1)
            analytics_f.pack(fill=BOTH, expand=True)

            # 1. Left Column: Member List
            left_col = Frame(analytics_f, bg=BG_DARK, width=260)
            left_col.pack(side=LEFT, fill=Y)
            left_col.pack_propagate(False)
            
            # Right border of left column
            Frame(analytics_f, bg=BORDER_NAVY, width=1).pack(side=LEFT, fill=Y)

            Label(left_col, text="Team Members", font=('Segoe UI', 12, 'bold'), 
                  bg=BG_DARK, fg=TEXT_WHITE).pack(anchor=W, padx=14, pady=(20, 2))
            Label(left_col, text="Click a member to view profile", font=('Segoe UI', 8), 
                  bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor=W, padx=14, pady=(0, 14))

            # Scrollable list for members
            list_wrap = Frame(left_col, bg=BG_DARK)
            list_wrap.pack(fill=BOTH, expand=True)
            list_cv = Canvas(list_wrap, bg=BG_DARK, highlightthickness=0)
            list_sb = ttk.Scrollbar(list_wrap, orient=VERTICAL, command=list_cv.yview)
            list_inner = Frame(list_cv, bg=BG_DARK)
            list_inner.bind("<Configure>", lambda e: list_cv.configure(scrollregion=list_cv.bbox("all")))
            list_fid = list_cv.create_window((0, 0), window=list_inner, anchor="nw")
            list_cv.configure(yscrollcommand=list_sb.set)
            list_cv.bind("<Configure>", lambda e: list_cv.itemconfig(list_fid, width=e.width))
            list_cv.pack(side=LEFT, fill=BOTH, expand=True)

            # 2. Right Column: Detailed Profile
            right_col = Frame(analytics_f, bg=BG_CARD)
            right_col.pack(side=LEFT, fill=BOTH, expand=True)

            detail_card = Frame(right_col, bg=BG_CARD)
            detail_card.pack(fill=BOTH, expand=True)
            
            # Storage for selection highlight
            self.member_item_frames = {}

            def set_frame_bg(f, color):
                f.config(bg=color)
                for w in f.winfo_children():
                    if w.winfo_class() in ('Frame', 'Label', 'Canvas'):
                        w.config(bg=color)
                    if w.winfo_class() == 'Frame':
                        set_frame_bg(w, color)

            def update_member_details(member_data):
                # Clear right column
                for widget in detail_card.winfo_children():
                    widget.destroy()

                name, role, dept, m_stats, m_perf, attr, hrs, avg_days, risk_data, burnout = member_data
                m_total, m_done, m_ip, m_late, m_pend = m_stats

                # Highlight the selected member in the list
                for m_name, mf in self.member_item_frames.items():
                    if m_name == name:
                        mf.config(highlightbackground="#732020", highlightthickness=1)
                        set_frame_bg(mf, "#2d1315") # Selection background
                        # Emphasize arrow
                        for child in mf.winfo_children():
                            if isinstance(child, Frame):
                                for subchild in child.winfo_children():
                                    if subchild.winfo_class() == 'Label':
                                        if subchild.cget('text') == '▶': 
                                            subchild.config(fg=ACCENT_RED, bg="#2d1315")
                                        else:
                                            subchild.config(bg="#2d1315")
                                    
                    else:
                        mf.config(highlightbackground=BG_DARK, highlightthickness=1)
                        set_frame_bg(mf, BG_DARK)
                        for child in mf.winfo_children():
                            if isinstance(child, Frame):
                                for subchild in child.winfo_children():
                                    if subchild.winfo_class() == 'Label' and subchild.cget('text') == '▶': 
                                        subchild.config(fg=TEXT_MUTED, bg=BG_DARK)

                # ── Profile Header ─────────────────────────────────────
                p_hdr = Frame(detail_card, bg=BG_CARD, padx=28, pady=26)
                p_hdr.pack(fill=X)

                av_char = name[0].upper()
                if av_char in 'DFG': av_fg, av_bg = ACCENT_ORANGE, "#7a3a00"
                elif av_char in 'AKL': av_fg, av_bg = ACCENT_BLUE, "#0a4a2f"
                elif av_char in 'SMR': av_fg, av_bg = ACCENT_GREEN, "#1a1060"
                else: av_fg, av_bg = ACCENT_PURPLE, "#3b1a2f"

                # Avatar
                av_f = Frame(p_hdr, bg=BG_CARD)
                av_f.pack(side=LEFT)
                av = Canvas(av_f, width=56, height=56, bg=BG_CARD, highlightthickness=0)
                av.pack()
                av.create_oval(2, 2, 54, 54, fill=av_bg, outline="#3e4359", width=2)
                av.create_text(28, 28, text=av_char, fill=av_fg, font=('Segoe UI', 16, 'bold'))

                info_f = Frame(p_hdr, bg=BG_CARD, padx=18)
                info_f.pack(side=LEFT, fill=BOTH)
                Label(info_f, text=f"Performance Profile: {name}", font=('Segoe UI', 16, 'bold'), 
                      bg=BG_CARD, fg=TEXT_WHITE).pack(anchor=W)
                Label(info_f, text=f"{role or 'Team Member'} • {dept or 'IT'}  |  Evaluated by: {tl_name}", 
                      font=('Segoe UI', 9), bg=BG_CARD, fg=TEXT_MUTED).pack(anchor=W, pady=(2, 0))

                Frame(detail_card, bg="#3e4359", height=1).pack(fill=X, padx=28)

                # ── Stats Grid (4 Boxes) ──────────────────────────────
                stats_row = Frame(detail_card, bg=BG_CARD, padx=28, pady=24)
                stats_row.pack(fill=X)

                def _stat_box(parent, label, value, color):
                    box = Frame(parent, bg=CARD_DARK, highlightbackground=BORDER_NAVY, highlightthickness=1, width=120, height=80)
                    box.pack(side=LEFT, padx=(0, 10))
                    box.pack_propagate(False)
                    Label(box, text=label, font=('Segoe UI', 8, 'bold'), bg=CARD_DARK, fg=TEXT_SECONDARY).pack(pady=(12, 0))
                    Label(box, text=value, font=('Segoe UI', 18, 'bold'), bg=CARD_DARK, fg=color).pack(pady=(2, 0))

                _stat_box(stats_row, "SCORE", f"{m_perf}%", ACCENT_BLUE)
                _stat_box(stats_row, "COMPLETED", str(m_done), ACCENT_GREEN)
                _stat_box(stats_row, "DELAYED", str(m_late), ACCENT_RED)
                _stat_box(stats_row, "AVG TIME", f"{avg_days}d" if avg_days else "—", ACCENT_PURPLE)

                # ── Autogenerated Insights ─────────────────────────────
                Label(detail_card, text="Autogenerated Insights", font=('Segoe UI', 11, 'bold'), 
                      bg=BG_CARD, fg=TEXT_WHITE).pack(anchor=W, padx=28, pady=(0, 10))

                # Insights Blocks
                def _insight_block(parent, title, text, icon, color, bg, border):
                    block = Frame(parent, bg=bg, padx=16, pady=14, highlightbackground=border, highlightthickness=1)
                    block.pack(fill=X, padx=28, pady=(0, 10))
                    
                    header = Frame(block, bg=bg)
                    header.pack(fill=X)
                    Label(header, text=icon, font=('Segoe UI', 10), bg=bg, fg=color).pack(side=LEFT)
                    Label(header, text=title, font=('Segoe UI', 9, 'bold'), bg=bg, fg=color).pack(side=LEFT, padx=6)
                    
                    Label(block, text=text, font=('Segoe UI', 9), bg=bg, fg="#8a8d9a", wraplength=500, justify=LEFT).pack(anchor=W, pady=(6, 0))

                # Logic for Insights
                if m_perf >= 75:
                    strength = "Strong completion rate with zero delayed tasks — reliable delivery."
                    impro ="Maintain momentum and take on higher complexity tasks next cycle."
                elif m_perf >= 30:
                    strength = "Solid QA coverage with good testing throughput across modules."
                    impro = "Reduce delay rate by improving task hand-off with the dev team."
                elif m_total > 0:
                    strength = "Showing consistent presence and engagement with assigned task modules."
                    impro = "Requires closer supervision on deadline management and task prioritization."
                else:
                    strength = "Task awareness with items currently in progress."
                    impro = "Begin completing assigned tasks and log hours consistently."

                # Logic for Summary
                risk_text = risk_data[0] if risk_data else "UNKNOWN"
                summary = f"{name} shows a {risk_text.lower()} risk profile. Burnout/Load: {burnout.split('  ')[-1]}. Has {m_pend} pending and {m_ip} task(s) in progress."

                _insight_block(detail_card, "Key Strengths", strength, "✓", ACCENT_GREEN, "#152d2b", "#1a3a37")
                _insight_block(detail_card, "Areas for Improvement", impro, "⚠", ACCENT_RED, "#2d1618", "#452023")
                _insight_block(detail_card, "Executive Summary", summary, "★", ACCENT_BLUE, "#172b38", "#1c3848")

            # Render Members in Left Column
            first_member_data = None
            for idx, (name, role, dept) in enumerate(team_rows):
                # Data Calculations
                cur.execute("""
                    SELECT COUNT(*), 
                    SUM(CASE WHEN status='Completed' THEN 1 ELSE 0 END), 
                    SUM(CASE WHEN status='In Progress' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='Delayed' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN status='Pending' THEN 1 ELSE 0 END)
                    FROM tasks WHERE assigned_to=?
                """, (name,))
                tr = cur.fetchone() or (0,0,0,0,0)
                m_stats = (tr[0] or 0, tr[1] or 0, tr[2] or 0, tr[3] or 0, tr[4] or 0)
                m_total, m_done, m_ip, m_late, m_pend = m_stats
                m_perf = int((m_done / m_total) * 100) if m_total else 0
                
                cur.execute("SELECT COUNT(*) FROM attendance WHERE employee_name=?", (name,))
                att_days = cur.fetchone()[0] or 0
                cur.execute("SELECT COUNT(*) FROM attendance WHERE employee_name=? AND lower(status)='present'", (name,))
                att_present = cur.fetchone()[0] or 0
                att_rate = int((att_present / att_days) * 100) if att_days else 0

                cur.execute("SELECT COALESCE(SUM(hours),0) FROM timesheets WHERE employee_name=?", (name,))
                hrs_logged = round(cur.fetchone()[0] or 0, 1)

                cur.execute("SELECT AVG(julianday(completed_date) - julianday(created_date)) FROM tasks WHERE assigned_to=? AND status='Completed'", (name,))
                avg_days_val = cur.fetchone()[0]
                avg_days = round(avg_days_val, 1) if avg_days_val else None

                # Risk
                if m_late > 2: risk_data = ("HIGH", ACCENT_RED, "#2d1618")
                elif m_late > 0: risk_data = ("MEDIUM", ACCENT_ORANGE, "#3b2a1a")
                else: risk_data = ("LOW", ACCENT_GREEN, "#152d2b")

                # Burnout
                workload = m_total - m_done
                if workload > 8: burnout = "⚠  Burnout Risk"
                else: burnout = "✓  Balanced"

                m_payload = (name, role, dept, m_stats, m_perf, att_rate, hrs_logged, avg_days, risk_data, burnout)
                if idx == 0: first_member_data = m_payload

                # List Item UI
                mf = Frame(list_inner, bg=BG_DARK, highlightbackground=BG_DARK, highlightthickness=1, padx=6, pady=8, cursor="hand2")
                mf.pack(fill=X, padx=8, pady=2)
                self.member_item_frames[name] = mf

                av_char = name[0].upper()
                if av_char in 'DFG': av_fg, av_bg = ACCENT_ORANGE, "#7a3a00"
                elif av_char in 'AKL': av_fg, av_bg = ACCENT_BLUE, "#0a4a2f"
                elif av_char in 'SMR': av_fg, av_bg = ACCENT_GREEN, "#1a1060"
                else: av_fg, av_bg = ACCENT_PURPLE, "#3b1a2f"

                av_sm = Canvas(mf, width=38, height=38, bg=BG_DARK, highlightthickness=0)
                av_sm.pack(side=LEFT)
                av_sm.create_oval(2, 2, 36, 36, fill=av_bg, outline="#3e4359", width=2)
                av_sm.create_text(19, 19, text=av_char, fill=av_fg, font=('Segoe UI', 11, 'bold'))

                text_f = Frame(mf, bg=BG_DARK, padx=8)
                text_f.pack(side=LEFT, fill=Y)
                Label(text_f, text=name, font=('Segoe UI', 10, 'bold'), bg=BG_DARK, fg=TEXT_WHITE).pack(anchor=W)
                Label(text_f, text=f"Member • {dept[0:2].upper() if dept else 'IT'}", font=('Segoe UI', 8), bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor=W)

                ind_f = Frame(mf, bg=BG_DARK)
                ind_f.pack(side=RIGHT)
                
                # Pill (like .pm, .pl)
                lcolor = av_fg
                lbg = av_bg
                if role and 'manager' in role.lower():
                    lcolor, lbg = ACCENT_ORANGE, "#4a1a00"
                else:
                    lcolor, lbg = ACCENT_BLUE, "#003020"

                pill_f = Frame(ind_f, bg=lbg, highlightbackground=lbg, highlightthickness=1)
                pill_f.pack(side=LEFT, padx=(0, 4))
                Label(pill_f, text="M", font=('Segoe UI', 7, 'bold'), bg=lbg, fg=lcolor, padx=4, pady=1).pack()

                Label(ind_f, text="▶", font=('Segoe UI', 8), bg=BG_DARK, fg=TEXT_SECONDARY).pack(side=LEFT)

                # Bind click
                def _on_click(e, d=m_payload): update_member_details(d)
                mf.bind("<Button-1>", _on_click)
                for child in mf.winfo_children():
                    child.bind("<Button-1>", _on_click)
                    if isinstance(child, Frame):
                        for subchild in child.winfo_children(): subchild.bind("<Button-1>", _on_click)

            # Initialize with first member
            if first_member_data:
                update_member_details(first_member_data)

            con.close()
        except Exception as e:
            import traceback
            debug_log(f"TEAM_ANALYTICS ERROR: {traceback.format_exc()}")
            messagebox.showerror("Team Analytics Error", str(e))

    def show_member_report_modal(self, name, role, dept, m_total, m_done, m_ip, m_late, m_pend, m_perf, att_rate, hrs_logged, avg_days, risk, burnout_text):
        tl_name = getattr(self, 'user_name', CURRENT_USER_NAME)
        
        modal = Toplevel(self.root)
        modal.title(f"Performance Analysis: {name}")
        modal.geometry("750x660")
        modal.configure(bg=CONTENT_BG)
        modal.transient(self.root)
        modal.grab_set()
        
        # Center Modal
        modal.update_idletasks()
        x = (modal.winfo_screenwidth() // 2) - (750 // 2)
        y = (modal.winfo_screenheight() // 2) - (660 // 2)
        modal.geometry(f"+{x}+{y}")
        
        hdr = Frame(modal, bg=BG_DARK, padx=30, pady=24)
        hdr.pack(fill=X)
        Label(hdr, text=f"Performance Profile: {name}", font=('Segoe UI', 18, 'bold'), bg=BG_DARK, fg=TEXT_WHITE).pack(anchor=W)
        Label(hdr, text=f"{role or 'Employee'}  •  {dept or 'General'}  |  Evaluated by: {tl_name}", font=('Segoe UI', 10), bg=BG_DARK, fg=MUTED_TEXT).pack(anchor=W, pady=(4,0))
        
        body = Frame(modal, bg=CONTENT_BG, padx=30, pady=24)
        body.pack(fill=BOTH, expand=True)
        
        # Stats summary row
        stats_frame = Frame(body, bg=CONTENT_BG)
        stats_frame.pack(fill=X, pady=(0, 24))
        
        items = [
            ("Score", f"{m_perf}%", ACCENT_BLUE),
            ("Completed", str(m_done), ACCENT_GREEN),
            ("Delayed", str(m_late), ACCENT_RED),
            ("Avg Time", f"{avg_days}d" if avg_days else "N/A", ACCENT_PURPLE)
        ]
        
        for lbl, val, col in items:
            cf = Frame(stats_frame, bg=CARD_BG, padx=15, pady=16, highlightbackground="#2e3760", highlightthickness=1)
            cf.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12))
            Label(cf, text=lbl.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack()
            Label(cf, text=val, font=('Segoe UI', 18, 'bold'), bg=CARD_BG, fg=col).pack(pady=(4,0))
            
        # Insights text
        Label(body, text="Autogenerated Insights:", font=('Segoe UI', 12, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 8))
        
        insights = Frame(body, bg=CARD_BG, padx=24, pady=24, highlightbackground="#2e3760", highlightthickness=1)
        insights.pack(fill=BOTH, expand=True)
        
        strengths = "High completion rate" if m_perf >= 70 else "Consistent attendance" if att_rate >= 80 else "Ongoing task involvement"
        areas = "Reduce overdue items." if m_late > 0 else "Improve pace." if (avg_days and avg_days > 5) else "Keep up the good work."
        
        summary = f"Summary: {name} is currently showing a {risk.lower()} risk profile. \n"
        summary += f"Burnout/Load: {burnout_text.split('  ')[-1] if '  ' in burnout_text else burnout_text}. \n"
        summary += f"They have {m_pend} pending and {m_ip} tasks in progress."
        
        Label(insights, text="💪  Key Strengths:\n" + strengths, font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_GREEN, justify=LEFT).pack(anchor=W, pady=(0, 16))
        Label(insights, text="🎯  Areas for Improvement:\n" + areas, font=('Segoe UI', 10), bg=CARD_BG, fg=ACCENT_ORANGE, justify=LEFT).pack(anchor=W, pady=(0, 16))
        Label(insights, text="📌  Executive Summary:\n" + summary, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, justify=LEFT, wraplength=600).pack(anchor=W, pady=(0, 10))
        
        # Share logic
        def share_report():
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                cur.execute('''CREATE TABLE IF NOT EXISTS employee_analysis_reports (
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
                               )''')
                               
                cur.execute("""
                    INSERT INTO employee_analysis_reports 
                    (employee_name, team_leader_name, report_title, performance_score, risk_level, trend_text, strengths, improvement_areas, leader_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (name, tl_name, f"Performance Review - {datetime.now().strftime('%b %Y')}", 
                      m_perf, risk, burnout_text, strengths, areas, summary))
                
                con.commit()
                con.close()
                modal.destroy()
                messagebox.showinfo("Report Shared", f"Performance report successfully generated and shared with '{name}'.")
            except Exception as ex:
                messagebox.showerror("Error", f"Failed to share report: {ex}")
        
        btn_box = Frame(body, bg=CONTENT_BG)
        btn_box.pack(fill=X, pady=(24, 0))
        Button(btn_box, text="Close", font=('Segoe UI', 10), bg=BG_DARK, fg=TEXT_WHITE,
               relief=SOLID, bd=1, padx=24, pady=8, command=modal.destroy, cursor="hand2").pack(side=LEFT)
        Button(btn_box, text="Share Report to Employee ➔", font=('Segoe UI', 10, 'bold'), bg=ACCENT_ORANGE, fg=TEXT_WHITE,
               relief=FLAT, padx=24, pady=8, command=share_report, cursor="hand2").pack(side=RIGHT)


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
        for c in cols:
            tree.heading(c, text=c)
            if c == 'ID': tree.column(c, width=50)
            else: tree.column(c, width=150)
            
        tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrolly = Scrollbar(f, orient=VERTICAL, command=tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        tree.configure(yscrollcommand=scrolly.set)
        
        def refresh():
            for item in tree.get_children(): tree.delete(item)
            # Remove empty state label if exists
            for widget in f.winfo_children():
                if isinstance(widget, Label) and widget.cget("text") == "No pending requests available.":
                    widget.destroy()

            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                # Hierarchy Filtering
                role = CURRENT_USER_ROLE.lower()
                query = "SELECT id, email, role, mobile, timestamp FROM reset_requests WHERE status='Pending'"
                
                if role == 'team leader':
                    query += " AND role IN ('Team Member', 'Employee')"
                elif role == 'project manager':
                    query += " AND role IN ('Team Leader', 'Team Member', 'Employee')"
                # Admin sees all (no extra filter)
                
                cur.execute(query)
                rows = cur.fetchall()
                
                if not rows:
                     Label(f, text="No pending requests available.", bg=CONTENT_BG, fg=MUTED_TEXT, font=('Segoe UI', 12)).place(relx=0.5, rely=0.5, anchor=CENTER)
                else:
                    for row in rows:
                        tree.insert("", END, values=row)
                con.close()
            except Exception as e:
                print(f"Error loading requests: {e}")
            
        refresh()
        
        def approve():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Please select a request to approve.", parent=t.winfo_toplevel())
                return
                
            item = tree.item(sel[0])
            rid = item['values'][0]
            email = item['values'][1]
            
            def submit_approval():
                comment = txt.get().strip()
                try:
                    con = sqlite3.connect(get_db_path())
                    con.execute("UPDATE reset_requests SET status='Approved' WHERE id=?", (rid,))
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                               (ts, CURRENT_USER_NAME, "Reset Approved", f"Approved for {email}. Comment: {comment}"))
                    con.commit()
                    con.close()
                    dialog.destroy()
                    messagebox.showinfo("Success", "Reset request approved.", parent=t.winfo_toplevel())
                    refresh()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=t.winfo_toplevel())

            dialog = Toplevel(t.winfo_toplevel())
            dialog.title("Approve Reset")
            dialog.geometry("400x250")
            dialog.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
            dialog.resizable(True, True)  # FIX 7: allow resize so no overflow
            dialog.configure(bg=BG_CARD)
            dialog.resizable(False, False)
            dialog.transient(t.winfo_toplevel())
            dialog.grab_set()

            # Center
            mx = t.winfo_rootx() + (t.winfo_width()//2) - 200
            my = t.winfo_rooty() + (t.winfo_height()//2) - 125
            dialog.geometry(f"400x250+{mx}+{my}")

            header = Frame(dialog, bg=HEADER_BG, pady=10)
            header.pack(fill=X)
            Label(header, text="APPROVE RESET", font=('Rajdhani', 12, 'bold'), bg=HEADER_BG, fg=WHITE).pack()

            body = Frame(dialog, bg=BG_CARD, padx=30, pady=20)
            body.pack(fill=BOTH, expand=True)

            Label(body, text="Optional Comment:", font=('Segoe UI', 9), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W)
            txt = Entry(body, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), relief=FLAT, highlightbackground="#2e3760", highlightthickness=1, insertbackground=WHITE)
            txt.pack(fill=X, pady=(5, 20), ipady=8)
            txt.focus_set()

            Button(body, text="CONFIRM APPROVAL", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT, pady=8, command=submit_approval).pack(fill=X)
            return
            
            try:
                con = sqlite3.connect(get_db_path())
                con.execute("UPDATE reset_requests SET status='Approved' WHERE id=?", (rid,))
                
                # Audit Log
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                           (ts, CURRENT_USER_NAME, "Reset Approved", f"Approved for {email}. Comment: {comment}"))
                
                con.commit()
                con.close()
                
                messagebox.showinfo("Success", "Action completed successfully.", parent=t.winfo_toplevel())
                refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=t.winfo_toplevel())
        
        # Double Click to Approve or Reject
        def on_double_click(event):
            sel = tree.selection()
            if not sel: return
            
            # Pop the message approve or not approve
            choice = messagebox.askyesnocancel("Action Required", "Do you want to Approve this request?\n\nYes: Approve\nNo: Reject", parent=t.winfo_toplevel())
            
            if choice is True: # Yes -> Approve
                approve()
            elif choice is False: # No -> Reject
                reject()
        
        tree.bind("<Double-1>", on_double_click)
            
        def reject():
            sel = tree.selection()
            if not sel:
                messagebox.showwarning("Warning", "Please select a request to reject.", parent=t.winfo_toplevel())
                return
                
            def submit_rejection():
                comment = txt.get().strip()
                if not comment:
                    messagebox.showwarning("Required", "Reason is required for rejection.")
                    return
                
                if not messagebox.askyesno("Confirm", "Reject this request?", parent=dialog): return

                try:
                    con = sqlite3.connect(get_db_path())
                    con.execute("DELETE FROM reset_requests WHERE id=?", (rid,))
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                               (ts, CURRENT_USER_NAME, "Reset Rejected", f"Rejected for {email}. Reason: {comment}"))
                    con.commit()
                    con.close()
                    dialog.destroy()
                    messagebox.showinfo("Success", "Reset request rejected.", parent=t.winfo_toplevel())
                    refresh()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=t.winfo_toplevel())

            dialog = Toplevel(t.winfo_toplevel())
            dialog.title("Reject Reset")
            dialog.geometry("400x250")
            dialog.minsize(400, 400)  # FIX 7: prevent content clipping when UI changes
            dialog.resizable(True, True)  # FIX 7: allow resize so no overflow
            dialog.configure(bg=BG_CARD)
            dialog.resizable(False, False)
            dialog.transient(t.winfo_toplevel())
            dialog.grab_set()

            # Center
            mx = t.winfo_rootx() + (t.winfo_width()//2) - 200
            my = t.winfo_rooty() + (t.winfo_height()//2) - 125
            dialog.geometry(f"400x250+{mx}+{my}")

            header = Frame(dialog, bg=HEADER_BG, pady=10)
            header.pack(fill=X)
            Label(header, text="REJECT RESET", font=('Rajdhani', 12, 'bold'), bg=HEADER_BG, fg=WHITE).pack()

            body = Frame(dialog, bg=BG_CARD, padx=30, pady=20)
            body.pack(fill=BOTH, expand=True)

            Label(body, text="Reason for Rejection:", font=('Segoe UI', 9), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W)
            txt = Entry(body, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), relief=FLAT, highlightbackground="#2e3760", highlightthickness=1, insertbackground=WHITE)
            txt.pack(fill=X, pady=(5, 20), ipady=8)
            txt.focus_set()

            Button(body, text="CONFIRM REJECTION", bg=ACCENT_RED, fg=WHITE, font=('Segoe UI', 10, 'bold'), relief=FLAT, pady=8, command=submit_rejection).pack(fill=X)
            return
            
            if not messagebox.askyesno("Confirm", "Reject this request?", parent=t.winfo_toplevel()): return
            
            item = tree.item(sel[0])
            rid = item['values'][0]
            email = item['values'][1]
            
            try:
                con = sqlite3.connect(get_db_path())
                con.execute("DELETE FROM reset_requests WHERE id=?", (rid,))
                
                # Audit Log
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                con.execute("INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?, ?, ?, ?)", 
                           (ts, CURRENT_USER_NAME, "Reset Rejected", f"Rejected for {email}. Reason: {comment}"))
                           
                con.commit()
                con.close()
                messagebox.showinfo("Success", "Action completed successfully.", parent=t.winfo_toplevel())
                refresh()
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=t.winfo_toplevel())
            
        # Fix: Use 'white' instead of undefined WHITE variable
        Button(btn_frame, text="Approve Request", command=approve, bg=ACCENT_GREEN, fg='white', font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(side=LEFT, padx=(0, 10))
        Button(btn_frame, text="Reject Request", command=reject, bg=ACCENT_RED, fg='white', font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(side=LEFT, padx=(0, 10))
        Button(btn_frame, text="Refresh", command=refresh, bg=ACCENT_BLUE, fg='white', font=('Segoe UI', 11), relief=FLAT).pack(side=LEFT)
        
        if not is_page:
            Button(btn_frame, text="Close", command=t.destroy, bg=INPUT_BG, fg='white', font=('Segoe UI', 11), relief=FLAT).pack(side=RIGHT)

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
            ("🏗️ Active Projects", str(proj_stats.get('total_projects', 0)), ACCENT_GREEN),
            ("📊 Tasks Completed", f"{task_stats.get('completion_rate', 0)}%", ACCENT_ORANGE),
            ("⚡ Avg Productivity", f"{emp_summary.get('avg_productivity', 0)}", ACCENT_PURPLE)
        ]

        for label, value, color in kpi_data:
            card = Frame(kpi_frame, bg=CARD_BG, padx=24, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
            card.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(card, text=label, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
            Label(card, text=value, font=('Segoe UI', 28, 'bold'), bg=CARD_BG, fg=color).pack(anchor=W, pady=(8, 0))

        # ========== ML DELAY PREDICTION SECTION ==========
        ml_frame = Frame(scrollable_frame, bg=CARD_BG, padx=20, pady=20, highlightbackground=ACCENT_RED, highlightthickness=1)
        ml_frame.pack(fill=X, padx=30, pady=20)
        
        Label(ml_frame, text="🔬 AI-Powered Project Risk Analysis", font=('Segoe UI', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(ml_frame, text="Dynamic, real-time prediction based on situational performance and workload.", 
              font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W, pady=(5, 15))
        
        # Prediction Logic
        model = get_ml_model()
        if not model:
            Label(ml_frame, text="AI Model not found. Please train the model first.", bg=CARD_BG, fg=ACCENT_ORANGE).pack(pady=20)
        elif not project_risks:
            Label(ml_frame, text="No ongoing projects to analyze.", bg=CARD_BG, fg=MUTED_TEXT).pack(pady=20)
        else:
            # Table for predictions
            pred_table = Frame(ml_frame, bg=CARD_BG)
            pred_table.pack(fill=X)
            
            headers = ["Project Name", "Team Leader", "Complexity", "Current Workload", "Delay Risk", "Status"]
            for i, h in enumerate(headers):
                Label(pred_table, text=h, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).grid(row=0, column=i, padx=15, pady=10, sticky=W)
            
            for idx, risk_item in enumerate(project_risks):
                # Be defensive: project_risks can arrive as tuple/list/dict depending on source version.
                pid = None
                pname = "Unknown Project"
                leader = "N/A"
                complexity = 1
                workload = 0
                avail = 0.5

                try:
                    if isinstance(risk_item, dict):
                        pid = risk_item.get('project_id') or risk_item.get('id')
                        pname = risk_item.get('project_name') or risk_item.get('name') or pname
                        leader = risk_item.get('team_leader') or risk_item.get('leader') or leader
                        complexity = risk_item.get('complexity', complexity)
                        workload = risk_item.get('workload', workload)
                        avail = risk_item.get('availability', risk_item.get('resource_availability', avail))
                    elif isinstance(risk_item, (list, tuple)):
                        if len(risk_item) >= 6:
                            pid, pname, leader, complexity, workload, avail = risk_item[:6]
                        elif len(risk_item) == 5:
                            pid, pname, leader, complexity, workload = risk_item
                        elif len(risk_item) == 4:
                            pid, pname, leader, complexity = risk_item
                        elif len(risk_item) == 3:
                            pid, pname, leader = risk_item
                        elif len(risk_item) == 2:
                            pid, pname = risk_item
                        elif len(risk_item) == 1:
                            pname = risk_item[0] or pname
                    else:
                        pname = str(risk_item) if risk_item else pname
                except Exception:
                    # Keep analytics alive even if one row is malformed.
                    pass

                try:
                    complexity = float(complexity)
                except Exception:
                    complexity = 1.0
                try:
                    workload = float(workload)
                except Exception:
                    workload = 0.0
                try:
                    avail = float(avail)
                except Exception:
                    avail = 0.5

                # Prepare data for prediction
                # Feature order: priority, estimated_days, complexity, resource_availability, team_experience, workload
                # Using some heuristics since we already pre-calculated complexity and availability in background
                # Fast heuristic risk estimate (kept local to avoid heavy model inference on UI thread).
                prob = 0.3 + (complexity * 0.1) + (workload * 0.05) - (avail * 0.2)
                prob = min(0.95, max(0.05, prob))

                risk_lvl = "Low"
                risk_color = ACCENT_GREEN
                if prob > 0.7:
                    risk_lvl = "Critical"
                    risk_color = ACCENT_RED
                elif prob > 0.4:
                    risk_lvl = "Medium"
                    risk_color = ACCENT_ORANGE

                # Render a row for every analyzed project (Low/Medium/Critical).
                r_idx = idx + 1
                Label(pred_table, text=pname, bg=CARD_BG, font=('Segoe UI', 10, 'bold'), fg=TEXT_WHITE).grid(row=r_idx, column=0, padx=15, pady=8, sticky=W)
                Label(pred_table, text=leader or "N/A", bg=CARD_BG, fg=MUTED_TEXT, font=('Segoe UI', 10)).grid(row=r_idx, column=1, padx=15, pady=8, sticky=W)

                complex_frame = Frame(pred_table, bg="#1e293b", padx=8, pady=4)
                complex_frame.grid(row=r_idx, column=2, padx=15, pady=8, sticky=W)
                Label(complex_frame, text=f"• {complexity}/5 Complexity", bg="#1e293b", fg=TEXT_WHITE, font=('Segoe UI', 9)).pack()

                Label(pred_table, text=f"{workload} Tasks", bg=CARD_BG, fg=TEXT_WHITE, font=('Segoe UI', 10)).grid(row=r_idx, column=3, padx=15, pady=8, sticky=W)

                risk_frame = Frame(pred_table, bg=risk_color, padx=12, pady=4)
                risk_frame.grid(row=r_idx, column=4, padx=15, pady=8, sticky=W)
                Label(risk_frame, text=f"{int(prob*100)}% RISK", bg=risk_color, fg=WHITE, font=('Segoe UI', 9, 'bold')).pack()

                Label(pred_table, text=risk_lvl.upper(), bg=CARD_BG, fg=risk_color, font=('Segoe UI', 10, 'bold')).grid(row=r_idx, column=5, padx=15, pady=8, sticky=W)
            
            # Success

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

        insights_frame = Frame(scrollable_frame, bg=CONTENT_BG)
        insights_frame.pack(fill=X, padx=30, pady=(0, 20))
        insights_header = Frame(insights_frame, bg=CONTENT_BG)
        insights_header.pack(fill=X, pady=(0, 10))
        Label(insights_header, text="Executive Insights", font=('Segoe UI', 18, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(insights_header, text="Stronger interpretation of trend, delivery pressure, and team health.",
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=MUTED_TEXT).pack(side=RIGHT, pady=(6, 0))

        insight_row = Frame(insights_frame, bg=CONTENT_BG)
        insight_row.pack(fill=X)

        def make_insight_card(parent, title, value, note, accent, icon=""):
            card = Frame(parent, bg=CARD_BG, padx=22, pady=20, highlightbackground=accent, highlightthickness=1)
            card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 15))
            
            hdr = Frame(card, bg=CARD_BG)
            hdr.pack(fill=X)
            Label(hdr, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            if icon: Label(hdr, text=icon, font=('Segoe UI', 12), bg=CARD_BG).pack(side=RIGHT)

            Label(card, text=value, font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg=accent).pack(anchor=W, pady=(12, 6))
            Label(card, text=note, font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, wraplength=220, justify=LEFT).pack(anchor=W)
            return card

        make_insight_card(insight_row, momentum_title, momentum_value, momentum_note, momentum_color, "📈")
        make_insight_card(insight_row, risk_title, risk_value, risk_note, risk_color, "🛡️")
        make_insight_card(insight_row, health_title, health_value, health_note, health_color, "🩺")
        make_insight_card(insight_row, "Recommended Action", action_value, action_note, action_color, "🎯")

        # ========== CHARTS ROW 1 ==========
        charts_row1 = Frame(scrollable_frame, bg=CONTENT_BG)
        charts_row1.pack(fill=X, padx=30, pady=(0, 20))
        charts_row1.columnconfigure(0, weight=1)
        charts_row1.columnconfigure(1, weight=1)

        # --- Monthly Trends Chart ---
        trends_card = Frame(charts_row1, bg=CARD_BG, padx=20, pady=20)
        trends_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        Label(trends_card, text="Monthly Performance Trends", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))

        if trends.get('months'):
            trend_canvas = Canvas(trends_card, bg=CARD_BG, height=200, highlightthickness=0)
            trend_canvas.pack(fill=X)

            months = trends['months']
            productivity = trends['avg_productivity']

            # Draw line chart
            if len(months) > 0:
                max_prod = max(productivity) if productivity else 1
                min_prod = min(productivity) if productivity else 0
                range_prod = max_prod - min_prod if max_prod != min_prod else 1

                chart_width = 400
                chart_height = 150
                padding = 30

                # Draw grid lines
                for i in range(5):
                    y = padding + (chart_height * i / 4)
                    trend_canvas.create_line(padding, y, padding + chart_width, y, fill="#3d3c3f", dash=(2, 2))

                # Draw line
                points = []
                for i, val in enumerate(productivity):
                    x = padding + (i * chart_width / max(len(months) - 1, 1))
                    y = padding + chart_height - ((val - min_prod) / range_prod * chart_height)
                    points.append((x, y))

                if len(points) > 1:
                    for i in range(len(points) - 1):
                        trend_canvas.create_line(points[i][0], points[i][1], points[i+1][0], points[i+1][1],
                                                fill=ACCENT_BLUE, width=3)
                    for x, y in points:
                        trend_canvas.create_oval(x-4, y-4, x+4, y+4, fill=ACCENT_BLUE, outline=WHITE)

                # Labels
                for i, month in enumerate(months):
                    x = padding + (i * chart_width / max(len(months) - 1, 1))
                    trend_canvas.create_text(x, padding + chart_height + 15, text=month[-2:], fill=MUTED_TEXT, font=('Segoe UI', 9))
        else:
            Label(trends_card, text="No trend data available", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=50)

        # --- Performance Distribution Bar Chart ---
        dist_card = Frame(charts_row1, bg=CARD_BG, padx=20, pady=20)
        dist_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        Label(dist_card, text="Performance Distribution", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))

        if perf_dist:
            dist_canvas = Canvas(dist_card, bg=CARD_BG, height=200, highlightthickness=0)
            dist_canvas.pack(fill=X)

            categories = ['Excellent\n(90+)', 'Good\n(75-89)', 'Average\n(60-74)', 'Poor\n(<60)']
            values = [perf_dist.get('excellent', 0), perf_dist.get('good', 0),
                     perf_dist.get('average', 0), perf_dist.get('poor', 0)]
            colors = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_ORANGE, ACCENT_RED]

            max_val = max(values) if values else 1
            bar_width = 60
            spacing = 40
            start_x = 50
            chart_height = 150

            for i, (cat, val, col) in enumerate(zip(categories, values, colors)):
                x = start_x + i * (bar_width + spacing)
                bar_height = (val / max_val) * chart_height if max_val > 0 else 0

                # Bar
                dist_canvas.create_rectangle(x, 180 - bar_height, x + bar_width, 180, fill=col, outline="")
                # Value label
                dist_canvas.create_text(x + bar_width/2, 170 - bar_height, text=str(val), fill=WHITE, font=('Segoe UI', 10, 'bold'))
                # Category label
                dist_canvas.create_text(x + bar_width/2, 195, text=cat, fill=MUTED_TEXT, font=('Segoe UI', 9), justify=CENTER)
        else:
            Label(dist_card, text="No performance data", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=50)

        # ========== CHARTS ROW 2 ==========
        charts_row2 = Frame(scrollable_frame, bg=CONTENT_BG)
        charts_row2.pack(fill=X, padx=30, pady=(0, 20))
        charts_row2.columnconfigure(0, weight=1)
        charts_row2.columnconfigure(1, weight=1)

        # --- Project Status Pie Chart ---
        proj_card = Frame(charts_row2, bg=CARD_BG, padx=20, pady=20)
        proj_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        Label(proj_card, text="Project Status", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))

        proj_dist = proj_stats.get('status_distribution', {})
        if proj_dist:
            proj_canvas = Canvas(proj_card, bg=CARD_BG, height=200, highlightthickness=0)
            proj_canvas.pack(fill=X)

            colors_pie = [ACCENT_GREEN, ACCENT_BLUE, ACCENT_ORANGE, ACCENT_RED, ACCENT_PURPLE]
            total = sum(proj_dist.values())
            start_angle = 0
            center_x, center_y = 225, 100
            radius = 70

            for i, (status, count) in enumerate(proj_dist.items()):
                extent = (count / total) * 360 if total > 0 else 0
                color = colors_pie[i % len(colors_pie)]
                proj_canvas.create_arc(center_x - radius, center_y - radius,
                                      center_x + radius, center_y + radius,
                                      start=start_angle, extent=extent, fill=color, outline=CARD_BG, width=2)
                start_angle += extent

            # Legend
            legend_y = 30
            for i, (status, count) in enumerate(proj_dist.items()):
                color = colors_pie[i % len(colors_pie)]
                proj_canvas.create_rectangle(340, legend_y + i*25, 355, legend_y + 15 + i*25, fill=color, outline="")
                proj_canvas.create_text(365, legend_y + 7 + i*25, text=f"{status}: {count}", fill=MUTED_TEXT, font=('Segoe UI', 9), anchor=W)
        else:
            Label(proj_card, text="No project data", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=50)

        # --- Task Completion Analytics ---
        task_card = Frame(charts_row2, bg=CARD_BG, padx=20, pady=20)
        task_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        Label(task_card, text="Task Analytics", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))

        task_breakdown = task_stats.get('status_breakdown', {})
        if task_breakdown:
            task_canvas = Canvas(task_card, bg=CARD_BG, height=200, highlightthickness=0)
            task_canvas.pack(fill=X)

            # Horizontal bar chart for tasks
            statuses = list(task_breakdown.keys())[:5]
            counts = [task_breakdown[s] for s in statuses]
            max_count = max(counts) if counts else 1

            bar_height = 25
            start_y = 20

            for i, (status, count) in enumerate(zip(statuses, counts)):
                y = start_y + i * 35
                bar_width = (count / max_count) * 250

                # Status label
                task_canvas.create_text(10, y + bar_height/2, text=status[:15], fill=MUTED_TEXT, font=('Segoe UI', 9), anchor=W)
                # Bar
                task_canvas.create_rectangle(100, y, 100 + bar_width, y + bar_height, fill=ACCENT_BLUE, outline="")
                # Value
                task_canvas.create_text(100 + bar_width + 10, y + bar_height/2, text=str(count), fill=TEXT_WHITE, font=('Segoe UI', 9, 'bold'), anchor=W)
        else:
            Label(task_card, text="No task data", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=50)

        # ========== TOP PERFORMERS & RISKS ==========
        lists_row = Frame(scrollable_frame, bg=CONTENT_BG)
        lists_row.pack(fill=X, padx=30, pady=(0, 20))
        lists_row.columnconfigure(0, weight=1)
        lists_row.columnconfigure(1, weight=1)

        # --- Top Performers ---
        top_card = Frame(lists_row, bg=CARD_BG, padx=20, pady=20)
        top_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        Label(top_card, text="Top Performers", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W, pady=(0, 15))

        top_performers = emp_summary.get('top_performers', [])
        if top_performers:
            for i, emp in enumerate(top_performers[:5]):
                row = Frame(top_card, bg=CARD_BG)
                row.pack(fill=X, pady=5)
                rank_color = ACCENT_GREEN if i < 3 else MUTED_TEXT
                Label(row, text=f"#{i+1}", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=rank_color, width=3).pack(side=LEFT)
                Label(row, text=emp.get('employee_name', 'Unknown'), font=('Segoe UI', 11), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT, padx=(10, 0))
                Label(row, text=f"{emp.get('productivity_score', 0):.1f}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(side=RIGHT)
        else:
            Label(top_card, text="No performance data", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=20)

        # --- At Risk Employees ---
        risk_card = Frame(lists_row, bg=CARD_BG, padx=20, pady=20)
        risk_card.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        Label(risk_card, text="Performance Risk Alert", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(anchor=W, pady=(0, 15))

        if at_risk:
            for emp in at_risk[:5]:
                row = Frame(risk_card, bg=CARD_BG)
                row.pack(fill=X, pady=5)
                Label(row, text=emp.get('name', 'Unknown'), font=('Segoe UI', 11), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                Label(row, text=f"↓ {emp.get('decline', 0):.1f}%", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_RED).pack(side=RIGHT)
        else:
            Label(risk_card, text="All employees performing well", font=('Segoe UI', 11), bg=CARD_BG, fg=ACCENT_GREEN).pack(pady=20)

        # ========== DEPARTMENT STATS ==========
        dept_card = Frame(scrollable_frame, bg=CARD_BG, padx=20, pady=20)
        dept_card.pack(fill=X, padx=30, pady=(0, 20))
        Label(dept_card, text="Department Performance", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 15))

        dept_stats = emp_summary.get('department_stats', [])
        if dept_stats:
            dept_canvas = Canvas(dept_card, bg=CARD_BG, height=100, highlightthickness=0)
            dept_canvas.pack(fill=X)

            card_width = 180
            spacing = 20
            start_x = 20

            for i, dept in enumerate(dept_stats[:4]):
                x = start_x + i * (card_width + spacing)
                # Card background
                dept_canvas.create_rectangle(x, 0, x + card_width, 90, fill="#2d2d30", outline=BORDER_COLOR, width=1)
                # Department name
                dept_canvas.create_text(x + card_width/2, 25, text=dept.get('department', 'Unknown'), fill=TEXT_WHITE, font=('Segoe UI', 12, 'bold'))
                # Count
                dept_canvas.create_text(x + card_width/2, 50, text=f"{dept.get('count', 0)} employees", fill=MUTED_TEXT, font=('Segoe UI', 10))
                # Avg score
                score = dept.get('avg_score', 0) or 0
                color = ACCENT_GREEN if score >= 75 else ACCENT_ORANGE if score >= 60 else ACCENT_RED
                dept_canvas.create_text(x + card_width/2, 75, text=f"Avg: {score:.1f}", fill=color, font=('Segoe UI', 11, 'bold'))
        else:
            Label(dept_card, text="No department data", font=('Segoe UI', 11, 'italic'), bg=CARD_BG, fg=MUTED_TEXT).pack(pady=20)

        # ========== AI/ML SECTION (Original) ==========
        ai_header = Frame(scrollable_frame, bg=CONTENT_BG)
        ai_header.pack(fill=X, padx=30, pady=(20, 10))
        Label(ai_header, text="AI Model Analytics", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)

        ai_grid = Frame(scrollable_frame, bg=CONTENT_BG)
        ai_grid.pack(fill=X, padx=30, pady=(0, 20))
        ai_grid.columnconfigure(0, weight=1)
        ai_grid.columnconfigure(1, weight=1)

        # AI Model Status
        ai = self.get_ai_engine()
        global_data = ai.get_global_analytics() if ai else {}
        model_info = global_data.get('model_info', {})

        ai_status = Frame(ai_grid, bg=CARD_BG, padx=20, pady=20)
        ai_status.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        Label(ai_status, text="Model Status", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=ACCENT_BLUE).pack(anchor=W, pady=(0, 15))

        ai_metrics = [
            ("Algorithm", model_info.get('type', 'N/A')),
            ("Framework", model_info.get('framework', 'N/A')),
            ("Status", "Active" if model_info.get('status') == "Active" else "Inactive"),
            ("Last Updated", model_info.get('last_updated', 'N/A')),
            ("Training Samples", str(model_info.get('records_trained', 0)))
        ]
        for label, value in ai_metrics:
            row = Frame(ai_status, bg=CARD_BG)
            row.pack(fill=X, pady=3)
            Label(row, text=label, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(row, text=value, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=RIGHT)

        # Model Performance
        ai_perf = Frame(ai_grid, bg=CARD_BG, padx=20, pady=20)
        ai_perf.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        Label(ai_perf, text="Model Performance", font=('Segoe UI', 14, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN).pack(anchor=W, pady=(0, 15))

        perf_metrics = [
            ("Accuracy", model_info.get('accuracy', 'N/A'), ACCENT_GREEN),
            ("MAE", str(model_info.get('mae', 'N/A')), ACCENT_BLUE),
            ("R² Score", str(model_info.get('r2_score', 'N/A')), ACCENT_ORANGE)
        ]
        for name, val, color in perf_metrics:
            row = Frame(ai_perf, bg=CARD_BG)
            row.pack(fill=X, pady=5)
            Label(row, text=name, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(side=LEFT)
            Label(row, text=val, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=color).pack(side=RIGHT)

        # Action Buttons
        btn_frame = Frame(scrollable_frame, bg=CONTENT_BG)
        btn_frame.pack(fill=X, padx=30, pady=(0, 30))

        def trigger_retrain():
            if not ai:
                messagebox.showerror("AI Unavailable", "AI engine is not available")
                return
            if messagebox.askyesno("Confirm", "Retrain the ML model?"):
                res = ai.train()
                messagebox.showinfo("Success", f"Model retrained!\nMAE: {res.get('mae')}\nR²: {res.get('r2_score')}")
                self.load_analytics()

        Button(btn_frame, text="Retrain Model", bg=ACCENT_BLUE, fg=WHITE, font=('Segoe UI', 10, 'bold'),
               relief=FLAT, padx=20, pady=10, command=trigger_retrain).pack(side=LEFT, padx=(0, 10))

        def export_data():
            from analytics_engine import export_analytics_to_json
            if export_analytics_to_json(data, 'analytics_export.json'):
                messagebox.showinfo("Success", "Analytics exported to analytics_export.json")
            else:
                messagebox.showerror("Error", "Failed to export analytics")

        Button(btn_frame, text="Export Data", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 10, 'bold'),
               relief=FLAT, padx=20, pady=10, command=export_data).pack(side=LEFT)

        # Footer
        Label(scrollable_frame, text="Powered by Enhanced Analytics Engine v2.0 | Scikit-learn Ensemble",
              font=('Segoe UI', 9), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=20)

    def load_review_tasks(self):
        # Implementation of Task Review & Approval System
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, padx=30, pady=20)
        
        Label(container, text="Task Review & Approval", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        # Scrollable Area
        canvas = Canvas(container, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=CONTENT_BG)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Find tasks in 'Pending Approval' status for projects led by this TL
            cur.execute("""
                SELECT t.id, t.title, t.assigned_to, p.name, t.priority, t.due_date 
                FROM tasks t
                JOIN projects p ON t.project_id = p.id
                WHERE t.status = 'Pending Approval' AND p.team_leader LIKE ?
            """, (f"%{CURRENT_USER_NAME}%",))
            tasks = cur.fetchall()
            
            if not tasks:
                Label(scrollable_frame, text="No tasks currently pending review.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=50)
            else:
                for tid, title, emp, proj, prio, due in tasks:
                    card = Frame(scrollable_frame, bg=CARD_BG, padx=20, pady=15, highlightbackground=BORDER_COLOR, highlightthickness=1)
                    card.pack(fill=X, pady=5)
                    
                    info = Frame(card, bg=CARD_BG)
                    info.pack(fill=X)
                    Label(info, text=title, font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    Label(info, text=f"Priority: {prio}", font=('Segoe UI', 9), bg=CARD_BG, fg=ACCENT_ORANGE).pack(side=LEFT, padx=15)
                    
                    details = Label(card, text=f"Employee: {emp} | Project: {proj} | Due: {due}", font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT)
                    details.pack(anchor=W, pady=5)
                    
                    actions = Frame(card, bg=CARD_BG)
                    actions.pack(fill=X, pady=(10, 0))
                    
                    def approve(t_id=tid):
                        if messagebox.askyesno("Approve Task", "Mark this task as officially Completed?"):
                            c = sqlite3.connect(get_db_path())
                            cu = c.cursor()
                            cu.execute("UPDATE tasks SET status='Completed' WHERE id=?", (t_id,))
                            c.commit(); c.close()
                            self.load_review_tasks()

                    def reject(t_id=tid):
                        rej_win = Toplevel(self.root)
                        rej_win.title("Reject Task")
                        rej_win.geometry("500x320")
                        rej_win.minsize(450, 300)
                        rej_win.resizable(True, True)
                        rej_win.configure(bg=BG_CARD)
                        rej_win.transient(self.root)
                        rej_win.grab_set()

                        # Brand Stripe
                        stripe = Frame(rej_win, bg=ACCENT_RED, height=3)
                        stripe.pack(fill=X)

                        # Center
                        mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 250
                        my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 160
                        rej_win.geometry(f"500x320+{mx}+{my}")

                        header = Frame(rej_win, bg=HEADER_BG, pady=15)
                        header.pack(fill=X)
                        Label(header, text="REJECT TASK", font=('Rajdhani', 14, 'bold'), 
                              bg=HEADER_BG, fg=WHITE).pack()

                        body = Frame(rej_win, bg=BG_CARD, padx=40, pady=25)
                        body.pack(fill=BOTH, expand=True)

                        Label(body, text="Reason for rejection / required changes:", font=('Segoe UI', 10), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 10))
                        
                        txt_container = Frame(body, bg="#1a2035", highlightbackground="#2e3760", highlightthickness=1)
                        txt_container.pack(fill=BOTH, expand=True)
                        
                        rej_text = Text(txt_container, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), 
                                       relief=FLAT, padx=15, pady=10, insertbackground=WHITE, height=4)
                        rej_text.pack(fill=BOTH, expand=True)
                        rej_text.focus_set()

                        def submit_rejection():
                            comment = rej_text.get("1.0", "end-1c").strip()
                            if comment:
                                try:
                                    c = sqlite3.connect(get_db_path())
                                    cu = c.cursor()
                                    cu.execute("UPDATE tasks SET status='Ongoing', review_comments=? WHERE id=?", (comment, t_id))
                                    c.commit(); c.close()
                                    rej_win.destroy()
                                    messagebox.showinfo("Success", "Task rejected with feedback.")
                                    self.load_review_tasks()
                                except Exception as e:
                                    messagebox.showerror("Error", f"Could not save rejection: {e}")
                            else:
                                messagebox.showwarning("Incomplete", "Please provide a reason for rejection.")

                        footer = Frame(rej_win, bg=BG_CARD, pady=20)
                        footer.pack(fill=X)
                        
                        btn_rej = Button(footer, text="REJECT WITH FEEDBACK", bg=ACCENT_RED, fg=WHITE, 
                                       font=('Segoe UI', 10, 'bold'), relief=FLAT, padx=30, pady=10,
                                       command=submit_rejection)
                        btn_rej.pack()

                    Button(actions, text="Approve", bg=ACCENT_GREEN, fg=WHITE, relief=FLAT, padx=15, command=approve).pack(side=LEFT)
                    Button(actions, text="Reject", bg=ACCENT_RED, fg=WHITE, relief=FLAT, padx=15, command=reject).pack(side=LEFT, padx=10)
            con.close()
        except Exception as e:
            Label(scrollable_frame, text=f"Error: {e}", bg=CONTENT_BG, fg=ACCENT_RED).pack()

    def load_team_leaves(self):
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, padx=30, pady=20)
        Label(container, text="Team Leave Management", font=('Segoe UI', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Show leaves for team members
            cur.execute("""
                SELECT id, member_name, start_date, end_date, reason, status, leave_type 
                FROM leave_requests 
                WHERE member_name IN (
                    SELECT DISTINCT name FROM employee 
                    WHERE reporting_manager = ?
                    OR name IN (SELECT DISTINCT assigned_to FROM tasks t JOIN projects p ON t.project_id=p.id WHERE p.team_leader LIKE ?)
                )
                  AND member_name != ?
                ORDER BY id DESC
            """, (CURRENT_USER_NAME, f"%{CURRENT_USER_NAME}%", CURRENT_USER_NAME))
            leaves = cur.fetchall()
            
            if not leaves:
                Label(container, text="No leave requests from your team.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=50)
            else:
                for lid, name, start, end, reason, status, l_type in leaves:
                    card = Frame(container, bg=CARD_BG, padx=25, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    header = Frame(card, bg=CARD_BG)
                    header.pack(fill=X)
                    
                    Label(header, text=f"{name} - {l_type}", font=('Rajdhani', 13, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    status_color = "#f59e0b" if status == 'Pending' else ("#10b981" if status == 'Approved' else "#e03030")
                    status_badge = Frame(header, bg=status_color, padx=10, pady=2)
                    status_badge.pack(side=RIGHT)
                    Label(status_badge, text=status.upper(), font=('Segoe UI', 8, 'bold'), bg=status_color, fg=WHITE).pack()
                    
                    details = Frame(card, bg=CARD_BG, pady=10)
                    details.pack(fill=X)
                    Label(details, text=f"Duration: {start} to {end}", font=('Segoe UI', 10), bg=CARD_BG, fg="#9aa3c2").pack(anchor=W)
                    Label(details, text=f"Reason: {reason}", font=('Segoe UI', 10), bg=CARD_BG, fg=TEXT_WHITE, wraplength=700, justify=LEFT).pack(anchor=W, pady=(5,0))
                    
                    if status == 'Pending':
                        btns = Frame(card, bg=CARD_BG)
                        btns.pack(anchor=W, pady=(10, 0))
                        
                        def update_leave(l_id=lid, new_status='Approved'):
                            c = sqlite3.connect(get_db_path())
                            cu = c.cursor()
                            cu.execute("UPDATE leave_requests SET status=? WHERE id=?", (new_status, l_id))
                            c.commit(); c.close()
                            self.load_team_leaves()

                        Button(btns, text="Approve", bg="#10b981", fg=WHITE, relief=FLAT, command=lambda id=lid: update_leave(id, 'Approved'), padx=15).pack(side=LEFT)
                        Button(btns, text="Reject", bg="#e03030", fg=WHITE, relief=FLAT, command=lambda id=lid: update_leave(id, 'Rejected'), padx=15).pack(side=LEFT, padx=10)
            con.close()
        except Exception as e:
            Label(container, text=f"Error: {e}", bg=CONTENT_BG, fg=ACCENT_RED).pack()

    def load_team_queries(self):
        container = Frame(self.content_area, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, padx=30, pady=20)
        Label(container, text="Team Queries & Support", font=('Rajdhani', 20, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT q.id, q.user_name, q.subject, q.message, q.status, q.created_at 
                FROM queries q
                JOIN employee e ON q.user_name = e.name
                WHERE e.reporting_manager = ? OR q.tl_name = ?
                ORDER BY q.status DESC, q.created_at DESC
            """, (CURRENT_USER_NAME, CURRENT_USER_NAME))
            rows = cur.fetchall()
            
            if not rows:
                Label(container, text="No queries from your team.", font=('Segoe UI', 12), bg=CONTENT_BG, fg=MUTED_TEXT).pack(pady=50)
            else:
                for qid, uname, subj, msg, status, dt in rows:
                    card = Frame(container, bg=CARD_BG, padx=25, pady=20, highlightbackground="#2e3760", highlightthickness=1)
                    card.pack(fill=X, pady=8)
                    
                    h = Frame(card, bg=CARD_BG)
                    h.pack(fill=X)
                    Label(h, text=f"From: {uname} | Subject: {subj}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                    
                    # status_badge removed as per user request
                    
                    Label(card, text=msg, font=('Segoe UI', 10), bg=CARD_BG, fg="#9aa3c2", wraplength=700, justify=LEFT).pack(anchor=W, pady=10)
                    
                    if status == 'Open':
                        btn_f = Frame(card, bg=CARD_BG)
                        btn_f.pack(anchor=W)
                        
                        def respond_query(q_id=qid):
                            resp_win = Toplevel(self.root)
                            resp_win.title("Respond to Query")
                            resp_win.geometry("500x320")
                            resp_win.minsize(450, 300)
                            resp_win.resizable(True, True)
                            resp_win.configure(bg=BG_CARD)
                            resp_win.transient(self.root)
                            resp_win.grab_set()

                            # Brand Stripe
                            stripe = Frame(resp_win, bg=PRIMARY_RED, height=3)
                            stripe.pack(fill=X)

                            # Center on main app
                            mx = self.root.winfo_rootx() + (self.root.winfo_width()//2) - 250
                            my = self.root.winfo_rooty() + (self.root.winfo_height()//2) - 160
                            resp_win.geometry(f"500x320+{mx}+{my}")

                            header = Frame(resp_win, bg=HEADER_BG, pady=15)
                            header.pack(fill=X)
                            Label(header, text="RESPOND TO QUERY", font=('Rajdhani', 14, 'bold'), 
                                  bg=HEADER_BG, fg=WHITE).pack()

                            body = Frame(resp_win, bg=BG_CARD, padx=40, pady=25)
                            body.pack(fill=BOTH, expand=True)

                            Label(body, text="Enter your response below:", font=('Segoe UI', 10), bg=BG_CARD, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 10))
                            
                            # Themed Entry / Text area
                            txt_container = Frame(body, bg="#1a2035", highlightbackground="#2e3760", highlightthickness=1)
                            txt_container.pack(fill=BOTH, expand=True)
                            
                            resp_text = Text(txt_container, bg="#1a2035", fg=WHITE, font=('Segoe UI', 10), 
                                           relief=FLAT, padx=15, pady=10, insertbackground=WHITE, height=4)
                            resp_text.pack(fill=BOTH, expand=True)
                            resp_text.focus_set()

                            def submit_response():
                                msg = resp_text.get("1.0", "end-1c").strip()
                                if msg:
                                    try:
                                        c = sqlite3.connect(get_db_path())
                                        cu = c.cursor()
                                        cu.execute("UPDATE queries SET response=?, status='Closed' WHERE id=?", (msg, q_id))
                                        c.commit(); c.close()
                                        resp_win.destroy()
                                        messagebox.showinfo("Success", "Response sent successfully.")
                                        self.load_team_queries()
                                    except Exception as e:
                                        messagebox.showerror("Error", f"Could not save response: {e}")
                                else:
                                    messagebox.showwarning("Incomplete", "Please enter a response message.")

                            footer = Frame(resp_win, bg=BG_CARD, pady=20)
                            footer.pack(fill=X)
                            
                            btn_send = Button(footer, text="SEND RESPONSE", bg=PRIMARY_RED, fg=WHITE, 
                                            font=('Segoe UI', 10, 'bold'), relief=FLAT, padx=30, pady=10,
                                            activebackground=PRIMARY_RED_DARK, activeforeground=WHITE,
                                            command=submit_response)
                            btn_send.pack()
                            btn_send.bind("<Enter>", lambda e: btn_send.config(bg=PRIMARY_RED_DARK))
                            btn_send.bind("<Leave>", lambda e: btn_send.config(bg=PRIMARY_RED))
                                
                        Button(btn_f, text="OPEN DIALOG", bg=PRIMARY_RED, fg=WHITE, relief=FLAT, 
                               font=('Segoe UI', 9, 'bold'), padx=20, pady=8, command=respond_query).pack()
            con.close()
        except Exception as e:
            Label(container, text=f"Error: {e}", bg=CONTENT_BG, fg="#e03030").pack()

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
                        c.commit(); c.close()
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
            for start, end, reason, status in cur.fetchall():
                card = Frame(container, bg=CARD_BG, padx=15, pady=10, highlightbackground=BORDER_COLOR, highlightthickness=1)
                card.pack(fill=X, pady=5)
                Label(card, text=f"{start} to {end}", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W)
                Label(card, text=reason, font=('Segoe UI', 10), bg=CARD_BG, fg=MUTED_TEXT).pack(anchor=W)
                color = ACCENT_ORANGE if status == 'Pending' else (ACCENT_GREEN if status == 'Approved' else ACCENT_RED)
                Label(card, text=status, font=('Segoe UI', 10, 'bold'), bg=CARD_BG, fg=color).pack(anchor=E)
            con.close()
        except:
            pass

    # ==================== EMPLOYEE SUB-PAGES ====================
    def load_emp_dashboard(self):
        debug_log("DEBUG: Loading ultra-beautiful employee dashboard...")
        # Clear existing content
        for widget in self.content_area.winfo_children(): widget.destroy()
        
        # Scrollable Canvas setup
        canvas = Canvas(self.content_area, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_area, orient=VERTICAL, command=canvas.yview)
        parent = Frame(canvas, bg=CONTENT_BG)
        
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        canvas_window = canvas.create_window((0,0), window=parent, anchor="nw")
        
        def update_width(event): canvas.itemconfigure(canvas_window, width=event.width)
        canvas.bind("<Configure>", update_width)
        parent.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # --- DB Data Gathering ---
        # --- DB Data Gathering - Optimized Single Pass ---
        con = sqlite3.connect(get_db_path()); cur = con.cursor()
        cur.execute("""
            SELECT 
                (SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status IN ('Pending', 'In Progress')),
                (SELECT COUNT(*) FROM tasks WHERE assigned_to=? AND status NOT IN ('Completed', 'Cancelled') AND due_date < date('now')),
                (SELECT COUNT(*) FROM queries WHERE user_name=? AND status='Open'),
                (SELECT status FROM attendance WHERE employee_name=? AND date=date('now'))
        """, (CURRENT_USER_NAME, CURRENT_USER_NAME, CURRENT_USER_NAME, CURRENT_USER_NAME))
        meta = cur.fetchone()
        sqlite_active = meta[0] or 0
        sqlite_overdue = meta[1] or 0
        active_queries = meta[2] or 0
        att_status = meta[3] if meta[3] else "Absent"
        
        today_date = datetime.now().strftime("%Y-%m-%d")
        cur.close(); con.close()

        # Threaded AI Score logic to avoid UI freeze
        def _load_ai_score():
            try:
                ai_engine = get_performance_ai()
                if ai_engine:
                    pred = ai_engine.predict_next_month(CURRENT_USER_NAME)
                    if pred and self.root.winfo_exists():
                        s = int(pred.get('predicted_score', 0))
                        t = pred.get('trend', 'Neutral')
                        self.root.after(0, lambda: self._update_emp_ai_stat(s, t))
            except: pass

        threading.Thread(target=_load_ai_score, daemon=True).start()

        score = "--"
        trend = "Analyzing..."

        # --- Dashboard UI ---
        
        # 1. Premium Header
        header = Frame(parent, bg=CONTENT_BG)
        header.pack(fill=X, pady=(20, 30), padx=20)
        
        welcome_f = Frame(header, bg=CONTENT_BG)
        welcome_f.pack(side=LEFT)
        Label(welcome_f, text=f"Hello, {CURRENT_USER_NAME.split()[0]}!", font=('Rajdhani', 28, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(welcome_f, text=f"You have {sqlite_active} active tasks for today. Keep up the great work!", font=('DM Sans', 11), bg=CONTENT_BG, fg=TEXT_SECONDARY).pack(anchor=W, pady=(5, 0))
        
        # Action Buttons / Filter
        actions_f = Frame(header, bg=CONTENT_BG)
        actions_f.pack(side=RIGHT, pady=10)
        self.emp_dash_filter = StringVar(value="Active")
        cb = ttk.Combobox(actions_f, textvariable=self.emp_dash_filter, values=["Active", "Completed", "Pending", "Overdue", "All"], state="readonly", width=14)
        cb.pack(side=LEFT, padx=10)
        cb.bind("<<ComboboxSelected>>", lambda e: self.refresh_emp_dashboard())

        # 2. Modern Stat Cards (SaaS Style)
        stats_frame = Frame(parent, bg=CONTENT_BG)
        stats_frame.pack(fill=X, pady=(0, 40), padx=10)
        
        self._emp_ai_score_label = None
        self._emp_ai_trend_label = None

        def create_saas_card(container, title, val, sub, color, growth="+12%"):
            card = Frame(container, bg=CARD_BG, highlightthickness=0)
            card.pack(side=LEFT, expand=True, fill=BOTH, padx=10)
            
            # Interior with depth
            inner = Frame(card, bg=CARD_BG, padx=25, pady=25, highlightbackground=BORDER_COLOR, highlightthickness=1)
            inner.pack(fill=BOTH, expand=True)
            
            top_f = Frame(inner, bg=CARD_BG)
            top_f.pack(fill=X)
            Label(top_f, text=title.upper(), font=('DM Sans', 9, 'bold'), bg=CARD_BG, fg=TEXT_SECONDARY).pack(side=LEFT)
            
            # Growth Pill
            pill = Frame(top_f, bg=color, padx=6, pady=2)
            pill.pack(side=RIGHT)
            Label(pill, text=growth, font=('DM Sans', 8, 'bold'), bg=color, fg=TEXT_WHITE).pack()
            
            v_lbl = Label(inner, text=val, font=('Rajdhani', 36, 'bold'), bg=CARD_BG, fg=TEXT_WHITE)
            v_lbl.pack(anchor=W, pady=(10, 0))
            
            footer = Frame(inner, bg=CARD_BG)
            footer.pack(fill=X, pady=(15, 0))
            s_lbl = Label(footer, text=sub, font=('DM Sans', 9), bg=CARD_BG, fg=MUTED_TEXT)
            s_lbl.pack(side=LEFT)
            
            # Bottom Progress Line
            progress_bg = Frame(inner, bg=BORDER_COLOR, height=2)
            progress_bg.pack(fill=X, pady=(15, 0))
            progress_val = Frame(progress_bg, bg=color, height=2, width=80)
            progress_val.pack(side=LEFT)
            
            if title.lower() == "efficiency":
                self._emp_ai_score_label = v_lbl
                self._emp_ai_trend_label = s_lbl

        create_saas_card(stats_frame, "Efficiency", f"{score}%", f"Next Month Trend: {trend}", ACCENT_PURPLE, growth="↑ Advanced")
        create_saas_card(stats_frame, "Active", str(sqlite_active), "Tasks in pipeline", ACCENT_BLUE, growth="+2 New")
        create_saas_card(stats_frame, "Overdue", str(sqlite_overdue), "Needs attention", ACCENT_RED, growth="Crit")
        create_saas_card(stats_frame, "Queries", str(active_queries), "Unresolved tickets", ACCENT_ORANGE, growth="Live")
        create_saas_card(stats_frame, "Clock-In", att_status.upper(), f"Today: {today_date}", ACCENT_GREEN, growth="On Time")

        # 3. Clean Grid (Zero Borders on Widgets) - Lazy Load
        grid = Frame(parent, bg=CONTENT_BG)
        grid.pack(fill=BOTH, expand=True, padx=20)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
        
        def _load_lazy_emp_widgets():
            if not grid.winfo_exists(): return
            
            def create_clean_table(container, row, col, title, accent):
                f = Frame(container, bg=CARD_BG, highlightbackground=BORDER_COLOR, highlightthickness=1)
                f.grid(row=row, column=col, sticky="nsew", padx=10)
                
                # Header
                h_f = Frame(f, bg=CARD_BG, padx=20, pady=20)
                h_f.pack(fill=X)
                Label(h_f, text=title, font=('Rajdhani', 16, 'bold'), bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
                Label(h_f, text="●", fg=accent, bg=CARD_BG, font=('Arial', 10)).pack(side=RIGHT)
                
                Frame(f, bg=BORDER_COLOR, height=1).pack(fill=X)
                inner = Frame(f, bg=CARD_BG, padx=10, pady=10)
                inner.pack(fill=BOTH, expand=True)
                return inner

            # Active Tasks
            at_inner = create_clean_table(grid, 0, 0, "My Active Tasks", ACCENT_BLUE)
            self.dash_task_tree = ttk.Treeview(at_inner, columns=("Task", "Project", "Due"), show='headings', height=10, style="Treeview")
            self.dash_task_tree.heading("Task", text="TASK")
            self.dash_task_tree.heading("Project", text="PROJECT")
            self.dash_task_tree.heading("Due", text="DUE DATE")
            self.dash_task_tree.column("Task", width=250, anchor=W)
            self.dash_task_tree.column("Project", width=180, anchor=W)
            self.dash_task_tree.column("Due", width=110, anchor=CENTER)
            self.dash_task_tree.pack(fill=BOTH, expand=True)

            # Deadlines
            dl_inner = create_clean_table(grid, 0, 1, "Upcoming Deadlines", ACCENT_RED)
            self.dash_dead_tree = ttk.Treeview(dl_inner, columns=("Task", "Deadline", "Days Left"), show='headings', height=10, style="Treeview")
            self.dash_dead_tree.heading("Task", text="TASK")
            self.dash_dead_tree.heading("Deadline", text="DEADLINE")
            self.dash_dead_tree.heading("Days Left", text="DAYS LEFT")
            self.dash_dead_tree.column("Task", width=250, anchor=W)
            self.dash_dead_tree.column("Deadline", width=110, anchor=CENTER)
            self.dash_dead_tree.column("Days Left", width=110, anchor=CENTER)
            self.dash_dead_tree.pack(fill=BOTH, expand=True)

            self.dash_dead_tree.tag_configure('Urgent', foreground=ACCENT_RED)
            self.dash_dead_tree.tag_configure('Warning', foreground=ACCENT_ORANGE)
            self.dash_dead_tree.tag_configure('Safe', foreground=ACCENT_GREEN)

            self.refresh_emp_dashboard()

        # Start lazy loading
        self.root.after(20, _load_lazy_emp_widgets)

    def _update_emp_ai_stat(self, score, trend):
        """Thread-safe UI update for AI statistics."""
        if not hasattr(self, 'current_page') or self.current_page != 'emp_dashboard':
            return
        try:
            if self._emp_ai_score_label and self._emp_ai_score_label.winfo_exists():
                self._emp_ai_score_label.config(text=f"{score}%")
            if self._emp_ai_trend_label and self._emp_ai_trend_label.winfo_exists():
                self._emp_ai_trend_label.config(text=f"Next Month Trend: {trend}")
        except: pass





    def load_emp_my_tasks(self):
        debug_log("DEBUG: Loading employee my tasks...")
        parent = self.content_area # The content area is now the parent

        # Header & Actions
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=25)
        
        Label(h, text="My Tasks", font=('Rajdhani', 22, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        btn_frame = Frame(h, bg=CONTENT_BG)
        btn_frame.pack(side=RIGHT)
        
        btn_upd = Button(btn_frame, text="UPDATE SELECTED TASK", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'), 
                       relief=FLAT, command=self.update_task_modal, padx=20, pady=8, cursor="hand2")
        btn_upd.pack(side=LEFT, padx=5)
        btn_upd.bind("<Enter>", lambda e: btn_upd.config(bg="#059669")) # Darker green hover
        btn_upd.bind("<Leave>", lambda e: btn_upd.config(bg=ACCENT_GREEN))
        
        # Search & Filters (Matching HTML preview)
        filter_card = Frame(parent, bg="#212840", padx=25, pady=20, highlightbackground="#2e3760", highlightthickness=1)
        filter_card.pack(fill=X, pady=(0, 20))
        
        # Grid layout for filters
        filter_grid = Frame(filter_card, bg="#212840")
        filter_grid.pack(fill=X)
        
        # Search
        search_f = Frame(filter_grid, bg="#212840")
        search_f.pack(side=LEFT, padx=(0, 25))
        Label(search_f, text="SEARCH:", font=('Segoe UI', 9, 'bold'), bg="#212840", fg="#9aa3c2").pack(side=LEFT, padx=(0, 10))
        self.emp_task_search = StringVar()
        self.emp_task_search.trace("w", lambda *args: self.refresh_emp_tasks_tab())
        Entry(search_f, textvariable=self.emp_task_search, width=30, bg="#1a2035", fg=TEXT_WHITE, 
              insertbackground=TEXT_WHITE, relief=FLAT, font=('Segoe UI', 10)).pack(side=LEFT, ipady=6, padx=2)
        
        # Status
        status_f = Frame(filter_grid, bg="#212840")
        status_f.pack(side=LEFT, padx=(0, 25))
        Label(status_f, text="STATUS:", font=('Segoe UI', 9, 'bold'), bg="#212840", fg="#9aa3c2").pack(side=LEFT, padx=(0, 10))
        self.emp_task_status = StringVar(value="All Active")
        cb_s = ttk.Combobox(status_f, textvariable=self.emp_task_status, 
                            values=["All", "All Active", "Pending", "In Progress", "Pending Approval"], 
                            state="readonly", width=18, style='Employee.TCombobox')
        cb_s.pack(side=LEFT)
        cb_s.bind("<<ComboboxSelected>>", lambda e: self.refresh_emp_tasks_tab())
        
        # Priority
        prio_f = Frame(filter_grid, bg="#212840")
        prio_f.pack(side=LEFT)
        Label(prio_f, text="PRIORITY:", font=('Segoe UI', 9, 'bold'), bg="#212840", fg="#9aa3c2").pack(side=LEFT, padx=(0, 10))
        self.emp_task_prio = StringVar(value="All")
        cb_p = ttk.Combobox(prio_f, textvariable=self.emp_task_prio, values=["All", "High", "Medium", "Low"], 
                            state="readonly", width=12, style='Employee.TCombobox')
        cb_p.pack(side=LEFT)
        cb_p.bind("<<ComboboxSelected>>", lambda e: self.refresh_emp_tasks_tab())
        
        # Treeview
        tree_f = Frame(parent, bg=CONTENT_BG)
        tree_f.pack(fill=BOTH, expand=True)
        
        cols = ("ID", "Title", "Project", "Priority", "Status", "Due Date", "Days Left")
        self.emp_tasks_tree = ttk.Treeview(tree_f, columns=cols, show='headings', height=15, style='Custom.Treeview')
        for c in cols: 
            self.emp_tasks_tree.heading(c, text=c.upper(), command=lambda _c=c: self.sort_emp_tasks(_c))
            self.emp_tasks_tree.column(c, width=130, anchor=W)
        
        self.emp_tasks_tree.column("ID", width=60, anchor=CENTER)
        self.emp_tasks_tree.column("Title", width=250)
        self.emp_tasks_tree.column("Project", width=180)
        self.emp_tasks_tree.column("Priority", width=100, anchor=CENTER)
        self.emp_tasks_tree.column("Status", width=130, anchor=CENTER)
        self.emp_tasks_tree.column("Due Date", width=120, anchor=CENTER)
        self.emp_tasks_tree.column("Days Left", width=120, anchor=CENTER)
        
        self.emp_tasks_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Add tags for status colors
        self.emp_tasks_tree.tag_configure('Completed', foreground='#10b981')  # Green
        self.emp_tasks_tree.tag_configure('In Progress', foreground='#f59e0b') # Orange
        self.emp_tasks_tree.tag_configure('Delayed', foreground='#e03030')    # Red
        self.emp_tasks_tree.tag_configure('Pending', foreground='#ffffff')    # White
        
        scrolly = Scrollbar(tree_f, orient=VERTICAL, command=self.emp_tasks_tree.yview)
        scrolly.pack(side=RIGHT, fill=Y)
        self.emp_tasks_tree.configure(yscrollcommand=scrolly.set)
        
        self.emp_tasks_tree.bind("<Double-1>", lambda e: self.update_task_modal())
        
        self.refresh_emp_tasks_tab()

    def load_emp_team(self):
        debug_log("DEBUG: Loading senior employee team hub...")
        parent = self.content_area
        
        # Header
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=(20, 10))
        Label(h, text="Project Colleagues", font=('Rajdhani', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Label(h, text="Shared insights and team synergy", font=('Segoe UI', 10), bg=CONTENT_BG, fg="#9aa3c2").pack(side=LEFT, padx=20, pady=(12, 0))

        # 0. Layout Wrapper
        canvas = Canvas(parent, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient=VERTICAL, command=canvas.yview)
        scroll_frame = Frame(canvas, bg=CONTENT_BG)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # SECTION 1: TEAM TASKS
        s2 = Frame(scroll_frame, bg=CONTENT_BG, pady=10)
        s2.pack(fill=X)
        Label(s2, text="PEER UPDATES", font=('Rajdhani', 14, 'bold'), bg=CONTENT_BG, fg=ACCENT_ORANGE).pack(anchor=W)
        
        tree_f2 = Frame(scroll_frame, bg=CARD_BG, padx=2, pady=2, highlightbackground="#2e3760", highlightthickness=1)
        tree_f2.pack(fill=X, pady=(5, 20))
        
        cols2 = ("Member", "Task Name", "Status", "Due Date")
        self.team_others_tasks_tree = ttk.Treeview(tree_f2, columns=cols2, show='headings', height=8, style='Custom.Treeview')
        # Status colors for peers
        self.team_others_tasks_tree.tag_configure('Completed', foreground=ACCENT_GREEN)
        self.team_others_tasks_tree.tag_configure('In Progress', foreground=ACCENT_BLUE)
        self.team_others_tasks_tree.tag_configure('Delayed', foreground=ACCENT_RED)
        self.team_others_tasks_tree.tag_configure('Pending', foreground=ACCENT_ORANGE)

        for c in cols2:
            self.team_others_tasks_tree.heading(c, text=c.upper())
            self.team_others_tasks_tree.column(c, width=150)
        self.team_others_tasks_tree.pack(fill=X)
        self._attach_tree_hover(self.team_others_tasks_tree)

        # SECTION 3: TEAM PROGRESS
        s3 = Frame(scroll_frame, bg=CONTENT_BG, pady=10)
        s3.pack(fill=X)
        Label(s3, text="TEAM MOMENTUM", font=('Rajdhani', 14, 'bold'), bg=CONTENT_BG, fg=ACCENT_GREEN).pack(anchor=W)
        
        self.team_prog_container = Frame(scroll_frame, bg=CONTENT_BG)
        self.team_prog_container.pack(fill=X, pady=10)
        
        # Data Population
        self._refresh_emp_team_data()


    def _refresh_emp_team_data(self):
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # 1. GET USER DEPARTMENT
            cur.execute("SELECT department FROM employee WHERE name = ?", (CURRENT_USER_NAME,))
            dept_row = cur.fetchone()
            user_dept = dept_row[0] if dept_row else None

            # 2. MY TASKS (Section removed from UI)
                
            # 3. TEAM TASKS (Everyone in same department OR same project)
            if user_dept:
                cur.execute("""
                    SELECT t.assigned_to, t.title, t.status, t.due_date 
                    FROM tasks t 
                    WHERE t.assigned_to != ? AND t.status != 'Cancelled'
                    AND (
                        t.assigned_to IN (SELECT name FROM employee WHERE department = ?)
                        OR t.project_id IN (SELECT DISTINCT project_id FROM tasks WHERE assigned_to = ?)
                    )
                    ORDER BY t.assigned_to, t.due_date ASC
                """, (CURRENT_USER_NAME, user_dept, CURRENT_USER_NAME))
            else:
                cur.execute("""
                    SELECT t.assigned_to, t.title, t.status, t.due_date 
                    FROM tasks t 
                    WHERE t.assigned_to != ? AND t.status != 'Cancelled'
                    AND t.project_id IN (SELECT DISTINCT project_id FROM tasks WHERE assigned_to = ?) 
                    ORDER BY t.assigned_to, t.due_date ASC
                """, (CURRENT_USER_NAME, CURRENT_USER_NAME))
                
            team_data = cur.fetchall()
            for row in team_data:
                self.team_others_tasks_tree.insert('', END, values=row, tags=(row[2],))
                
            # 4. TEAM PROGRESS
            members = {}
            for member, _, status, _ in team_data:
                if member not in members: members[member] = {'total': 0, 'comp': 0}
                members[member]['total'] += 1
                if status == 'Completed': members[member]['comp'] += 1
                
            if not members:
                Label(self.team_prog_container, text="No team members found in your current projects.", 
                      font=('Segoe UI', 10, 'italic'), bg=CONTENT_BG, fg="#9aa3c2").pack(pady=20)
            else:
                for m_name, stats in members.items():
                    mf = Frame(self.team_prog_container, bg="#212840", padx=20, pady=15, highlightbackground="#2e3760", highlightthickness=1)
                    mf.pack(fill=X, pady=5)
                    
                    perc = int((stats['comp'] / stats['total']) * 100) if stats['total'] > 0 else 0
                    
                    Label(mf, text=m_name, font=('Segoe UI', 11, 'bold'), bg="#212840", fg=TEXT_WHITE, width=20, anchor=W).pack(side=LEFT)
                    
                    p_bar = ttk.Progressbar(mf, length=300, mode='determinate', style='Team.Horizontal.TProgressbar')
                    p_bar.pack(side=LEFT, padx=30, expand=True, fill=X)
                    p_bar['value'] = perc
                    
                    Label(mf, text=f"{perc}% ({stats['comp']}/{stats['total']})", font=('Segoe UI', 10), 
                          bg="#212840", fg=ACCENT_GREEN if perc==100 else "#9aa3c2", width=12).pack(side=LEFT)
            
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Team data refresh failed: {e}")


    def load_emp_analysis(self):
        debug_log("DEBUG: Loading employee analysis...")
        main_parent = self.content_area
        
        # --- Scrollable Wrapper ---
        canvas = Canvas(main_parent, bg=CONTENT_BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_parent, orient=VERTICAL, command=canvas.yview)
        parent = Frame(canvas, bg=CONTENT_BG)

        def configure_canvas_region(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        parent.bind("<Configure>", configure_canvas_region)
        canvas_window = canvas.create_window((0, 0), window=parent, anchor="nw")
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind("<Configure>", configure_canvas_width)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # ── HEADER ──
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=(20, 10))
        Label(h, text="Advanced Analytics Suite", font=('Rajdhani', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(h, text="Comprehensive deep-dive into your workflow velocity and execution quality.", font=('Segoe UI', 10), bg=CONTENT_BG, fg="#9aa3c2").pack(anchor=W, pady=(5,0))

        # ── TOP KPI CARDS ──
        kpi_frame = Frame(parent, bg=CONTENT_BG)
        kpi_frame.pack(fill=X, pady=(10, 20))
        
        self.emp_ana_kpis = {}
        for title, accent, icon, key in [("Completion Rate", "#10b981", "🎯", "rate"), 
                                         ("Total Hours Logged", "#8b5cf6", "⏱️", "hours"), 
                                         ("High Prio Focus", "#ef4444", "🔥", "high")]:
            card = Frame(kpi_frame, bg="#212840", padx=25, pady=20, highlightbackground=accent, highlightthickness=1)
            card.pack(side=LEFT, fill=X, expand=True, padx=(0, 15))
            Label(card, text=icon, font=('Segoe UI', 16), bg="#212840", fg=accent).pack(side=LEFT, padx=(0,10))
            v_f = Frame(card, bg="#212840")
            v_f.pack(side=LEFT)
            Label(v_f, text=title.upper(), font=('Segoe UI', 8, 'bold'), bg="#212840", fg="#9aa3c2").pack(anchor=W)
            lbl = Label(v_f, text="0", font=('Segoe UI', 22, 'bold'), bg="#212840", fg=TEXT_WHITE)
            lbl.pack(anchor=W)
            self.emp_ana_kpis[key] = lbl

        # ── MID SECTION (PRIORITY & STAGES) ──
        container = Frame(parent, bg=CONTENT_BG)
        container.pack(fill=BOTH, expand=True, pady=10)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=1)

        # Left: Priority Mix
        self.ana_prio_f = Frame(container, bg="#212840", padx=30, pady=25, highlightbackground="#2e3760", highlightthickness=1)
        self.ana_prio_f.grid(row=0, column=0, sticky="nsew", padx=(0, 15))
        
        prio_header = Frame(self.ana_prio_f, bg="#212840")
        prio_header.pack(fill=X, pady=(0, 20))
        Label(prio_header, text="🔥", font=('Segoe UI', 12), bg="#212840", fg="#ef4444").pack(side=LEFT, padx=(0,5))
        Label(prio_header, text="TASK PRIORITY MIX", font=('Rajdhani', 14, 'bold'), bg="#212840", fg=TEXT_WHITE).pack(side=LEFT)
        self.ana_prio_container = Frame(self.ana_prio_f, bg="#212840")
        self.ana_prio_container.pack(fill=BOTH, expand=True)

        # Right: Delivery Stages
        self.ana_stat_f = Frame(container, bg="#212840", padx=30, pady=25, highlightbackground="#2e3760", highlightthickness=1)
        self.ana_stat_f.grid(row=0, column=1, sticky="nsew", padx=(0, 0))
        
        stat_header = Frame(self.ana_stat_f, bg="#212840")
        stat_header.pack(fill=X, pady=(0, 20))
        Label(stat_header, text="📈", font=('Segoe UI', 12), bg="#212840", fg="#4d7cfe").pack(side=LEFT, padx=(0,5))
        Label(stat_header, text="DELIVERY STAGES", font=('Rajdhani', 14, 'bold'), bg="#212840", fg=TEXT_WHITE).pack(side=LEFT)
        self.ana_stat_container = Frame(self.ana_stat_f, bg="#212840")
        self.ana_stat_container.pack(fill=BOTH, expand=True)

        # ── AI INSIGHTS ──
        ai_card = Frame(parent, bg="#212840", padx=30, pady=25, highlightbackground="#8b5cf6", highlightthickness=1)
        ai_card.pack(fill=X, pady=20)
        
        ai_h = Frame(ai_card, bg="#212840")
        ai_h.pack(fill=X, pady=(0, 15))
        Label(ai_h, text="🧠", font=('Segoe UI', 14), bg="#212840").pack(side=LEFT, padx=(0,10))
        Label(ai_h, text="AI EFFICIENCY INSIGHT", font=('Rajdhani', 14, 'bold'), bg="#212840", fg=TEXT_WHITE).pack(side=LEFT)
        
        self.emp_ana_ai_lbl = Label(ai_card, text="Generating real-time insights...", font=('Segoe UI', 10), 
                                    bg="#212840", fg=TEXT_WHITE, wraplength=800, justify=LEFT)
        self.emp_ana_ai_lbl.pack(anchor=W)

        self.refresh_emp_analysis()

    def refresh_emp_analysis(self):
        """High-fidelity partial refresh for Employee Analysis page"""
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            
            # 1. Fetch Task Stats
            cur.execute("SELECT status, COUNT(*) FROM tasks WHERE assigned_to=? AND status!='Cancelled' GROUP BY status", (CURRENT_USER_NAME,))
            status_data = dict(cur.fetchall())
            comp = status_data.get('Completed', 0)
            total = sum(status_data.values())
            rate = int((comp / total) * 100) if total > 0 else 0

            # 2. Fetch Hours
            cur.execute("SELECT SUM(hours) FROM timesheets WHERE employee_name=?", (CURRENT_USER_NAME,))
            hours = cur.fetchone()[0] or 0.0

            # 3. Fetch Priorities
            cur.execute("SELECT priority, COUNT(*) FROM tasks WHERE assigned_to=? GROUP BY priority", (CURRENT_USER_NAME,))
            prio_data = dict(cur.fetchall())
            high = prio_data.get("High", 0)
            
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
                    f = Frame(self.ana_prio_container, bg="#212840", pady=8)
                    f.pack(fill=X)
                    Label(f, text=p_name, bg="#212840", fg=TEXT_WHITE, font=('Segoe UI', 9)).pack(side=LEFT)
                    Label(f, text=f"{count} items ({int(perc)}%)", bg="#212840", fg=MUTED_TEXT, font=('Segoe UI', 8)).pack(side=RIGHT)
                    track = Frame(f, bg="#1a2035", height=10)
                    track.pack(fill=X, pady=(5,0), side=BOTTOM)
                    color = "#ef4444" if "High" in p_name else ("#f59e0b" if "Medium" in p_name else "#10b981")
                    Frame(track, bg=color, height=10).place(x=0, y=0, relwidth=max(0.01, perc/100))
            else:
                Label(self.ana_prio_container, text="No tasks to analyze.", bg="#212840", fg=MUTED_TEXT, pady=20).pack()

            # 6. Update Delivery Stages
            for widget in self.ana_stat_container.winfo_children(): widget.destroy()
            if status_data:
                for status, count in status_data.items():
                    r = Frame(self.ana_stat_container, bg="#1a2035", padx=15, pady=10, highlightbackground="#2e3760", highlightthickness=1)
                    r.pack(fill=X, pady=4)
                    acc = "#10b981" if status=="Completed" else ("#f59e0b" if status=="In Progress" else "#4d7cfe")
                    Label(r, text="●", bg="#1a2035", fg=acc, font=('Segoe UI', 10)).pack(side=LEFT, padx=(0, 8))
                    Label(r, text=status, bg="#1a2035", fg=TEXT_WHITE, font=('Segoe UI', 10, 'bold')).pack(side=LEFT)
                    Label(r, text=f"{count} items", bg="#1a2035", fg="#9aa3c2", font=('Segoe UI', 10)).pack(side=RIGHT)

            # 7. AI Insight Generation
            # Using local variables instead of undefined ones
            med_p = prio_data.get("Medium", 0)
            low_p = prio_data.get("Low", 0)
            pend_count = status_data.get('Pending', 0)
            prog_count = status_data.get('In Progress', 0)

            if high > med_p + low_p and high > 0:
                insight_text = "Your backlog is heavily saturated with High Priority tasks. The AI suggests proactively negotiating deadlines to distribute operational load."
            elif rate > 75:
                insight_text = "Exceptional tracking velocity. You are currently closing tasks faster than the median operational standard. AI Confidence remains extremely high."
            elif hours > (total * 8) and total > 0:
                insight_text = "You are logging statistically high hours relative to your current task throughput. Consider re-evaluating task scopes."
            elif pend_count > prog_count and pend_count > 3:
                insight_text = "A backlog bottleneck is detected in your Pending queue. Focus your next operational cycle on transitioning these items to 'In Progress'."
            else:
                insight_text = "Operations are nominal. Task intake and closure rates are highly balanced. Maintain your current operational paradigm and focus on steady execution."

            if hasattr(self, 'emp_ana_ai_lbl'):
                self.emp_ana_ai_lbl.config(text=insight_text)

            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Analysis Refresh Error: {e}")
            if hasattr(self, 'emp_ana_ai_lbl'):
                self.emp_ana_ai_lbl.config(text=f"AI Insight temporarily unavailable: {e}")


    def load_emp_queries(self):
        debug_log("DEBUG: Loading employee queries...")
        parent = self.content_area
        
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=20)
        Label(h, text="My Queries & Support", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Action Bar
        action_f = Frame(parent, bg=CARD_BG, padx=20, pady=15)
        action_f.pack(fill=X, pady=(0, 15))
        
        Button(action_f, text="+ Raise New Query", bg=PRIMARY_RED, fg=WHITE, font=('Segoe UI', 9, 'bold'),
               relief=FLAT, padx=15, command=self.raise_new_query_window).pack(side=LEFT)
               
        Label(action_f, text="Search:", bg=CARD_BG, fg="#9aa3c2", font=('Segoe UI', 9)).pack(side=LEFT, padx=(30, 5))
        self.query_search_var = StringVar()
        ent = Entry(action_f, textvariable=self.query_search_var, bg="#1a2035", fg=WHITE, insertbackground=WHITE, 
                    relief=FLAT, width=30, font=('Segoe UI', 10))
        ent.pack(side=LEFT, pady=5)
        self.query_search_var.trace_add("write", lambda *args: self.refresh_emp_queries())

        tree_frame = Frame(parent, bg=CONTENT_BG)
        tree_frame.pack(fill=BOTH, expand=True)
        
        cols = ("ID", "Project", "Subject", "Status", "Last Updated")
        self.query_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', style='Custom.Treeview')
        
        for c in cols:
            self.query_tree.heading(c, text=c)
            self.query_tree.column(c, width=120)
            
        self.query_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._attach_tree_hover(self.query_tree)
        
        self.refresh_emp_queries()

    def refresh_emp_queries(self):
        if not hasattr(self, 'query_tree'): return
        self.query_tree.delete(*self.query_tree.get_children())
        search = self.query_search_var.get().lower()
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT q.id, p.name, q.subject, q.status, q.created_at 
                FROM queries q
                LEFT JOIN projects p ON q.project_id = p.id
                WHERE q.user_name=?
                ORDER BY q.created_at DESC
            """, (CURRENT_USER_NAME,))
            
            for row in cur.fetchall():
                if search and not any(search in str(v).lower() for v in row):
                    continue
                self.query_tree.insert('', END, values=row)
            con.close()
        except Exception as e:
            debug_log(f"DEBUG: Error refreshing queries: {e}")

    def load_emp_attendance(self):
        debug_log("DEBUG: Loading employee time & attendance...")
        parent = self.content_area
        
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=20)
        Label(h, text="Time & Attendance Log", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        # Action Frame
        action_f = Frame(parent, bg=CARD_BG, padx=20, pady=15)
        action_f.pack(fill=X, pady=(0, 15))
        
        Button(action_f, text="+ Log Time & Mark Attendance", bg=ACCENT_GREEN, fg=WHITE, font=('Segoe UI', 9, 'bold'),
               relief=FLAT, padx=15, command=self.log_time_window).pack(side=LEFT)

        tables_frame = Frame(parent, bg=CONTENT_BG)
        tables_frame.pack(fill=BOTH, expand=True)
        
        # Left: Attendance Card
        att_frame = Frame(tables_frame, bg="#252b40", highlightbackground="#2c3144", highlightthickness=1, padx=20, pady=20)
        att_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))
        
        lbl_att = Frame(att_frame, bg="#252b40")
        lbl_att.pack(fill=X, pady=(0, 15))
        Label(lbl_att, text="📋", font=('Segoe UI', 12), bg="#252b40", fg="#81F4E1").pack(side=LEFT, padx=(0, 6))
        Label(lbl_att, text="Attendance Record", font=('Segoe UI', 12, 'bold'), bg="#252b40", fg="#e2e6ff").pack(side=LEFT)
        
        cols_att = ("Date", "Status", "Clock In")
        self.att_tree = ttk.Treeview(att_frame, columns=cols_att, show='headings', style='Custom.Treeview')
        for c in cols_att:
            self.att_tree.heading(c, text=c)
            self.att_tree.column(c, width=120)
        self.att_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._attach_tree_hover(self.att_tree)
        
        # Right: Timesheets Card
        ts_frame = Frame(tables_frame, bg="#252b40", highlightbackground="#2c3144", highlightthickness=1, padx=20, pady=20)
        ts_frame.pack(side=RIGHT, fill=BOTH, expand=True, padx=(10, 0))
        
        lbl_ts = Frame(ts_frame, bg="#252b40")
        lbl_ts.pack(fill=X, pady=(0, 15))
        Label(lbl_ts, text="📅", font=('Segoe UI', 12), bg="#252b40", fg="#56CBF9").pack(side=LEFT, padx=(0, 6))
        Label(lbl_ts, text="Timesheets Log", font=('Segoe UI', 12, 'bold'), bg="#252b40", fg="#e2e6ff").pack(side=LEFT)
        
        cols_ts = ("Date", "Task", "Hours")
        self.ts_tree = ttk.Treeview(ts_frame, columns=cols_ts, show='headings', style='Custom.Treeview')
        for c in cols_ts:
            self.ts_tree.heading(c, text=c)
            self.ts_tree.column(c, width=130)
        self.ts_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._attach_tree_hover(self.ts_tree)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # Load Attendance
            cur.execute("SELECT date, status, clock_in FROM attendance WHERE name=? ORDER BY date DESC", (CURRENT_USER_NAME,))
            for row in cur.fetchall():
                self.att_tree.insert('', END, values=row)
                
            # Load Timesheets
            cur.execute("""
                SELECT ts.date, t.title, ts.hours 
                FROM timesheets ts
                JOIN tasks t ON ts.task_id = t.id
                WHERE ts.employee_name=?
                ORDER BY ts.date DESC
            """, (CURRENT_USER_NAME,))
            for row in cur.fetchall():
                self.ts_tree.insert('', END, values=row)
                
            con.close()
        except: pass

    def load_emp_leave_requests(self):
        debug_log("DEBUG: Loading employee leave requests...")
        parent = self.content_area
        
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=20)
        Label(h, text="My Leave Requests", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        action_f = Frame(parent, bg=CARD_BG, padx=20, pady=15)
        action_f.pack(fill=X, pady=(0, 15))
        
        Button(action_f, text="+ Request Leave", bg=PRIMARY_RED, fg=WHITE, font=('Segoe UI', 9, 'bold'),
               relief=FLAT, padx=15, command=self.request_leave_window).pack(side=LEFT)

        tree_frame = Frame(parent, bg=CONTENT_BG)
        tree_frame.pack(fill=BOTH, expand=True)
        
        cols = ("Type", "Start Date", "End Date", "Status", "Reason")
        self.leave_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', style='Custom.Treeview')
        
        for c in cols:
            self.leave_tree.heading(c, text=c)
            self.leave_tree.column(c, width=120)
            
        self.leave_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._attach_tree_hover(self.leave_tree)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            # CORRECTED: member_name instead of name, leave_type instead of type
            cur.execute("SELECT leave_type, start_date, end_date, status, reason FROM leave_requests WHERE member_name=? ORDER BY id DESC", (CURRENT_USER_NAME,))
            for row in cur.fetchall():
                self.leave_tree.insert('', END, values=row)
            con.close()
        except: pass

    def load_emp_timesheets(self):
        debug_log("DEBUG: Loading employee timesheets...")
        parent = self.content_area
        
        h = Frame(parent, bg=CONTENT_BG)
        h.pack(fill=X, pady=20)
        Label(h, text="My Timesheets", font=('Segoe UI', 14, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(side=LEFT)
        
        action_f = Frame(parent, bg=CARD_BG, padx=20, pady=15)
        action_f.pack(fill=X, pady=(0, 15))
        
        Button(action_f, text="+ Log Time", bg="#ff9f43", fg=WHITE, font=('Segoe UI', 9, 'bold'),
               relief=FLAT, padx=15, command=self.log_time_window).pack(side=LEFT)

        tree_frame = Frame(parent, bg=CONTENT_BG)
        tree_frame.pack(fill=BOTH, expand=True)
        
        cols = ("Date", "Task", "Hours", "Description")
        self.ts_tree = ttk.Treeview(tree_frame, columns=cols, show='headings', style='Custom.Treeview')
        
        for c in cols:
            self.ts_tree.heading(c, text=c)
            self.ts_tree.column(c, width=150)
            
        self.ts_tree.pack(side=LEFT, fill=BOTH, expand=True)
        self._attach_tree_hover(self.ts_tree)
        
        try:
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("""
                SELECT ts.date, t.title, ts.hours, ts.description 
                FROM timesheets ts
                JOIN tasks t ON ts.task_id = t.id
                WHERE ts.employee_name=?
                ORDER BY ts.date DESC
            """, (CURRENT_USER_NAME,))
            for row in cur.fetchall():
                self.ts_tree.insert('', END, values=row)
            con.close()
        except: pass

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
                con.commit()
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
                con.commit()
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
                con.commit()
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
    
    # seed_data()
    load_session()
    
    root = Tk()
    app = ProjectMonitorApp(root, standalone=standalone)
    root.mainloop()

if __name__ == "__main__":
    main(standalone=True)












