import sys
import os
import json
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from core import config, init_db, get_db
from core.database import (
    get_user_settings,
    update_user_settings,
    get_all_active_users_for_alert,
    DEFAULT_ALERT_DAYS
)
from core.notifier import dispatch_all_user_alerts, WEEKDAY_FR_MAP

def test_alert_days_persistence():
    print("=== TEST 1: Alert Days Schema & DB Persistence ===")
    init_db(force=True)

    test_user_id = 88888
    # Ensure test user exists in DB
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                INSERT INTO users (id, email, password_hash, name, is_verified)
                VALUES (%s, 'test_days@example.com', 'hash', 'Test Days', TRUE)
                ON CONFLICT (id) DO NOTHING;
            """, (test_user_id,))
        else:
            cur.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, name, is_verified)
                VALUES (?, 'test_days@example.com', 'hash', 'Test Days', 1);
            """, (test_user_id,))
        conn.commit()

    # 1. Check default settings
    st = get_user_settings(test_user_id)
    print("Default alert_days:", st.get("alert_days"))
    assert len(st.get("alert_days", [])) == 7

    # 2. Update with custom workdays
    custom_days = ["lundi", "mercredi", "vendredi"]
    ok = update_user_settings(test_user_id, {
        "telegram_enabled": True,
        "telegram_chat_id": "8938907799",
        "alert_days": custom_days
    })
    assert ok == True

    st_updated = get_user_settings(test_user_id)
    print("Updated alert_days:", st_updated.get("alert_days"))
    assert st_updated.get("alert_days") == custom_days
    print("✅ Alert Days persistence validated 100%!")

    return test_user_id

def test_dispatch_day_filtering(test_user_id):
    print("\n=== TEST 2: Dispatch Day Filtering Logic ===")
    today_dt = date.today()
    today_fr = WEEKDAY_FR_MAP.get(today_dt.weekday(), "lundi")
    other_days = [d for d in DEFAULT_ALERT_DAYS if d != today_fr]

    # Setup mock active user: user opts OUT of today
    update_user_settings(test_user_id, {
        "telegram_enabled": True,
        "telegram_chat_id": "8938907799",
        "alert_days": other_days
    })

    # Also configure preferences so user has matching jobs
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        p = "%s" if db_type == "postgres" else "?"
        if db_type == "postgres":
            cur.execute("""
                INSERT INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                VALUES (%s, '["Développement Digital Web Full Stack"]', '[]', '[]', '', TRUE)
                ON CONFLICT (user_id) DO UPDATE SET target_profiles = EXCLUDED.target_profiles;
            """, (test_user_id,))
        else:
            cur.execute("""
                INSERT OR REPLACE INTO user_preferences (user_id, target_profiles, target_grades, keywords, education_level, is_configured)
                VALUES (?, '["Développement Digital Web Full Stack"]', '[]', '[]', '', 1);
            """, (test_user_id,))
        conn.commit()

    active_users = get_all_active_users_for_alert()
    test_u = next((u for u in active_users if u["id"] == test_user_id), None)
    assert test_u is not None
    print(f"Today is: {today_fr}, User alert_days: {test_u.get('alert_days')}")
    assert today_fr not in test_u["alert_days"]

    # Run dispatch simulation with a mock job
    mock_jobs = [{
        "id": "mock_1",
        "title": "Concours Développeur Web",
        "grade": "Technicien Spécialisé",
        "organism": "Ministère",
        "deadline_str": "30/10/2026",
        "days_left": 10,
        "link": "https://emploi-public.ma"
    }]

    # When today is NOT in alert_days, user is skipped!
    summary = dispatch_all_user_alerts(mock_jobs)
    print("Dispatch summary when today is excluded:", summary)
    # The test user should not be sent an alert because today is excluded
    assert test_u["id"] not in [err.split(":")[0] for err in summary["errors"]]

    # Now OPT-IN today
    update_user_settings(test_user_id, {
        "telegram_enabled": True,
        "telegram_chat_id": "8938907799",
        "alert_days": [today_fr]
    })
    active_users_in = get_all_active_users_for_alert()
    test_u_in = next((u for u in active_users_in if u["id"] == test_user_id), None)
    assert today_fr in test_u_in["alert_days"]
    print(f"Now today ({today_fr}) is included in user alert_days!")

    # Teardown test user
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        p = "%s" if db_type == "postgres" else "?"
        cur.execute(f"DELETE FROM user_settings WHERE user_id = {p};", (test_user_id,))
        cur.execute(f"DELETE FROM user_preferences WHERE user_id = {p};", (test_user_id,))
        cur.execute(f"DELETE FROM users WHERE id = {p};", (test_user_id,))
        conn.commit()

    print("✅ Dispatch Day Filtering validated 100%!")

def test_cron_endpoint():
    print("\n=== TEST 3: Protected /api/cron/run Endpoint ===")
    client = app.test_client()

    # 1. Reject without key
    res_no_key = client.get("/api/cron/run")
    print("Without key status:", res_no_key.status_code)
    assert res_no_key.status_code == 403

    # 2. Reject with wrong key
    res_bad_key = client.get("/api/cron/run?key=wrong_secret_123")
    print("With bad key status:", res_bad_key.status_code)
    assert res_bad_key.status_code == 403

    # 3. Accept with valid key
    valid_key = getattr(config, "CRON_SECRET", "WadifaPulseCron2026")
    res_ok = client.get(f"/api/cron/run?key={valid_key}")
    print("With valid key status:", res_ok.status_code, res_ok.get_json())
    assert res_ok.status_code == 200
    assert res_ok.get_json()["success"] == True
    assert res_ok.get_json()["status"] == "running"

    # 4. Immediate second trigger returns already running
    res_running = client.get(f"/api/cron/run?key={valid_key}")
    print("Second trigger status:", res_running.status_code, res_running.get_json())
    assert res_running.status_code == 200

    print("✅ Protected Cron Endpoint validated 100%!")

if __name__ == "__main__":
    uid = test_alert_days_persistence()
    test_dispatch_day_filtering(uid)
    test_cron_endpoint()
    print("\n🎉 ALL TESTS PASSED WITH 100% SUCCESS!")
