import os
import sqlite3
import json
import webbrowser
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "employee.db")
PORT = 8080

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

class DashboardHandler(BaseHTTPRequestHandler):
    # Disable default console logging to keep terminal clean
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # API: Get list of tables and row counts
        if path == "/api/tables":
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [r[0] for r in cursor.fetchall() if r[0] != "sqlite_sequence"]
                
                result = []
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM `{table}`;")
                    count = cursor.fetchone()[0]
                    result.append({"name": table, "count": count})
                
                conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_error(500, str(e))

        # API: Get data and columns for a specific table
        elif path == "/api/data":
            query = parse_qs(parsed_url.query)
            table_name = query.get("table", [None])[0]
            if not table_name:
                self.send_error(400, "Missing table parameter")
                return

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 500;")
                rows = cursor.fetchall()
                
                columns = [description[0] for description in cursor.description] if cursor.description else []
                data = [dict(row) for row in rows]
                
                conn.close()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"columns": columns, "data": data}).encode())
            except Exception as e:
                self.send_error(500, str(e))

        # Frontend SPA Page
        elif path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.get_frontend_html().encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def get_frontend_html(self):
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PMS Database Hub</title>
    <!-- Premium Fonts -->
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #0b0f19;
            --glass-bg: rgba(17, 24, 39, 0.7);
            --glass-border: rgba(255, 255, 255, 0.08);
            --text-primary: #f3f4f6;
            --text-secondary: #9ca3af;
            --accent-glow: #3b82f6;
            --accent-success: #10b981;
            --accent-warning: #f59e0b;
            --accent-error: #ef4444;
            --accent-purple: #8b5cf6;
            --sidebar-width: 280px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
            -webkit-font-smoothing: antialiased;
        }

        body {
            background-color: var(--bg-color);
            color: var(--text-primary);
            overflow-hidden: auto;
            min-height: 100vh;
            background-image: 
                radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(139, 92, 246, 0.15) 0px, transparent 50%);
            display: flex;
        }

        /* Sidebar Glassmorphism */
        .sidebar {
            width: var(--sidebar-width);
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-right: 1px solid var(--glass-border);
            display: flex;
            flex-direction: column;
            padding: 24px;
            position: fixed;
            height: 100vh;
            left: 0;
            top: 0;
            z-index: 10;
        }

        .logo-area {
            display: flex;
            align-items: center;
            gap: 12px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--glass-border);
            margin-bottom: 24px;
        }

        .logo-icon {
            width: 36px;
            height: 36px;
            background: linear-gradient(135deg, var(--accent-glow), var(--accent-purple));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            color: #fff;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.4);
        }

        .logo-text h1 {
            font-size: 1.1rem;
            font-weight: 700;
            background: linear-gradient(to right, #fff, #a7f3d0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .logo-text p {
            font-size: 0.75rem;
            color: var(--text-secondary);
        }

        .menu-title {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 12px;
            font-weight: 600;
        }

        .table-list {
            list-style: none;
            overflow-y: auto;
            flex-grow: 1;
            padding-right: 4px;
        }

        .table-list::-webkit-scrollbar {
            width: 4px;
        }
        .table-list::-webkit-scrollbar-thumb {
            background: var(--glass-border);
            border-radius: 4px;
        }

        .table-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 12px 16px;
            border-radius: 12px;
            cursor: pointer;
            margin-bottom: 8px;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            border: 1px solid transparent;
            color: var(--text-secondary);
        }

        .table-item:hover {
            background: rgba(255, 255, 255, 0.04);
            color: #fff;
        }

        .table-item.active {
            background: rgba(59, 130, 246, 0.15);
            border-color: rgba(59, 130, 246, 0.3);
            color: #fff;
            box-shadow: 0 4px 20px rgba(59, 130, 246, 0.1);
        }

        .table-name {
            font-size: 0.875rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .row-count {
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.08);
            padding: 2px 8px;
            border-radius: 20px;
            font-weight: 600;
        }

        .table-item.active .row-count {
            background: rgba(59, 130, 246, 0.3);
            color: #93c5fd;
        }

        /* Main Content Panel */
        .main-panel {
            margin-left: var(--sidebar-width);
            flex-grow: 1;
            padding: 40px;
            display: flex;
            flex-direction: column;
            gap: 24px;
            max-width: calc(100% - var(--sidebar-width));
        }

        /* Premium KPI Cards */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
        }

        .kpi-card {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            padding: 20px;
            border-radius: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.3s ease;
        }

        .kpi-card:hover {
            transform: translateY(-2px);
            border-color: rgba(255, 255, 255, 0.15);
        }

        .kpi-info h3 {
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .kpi-info p {
            font-size: 1.75rem;
            font-weight: 700;
        }

        .kpi-icon {
            width: 48px;
            height: 48px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.25rem;
        }

        .blue-kpi { background: rgba(59, 130, 246, 0.15); color: var(--accent-glow); }
        .green-kpi { background: rgba(16, 114, 181, 0.15); color: var(--accent-success); }
        .purple-kpi { background: rgba(139, 92, 246, 0.15); color: var(--accent-purple); }
        .orange-kpi { background: rgba(245, 158, 11, 0.15); color: var(--accent-warning); }

        /* Data Panel Header */
        .data-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 16px;
        }

        .data-header h2 {
            font-size: 1.5rem;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .search-container {
            position: relative;
            width: 320px;
        }

        .search-input {
            width: 100%;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 12px 16px 12px 40px;
            color: #fff;
            outline: none;
            transition: all 0.3s ease;
            font-size: 0.875rem;
        }

        .search-input:focus {
            background: rgba(255, 255, 255, 0.08);
            border-color: var(--accent-glow);
            box-shadow: 0 0 15px rgba(59, 130, 246, 0.2);
        }

        .search-icon {
            position: absolute;
            left: 14px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
            font-size: 0.9rem;
        }

        /* Glassmorphic Table Container */
        .table-container {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--glass-border);
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }

        .table-scroll {
            overflow-x: auto;
            max-height: calc(100vh - 350px);
            width: 100%;
        }

        .table-scroll::-webkit-scrollbar {
            height: 8px;
            width: 8px;
        }
        .table-scroll::-webkit-scrollbar-thumb {
            background: var(--glass-border);
            border-radius: 10px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }

        th {
            background: rgba(255, 255, 255, 0.02);
            color: #fff;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            padding: 16px 24px;
            border-bottom: 1px solid var(--glass-border);
            position: sticky;
            top: 0;
            z-index: 2;
        }

        td {
            padding: 16px 24px;
            font-size: 0.875rem;
            color: var(--text-secondary);
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            white-space: nowrap;
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
            color: #fff;
        }

        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .badge-completed, .badge-active, .badge-present {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
        }

        .badge-ongoing, .badge-pending {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
        }

        .badge-delayed, .badge-absent {
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px;
            text-align: center;
            color: var(--text-secondary);
            gap: 16px;
        }

        .empty-state-icon {
            font-size: 3rem;
            opacity: 0.3;
        }
    </style>
