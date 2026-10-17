import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from core.database import (
    create_telegram_link_token,
    get_telegram_link_status,
    consume_telegram_link_token,
    disconnect_user_telegram,
    get_db,
    get_user_settings
)
from core.notifier import process_telegram_update, BILINGUAL_PROFILE_SYNONYMS

def test_telegram_flow():
    print("=== TEST 1: Profile Synonyms Expansion ===")
    assert "agriculture" in BILINGUAL_PROFILE_SYNONYMS
    agri_syns = BILINGUAL_PROFILE_SYNONYMS["agriculture"]
    print("Agriculture synonyms:", agri_syns[:5])
    assert "فلاحة" in agri_syns
    assert "santé" in BILINGUAL_PROFILE_SYNONYMS
    assert "génie civil" in BILINGUAL_PROFILE_SYNONYMS
    assert "électromécanique" in BILINGUAL_PROFILE_SYNONYMS
    assert "éducation" in BILINGUAL_PROFILE_SYNONYMS

    from core.notifier import filter_jobs_for_user_prefs
    mock_jobs = [
        {"title": "مباراة توظيف تقنيين من الدرجة الثالثة في الفلاحة والصيد البحري", "grade": "تقني من الدرجة الثالثة", "organism": "وزارة الفلاحة", "days_left": 10},
        {"title": "Concours de recrutement Développeur Web Full Stack", "grade": "Technicien Spécialisé", "organism": "Ministère", "days_left": 5}
    ]
    matched = filter_jobs_for_user_prefs(mock_jobs, {"target_profiles": ["Agriculture, Eaux & Forêts & Halieutique"]})
    print(f"Matched agriculture jobs count: {len(matched)}")
    assert len(matched) == 1
    assert "الفلاحة" in matched[0]["title"]
    print("✅ All new sector synonyms and Arabic filtering validated successfully!")

    print("\n=== TEST 2: Token Creation & Consumption in DB ===")
    test_user_id = 99999

    # Create temporary user for foreign key safety
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                INSERT INTO users (id, email, password_hash, name, is_verified)
                VALUES (%s, 'test_telegram@example.com', 'hash', 'Testeur Wadifa', TRUE)
                ON CONFLICT (id) DO NOTHING;
            """, (test_user_id,))
        else:
            cur.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, name, is_verified)
                VALUES (?, 'test_telegram@example.com', 'hash', 'Testeur Wadifa', 1);
            """, (test_user_id,))
        conn.commit()

    token = create_telegram_link_token(test_user_id)
    print(f"Generated token: {token}")
    assert len(token) == 32

    status = get_telegram_link_status(token)
    print(f"Initial status: {status}")
    assert status["valid"] == True
    assert status["connected"] == False
    assert status["user_id"] == test_user_id

    # Test Webhook / Update processor simulation
    simulated_update = {
        "update_id": 10001,
        "message": {
            "message_id": 42,
            "from": {
                "id": 8938907799,
                "is_bot": False,
                "first_name": "Abdelkhalek",
                "username": "abdelkhalek_test"
            },
            "chat": {
                "id": 8938907799,
                "first_name": "Abdelkhalek",
                "type": "private"
            },
            "date": 1729000000,
            "text": f"/start wp_{token}"
        }
    }

    ok, reason = process_telegram_update(simulated_update)
    print(f"Process update result: ok={ok}, reason={reason}")
    assert ok == True

    # Status check after consumption
    post_status = get_telegram_link_status(token)
    print(f"Post-consumption status: {post_status}")
    assert post_status["connected"] == True
    assert post_status["chat_id"] == "8938907799"

    # Check that user settings were updated
    settings = get_user_settings(test_user_id)
    print(f"User {test_user_id} settings: telegram_chat_id={settings.get('telegram_chat_id')}, enabled={settings.get('telegram_enabled')}")
    assert str(settings.get("telegram_chat_id")) == "8938907799"
    assert settings.get("telegram_enabled") == True

    # Test disconnect
    dc_res = disconnect_user_telegram(test_user_id)
    assert dc_res == True
    settings_after = get_user_settings(test_user_id)
    print(f"After disconnect: telegram_chat_id={settings_after.get('telegram_chat_id')}, enabled={settings_after.get('telegram_enabled')}")
    assert settings_after.get("telegram_chat_id") in ("", None)
    assert not bool(settings_after.get("telegram_enabled"))

    # Cleanup test token and settings and user
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        p = "%s" if db_type == "postgres" else "?"
        cur.execute(f"DELETE FROM telegram_link_tokens WHERE user_id = {p};", (test_user_id,))
        cur.execute(f"DELETE FROM user_settings WHERE user_id = {p};", (test_user_id,))
        cur.execute(f"DELETE FROM users WHERE id = {p};", (test_user_id,))
        conn.commit()

    print("✅ Full Telegram linking lifecycle passed 100%!")

def test_api_endpoints():
    print("\n=== TEST 3: HTTP API Endpoints ===")
    client = app.test_client()

    api_uid = 88889
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        if db_type == "postgres":
            cur.execute("""
                INSERT INTO users (id, email, password_hash, name, is_verified)
                VALUES (%s, 'test_api@example.com', 'hash', 'API Tester', TRUE)
                ON CONFLICT (id) DO NOTHING;
            """, (api_uid,))
        else:
            cur.execute("""
                INSERT OR IGNORE INTO users (id, email, password_hash, name, is_verified)
                VALUES (?, 'test_api@example.com', 'hash', 'API Tester', 1);
            """, (api_uid,))
        conn.commit()

    # Create session mock
    with client.session_transaction() as sess:
        sess["user"] = {"id": api_uid, "email": "test_api@example.com", "name": "API Tester"}

    # Test link-init
    res = client.post("/api/user/telegram/link-init")
    print("link-init status:", res.status_code)
    data = res.get_json()
    assert data["success"] == True
    assert "deep_link" in data
    assert "token" in data
    print("Generated Deep Link:", data["deep_link"])
    token = data["token"]

    # Test link-status before start
    res_status = client.get(f"/api/user/telegram/link-status?token={token}")
    data_status = res_status.get_json()
    print("link-status response:", data_status)
    assert data_status["success"] == True
    assert data_status["connected"] == False

    # Simulate webhook call from Telegram
    webhook_payload = {
        "update_id": 99999,
        "message": {
            "message_id": 100,
            "from": {"id": 12345678, "first_name": "Test"},
            "chat": {"id": 12345678, "type": "private"},
            "text": f"/start wp_{token}"
        }
    }
    res_wh = client.post("/api/telegram/webhook", data=json.dumps(webhook_payload), content_type="application/json")
    print("Webhook response:", res_wh.status_code, res_wh.get_json())
    assert res_wh.status_code == 200
    assert res_wh.get_json()["ok"] == True

    # Test link-status after start
    res_status_after = client.get(f"/api/user/telegram/link-status?token={token}")
    data_after = res_status_after.get_json()
    print("link-status after start:", data_after)
    assert data_after["connected"] == True
    assert data_after["chat_id"] == "12345678"

    # Cleanup API test user
    with get_db() as (conn, db_type):
        cur = conn.cursor()
        p = "%s" if db_type == "postgres" else "?"
        cur.execute(f"DELETE FROM telegram_link_tokens WHERE user_id = {p};", (api_uid,))
        cur.execute(f"DELETE FROM user_settings WHERE user_id = {p};", (api_uid,))
        cur.execute(f"DELETE FROM users WHERE id = {p};", (api_uid,))
        conn.commit()

    print("✅ All HTTP API endpoints verified successfully!")

if __name__ == "__main__":
    test_telegram_flow()
    test_api_endpoints()
