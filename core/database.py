import os
import json
import sqlite3
import secrets
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
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INT PRIMARY KEY,
                telegram_enabled BOOLEAN DEFAULT FALSE,
                telegram_bot_token VARCHAR(255),
                telegram_chat_id VARCHAR(100),
                email_alerts_enabled BOOLEAN DEFAULT TRUE,
                notification_email VARCHAR(255),
                google_sheet_url TEXT,
                alert_days TEXT DEFAULT '["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS alert_days TEXT DEFAULT '["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]';
            CREATE TABLE IF NOT EXISTS email_change_requests (
                id SERIAL PRIMARY KEY,
                user_id INT NOT NULL,
                new_email VARCHAR(255) NOT NULL,
                token VARCHAR(100) UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
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
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                telegram_enabled INTEGER DEFAULT 0,
                telegram_bot_token TEXT,
                telegram_chat_id TEXT,
                email_alerts_enabled INTEGER DEFAULT 1,
                notification_email TEXT,
                google_sheet_url TEXT,
                alert_days TEXT DEFAULT '["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS email_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                new_email TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)
            cursor.execute("PRAGMA table_info(user_settings);")
            cols = [col[1] for col in cursor.fetchall()]
            if "alert_days" not in cols:
                cursor.execute("ALTER TABLE user_settings ADD COLUMN alert_days TEXT DEFAULT '[\"lundi\",\"mardi\",\"mercredi\",\"jeudi\",\"vendredi\",\"samedi\",\"dimanche\"]';")

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
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            telegram_enabled INTEGER DEFAULT 0,
            telegram_bot_token TEXT,
            telegram_chat_id TEXT,
            email_alerts_enabled INTEGER DEFAULT 1,
            notification_email TEXT,
            google_sheet_url TEXT,
            alert_days TEXT DEFAULT '["lundi","mardi","mercredi","jeudi","vendredi","samedi","dimanche"]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS email_change_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            new_email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        s_cur = s_conn.cursor()
        s_cur.execute("PRAGMA table_info(user_settings);")
        s_cols = [col[1] for col in s_cur.fetchall()]
        if "alert_days" not in s_cols:
            s_conn.execute("ALTER TABLE user_settings ADD COLUMN alert_days TEXT DEFAULT '[\"lundi\",\"mardi\",\"mercredi\",\"jeudi\",\"vendredi\",\"samedi\",\"dimanche\"]';")
        s_conn.commit()
        s_conn.close()
    except Exception:
        pass

    _db_initialized = True

def authenticate_user(email: str, password: str) -> dict | None:
    """Authentifie un utilisateur depuis la base de données et vérifie le statut de validation email."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        user = None

        if db_type == "postgres":
            cursor.execute("SELECT id, email, password_hash, name, COALESCE(is_verified, FALSE) FROM users WHERE email = %s", (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                if check_password_hash(row[2], password):
                    is_verif = bool(row[4])
                    user = {
                        "id": row[0],
                        "email": row[1],
                        "name": row[3],
                        "is_verified": is_verif,
                        "pending_verification": not is_verif
                    }
        else:
            cursor.execute("SELECT id, email, password_hash, name, is_verified FROM users WHERE email = ?", (email.strip().lower(),))
            row = cursor.fetchone()
            if row:
                if check_password_hash(row["password_hash"], password):
                    is_verif = bool(row["is_verified"]) if "is_verified" in row.keys() else True
                    user = {
                        "id": row["id"],
                        "email": row["email"],
                        "name": row["name"],
                        "is_verified": is_verif,
                        "pending_verification": not is_verif
                    }

        # Fallback local SQLite si non trouvé sur postgres
        if not user and db_type == "postgres" and os.path.exists(SQLITE_PATH):
            try:
                s_conn = sqlite3.connect(SQLITE_PATH)
                s_conn.row_factory = sqlite3.Row
                s_cur = s_conn.cursor()
                s_cur.execute("SELECT id, email, password_hash, name, is_verified FROM users WHERE email = ?", (email.strip().lower(),))
                s_row = s_cur.fetchone()
                if s_row and check_password_hash(s_row["password_hash"], password):
                    is_verif = bool(s_row["is_verified"]) if "is_verified" in s_row.keys() else True
                    user = {
                        "id": s_row["id"],
                        "email": s_row["email"],
                        "name": s_row["name"],
                        "is_verified": is_verif,
                        "pending_verification": not is_verif
                    }
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

def register_user(name: str, email: str, password: str) -> tuple[bool, str, dict | None, str | None]:
    """Inscrit un nouvel utilisateur, bloque les emails temporaires et génère un code OTP."""
    from .security import is_disposable_email, generate_otp_code, get_otp_expiry
    from .notifier import send_otp_email

    email_clean = email.strip().lower()
    name_clean = name.strip()

    if not email_clean or "@" not in email_clean:
        return False, "Adresse email invalide.", None, None
    if len(password) < 6:
        return False, "Le mot de passe doit comporter au moins 6 caractères.", None, None

    # Blocage strict des emails temporaires ou jetables
    is_disp, disp_msg = is_disposable_email(email_clean)
    if is_disp:
        return False, disp_msg, None, None

    pw_hash = generate_password_hash(password)
    otp_code = generate_otp_code()
    otp_expires = get_otp_expiry(15)

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("SELECT id, is_verified FROM users WHERE email = %s", (email_clean,))
                existing = cursor.fetchone()
                if existing:
                    if existing[1]:
                        return False, "Un compte actif existe déjà avec cette adresse email. Veuillez vous connecter.", None, None
                    # Utilisateur non encore vérifié : régénération OTP
                    cursor.execute("""
                        UPDATE users SET name = %s, password_hash = %s, otp_code = %s, otp_expires_at = %s
                        WHERE id = %s RETURNING id, email, name;
                    """, (name_clean, pw_hash, otp_code, otp_expires, existing[0]))
                    row = cursor.fetchone()
                    user_dict = {"id": row[0], "email": row[1], "name": row[2]}
                else:
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, name, is_verified, otp_code, otp_expires_at)
                        VALUES (%s, %s, %s, FALSE, %s, %s)
                        RETURNING id, email, name;
                    """, (email_clean, pw_hash, name_clean, otp_code, otp_expires))
                    row = cursor.fetchone()
                    user_dict = {"id": row[0], "email": row[1], "name": row[2]}

                user_id = user_dict["id"]
                cursor.execute("""
                    INSERT INTO user_settings (user_id, notification_email)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                    VALUES (%s, '[]', '[]', '[]', '', FALSE)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id,))
                conn.commit()

            else:
                cursor.execute("SELECT id, is_verified FROM users WHERE email = ?", (email_clean,))
                existing = cursor.fetchone()
                if existing:
                    if bool(existing["is_verified"]):
                        return False, "Un compte actif existe déjà avec cette adresse email.", None, None
                    cursor.execute("""
                        UPDATE users SET name = ?, password_hash = ?, otp_code = ?, otp_expires_at = ?
                        WHERE id = ?;
                    """, (name_clean, pw_hash, otp_code, str(otp_expires), existing["id"]))
                    user_dict = {"id": existing["id"], "email": email_clean, "name": name_clean}
                else:
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, name, is_verified, otp_code, otp_expires_at)
                        VALUES (?, ?, ?, 0, ?, ?);
                    """, (email_clean, pw_hash, name_clean, otp_code, str(otp_expires)))
                    user_id = cursor.lastrowid
                    user_dict = {"id": user_id, "email": email_clean, "name": name_clean}

                user_id = user_dict["id"]
                cursor.execute("""
                    INSERT OR IGNORE INTO user_settings (user_id, notification_email)
                    VALUES (?, ?);
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT OR IGNORE INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                    VALUES (?, '[]', '[]', '[]', '', 0);
                """, (user_id,))
                conn.commit()

            # Envoi du code OTP par email
            send_otp_email(email_clean, otp_code, name_clean)
            return True, "Code de validation envoyé par email.", user_dict, otp_code

        except Exception as e:
            return False, f"Erreur lors de l'inscription : {e}", None, None


def verify_user_otp(email: str, entered_otp: str) -> tuple[bool, str, dict | None]:
    """Valide le code OTP saisi par l'utilisateur."""
    from datetime import datetime

    email_clean = (email or "").strip().lower()
    otp_clean = (entered_otp or "").strip()

    if not email_clean or not otp_clean:
        return False, "Veuillez renseigner votre email et le code reçu.", None

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT id, email, name, is_verified, otp_code, otp_expires_at
                    FROM users WHERE email = %s;
                """, (email_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Compte introuvable.", None

                user_id, u_email, u_name, is_verif, saved_otp, expires_at = row
                if is_verif:
                    return True, "Compte déjà vérifié.", {"id": user_id, "email": u_email, "name": u_name}

                if not saved_otp or saved_otp.strip() != otp_clean:
                    return False, "Code de vérification incorrect. Veuillez réessayer.", None

                if expires_at:
                    now_utc = datetime.utcnow()
                    exp_naive = expires_at.replace(tzinfo=None) if hasattr(expires_at, "replace") else expires_at
                    if now_utc > exp_naive:
                        return False, "Ce code a expiré. Veuillez cliquer sur 'Renvoyer le code'.", None

                cursor.execute("""
                    UPDATE users SET is_verified = TRUE, otp_code = NULL, otp_expires_at = NULL
                    WHERE id = %s;
                """, (user_id,))
                conn.commit()
                return True, "Adresse email validée avec succès !", {"id": user_id, "email": u_email, "name": u_name}
            else:
                cursor.execute("""
                    SELECT id, email, name, is_verified, otp_code, otp_expires_at
                    FROM users WHERE email = ?;
                """, (email_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Compte introuvable.", None

                if bool(row["is_verified"]):
                    return True, "Compte déjà vérifié.", {"id": row["id"], "email": row["email"], "name": row["name"]}

                if not row["otp_code"] or str(row["otp_code"]).strip() != otp_clean:
                    return False, "Code de vérification incorrect.", None

                cursor.execute("""
                    UPDATE users SET is_verified = 1, otp_code = NULL, otp_expires_at = NULL
                    WHERE id = ?;
                """, (row["id"],))
                conn.commit()
                return True, "Adresse email validée avec succès !", {"id": row["id"], "email": row["email"], "name": row["name"]}
        except Exception as e:
            return False, f"Erreur de validation : {e}", None


def resend_user_otp(email: str) -> tuple[bool, str]:
    """Génère et renvoie un nouveau code OTP par email."""
    from .security import generate_otp_code, get_otp_expiry
    from .notifier import send_otp_email

    email_clean = (email or "").strip().lower()
    if not email_clean:
        return False, "Adresse email manquante."

    new_otp = generate_otp_code()
    new_expiry = get_otp_expiry(15)

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("SELECT id, name, is_verified FROM users WHERE email = %s;", (email_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Aucun compte associé à cette adresse."
                if row[2]:
                    return False, "Ce compte est déjà validé. Vous pouvez vous connecter directement."

                user_id, u_name = row[0], row[1]
                cursor.execute("""
                    UPDATE users SET otp_code = %s, otp_expires_at = %s WHERE id = %s;
                """, (new_otp, new_expiry, user_id))
                conn.commit()
            else:
                cursor.execute("SELECT id, name, is_verified FROM users WHERE email = ?;", (email_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Aucun compte associé à cette adresse."
                if bool(row["is_verified"]):
                    return False, "Ce compte est déjà validé."

                user_id, u_name = row["id"], row["name"]
                cursor.execute("""
                    UPDATE users SET otp_code = ?, otp_expires_at = ? WHERE id = ?;
                """, (new_otp, str(new_expiry), user_id))
                conn.commit()

            send_otp_email(email_clean, new_otp, u_name)
            return True, "Un nouveau code de vérification a été envoyé sur votre boîte email."
        except Exception as e:
            return False, f"Erreur lors du renvoi : {e}"


def get_or_create_google_user(email: str, name: str = "", google_id: str = "") -> dict | None:
    """Récupère ou crée automatiquement un utilisateur authentifié via Google OAuth 2.0."""
    email_clean = (email or "").strip().lower()
    name_clean = (name or "").strip() or email_clean.split("@")[0]

    if not email_clean or "@" not in email_clean:
        return None

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        user_dict = None
        try:
            if db_type == "postgres":
                cursor.execute("SELECT id, email, name, is_verified FROM users WHERE email = %s", (email_clean,))
                row = cursor.fetchone()
                if row:
                    user_id = row[0]
                    cursor.execute("UPDATE users SET is_verified = TRUE WHERE id = %s", (user_id,))
                    user_dict = {"id": user_id, "email": row[1], "name": row[2] or name_clean, "is_verified": True}
                else:
                    random_pw = generate_password_hash(secrets.token_urlsafe(32))
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, name, is_verified)
                        VALUES (%s, %s, %s, TRUE)
                        RETURNING id, email, name;
                    """, (email_clean, random_pw, name_clean))
                    row = cursor.fetchone()
                    user_dict = {"id": row[0], "email": row[1], "name": row[2], "is_verified": True}

                user_id = user_dict["id"]
                cursor.execute("""
                    INSERT INTO user_settings (user_id, notification_email)
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                    VALUES (%s, '[]', '[]', '[]', '', FALSE)
                    ON CONFLICT (user_id) DO NOTHING;
                """, (user_id,))
                conn.commit()

            else:
                cursor.execute("SELECT id, email, name, is_verified FROM users WHERE email = ?", (email_clean,))
                row = cursor.fetchone()
                if row:
                    user_id = row["id"]
                    cursor.execute("UPDATE users SET is_verified = 1 WHERE id = ?", (user_id,))
                    user_dict = {"id": user_id, "email": row["email"], "name": row["name"] or name_clean, "is_verified": True}
                else:
                    random_pw = generate_password_hash(secrets.token_urlsafe(32))
                    cursor.execute("""
                        INSERT INTO users (email, password_hash, name, is_verified)
                        VALUES (?, ?, ?, 1);
                    """, (email_clean, random_pw, name_clean))
                    user_id = cursor.lastrowid
                    user_dict = {"id": user_id, "email": email_clean, "name": name_clean, "is_verified": True}

                cursor.execute("""
                    INSERT OR IGNORE INTO user_settings (user_id, notification_email)
                    VALUES (?, ?);
                """, (user_id, email_clean))

                cursor.execute("""
                    INSERT OR IGNORE INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                    VALUES (?, '[]', '[]', '[]', '', 0);
                """, (user_id,))
                conn.commit()

            return user_dict
        except Exception as e:
            print(f"⚠️ Erreur get_or_create_google_user : {e}")
            return None


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


