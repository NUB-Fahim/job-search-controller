# Job Portal Management System

A single-purpose desktop app built with **Python + Tkinter (ttk) + SQLite3**.

## Structure

The codebase is split into three layers, developed on three separate
branches and merged into `main`:

| Layer    | Branch     | File         | Responsibility                                   |
|----------|-----------|--------------|---------------------------------------------------|
| Backend  | `backend`  | `backend.py` | SQLite schema, auth, validation, all business logic |
| UI       | `ui`       | `ui.py`      | Tkinter/ttk screens (login, dashboards, dialogs)  |
| Frontend | `frontend` | `app.py`     | App window, theming/styling, navigation, entry point |

## Features

1. User Registration & Login (Job Seeker / Employer / Admin)
2. Admin Dashboard (manage users, jobs, feedback)
3. Profile Management (seeker + employer)
4. Job Posting Module (with admin approval workflow)
5. Job Search & Filter (keyword, location, type, salary — FTS5 with LIKE fallback)
6. Job Application System
7. Resume Upload (validated, copied into local storage)
8. View Applied Jobs
9. Notifications (skill-matching alerts + application status updates)
10. SQLite3 backend (foreign keys, audit log)
11. ttk-styled Tkinter GUI
12. Input validation & error handling throughout

## Run it

```bash
python app.py
```

On first run, a default admin account is created:

```
email: admin@jobportal.local
password: Admin@123
```

## Requirements

- Python 3.9+
- Tkinter (bundled with most Python installers; on Debian/Ubuntu: `sudo apt install python3-tk`)
- No third-party pip packages required (stdlib only)

## Data storage

Runtime data (`app_data/`, containing the SQLite DB and uploaded resumes)
is git-ignored — each environment gets its own local database.
