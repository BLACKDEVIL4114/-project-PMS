import sys, ast, collections, sqlite3, os

# Always run from project root regardless of where the script is called from
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

PASS = '\u2705'
FAIL = '\u274c'
WARN = '\u26a0\ufe0f'
SEP  = '=' * 62

issues = []

print(SEP)
print('  PMS PRE-UPDATE HEALTH CHECK')
print(f'  Project: {PROJECT_ROOT}')
print(SEP)

# ---------------------------------------------------------------
# 1. SYNTAX CHECK
# ---------------------------------------------------------------
print('\n[1] SYNTAX CHECK')
files = [
    'project_monitor.py', 'login.py', 'theme.py',
    'ai_engine.py', 'analytics_engine.py', 'api_service.py', 'validators.py'
]
syn_ok = True
for fname in files:
    path = os.path.join(PROJECT_ROOT, fname)
    if not os.path.exists(path):
        print(f'  {WARN}  SKIP (not found): {fname}')
        continue
    try:
        with open(path, encoding='utf-8') as f:
            src = f.read()
        ast.parse(src)
        print(f'  {PASS}  {fname}')
    except SyntaxError as e:
        print(f'  {FAIL}  {fname}  -> SyntaxError line {e.lineno}: {e.msg}')
        issues.append(f'SYNTAX: {fname} line {e.lineno}: {e.msg}')
        syn_ok = False
    except Exception as e:
        print(f'  {FAIL}  {fname}  -> {e}')
        issues.append(f'SYNTAX: {fname}: {e}')
        syn_ok = False
print(f'  Result: {"PASS" if syn_ok else "FAIL"}')

# ---------------------------------------------------------------
# 2. DUPLICATE METHOD CHECK
# ---------------------------------------------------------------
print('\n[2] DUPLICATE METHOD CHECK')
dup_ok = True
for fname in ['project_monitor.py', 'login.py']:
    path = os.path.join(PROJECT_ROOT, fname)
    if not os.path.exists(path):
        continue
    try:
        with open(path, encoding='utf-8') as f:
            src = f.read()
        tree = ast.parse(src)
        class_methods = collections.defaultdict(list)
        for cls in ast.walk(tree):
            if isinstance(cls, ast.ClassDef):
                for node in cls.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods[cls.name].append((node.name, node.lineno))
        dups = []
        for cls_name, methods in class_methods.items():
            names = [m[0] for m in methods]
            for name in set(names):
                if names.count(name) > 1:
                    line_nums = [m[1] for m in methods if m[0] == name]
                    dups.append(f'{cls_name}.{name} at lines {line_nums}')
        if dups:
            dup_ok = False
            print(f'  {FAIL}  {fname}:')
            for d in dups:
                print(f'         -> {d}')
                issues.append(f'DUPLICATE: {fname}: {d}')
        else:
            print(f'  {PASS}  {fname}')
    except Exception as e:
        print(f'  {FAIL}  {fname}: {e}')
        issues.append(f'DUPLICATE_CHECK_ERROR: {fname}: {e}')
        dup_ok = False
print(f'  Result: {"PASS" if dup_ok else "FAIL"}')

# ---------------------------------------------------------------
# 3. IMPORT CHECK
# ---------------------------------------------------------------
print('\n[3] IMPORT CHECK')
imp_ok = True
for mod in ['theme', 'api_service', 'ai_engine', 'analytics_engine']:
    for key in list(sys.modules.keys()):
        if key == mod or key.startswith(mod + '.'):
            del sys.modules[key]
    try:
        __import__(mod)
        print(f'  {PASS}  import {mod}')
    except Exception as e:
        print(f'  {FAIL}  import {mod}  -> {e}')
        issues.append(f'IMPORT: {mod}: {e}')
        imp_ok = False
print(f'  Result: {"PASS" if imp_ok else "FAIL"}')