def create_email_change_request(user_id: int, new_email: str) -> tuple[bool, str, str | None]:
    """Valide et enregistre une demande de changement d'email avec token sécurisé."""
    from .security import is_disposable_email
    from datetime import datetime, timedelta

    email_clean = (new_email or "").strip().lower()
    if not email_clean or "@" not in email_clean or "." not in email_clean:
        return False, "Adresse email invalide.", None

    is_disp, disp_msg = is_disposable_email(email_clean)
    if is_disp:
        return False, disp_msg, None

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("SELECT id, email FROM users WHERE email = %s", (email_clean,))
                existing = cursor.fetchone()
                if existing:
                    if existing[0] == user_id:
                        return False, "Vous utilisez déjà cette adresse email pour votre compte.", None
                    return False, "Cette adresse email est déjà associée à un autre compte.", None

                cursor.execute("DELETE FROM email_change_requests WHERE user_id = %s", (user_id,))

                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=24)
                cursor.execute("""
                    INSERT INTO email_change_requests (user_id, new_email, token, expires_at)
                    VALUES (%s, %s, %s, %s);
                """, (user_id, email_clean, token, expires_at))
                conn.commit()
            else:
                cursor.execute("SELECT id, email FROM users WHERE email = ?", (email_clean,))
                existing = cursor.fetchone()
                if existing:
                    if existing["id"] == user_id:
                        return False, "Vous utilisez déjà cette adresse email pour votre compte.", None
                    return False, "Cette adresse email est déjà associée à un autre compte.", None

                cursor.execute("DELETE FROM email_change_requests WHERE user_id = ?", (user_id,))

                token = secrets.token_urlsafe(32)
                expires_at = datetime.utcnow() + timedelta(hours=24)
                cursor.execute("""
                    INSERT INTO email_change_requests (user_id, new_email, token, expires_at)
                    VALUES (?, ?, ?, ?);
                """, (user_id, email_clean, token, str(expires_at)))
                conn.commit()

            return True, "Demande enregistrée avec succès.", token
        except Exception as e:
            return False, f"Erreur lors de la demande : {e}", None


