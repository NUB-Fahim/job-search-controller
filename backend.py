"""
backend.py
----------
Data layer + business logic for the Job Portal Management System.
No GUI code lives here. UI modules import from this file only.

Covers:
- SQLite3 schema + migrations
- Password hashing (PBKDF2-HMAC-SHA256, salted)
- Auth (register / login) for seeker, employer, admin
- Profile management (seeker + employer)
- Job posting / moderation / search & filter (FTS5 with LIKE fallback)
- Application system (apply, list, status updates)
- Resume upload (copies file into local storage, stores path)
- Notifications (simple keyword-matching alerts)
- Admin dashboard operations (users, jobs, feedback)
- Audit logging
"""

import os
import re
import sqlite3
import hashlib
import hmac
import base64
import shutil
import uuid
from datetime import datetime
from pathlib import Path

# -------------------- Paths --------------------
APP_DIR = Path("app_data")
DB_PATH = APP_DIR / "app.db"
RESUME_DIR = APP_DIR / "resumes"
APP_DIR.mkdir(parents=True, exist_ok=True)
RESUME_DIR.mkdir(parents=True, exist_ok=True)

USE_FTS = True

ALLOWED_RESUME_EXT = {".pdf", ".doc", ".docx", ".txt", ".rtf"}
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship", "Remote"]
JOB_STATUSES = ["draft", "pending", "approved", "closed", "rejected"]
APPLICATION_STATUSES = [
    "submitted", "under_review", "shortlisted", "interviewed", "offered", "rejected"
]


# -------------------- Connection --------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds")


