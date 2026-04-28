import sqlite3
import os

def add_indexes():
    db_path = 'employee.db'
    if not os.path.exists(db_path):
        return

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    indexes = [
        # Projects
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_projects_end_date ON projects(end_date)",
        "CREATE INDEX IF NOT EXISTS idx_projects_manager ON projects(manager)",
        "CREATE INDEX IF NOT EXISTS idx_projects_team_leader ON projects(team_leader)",
        
        # Tasks
        "CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority)",
        
        # Employee
        "CREATE INDEX IF NOT EXISTS idx_employee_name ON employee(name)",
        "CREATE INDEX IF NOT EXISTS idx_employee_dept ON employee(department)",
        "CREATE INDEX IF NOT EXISTS idx_employee_role ON employee(role)",
        
        # Attendance & Performance
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_name ON attendance(employee_name)",
        "CREATE INDEX IF NOT EXISTS idx_performance_month ON performance_history(month)",
        "CREATE INDEX IF NOT EXISTS idx_performance_emp_name ON performance_history(employee_name)",
        
        # Queries & Requests
        "CREATE INDEX IF NOT EXISTS idx_queries_user ON queries(user_name)",
        "CREATE INDEX IF NOT EXISTS idx_queries_status ON queries(status)",
        "CREATE INDEX IF NOT EXISTS idx_reset_status ON reset_requests(status)"
    ]

    for idx in indexes:
        try:
            cur.execute(idx)
            print(f"Executed: {idx}")
        except Exception as e:
            print(f"Error executing {idx}: {e}")

    con.commit()
    con.close()
    print("Database indexing complete.")

if __name__ == "__main__":
    add_indexes()