def verify_and_apply_email_change(token: str) -> tuple[bool, str, dict | None]:
    """Vérifie le token de confirmation et met à jour l'email de l'utilisateur."""
    from datetime import datetime

    token_clean = (token or "").strip()
    if not token_clean:
        return False, "Jeton de validation manquant.", None

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT r.id, r.user_id, r.new_email, r.expires_at, u.name, u.email
                    FROM email_change_requests r
                    JOIN users u ON u.id = r.user_id
                    WHERE r.token = %s;
                """, (token_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Ce lien de confirmation est invalide ou a déjà été utilisé.", None

                req_id, user_id, new_email, expires_at, user_name, old_email = row

                now_utc = datetime.utcnow()
                exp_naive = expires_at.replace(tzinfo=None) if hasattr(expires_at, "replace") else expires_at
                if now_utc > exp_naive:
                    cursor.execute("DELETE FROM email_change_requests WHERE id = %s", (req_id,))
                    conn.commit()
                    return False, "Ce lien de confirmation a expiré. Veuillez faire une nouvelle demande depuis vos paramètres.", None

                cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (new_email, user_id))
                if cursor.fetchone():
                    cursor.execute("DELETE FROM email_change_requests WHERE id = %s", (req_id,))
                    conn.commit()
                    return False, "Cette adresse email a été réservée par un autre compte entre-temps.", None

                cursor.execute("""
                    UPDATE users SET email = %s, is_verified = TRUE WHERE id = %s;
                """, (new_email, user_id))

                cursor.execute("""
                    UPDATE user_settings SET notification_email = %s 
                    WHERE user_id = %s AND (notification_email = %s OR notification_email IS NULL);
                """, (new_email, user_id, old_email))

                cursor.execute("DELETE FROM email_change_requests WHERE user_id = %s", (user_id,))
                conn.commit()

                user_dict = {"id": user_id, "email": new_email, "name": user_name, "is_verified": True}
                return True, "Votre adresse email a été modifiée avec succès !", user_dict

            else:
                cursor.execute("""
                    SELECT r.id, r.user_id, r.new_email, r.expires_at, u.name, u.email
                    FROM email_change_requests r
                    JOIN users u ON u.id = r.user_id
                    WHERE r.token = ?;
                """, (token_clean,))
                row = cursor.fetchone()
                if not row:
                    return False, "Ce lien de confirmation est invalide ou a déjà été utilisé.", None

                req_id, user_id, new_email = row["id"], row["user_id"], row["new_email"]
                user_name, old_email = row["name"], row["email"]

                cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user_id))
                if cursor.fetchone():
                    cursor.execute("DELETE FROM email_change_requests WHERE id = ?", (req_id,))
                    conn.commit()
                    return False, "Cette adresse email est déjà prise.", None

                cursor.execute("UPDATE users SET email = ?, is_verified = 1 WHERE id = ?;", (new_email, user_id))
                cursor.execute("UPDATE user_settings SET notification_email = ? WHERE user_id = ? AND (notification_email = ? OR notification_email IS NULL);", (new_email, user_id, old_email))
                cursor.execute("DELETE FROM email_change_requests WHERE user_id = ?;", (user_id,))
                conn.commit()

                user_dict = {"id": user_id, "email": new_email, "name": user_name, "is_verified": True}
                return True, "Votre adresse email a été modifiée avec succès !", user_dict

        except Exception as e:
            return False, f"Erreur lors de la validation : {e}", None


def get_pending_email_change(user_id: int) -> dict | None:
    """Récupère la demande de changement d'email en cours pour un utilisateur."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("SELECT new_email, expires_at FROM email_change_requests WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if row:
                    return {"new_email": row[0], "expires_at": str(row[1])}
            else:
                cursor.execute("SELECT new_email, expires_at FROM email_change_requests WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row:
                    return {"new_email": row["new_email"], "expires_at": str(row["expires_at"])}
        except Exception:
            pass
    return None


def cancel_email_change_request(user_id: int) -> bool:
    """Annule toute demande de changement d'email en cours pour un utilisateur."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("DELETE FROM email_change_requests WHERE user_id = %s", (user_id,))
            else:
                cursor.execute("DELETE FROM email_change_requests WHERE user_id = ?", (user_id,))
            conn.commit()
            return True
        except Exception:
            return False


DEFAULT_ALERT_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

def get_user_settings(user_id: int) -> dict:
    """Récupère les paramètres de notification et intégrations d'un utilisateur."""
    default_settings = {
        "user_id": user_id,
        "telegram_enabled": False,
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "email_alerts_enabled": True,
        "notification_email": "",
        "google_sheet_url": "",
        "alert_days": list(DEFAULT_ALERT_DAYS)
    }
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, alert_days
                    FROM user_settings WHERE user_id = %s;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    days_raw = row[6]
                    try:
                        alert_days = json.loads(days_raw) if days_raw else list(DEFAULT_ALERT_DAYS)
                    except Exception:
                        alert_days = list(DEFAULT_ALERT_DAYS)

                    return {
                        "user_id": user_id,
                        "telegram_enabled": bool(row[0]),
                        "telegram_bot_token": row[1] or "",
                        "telegram_chat_id": row[2] or "",
                        "email_alerts_enabled": bool(row[3]),
                        "notification_email": row[4] or "",
                        "google_sheet_url": row[5] or "",
                        "alert_days": alert_days
                    }
            else:
                cursor.execute("""
                    SELECT telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, alert_days
                    FROM user_settings WHERE user_id = ?;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    days_raw = row["alert_days"] if "alert_days" in row.keys() else row[6]
                    try:
                        alert_days = json.loads(days_raw) if days_raw else list(DEFAULT_ALERT_DAYS)
                    except Exception:
                        alert_days = list(DEFAULT_ALERT_DAYS)

                    return {
                        "user_id": user_id,
                        "telegram_enabled": bool(row["telegram_enabled"]),
                        "telegram_bot_token": row["telegram_bot_token"] or "",
                        "telegram_chat_id": row["telegram_chat_id"] or "",
                        "email_alerts_enabled": bool(row["email_alerts_enabled"]),
                        "notification_email": row["notification_email"] or "",
                        "google_sheet_url": row["google_sheet_url"] or "",
                        "alert_days": alert_days
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
            days_val = settings.get("alert_days", DEFAULT_ALERT_DAYS)
            days_json = json.dumps(days_val) if isinstance(days_val, list) else str(days_val)

            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO user_settings (user_id, telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, alert_days, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        telegram_enabled = EXCLUDED.telegram_enabled,
                        telegram_bot_token = EXCLUDED.telegram_bot_token,
                        telegram_chat_id = EXCLUDED.telegram_chat_id,
                        email_alerts_enabled = EXCLUDED.email_alerts_enabled,
                        notification_email = EXCLUDED.notification_email,
                        google_sheet_url = EXCLUDED.google_sheet_url,
                        alert_days = EXCLUDED.alert_days,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, tg_en, tg_tok, tg_chat, em_en, em_mail, sheet_url, days_json))
            else:
                cursor.execute("""
                    INSERT INTO user_settings (user_id, telegram_enabled, telegram_bot_token, telegram_chat_id, email_alerts_enabled, notification_email, google_sheet_url, alert_days, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        telegram_enabled = excluded.telegram_enabled,
                        telegram_bot_token = excluded.telegram_bot_token,
                        telegram_chat_id = excluded.telegram_chat_id,
                        email_alerts_enabled = excluded.email_alerts_enabled,
                        notification_email = excluded.notification_email,
                        google_sheet_url = excluded.google_sheet_url,
                        alert_days = excluded.alert_days,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, int(tg_en), tg_tok, tg_chat, int(em_en), em_mail, sheet_url, days_json))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur update_user_settings: {e}")
            return False

def create_telegram_link_token(user_id: int) -> str:
    """Génère un token éphémère sécurisé pour lier le compte Telegram de l'utilisateur."""
    token = secrets.token_hex(16)
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
                INSERT INTO telegram_link_tokens (token, user_id, is_used)
                VALUES (%s, %s, FALSE)
                ON CONFLICT (token) DO NOTHING;
            """, (token, user_id))
        else:
            cursor.execute("""
                INSERT OR REPLACE INTO telegram_link_tokens (token, user_id, is_used)
                VALUES (?, ?, 0);
            """, (token, user_id))
        conn.commit()
    return token

def get_telegram_link_status(token: str) -> dict:
    """Vérifie si un token a été consommé et renvoie l'état de liaison."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
                SELECT t.user_id, t.is_used, s.telegram_chat_id, u.name
                FROM telegram_link_tokens t
                LEFT JOIN users u ON t.user_id = u.id
                LEFT JOIN user_settings s ON t.user_id = s.user_id
                WHERE t.token = %s;
            """, (token,))
            row = cursor.fetchone()
        else:
            cursor.execute("""
                SELECT t.user_id, t.is_used, s.telegram_chat_id, u.name
                FROM telegram_link_tokens t
                LEFT JOIN users u ON t.user_id = u.id
                LEFT JOIN user_settings s ON t.user_id = s.user_id
                WHERE t.token = ?;
            """, (token,))
            row = cursor.fetchone()

        if not row:
            return {"valid": False, "connected": False}
        
        user_id, is_used, chat_id, user_name = row[0], bool(row[1]), row[2], row[3]
        return {
            "valid": True,
            "connected": is_used and bool(chat_id),
            "chat_id": chat_id or "",
            "user_name": user_name or "",
            "user_id": user_id
        }

def consume_telegram_link_token(token: str, chat_id: str, telegram_name: str = "") -> tuple[bool, str]:
    """Valide le token envoyé lors du /start et associe automatiquement le chat_id à l'utilisateur."""
    token = (token or "").strip()
    chat_id = str(chat_id or "").strip()
    if not token or not chat_id:
        return False, "Token ou Chat ID manquant."

    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        if db_type == "postgres":
            cursor.execute("""
                SELECT t.user_id, t.is_used, u.name, u.email
                FROM telegram_link_tokens t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.token = %s;
            """, (token,))
            row = cursor.fetchone()
        else:
            cursor.execute("""
                SELECT t.user_id, t.is_used, u.name, u.email
                FROM telegram_link_tokens t
                LEFT JOIN users u ON t.user_id = u.id
                WHERE t.token = ?;
            """, (token,))
            row = cursor.fetchone()

        if not row:
            return False, "Lien d'activation invalide ou introuvable."

        user_id, is_used, user_name, user_email = row[0], bool(row[1]), row[2], row[3]
        if is_used:
            return True, user_name or "Candidat"

        if db_type == "postgres":
            cursor.execute("UPDATE telegram_link_tokens SET is_used = TRUE WHERE token = %s;", (token,))
            cursor.execute("""
                INSERT INTO user_settings (user_id, telegram_enabled, telegram_chat_id, updated_at)
                VALUES (%s, TRUE, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (user_id) DO UPDATE SET
                    telegram_enabled = TRUE,
                    telegram_chat_id = EXCLUDED.telegram_chat_id,
                    updated_at = CURRENT_TIMESTAMP;
            """, (user_id, chat_id))
        else:
            cursor.execute("UPDATE telegram_link_tokens SET is_used = 1 WHERE token = ?;", (token,))
            cursor.execute("""
                INSERT INTO user_settings (user_id, telegram_enabled, telegram_chat_id, updated_at)
                VALUES (?, 1, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    telegram_enabled = 1,
                    telegram_chat_id = excluded.telegram_chat_id,
                    updated_at = CURRENT_TIMESTAMP;
            """, (user_id, chat_id))

        conn.commit()
        return True, user_name or "Candidat"

def disconnect_user_telegram(user_id: int) -> bool:
    """Désactive et dissocie le compte Telegram d'un utilisateur."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    UPDATE user_settings
                    SET telegram_enabled = FALSE, telegram_chat_id = '', updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s;
                """, (user_id,))
            else:
                cursor.execute("""
                    UPDATE user_settings
                    SET telegram_enabled = 0, telegram_chat_id = '', updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?;
                """, (user_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur disconnect_user_telegram: {e}")
            return False

def get_user_preferences(user_id: int) -> dict:
    """Récupère les préférences de profils et mots-clés d'un utilisateur."""
    default_prefs = {
        "user_id": user_id,
        "target_profiles": [],
        "target_grades": [],
        "keywords": [],
        "education_level": "",
        "is_configured": False
    }
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            if db_type == "postgres":
                cursor.execute("""
                    SELECT target_profiles, target_grades, keywords, education_level, COALESCE(is_configured, FALSE)
                    FROM user_preferences WHERE user_id = %s;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    profiles = json.loads(row[0]) if row[0] else []
                    grades = json.loads(row[1]) if row[1] else []
                    kw = json.loads(row[2]) if row[2] else []
                    is_conf = bool(row[4]) or bool(profiles or grades or kw)
                    return {
                        "user_id": user_id,
                        "target_profiles": profiles if isinstance(profiles, list) else [],
                        "target_grades": grades if isinstance(grades, list) else [],
                        "keywords": kw if isinstance(kw, list) else [],
                        "education_level": row[3] or "",
                        "is_configured": is_conf
                    }
            else:
                cursor.execute("""
                    SELECT target_profiles, target_grades, keywords, education_level, is_configured
                    FROM user_preferences WHERE user_id = ?;
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    profiles = json.loads(row["target_profiles"]) if row["target_profiles"] else []
                    grades = json.loads(row["target_grades"]) if row["target_grades"] else []
                    kw = json.loads(row["keywords"]) if row["keywords"] else []
                    is_conf = bool(row["is_configured"]) if "is_configured" in row.keys() else bool(profiles or grades or kw)
                    return {
                        "user_id": user_id,
                        "target_profiles": profiles if isinstance(profiles, list) else [],
                        "target_grades": grades if isinstance(grades, list) else [],
                        "keywords": kw if isinstance(kw, list) else [],
                        "education_level": row["education_level"] or "",
                        "is_configured": is_conf
                    }
        except Exception as e:
            print(f"⚠️ Erreur get_user_preferences: {e}")
    return default_prefs

def update_user_preferences(user_id: int, prefs: dict) -> bool:
    """Met à jour les préférences de recherche et critères de profil et marque le profil comme configuré."""
    with get_db() as (conn, db_type):
        cursor = conn.cursor()
        try:
            target_profs = prefs.get("target_profiles", [])
            target_grds = prefs.get("target_grades", [])
            target_kws = prefs.get("keywords", [])
            edu = prefs.get("education_level", "").strip()

            profiles_json = json.dumps(target_profs, ensure_ascii=False)
            grades_json = json.dumps(target_grds, ensure_ascii=False)
            keywords_json = json.dumps(target_kws, ensure_ascii=False)
            is_conf = bool(target_profs or target_grds or target_kws or edu)

            if db_type == "postgres":
                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE SET
                        target_profiles = EXCLUDED.target_profiles,
                        target_grades = EXCLUDED.target_grades,
                        keywords = EXCLUDED.keywords,
                        education_level = EXCLUDED.education_level,
                        is_configured = EXCLUDED.is_configured,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, profiles_json, grades_json, keywords_json, edu, is_conf))
            else:
                cursor.execute("""
                    INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET
                        target_profiles = excluded.target_profiles,
                        target_grades = excluded.target_grades,
                        keywords = excluded.keywords,
                        education_level = excluded.education_level,
                        is_configured = excluded.is_configured,
                        updated_at = CURRENT_TIMESTAMP;
                """, (user_id, profiles_json, grades_json, keywords_json, edu, int(is_conf)))
            conn.commit()
            return True
        except Exception as e:
            print(f"⚠️ Erreur update_user_preferences: {e}")
            return False

def get_user_jobs(user_id: int | None, active_only: bool = True) -> list[dict]:
    """Récupère les concours strictement filtrés selon les critères configurés par l'utilisateur."""
    if not user_id:
        return []

    prefs = get_user_preferences(user_id)
    is_conf = prefs.get("is_configured", False)
    profs = prefs.get("target_profiles", [])
    grades = prefs.get("target_grades", [])
    kws = prefs.get("keywords", [])

    # Si l'utilisateur n'a pas encore configuré ses filtres, ne retourner aucun concours (0 par défaut)
    if not is_conf or (not profs and not grades and not kws):
        return []

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
            all_jobs = [dict(zip(columns, row)) for row in cursor.fetchall()]
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
            all_jobs = [dict(r) for r in cursor.fetchall()]

    from .notifier import filter_jobs_for_user_prefs
    return filter_jobs_for_user_prefs(all_jobs, prefs)


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
                        p.target_profiles, p.target_grades, p.keywords, p.education_level,
                        s.alert_days
                    FROM users u
                    LEFT JOIN user_settings s ON u.id = s.user_id
                    LEFT JOIN user_preferences p ON u.id = p.user_id
                    WHERE s.telegram_enabled = TRUE OR s.email_alerts_enabled = TRUE;
                """)
                for r in cursor.fetchall():
                    days_raw = r[13]
                    try:
                        alert_days = json.loads(days_raw) if days_raw else list(DEFAULT_ALERT_DAYS)
                    except Exception:
                        alert_days = list(DEFAULT_ALERT_DAYS)

                    users_list.append({
                        "id": r[0], "email": r[1], "name": r[2],
                        "telegram_enabled": bool(r[3]), "telegram_bot_token": r[4] or "", "telegram_chat_id": r[5] or "",
                        "email_alerts_enabled": bool(r[6]), "notification_email": r[7] or r[1], "google_sheet_url": r[8] or "",
                        "target_profiles": json.loads(r[9]) if r[9] else [],
                        "target_grades": json.loads(r[10]) if r[10] else [],
                        "keywords": json.loads(r[11]) if r[11] else [],
                        "education_level": r[12] or "",
                        "alert_days": alert_days
                    })
            else:
                cursor.execute("""
                    SELECT 
                        u.id, u.email, u.name,
                        s.telegram_enabled, s.telegram_bot_token, s.telegram_chat_id,
                        s.email_alerts_enabled, s.notification_email, s.google_sheet_url,
                        p.target_profiles, p.target_grades, p.keywords, p.education_level,
                        s.alert_days
                    FROM users u
                    LEFT JOIN user_settings s ON u.id = s.user_id
                    LEFT JOIN user_preferences p ON u.id = p.user_id
                    WHERE s.telegram_enabled = 1 OR s.email_alerts_enabled = 1;
                """)
                for r in cursor.fetchall():
                    days_raw = r[13]
                    try:
                        alert_days = json.loads(days_raw) if days_raw else list(DEFAULT_ALERT_DAYS)
                    except Exception:
                        alert_days = list(DEFAULT_ALERT_DAYS)

                    users_list.append({
                        "id": r[0], "email": r[1], "name": r[2],
                        "telegram_enabled": bool(r[3]), "telegram_bot_token": r[4] or "", "telegram_chat_id": r[5] or "",
                        "email_alerts_enabled": bool(r[6]), "notification_email": r[7] or r[1], "google_sheet_url": r[8] or "",
                        "target_profiles": json.loads(r[9]) if r[9] else [],
                        "target_grades": json.loads(r[10]) if r[10] else [],
                        "keywords": json.loads(r[11]) if r[11] else [],
                        "education_level": r[12] or "",
                        "alert_days": alert_days
                    })
        except Exception as e:
            print(f"⚠️ Erreur get_all_active_users_for_alert: {e}")
    return users_list
