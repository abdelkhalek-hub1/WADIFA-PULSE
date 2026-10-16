import sqlite3
import os
from datetime import date
import config

DB_PATH = os.path.join(config.BASE_DIR, "wadifa_local.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialise la base de données locale SQLite."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id TEXT PRIMARY KEY,
        title TEXT,
        grade TEXT,
        organism TEXT,
        deadline_date TEXT,
        deadline_str TEXT,
        days_left INTEGER,
        diplomas TEXT,
        specialties TEXT,
        link TEXT,
        source TEXT,
        date_found TEXT,
        description TEXT,
        is_favorite INTEGER DEFAULT 0,
        status_applied TEXT DEFAULT 'a_postuler',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

def save_jobs(jobs: list[dict]):
    """Sauvegarde ou met à jour les concours dans la base de données locale."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    for j in jobs:
        cursor.execute("""
        INSERT INTO jobs (id, title, grade, organism, deadline_date, deadline_str, days_left, diplomas, specialties, link, source, date_found, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            days_left = excluded.days_left,
            deadline_str = excluded.deadline_str,
            deadline_date = excluded.deadline_date,
            diplomas = excluded.diplomas,
            specialties = excluded.specialties,
            source = excluded.source
        """, (
            j.get("id"),
            j.get("title"),
            j.get("grade"),
            j.get("organism"),
            j.get("deadline_date"),
            j.get("deadline_str"),
            j.get("days_left"),
            j.get("diplomas"),
            j.get("specialties"),
            j.get("link"),
            j.get("source"),
            j.get("date_found"),
            j.get("description", "")
        ))
    
    conn.commit()
    conn.close()

def get_all_jobs(active_only: bool = True) -> list[dict]:
    """Récupère tous les concours stockés en local."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs"
    if active_only:
        query += " WHERE days_left >= 0"
    query += " ORDER BY days_left ASC"
    
    rows = cursor.execute(query).fetchall()
    jobs = [dict(row) for row in rows]
    conn.close()
    return jobs

def toggle_favorite(job_id: str) -> bool:
    """Marque ou démarque un concours comme favori."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT is_favorite FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row:
        new_fav = 0 if row["is_favorite"] == 1 else 1
        cursor.execute("UPDATE jobs SET is_favorite = ? WHERE id = ?", (new_fav, job_id))
        conn.commit()
        conn.close()
        return bool(new_fav)
    conn.close()
    return False

def update_status(job_id: str, status: str) -> bool:
    """Met à jour le statut de candidature (a_postuler, postule, rejete, etc.)."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status_applied = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()
    return True

def get_stats() -> dict:
    """Calcule les statistiques globales des concours stockés."""
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    total = cursor.execute("SELECT COUNT(*) FROM jobs WHERE days_left >= 0").fetchone()[0]
    urgent = cursor.execute("SELECT COUNT(*) FROM jobs WHERE days_left >= 0 AND days_left <= 3").fetchone()[0]
    favorites = cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_favorite = 1").fetchone()[0]
    applied = cursor.execute("SELECT COUNT(*) FROM jobs WHERE status_applied = 'postule'").fetchone()[0]
    
    conn.close()
    return {
        "total": total,
        "urgent": urgent,
        "favorites": favorites,
        "applied": applied
    }