</head>
<body>

    <!-- Sidebar -->
    <div class="sidebar">
        <div class="logo-area">
            <div class="logo-icon">📊</div>
            <div class="logo-text">
                <h1>PMS Database</h1>
                <p>SQL-Free Core Hub</p>
            </div>
        </div>

        <div class="menu-title">Database Tables</div>
        <ul class="table-list" id="table-list">
            <!-- Populated via AJAX -->
        </ul>
    </div>

    <!-- Main Content Panel -->
    <div class="main-panel">
        
        <!-- KPI Headers -->
        <div class="kpi-container" id="kpi-container">
            <div class="kpi-card">
                <div class="kpi-info">
                    <h3>Total Employees</h3>
                    <p id="kpi-employees">-</p>
                </div>
                <div class="kpi-icon blue-kpi">👥</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-info">
                    <h3>Active Projects</h3>
                    <p id="kpi-projects">-</p>
                </div>
                <div class="kpi-icon green-kpi">📁</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-info">
                    <h3>Assigned Tasks</h3>
                    <p id="kpi-tasks">-</p>
                </div>
                <div class="kpi-icon purple-kpi">📝</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-info">
                    <h3>Database Status</h3>
                    <p style="font-size: 1.1rem; color: var(--accent-success); font-weight:600;">CONNECTED</p>
                </div>
                <div class="kpi-icon orange-kpi">🛡️</div>
            </div>
        </div>

        <!-- Data Filter Header -->
        <div class="data-header">
            <h2 id="current-table-title">Select a Table</h2>
            <div class="search-container">
                <span class="search-icon">🔍</span>
                <input type="text" class="search-input" id="search-input" placeholder="Search rows..." oninput="filterRows()">
            </div>
        </div>

        <!-- Scrollable Datagrid -->
        <div class="table-container">
            <div class="table-scroll">
                <table id="data-table">
                    <thead id="table-head">
                        <!-- Columns will inject here -->
                    </thead>
                    <tbody id="table-body">
                        <tr class="empty-state">
                            <td colspan="100%" style="text-align: center; border: none;">
                                <div class="empty-state-icon">📂</div>
                                <div>Click on any table in the sidebar to browse all values instantly.</div>
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>

    </div>

    <script>
        let currentRawData = [];
        let currentColumns = [];

        // Load Tables lists
        async function loadTables() {
            try {
                const res = await fetch('/api/tables');
                const tables = await res.json();
                const listEl = document.getElementById('table-list');
                listEl.innerHTML = '';
                
                tables.forEach(t => {
                    const li = document.createElement('li');
                    li.className = 'table-item';
                    li.onclick = () => loadTableData(t.name, li);
                    li.innerHTML = `
                        <div class="table-name"><span>📁</span> ${t.name}</div>
                        <div class="row-count">${t.count}</div>
                    `;
                    listEl.appendChild(li);

                    // Update Top level counts for main tables
                    if (t.name === 'employee') document.getElementById('kpi-employees').innerText = t.count;
                    if (t.name === 'projects') document.getElementById('kpi-projects').innerText = t.count;
                    if (t.name === 'tasks') document.getElementById('kpi-tasks').innerText = t.count;
                });
            } catch(e) {
                console.error("Error loading tables", e);
            }
        }

        // Fetch values for a table
        async function loadTableData(tableName, element) {
            // Update Active class
            document.querySelectorAll('.table-item').forEach(el => el.classList.remove('active'));
            if (element) element.classList.add('active');

            document.getElementById('current-table-title').innerText = tableName.charAt(0).toUpperCase() + tableName.slice(1);
            document.getElementById('search-input').value = '';

            try {
                const res = await fetch(`/api/data?table=${tableName}`);
                const payload = await res.json();
                currentRawData = payload.data;
                currentColumns = payload.columns;

                renderTable(currentColumns, currentRawData);
            } catch(e) {
                console.error(e);
            }
        }

        // Render columns and rows
        function renderTable(cols, rows) {
            const head = document.getElementById('table-head');
            const body = document.getElementById('table-body');
            head.innerHTML = '';
            body.innerHTML = '';

            if (cols.length === 0 || rows.length === 0) {
                body.innerHTML = `
                    <tr>
                        <td colspan="100%" class="empty-state">
                            <div class="empty-state-icon">📭</div>
                            <div>No rows found in this table.</div>
                        </td>
                    </tr>
                `;
                return;
            }

            // Render Header
            const hr = document.createElement('tr');
            cols.forEach(col => {
                const th = document.createElement('th');
                th.innerText = col.replace('_', ' ');
                hr.appendChild(th);
            });
            head.appendChild(hr);

            // Render Rows
            rows.forEach(row => {
                const tr = document.createElement('tr');
                cols.forEach(col => {
                    const td = document.createElement('td');
                    const val = row[col] === null ? '<span style="opacity:0.3">null</span>' : row[col];
                    
                    // Add beautiful badges for status values
                    if (col === 'status' && typeof val === 'string') {
                        const statusClass = val.toLowerCase().replace(' ', '');
                        td.innerHTML = `<span class="status-badge badge-${statusClass}">${val}</span>`;
                    } else {
                        td.innerHTML = val;
                    }
                    tr.appendChild(td);
                });
                body.appendChild(tr);
            });
        }

        // Live search filter inside active table
        function filterRows() {
            const q = document.getElementById('search-input').value.toLowerCase().trim();
            if (!q) {
                renderTable(currentColumns, currentRawData);
                return;
            }

            const filtered = currentRawData.filter(row => {
                return Object.values(row).some(val => 
                    val !== null && String(val).toLowerCase().includes(q)
                );
            });
            renderTable(currentColumns, filtered);
        }

        // Init load
        loadTables();
    </script>
</body>
</html>
"""

def start_server():
    server = HTTPServer(("127.0.0.1", PORT), DashboardHandler)
    server.serve_forever()

if __name__ == "__main__":
    print("🚀 Connecting to employee.db...")
    if not os.path.exists(DB_FILE):
        print(f"❌ Error: {DB_FILE} not found in current directory.")
        exit(1)

    # Start simple HTTP server in background thread
    t = threading.Thread(target=start_server, daemon=True)
    t.start()
    
    url = f"http://127.0.0.1:{PORT}"
    print(f"✨ PMS Glassmorphic Dashboard started successfully on {url}")
    print("🖥️ Opening web app in your default browser...")
    
    time.sleep(1)
    webbrowser.open(url)
    
    print("\nPress Ctrl+C inside this terminal window to stop the dashboard server anytime.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Stopping Dashboard server. Have a great day!")
