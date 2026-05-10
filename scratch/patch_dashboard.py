import sys
import re
sys.stdout.reconfigure(encoding='utf-8')

with open('project_monitor.py', encoding='utf-8') as f:
    content = f.read()

# ─── PATCH 1: Project list rows in load_pm_dashboard ───────────────────────
OLD_PROJ_ROWS = '''        else:
            for pid, pname, leader, mgr, end_date, prog, status in project_progress_data:
                p_item = Frame(left_col, bg=CARD_BG, pady=10, cursor="hand2")
                p_item.pack(fill=X)

                def open_proj(p=pid, n=pname):
                    self.show_project_tasks_modal(p, n)

                # Info Row
                info = Frame(p_item, bg=CARD_BG)
                info.pack(fill=X)
                l1 = Label(info, text=pname, font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=TEXT_WHITE)
                l1.pack(side=LEFT)

                # Status Color
                s_color = ACCENT_ORANGE
                if status == "Delayed": s_color = ACCENT_RED
                elif status == "Not Started": s_color = MUTED_TEXT
                elif status == "Completed": s_color = ACCENT_GREEN

                l_stat = Label(info, text=status, font=('Segoe UI', 9), bg=CARD_BG, fg=s_color)
                l_stat.pack(side=LEFT, padx=10)

                l2 = Label(info, text=f"{prog}%", font=('Segoe UI', 11, 'bold'), bg=CARD_BG, fg=ACCENT_GREEN)
                l2.pack(side=RIGHT)

                # Sub-info
                sub = Frame(p_item, bg=CARD_BG)
                sub.pack(fill=X, pady=(2, 5))
                leader_txt = leader if leader else (mgr if mgr else "No Leader")
                l3 = Label(sub, text=f"Lead: {leader_txt} | Due: {end_date}", font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT)
                l3.pack(side=LEFT)

                # 3. Show "No Data" Message
                if prog == 0:
                    Label(sub, text="(No tasks assigned yet)", font=('Segoe UI', 9), bg=CARD_BG, fg=ACCENT_ORANGE).pack(side=LEFT, padx=10)

                # Progress Bar
                bar_bg = Frame(p_item, bg="#404040", height=8)
                bar_bg.pack(fill=X)
                if prog > 0:
                    bar_fg = Frame(bar_bg, bg=ACCENT_GREEN, width=int(prog)*2, height=8)
                    bar_fg.place(x=0, y=0, relwidth=prog/100)
                    bar_fg.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))

                ttk.Separator(left_col, orient='horizontal').pack(fill=X, pady=5)

                # Bind events
                for w in [p_item, info, l1, l_stat, l2, sub, l3, bar_bg]:
                    w.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))'''

NEW_PROJ_ROWS = '''        else:
            for pid, pname, leader, mgr, end_date, prog, status in project_progress_data:
                # ── Enhanced row: colored left stripe + pill badge ──
                _s_bg     = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_ORANGE,
                              "Delayed": ACCENT_RED, "Not Started": MUTED_TEXT}.get(status, MUTED_TEXT)
                _s_stripe = {"Completed": ACCENT_GREEN, "Ongoing": ACCENT_BLUE,
                             "Delayed": ACCENT_RED, "Not Started": "#555e7a"}.get(status, MUTED_TEXT)
                _bar_col  = (ACCENT_GREEN if prog >= 75 else
                             ACCENT_ORANGE if prog >= 40 else ACCENT_RED)
                if status == "Completed": _bar_col = ACCENT_GREEN

                # Colored left stripe
                row_wrap = Frame(left_col, bg=_s_stripe, pady=0)
                row_wrap.pack(fill=X, pady=3)

                p_item = Frame(row_wrap, bg=CARD_BG, padx=16, pady=10, cursor="hand2")
                p_item.pack(fill=BOTH, expand=True, padx=(4, 0))

                def open_proj(p=pid, n=pname):
                    self.show_project_tasks_modal(p, n)

                # Info Row
                info = Frame(p_item, bg=CARD_BG)
                info.pack(fill=X)

                l1 = Label(info, text=pname, font=('Segoe UI', 11, 'bold'),
                           bg=CARD_BG, fg=TEXT_WHITE)
                l1.pack(side=LEFT)

                # Pill-style status badge
                badge_frame = Frame(info, bg=_s_bg, padx=7, pady=2)
                badge_frame.pack(side=LEFT, padx=8)
                Label(badge_frame, text=status, font=('Segoe UI', 8, 'bold'),
                      bg=_s_bg, fg=WHITE).pack()

                l2 = Label(info, text=f"{prog}%", font=('Segoe UI', 11, 'bold'),
                           bg=CARD_BG, fg=_bar_col)
                l2.pack(side=RIGHT)

                # Sub-info
                sub = Frame(p_item, bg=CARD_BG)
                sub.pack(fill=X, pady=(3, 6))
                leader_txt = leader if leader else (mgr if mgr else "No Leader")
                l3 = Label(sub, text=f"Lead: {leader_txt}  \u00b7  Due: {end_date or chr(8212)}",
                           font=('Segoe UI', 9), bg=CARD_BG, fg=MUTED_TEXT)
                l3.pack(side=LEFT)
                if prog == 0 and status != "Completed":
                    Label(sub, text="  No tasks yet", font=('Segoe UI', 9, 'italic'),
                          bg=CARD_BG, fg=ACCENT_ORANGE).pack(side=LEFT)

                # Sleek thin progress bar
                bar_track = Frame(p_item, bg="#2a3352", height=5)
                bar_track.pack(fill=X)
                if prog > 0:
                    bar_fill = Frame(bar_track, bg=_bar_col, height=5)
                    bar_fill.place(x=0, y=0, relwidth=min(prog / 100, 1.0))
                    bar_fill.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))

                for w in [row_wrap, p_item, info, l1, badge_frame, l2, sub, l3, bar_track]:
                    w.bind("<Button-1>", lambda e, p=pid, n=pname: open_proj(p, n))'''