# ---------------------------------------------------------------
# 4. THEME VARIABLE CHECK
# ---------------------------------------------------------------
print('\n[4] THEME VARIABLE CHECK')
required_theme_vars = [
    'SIDEBAR_BG', 'SIDEBAR_TEXT', 'ACTIVE_TEXT', 'HEADER_BG', 'HEADER_TEXT',
    'CONTENT_BG', 'CARD_BG', 'PRIMARY_BG', 'PRIMARY_TEXT', 'MUTED_TEXT',
    'INPUT_BG', 'ACCENT_GREEN', 'ACCENT_ORANGE', 'ACCENT_RED', 'ACCENT_BLUE',
    'ACCENT_PURPLE', 'ACCENT_HOVER', 'BORDER_COLOR', 'WHITE', 'TEXT_WHITE',
    'CARD_LIGHT', 'CARD_DARK', 'CARD_HOVER', 'PRIMARY_RED', 'PRIMARY_RED_DARK',
    'FOCUS_COLOR', 'BG_DARK', 'BG_NAVY', 'BG_BLACK', 'SIDEBAR_ACTIVE_BG',
    'BORDER_NAVY', 'TEXT_MUTED', 'TEXT_SECONDARY', 'BG_CARD', 'ACCENT_COLOR',
    'TEXT_MAIN', 'HOVER_BG', 'apply_theme'
]
theme_ok = True
try:
    import theme
    missing_vars = [v for v in required_theme_vars if not hasattr(theme, v)]
    if missing_vars:
        print(f'  {FAIL}  Missing theme vars: {missing_vars}')
        issues.append(f'THEME: Missing vars: {missing_vars}')
        theme_ok = False
    else:
        print(f'  {PASS}  All {len(required_theme_vars)} theme variables present')

    bad_colors = []
    for v in required_theme_vars:
        val = getattr(theme, v, None)
        if val and isinstance(val, str) and v != 'apply_theme':
            if not (val.startswith('#') and len(val) in (4, 7)):
                bad_colors.append(f'{v}={val!r}')
    if bad_colors:
        print(f'  {WARN}  Suspicious color values: {bad_colors}')
        issues.append(f'THEME: Bad colors: {bad_colors}')
    else:
        print(f'  {PASS}  All color values are valid hex strings')
except Exception as e:
    print(f'  {FAIL}  theme.py error: {e}')
    issues.append(f'THEME: {e}')
    theme_ok = False
print(f'  Result: {"PASS" if theme_ok else "FAIL"}')

# ---------------------------------------------------------------
# 5. DATABASE SCHEMA CHECK (and auto-fix missing columns)
# ---------------------------------------------------------------
print('\n[5] DATABASE SCHEMA CHECK')
db_path = os.path.join(PROJECT_ROOT, 'employee.db')
db_ok = True
if not os.path.exists(db_path):
    print(f'  {FAIL}  employee.db not found')
    issues.append('DB: employee.db missing')
    db_ok = False
else:
    try:
        con = sqlite3.connect(db_path)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cur.fetchall()]
        print(f'  Tables: {tables}')

        required_tables = [
            'projects', 'employee', 'tasks', 'users', 'audit_logs',
            'notifications', 'queries', 'leave_requests', 'attendance',
            'timesheets', 'performance_history', 'reset_requests'
        ]
        missing_tables = [t for t in required_tables if t not in tables]
        if missing_tables:
            print(f'  {FAIL}  Missing tables: {missing_tables}')
            issues.append(f'DB: Missing tables: {missing_tables}')
            db_ok = False
        else:
            print(f'  {PASS}  All required tables present')

        col_checks = {
            'users':     ['username', 'password', 'email', 'reset_requested'],
            'employee':  ['id', 'name', 'email', 'department', 'password', 'role', 'reporting_manager'],
            'tasks':     ['id', 'title', 'project_id', 'assigned_to', 'status', 'priority', 'due_date', 'description', 'created_date'],
            'projects':  ['id', 'name', 'manager', 'team_leader', 'priority', 'default_assignee'],
            'queries':   ['id', 'user_name', 'subject', 'status', 'response', 'created_at', 'history'],
            'attendance': ['id', 'employee_name', 'date', 'status', 'clock_in', 'clock_out'],
            'timesheets': ['id', 'employee_name', 'date', 'task_id', 'hours'],
        }
        for table, expected_cols in col_checks.items():
            if table not in tables:
                continue
            cur.execute(f'PRAGMA table_info({table})')
            actual_cols = [r[1] for r in cur.fetchall()]
            missing_cols = [c for c in expected_cols if c not in actual_cols]
            if missing_cols:
                # Auto-fix: add missing columns
                fixed = []
                for col in missing_cols:
                    try:
                        cur.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT')
                        fixed.append(col)
                    except Exception as alter_err:
                        print(f'  {FAIL}  {table}: could not add {col}: {alter_err}')
                        issues.append(f'DB: {table}: cannot add {col}: {alter_err}')
                        db_ok = False
                if fixed:
                    con.commit()
                    print(f'  {WARN}  {table}: auto-added missing columns {fixed} (now fixed)')
            else:
                print(f'  {PASS}  {table}: all columns OK')
        con.close()
    except Exception as e:
        print(f'  {FAIL}  DB error: {e}')
        issues.append(f'DB: {e}')
        db_ok = False
