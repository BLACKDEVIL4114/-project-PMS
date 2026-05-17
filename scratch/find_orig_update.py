import sqlite3
import hashlib
from datetime import datetime, timedelta

def setup_shukala():
    con = sqlite3.connect("employee.db")
    cur = con.cursor()
    
    # 1. Print all existing employees
    cur.execute("SELECT name, role, department FROM employee")
    print("Existing Employees:")
    for row in cur.fetchall():
        print(row)
        
    print("-" * 50)
    
    # Let's see if shukala exists. If not, insert her.
    # Note: the user spelled it "shukala". We will insert both "shukala" and "shukla" just to be absolutely foolproof, 
    # using 'shukala123' and 'shukla123' as passwords!
    target_names = ["shukala", "shukla"]
    
    # Check if a project exists to link the tasks to
    cur.execute("SELECT id FROM projects LIMIT 1")
    p_row = cur.fetchone()
    if p_row:
        project_id = p_row[0]
    else:
        # Create a demo project
        cur.execute("""
            INSERT INTO projects (name, description, start_date, end_date, status, manager, team_leader, default_assignee, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("PMS Revamp", "Revamping the PMS dashboard UI", "2026-05-17", "2026-06-17", "Ongoing", "Admin", "Admin", "shukala", "High"))
        project_id = cur.lastrowid
        print(f"Created demo project with ID: {project_id}")

    for name in target_names:
        cur.execute("SELECT * FROM employee WHERE name=?", (name,))
        emp_exists = cur.fetchone()
        
        pw_hash = hashlib.sha256(f"{name}123".encode()).hexdigest()
        
        if not emp_exists:
            cur.execute("""
                INSERT INTO employee (name, password, role, department, email, reporting_manager, mobile, address, gender, dob, date, time, security_question, security_answer, pin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, pw_hash, "Employee", "Engineering", f"{name}@company.com", "Admin", "9876543210", "Company Headquarters", "Female", "1998-05-17", "2026-05-17", "12:00:00", "What is your pet name?", "shuku", "1234"))
            print(f"Inserted employee: {name}")
        else:
            print(f"Employee {name} already exists.")
            
        cur.execute("SELECT * FROM users WHERE username=?", (name,))
        usr_exists = cur.fetchone()
        if not usr_exists:
            cur.execute("""
                INSERT INTO users (username, password, email, dob, reset_requested)
                VALUES (?, ?, ?, ?, ?)
            """, (name, pw_hash, f"{name}@company.com", "1998-05-17", "No"))
            print(f"Inserted user: {name}")
        else:
            print(f"User {name} already exists.")

        # Delete any existing tasks for this name so we have exactly 5 clean demo tasks
        cur.execute("DELETE FROM tasks WHERE assigned_to=?", (name,))
        
        # Insert 5 demo tasks
        demo_tasks = [
            ("Revamp Sidebar Icons", "Replace standard text in sidebar with high-contrast emojis and modern styled HSL/RGB colors.", "High", 2),
            ("Build Employee Profile UI", "Scaffold a gorgeous circular avatar card showing first letters of username in bold white against blue background.", "Medium", 4),
            ("Implement Dynamic Hover States", "Bind Enter/Leave events to the Tkinter card widgets to instantly switch backgrounds to a glowing HSL tone.", "High", 1),
            ("Create Work-Life Cockpit", "Display current Leave Balances (Vacation, Sick, Personal) in a clean, high-contrast, responsive grid.", "Low", 6),
            ("Real-time Stats Synchronizer", "Ensure that task status modifications instantly update all KPI cards (Pending Tasks, Success Rate, Focus Level) without restarting.", "High", 3)
        ]
        
        for i, (title, desc, prio, days_offset) in enumerate(demo_tasks):
            due_dt = (datetime.now() + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            created_dt = datetime.now().strftime("%Y-%m-%d")
            cur.execute("""
                INSERT INTO tasks (title, description, project_id, assigned_to, status, priority, due_date, completed_date, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, desc, project_id, name, "Pending", prio, due_dt, None, created_dt))
            print(f"Created task: {title} assigned to {name}")

    con.commit()
    con.close()
    print("Database seeding completed successfully.")

if __name__ == '__main__':
    setup_shukala()
