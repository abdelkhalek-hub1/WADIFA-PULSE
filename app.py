import os
import json
import threading
from functools import wraps
from datetime import date
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
from core import (
    config,
    init_db,
    save_jobs,
    get_all_jobs,
    toggle_favorite,
    update_status,
    get_stats,
    authenticate_user,
    record_daily_history,
    get_daily_history,
    calculate_stats,
    fetch_all_jobs,
    sync_all_storage,
    send_telegram_message,
    send_email_notification,
    register_user,
    get_user_settings,
    update_user_settings,
    get_user_preferences,
    update_user_preferences,
    get_user_jobs,
    toggle_user_favorite,
    update_user_job_status,
    update_user_account,
    send_telegram_direct,
    send_email_direct,
    dispatch_all_user_alerts,
)

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "wadifa-secret-super-key-2026-xyz-morocco")

# Initialisation unique de la base Supabase / SQLite
init_db()

is_scraping = False
last_scrape_result = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# Routes d'Authentification (Auth)
# ==========================================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if "user" in session:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        ok, msg, user_dict = register_user(name, email, password)
        if ok and user_dict:
            session["user"] = user_dict
            return redirect(url_for("settings"))
        else:
            error = msg

    return render_template("signup.html", error=error)

@app.route("/login", methods=["GET", "POST"])
def login():
    if "user" in session:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        user = authenticate_user(email, password)
        if user:
            session["user"] = user
            return redirect(url_for("index"))
        else:
            error = "Identifiants invalides. Veuillez vérifier votre email et mot de passe."

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==========================================
# Tableau de Bord Principal & Paramètres
# ==========================================
@app.route("/")
@login_required
def index():
    user = session.get("user", {})
    return render_template("index.html", user=user)

@app.route("/settings")
@login_required
def settings():
    user = session.get("user", {})
    return render_template("settings.html", user=user)

@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    user = session.get("user")
    user_id = user["id"] if user else None
    jobs = get_user_jobs(user_id=user_id, active_only=False)
    stats = calculate_stats(jobs)
    return jsonify({
        "jobs": jobs,
        "stats": stats,
        "is_scraping": is_scraping,
        "profile": config.PROFILE_NAME,
        "user": user
    })

@app.route("/api/scrape/status", methods=["GET"])
@login_required
def api_scrape_status():
    return jsonify({
        "is_scraping": is_scraping,
        "last_result": last_scrape_result
    })

@app.route("/api/history", methods=["GET"])
@login_required
def api_get_history():
    """Renvoie l'historique de chaque jour."""
    history = get_daily_history()
    return jsonify({"history": history})

@app.route("/api/scrape", methods=["POST"])
@login_required
def api_scrape():
    global is_scraping, last_scrape_result
    if is_scraping:
        return jsonify({"success": False, "message": "Scraping déjà en cours..."}), 400

    def run_worker():
        global is_scraping, last_scrape_result
        try:
            is_scraping = True
            print("🚀 Début de l'actualisation en direct...")
            jobs = fetch_all_jobs()
            if jobs:
                # 1. Sauvegarde dans Supabase
                save_jobs(jobs)
                
                # 2. Enregistrement dans l'historique quotidien
                today_str = date.today().strftime("%d/%m/%Y")
                urgent_count = sum(1 for j in jobs if j.get("days_left", 99) <= 3)
                record_daily_history(
                    run_date=today_str,
                    total_jobs=len(jobs),
                    new_jobs=len(jobs),
                    urgent_jobs=urgent_count,
                    sources="emploi-public.ma + wadifa-info.com",
                    jobs_snapshot=jobs
                )
                
                # 3. Synchronisation Sheets et alertes administrateur
                sheet_url = sync_all_storage(jobs)
                telegram_ok = send_telegram_message(jobs, sheet_url)
                email_ok = send_email_notification(jobs, sheet_url)

                # 4. Distribution des alertes multi-utilisateurs personnalisées
                user_alerts_summary = dispatch_all_user_alerts(jobs)
                print(f"👥 Alertes personnalisées diffusées : {user_alerts_summary}")

                last_scrape_result = {
                    "success": True,
                    "total_jobs": len(jobs),
                    "urgent_jobs": urgent_count,
                    "telegram_sent": bool(telegram_ok),
                    "email_sent": bool(email_ok),
                    "users_alerted": user_alerts_summary.get("total_users", 0),
                    "message": f"{len(jobs)} concours synchronisés et alertes diffusées."
                }
                print(f"✅ Scraping terminé avec succès : {len(jobs)} concours synchronisés.")
            else:
                last_scrape_result = {
                    "success": True,
                    "total_jobs": 0,
                    "urgent_jobs": 0,
                    "telegram_sent": False,
                    "email_sent": False,
                    "message": "Aucun concours actif trouvé lors de ce passage."
                }
        except Exception as e:
            print(f"❌ Erreur lors de l'actualisation : {e}")
            last_scrape_result = {
                "success": False,
                "error": str(e),
                "message": f"Erreur de veille : {e}"
            }
        finally:
            is_scraping = False

    t = threading.Thread(target=run_worker)
    t.start()
    return jsonify({"success": True, "message": "Scraping lancé en arrière-plan."})

