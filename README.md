# Project Monitoring System 2.0

[![CI/CD](https://github.com/BLACKDEVIL4114/-project-PMS/actions/workflows/ci.yml/badge.svg)](https://github.com/BLACKDEVIL4114/-project-PMS/actions)
![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![GUI](https://img.shields.io/badge/GUI-Tkinter-green)
![DB](https://img.shields.io/badge/Database-SQLite-orange)
![Security](https://img.shields.io/badge/Auth-SHA--256%20%2B%20API%20Key-red)
![License](https://img.shields.io/badge/License-MIT-yellow)

> A professional desktop application for project planning, task assignment, and progress tracking — built with Python, Tkinter, SQLite, and Flask.

---

## 🚀 Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/BLACKDEVIL4114/-project-PMS.git
cd -project-PMS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the application
python login.py
```

**Default Admin Login:**
- Username: `admin`
- Password: `1234`

---

## 📁 Project Structure

```
-project-PMS/
├── login.py              # Entry point - auth & role routing
├── project_monitor.py    # Main dashboard & CRUD operations
├── api.py                # Flask REST API (secured)
├── api_service.py        # API client service layer
├── ai_engine.py          # ML Performance prediction engine
├── analytics_engine.py   # Data analytics & reporting
├── theme.py              # UI constants and color system
├── logger.py             # Centralized logging module
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── USER_MANUAL.md        # End-user guide
└── .github/workflows/    # CI/CD pipeline
    └── ci.yml
```

---

## 🔐 Security

| Feature | Implementation |
|---|---|
| Password Hashing | SHA-256 |
| Password Policy | 8+ chars, Upper, Lower, Digit, Symbol |
| Session Timeout | 8 hours auto-logout |
| API Authentication | `X-API-Key` header |
| SQL Injection | Parameterized queries throughout |
| Login Rate Limiting | Account lockout after failed attempts |

### API Authentication

All API endpoints require the `X-API-Key` header:

```bash
# Example request
curl -H "X-API-Key: pms_secret_key_2026" http://localhost:5000/api/projects

# Response (unauthenticated)
{"error": "Unauthorized"}
```

---

## 🌐 REST API Reference

Start the API server:
```bash
python api.py
```
Server runs at: `http://127.0.0.1:5000`

### Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/` | Health check | ✅ |
| `GET` | `/api/projects` | List all projects | ✅ |
| `GET` | `/api/projects/<id>` | Get single project | ✅ |
| `GET` | `/api/tasks` | List all tasks | ✅ |
| `GET` | `/api/tasks/project/<pid>` | Tasks by project | ✅ |
| `GET` | `/api/members` | List all members | ✅ |
| `GET` | `/api/stats/summary` | System statistics | ✅ |

**Authentication header:** `X-API-Key: pms_secret_key_2026`

---

## 👥 Role-Based Access

| Role | Dashboard | Projects | Tasks | Members | Reports | Analytics |
|------|-----------|----------|-------|---------|---------|-----------|
| Admin | ✅ | ✅ Full CRUD | ✅ Full CRUD | ✅ | ✅ | ✅ |
| Project Manager | ✅ | ✅ Create/Update | ✅ | ❌ | ✅ | ✅ |
| Team Leader | ✅ | ✅ View | ✅ Assign | ✅ Team | ❌ | ❌ |
| Team Member | ✅ Personal | ❌ | ✅ Own tasks | ❌ | ❌ | ❌ |

---

## 🤖 ML Features

The system includes an AI performance prediction engine:

| Model | File | Purpose |
|---|---|---|
| ANN Performance | `employee_ann_model.h5` | Employee performance scoring |
| ANN Enhanced | `employee_performance_ann.h5` | Advanced performance analysis |
| Delay Predictor | `pms_delay_model.joblib` | Project delay risk forecasting |
| Performance Model | `performance_model.pkl` | Task completion prediction |

> **Note:** ML models are excluded from the repo (`.gitignore`) due to file size. Run `python train_model.py` to regenerate locally.

---

## ⚙️ Requirements

```
flask
flask-cors
requests
```

Install: `pip install -r requirements.txt`

**System Requirements:**
- Python 3.9+
- Tkinter (included in standard Python)
- Windows 10/11 recommended (tested)

---

## 🧪 Running Tests

```bash
# Run the test suite
python -m pytest tests.py -v

# Run API tests manually
python tests.py
```

---

## 📝 Logging

Logs are written to `logs/pms_YYYY-MM.log`:

```python
from logger import get_logger
log = get_logger("my_module")
log.info("Operation completed")
log.warning("Security event detected")
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 👨‍💻 Author

**BLACKDEVIL4114** — [GitHub Profile](https://github.com/BLACKDEVIL4114)
