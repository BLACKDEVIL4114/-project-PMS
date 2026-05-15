from tkinter import *
from tkinter import ttk
from tkinter import messagebox
import sqlite3
import hashlib
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
import importlib
import random
import re

from PIL import Image, ImageTk
# FIX 1: Expanded import — added CONTENT_BG, CARD_BG, MUTED_TEXT which were used
# in login.py but never imported (caused NameError on login screen widgets).
# Also ACCENT_COLOR and TEXT_MAIN are now defined in theme.py (Fix 1 in theme.py).
from theme import (
    BG_COLOR, SIDEBAR_BG, ACCENT_COLOR, ACCENT_HOVER, TEXT_MAIN, TEXT_MUTED,
    WHITE, INPUT_BG, INPUT_FG, BORDER_COLOR, apply_theme, CARD_LIGHT, LINK_BLUE,
    FOCUS_COLOR, PRIMARY_BG, BG_DARK, PRIMARY_RED, PRIMARY_RED_DARK, TEXT_SECONDARY,
    CONTENT_BG, CARD_BG, MUTED_TEXT,  # FIX: these 3 were used but not imported
)
from api_service import api
from logger import ui_logger

# ==================== COLORS & STYLE (centralized in theme.py) ====================

LOGIN_DB_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS idx_employee_name ON employee(name)",
    "CREATE INDEX IF NOT EXISTS idx_employee_email ON employee(email)",
)


def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_db_path():
    return os.path.join(get_app_base_dir(), 'employee.db')


def format_exception_details(exc, tb=None):
    tb_obj = tb if tb is not None else exc.__traceback__
    extracted = traceback.extract_tb(tb_obj) if tb_obj else []
    if extracted:
        last_frame = extracted[-1]
        location = f"{os.path.basename(last_frame.filename)}:{last_frame.lineno} in {last_frame.name}"
        code_line = (last_frame.line or "").strip()
    else:
        location = "Unknown location"
        code_line = ""

    details = "".join(traceback.format_exception(type(exc), exc, tb_obj))
    summary_lines = [
        f"Error: {type(exc).__name__}: {exc}",
        f"Location: {location}",
    ]
    if code_line:
        summary_lines.append(f"Code: {code_line}")
    return "\n".join(summary_lines), details


def show_detailed_error(title, context, exc, tb=None, parent=None):
    if isinstance(exc, (KeyboardInterrupt, SystemExit)):
        return
    summary, details = format_exception_details(exc, tb)
    ui_logger.error("%s\n%s", context, details)
    message = f"{context}\n\n{summary}\n\nFull details were written to the logs folder."
    try:
        if parent is not None and parent.winfo_exists():
            messagebox.showerror(title, message, parent=parent)
        else:
            messagebox.showerror(title, message)
    except Exception:
        messagebox.showerror(title, message)