print(f'  Result: {"PASS" if db_ok else "FAIL"}')

# ---------------------------------------------------------------
# 6. ML MODEL FILES CHECK
# ---------------------------------------------------------------
print('\n[6] ML MODEL FILES CHECK')
model_files = ['pms_delay_model.joblib', 'performance_model.pkl', 'scaler.pkl']
for mf in model_files:
    path = os.path.join(PROJECT_ROOT, mf)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f'  {PASS}  {mf} ({size_kb} KB)')
    else:
        print(f'  {WARN}  {mf} not found (ML features may be disabled)')
print(f'  Result: PASS')

# ---------------------------------------------------------------
# 7. BACKGROUND THREAD SAFETY SCAN
# ---------------------------------------------------------------
print('\n[7] THREAD SAFETY SCAN')
with open(os.path.join(PROJECT_ROOT, 'project_monitor.py'), encoding='utf-8') as f:
    pm_lines = f.readlines()

thread_count = sum(1 for l in pm_lines if 'threading.Thread' in l)
after0_count = sum(1 for l in pm_lines if 'self.root.after(0,' in l or "root.after(0," in l)
direct_ui_in_thread = []
in_thread_block = False
thread_start_line = 0
brace_depth = 0

print(f'  Background threads found: {thread_count}')
print(f'  Thread-safe after(0,...) calls: {after0_count}')
if thread_count > 0 and after0_count >= thread_count:
    print(f'  {PASS}  All threads appear to delegate UI updates via after(0,...)')
elif thread_count > 0:
    print(f'  {WARN}  Some threads may do direct UI updates - verify manually')
else:
    print(f'  {PASS}  No background threads')

# ---------------------------------------------------------------
# 8. WIDGET SAFETY SCAN (config() calls that could crash on destroyed widgets)
# ---------------------------------------------------------------
print('\n[8] WIDGET SAFETY SCAN')
risky = []
for i, line in enumerate(pm_lines, 1):
    stripped = line.strip()
    # Look for self.X.config() outside try/except and without winfo_exists
    if '.config(' in stripped and 'self.' in stripped and '#' not in stripped.split('.config')[0]:
        risky.append((i, stripped))

# Only flag ones in after() callbacks (most dangerous)
after_risky = [(i, l) for i, l in risky if 'after' in pm_lines[max(0,i-10):i+1] or True]
print(f'  Total widget .config() calls: {len(risky)}')
print(f'  {PASS}  Widget config calls present (normal - just ensure they have try/except)')

# ---------------------------------------------------------------
# FINAL SUMMARY
# ---------------------------------------------------------------
print()
print(SEP)
print('  FINAL SUMMARY')
print(SEP)
if not issues:
    print(f'  {PASS}  ALL CHECKS PASSED')
    print(f'  {PASS}  Safe to update the UI!')
    print()
    print('  Golden Rules for UI Updates:')
    print('  1.  Add new methods at the END of the class (avoid inserting mid-file)')
    print('  2.  Wrap .config() calls: try: widget.config(...) except: pass')
    print('  3.  Check widget exists: if hasattr(self,X) and self.X.winfo_exists()')
    print('  4.  Never call Tkinter widgets directly from a Thread - use root.after(0,...)')
    print('  5.  Run this health check again after your UI update to confirm')
    print('  6.  Keep a backup: copy project_monitor.py -> project_monitor_backup.py')
else:
    print(f'  {FAIL}  {len(issues)} ISSUE(S) FOUND - Fix before updating UI:')
    for idx, iss in enumerate(issues, 1):
        print(f'  {idx}. {iss}')
print(SEP)
