import os
import json
import sqlite3
import threading
from contextlib import contextmanager
from werkzeug.security import generate_password_hash, check_password_hash
from . import config

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


# ==========================================
# Fonctions Multi-Tenant v2.0 (Users, Settings & Targets)
# ==========================================

def register_user(name: str, email: str, password: str) -> tuple[bool, str, dict | None]:
    """Inscrit un nouvel utilisateur et initialise ses paramètres par défaut."""
    email_clean = email.strip().lower()
    name_clean = name.strip()

    if not email_clean or "@" not in email_clean:
        return False, "Adresse email invalide.", None
    if len(password) < 6:
        return False, "Le mot de passe doit comporter au moins 6 caractères.", None

    pw_hash = generate_password_hash(password)

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("SELECT id FROM users WHERE email = %s", (email_clean,))
                if cursor.fetchone():
                    return False, "Un compte existe déjà avec cette adresse email.", None

                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, is_verified)
                    VALUES (%s, %s, %s, TRUE)
                    RETURNING id, email, name, created_at;
                """, (email_clean, pw_hash, name_clean))
                row = cursor.fetchone()
                user_id = row[0]
                user_dict = {"id": user_id, "email": row[1], "name": row[2]}

                cursor.execute("""
                    INSERT INTO user_settings (user_id, notification_email)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT INTO user_preferences (user_id)
                    VALUES (%s)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id,))

                conn.commit()
                return True, "Compte créé avec succès.", user_dict
            else:
                cursor.execute("SELECT id FROM users WHERE email = ?", (email_clean,))
                if cursor.fetchone():
                    return False, "Un compte existe déjà avec cette adresse email.", None

                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, is_verified)
                    VALUES (?, ?, ?, 1);
                """, (email_clean, pw_hash, name_clean))
                user_id = cursor.lastrowid
                user_dict = {"id": user_id, "email": email_clean, "name": name_clean}

                cursor.execute("""
                    INSERT OR IGNORE INTO user_settings (user_id, notification_email)
                    VALUES (?, ?);
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT OR IGNORE INTO user_preferences (user_id)
                    VALUES (?);
                """, (user_id,))

                conn.commit()
                return True, "Compte créé avec succès.", user_dict
        except Exception as e:
            return False, f"Erreur lors de l'inscription : {e}", None

def update_user_account(user_id: int, name: str, new_password: str = None) -> tuple[bool, str]:
    """Met à jour le nom et optionnellement le mot de passe d'un utilisateur."""
    name_clean = (name or "").strip()
    if not name_clean:
        return False, "Le nom ne peut pas être vide."
    
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if new_password and len(new_password) >= 6:
                pw_hash = generate_password_hash(new_password)
                if db_type == "postgres":
                    cursor.execute("""
                        UPDATE users SET name = %s, password_hash = %s
                        WHERE id = %s;
                    """, (name_clean, pw_hash, user_id))
                else:
                    cursor.execute("""
                        UPDATE users SET name = ?, password_hash = ?
                        WHERE id = ?;
                    """, (name_clean, pw_hash, user_id))
            else:
                if db_type == "postgres":
                    cursor.execute("""
                        UPDATE users SET name = %s
                        WHERE id = %s;
                    """, (name_clean, user_id))
                else:
                    cursor.execute("""
                        UPDATE users SET name = ?
                        WHERE id = ?;
                    """, (name_clean, user_id))
            conn.commit()
            return True, "Profil mis à jour avec succès."
        except Exception as e:
            return False, f"Erreur lors de la mise à jour : {e}"


