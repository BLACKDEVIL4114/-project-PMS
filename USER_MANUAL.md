# User Manual - Project Monitoring System

This manual provides a detailed guide on how to use the Project Monitoring System based on your assigned role.

## 1. Login
- Launch the application via `login.py`.
- Enter your **Username** and **Password**.
- The system will detect your role (Project Manager, Team Leader, or Senior Employee) and load the appropriate interface.

## 2. Panels & Roles

### A. Project Manager (Admin)
*Full System Access*
1. **Dashboard:**
   - View high-level metrics: Total Projects, Active Tasks, Pending Approvals.
   - Access Quick Actions.
2. **Projects:**
   - **Add Project:** Click "Add Project", enter details (Name, Start/End Date), and save.
   - **Filter:** Use the dropdown to filter projects by status (All, Ongoing, Completed, Delayed).
3. **Tasks:**
   - **Assign Task:** Select a project, enter task details, assign a member, set priority/deadline.
   - **Monitor:** View all tasks across all projects.
4. **Members:**
   - **Add Member:** Register new users with specific roles (Project Manager, Team Leader, Senior Employee).
   - **Manage:** Update or delete existing members.
5. **Reports:**
   - Generate "Project Status", "Task Delays", or "Member Performance" reports.
   - **Export:** Click "Export CSV" to save the data for external analysis.
6. **Audit Trail:**
   - View a log of all actions (Login, Create, Update, Delete) performed by any user.
   - **Backup DB:** Create a secure backup of the current database.

### B. Team Leader
*Operational Access*
1. **My Tasks:**
   - View tasks specifically assigned to you or your team.
2. **Update Status:**
   - Select a task and change its status (e.g., "In Progress" to "Completed").
   - *Note:* Critical updates may require Project Manager approval.
3. **Productivity:**
   - View visual charts (Progress Bars) showing your task completion rates vs. deadlines.

### C. Senior Employee
*Oversight Access*
1. **Dashboard:**
   - View read-only summaries of project health.
2. **Reports:**
   - Access all reports to monitor organizational performance without the ability to modify data.
3. **Audit:**
   - View the audit trail to ensure compliance.

## 3. Key Features Guide

### Notifications
- Click the **Bell Icon** in the top header.
- View alerts for new task assignments or approval requests.
- Click "Mark All Read" to clear notifications.

### Database Backup
- Go to the **Audit** page (Project Manager only).
- Click **"Backup Database"**.
- Select a location to save the `.db` file.

### Troubleshooting
- **Login Failed:** Check credentials or contact a Project Manager to reset your password.
- **Data Not Saving:** Ensure all required fields (marked with *) are filled.
- **Application Error:** Check the terminal output for error logs if the application closes unexpectedly.
