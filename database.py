import os
import json
import sqlite3
from datetime import date, datetime
from werkzeug.security import generate_password_hash, check_password_hash
import config

# Paramètres de connexion Supabase PostgreSQL
DB_USER = "postgres.xiyilbkzcaczzmbthssl"
DB_PASS = "wadifa123@dc"
DB_HOST = "aws-0-eu-west-1.pooler.supabase.com"
DB_PORT = 6543
DB_NAME = "postgres"

SQLITE_PATH = os.path.join(config.BASE_DIR, "wadifa_local.db")

def get_pg_connection():
    """Tente une connexion à Supabase PostgreSQL."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            sslmode="require",
            connect_timeout=10
        )
        return conn, "postgres"
    except Exception as e:
        print(f"ℹ️ Connexion Supabase indisponible ({e}), utilisation de la base locale SQLite.")
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn, "sqlite"

def init_db():
    """Initialise les tables dans Supabase (users, jobs, daily_history) et crée le compte utilisateur."""
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    if db_type == "postgres":
        # 1. Table Utilisateurs (Auth)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            name VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 2. Table Concours
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id VARCHAR(255) PRIMARY KEY,
            title TEXT,
            grade TEXT,
            organism TEXT,
            deadline_date VARCHAR(50),
            deadline_str VARCHAR(100),
            days_left INT,
            diplomas TEXT,
            specialties TEXT,
            link TEXT,
            source VARCHAR(100),
            date_found VARCHAR(50),
            description TEXT,
            is_favorite BOOLEAN DEFAULT FALSE,
            status_applied VARCHAR(50) DEFAULT 'a_postuler',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # 3. Table Historique Quotidien
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_history (
            id SERIAL PRIMARY KEY,
            run_date VARCHAR(50) NOT NULL,
            total_jobs INT DEFAULT 0,
            new_jobs INT DEFAULT 0,
            urgent_jobs INT DEFAULT 0,
            sources VARCHAR(255),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    else:
        # Fallback SQLite
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
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
        );
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            total_jobs INTEGER DEFAULT 0,
            new_jobs INTEGER DEFAULT 0,
            urgent_jobs INTEGER DEFAULT 0,
            sources TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

    conn.commit()
    conn.close()

def authenticate_user(email: str, password: str) -> dict | None:
    """Authentifie un utilisateur depuis la base de données sans rien coder en dur."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    user = None
    if db_type == "postgres":
        cursor.execute("SELECT id, email, password_hash, name FROM users WHERE email = %s", (email.strip().lower(),))
        row = cursor.fetchone()
        if row:
            # row: (id, email, password_hash, name)
            if check_password_hash(row[2], password):
                user = {"id": row[0], "email": row[1], "name": row[3]}
    else:
        cursor.execute("SELECT id, email, password_hash, name FROM users WHERE email = ?", (email.strip().lower(),))
        row = cursor.fetchone()
        if row:
            if check_password_hash(row["password_hash"], password):
                user = {"id": row["id"], "email": row["email"], "name": row["name"]}

    conn.close()
    return user

