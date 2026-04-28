"""
Enhanced Analytics Module for PMS 2.0
Provides comprehensive analytics with proper visualizations
"""

import sqlite3
import json
from datetime import datetime, timedelta
from collections import defaultdict
import math

# Database path helper
def get_db_path():
    return 'employee.db'

class AnalyticsEngine:
    """Comprehensive analytics engine for employee and project data"""

    def __init__(self):
        self.db_path = get_db_path()

    def get_db_connection(self):
        """Get database connection with row factory"""
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    # ==================== EMPLOYEE ANALYTICS ====================

    def get_employee_performance_summary(self):
        """Get comprehensive employee performance summary"""
        con = self.get_db_connection()
        cur = con.cursor()

        summary = {
            'total_employees': 0,
            'avg_productivity': 0,
            'top_performers': [],
            'underperformers': [],
            'performance_distribution': {'excellent': 0, 'good': 0, 'average': 0, 'poor': 0},
            'department_stats': []
        }

        try:
            # Total employees
            cur.execute("SELECT COUNT(*) FROM employee")
            summary['total_employees'] = cur.fetchone()[0]

            # Average productivity from performance history
            cur.execute("""
                SELECT AVG(productivity_score) as avg_score,
                       COUNT(DISTINCT employee_name) as emp_count
                FROM performance_history
                WHERE month = (SELECT MAX(month) FROM performance_history)
            """)
            row = cur.fetchone()
            if row and row['avg_score']:
                summary['avg_productivity'] = round(row['avg_score'], 2)

            # Performance distribution
            cur.execute("""
                SELECT employee_name, productivity_score
                FROM performance_history
                WHERE month = (SELECT MAX(month) FROM performance_history)
            """)
            for row in cur.fetchall():
                score = row['productivity_score'] or 0
                if score >= 90:
                    summary['performance_distribution']['excellent'] += 1
                elif score >= 75:
                    summary['performance_distribution']['good'] += 1
                elif score >= 60:
                    summary['performance_distribution']['average'] += 1
                else:
                    summary['performance_distribution']['poor'] += 1

            # Top performers (last month)
            cur.execute("""
                SELECT employee_name, productivity_score, tasks_completed, attendance_rate
                FROM performance_history
                WHERE month = (SELECT MAX(month) FROM performance_history)
                ORDER BY productivity_score DESC
                LIMIT 5
            """)
            summary['top_performers'] = [dict(r) for r in cur.fetchall()]

            # Underperformers (score < 60)
            cur.execute("""
                SELECT employee_name, productivity_score
                FROM performance_history
                WHERE month = (SELECT MAX(month) FROM performance_history)
                AND productivity_score < 60
                ORDER BY productivity_score ASC
                LIMIT 5
            """)
            summary['underperformers'] = [dict(r) for r in cur.fetchall()]

            # Department stats
            cur.execute("""
                SELECT department, COUNT(*) as count,
                       AVG(CASE WHEN ph.productivity_score IS NOT NULL
                           THEN ph.productivity_score ELSE 0 END) as avg_score
                FROM employee e
                LEFT JOIN performance_history ph ON e.name = ph.employee_name
                AND ph.month = (SELECT MAX(month) FROM performance_history)
                GROUP BY department
            """)
            summary['department_stats'] = [dict(r) for r in cur.fetchall()]

        except Exception as e:
            print(f"Error in employee performance summary: {e}")
        finally:
            con.close()

        return summary

    def get_monthly_trends(self, months=6):
        """Get monthly performance trends"""
        con = self.get_db_connection()
        cur = con.cursor()

        trends = {
            'months': [],
            'avg_productivity': [],
            'total_tasks': [],
            'attendance_rate': []
        }

        try:
            cur.execute("""
                SELECT month,
                       AVG(productivity_score) as avg_prod,
                       SUM(tasks_completed) as total_tasks,
                       AVG(attendance_rate) as avg_attendance
                FROM performance_history
                GROUP BY month
                ORDER BY month DESC
                LIMIT ?
            """, (months,))

            rows = cur.fetchall()
            for row in reversed(rows):
                trends['months'].append(row['month'])
                trends['avg_productivity'].append(round(row['avg_prod'] or 0, 2))
                trends['total_tasks'].append(row['total_tasks'] or 0)
                trends['attendance_rate'].append(round(row['avg_attendance'] or 0, 2))

        except Exception as e:
            print(f"Error in monthly trends: {e}")
        finally:
            con.close()

        return trends

    # ==================== PROJECT ANALYTICS ====================

    def get_project_analytics(self):
        """Get comprehensive project analytics"""
        con = self.get_db_connection()
        cur = con.cursor()

        analytics = {
            'total_projects': 0,
            'status_distribution': {},
            'priority_distribution': {},
            'completion_rate': 0,
            'overdue_count': 0,
            'avg_progress': 0,
            'projects_by_month': []
        }

        try:
            # Total projects
            cur.execute("SELECT COUNT(*) FROM projects")
            analytics['total_projects'] = cur.fetchone()[0]

            # Status distribution
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM projects
                GROUP BY status
            """)
            analytics['status_distribution'] = {r['status']: r['count'] for r in cur.fetchall()}

            # Priority distribution
            cur.execute("""
                SELECT priority, COUNT(*) as count
                FROM projects
                GROUP BY priority
            """)
            analytics['priority_distribution'] = {r['priority']: r['count'] for r in cur.fetchall()}

            # Average progress
            try:
                cur.execute("SELECT AVG(progress) FROM projects")
                row = cur.fetchone()
                analytics['avg_progress'] = round(row[0] or 0, 2)
            except:
                analytics['avg_progress'] = 0

            # Overdue projects
            today = datetime.now().strftime('%Y-%m-%d')
            cur.execute("""
                SELECT COUNT(*) FROM projects
                WHERE end_date < ? AND status != 'Completed'
            """, (today,))
            analytics['overdue_count'] = cur.fetchone()[0]

            # Projects created by month (last 6 months)
            try:
                cur.execute("""
                    SELECT strftime('%Y-%m', start_date) as month, COUNT(*) as count
                    FROM projects
                    WHERE start_date >= date('now', '-6 months')
                    GROUP BY month
                    ORDER BY month
                """)
                analytics['projects_by_month'] = [dict(r) for r in cur.fetchall()]
            except:
                analytics['projects_by_month'] = []

        except Exception as e:
            print(f"Error in project analytics: {e}")
        finally:
            con.close()

        return analytics

    def get_task_analytics(self):
        """Get comprehensive task analytics"""
        con = self.get_db_connection()
        cur = con.cursor()

        analytics = {
            'total_tasks': 0,
            'status_breakdown': {},
            'priority_breakdown': {},
            'completion_rate': 0,
            'avg_completion_time': 0,
            'tasks_by_employee': [],
            'overdue_tasks': 0
        }

        try:
            # Total tasks
            cur.execute("SELECT COUNT(*) FROM tasks")
            analytics['total_tasks'] = cur.fetchone()[0]

            # Status breakdown
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            """)
            analytics['status_breakdown'] = {r['status']: r['count'] for r in cur.fetchall()}

            # Priority breakdown
            cur.execute("""
                SELECT priority, COUNT(*) as count
                FROM tasks
                GROUP BY priority
            """)
            analytics['priority_breakdown'] = {r['priority']: r['count'] for r in cur.fetchall()}

            # Completion rate
            cur.execute("""
                SELECT
                    SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed,
                    COUNT(*) as total
                FROM tasks
            """)
            row = cur.fetchone()
            if row and row['total'] > 0:
                analytics['completion_rate'] = round((row['completed'] / row['total']) * 100, 2)

            # Tasks by employee
            cur.execute("""
                SELECT assigned_to, COUNT(*) as task_count,
                       SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) as completed
                FROM tasks
                GROUP BY assigned_to
                ORDER BY task_count DESC
                LIMIT 10
            """)
            analytics['tasks_by_employee'] = [dict(r) for r in cur.fetchall()]

            # Overdue tasks
            today = datetime.now().strftime('%Y-%m-%d')
            cur.execute("""
                SELECT COUNT(*) FROM tasks
                WHERE due_date < ? AND status != 'Completed'
            """, (today,))
            analytics['overdue_tasks'] = cur.fetchone()[0]

        except Exception as e:
            print(f"Error in task analytics: {e}")
        finally:
            con.close()

        return analytics

    # ==================== ATTENDANCE ANALYTICS ====================

    def get_attendance_analytics(self):
        """Get attendance analytics"""
        con = self.get_db_connection()
        cur = con.cursor()

        analytics = {
            'today_attendance': {'present': 0, 'absent': 0, 'late': 0},
            'weekly_trend': [],
            'attendance_by_department': [],
            'avg_attendance_rate': 0
        }

        try:
            # Today's attendance
            today = datetime.now().strftime('%Y-%m-%d')
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM attendance
                WHERE date = ?
                GROUP BY status
            """, (today,))
            for row in cur.fetchall():
                if row['status'].lower() in analytics['today_attendance']:
                    analytics['today_attendance'][row['status'].lower()] = row['count']

            # Weekly trend
            cur.execute("""
                SELECT date,
                       SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) as present,
                       COUNT(*) as total
                FROM attendance
                WHERE date >= date('now', '-7 days')
                GROUP BY date
                ORDER BY date
            """)
            analytics['weekly_trend'] = [dict(r) for r in cur.fetchall()]

            # Attendance by department
            cur.execute("""
                SELECT e.department,
                       AVG(CASE WHEN a.status = 'Present' THEN 100.0 ELSE 0.0 END) as rate
                FROM employee e
                LEFT JOIN attendance a ON e.name = a.employee_name
                AND a.date >= date('now', '-30 days')
                GROUP BY e.department
            """)
            analytics['attendance_by_department'] = [dict(r) for r in cur.fetchall()]

        except Exception as e:
            print(f"Error in attendance analytics: {e}")
        finally:
            con.close()

        return analytics

    # ==================== PREDICTIVE ANALYTICS ====================

    def get_performance_predictions(self):
        """Get performance predictions based on trends"""
        con = self.get_db_connection()
        cur = con.cursor()

        predictions = {
            'at_risk_employees': [],
            'rising_stars': [],
            'trend_analysis': []
        }

        try:
            # Get last 3 months of data for trend analysis
            cur.execute("""
                SELECT employee_name, month, productivity_score
                FROM performance_history
                WHERE month >= (SELECT MAX(month) FROM performance_history)
                ORDER BY employee_name, month
            """)

            employee_trends = defaultdict(list)
            for row in cur.fetchall():
                employee_trends[row['employee_name']].append({
                    'month': row['month'],
                    'score': row['productivity_score']
                })

            # Analyze trends
            for emp, scores in employee_trends.items():
                if len(scores) >= 2:
                    # Calculate trend
                    first_score = scores[0]['score']
                    last_score = scores[-1]['score']
                    change = last_score - first_score

                    if change < -10:
                        predictions['at_risk_employees'].append({
                            'name': emp,
                            'current_score': last_score,
                            'decline': round(abs(change), 2)
                        })
                    elif change > 10:
                        predictions['rising_stars'].append({
                            'name': emp,
                            'current_score': last_score,
                            'improvement': round(change, 2)
                        })

            # Sort by severity
            predictions['at_risk_employees'].sort(key=lambda x: x['decline'], reverse=True)
            predictions['rising_stars'].sort(key=lambda x: x['improvement'], reverse=True)

        except Exception as e:
            print(f"Error in performance predictions: {e}")
        finally:
            con.close()

        return predictions

    # ==================== DASHBOARD SUMMARY ====================

    def get_dashboard_summary(self):
        """Get complete dashboard summary"""
        return {
            'employee_summary': self.get_employee_performance_summary(),
            'monthly_trends': self.get_monthly_trends(),
            'project_stats': self.get_project_analytics(),
            'task_stats': self.get_task_analytics(),
            'attendance_stats': self.get_attendance_analytics(),
            'predictions': self.get_performance_predictions(),
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }


# Chart data generators for tkinter canvas
def generate_bar_chart_data(values, labels, max_bars=10):
    """Generate bar chart data for canvas drawing"""
    if not values or not labels:
        return None

    max_val = max(values) if values else 1
    data = []
    for i, (val, label) in enumerate(zip(values[:max_bars], labels[:max_bars])):
        percentage = (val / max_val) * 100 if max_val > 0 else 0
        data.append({
            'value': val,
            'label': label,
            'percentage': percentage,
            'index': i
        })
    return data


def generate_line_chart_data(points, labels):
    """Generate line chart data for canvas drawing"""
    if not points or len(points) < 2:
        return None

    min_val = min(points)
    max_val = max(points)
    range_val = max_val - min_val if max_val != min_val else 1

    data = []
    for i, (val, label) in enumerate(zip(points, labels)):
        normalized = ((val - min_val) / range_val) * 100 if range_val > 0 else 50
        data.append({
            'value': val,
            'label': label,
            'normalized': normalized,
            'index': i
        })
    return data


def generate_pie_chart_data(values, labels):
    """Generate pie chart data for canvas drawing"""
    if not values or not labels:
        return None

    total = sum(values)
    data = []
    colors = ['#4CAF50', '#2196F3', '#FF9800', '#F44336', '#9C27B0', '#00BCD4']

    for i, (val, label) in enumerate(zip(values, labels)):
        percentage = (val / total) * 100 if total > 0 else 0
        data.append({
            'value': val,
            'label': label,
            'percentage': percentage,
            'color': colors[i % len(colors)],
            'index': i
        })
    return data


# Export function
def export_analytics_to_json(analytics_data, filename='analytics_export.json'):
    """Export analytics data to JSON file"""
    try:
        with open(filename, 'w') as f:
            json.dump(analytics_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Export error: {e}")
        return False


def export_analytics_to_csv(data, filename='analytics_export.csv'):
    """Export analytics data to CSV file"""
    try:
        import csv
        with open(filename, 'w', newline='') as f:
            if data and len(data) > 0:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        return True
    except Exception as e:
        print(f"CSV export error: {e}")
        return False


if __name__ == '__main__':
    # Test the analytics engine
    engine = AnalyticsEngine()
    summary = engine.get_dashboard_summary()
    print(json.dumps(summary, indent=2))
