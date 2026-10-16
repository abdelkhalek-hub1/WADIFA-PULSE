import os
import json
import sqlite3
import threading
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash
import config

# Paramètres de connexion PostgreSQL / Supabase
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_USER = os.getenv("DB_USER", "").strip()
DB_PASS = os.getenv("DB_PASS", "").strip()
DB_HOST = os.getenv("DB_HOST", "").strip()
DB_PORT = int(os.getenv("DB_PORT", "6543"))
DB_NAME = os.getenv("DB_NAME", "postgres").strip()

SQLITE_PATH = os.path.join(config.BASE_DIR, "wadifa_local.db")

_pg_pool = None
_pool_lock = threading.Lock()
_db_initialized = False

def get_pg_pool():
    """Initialise ou renvoie le pool de connexions PostgreSQL réutilisable."""
    global _pg_pool
    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                try:
                    import psycopg2
                    from psycopg2 import pool
                    
                    db_url = os.getenv("DATABASE_URL", "").strip()
                    if db_url:
                        _pg_pool = pool.ThreadedConnectionPool(
                            minconn=1,
                            maxconn=10,
                            dsn=db_url,
                            sslmode="require",
                            connect_timeout=8
                        )
                    elif DB_USER and DB_PASS and DB_HOST:
                        _pg_pool = pool.ThreadedConnectionPool(
                            minconn=1,
                            maxconn=10,
                            user=DB_USER,
                            password=DB_PASS,
                            host=DB_HOST,
                            port=DB_PORT,
                            database=DB_NAME,
                            sslmode="require",
                            connect_timeout=8
                        )
                    else:
                        _pg_pool = False
                except Exception as e:
                    print(f"Connexion Supabase indisponible ({e}), bascule vers SQLite local.")
                    _pg_pool = False
    return _pg_pool if _pg_pool is not False else None

@contextmanager
def get_db():
    """Fournit une connexion ultra-rapide via pool réutilisable (Supabase) ou fallback SQLite."""
    pg_pool = get_pg_pool()
    conn = None
    db_type = "sqlite"

    if pg_pool:
        try:
            conn = pg_pool.getconn()
            db_type = "postgres"
        except Exception:
            conn = None

    if conn is None:
        conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        db_type = "sqlite"

    try:
        yield conn, db_type
    finally:
        if db_type == "postgres" and pg_pool and conn:
            pg_pool.putconn(conn)
        elif db_type == "sqlite" and conn:
            conn.close()

