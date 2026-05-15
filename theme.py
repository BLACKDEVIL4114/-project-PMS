# NOVA EXPERIENCE THEME - High Fidelity Color Suite
# ============================================================
# FIX: Added all missing variables that were causing ImportError
# and NameError crashes when changing the UI.
# ============================================================

PRIMARY_RED = "#ff4d4d"      # Vibrant Crimson
PRIMARY_RED_DARK = "#cc3d3d" # Deep Crimson
SIDEBAR_BG = "#111428"       # Midnight Navy
BG_DARK = "#13172e"          # Content Dark
CONTENT_BG = "#13172e"       # Content Dark
CARD_BG = "#252d4d"          # Lighter Indigo-Navy Card for contrast
BG_CARD = "#252d4d"          # Alias
CARD_LIGHT = "#323b63"       # Even lighter for depth
SIDEBAR_ACTIVE_BG = "#1e2540" # Highlight in sidebar
HOVER_BG = "#2d3555"         # Hover State
BORDER_COLOR = "#2e3760"     # Professional subtle border

# Text & Accents
TEXT_WHITE = "#ffffff"
WHITE = "#ffffff"
TEXT_SECONDARY = "#9aa3c2"
MUTED_TEXT = "#707ea2"
ACCENT_BLUE = "#3b82f6"
ACCENT_GREEN = "#10b981"
ACCENT_ORANGE = "#f59e0b"
ACCENT_RED = "#ff4d4d"
ACCENT_PURPLE = "#8b5cf6"
ACCENT_HOVER = "#2d3555"

# Utility
INPUT_BG = "#111428"
INPUT_FG = "#ffffff"
FOCUS_COLOR = "#ff4d4d"
LINK_BLUE = "#60a5fa"

# Mapping for global usage
BG_COLOR = "#13172e"
SIDEBAR_TEXT = "#9aa3c2"
ACTIVE_TEXT = "#ffffff"
HEADER_BG = "#111428"
HEADER_TEXT = "#ffffff"
PRIMARY_BG = "#ff4d4d"
PRIMARY_TEXT = "#ffffff"
CARD_DARK = "#1e2540"
CARD_HOVER = "#2d3555"
BORDER_NAVY = "#2e3760"
TEXT_MUTED = "#707ea2"

# ── FIX 1: Variables missing from theme.py but imported by login.py ──────────
ACCENT_COLOR = "#ff4d4d"    # Was missing -> caused ImportError crash in login.py
TEXT_MAIN    = "#ffffff"    # Was missing -> caused ImportError crash in login.py

# ── FIX 2: Variables missing from theme.py but imported by project_monitor.py ─
BG_NAVY  = "#111428"        # Was missing -> project_monitor had a local fallback
                             # but still tried to import it, risking override issues
BG_BLACK = "#0a0c1a"        # Same issue


def apply_theme(root):
    """Apply the Nova theme to a Tk root window."""
    root.configure(bg=CONTENT_BG)
    from tkinter import ttk

    # FIX 3: Create ONE shared Style instance. Re-creating ttk.Style() inside
    # every load_* function resets state and causes visual flicker when switching pages.
    style = ttk.Style()
    style.theme_use('clam')

    # Custom Treeview Styles matching Nova
    style.configure("Treeview",
                    background=CARD_BG,
                    foreground=TEXT_WHITE,
                    fieldbackground=CARD_BG,
                    padding=10,
                    borderwidth=0,
                    font=('Segoe UI', 10),
                    rowheight=45)

    style.configure("Treeview.Heading",
                    background=SIDEBAR_BG,
                    foreground=TEXT_SECONDARY,
                    font=('Segoe UI', 9, 'bold'),
                    borderwidth=0,
                    padding=10)

    # Sidebar Buttons
    style.configure("Sidebar.TButton",
                    font=('Segoe UI', 11),
                    padding=12)

    # Selection color
    style.map("Treeview",
              background=[('selected', PRIMARY_RED)],
              foreground=[('selected', WHITE)])

    # FIX 4: Combobox dark theme (was never styled, looked wrong on all pages)
    style.configure("TCombobox",
                    fieldbackground=INPUT_BG,
                    background=INPUT_BG,
                    foreground=TEXT_WHITE,
                    selectbackground=PRIMARY_RED,
                    selectforeground=WHITE,
                    borderwidth=0)
    style.map("TCombobox",
              fieldbackground=[('readonly', INPUT_BG)],
              foreground=[('readonly', TEXT_WHITE)],
              selectbackground=[('readonly', PRIMARY_RED)])

    # FIX 5: Scrollbar dark theme (was OS-default light bar on dark background)
    style.configure("Vertical.TScrollbar",
                    background=CARD_BG,
                    troughcolor=BG_DARK,
                    bordercolor=BG_DARK,
                    arrowcolor=TEXT_SECONDARY)
    style.configure("Horizontal.TScrollbar",
                    background=CARD_BG,
                    troughcolor=BG_DARK,
                    bordercolor=BG_DARK,
                    arrowcolor=TEXT_SECONDARY)