def get_user_settings(user_id: int) -> dict:
    """Récupère les paramètres de notification et intégrations d'un utilisateur."""
    default_settings = {
        "user_id": user_id,
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "email_alerts_enabled": True,
        "notification_email": "",
        "google_sheet_url": ""
    }
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url
                    FROM user_settings WHERE user_id = %s;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": user_id,
                        "telegram_enabled": bool(row[0]),
                        "telegram_bot_token": row[1] or "",
                        "telegram_chat_id": row[2] or "",
                        "email_alerts_enabled": bool(row[3]),
                        "notification_email": row[4] or "",
                        "google_sheet_url": row[5] or ""
                    }
            else:
                cursor.execute("""
                    SELECT telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url
                    FROM user_settings WHERE user_id = ?;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": user_id,
                        "telegram_enabled": bool(row["telegram_enabled"]),
                        "telegram_bot_token": row["telegram_bot_token"] or "",
                        "telegram_chat_id": row["telegram_chat_id"] or "",
                        "email_alerts_enabled": bool(row["email_alerts_enabled"]),
                        "notification_email": row["notification_email"] or "",
                        "google_sheet_url": row["google_sheet_url"] or ""
                    }
        except Exception as e:
            print(f"⚠️ Erreur get_user_settings: {e}")
    return default_settings

def update_user_settings(user_id: int, settings: dict) -> bool:
    """Met à jour les paramètres d'alerte et d'intégration de l'utilisateur."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            tg_en = bool(settings.get("telegram_enabled", False))
            tg_tok = settings.get("telegram_bot_token", "").strip()
            tg_chat = settings.get("telegram_chat_id", "").strip()
            em_en = bool(settings.get("email_alerts_enabled", True))
            em_mail = settings.get("notification_email", "").strip()
            sheet_url = settings.get("google_sheet_url", "").strip()

            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO user_settings (user_id, telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        telegram_enabled = EXCLUDED.telegram_enabled,
                        telegram_bot_token = EXCLUDED.telegram_bot_token,
                        telegram_chat_id = EXCLUDED.telegram_chat_id,
                        email_alerts_enabled = EXCLUDED.email_alerts_enabled,
                        notification_email = EXCLUDED.notification_email,
                        google_sheet_url = EXCLUDED.google_sheet_url,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, tg_en, tg_tok, tg_chat, em_en, em_mail, sheet_url))
            else:
                cursor.execute("""
                    INSERT INTO user_settings (user_id, telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        telegram_enabled = excluded.telegram_enabled,
                        telegram_bot_token = excluded.telegram_bot_token,
                        telegram_chat_id = excluded.telegram_chat_id,
                        email_alerts_enabled = excluded.email_alerts_enabled,
                        notification_email = excluded.notification_email,
                        google_sheet_url = excluded.google_sheet_url,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, int(tg_en), tg_tok, tg_chat, int(em_en), em_mail, sheet_url))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur update_user_settings: {e}")
            return False

def get_user_preferences(user_id: int) -> dict:
    """Récupère les préférences de profils et mots-clés d'un utilisateur."""
    default_prefs = {
        "user_id": user_id,
        "target_profiles": ["Développement Digital Web Full Stack"],
        "target_grades": ["Technicien Spécialisé (3ème grade)"],
        "keywords": ["informatique", "web", "full stack"],
        "education_level": "Bac+2 / Bac+3"
    }
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT target_profiles, target_grades, keywords, education_level
                    FROM user_preferences WHERE user_id = %s;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    profiles = json.loads(row[0]) if row[0] else default_prefs["target_profiles"]
                    grades = json.loads(row[1]) if row[1] else default_prefs["target_grades"]
                    kw = json.loads(row[2]) if row[2] else default_prefs["keywords"]
                    return {
                        "user_id": user_id,
                        "target_profiles": profiles if isinstance(profiles, list) else [profiles],
                        "target_grades": grades if isinstance(grades, list) else [grades],
                        "keywords": kw if isinstance(kw, list) else [kw],
                        "education_level": row[3] or "Bac+2 / Bac+3"
                    }
            else:
                cursor.execute("""
                    SELECT target_profiles, target_grades, keywords, education_level
                    FROM user_preferences WHERE user_id = ?;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    profiles = json.loads(row["target_profiles"]) if row["target_profiles"] else default_prefs["target_profiles"]
                    grades = json.loads(row["target_grades"]) if row["target_grades"] else default_prefs["target_grades"]
                    kw = json.loads(row["keywords"]) if row["keywords"] else default_prefs["keywords"]
                    return {
                        "user_id": user_id,
                        "target_profiles": profiles if isinstance(profiles, list) else [profiles],
                        "target_grades": grades if isinstance(grades, list) else [grades],
                        "keywords": kw if isinstance(kw, list) else [kw],
                        "education_level": row["education_level"] or "Bac+2 / Bac+3"
                    }
        except Exception as e:
            print(f"⚠️ Erreur get_user_preferences: {e}")
    return default_prefs

def update_user_preferences(user_id: int, prefs: dict) -> bool:
    """Met à jour les préférences de recherche et critères de profil."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            profiles_json = json.dumps(prefs.get("target_profiles", ["Développement Digital Web Full Stack"]), ensure_ascii=False)
            grades_json = json.dumps(prefs.get("target_grades", ["Technicien Spécialisé (3ème grade)"]), ensure_ascii=False)
            keywords_json = json.dumps(prefs.get("keywords", ["informatique", "web"]), ensure_ascii=False)
            edu = prefs.get("education_level", "Bac+2 / Bac+3").strip()

            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, updated_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        target_profiles = EXCLUDED.target_profiles,
                        target_grades = EXCLUDED.target_grades,
                        keywords = EXCLUDED.keywords,
                        education_level = EXCLUDED.education_level,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, profiles_json, grades_json, keywords_json, edu))
            else:
                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        target_profiles = excluded.target_profiles,
                        target_grades = excluded.target_grades,
                        keywords = excluded.keywords,
                        education_level = excluded.education_level,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, profiles_json, grades_json, keywords_json, edu))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur update_user_preferences: {e}")
            return False

