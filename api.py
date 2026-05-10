"""
PMS 2.0 - REST API
Secured with X-API-Key authentication. All inputs validated.
Run: python api.py
"""

from flask import Flask, jsonify, request
import sqlite3
import os

from config import API_KEY, DB_NAME, API_HOST, API_PORT, API_DEBUG
from validators import validate_task, validate_project, is_safe_input, validate_api_key
from logger import api_logger, log_api_request, log_db_error

app = Flask(__name__)


# ─────────────────────────────────────────────
# DB Helper
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ─────────────────────────────────────────────
# Authentication Decorator
# ─────────────────────────────────────────────
def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-API-Key", "")
        authenticated = validate_api_key(key, API_KEY)
        log_api_request(request.path, request.method, authenticated, 401 if not authenticated else 200)
        if not authenticated:
            return jsonify({"error": "Unauthorized. Provide X-API-Key header."}), 401
        return f(*args, **kwargs)
    return decorated


# ─────────────────────────────────────────────
# Error Handlers
# ─────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Method not allowed"}), 405


# ─────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────
@app.route("/")
@require_auth
def home():
    return jsonify({
        "status": "running",
        "app": "Project Monitoring System API",
        "version": "2.0.0",
        "endpoints": ["/api/projects", "/api/tasks", "/api/members", "/api/stats/summary"]
    })


