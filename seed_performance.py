import sqlite3
import random
import os
import sys
from datetime import datetime, timedelta

def get_db_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, 'employee.db')

def seed_data():
    con = sqlite3.connect(get_db_path())
    cur = con.cursor()

    # Create table
    cur.execute("""
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
            productivity_score REAL
        )
    """)
    cur.execute("DELETE FROM performance_history") # Clear old data

    # Get existing employees
    cur.execute("SELECT name FROM employee")
    employees = [r[0] for r in cur.fetchall()]
    
    if not employees:
        employees = [f"Employee_{i}" for i in range(1, 21)]
        # Also insert them into employee table if empty for consistency
        for name in employees:
            cur.execute("INSERT INTO employee (name, role, department) VALUES (?, 'Team Member', 'IT')", (name,))

    # Generate data for last 36 months (3 years)
    months = []
    current_date = datetime.now()
    for i in range(36):
        month_str = (current_date - timedelta(days=i*30)).strftime("%Y-%m")
        months.append(month_str)
    
    data_points = []
    for emp in employees:
        # Base stats for each employee to make them consistent
        base_on_time = random.uniform(0.6, 0.95)
        base_attendance = random.uniform(0.85, 0.99)
        base_quality = random.uniform(3.0, 5.0)
        
        for month in months:
            tasks_assigned = random.randint(5, 15)
            # Add some variance and noise to make the model learn robustly
            # Occasionally a bad month or a stellar month
            noise_factor = random.choice([0.8, 1.0, 1.0, 1.0, 1.2]) 
            
            tasks_completed = random.randint(max(0, int((tasks_assigned - 3) * noise_factor)), tasks_assigned)
            on_time_rate = min(1.0, (base_on_time + random.uniform(-0.15, 0.15)) * noise_factor)
            on_time_rate = max(0.4, on_time_rate)
            
            attendance_rate = min(1.0, (base_attendance + random.uniform(-0.1, 0.05)) * noise_factor)
            attendance_rate = max(0.5, attendance_rate)
            
            avg_priority = random.uniform(1, 3) # 1: Low, 2: Med, 3: High
            quality_rating = min(5.0, (base_quality + random.uniform(-1.0, 0.5)) * noise_factor)
            quality_rating = max(1.0, quality_rating)
            
            # Target variable: productivity_score (0-100)
            # Complex weighted formula with non-linear interaction
            comp_rate = tasks_completed / tasks_assigned if tasks_assigned > 0 else 0
            
            # Base score from linear components
            score = (comp_rate * 35) + (on_time_rate * 25) + (attendance_rate * 15) + (quality_rating/5 * 15)
            
            # Add non-linear bonus for high priority tasks done well
            if avg_priority > 2.5 and comp_rate > 0.9:
                score += 10
            
            # Add penalty for low attendance
            if attendance_rate < 0.8:
                score -= 5
                
            score = max(0, min(100, score)) # Ensure 0-100 range
            score = round(score, 2)

            data_points.append((emp, month, tasks_assigned, tasks_completed, 
                               round(on_time_rate, 2), round(avg_priority, 2), 
                               round(attendance_rate, 2), round(quality_rating, 2), score))

    cur.executemany("""
        INSERT INTO performance_history 
        (employee_name, month, tasks_assigned, tasks_completed, on_time_rate, avg_task_priority, attendance_rate, quality_rating, productivity_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data_points)

    con.commit()
    print(f"Generated {len(data_points)} records for {len(employees)} employees.")
    con.close()

if __name__ == "__main__":
    seed_data()
