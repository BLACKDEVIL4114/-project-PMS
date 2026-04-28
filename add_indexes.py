import sqlite3
import os

def add_indexes():
    db_path = 'employee.db'
    if not os.path.exists(db_path):
        return

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)",
        "CREATE INDEX IF NOT EXISTS idx_projects_end_date ON projects(end_date)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)",
        "CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)",
        "CREATE INDEX IF NOT EXISTS idx_performance_month ON performance_history(month)",
        "CREATE INDEX IF NOT EXISTS idx_performance_emp_name ON performance_history(employee_name)"
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