# -------------------- Schema --------------------
SCHEMA_BASE = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash BLOB NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('seeker','employer','admin')),
    is_verified INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS seeker_profiles (
    user_id INTEGER PRIMARY KEY,
    name TEXT, phone TEXT, skills TEXT,
    resume_path TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employer_profiles (
    user_id INTEGER PRIMARY KEY,
    company TEXT NOT NULL, website TEXT, industry TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY,
    employer_id INTEGER NOT NULL,
    title TEXT NOT NULL, description TEXT NOT NULL,
    location TEXT, type TEXT, experience TEXT,
    salary_min INTEGER, salary_max INTEGER,
    status TEXT NOT NULL DEFAULT 'pending', -- draft|pending|approved|closed|rejected
    created_at TEXT NOT NULL,
    FOREIGN KEY(employer_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    seeker_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'submitted',
    cover_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, seeker_id),
    FOREIGN KEY(job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY(seeker_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open', -- open|reviewed|closed
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY,
    actor_id INTEGER,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(actor_id) REFERENCES users(id) ON DELETE SET NULL
);
"""

SCHEMA_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
    title, description, content='jobs', content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS jobs_ai AFTER INSERT ON jobs BEGIN
    INSERT INTO jobs_fts(rowid, title, description)
    VALUES (new.id, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS jobs_au AFTER UPDATE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, title, description)
    VALUES('delete', old.id, old.title, old.description);
    INSERT INTO jobs_fts(rowid, title, description)
    VALUES (new.id, new.title, new.description);
END;

CREATE TRIGGER IF NOT EXISTS jobs_ad AFTER DELETE ON jobs BEGIN
    INSERT INTO jobs_fts(jobs_fts, rowid, title, description)
    VALUES('delete', old.id, old.title, old.description);
END;
"""


def init_db():
    global USE_FTS
    with get_conn() as conn:
        conn.executescript(SCHEMA_BASE)
        try:
            conn.executescript(SCHEMA_FTS)
            USE_FTS = True
        except sqlite3.DatabaseError:
            USE_FTS = False
    _ensure_default_admin()


def _ensure_default_admin():
    """Create a default admin account on first run: admin@jobportal.local / Admin@123"""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE role='admin' LIMIT 1").fetchone()
        if row is None:
            try:
                register_user("admin@jobportal.local", "Admin@123", "admin", auto_verify=True)
            except ValueError:
                pass


# -------------------- Validation helpers --------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> bool:
    return bool(EMAIL_RE.match((email or "").strip()))


def validate_password(pw: str) -> bool:
    """At least 6 chars, one letter and one digit."""
    if not pw or len(pw) < 6:
        return False
    return bool(re.search(r"[A-Za-z]", pw)) and bool(re.search(r"\d", pw))


# -------------------- Password hashing --------------------
def _hash_password(password: str, salt: bytes = None) -> bytes:
    if salt is None:
        salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return salt + dk  # store salt prefixed to derived key


def _verify_password(password: str, stored: bytes) -> bool:
    salt, dk = stored[:16], stored[16:]
    new_dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(dk, new_dk)


# -------------------- Audit --------------------
def log_action(actor_id, action, entity_type, entity_id):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO audit_logs(actor_id, action, entity_type, entity_id, timestamp) "
            "VALUES (?,?,?,?,?)",
            (actor_id, action, entity_type, entity_id, now_iso()),
        )


# -------------------- Auth --------------------
def register_user(email, password, role, auto_verify=False):
    email = (email or "").strip().lower()
    if not validate_email(email):
        raise ValueError("Please enter a valid email address.")
    if not validate_password(password):
        raise ValueError("Password must be 6+ characters and include a letter and a digit.")
    if role not in ("seeker", "employer", "admin"):
        raise ValueError("Invalid role.")

    pw_hash = _hash_password(password)
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            raise ValueError("An account with this email already exists.")
        cur = conn.execute(
            "INSERT INTO users(email, password_hash, role, is_verified, created_at) "
            "VALUES (?,?,?,?,?)",
            (email, pw_hash, role, 1 if auto_verify else 0, now_iso()),
        )
        user_id = cur.lastrowid
        if role == "seeker":
            conn.execute("INSERT INTO seeker_profiles(user_id, name) VALUES (?,?)", (user_id, ""))
        elif role == "employer":
            conn.execute(
                "INSERT INTO employer_profiles(user_id, company, approved) VALUES (?,?,0)",
                (user_id, ""),
            )
    log_action(user_id, "register", "user", user_id)
    return user_id


def login_user(email, password):
    email = (email or "").strip().lower()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if row is None:
            raise ValueError("No account found with that email.")
        if not row["is_active"]:
            raise ValueError("This account has been disabled. Contact admin.")
        if not _verify_password(password, row["password_hash"]):
            raise ValueError("Incorrect password.")
        log_action(row["id"], "login", "user", row["id"])
        return dict(row)


# -------------------- Profile management --------------------
def get_seeker_profile(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM seeker_profiles WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_seeker_profile(user_id, name, phone, skills):
    with get_conn() as conn:
        conn.execute(
            "UPDATE seeker_profiles SET name=?, phone=?, skills=? WHERE user_id=?",
            (name.strip(), phone.strip(), skills.strip(), user_id),
        )
    log_action(user_id, "update_profile", "seeker_profile", user_id)


def get_employer_profile(user_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM employer_profiles WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_employer_profile(user_id, company, website, industry):
    if not company.strip():
        raise ValueError("Company name is required.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE employer_profiles SET company=?, website=?, industry=? WHERE user_id=?",
            (company.strip(), website.strip(), industry.strip(), user_id),
        )
    log_action(user_id, "update_profile", "employer_profile", user_id)


def upload_resume(user_id, source_path: str) -> str:
    src = Path(source_path)
    if not src.exists():
        raise ValueError("Selected file does not exist.")
    if src.suffix.lower() not in ALLOWED_RESUME_EXT:
        raise ValueError(f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_RESUME_EXT))}")
    if src.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Resume file must be smaller than 5MB.")

    dest_name = f"{user_id}_{uuid.uuid4().hex[:8]}{src.suffix.lower()}"
    dest = RESUME_DIR / dest_name
    shutil.copyfile(src, dest)

    with get_conn() as conn:
        conn.execute(
            "UPDATE seeker_profiles SET resume_path=? WHERE user_id=?", (str(dest), user_id)
        )
    log_action(user_id, "upload_resume", "seeker_profile", user_id)
    return str(dest)


# -------------------- Jobs --------------------
def create_job(employer_id, title, description, location, jtype, experience,
                salary_min, salary_max, submit_for_approval=True):
    if not title.strip() or not description.strip():
        raise ValueError("Title and description are required.")
    try:
        smin = int(salary_min) if salary_min not in (None, "") else None
        smax = int(salary_max) if salary_max not in (None, "") else None
    except ValueError:
        raise ValueError("Salary must be a whole number.")
    if smin is not None and smax is not None and smin > smax:
        raise ValueError("Minimum salary cannot exceed maximum salary.")

    status = "pending" if submit_for_approval else "draft"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO jobs(employer_id, title, description, location, type, experience, "
            "salary_min, salary_max, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (employer_id, title.strip(), description.strip(), location.strip(), jtype,
             experience.strip(), smin, smax, status, now_iso()),
        )
        job_id = cur.lastrowid
    log_action(employer_id, "create_job", "job", job_id)
    if status == "pending":
        _notify_matching_seekers(job_id)
    return job_id


def update_job_status(job_id, status, actor_id=None):
    if status not in JOB_STATUSES:
        raise ValueError("Invalid job status.")
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    log_action(actor_id, f"job_status_{status}", "job", job_id)
    if status == "approved":
        _notify_matching_seekers(job_id)


def list_jobs_by_employer(employer_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE employer_id=? ORDER BY created_at DESC", (employer_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_job(job_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row) if row else None


def search_jobs(keyword="", location="", jtype="", min_salary=None, status="approved"):
    keyword = (keyword or "").strip()
    location = (location or "").strip()
    with get_conn() as conn:
        if keyword and USE_FTS:
            sql = (
                "SELECT j.* FROM jobs j JOIN jobs_fts f ON j.id = f.rowid "
                "WHERE jobs_fts MATCH ? AND j.status=?"
            )
            params = [keyword.replace('"', '') + "*", status]
        else:
            sql = "SELECT * FROM jobs WHERE status=?"
            params = [status]
            if keyword:
                sql += " AND (title LIKE ? OR description LIKE ?)"
                params += [f"%{keyword}%", f"%{keyword}%"]

        if location:
            sql += " AND location LIKE ?"
            params.append(f"%{location}%")
        if jtype:
            sql += " AND type = ?"
            params.append(jtype)
        if min_salary:
            sql += " AND (salary_max IS NULL OR salary_max >= ?)"
            params.append(int(min_salary))

        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def list_pending_jobs():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT j.*, e.company FROM jobs j "
            "LEFT JOIN employer_profiles e ON e.user_id = j.employer_id "
            "WHERE j.status='pending' ORDER BY j.created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


# -------------------- Applications --------------------
def apply_to_job(seeker_id, job_id, cover_note=""):
    job = get_job(job_id)
    if job is None or job["status"] != "approved":
        raise ValueError("This job is not open for applications.")
    profile = get_seeker_profile(seeker_id)
    if not profile or not profile.get("resume_path"):
        raise ValueError("Please upload your resume before applying.")

    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM applications WHERE job_id=? AND seeker_id=?", (job_id, seeker_id)
        ).fetchone()
        if existing:
            raise ValueError("You have already applied to this job.")
        cur = conn.execute(
            "INSERT INTO applications(job_id, seeker_id, status, cover_note, created_at, updated_at) "
            "VALUES (?,?, 'submitted', ?, ?, ?)",
            (job_id, seeker_id, cover_note.strip(), now_iso(), now_iso()),
        )
        app_id = cur.lastrowid
        conn.execute(
            "INSERT INTO notifications(user_id, type, payload, created_at) VALUES (?,?,?,?)",
            (job["employer_id"], "new_application",
             f"New application received for '{job['title']}'.", now_iso()),
        )
    log_action(seeker_id, "apply", "job", job_id)
    return app_id


def list_applications_for_seeker(seeker_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.*, j.title, j.location, j.type, j.status AS job_status "
            "FROM applications a JOIN jobs j ON j.id = a.job_id "
            "WHERE a.seeker_id=? ORDER BY a.created_at DESC", (seeker_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def list_applications_for_job(job_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.*, sp.name, sp.phone, sp.skills, sp.resume_path, u.email "
            "FROM applications a "
            "JOIN seeker_profiles sp ON sp.user_id = a.seeker_id "
            "JOIN users u ON u.id = a.seeker_id "
            "WHERE a.job_id=? ORDER BY a.created_at DESC", (job_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def update_application_status(app_id, status, actor_id=None):
    if status not in APPLICATION_STATUSES:
        raise ValueError("Invalid application status.")
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
        if row is None:
            raise ValueError("Application not found.")
        conn.execute(
            "UPDATE applications SET status=?, updated_at=? WHERE id=?",
            (status, now_iso(), app_id),
        )
        job = conn.execute("SELECT title FROM jobs WHERE id=?", (row["job_id"],)).fetchone()
        conn.execute(
            "INSERT INTO notifications(user_id, type, payload, created_at) VALUES (?,?,?,?)",
            (row["seeker_id"], "application_update",
             f"Your application for '{job['title']}' is now '{status}'.", now_iso()),
        )
    log_action(actor_id, f"application_{status}", "application", app_id)


# -------------------- Notifications --------------------
def _notify_matching_seekers(job_id):
    """Simple keyword-matching alert: notify seekers whose skills overlap job title/description."""
    job = get_job(job_id)
    if not job:
        return
    haystack = f"{job['title']} {job['description']}".lower()
    with get_conn() as conn:
        seekers = conn.execute(
            "SELECT user_id, skills FROM seeker_profiles WHERE skills IS NOT NULL AND skills != ''"
        ).fetchall()
        for s in seekers:
            skills = [sk.strip().lower() for sk in (s["skills"] or "").split(",") if sk.strip()]
            if any(sk in haystack for sk in skills):
                conn.execute(
                    "INSERT INTO notifications(user_id, type, payload, created_at) VALUES (?,?,?,?)",
                    (s["user_id"], "job_match",
                     f"New job matching your skills: '{job['title']}'.", now_iso()),
                )


def list_notifications(user_id, unread_only=False):
    with get_conn() as conn:
        sql = "SELECT * FROM notifications WHERE user_id=?"
        params = [user_id]
        if unread_only:
            sql += " AND is_read=0"
        sql += " ORDER BY created_at DESC"
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def mark_notification_read(notification_id):
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (notification_id,))


def mark_all_notifications_read(user_id):
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))


# -------------------- Feedback --------------------
def submit_feedback(user_id, subject, message):
    if not subject.strip() or not message.strip():
        raise ValueError("Subject and message are required.")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO feedback(user_id, subject, message, created_at) VALUES (?,?,?,?)",
            (user_id, subject.strip(), message.strip(), now_iso()),
        )


def list_feedback(status=None):
    with get_conn() as conn:
        if status:
            rows = conn.execute(
                "SELECT f.*, u.email FROM feedback f LEFT JOIN users u ON u.id=f.user_id "
                "WHERE f.status=? ORDER BY f.created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT f.*, u.email FROM feedback f LEFT JOIN users u ON u.id=f.user_id "
                "ORDER BY f.created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def update_feedback_status(feedback_id, status):
    if status not in ("open", "reviewed", "closed"):
        raise ValueError("Invalid feedback status.")
    with get_conn() as conn:
        conn.execute("UPDATE feedback SET status=? WHERE id=?", (status, feedback_id))


# -------------------- Admin: users --------------------
def list_users(role=None):
    with get_conn() as conn:
        if role:
            rows = conn.execute(
                "SELECT * FROM users WHERE role=? ORDER BY created_at DESC", (role,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


def set_user_active(user_id, active: bool, actor_id=None):
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, user_id))
    log_action(actor_id, "activate" if active else "deactivate", "user", user_id)


def approve_employer(user_id, actor_id=None):
    with get_conn() as conn:
        conn.execute("UPDATE employer_profiles SET approved=1 WHERE user_id=?", (user_id,))
        conn.execute("UPDATE users SET is_verified=1 WHERE id=?", (user_id,))
    log_action(actor_id, "approve_employer", "user", user_id)


def admin_stats():
    with get_conn() as conn:
        stats = {}
        stats["total_users"] = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        stats["total_seekers"] = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE role='seeker'"
        ).fetchone()["c"]
        stats["total_employers"] = conn.execute(
            "SELECT COUNT(*) c FROM users WHERE role='employer'"
        ).fetchone()["c"]
        stats["total_jobs"] = conn.execute("SELECT COUNT(*) c FROM jobs").fetchone()["c"]
        stats["pending_jobs"] = conn.execute(
            "SELECT COUNT(*) c FROM jobs WHERE status='pending'"
        ).fetchone()["c"]
        stats["total_applications"] = conn.execute(
            "SELECT COUNT(*) c FROM applications"
        ).fetchone()["c"]
        stats["open_feedback"] = conn.execute(
            "SELECT COUNT(*) c FROM feedback WHERE status='open'"
        ).fetchone()["c"]
        return stats
