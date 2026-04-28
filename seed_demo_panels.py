import hashlib
import os
import random
import sqlite3
import sys
from datetime import datetime, timedelta
import sys


def get_db_path():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "employee.db")


def hash_password(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def ensure_employee(cur, name, mobile, email, department, role, reporting_manager="", gender="N/A"):
    cur.execute("SELECT id FROM employee WHERE lower(name)=lower(?)", (name,))
    row = cur.fetchone()
    payload = (
        name,
        mobile,
        email,
        f"{department} workspace",
        gender,
        "1997-01-01",
        datetime.now().strftime("%Y-%m-%d"),
        datetime.now().strftime("%H:%M:%S"),
        department,
        hash_password("1234"),
        role,
        "N/A",
        "N/A",
        "0000",
        reporting_manager,
    )
    if row:
        cur.execute(
            """
            UPDATE employee
            SET mobile=?, email=?, address=?, gender=?, dob=?, date=?, time=?, department=?,
                password=?, role=?, security_question=?, security_answer=?, pin=?, reporting_manager=?
            WHERE id=?
            """,
            payload[1:] + (row[0],),
        )
        return row[0]

    cur.execute(
        """
        INSERT INTO employee
        (name, mobile, email, address, gender, dob, date, time, department, password, role,
         security_question, security_answer, pin, reporting_manager)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        payload,
    )
    return cur.lastrowid


def ensure_admin_user(cur):
    cur.execute("SELECT username FROM users WHERE username='admin'")
    if cur.fetchone():
        cur.execute(
            "UPDATE users SET password=?, email=? WHERE username='admin'",
            (hash_password("1234"), "admin@company.com"),
        )
    else:
        cur.execute(
            "INSERT INTO users (username, password, email) VALUES (?,?,?)",
            ("admin", hash_password("1234"), "admin@company.com"),
        )


def clear_old_demo(cur):
    cur.execute("SELECT id FROM projects WHERE name LIKE '[DEMO] %'")
    demo_project_ids = [row[0] for row in cur.fetchall()]

    if demo_project_ids:
        placeholders = ",".join("?" for _ in demo_project_ids)
        cur.execute(f"DELETE FROM tasks WHERE project_id IN ({placeholders})", demo_project_ids)
        cur.execute(f"DELETE FROM activity_timeline WHERE project_id IN ({placeholders})", demo_project_ids)
        cur.execute(f"DELETE FROM project_milestones WHERE project_id IN ({placeholders})", demo_project_ids)
        cur.execute(f"DELETE FROM queries WHERE project_id IN ({placeholders})", demo_project_ids)
        cur.execute(f"DELETE FROM projects WHERE id IN ({placeholders})", demo_project_ids)

    cur.execute("DELETE FROM performance_history WHERE employee_name LIKE '[DEMO] %'")
    cur.execute("DELETE FROM audit_logs WHERE details LIKE '[DEMO] %' OR action LIKE '[DEMO] %'")
    cur.execute("DELETE FROM notifications WHERE title LIKE '[DEMO] %' OR message LIKE '[DEMO] %'")
    cur.execute("DELETE FROM attendance WHERE lower(name) IN ('dev patel','ayush patel','sharavan panchal','krishn shukala','jahan xyz','dhrumil xyz','jarmil patel','mohit zinzuwadiya')")
    cur.execute("DELETE FROM timesheets WHERE lower(employee_name) IN ('dev patel','ayush patel','sharavan panchal','krishn shukala','jahan xyz','dhrumil xyz','jarmil patel','mohit zinzuwadiya')")


def seed_projects_and_tasks(cur):
    today = datetime.now()
    project_specs = [
        {
            "name": "[DEMO] Q2 Platform Revamp",
            "description": "Modernize the PMS delivery workflow, reporting, and employee experience.",
            "start": today - timedelta(days=28),
            "end": today + timedelta(days=36),
            "status": "Ongoing",
            "manager": "Henil Patel",
            "team_leader": "Jarmil Patel",
            "default_assignee": "Jarmil Patel",
            "priority": "High",
            "tasks": [
                ("Requirements Finalization", "Jarmil Patel", "Completed", "High", -18, -12, "Leadership alignment and scope freeze."),
                ("Dashboard UX Upgrade", "Dev Patel", "In Progress", "High", -12, 4, "Refresh employee dashboard layout and cards."),
                ("Task Workflow Cleanup", "Ayush Patel", "Pending", "Medium", -8, 8, "Reduce friction in PM to TL handoffs."),
                ("Analytics Insights Polish", "sharavan panchal", "Pending", "High", -6, 10, "Surface stronger AI-backed insights."),
                ("Release QA Sweep", "krishn shukala", "Pending", "Medium", -2, 14, "Validate PM, TL, and employee flows."),
                ("Launch Checklist", "Dev Patel", "Completed", "Low", -16, -9, "Prepared release readiness checklist."),
            ],
        },
        {
            "name": "[DEMO] Client Success Portal",
            "description": "Build a support-facing workspace with task visibility and team reporting.",
            "start": today - timedelta(days=20),
            "end": today + timedelta(days=22),
            "status": "Ongoing",
            "manager": "Henil Patel",
            "team_leader": "Mohit Zinzuwadiya",
            "default_assignee": "Mohit Zinzuwadiya",
            "priority": "Medium",
            "tasks": [
                ("Portal Wireframes", "Mohit Zinzuwadiya", "Completed", "Medium", -18, -11, "Initial portal blueprint approved."),
                ("API Contract Review", "Jahan xyz", "In Progress", "High", -10, 5, "Backend integration review in progress."),
                ("Notification Engine", "Dhrumil xyz", "Pending", "High", -7, 9, "Create user-facing alerts and reminders."),
                ("Support Metrics Feed", "Mohit Zinzuwadiya", "Pending", "Medium", -5, 12, "Roll up productivity insights for client-facing team."),
                ("Regression Suite", "Jahan xyz", "Delayed", "High", -15, -2, "Test suite slipped due to dependency issues."),
            ],
        },
        {
            "name": "[DEMO] Finance Workflow Automation",
            "description": "Automate handoffs, tracking, and reporting for internal finance approvals.",
            "start": today - timedelta(days=34),
            "end": today - timedelta(days=2),
            "status": "Delayed",
            "manager": "Henil Patel",
            "team_leader": "Jarmil Patel",
            "default_assignee": "Jarmil Patel",
            "priority": "High",
            "tasks": [
                ("Approval Matrix Setup", "Jarmil Patel", "Completed", "Medium", -25, -18, "Core routing matrix configured."),
                ("Finance Rules Engine", "Dev Patel", "Delayed", "High", -18, -4, "Complex edge cases still pending."),
                ("Exception Handling", "Ayush Patel", "In Progress", "High", -11, 2, "Handling fallback and escalation paths."),
                ("Audit Trail Validation", "sharavan panchal", "Pending", "Medium", -9, 6, "Verify finance tracking completeness."),
            ],
        },
    ]

    created_projects = []
    created_task_ids = []

    for spec in project_specs:
        cur.execute(
            """
            INSERT INTO projects
            (name, description, start_date, end_date, status, manager, team_leader, default_assignee, priority)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                spec["name"],
                spec["description"],
                spec["start"].strftime("%Y-%m-%d"),
                spec["end"].strftime("%Y-%m-%d"),
                spec["status"],
                spec["manager"],
                spec["team_leader"],
                spec["default_assignee"],
                spec["priority"],
            ),
        )
        project_id = cur.lastrowid
        created_projects.append((project_id, spec))

        for title, assigned_to, status, priority, created_offset, due_offset, description in spec["tasks"]:
            created_date = (today + timedelta(days=created_offset)).strftime("%Y-%m-%d")
            due_date = (today + timedelta(days=due_offset)).strftime("%Y-%m-%d")
            completed_date = due_date if status == "Completed" else None
            cur.execute(
                """
                INSERT INTO tasks
                (title, assigned_to, status, due_date, completed_date, priority, project_id, description, created_date)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    title,
                    assigned_to,
                    status,
                    due_date,
                    completed_date,
                    priority,
                    project_id,
                    description,
                    created_date,
                ),
            )
            created_task_ids.append((cur.lastrowid, assigned_to, status, due_date, created_date, spec["name"], title))

    return created_projects, created_task_ids


def seed_queries_activity_and_logs(cur, created_projects):
    now = datetime.now()
    project_map = {spec["name"]: pid for pid, spec in created_projects}

    demo_queries = [
        ("Dev Patel", "Jarmil Patel", "[DEMO] Q2 Platform Revamp", "API dependency clarification", "Can we finalize the analytics API today?", "Open"),
        ("Ayush Patel", "Jarmil Patel", "[DEMO] Finance Workflow Automation", "Need approval on exception flow", "Please confirm fallback logic for finance edge cases.", "Open"),
        ("Jahan xyz", "Mohit Zinzuwadiya", "[DEMO] Client Success Portal", "Regression support needed", "I need one more reviewer on the regression plan.", "Open"),
    ]
    for user_name, tl_name, project_name, subject, message, status in demo_queries:
        cur.execute(
            """
            INSERT INTO queries (user_name, tl_name, project_id, subject, message, status, created_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                user_name,
                tl_name,
                project_map[project_name],
                subject,
                message,
                status,
                now.strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

    for project_id, spec in created_projects:
        actions = [
            (spec["manager"], "[DEMO] Project aligned with manager"),
            (spec["team_leader"], "[DEMO] Sprint plan approved by team leader"),
            ("Dev Patel", "[DEMO] Progress updated on key workstream"),
        ]
        for idx, (user_name, action) in enumerate(actions):
            ts = (now - timedelta(hours=idx * 5 + random.randint(1, 3))).strftime("%Y-%m-%d %H:%M:%S")
            cur.execute(
                "INSERT INTO activity_timeline (project_id, user_name, action, timestamp) VALUES (?,?,?,?)",
                (project_id, user_name, action, ts),
            )

    audit_entries = [
        ("Henil Patel", "[DEMO] Portfolio Review", "[DEMO] Reviewed delivery health across active projects."),
        ("Jarmil Patel", "[DEMO] Team Sync", "[DEMO] Updated sprint assignments and reviewed blockers."),
        ("Mohit Zinzuwadiya", "[DEMO] Quality Check", "[DEMO] Flagged regression risk on client portal."),
        ("Dev Patel", "[DEMO] Task Progress", "[DEMO] Logged progress on dashboard UX upgrade."),
        ("admin", "[DEMO] Analytics Snapshot", "[DEMO] Reviewed KPI trends and workforce signals."),
    ]
    for idx, (user, action, details) in enumerate(audit_entries):
        ts = (now - timedelta(hours=idx * 3)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            "INSERT INTO audit_logs (timestamp, user, action, details) VALUES (?,?,?,?)",
            (ts, user, action, details),
        )

    notifications = [
        ("[DEMO] Release Watch", "Two projects have milestones due within this week.", now.strftime("%I:%M %p"), "#f59e0b", "admin"),
        ("[DEMO] Manager Update", "Team leaders submitted fresh delivery updates.", now.strftime("%I:%M %p"), "#3b82f6", "Henil Patel"),
        ("[DEMO] Team Reminder", "Please update status before the stand-up.", now.strftime("%I:%M %p"), "#10b981", "Jarmil Patel"),
        ("[DEMO] Personal Reminder", "Log timesheet entries for your active tasks.", now.strftime("%I:%M %p"), "#8b5cf6", "Dev Patel"),
    ]
    for title, message, time_text, color, user in notifications:
        cur.execute(
            "INSERT INTO notifications (title, message, time, color, user) VALUES (?,?,?,?,?)",
            (title, message, time_text, color, user),
        )


def seed_attendance_and_timesheets(cur, created_task_ids):
    tracked_people = [
        "Dev Patel",
        "Ayush Patel",
        "sharavan panchal",
        "krishn shukala",
        "Jahan xyz",
        "Dhrumil xyz",
        "Jarmil Patel",
        "Mohit Zinzuwadiya",
    ]
    today = datetime.now().date()

    for person in tracked_people:
        for days_back in range(10):
            day = today - timedelta(days=days_back)
            if day.weekday() >= 5:
                continue
            status = "Present"
            clock_in = "09:30"
            clock_out = "18:15"
            if days_back == 3 and person in ("Dev Patel", "Jahan xyz"):
                status = "Late"
                clock_in = "10:12"
            elif days_back == 6 and person == "Ayush Patel":
                status = "WFH"
                clock_in = "09:10"
            cur.execute(
                """
                INSERT INTO attendance (name, date, time_in, time_out, status, clock_in, clock_out)
                VALUES (?,?,?,?,?,?,?)
                """,
                (person, day.strftime("%Y-%m-%d"), clock_in, clock_out, status, clock_in, clock_out),
            )

    task_lookup = {}
    for task_id, assigned_to, status, due_date, created_date, project_name, title in created_task_ids:
        task_lookup.setdefault(assigned_to, []).append((task_id, title, project_name))

    for person, task_rows in task_lookup.items():
        for idx, (task_id, title, project_name) in enumerate(task_rows[:4]):
            for days_back in range(3):
                day = today - timedelta(days=days_back + idx)
                if day.weekday() >= 5:
                    continue
                hours = round(1.5 + (idx * 0.7) + (days_back * 0.4), 1)
                cur.execute(
                    """
                    INSERT INTO timesheets (employee_name, date, task_id, hours, description, timestamp)
                    VALUES (?,?,?,?,?,?)
                    """,
                    (
                        person,
                        day.strftime("%Y-%m-%d"),
                        task_id,
                        hours,
                        f"Worked on {title} for {project_name}",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    ),
                )


def purge_demo_data(cur):
    cur.execute("SELECT id FROM projects WHERE name LIKE '[DEMO] %' OR name LIKE '%Onboarding – Himanshu%'")
    ids = [r[0] for r in cur.fetchall()]
    if ids:
        ph = ",".join("?" for _ in ids)
        cur.execute(f"DELETE FROM tasks WHERE project_id IN ({ph})", ids)
        try:
            cur.execute(f"DELETE FROM activity_timeline WHERE project_id IN ({ph})", ids)
        except Exception:
            pass
        try:
            cur.execute(f"DELETE FROM project_milestones WHERE project_id IN ({ph})", ids)
        except Exception:
            pass
        cur.execute(f"DELETE FROM queries WHERE project_id IN ({ph})", ids)
        cur.execute(f"DELETE FROM projects WHERE id IN ({ph})", ids)
    names = [
        "Dev Patel",
        "Ayush Patel",
        "sharavan panchal",
        "krishn shukala",
        "Jahan xyz",
        "Dhrumil xyz",
        "Jarmil Patel",
        "Mohit Zinzuwadiya",
        "Henil Patel",
    ]
    lower_names = [n.lower() for n in names]
    ph = ",".join("?" for _ in lower_names)
    try:
        cur.execute(f"DELETE FROM attendance WHERE lower(name) IN ({ph})", lower_names)
    except Exception:
        try:
            cur.execute(f"DELETE FROM attendance WHERE lower(employee_name) IN ({ph})", lower_names)
        except Exception:
            pass
    try:
        cur.execute(f"DELETE FROM timesheets WHERE lower(employee_name) IN ({ph})", lower_names)
    except Exception:
        pass
    cur.execute("DELETE FROM performance_history WHERE employee_name LIKE '[DEMO] %'")
    cur.execute("DELETE FROM audit_logs WHERE details LIKE '[DEMO] %' OR action LIKE '[DEMO] %'")
    cur.execute("DELETE FROM notifications WHERE title LIKE '[DEMO] %' OR message LIKE '[DEMO] %'")
    cur.execute(f"DELETE FROM employee WHERE lower(name) IN ({ph})", lower_names)


def seed_performance_history(cur):
    monthly_profiles = {
        "Dev Patel": [68, 71, 74, 78, 82, 86],
        "Ayush Patel": [62, 66, 69, 73, 76, 79],
        "sharavan panchal": [58, 61, 65, 68, 72, 75],
        "krishn shukala": [60, 63, 67, 70, 73, 77],
        "Jahan xyz": [55, 59, 63, 66, 69, 72],
        "Dhrumil xyz": [64, 67, 70, 74, 78, 81],
        "Jarmil Patel": [72, 76, 79, 83, 86, 89],
        "Mohit Zinzuwadiya": [69, 72, 75, 79, 82, 85],
        "Henil Patel": [74, 78, 81, 84, 87, 90],
    }

    today = datetime.now()
    months = [(today - timedelta(days=30 * offset)).strftime("%Y-%m") for offset in range(5, -1, -1)]

    for employee_name, scores in monthly_profiles.items():
        for month, score in zip(months, scores):
            tasks_assigned = 8 + (score % 5)
            tasks_completed = max(1, min(tasks_assigned, tasks_assigned - (100 - score) // 12))
            on_time_rate = round(min(0.98, 0.62 + (score / 200)), 2)
            attendance_rate = round(min(0.99, 0.84 + (score / 500)), 2)
            quality_rating = round(min(5.0, 2.8 + (score / 40)), 2)
            avg_task_priority = round(1.8 + ((score % 4) * 0.3), 2)
            cur.execute(
                """
                INSERT INTO performance_history
                (employee_name, month, tasks_assigned, tasks_completed, on_time_rate,
                 avg_task_priority, attendance_rate, quality_rating, productivity_score)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    employee_name,
                    month,
                    tasks_assigned,
                    tasks_completed,
                    on_time_rate,
                    avg_task_priority,
                    attendance_rate,
                    quality_rating,
                    score,
                ),
            )


def main():
    db_path = get_db_path()
    con = sqlite3.connect(db_path)
    cur = con.cursor()

    try:
        ensure_admin_user(cur)

        ensure_employee(cur, "Henil Patel", "9000000001", "henil@company.com", "Management", "Project Manager")
        ensure_employee(cur, "Jarmil Patel", "9000000002", "jarmil@company.com", "IT", "Team Leader")
        ensure_employee(cur, "Mohit Zinzuwadiya", "9000000003", "mohit@company.com", "Product", "Team Leader")
        ensure_employee(cur, "Dev Patel", "9000000004", "dev@gmail.com", "IT", "Team Member", "Jarmil Patel")
        ensure_employee(cur, "Ayush Patel", "9000000005", "ayush@company.com", "IT", "Team Member", "Jarmil Patel")
        ensure_employee(cur, "sharavan panchal", "9000000006", "sharavan@company.com", "IT", "Team Member", "Jarmil Patel")
        ensure_employee(cur, "krishn shukala", "9000000007", "krishn@company.com", "QA", "Team Member", "Jarmil Patel")
        ensure_employee(cur, "Jahan xyz", "9000000008", "jahan@company.com", "Product", "Team Member", "Mohit Zinzuwadiya")
        ensure_employee(cur, "Dhrumil xyz", "9000000009", "dhrumil@company.com", "Product", "Team Member", "Mohit Zinzuwadiya")
        ensure_employee(cur, "Himanshu Kotval", "9999999999", "himanshu@example.com", "IT", "Team Member", "Unassigned")

        clear_old_demo(cur)
        created_projects, created_task_ids = seed_projects_and_tasks(cur)
        seed_queries_activity_and_logs(cur, created_projects)
        seed_attendance_and_timesheets(cur, created_task_ids)
        seed_performance_history(cur)

        # Create a small personal project and tasks for Himanshu so the Employee Panel shows data
        try:
            today = datetime.now()
            cur.execute(
                """
                INSERT INTO projects
                (name, description, start_date, end_date, status, manager, team_leader, default_assignee, priority)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    "[DEMO] Onboarding – Himanshu",
                    "Getting started with PMS 2.0 employee workflow and dashboards.",
                    (today).strftime("%Y-%m-%d"),
                    (today + timedelta(days=21)).strftime("%Y-%m-%d"),
                    "Ongoing",
                    "Auto Seed",
                    "Unassigned",
                    "Himanshu Kotval",
                    "Medium",
                ),
            )
            him_proj_id = cur.lastrowid
            task_specs = [
                ("Complete Profile", "Pending", 3, "Fill basic profile and department details."),
                ("Read Team Guidelines", "In Progress", 7, "Review working agreements and rituals."),
                ("First Status Update", "Pending", 10, "Post initial update on My Tasks tab."),
            ]
            for title, status, due_in_days, desc in task_specs:
                due_date = (today + timedelta(days=due_in_days)).strftime("%Y-%m-%d")
                cur.execute(
                    """
                    INSERT INTO tasks (title, assigned_to, status, due_date, completed_date, priority, project_id, description, created_date)
                    VALUES (?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        title,
                        "Himanshu Kotval",
                        status,
                        due_date,
                        None,
                        "Medium",
                        him_proj_id,
                        desc,
                        today.strftime("%Y-%m-%d"),
                    ),
                )
        except Exception:
            pass

        con.commit()
        print("Demo panel data seeded successfully.")
        print("Suggested demo logins:")
        print("  Admin: admin / 1234")
        print("  Project Manager: Henil Patel / 1234")
        print("  Team Leader: Jarmil Patel / 1234")
        print("  Team Member: Dev Patel / 1234")
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("--clear-demo", "--purge-demo"):
        db_path = get_db_path()
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        try:
            purge_demo_data(cur)
            con.commit()
            print("Demo data removed.")
        finally:
            con.close()
    else:
        main()