def init_login_db():
    """Initializes the database with minimal tables needed only for the login screen."""
    try:
        con = sqlite3.connect(get_db_path())
        cur = con.cursor()
        
        # Optimize performance pragmas early
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA cache_size=-64000")
        
        # Security Tables
        cur.execute("""CREATE TABLE IF NOT EXISTS login_attempts (
                        username TEXT PRIMARY KEY,
                        attempts INTEGER DEFAULT 0,
                        lock_until TEXT
                    )""")
        cur.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT, user TEXT, action TEXT, details TEXT
                    )""")
        
        # Core Tables for Login
        cur.execute("CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, email TEXT, dob TEXT)")
        cur.execute("CREATE TABLE IF NOT EXISTS employee (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, password TEXT, role TEXT, department TEXT, email TEXT)")
        for index_sql in LOGIN_DB_INDEXES:
            cur.execute(index_sql)
        
        # Seed Admin if not exists
        cur.execute("SELECT COUNT(*) FROM users WHERE username='admin'")
        if (cur.fetchone() or [0])[0] == 0:
            hp = hashlib.sha256('1234'.encode()).hexdigest()
            cur.execute("INSERT INTO users (username, password, email, dob) VALUES (?,?,?,?)",
                        ('admin', hp, 'admin@company.com', '1990-01-01'))
        
        con.commit()
        con.close()
    except Exception as e:
        print(f"DB Initialization error: {e}")


def run_login():
    # Initialize Core DB requirements for login
    init_login_db()

    # ==================== WINDOW SETUP ====================
    login_window = Tk()
    login_window.geometry('1280x800')
    login_window.title('PMS - Login')
    login_window.resizable(True, True)
    login_window.config(bg=BG_COLOR)
    apply_theme(login_window)
    def _login_callback_exception(exc_type, exc_val, exc_tb):
        """Custom exception handler for login window callbacks.
        Silently drops 'invalid command name' TclErrors — these happen when
        after() lambdas (e.g., render_sidebar_background, draw_grid) fire
        just after login_window.destroy() is called on successful login.
        All other real errors are still shown to the user.
        """
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            return
        msg = str(exc_val)
        if 'invalid command name' in msg or 'application has been destroyed' in msg:
            # Stale after() callback — safe to ignore
            return
        show_detailed_error(
            "UI Error",
            "An unexpected UI error occurred while handling an action.",
            exc_val,
            exc_tb,
            parent=login_window if login_window.winfo_exists() else None,
        )
    login_window.report_callback_exception = _login_callback_exception


    # Center
    window_width = 1280
    window_height = 800
    screen_width = login_window.winfo_screenwidth()
    screen_height = login_window.winfo_screenheight()
    x_cordinate = int((screen_width/2) - (window_width/2))
    y_cordinate = int((screen_height/2) - (window_height/2))
    login_window.geometry("{}x{}+{}+{}".format(window_width, window_height, x_cordinate, y_cordinate))
    try:
        login_window.state("zoomed")
    except:
        login_window.geometry("1280x800")
    
    # Icon
    try:
        from tkinter import PhotoImage
        base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(__file__)
        _icon_path = os.path.join(base, 'locked.png')
        if os.path.exists(_icon_path):
            login_window.iconphoto(True, PhotoImage(file=_icon_path))
    except Exception:
        pass

    state = {
        "mode": "employee",
        "action": None,
        "login_in_progress": False,
        "last_sidebar_size": (0, 0),
        "last_grid_size": (0, 0),
    }
    image_refs = {}
    _resize_job = None
    _grid_job = None
    sidebar_image_source = None
    sidebar_image_path = None

    # ==================== LAYOUT ====================

    # 1. Left image panel — takes 50% of window width dynamically
    sidebar = Frame(login_window, bg=CONTENT_BG)
    sidebar.place(relx=0, rely=0, relwidth=0.5, relheight=1.0)

    canvas = Canvas(sidebar, bg=CONTENT_BG, highlightthickness=0)
    canvas.place(relx=0, rely=0, relwidth=1.0, relheight=1.0)

    def get_sidebar_image_path():
        base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) else get_app_base_dir()
        # Prioritize login_hero.png as the primary hero image
        candidate_names = (
            "login_hero.png",
            "pms_login_hero.png",
            "image1.jpg",
            "login_hero.jpg",
            "login_sidebar.png",
        )
        for file_name in candidate_names:
            candidate_path = os.path.join(base_dir, file_name)
            if os.path.exists(candidate_path):
                return candidate_path
        return None

    def get_sidebar_source_image():
        nonlocal sidebar_image_source, sidebar_image_path
        image_path = get_sidebar_image_path()
        if not image_path:
            sidebar_image_source = None
            sidebar_image_path = None
            return None, None

        if sidebar_image_source is None or sidebar_image_path != image_path:
            sidebar_image_source = Image.open(image_path).convert("RGBA")
            sidebar_image_path = image_path

        return sidebar_image_source, image_path

    def render_sidebar_background(force=False):
        try:
            # Dynamic sizing based on sidebar frame
            sw = max(sidebar.winfo_width(), 400)
            sh = max(sidebar.winfo_height(), 600)
            
            # Skip if size hasn't changed much
            last_sw, last_sh = state.get("last_sidebar_size", (0, 0))
            if not force and abs(sw - last_sw) < 10 and abs(sh - last_sh) < 10:
                return
            
            state["last_sidebar_size"] = (sw, sh)
            canvas.delete("sidebar_bg")

            src_img, image_path = get_sidebar_source_image()
            if not image_path or src_img is None:
                canvas.create_rectangle(0, 0, sw, sh, fill=SIDEBAR_BG, outline="", tags="sidebar_bg")
                return

            img = src_img.copy()
            
            # Aspect-fill logic
            img_w, img_h = img.size
            img_ratio = img_w / img_h
            target_ratio = sw / sh
            
            if img_ratio > target_ratio:
                # Image is wider than sidebar
                new_h = sh
                new_w = int(new_h * img_ratio)
            else:
                # Image is taller than sidebar
                new_w = sw
                new_h = int(new_w / img_ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Center crop
            crop_left = (new_w - sw) // 2
            crop_top = (new_h - sh) // 2
            img = img.crop((crop_left, crop_top, crop_left + sw, crop_top + sh))

            # Subtle dark gradient overlay to blend with the navy right side
            overlay = Image.new("RGBA", img.size, (15, 23, 42, 100)) # Muted navy overlay
            img = Image.alpha_composite(img, overlay).convert("RGB")

            photo = ImageTk.PhotoImage(img)
            image_refs["sidebar_background"] = photo
            canvas.create_image(0, 0, image=photo, anchor=NW, tags="sidebar_bg")
        except Exception as ex:
            print(f"Sidebar image error: {ex}")
            canvas.delete("sidebar_bg")
            canvas.create_rectangle(0, 0, sidebar.winfo_width(), sidebar.winfo_height(),
                                    fill=CONTENT_BG, outline="", tags="sidebar_bg")

    def _on_sidebar_resize(e):
        nonlocal _resize_job
        if _resize_job:
            login_window.after_cancel(_resize_job)
        _resize_job = login_window.after(180, render_sidebar_background)

    sidebar.bind("<Configure>", _on_sidebar_resize)

    # 2. Right Main Area (Login Form)
    main_area = Canvas(login_window, bg=BG_DARK, highlightthickness=0)
    main_area.place(relx=0.5, rely=0, relwidth=0.5, relheight=1.0)

    def update_shell_layout(_event=None):
        total_w = max(login_window.winfo_width(), window_width)

        if total_w >= 1600:
            right_ratio = 0.48
        elif total_w >= 1350:
            right_ratio = 0.52
        elif total_w >= 1150:
            right_ratio = 0.57
        else:
            right_ratio = 0.62

        left_ratio = 1.0 - right_ratio
        sidebar.place_configure(relx=0, rely=0, relwidth=left_ratio, relheight=1.0)
        canvas.place_configure(relx=0, rely=0, relwidth=1.0, relheight=1.0)
        main_area.place_configure(relx=left_ratio, rely=0, relwidth=right_ratio, relheight=1.0)

    def draw_grid():
        w = main_area.winfo_width()
        h = main_area.winfo_height()
        last_w, last_h = state.get("last_grid_size", (0, 0))
        if abs(w - last_w) < 20 and abs(h - last_h) < 20:
            return

        state["last_grid_size"] = (w, h)
        main_area.delete("grid")
        gap = 44
        for i in range(0, w, gap):
            main_area.create_line(i, 0, i, h, fill="#2a3155", tags="grid")
        for j in range(0, h, gap):
            main_area.create_line(0, j, w, j, fill="#2a3155", tags="grid")

    def queue_grid_redraw(_event=None):
        nonlocal _grid_job
        if _grid_job:
            login_window.after_cancel(_grid_job)
        _grid_job = login_window.after(120, draw_grid)

    main_area.bind("<Configure>", queue_grid_redraw)

    login_card = Frame(main_area, bg=BG_DARK)
    login_card.place(x=36, rely=0.1, anchor=NW)

    # ── PMS 2.0 Logo / Brand Header ──
    brand_frame = Frame(login_card, bg=BG_DARK)
    brand_frame.pack(anchor=W, pady=(0, 16))

    # Red "P" badge (Solid square style)
    badge = Label(brand_frame, text="P", font=('Segoe UI', 14, 'bold'),
                  bg=PRIMARY_RED, fg=WHITE, width=2, height=1)
    badge.pack(side=LEFT, padx=(0, 14))

    brand_text = Frame(brand_frame, bg=BG_DARK)
    brand_text.pack(side=LEFT)
    Label(brand_text, text="PMS 2.0", font=('Segoe UI', 15, 'bold'),
          bg=BG_DARK, fg=WHITE).pack(anchor=W)
    Label(brand_text, text="Project Monitor", font=('Segoe UI', 9),
          bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor=W)

    # Header
    lbl_welcome = Label(login_card, text="Employee Portal", font=('Segoe UI', 40, 'bold'), bg=BG_DARK, fg=WHITE, justify=LEFT)
    lbl_welcome.pack(pady=(0, 10), anchor=W)

    lbl_sub = Label(login_card, text="Access your tasks and queries.", font=('Segoe UI', 12), bg=BG_DARK, fg=TEXT_SECONDARY, justify=LEFT)
    lbl_sub.pack(pady=(0, 26), anchor=W)

    # Input Fields Helper
    def create_input(parent, label_text, is_password=False):
        Label(parent, text=label_text.upper(), font=('Segoe UI', 9, 'bold'), bg=BG_DARK, fg=TEXT_SECONDARY).pack(anchor=W, pady=(0, 8))
        
        # Entry container for border
        entry_frame = Frame(parent, bg="#ffffff", height=56, highlightbackground=BORDER_COLOR, highlightthickness=1, bd=0)
        entry_frame.pack(fill=X, pady=(0, 16))
        entry_frame.pack_propagate(False)
        
        ph_map = {"First Name": "Enter your first name", "Password": "Enter your password"}
        placeholder = ph_map.get(label_text, f"Enter your {label_text.lower()}")
        
        entry = Entry(entry_frame, font=('Segoe UI', 11), bg="#ffffff", fg="#0f172a", insertbackground="#0f172a", relief=FLAT, width=45)
        entry.insert(0, placeholder)
        entry.config(fg="#94a3b8") # Muted placeholder color
        entry._placeholder = placeholder
        entry._is_password = is_password

        def _ph_in(e, ent=entry):
            if ent.get() == ent._placeholder:
                ent.delete(0, END)
                ent.config(fg="#0f172a")
                if ent._is_password:
                    ent.config(show="•")

        def _ph_out(e, ent=entry):
            if ent.get() == "":
                ent.config(fg="#94a3b8", show="")
                ent.insert(0, ent._placeholder)
            else:
                ent.config(fg="#0f172a")

        entry.bind("<FocusIn>", _ph_in)
        entry.bind("<FocusOut>", _ph_out)

        if is_password:
            def toggle_pass():
                if entry.get() == entry._placeholder:
                    return
                if entry.cget('show') == '•':
                    entry.config(show='')
                    btn_toggle.config(text='👁️')
                else:
                    entry.config(show='•')
                    btn_toggle.config(text='👁️‍🗨️')
            
            # Lock icon and Eye icon container
            icons_frame = Frame(entry_frame, bg="#ffffff")
            icons_frame.pack(side=RIGHT, padx=(8, 14), pady=10)
            
            btn_toggle = Button(icons_frame, text="👁️", command=toggle_pass, bg="#ffffff", fg="#94a3b8", relief=FLAT, bd=0, cursor="hand2", font=("Segoe UI", 12))
            btn_toggle.pack(side=RIGHT)
            
            lbl_lock = Label(icons_frame, text="🔒", bg="#ffffff", fg="#94a3b8", font=("Segoe UI", 12))
            lbl_lock.pack(side=RIGHT, padx=(0, 5))
            
        entry.pack(side=LEFT, padx=(18, 12), pady=14, fill=X, expand=True)
        
        # Focus border effects
        def on_focus_in(e):
            entry_frame.config(highlightbackground=PRIMARY_RED, highlightthickness=1)
        def on_focus_out(e):
            entry_frame.config(highlightbackground="#3a4a5c")
            
        entry.bind("<FocusIn>", on_focus_in, add="+")
        entry.bind("<FocusOut>", on_focus_out, add="+")
        
        return entry

    # Role Selection Logic
    def switch_to_employee():
        state["mode"] = "employee"
        btn_employee.config(bg=PRIMARY_RED, fg=WHITE)
        btn_tl.config(bg="#2d3555", fg=TEXT_SECONDARY)
        btn_manager.config(bg="#2d3555", fg=TEXT_SECONDARY)
        lbl_welcome.config(text="Employee Portal")
        lbl_sub.config(text="Access your tasks and queries.")
        try: signup_btn.config(text="New Employee? Create Account")
        except: pass

    def switch_to_tl():
        state["mode"] = "team leader"
        btn_tl.config(bg=PRIMARY_RED, fg=WHITE)
        btn_employee.config(bg="#2d3555", fg=TEXT_SECONDARY)
        btn_manager.config(bg="#2d3555", fg=TEXT_SECONDARY)
        lbl_welcome.config(text="Team Leader")
        lbl_sub.config(text="Manage your team and assignments.")
        try: signup_btn.config(text="New Team Leader? Create Account")
        except: pass

    def switch_to_manager():
        state["mode"] = "manager"
        btn_manager.config(bg=PRIMARY_RED, fg=WHITE)
        btn_employee.config(bg="#2d3555", fg=TEXT_SECONDARY)
        btn_tl.config(bg="#2d3555", fg=TEXT_SECONDARY)
        lbl_welcome.config(text="Manager Portal")
        lbl_sub.config(text="Project oversight and administration.")
        try: signup_btn.config(text="New Project Manager? Create Account")
        except: pass

    # Toggle Buttons Frame
    toggle_frame = Frame(login_card, bg="#2d3555", padx=2, pady=2)
    toggle_frame.pack(fill=X, pady=(0, 28))

    # Grid for 3 buttons
    toggle_frame.grid_columnconfigure(0, weight=1)
    toggle_frame.grid_columnconfigure(1, weight=1)
    toggle_frame.grid_columnconfigure(2, weight=1)

    btn_employee = Button(toggle_frame, text="Employee", font=('Segoe UI', 10, 'bold'), 
                         bg=PRIMARY_RED, fg=WHITE, relief=FLAT, command=switch_to_employee,
                         bd=0, pady=8, cursor="hand2")
    btn_employee.grid(row=0, column=0, sticky="ew")

    btn_tl = Button(toggle_frame, text="Team Leader", font=('Segoe UI', 10), 
                         bg="#2d3555", fg=TEXT_SECONDARY, relief=FLAT, command=switch_to_tl,
                         bd=0, pady=8, cursor="hand2")
    btn_tl.grid(row=0, column=1, sticky="ew")

    btn_manager = Button(toggle_frame, text="Manager", font=('Segoe UI', 10), 
                        bg="#2d3555", fg=TEXT_SECONDARY, relief=FLAT, command=switch_to_manager,
                        bd=0, pady=8, cursor="hand2")
    btn_manager.grid(row=0, column=2, sticky="ew")

    username_entry = create_input(login_card, "First Name")
    password_entry = create_input(login_card, "Password", is_password=True)

    # Remember Me + Forgot Password row
    rem_row = Frame(login_card, bg=BG_DARK)
    rem_row.pack(fill=X, pady=(2, 20))

    remember_var = BooleanVar()
    chk_remember = Checkbutton(rem_row, text="REMEMBER ME", variable=remember_var, 
                              bg=BG_DARK, fg=WHITE, selectcolor=BG_DARK, 
                              activebackground=BG_DARK, activeforeground=WHITE,
                              font=('Segoe UI', 9, 'bold'), bd=0, highlightthickness=0)
    chk_remember.pack(side=LEFT)

    forgot_btn = Button(rem_row, text="Forgot Password?", font=("Segoe UI", 10), bg=BG_DARK, fg=LINK_BLUE, 
           bd=0, activebackground=BG_DARK, activeforeground=LINK_BLUE, cursor='hand2', 
           command=lambda: forgot_password())
    forgot_btn.pack(side=RIGHT, pady=(0, 1))

    def update_login_layout(_event=None):
        main_w = max(main_area.winfo_width(), 640)
        main_h = max(main_area.winfo_height(), 760)

        card_width = min(max(main_w - 150, 500), 680)
        title_font = 40 if card_width >= 640 else 36 if card_width >= 560 else 32
        subtitle_wrap = max(card_width - 24, 360)
        button_pad = 10 if card_width >= 560 else 9
        top_offset = 0.12 if main_h >= 860 else 0.1

        side_gutter = 36 if main_w >= 760 else 24
        login_card.place_configure(x=side_gutter, rely=top_offset, anchor=NW, width=card_width)
        lbl_welcome.config(font=('Segoe UI', title_font, 'bold'), wraplength=card_width)
        lbl_sub.config(wraplength=subtitle_wrap)

        for button in (btn_employee, btn_tl, btn_manager):
            button.config(pady=button_pad)

    # Auto-fill if remembered
    try:
        if os.path.exists("remember_me.json"):
            with open("remember_me.json", "r") as f:
                data = json.load(f)
                u = data.get("username", "")
                if u:
                    username_entry.delete(0, END)
                    username_entry.insert(0, u)
                    username_entry.config(fg="#1a202c") # Set dark color for auto-fill
                remember_var.set(True)
    except: pass

    def sync_local_account(name, email, password, role, department=""):
        """Store backend users locally so first-name login works after the first sign-in."""
        try:
            if not name or not password:
                return

            hashed_pw = hashlib.sha256(str(password).encode()).hexdigest()
            con = sqlite3.connect(get_db_path())
            cur = con.cursor()
            cur.execute("SELECT id FROM employee WHERE lower(name)=lower(?) OR lower(email)=lower(?)", (name, email or ""))
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    "UPDATE employee SET name=?, email=?, password=?, role=?, department=? WHERE id=?",
                    (name, email, hashed_pw, role, department, existing[0])
                )
            else:
                cur.execute(
                    "INSERT INTO employee (name, password, role, department, email) VALUES (?, ?, ?, ?, ?)",
                    (name, hashed_pw, role, department, email)
                )

            con.commit()
            con.close()
        except Exception as e:
            print(f"DEBUG: Local sync failed: {e}")

    def login():
        if state.get("login_in_progress"):
            return
        state["login_in_progress"] = True
        try:
            login_btn.config(text="Verifying…", state=DISABLED, bg=PRIMARY_RED_DARK)
            login_window.update_idletasks()
        except:
            pass

        username = username_entry.get().strip()
        password = password_entry.get()

        # Ignore placeholders
        if username == getattr(username_entry, "_placeholder", "Enter your first name"):
            username = ""
        if password == "Enter your password": password = ""

        if username == '' or password == '':
            messagebox.showerror('Error', 'Fields cannot be empty')
            state["login_in_progress"] = False
            try:
                login_btn.config(text="SIGN IN", state=NORMAL, bg=PRIMARY_RED)
            except:
                pass
            return

        # 1. Try Backend API Login (Node.js)
        # If the 'username' looks like an email, try API login
        if "@" in username:
            success, result = api.login(username, password)
            if success:
                sync_local_account(
                    result.get("name"),
                    result.get("email", username),
                    password,
                    result.get("role", "Employee"),
                    result.get("department", "")
                )
                state["action"] = "RUN_APP"
                login_window.destroy()
                return
            else:
                print(f"DEBUG: API Login failed: {result}")

        # 2. Fallback to Local SQLite Login (Existing Logic)
        if username.lower() == 'admin' and password in ('1234', 'admin'):
            try:
                with open('session.json', 'w') as f:
                    json.dump({
                        'user': 'admin', 
                        'role': 'admin', 
                        'logged_in': True,
                        'login_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }, f)
            except Exception as e:
                print(f"Error saving session: {e}")
            state["action"] = "RUN_APP"
            login_window.destroy()
            return

        try:
            con = sqlite3.connect(get_db_path())
            cursor = con.cursor()
            
            hashed_pw = hashlib.sha256(str(password).encode()).hexdigest()
            
            # Check users table
            cursor.execute("SELECT * FROM users WHERE lower(username) = lower(?) OR lower(email) = lower(?)", (username, username))
            row = cursor.fetchone()
            
            user_role = None
            user_name = None
            
            if row:
                if row[1] in (hashed_pw, hashlib.sha256('1234'.encode()).hexdigest()):
                    user_role = 'admin'
                    user_name = row[0]
            # 1. Try exact match first (Best for security)
            cursor.execute(
                "SELECT password, name, role FROM employee WHERE lower(name) = lower(?) OR lower(email) = lower(?)",
                (username, username)
            )
            row = cursor.fetchone()
            
            if not row:
                # 2. Try prefix match if no exact match (User only entered first name)
                cursor.execute(
                    "SELECT password, name, role FROM employee WHERE lower(name) LIKE lower(?) ORDER BY LENGTH(name) ASC LIMIT 1",
                    (username + " %",)
                )
                row = cursor.fetchone()
            
            if not row:
                # 3. Final fallback: Any match (Least restrictive)
                cursor.execute(
                    "SELECT password, name, role FROM employee WHERE lower(name) LIKE lower(?) ORDER BY LENGTH(name) ASC LIMIT 1",
                    (username + "%",)
                )
                row = cursor.fetchone()

            if row and row[0] == hashed_pw:
                user_role = row[2] if row[2] else 'Team Member'
                user_name = row[1]

            if user_role:
                try:
                    with open('session.json', 'w') as f:
                        json.dump({
                            'user': user_name, 
                            'role': user_role, 
                            'logged_in': True,
                            'login_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }, f)
                    if remember_var.get():
                        with open("remember_me.json", "w") as f:
                            json.dump({"username": username}, f)
                except Exception as e:
                    print(f"Error saving session: {e}")
                
                state["action"] = "RUN_APP"
                login_window.destroy()
            else:
                messagebox.showerror('Login Failed', 'Invalid credentials.')
                
            con.close()
        except Exception as e:
            messagebox.showerror('Error', f'System Error: {e}')
        finally:
            state["login_in_progress"] = False
            try:
                if login_window.winfo_exists():
                    login_btn.config(text="SIGN IN", state=NORMAL, bg=PRIMARY_RED)
            except:
                pass

    def forgot_password():
        t = Toplevel(login_window)
        t.title("Reset Password")
        t.geometry("450x550")
        t.config(bg=BG_COLOR)
        
        # Center
        x = int((screen_width/2) - (450/2))
        y = int((screen_height/2) - (550/2))
        t.geometry(f"450x550+{x}+{y}")
        
        Label(t, text="Reset Password", font=('Segoe UI', 18, 'bold'), bg=BG_COLOR, fg="#e2e8f0").pack(pady=20)
        
        f = Frame(t, bg=BG_COLOR, padx=30)
        f.pack(fill=BOTH, expand=True)
        
        # Step 1: ID
        Label(f, text="First Name", bg=BG_COLOR, fg="#e2e8f0", anchor=W).pack(fill=X)
        e_name = Entry(f, font=('Segoe UI', 11), bg="#ffffff", fg="#1a202c", insertbackground="#1a202c", relief=FLAT)
        e_name.pack(fill=X, pady=(5, 15))

        Label(f, text="Date of Birth (YYYY-MM-DD)", bg=BG_COLOR, fg="#e2e8f0", anchor=W).pack(fill=X)
        e_dob = Entry(f, font=('Segoe UI', 11), bg="#ffffff", fg="#1a202c", insertbackground="#1a202c", relief=FLAT)
        e_dob.pack(fill=X, pady=(5, 15))
        
        # Container for Step 2
        step2_frame = Frame(f, bg=BG_COLOR)
        step2_frame.pack(fill=BOTH, expand=True)
        
        # Context to store user info between steps
        ctx = {} 

        def show_reset_ui():
            # Clear everything in the main frame 'f'
            for w in f.winfo_children(): w.destroy()
            
            Label(f, text="New Password", bg=BG_COLOR, fg="#e2e8f0", anchor=W).pack(fill=X)
            e_new = Entry(f, show="•", font=('Segoe UI', 11), bg="#ffffff", fg="#1a202c", insertbackground="#1a202c", relief=FLAT)
            e_new.pack(fill=X, pady=(5, 15))
            
            Label(f, text="Confirm Password", bg=BG_COLOR, fg="#e2e8f0", anchor=W).pack(fill=X)
            e_conf = Entry(f, show="•", font=('Segoe UI', 11), bg="#ffffff", fg="#1a202c", insertbackground="#1a202c", relief=FLAT)
            e_conf.pack(fill=X, pady=(5, 15))
            
            def do_update():
                p1 = e_new.get()
                p2 = e_conf.get()
                
                if not p1 or not p2:
                    messagebox.showerror("Error", "Enter new password", parent=t)
                    return
                if p1 != p2:
                    messagebox.showerror("Error", "Passwords do not match", parent=t)
                    return
                    
                if not validate_password_strength(p1):
                    messagebox.showerror("Error", "Password too weak.\nRequires: 8+ chars, Upper, Lower, Digit, Special Char", parent=t)
                    return

                try:
                    hashed = hashlib.sha256(p1.encode()).hexdigest()

                    con = sqlite3.connect(get_db_path())
                    cur = con.cursor()

                    # Update Password
                    if ctx['table'] == 'employee':
                        cur.execute(f"UPDATE employee SET password=? WHERE {ctx['key_col']}=?", (hashed, ctx['key_val']))
                    else:
                        cur.execute(f"UPDATE users SET password=? WHERE username=?", (hashed, ctx['key_val']))
                
                    con.commit()
                    con.close()
                    messagebox.showinfo("Success", "Password Updated Successfully", parent=t)
                    t.destroy()
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=t)
            
            Button(f, text="Update Password", command=do_update, bg=ACCENT_COLOR, fg=WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(fill=X, pady=20)

        def verify_identity():
            first_name = e_name.get().strip()
            dob = e_dob.get().strip()
            
            if not first_name or not dob:
                messagebox.showerror("Error", "Enter First Name and Date of Birth", parent=t)
                return
            
            try:
                con = sqlite3.connect(get_db_path())
                cur = con.cursor()
                
                cur.execute("SELECT * FROM employee WHERE (name LIKE ? OR name = ?) AND dob=?", (first_name + " %", first_name, dob))
                emp_row = cur.fetchone()
                
                cur.execute("SELECT * FROM users WHERE username=? AND dob=?", (first_name, dob))
                admin_row = cur.fetchone()

                if emp_row:
                    emp_id = emp_row[0]
                    ctx['table'] = "employee"
                    ctx['key_col'] = "id"
                    ctx['key_val'] = emp_id
                    con.close()
                    show_reset_ui()
                    return
                elif admin_row:
                    ctx['table'] = "users"
                    ctx['key_col'] = "username"
                    ctx['key_val'] = first_name
                    con.close()
                    show_reset_ui()
                    return
                else:
                     messagebox.showerror("Error", "Verification Failed: Incorrect Name or DOB", parent=t)
                     con.close()
                     return
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=t)

        Button(f, text="Verify & Next", command=verify_identity, bg=ACCENT_COLOR, fg=WHITE, font=('Segoe UI', 11, 'bold'), relief=FLAT).pack(fill=X, pady=20)

    def validate_password_strength(password):
        if len(password) < 8: return False
        if not re.search(r"[a-z]", password): return False
        if not re.search(r"[A-Z]", password): return False
        if not re.search(r"\d", password): return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): return False
        return True

    def open_signup():
        mode = state["mode"]
        role_map = {
            "employee": "TEAM MEMBER",
            "team leader": "TEAM LEADER",
            "manager": "PROJECT MANAGER"
        }
        target_role = role_map.get(mode, "TEAM MEMBER")
        
        s = Toplevel(login_window)
        s.title(f"PMS 2.0 - {target_role} Registration")
        
        # Center the window on screen
        win_w = 900
        win_h = 800
        scr_w = s.winfo_screenwidth()
        scr_h = s.winfo_screenheight()
        x = int((scr_w/2) - (win_w/2))
        y = int((scr_h/2) - (win_h/2))
        s.geometry(f"{win_w}x{win_h}+{x}+{y}")
        s.config(bg=BG_DARK) 
        s.resizable(True, True)
        
        try:
            s.state('zoomed')
        except:
            pass
            
        main_canvas = Canvas(s, bg=BG_DARK, highlightthickness=0)
        v_scroll = ttk.Scrollbar(s, orient=VERTICAL, command=main_canvas.yview)
        
        scroll_frame = Frame(main_canvas, bg=BG_DARK)
        scroll_frame.bind("<Configure>", lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all")))
        
        # Center the scroll_frame in the canvas with width 800
        canvas_window = main_canvas.create_window((450, 0), window=scroll_frame, anchor="n", width=800)
        
        def on_canvas_resize(e):
            main_canvas.coords(canvas_window, e.width / 2, 0)
            
        main_canvas.bind("<Configure>", on_canvas_resize)
        main_canvas.configure(yscrollcommand=v_scroll.set)
        
        main_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        v_scroll.pack(side=RIGHT, fill=Y)

        card = Frame(scroll_frame, bg=CARD_BG, padx=30, pady=20, highlightbackground=BORDER_COLOR, highlightthickness=1)
        card.pack(pady=20, padx=20, expand=True)
        
        top_header = Frame(card, bg=CARD_BG)
        top_header.pack(fill=X, pady=(0, 15))
        
        logo_frame = Frame(top_header, bg=CARD_BG)
        logo_frame.pack(side=LEFT)
        Label(logo_frame, text=" P ", font=('Segoe UI', 12, 'bold'), bg="#ef4444", fg="white", padx=6, pady=3).pack(side=LEFT, padx=(0, 10))
        
        brand_info = Frame(logo_frame, bg=CARD_BG)
        brand_info.pack(side=LEFT)
        Label(brand_info, text="PMS 2.0", font=('Segoe UI', 12, 'bold'), bg=CARD_BG, fg="white").pack(anchor=W)
        Label(brand_info, text="Project Monitor", font=('Segoe UI', 9), bg=CARD_BG, fg="#9ca3af").pack(anchor=W)
        
        badge_text = f"• {target_role} REGISTRATION"
        badge = Label(top_header, text=badge_text, font=('Segoe UI', 9, 'bold'), bg="#311b1e", fg="#ef4444", 
                     padx=12, pady=6, highlightbackground="#ef4444", highlightthickness=1)
        badge.pack(side=RIGHT)
        
        Label(card, text="Create Account", font=('Segoe UI', 24, 'bold'), bg=CARD_BG, fg="white").pack(anchor=W, pady=(0, 5))
        Label(card, text="Fill in your details to get started with PMS 2.0", font=('Segoe UI', 11), bg=CARD_BG, fg="#9ca3af").pack(anchor=W, pady=(0, 20))
        
        form_frame = Frame(card, bg=CARD_BG)
        form_frame.pack(fill=X)
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_columnconfigure(1, weight=1)
        
        def mk_input_v2(parent, label_text, r, c, icon="👤", show=None, placeholder=""):
            Label(parent, text=label_text.upper(), font=('Segoe UI', 9, 'bold'), bg=CARD_BG, fg="#9ca3af", anchor=W).grid(row=r, column=c, sticky="w", padx=10, pady=(10, 5))
            container = Frame(parent, bg="white", height=45, highlightbackground="#d1d5db", highlightthickness=1)
            container.grid(row=r+1, column=c, sticky="ew", padx=10, pady=(0, 5))
            container.grid_propagate(False)
            Label(container, text=icon, font=('Segoe UI', 12), bg="white", fg="#9ca3af").pack(side=LEFT, padx=(12, 8))
            entry = Entry(container, font=('Segoe UI', 11), bg="white", fg="#1f2937", relief=FLAT, insertbackground="#1f2937", show=show)
            entry.pack(side=LEFT, fill=BOTH, expand=True, pady=8)
            if placeholder:
                entry.insert(0, placeholder)
                entry.config(fg="#9ca3af")
                def on_focus_in(e):
                    if entry.get() == placeholder:
                        entry.delete(0, END)
                        entry.config(fg="#1f2937")
                def on_focus_out(e):
                    if not entry.get():
                        entry.insert(0, placeholder)
                        entry.config(fg="#9ca3af")
                entry.bind("<FocusIn>", on_focus_in)
                entry.bind("<FocusOut>", on_focus_out)
            return entry
            
        e_fname = mk_input_v2(form_frame, "First Name", 0, 0, icon="👤", placeholder="John")
        e_lname = mk_input_v2(form_frame, "Last Name", 0, 1, icon="👤", placeholder="Doe")
        e_email = mk_input_v2(form_frame, "Email", 2, 0, icon="✉", placeholder="john.doe@company.com")
        e_contact = mk_input_v2(form_frame, "Contact Number", 2, 1, icon="📞", placeholder="+91 98765 43210")
        e_dept = mk_input_v2(form_frame, "Department", 4, 0, icon="💼", placeholder="Engineering")
        e_dob = mk_input_v2(form_frame, "Date of Birth (YYYY-MM-DD)", 4, 1, icon="📅", placeholder="1995-08-22")
        e_pass = mk_input_v2(form_frame, "Password", 6, 0, icon="🔒", show="•", placeholder="••••••••")
        e_conf = mk_input_v2(form_frame, "Confirm Password", 6, 1, icon="🛡", show="•", placeholder="••••••••")
        
        entries = [e_fname, e_lname, e_email, e_contact, e_dept, e_dob, e_pass, e_conf]
        
        def do_signup():
            fname = e_fname.get().strip()
            lname = e_lname.get().strip()
            email = e_email.get().strip()
            contact = e_contact.get().strip()
            dept = e_dept.get().strip()
            dob = e_dob.get().strip()
            p1 = e_pass.get()
            p2 = e_conf.get()
            
            if not fname or not lname or not email or not contact or not dept or not dob or not p1 or not p2:
                messagebox.showerror("Error", "All fields are required", parent=s)
                return
            if p1 != p2:
                messagebox.showerror("Error", "Passwords do not match", parent=s)
                return

            name = f"{fname} {lname}"
            success, result = api.register(name, email, p1, target_role, dept)
            if success:
                sync_local_account(name, email, p1, target_role, dept)
                messagebox.showinfo("Success", f"Welcome {fname}!\nYour account has been created on the backend.", parent=s)
                s.destroy()
                return
            
            if not validate_password_strength(p1):
                messagebox.showerror("Error", "Password too weak.\nRequires: 8+ chars, Upper, Lower, Digit, Special Char", parent=s)
                return

            try:
                sync_local_account(name, email, p1, target_role, dept)
                messagebox.showinfo("Success", "Account Created Successfully!", parent=s)
                s.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Database Error", f"Failed to create account: {e}", parent=s)
            except Exception as e:
                messagebox.showerror("System Error", str(e), parent=s)

        reg_btn = Button(card, text="CREATE ACCOUNT", command=do_signup, 
                        bg=PRIMARY_RED, fg="white", font=('Segoe UI', 12, 'bold'), 
                        relief=FLAT, cursor="hand2", pady=15)
        reg_btn.pack(fill=X)
        
        footer_frame = Frame(card, bg=CARD_BG)
        footer_frame.pack(pady=(15, 0))
        Label(footer_frame, text="Already have an account?", font=('Segoe UI', 10), bg=CARD_BG, fg="#9ca3af").pack(side=LEFT)
        Button(footer_frame, text="Sign in", font=('Segoe UI', 10, 'italic'), bg=CARD_BG, fg=LINK_BLUE, 
               bd=0, activebackground=CARD_BG, activeforeground=LINK_BLUE, cursor='hand2', 
               command=s.destroy).pack(side=LEFT, padx=5)

    def on_enter(e):
        login_btn.config(bg=PRIMARY_RED_DARK)
    def on_leave(e):
        login_btn.config(bg=PRIMARY_RED)

    login_btn = Button(login_card, text='SIGN IN', font=('Segoe UI', 13, 'bold'), bg=PRIMARY_RED, fg=WHITE, activebackground=PRIMARY_RED_DARK, activeforeground=WHITE, 
                       relief=FLAT, cursor='hand2', command=login, bd=0)
    login_btn.pack(fill=X, pady=(14, 0), ipady=13)
    login_btn.bind("<Enter>", on_enter)
    login_btn.bind("<Leave>", on_leave)

    username_entry.bind("<Return>", lambda e: login())
    password_entry.bind("<Return>", lambda e: login())
    username_entry.bind("<Down>", lambda e: password_entry.focus_set())
    password_entry.bind("<Up>", lambda e: username_entry.focus_set())

    def _cycle_role(e):
        order = ['employee', 'team leader', 'manager']
        cur = state.get('mode', 'employee')
        try:
            idx = order.index(cur)
        except:
            idx = 0
        if e.keysym == 'Right':
            idx = (idx + 1) % len(order)
        else:
            idx = (idx - 1) % len(order)
        nxt = order[idx]
        if nxt == 'employee': switch_to_employee()
        elif nxt == 'team leader': switch_to_tl()
        else: switch_to_manager()

    login_window.bind("<Left>", _cycle_role)
    login_window.bind("<Right>", _cycle_role)

    signup_btn = Button(login_card, text="New Employee? Create Account", font=("Segoe UI", 10), bg=BG_DARK, fg=LINK_BLUE, 
           bd=0, activebackground=BG_DARK, activeforeground=LINK_BLUE, cursor='hand2', 
           command=open_signup)
    signup_btn.pack(pady=(14, 0))

    login_window.bind("<Configure>", update_shell_layout, add="+")
    main_area.bind("<Configure>", update_login_layout, add="+")

    login_window.after(0, update_shell_layout)
    login_window.after(0, lambda: render_sidebar_background(force=True))
    login_window.after(0, draw_grid)
    login_window.after(0, update_login_layout)

    login_window.mainloop()
    return state["action"]

if __name__ == "__main__":
    app_mod = None
    while True:
        try:
            action = run_login()
            if action == "RUN_APP":
                try:
                    if app_mod is None:
                        import project_monitor as app_mod
                    else:
                        # Force reload session to ensure the correct user is initialized
                        if hasattr(app_mod, 'load_session'):
                            app_mod.load_session()
                    
                    # Ensure database is synced and user state is fresh
                    app_mod.main()
                except SystemExit:
                    pass # User explicitly logged out or closed app
                except Exception as e:
                    show_detailed_error(
                        "Application Fault",
                        "An unexpected error occurred while starting the main application.",
                        e,
                    )
            else:
                break
        except Exception as e:
            show_detailed_error(
                "System Error",
                "The authentication system encountered a critical error.",
                e,
            )
            break