@app.route("/api/favorite", methods=["POST"])
@login_required
def api_favorite():
    data = request.get_json() or {}
    job_id = data.get("id")
    if not job_id:
        return jsonify({"success": False, "message": "ID manquant"}), 400
    
    user = session.get("user")
    user_id = user["id"] if user else None
    if not user_id:
        return jsonify({"success": False, "message": "Non authentifié"}), 401
    
    new_status = toggle_user_favorite(user_id, job_id)
    return jsonify({"success": True, "is_favorite": new_status})

@app.route("/api/status", methods=["POST"])
@login_required
def api_update_status():
    data = request.get_json() or {}
    job_id = data.get("id")
    status = data.get("status", "a_postuler")
    if not job_id:
        return jsonify({"success": False, "message": "ID manquant"}), 400
    
    user = session.get("user")
    user_id = user["id"] if user else None
    if not user_id:
        return jsonify({"success": False, "message": "Non authentifié"}), 401
    
    update_user_job_status(user_id, job_id, status)
    return jsonify({"success": True, "status": status})

# ==========================================
# Routes API Paramètres Utilisateur & Tests
# ==========================================
@app.route("/api/user/settings", methods=["GET", "POST"])
@login_required
def api_user_settings():
    user = session.get("user")
    user_id = user["id"]
    if request.method == "POST":
        payload = request.get_json() or {}
        ok = update_user_settings(user_id, payload)
        return jsonify({"success": ok})
    else:
        st = get_user_settings(user_id)
        return jsonify(st)

@app.route("/api/user/preferences", methods=["GET", "POST"])
@login_required
def api_user_preferences():
    user = session.get("user")
    user_id = user["id"]
    if request.method == "POST":
        payload = request.get_json() or {}
        ok = update_user_preferences(user_id, payload)
        return jsonify({"success": ok})
    else:
        prefs = get_user_preferences(user_id)
        return jsonify(prefs)

@app.route("/api/user/account", methods=["POST"])
@login_required
def api_user_account():
    user = session.get("user")
    user_id = user["id"]
    payload = request.get_json() or {}
    name = payload.get("name", "").strip()
    new_password = payload.get("new_password", "").strip() or None

    ok, msg = update_user_account(user_id, name, new_password)
    if ok:
        session["user"]["name"] = name
        session.modified = True
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/user/test/telegram", methods=["POST"])
@login_required
def api_test_telegram():
    payload = request.get_json() or {}
    chat_id = payload.get("telegram_chat_id", "").strip()
    bot_token = payload.get("telegram_bot_token", "").strip() or None

    if not chat_id:
        return jsonify({"success": False, "message": "Chat ID manquant."}), 400

    test_message = (
        "🔔 <b>Test de Connexion — Wadifa Pulse</b>\n\n"
        "Félicitations ! Votre compte Telegram est parfaitement configuré. "
        "Vous recevrez désormais chaque matin vos alertes de concours ciblés directement ici.\n\n"
        "🏛 <i>Wadifa Pulse · Système Autonome de Veille</i>"
    )

    ok, err_msg = send_telegram_direct(chat_id=chat_id, bot_token=bot_token, message=test_message)
    return jsonify({"success": ok, "message": err_msg})

@app.route("/api/user/test/email", methods=["POST"])
@login_required
def api_test_email():
    payload = request.get_json() or {}
    notif_email = payload.get("notification_email", "").strip()

    if not notif_email or "@" not in notif_email:
        return jsonify({"success": False, "message": "Adresse email invalide."}), 400

    html_content = """
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 25px; background-color: #f8fafc; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden;">
            <div style="background: linear-gradient(135deg, #15803d, #047857); padding: 20px; color: white;">
                <h2 style="margin: 0; font-size: 18px;">Wadifa Pulse — Test de Notification</h2>
            </div>
            <div style="padding: 20px; font-size: 14px; line-height: 1.6;">
                <p>Bonjour,</p>
                <p>Ceci est un email de test confirmant que votre boîte de réception est convenablement connectée à votre profil <strong>Wadifa Pulse</strong>.</p>
                <p>Vos alertes quotidiennes de concours de la fonction publique marocaine vous parviendront chaque matin à cette adresse.</p>
                <div style="margin-top: 25px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center;">
                    Wadifa Pulse · Veille de Recrutement Autonome
                </div>
            </div>
        </div>
    </div>
    """

    ok, err_msg = send_email_direct(recipient=notif_email, subject="🔔 Test de Connexion Réussi — Wadifa Pulse", html_body=html_content)
    return jsonify({"success": ok, "message": err_msg})

@app.route("/api/export/excel", methods=["GET"])
@login_required
def api_download_excel():
    if os.path.exists(config.EXCEL_OUTPUT):
        return send_file(config.EXCEL_OUTPUT, as_attachment=True)
    return jsonify({"success": False, "message": "Fichier Excel non disponible."}), 404

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print("\n" + "=" * 65)
    print("WadifaBot v2.0 sécurisé avec Supabase PostgreSQL & Multi-Tenant SaaS")
    print(f"Serveur actif sur le port {port}")
    print("=" * 65 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