def save_jobs(jobs: list[dict]):
    """Sauvegarde les concours dans Supabase / SQLite."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    for j in jobs:
        if db_type == "postgres":
            query = """
            INSERT INTO jobs (id, title, grade, organism, deadline_date, deadline_str, days_left, diplomas, specialties, link, source, date_found, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                days_left = EXCLUDED.days_left,
                deadline_str = EXCLUDED.deadline_str,
                deadline_date = EXCLUDED.deadline_date,
                diplomas = EXCLUDED.diplomas,
                specialties = EXCLUDED.specialties,
                source = EXCLUDED.source;
            """
            cursor.execute(query, (
                j.get("id"), j.get("title"), j.get("grade"), j.get("organism"),
                str(j.get("deadline_date")), j.get("deadline_str"), j.get("days_left"),
                j.get("diplomas"), j.get("specialties"), j.get("link"),
                j.get("source"), j.get("date_found"), j.get("description", "")
            ))
        else:
            query = """
            INSERT INTO jobs (id, title, grade, organism, deadline_date, deadline_str, days_left, diplomas, specialties, link, source, date_found, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                days_left = excluded.days_left,
                deadline_str = excluded.deadline_str,
                deadline_date = excluded.deadline_date,
                diplomas = excluded.diplomas,
                specialties = excluded.specialties,
                source = excluded.source;
            """
            cursor.execute(query, (
                j.get("id"), j.get("title"), j.get("grade"), j.get("organism"),
                str(j.get("deadline_date")), j.get("deadline_str"), j.get("days_left"),
                j.get("diplomas"), j.get("specialties"), j.get("link"),
                j.get("source"), j.get("date_found"), j.get("description", "")
            ))

    conn.commit()
    conn.close()

def record_daily_history(run_date: str, total_jobs: int, new_jobs: int, urgent_jobs: int, sources: str = "emploi-public + wadifa-info"):
    """Enregistre l'exécution quotidienne dans l'historique."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    if db_type == "postgres":
        cursor.execute("""
        INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources)
        VALUES (%s, %s, %s, %s, %s)
        """, (run_date, total_jobs, new_jobs, urgent_jobs, sources))
    else:
        cursor.execute("""
        INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources)
        VALUES (?, ?, ?, ?, ?)
        """, (run_date, total_jobs, new_jobs, urgent_jobs, sources))

    conn.commit()
    conn.close()

def get_daily_history() -> list[dict]:
    """Récupère l'historique complet des exécutions par jour."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM daily_history ORDER BY id DESC"
    cursor.execute(query)

    history = []
    if db_type == "postgres":
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            history.append(dict(zip(columns, row)))
    else:
        for row in cursor.fetchall():
            history.append(dict(row))

    conn.close()
    return history

def get_all_jobs(active_only: bool = True) -> list[dict]:
    """Récupère les concours depuis Supabase / SQLite."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM jobs"
    if active_only:
        query += " WHERE days_left >= 0"
    query += " ORDER BY days_left ASC"

    cursor.execute(query)
    jobs = []
    if db_type == "postgres":
        columns = [desc[0] for desc in cursor.description]
        for row in cursor.fetchall():
            jobs.append(dict(zip(columns, row)))
    else:
        for row in cursor.fetchall():
            jobs.append(dict(row))

    conn.close()
    return jobs

def toggle_favorite(job_id: str) -> bool:
    """Bascule le statut favori."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    new_fav = False
    if db_type == "postgres":
        cursor.execute("SELECT is_favorite FROM jobs WHERE id = %s", (job_id,))
        row = cursor.fetchone()
        if row:
            new_fav = not bool(row[0])
            cursor.execute("UPDATE jobs SET is_favorite = %s WHERE id = %s", (new_fav, job_id))
    else:
        cursor.execute("SELECT is_favorite FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            new_fav = not bool(row["is_favorite"])
            cursor.execute("UPDATE jobs SET is_favorite = ? WHERE id = ?", (int(new_fav), job_id))

    conn.commit()
    conn.close()
    return new_fav

def update_status(job_id: str, status: str) -> bool:
    """Met à jour le statut (a_postuler, postule)."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    if db_type == "postgres":
        cursor.execute("UPDATE jobs SET status_applied = %s WHERE id = %s", (status, job_id))
    else:
        cursor.execute("UPDATE jobs SET status_applied = ? WHERE id = ?", (status, job_id))

    conn.commit()
    conn.close()
    return True

def get_stats() -> dict:
    """Calcule les statistiques."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE days_left >= 0")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE days_left >= 0 AND days_left <= 3")
    urgent = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE is_favorite = true or is_favorite = 1")
    favorites = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM jobs WHERE status_applied = 'postule'")
    applied = cursor.fetchone()[0]

    conn.close()
    return {
        "total": total,
        "urgent": urgent,
        "favorites": favorites,
        "applied": applied
    }

def record_daily_history(run_date: str, total_jobs: int, new_jobs: int, urgent_jobs: int, sources: str = "emploi-public.ma + wadifa-info.com") -> bool:
    """Enregistre l'historique d'une exécution de scraping dans Supabase ou SQLite."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    try:
        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources)
                VALUES (%s, %s, %s, %s, %s)
            """, (run_date, total_jobs, new_jobs, urgent_jobs, sources))
        else:
            cursor.execute("""
                INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources)
                VALUES (?, ?, ?, ?, ?)
            """, (run_date, total_jobs, new_jobs, urgent_jobs, sources))
        conn.commit()
    except Exception as e:
        print(f"⚠️ Erreur enregistrement historique : {e}")
    finally:
        conn.close()
    return True

def get_daily_history(limit: int = 30) -> list[dict]:
    """Récupère l'historique des exécutions par jour."""
    init_db()
    conn, db_type = get_pg_connection()
    cursor = conn.cursor()

    history = []
    try:
        if db_type == "postgres":
            cursor.execute("""
                SELECT id, run_date, total_jobs, new_jobs, urgent_jobs, sources, created_at
                FROM daily_history
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
            rows = cursor.fetchall()
            for r in rows:
                c_at = r[6].strftime("%d/%m/%Y %H:%M") if hasattr(r[6], "strftime") else str(r[6])
                history.append({
                    "id": r[0],
                    "run_date": r[1],
                    "total_jobs": r[2],
                    "new_jobs": r[3],
                    "urgent_jobs": r[4],
                    "sources": r[5],
                    "created_at": c_at
                })
        else:
            cursor.execute("""
                SELECT id, run_date, total_jobs, new_jobs, urgent_jobs, sources, created_at
                FROM daily_history
                ORDER BY id DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            for r in rows:
                history.append({
                    "id": r["id"],
                    "run_date": r["run_date"],
                    "total_jobs": r["total_jobs"],
                    "new_jobs": r["new_jobs"],
                    "urgent_jobs": r["urgent_jobs"],
                    "sources": r["sources"],
                    "created_at": str(r["created_at"])
                })
    except Exception as e:
        print(f"⚠️ Erreur récupération historique : {e}")
    finally:
        conn.close()

    return history