# ═══════════════════════════════════════════════
# PROJECTS
# ═══════════════════════════════════════════════
@app.route("/api/projects", methods=["GET"])
@require_auth
def get_projects():
    """List projects. Optional ?status= and ?search= filters."""
    try:
        status = request.args.get("status", "")
        search = request.args.get("search", "")
        query  = "SELECT * FROM projects WHERE 1=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if search:
            query += " AND (name LIKE ? OR team_leader LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY id DESC"
        conn = get_db()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_db_error("get_projects", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<int:pid>", methods=["GET"])
@require_auth
def get_project(pid):
    """Get a single project by ID."""
    try:
        conn = get_db()
        row  = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        conn.close()
        if not row:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(dict(row))
    except Exception as e:
        log_db_error("get_project", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects", methods=["POST"])
@require_auth
def create_project():
    """Create a new project. JSON body required."""
    try:
        data = request.get_json(force=True)
        name       = data.get("name", "").strip()
        start_date = data.get("start_date", "")
        end_date   = data.get("end_date", "")
        description = data.get("description", "")
        team_leader = data.get("team_leader", "")

        result = validate_project(name, start_date, end_date, description)
        if not result:
            return jsonify({"error": result.all_errors()}), 400

        conn = get_db()
        conn.execute(
            "INSERT INTO projects (name, team_leader, start_date, end_date, description, status) VALUES (?,?,?,?,?,'Ongoing')",
            (name, team_leader, start_date, end_date, description)
        )
        conn.commit()
        pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        api_logger.info(f"Project created: id={pid} name='{name}'")
        return jsonify({"message": "Project created", "id": pid}), 201
    except Exception as e:
        log_db_error("create_project", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<int:pid>", methods=["PUT"])
@require_auth
def update_project(pid):
    """Update a project by ID."""
    try:
        data   = request.get_json(force=True)
        conn   = get_db()
        exists = conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone()
        if not exists:
            conn.close()
            return jsonify({"error": "Project not found"}), 404

        fields, params = [], []
        allowed = {"name", "team_leader", "start_date", "end_date", "description", "status", "priority"}
        for key, val in data.items():
            if key in allowed:
                if not is_safe_input(str(val)):
                    return jsonify({"error": f"Invalid input in field '{key}'"}), 400
                fields.append(f"{key}=?")
                params.append(val)

        if not fields:
            conn.close()
            return jsonify({"error": "No valid fields provided"}), 400

        params.append(pid)
        conn.execute(f"UPDATE projects SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
        conn.close()
        return jsonify({"message": "Project updated"})
    except Exception as e:
        log_db_error("update_project", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/projects/<int:pid>", methods=["DELETE"])
@require_auth
def delete_project(pid):
    """Delete a project and its tasks."""
    try:
        conn = get_db()
        if not conn.execute("SELECT id FROM projects WHERE id=?", (pid,)).fetchone():
            conn.close()
            return jsonify({"error": "Project not found"}), 404
        conn.execute("DELETE FROM tasks WHERE project_id=?", (pid,))
        conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        conn.commit()
        conn.close()
        api_logger.info(f"Project deleted: id={pid}")
        return jsonify({"message": "Project deleted"})
    except Exception as e:
        log_db_error("delete_project", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════
# TASKS
# ═══════════════════════════════════════════════
@app.route("/api/tasks", methods=["GET"])
@require_auth
def get_tasks():
    """List tasks. Optional ?status=, ?priority=, ?assigned_to= filters."""
    try:
        query, params = "SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON t.project_id=p.id WHERE 1=1", []
        for field in ("status", "priority", "assigned_to"):
            val = request.args.get(field)
            if val:
                query += f" AND t.{field}=?"
                params.append(val)
        search = request.args.get("search", "")
        if search:
            query += " AND (t.title LIKE ? OR t.assigned_to LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        query += " ORDER BY t.id DESC"
        conn = get_db()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_db_error("get_tasks", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/project/<int:pid>", methods=["GET"])
@require_auth
def get_project_tasks(pid):
    try:
        conn = get_db()
        rows = conn.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_db_error("get_project_tasks", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks", methods=["POST"])
@require_auth
def create_task():
    """Create a new task."""
    try:
        data     = request.get_json(force=True)
        title    = data.get("title", "").strip()
        due_date = data.get("due_date", "")
        priority = data.get("priority", "Medium")
        status   = data.get("status", "Pending")

        result = validate_task(title, due_date, priority, status)
        if not result:
            return jsonify({"error": result.all_errors()}), 400

        conn = get_db()
        conn.execute(
            "INSERT INTO tasks (title, description, project_id, assigned_to, due_date, priority, status, created_date) VALUES (?,?,?,?,?,?,?,date('now'))",
            (title, data.get("description",""), data.get("project_id"), data.get("assigned_to",""), due_date, priority, status)
        )
        conn.commit()
        tid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()
        return jsonify({"message": "Task created", "id": tid}), 201
    except Exception as e:
        log_db_error("create_task", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<int:tid>", methods=["PUT"])
@require_auth
def update_task(tid):
    """Update a task by ID."""
    try:
        data = request.get_json(force=True)
        conn = get_db()
        if not conn.execute("SELECT id FROM tasks WHERE id=?", (tid,)).fetchone():
            conn.close()
            return jsonify({"error": "Task not found"}), 404

        fields, params = [], []
        allowed = {"title", "description", "assigned_to", "due_date", "priority", "status"}
        for key, val in data.items():
            if key in allowed:
                if not is_safe_input(str(val)):
                    return jsonify({"error": f"Invalid input in field '{key}'"}), 400
                fields.append(f"{key}=?")
                params.append(val)
        if not fields:
            conn.close()
            return jsonify({"error": "No valid fields"}), 400
        params.append(tid)
        conn.execute(f"UPDATE tasks SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()
        conn.close()
        return jsonify({"message": "Task updated"})
    except Exception as e:
        log_db_error("update_task", e)
        return jsonify({"error": str(e)}), 500


@app.route("/api/tasks/<int:tid>", methods=["DELETE"])
@require_auth
def delete_task(tid):
    try:
        conn = get_db()
        if not conn.execute("SELECT id FROM tasks WHERE id=?", (tid,)).fetchone():
            conn.close()
            return jsonify({"error": "Task not found"}), 404
        conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
        conn.commit()
        conn.close()
        return jsonify({"message": "Task deleted"})
    except Exception as e:
        log_db_error("delete_task", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════
# MEMBERS
# ═══════════════════════════════════════════════
@app.route("/api/members", methods=["GET"])
@require_auth
def get_members():
    try:
        search = request.args.get("search", "")
        role   = request.args.get("role", "")
        query  = "SELECT id, name, email, role, gender, mobile, dob FROM employee WHERE 1=1"
        params = []
        if search:
            query += " AND (name LIKE ? OR email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        if role:
            query += " AND role=?"
            params.append(role)
        conn = get_db()
        rows = conn.execute(query, params).fetchall()
        conn.close()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        log_db_error("get_members", e)
        return jsonify({"error": str(e)}), 500


# ═══════════════════════════════════════════════
# STATS
# ═══════════════════════════════════════════════
@app.route("/api/stats/summary", methods=["GET"])
@require_auth
def get_stats_summary():
    try:
        conn = get_db()
        def count(q, *p): return conn.execute(q, p).fetchone()[0]
        data = {
            "projects": {
                "total":     count("SELECT COUNT(*) FROM projects"),
                "ongoing":   count("SELECT COUNT(*) FROM projects WHERE status='Ongoing'"),
                "completed": count("SELECT COUNT(*) FROM projects WHERE status='Completed'"),
                "delayed":   count("SELECT COUNT(*) FROM projects WHERE status='Delayed'"),
            },
            "tasks": {
                "total":       count("SELECT COUNT(*) FROM tasks"),
                "completed":   count("SELECT COUNT(*) FROM tasks WHERE status='Completed'"),
                "pending":     count("SELECT COUNT(*) FROM tasks WHERE status='Pending'"),
                "in_progress": count("SELECT COUNT(*) FROM tasks WHERE status='In Progress'"),
            },
            "members": {
                "total": count("SELECT COUNT(*) FROM employee"),
            }
        }
        conn.close()
        return jsonify(data)
    except Exception as e:
        log_db_error("get_stats_summary", e)
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(DB_NAME):
        print(f"[!] Database '{DB_NAME}' not found. Run login.py first to initialize it.")
    else:
        print(f"[*] PMS API starting on http://{API_HOST}:{API_PORT}")
        print(f"[*] Auth header: X-API-Key: {API_KEY}")
        app.run(host=API_HOST, port=API_PORT, debug=API_DEBUG)
