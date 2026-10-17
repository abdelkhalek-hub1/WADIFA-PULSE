import os
import sys
import sqlite3

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.database import get_db, SQLITE_PATH

def run_migration():
    print("🚀 Migration OTP et Onboarding Personnalisé...")

    pg_sql = """
    -- 1. Colonnes OTP dans users
    ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_code VARCHAR(10);
    ALTER TABLE users ADD COLUMN IF NOT EXISTS otp_expires_at TIMESTAMP;

    -- 2. Colonne is_configured dans user_preferences
    ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS is_configured BOOLEAN DEFAULT FALSE;
    """

    sqlite_sql = """
    ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0;
    ALTER TABLE users ADD COLUMN otp_code TEXT;
    ALTER TABLE users ADD COLUMN otp_expires_at TEXT;
    """

    # PostgreSQL / Supabase
    try:
        with get_db() as (conn, db_type):
            if db_type == "postgres":
                cur = conn.cursor()
                cur.execute(pg_sql)
                conn.commit()
                cur.close()
                print("✅ Colonnes OTP et is_configured ajoutées sur Supabase PostgreSQL !")
    except Exception as e:
        print(f"⚠️ Erreur PostgreSQL : {e}")

    # SQLite local
    try:
        s_conn = sqlite3.connect(SQLITE_PATH)
        s_cur = s_conn.cursor()
        for col_def in [
            ("users", "is_verified", "INTEGER DEFAULT 0"),
            ("users", "otp_code", "TEXT"),
            ("users", "otp_expires_at", "TEXT"),
            ("user_preferences", "is_configured", "INTEGER DEFAULT 0"),
        ]:
            try:
                s_cur.execute(f"ALTER TABLE {col_def[0]} ADD COLUMN {col_def[1]} {col_def[2]};")
            except Exception:
                pass
        s_conn.commit()
        s_conn.close()
        print("✅ Base SQLite locale synchronisée !")
    except Exception as e:
        print(f"⚠️ Erreur SQLite : {e}")

    print("🏁 Migration terminée avec succès.")

if __name__ == "__main__":
    run_migration()