def init_db(force: bool = False):
    """Initialise les tables Supabase / SQLite une seule fois au démarrage."""
    global _db_initialized
    if _db_initialized and not force:
        return

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
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
            CREATE TABLE IF NOT EXISTS daily_history (
                id SERIAL PRIMARY KEY,
                run_date VARCHAR(50) NOT NULL,
                total_jobs INT DEFAULT 0,
                new_jobs INT DEFAULT 0,
                urgent_jobs INT DEFAULT 0,
                sources VARCHAR(255),
                jobs_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        else:
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
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
            CREATE TABLE IF NOT EXISTS daily_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_date TEXT NOT NULL,
                total_jobs INTEGER DEFAULT 0,
                new_jobs INTEGER DEFAULT 0,
                urgent_jobs INTEGER DEFAULT 0,
                sources TEXT,
                jobs_snapshot TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
        conn.commit()

    # Initialiser aussi la base locale SQLite en miroir pour un accès instantané
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
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
        s_conn.commit()
        s_conn.close()
    except Exception:
        pass

    _db_initialized = True

def authenticate_user(email: str, password: str) -> dict | None:
    """Authentifie un utilisateur depuis la base de données sans rien coder en dur."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        user = None

        if db_type == "postgres":
            cursor.execute("SELECT id, email, password_hash, name FROM users WHERE email = %s", (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                if check_password_hash(row[2], password):
                    user = {"id": row[0], "email": row[1], "name": row[3]}
        else:
            cursor.execute("SELECT id, email, password_hash, name FROM users WHERE email = ?", (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                if check_password_hash(row["password_hash"], password):
                    user = {"id": row["id"], "email": row["email"], "name": row["name"]}

        # Fallback local SQLite si non trouvé sur postgres
        if not user and db_type == "postgres" and os.path.exists(SQLITE_PATH):
            try:
                s_conn = sqlite3.connect(SQLITE_PATH)
                s_conn.row_factory = sqlite3.Row
                s_cur = s_conn.cursor()
                s_cur.execute("SELECT id, email, password_hash, name FROM users WHERE email = ?", (email.strip().lower(),))
                s_row = s_cur.fetchone()
                if s_row and check_password_hash(s_row["password_hash"], password):
                    user = {"id": s_row["id"], "email": s_row["email"], "name": s_row["name"]}
                s_conn.close()
            except Exception:
                pass

        return user

def save_jobs(jobs: list[dict]):
    """Sauvegarde les concours dans Supabase et en local SQLite de manière optimisée."""
    if not jobs:
        return

    # 1. Sauvegarde locale SQLite immédiate (0ms)
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_cur = s_conn.cursor()
        for j in jobs:
            s_cur.execute("""
            INSERT INTO jobs (id, title, grade, organism, deadline_date, deadline_str, days_left, diplomas, specialties, link, source, date_found, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                days_left = excluded.days_left,
                deadline_str = excluded.deadline_str,
                deadline_date = excluded.deadline_date,
                diplomas = excluded.diplomas,
                specialties = excluded.specialties,
                source = excluded.source;
            """, (
                j.get("id"), j.get("title"), j.get("grade"), j.get("organism"),
                str(j.get("deadline_date")), j.get("deadline_str"), j.get("days_left"),
                j.get("diplomas"), j.get("specialties"), j.get("link"),
                j.get("source"), j.get("date_found"), j.get("description", "")
            ))
        s_conn.commit()
        s_conn.close()
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde SQLite : {e}")

    # 2. Synchronisation Supabase PostgreSQL
    try:
        with get_db() as (conn, db_type):
            if db_type == "postgres":
                cursor = conn.cursor()
                for j in jobs:
                    cursor.execute("""
                    INSERT INTO jobs (id, title, grade, organism, deadline_date, deadline_str, days_left, diplomas, specialties, link, source, date_found, description)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET
                        days_left = EXCLUDED.days_left,
                        deadline_str = EXCLUDED.deadline_str,
                        deadline_date = EXCLUDED.deadline_date,
                        diplomas = EXCLUDED.diplomas,
                        specialties = EXCLUDED.specialties,
                        source = EXCLUDED.source;
                    """, (
                        j.get("id"), j.get("title"), j.get("grade"), j.get("organism"),
                        str(j.get("deadline_date")), j.get("deadline_str"), j.get("days_left"),
                        j.get("diplomas"), j.get("specialties"), j.get("link"),
                        j.get("source"), j.get("date_found"), j.get("description", "")
                    ))
                conn.commit()
    except Exception as e:
        print(f"⚠️ Sync Supabase : {e}")

def get_all_jobs(active_only: bool = True) -> list[dict]:
    """Récupère les concours depuis Supabase / SQLite de façon ultra-rapide."""
    query = "SELECT * FROM jobs"
    if active_only:
        query += " WHERE days_left >= 0"
    query += " ORDER BY days_left ASC"

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        cursor.execute(query)
        jobs = []

        if db_type == "postgres":
            columns = [desc[0] for desc in cursor.description]
            for row in cursor.fetchall():
                jobs.append(dict(zip(columns, row)))
        else:
            for row in cursor.fetchall():
                jobs.append(dict(row))

        # Si postgres est vide mais SQLite a des données, fallback vers SQLite
        if not jobs and db_type == "postgres" and os.path.exists(SQLITE_PATH):
            try:
                s_conn = sqlite3.connect(SQLITE_PATH)
                s_conn.row_factory = sqlite3.Row
                s_cur = s_conn.cursor()
                s_cur.execute(query)
                for row in s_cur.fetchall():
                    jobs.append(dict(row))
                s_conn.close()
            except Exception:
                pass

        return jobs

def toggle_favorite(job_id: str) -> bool:
    """Bascule le statut favori de manière instantanée."""
    new_fav = False
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("SELECT is_favorite FROM jobs WHERE id = %s", (job_id,))
            row = cursor.fetchone()
            if row:
                new_fav = not bool(row[0])
                cursor.execute("UPDATE jobs SET is_favorite = %s WHERE id = %s", (new_fav, job_id))
                conn.commit()
        else:
            cursor.execute("SELECT is_favorite FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                new_fav = not bool(row["is_favorite"])
                cursor.execute("UPDATE jobs SET is_favorite = ? WHERE id = ?", (int(new_fav), job_id))
                conn.commit()

    # Mise à jour locale SQLite immédiate
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_conn.execute("UPDATE jobs SET is_favorite = ? WHERE id = ?", (int(new_fav), job_id))
        s_conn.commit()
        s_conn.close()
    except Exception:
        pass

    return new_fav

def update_status(job_id: str, status: str) -> bool:
    """Met à jour le statut (a_postuler, postule) instantanément."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("UPDATE jobs SET status_applied = %s WHERE id = %s", (status, job_id))
        else:
            cursor.execute("UPDATE jobs SET status_applied = ? WHERE id = ?", (status, job_id))
        conn.commit()

    # Mise à jour locale SQLite immédiate
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_conn.execute("UPDATE jobs SET status_applied = ? WHERE id = ?", (status, job_id))
        s_conn.commit()
        s_conn.close()
    except Exception:
        pass

    return True

def calculate_stats(jobs: list[dict]) -> dict:
    """Calcule instantanément (0ms) les KPIs en mémoire sans requêtes SQL superflues."""
    total = sum(1 for j in jobs if j.get("days_left", -1) >= 0)
    urgent = sum(1 for j in jobs if 0 <= j.get("days_left", 99) <= 3)
    favorites = sum(1 for j in jobs if j.get("is_favorite"))
    applied = sum(1 for j in jobs if j.get("status_applied") == "postule")
    return {
        "total": total,
        "urgent": urgent,
        "favorites": favorites,
        "applied": applied
    }

def get_stats() -> dict:
    """Récupère les statistiques calculées rapidement."""
    jobs = get_all_jobs(active_only=False)
    return calculate_stats(jobs)

def record_daily_history(run_date: str, total_jobs: int, new_jobs: int, urgent_jobs: int, sources: str = "emploi-public.ma + wadifa-info.com", jobs_snapshot: list[dict] = None) -> bool:
    """Enregistre l'historique d'une exécution de scraping dans Supabase et SQLite avec les détails complets des concours."""
    snapshot_json = json.dumps(jobs_snapshot or [], ensure_ascii=False, default=str)

    # 1. Enregistrement local
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_conn.execute("""
            INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources, jobs_snapshot)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (run_date, total_jobs, new_jobs, urgent_jobs, sources, snapshot_json))
        s_conn.commit()
        s_conn.close()
    except Exception as e:
        pass

    # 2. Enregistrement Supabase
    try:
        with get_db() as (conn, db_type):
            if db_type == "postgres":
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO daily_history (run_date, total_jobs, new_jobs, urgent_jobs, sources, jobs_snapshot)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (run_date, total_jobs, new_jobs, urgent_jobs, sources, snapshot_json))
                conn.commit()
    except Exception as e:
        pass

    return True

def get_daily_history(limit: int = 30) -> list[dict]:
    """Récupère l'historique des exécutions par jour avec le détail complet des concours trouvés."""
    history = []
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT id, run_date, total_jobs, new_jobs, urgent_jobs, sources, jobs_snapshot, created_at
                    FROM daily_history
                    ORDER BY id DESC
                    LIMIT %s
                """, (limit,))
                rows = cursor.fetchall()
                for r in rows:
                    c_at = r[7].strftime("%d/%m/%Y %H:%M") if hasattr(r[7], "strftime") else str(r[7])
                    try:
                        jobs_list = json.loads(r[6]) if r[6] else []
                    except Exception:
                        jobs_list = []
                    history.append({
                        "id": r[0],
                        "run_date": r[1],
                        "total_jobs": r[2],
                        "new_jobs": r[3],
                        "urgent_jobs": r[4],
                        "sources": r[5],
                        "jobs": jobs_list,
                        "created_at": c_at
                    })
            else:
                cursor.execute("""
                    SELECT id, run_date, total_jobs, new_jobs, urgent_jobs, sources, jobs_snapshot, created_at
                    FROM daily_history
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                for r in rows:
                    try:
                        jobs_list = json.loads(r["jobs_snapshot"]) if r["jobs_snapshot"] else []
                    except Exception:
                        jobs_list = []
                    history.append({
                        "id": r["id"],
                        "run_date": r["run_date"],
                        "total_jobs": r["total_jobs"],
                        "new_jobs": r["new_jobs"],
                        "urgent_jobs": r["urgent_jobs"],
                        "sources": r["sources"],
                        "jobs": jobs_list,
                        "created_at": str(r["created_at"])
                    })
        except Exception as e:
            print(f"⚠️ Erreur récupération historique : {e}")

    # Fallback local si la liste est vide
    if not history and os.path.exists(SQLITE_PATH):
        try:
            s_conn = sqlite3.connect(SQLITE_PATH)
            s_conn.row_factory = sqlite3.Row
            s_cur = s_conn.cursor()
            s_cur.execute("SELECT id, run_date, total_jobs, new_jobs, urgent_jobs, sources, jobs_snapshot, created_at FROM daily_history ORDER BY id DESC LIMIT ?", (limit,))
            for r in s_cur.fetchall():
                try:
                    jobs_list = json.loads(r["jobs_snapshot"]) if r["jobs_snapshot"] else []
                except Exception:
                    jobs_list = []
                history.append({
                    "id": r["id"],
                    "run_date": r["run_date"],
                    "total_jobs": r["total_jobs"],
                    "new_jobs": r["new_jobs"],
                    "urgent_jobs": r["urgent_jobs"],
                    "sources": r["sources"],
                    "jobs": jobs_list,
                    "created_at": str(r["created_at"])
                })
            s_conn.close()
        except Exception:
            pass

    return history
