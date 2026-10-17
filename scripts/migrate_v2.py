import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database import get_db, SQLITE_PATH

def run_migration():
    print("🚀 Démarrage de la migration de schéma v2.0 (Multi-Tenant)...")

    pg_migration_sql = """
    -- 1. Table des utilisateurs (ajout colonnes si manquantes)
    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT TRUE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS verification_token VARCHAR(100);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS reset_token VARCHAR(100);

    -- 2. Paramètres de notifications par utilisateur
    CREATE TABLE IF NOT EXISTS user_settings (
        id SERIAL PRIMARY KEY,
        user_id INT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        telegram_enabled BOOLEAN DEFAULT FALSE,
        telegram_bot_token VARCHAR(255) DEFAULT '',
        telegram_chat_id VARCHAR(100) DEFAULT '',
        email_alerts_enabled BOOLEAN DEFAULT TRUE,
        notification_email VARCHAR(255) DEFAULT '',
        google_sheet_url VARCHAR(500) DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 3. Préférences de recherche et mots-clés par utilisateur
    CREATE TABLE IF NOT EXISTS user_preferences (
        id SERIAL PRIMARY KEY,
        user_id INT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        target_profiles TEXT DEFAULT '["Développement Digital Web Full Stack"]',
        target_grades TEXT DEFAULT '["Technicien Spécialisé (3ème grade)"]',
        keywords TEXT DEFAULT '["informatique", "web", "full stack"]',
        education_level VARCHAR(100) DEFAULT 'Bac+2 / Bac+3',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- 4. Interactions utilisateur avec les concours (Favoris et Postulés individuels)
    CREATE TABLE IF NOT EXISTS user_job_interactions (
        id SERIAL PRIMARY KEY,
        user_id INT REFERENCES users(id) ON DELETE CASCADE,
        job_id VARCHAR(255) REFERENCES jobs(id) ON DELETE CASCADE,
        is_favorite BOOLEAN DEFAULT FALSE,
        application_status VARCHAR(50) DEFAULT 'none',
        notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, job_id)
    );
    """

    sqlite_migration_sql = """
    CREATE TABLE IF NOT EXISTS user_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        telegram_enabled BOOLEAN DEFAULT 0,
        telegram_bot_token TEXT DEFAULT '',
        telegram_chat_id TEXT DEFAULT '',
        email_alerts_enabled BOOLEAN DEFAULT 1,
        notification_email TEXT DEFAULT '',
        google_sheet_url TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        target_profiles TEXT DEFAULT '["Développement Digital Web Full Stack"]',
        target_grades TEXT DEFAULT '["Technicien Spécialisé (3ème grade)"]',
        keywords TEXT DEFAULT '["informatique", "web", "full stack"]',
        education_level TEXT DEFAULT 'Bac+2 / Bac+3',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS user_job_interactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
        job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
        is_favorite BOOLEAN DEFAULT 0,
        application_status TEXT DEFAULT 'none',
        notes TEXT DEFAULT '',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, job_id)
    );
    """

    # 1. Migration PostgreSQL / Supabase
    try:
        with get_db() as (conn, db_type):
            if db_type == "postgres":
                cur = conn.cursor()
                cur.execute(pg_migration_sql)
                conn.commit()
                cur.close()
                print("✅ Tables Supabase PostgreSQL créées et vérifiées avec succès !")
    except Exception as e:
        print(f"⚠️ Erreur lors de la migration PostgreSQL : {e}")

    # 2. Migration SQLite locale
    try:
        conn = sqlite3.connect(SQLITE_PATH)
        cur = conn.cursor()
        # Ajouter colonnes users si manquantes
        try:
            cur.execute("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT 1;")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE users ADD COLUMN verification_token TEXT;")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE users ADD COLUMN reset_token TEXT;")
        except Exception:
            pass

        cur.executescript(sqlite_migration_sql)
        conn.commit()
        conn.close()
        print("✅ Tables SQLite locales créées et vérifiées avec succès !")
    except Exception as e:
        print(f"⚠️ Erreur lors de la migration SQLite : {e}")

    print("🎉 Migration v2.0 terminée avec succès.")

if __name__ == "__main__":
    run_migration()