if OLD_PROJ_ROWS in content:
    content = content.replace(OLD_PROJ_ROWS, NEW_PROJ_ROWS, 1)
    print("PATCH 1 (project rows): APPLIED")
else:
    print("PATCH 1 (project rows): NOT FOUND - checking variants...")
    # Try with \r\n
    old_rn = OLD_PROJ_ROWS.replace('\n', '\r\n')
    if old_rn in content:
        content = content.replace(old_rn, NEW_PROJ_ROWS, 1)
        print("PATCH 1 (project rows): APPLIED (CRLF variant)")
    else:
        print("PATCH 1: FAILED - manual check needed")

# ─── PATCH 2: Section header for left column ────────────────────────────────
OLD_LEFT_HDR = 'Label(left_col, text="Company Projects List", font=(\'Segoe UI\', 14, \'bold\'), bg=CARD_BG, fg=TEXT_WHITE).pack(anchor=W, pady=(0, 20))'
NEW_LEFT_HDR = '''# Section header with separator line
        lh = Frame(left_col, bg=CARD_BG)
        lh.pack(fill=X, pady=(0, 8))
        Label(lh, text="\U0001f4c2  Company Projects", font=('Segoe UI', 14, 'bold'),
              bg=CARD_BG, fg=TEXT_WHITE).pack(side=LEFT)
        Frame(left_col, bg=BORDER_NAVY, height=1).pack(fill=X, pady=(0, 12))'''

if OLD_LEFT_HDR in content:
    content = content.replace(OLD_LEFT_HDR, NEW_LEFT_HDR, 1)
    print("PATCH 2 (section header): APPLIED")
else:
    print("PATCH 2 (section header): NOT FOUND")

# ─── PATCH 3: Dashboard page title — bigger, with subtitle ──────────────────
OLD_TITLE = 'Label(title_box, text="Project Manager Dashboard", font=(\'Segoe UI\', 24, \'bold\'),\n              bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)'
NEW_TITLE = '''Label(title_box, text="Project Manager Dashboard",
              font=('Segoe UI', 24, 'bold'), bg=CONTENT_BG, fg=TEXT_WHITE).pack(anchor=W)
        Label(title_box, text="Real-time overview of all projects and team performance",
              font=('Segoe UI', 10), bg=CONTENT_BG, fg=TEXT_SECONDARY).pack(anchor=W, pady=(2, 0))'''

if OLD_TITLE in content:
    content = content.replace(OLD_TITLE, NEW_TITLE, 1)
    print("PATCH 3 (title subtitle): APPLIED")
else:
    print("PATCH 3 (title subtitle): NOT FOUND - trying alt...")
    # The text might differ slightly
    idx = content.find('"Project Manager Dashboard"')
    if idx >= 0:
        print(f"  Title text found at char {idx}, context:")
        print(repr(content[idx-80:idx+80]))

with open('project_monitor.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("\nFile saved.")