def get_user_jobs(user_id: int | None, active_only: bool = True) -> list[dict]:
    """Récupère les concours avec le statut Favoris et Postulé spécifique à cet utilisateur."""
    if not user_id:
        return get_all_jobs(active_only=active_only)

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            query = """
                SELECT 
                    j.id, j.title, j.grade, j.organism, j.deadline_date, j.deadline_str, j.days_left,
                    j.diplomas, j.specialties, j.link, j.source, j.date_found, j.description,
                    COALESCE(ui.is_favorite, FALSE) as is_favorite,
                    COALESCE(ui.application_status, 'a_postuler') as status_applied,
                    j.created_at
                FROM jobs j
                LEFT JOIN user_job_interactions ui ON j.id = ui.job_id AND ui.user_id = %s
            """
            if active_only:
                query += " WHERE j.days_left >= 0"
            query += " ORDER BY j.days_left ASC"

            cursor.execute(query, (user_id,))
            columns = [desc[0] for desc in cursor.description]
            jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return jobs
        else:
            query = """
                SELECT 
                    j.id, j.title, j.grade, j.organism, j.deadline_date, j.deadline_str, j.days_left,
                    j.diplomas, j.specialties, j.link, j.source, j.date_found, j.description,
                    COALESCE(ui.is_favorite, 0) as is_favorite,
                    COALESCE(ui.application_status, 'a_postuler') as status_applied,
                    j.created_at
                FROM jobs j
                LEFT JOIN user_job_interactions ui ON j.id = ui.job_id AND ui.user_id = ?
            """
            if active_only:
                query += " WHERE j.days_left >= 0"
            query += " ORDER BY j.days_left ASC"

            cursor.execute(query, (user_id,))
            jobs = [dict(r) for r in cursor.fetchall()]
            return jobs

def toggle_user_favorite(user_id: int, job_id: str) -> bool:
    """Bascule le statut favori d'un concours pour un utilisateur spécifique."""
    new_fav = False
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT is_favorite FROM user_job_interactions 
                    WHERE user_id = %s AND job_id = %s;
                """, (user_id, job_id))
                row = cursor.fetchone()
                if row:
                    new_fav = not bool(row[0])
                    cursor.execute("""
                        UPDATE user_job_interactions SET is_favorite = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = %s AND job_id = %s;
                    """, (new_fav, user_id, job_id))
                else:
                    new_fav = True
                    cursor.execute("""
                        INSERT INTO user_job_interactions (user_id, job_id, is_favorite)
                        VALUES (%s, %s, TRUE);
                    """, (user_id, job_id))
            else:
                cursor.execute("""
                    SELECT is_favorite FROM user_job_interactions 
                    WHERE user_id = ? AND job_id = ?;
                """, (user_id, job_id))
                row = cursor.fetchone()
                if row:
                    new_fav = not bool(row["is_favorite"])
                    cursor.execute("""
                        UPDATE user_job_interactions SET is_favorite = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ? AND job_id = ?;
                    """, (int(new_fav), user_id, job_id))
                else:
                    new_fav = True
                    cursor.execute("""
                        INSERT INTO user_job_interactions (user_id, job_id, is_favorite)
                        VALUES (?, ?, 1);
                    """, (user_id, job_id))
            conn.commit()
            return new_fav
        except Exception as e:
            print(f"⚠️ Erreur toggle_user_favorite: {e}")
            return False

def update_user_job_status(user_id: int, job_id: str, status: str) -> bool:
    """Met à jour le statut (a_postuler, postule) pour un utilisateur spécifique."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO user_job_interactions (user_id, job_id, application_status, updated_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id, job_id) DO UPDATE SET
                        application_status = EXCLUDED.application_status,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, job_id, status))
            else:
                cursor.execute("""
                    INSERT INTO user_job_interactions (user_id, job_id, application_status, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id, job_id) DO UPDATE SET
                        application_status = excluded.application_status,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, job_id, status))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur update_user_job_status: {e}")
            return False

def get_all_active_users_for_alert() -> list[dict]:
    """Récupère tous les utilisateurs ayant activé les alertes avec leurs préférences."""
    users_list = []
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT 
                        u.id, u.email, u.name,
                        s.telegram_enabled, s.telegram_bot_token, s.telegram_chat_id,
                        s.email_alerts_enabled, s.notification_email, s.google_sheet_url,
                        p.target_profiles, p.target_grades, p.keywords, p.education_level
                    FROM users u
                    LEFT JOIN user_settings s ON u.id = s.user_id
                    LEFT JOIN user_preferences p ON u.id = p.user_id
                    WHERE s.telegram_enabled = TRUE OR s.email_alerts_enabled = TRUE;
                """)
                for r in cursor.fetchall():
                    users_list.append({
                        "id": r[0], "email": r[1], "name": r[2],
                        "telegram_enabled": bool(r[3]), "telegram_bot_token": r[4] or "", "telegram_chat_id": r[5] or "",
                        "email_alerts_enabled": bool(r[6]), "notification_email": r[7] or r[1], "google_sheet_url": r[8] or "",
                        "target_profiles": json.loads(r[9]) if r[9] else [],
                        "target_grades": json.loads(r[10]) if r[10] else [],
                        "keywords": json.loads(r[11]) if r[11] else [],
                        "education_level": r[12] or ""
                    })
        except Exception as e:
            print(f"⚠️ Erreur get_all_active_users_for_alert: {e}")
    return users_list
