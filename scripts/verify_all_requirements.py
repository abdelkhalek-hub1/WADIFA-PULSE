import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import app
from core.security import is_disposable_email
from core.database import get_db

client = app.test_client()

print("=== TEST 1: Disposable Email Detection ===")
for mail in ["john@tempmail.com", "alice@yopmail.fr", "bob@10minutemail.com", "fake@mailinator.com", "user@guerrillamail.org", "bad@throwawaymail.com"]:
    is_disp, msg = is_disposable_email(mail)
    print(f"Check {mail}: is_disposable={is_disp}")
    assert is_disp == True, f"{mail} should be detected as disposable"

is_disp, _ = is_disposable_email("abdelkhalek@gmail.com")
assert is_disp == False, "abdelkhalek@gmail.com should be valid"
print("✅ Disposable email checks passed 100%!")

print("\n=== TEST 2: Signup Rejection on Tempmail ===")
res_disp = client.post("/signup", data={"name": "Temp Guy", "email": "hacker@tempmail.com", "password": "password123"}, follow_redirects=True)
body = res_disp.get_data(as_text=True)
assert "temporaires ou jetables" in body
print("✅ Signup with tempmail correctly rejected!")

print("\n=== TEST 3: Signup with Valid Email & OTP Generation ===")
test_email = "karim_alami_test_v2@gmail.com"
with get_db() as (conn, db_type):
    cur = conn.cursor()
    if db_type == "postgres":
        cur.execute("DELETE FROM user_preferences WHERE user_id IN (SELECT id FROM users WHERE email = %s);", (test_email,))
        cur.execute("DELETE FROM users WHERE email = %s;", (test_email,))
    else:
        cur.execute("DELETE FROM user_preferences WHERE user_id IN (SELECT id FROM users WHERE email = ?);", (test_email,))
        cur.execute("DELETE FROM users WHERE email = ?;", (test_email,))
    conn.commit()

res_signup = client.post("/signup", data={"name": "Karim Alami", "email": test_email, "password": "securepassword2026"}, follow_redirects=False)
print("Signup redirect status:", res_signup.status_code, "Location:", res_signup.headers.get("Location"))
assert res_signup.status_code == 302
assert "/verify-otp" in res_signup.headers.get("Location")

with get_db() as (conn, db_type):
    cur = conn.cursor()
    if db_type == "postgres":
        cur.execute("SELECT id, otp_code, is_verified FROM users WHERE email = %s;", (test_email,))
        u_row = cur.fetchone()
    else:
        cur.execute("SELECT id, otp_code, is_verified FROM users WHERE email = ?;", (test_email,))
        u_row = cur.fetchone()
    user_id = u_row[0]
    otp_code = u_row[1]
    is_verif = u_row[2]

print(f"User ID: {user_id}, Generated OTP: {otp_code}, is_verified: {is_verif}")
assert len(str(otp_code)) == 6
assert not bool(is_verif)
print("✅ OTP generated and user marked as unverified!")

print("\n=== TEST 4: Attempt Login Before OTP Verification ===")
res_login_unverified = client.post("/login", data={"email": test_email, "password": "securepassword2026"}, follow_redirects=False)
print("Login redirect for unverified user:", res_login_unverified.headers.get("Location"))
assert "/verify-otp" in res_login_unverified.headers.get("Location")
print("✅ Unverified login blocked and redirected to /verify-otp!")

print("\n=== TEST 5: Verify with Incorrect OTP ===")
res_wrong_otp = client.post("/verify-otp", data={"email": test_email, "otp_code": "000000"}, follow_redirects=True)
assert "incorrect" in res_wrong_otp.get_data(as_text=True).lower()
print("✅ Incorrect OTP correctly rejected!")

print("\n=== TEST 6: Verify with Correct OTP ===")
res_valid_otp = client.post("/verify-otp", data={"email": test_email, "otp_code": otp_code}, follow_redirects=False)
print("Valid OTP redirect status:", res_valid_otp.status_code, "Location:", res_valid_otp.headers.get("Location"))
assert res_valid_otp.status_code == 302
assert "/settings" in res_valid_otp.headers.get("Location")
print("✅ Correct OTP verified and redirected to /settings!")

print("\n=== TEST 7: Fresh User Dashboard (0 Premature Jobs & Onboarding Prompt) ===")
# User is logged in
res_jobs_fresh = client.get("/api/jobs")
jobs_data_fresh = res_jobs_fresh.get_json()
print("Fresh user jobs count:", len(jobs_data_fresh["jobs"]))
print("Fresh user is_configured:", jobs_data_fresh["is_configured"])
print("Fresh user profile label:", jobs_data_fresh["profile"])
assert len(jobs_data_fresh["jobs"]) == 0, "New user must see 0 jobs before configuring"
assert jobs_data_fresh["is_configured"] == False
assert jobs_data_fresh["profile"] == "Non configuré"
print("✅ Fresh user sees 0 premature jobs and profile is 'Non configuré'!")

print("\n=== TEST 8: Configure Preferences & View Matching Jobs ===")
res_save_prefs = client.post("/api/user/preferences", json={
    "target_profiles": ["Développement Digital Web Full Stack"],
    "target_grades": ["Technicien Spécialisé (3ème grade)"],
    "keywords": ["informatique", "web"],
    "education_level": "Bac+2 (DTS / DUT / BTS)"
})
assert res_save_prefs.get_json()["success"] == True

res_jobs_after = client.get("/api/jobs")
jobs_data_after = res_jobs_after.get_json()
print("Jobs count after configuration:", len(jobs_data_after["jobs"]))
print("is_configured after configuration:", jobs_data_after["is_configured"])
print("profile label after configuration:", jobs_data_after["profile"])
assert len(jobs_data_after["jobs"]) > 0, "User should now see matching jobs"
assert jobs_data_after["is_configured"] == True
assert "Développement Digital" in jobs_data_after["profile"]
print(f"✅ User now sees {len(jobs_data_after['jobs'])} matching jobs after configuring their preferences!")

print("\n🎉 ALL 8 TESTS PASSED WITH 100% SUCCESS ON BRANCH TEST!")
