import os
import json
import secrets
import urllib.parse
import urllib.request
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
    verify_user_otp,
    resend_user_otp,
    create_telegram_link_token,
    get_telegram_link_status,
    consume_telegram_link_token,
    disconnect_user_telegram,
    process_telegram_update,
    check_telegram_updates_for_token,
    get_or_create_google_user,
    create_email_change_request,
    verify_and_apply_email_change,
    get_pending_email_change,
    cancel_email_change_request,
    send_email_change_confirmation,
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
# Routes d'Authentification & Vérification OTP
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

        ok, msg, user_dict, otp = register_user(name, email, password)
        if ok and user_dict:
            session["pending_verification_email"] = user_dict["email"]
            return redirect(url_for("verify_otp_page"))
        else:
            error = msg

    google_client_id = getattr(config, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "").strip()
    return render_template("signup.html", error=error, google_client_id=google_client_id)

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp_page():
    if "user" in session:
        return redirect(url_for("index"))

    email = request.args.get("email") or session.get("pending_verification_email", "")
    if not email:
        return redirect(url_for("signup"))

    error = None
    if request.method == "POST":
        entered_email = request.form.get("email") or email
        otp_code = request.form.get("otp_code", "").strip()

        ok, msg, user_dict = verify_user_otp(entered_email, otp_code)
        if ok and user_dict:
            session.pop("pending_verification_email", None)
            session["user"] = user_dict
            # Redirection directe vers la configuration des critères
            return redirect(url_for("settings"))
        else:
            error = msg

    return render_template("verify_otp.html", email=email, error=error)

@app.route("/api/resend-otp", methods=["POST"])
def api_resend_otp():
    data = request.get_json() or {}
    email = data.get("email") or session.get("pending_verification_email")
    if not email:
        return jsonify({"success": False, "message": "Email manquant."}), 400

    ok, msg = resend_user_otp(email)
    return jsonify({"success": ok, "message": msg})

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
            if user.get("pending_verification"):
                session["pending_verification_email"] = user["email"]
                return redirect(url_for("verify_otp_page", email=user["email"]))
            session["user"] = user
            return redirect(url_for("index"))
        else:
            error = "Identifiants invalides. Veuillez vérifier votre email et mot de passe."

    google_client_id = getattr(config, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "").strip()
    return render_template("login.html", error=error, google_client_id=google_client_id)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==========================================
# Routes Google OAuth 2.0 (Sign in / Sign up)
# ==========================================
@app.route("/auth/google/login")
def auth_google_login():
    """Redirige l'utilisateur vers la mire de consentement Google OAuth 2.0."""
    if "user" in session:
        return redirect(url_for("index"))

    client_id = getattr(config, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not client_id:
        return render_template("login.html", error="Connexion Google indisponible : GOOGLE_CLIENT_ID non configuré.", google_client_id="")

    state = secrets.token_urlsafe(16)
    session["google_oauth_state"] = state

    redirect_uri = url_for("auth_google_callback", _external=True)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account"
    }
    google_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode(params)
    return redirect(google_url)

@app.route("/auth/google/callback")
def auth_google_callback():
    """Réceptionne le code d'autorisation Google et connecte l'utilisateur."""
    if "user" in session:
        return redirect(url_for("index"))

    error = request.args.get("error")
    if error:
        return render_template("login.html", error=f"Connexion Google annulée ({error}).", google_client_id=getattr(config, "GOOGLE_CLIENT_ID", ""))

    code = request.args.get("code")
    state = request.args.get("state")
    expected_state = session.pop("google_oauth_state", None)

    client_id = getattr(config, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = getattr(config, "GOOGLE_CLIENT_SECRET", "") or os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    if not code or not state or (expected_state and state != expected_state):
        return render_template("login.html", error="Session OAuth expirée ou invalide. Veuillez réessayer.", google_client_id=client_id)

    redirect_uri = url_for("auth_google_callback", _external=True)

    try:
        # Échange du code d'autorisation contre les tokens
        token_url = "https://oauth2.googleapis.com/token"
        token_payload = urllib.parse.urlencode({
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }).encode("utf-8")

        req = urllib.request.Request(token_url, data=token_payload, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))

        access_token = token_data.get("access_token")
        if not access_token:
            return render_template("login.html", error="Impossible d'obtenir le jeton d'accès Google.", google_client_id=client_id)

        # Récupération des informations du profil
        info_req = urllib.request.Request("https://www.googleapis.com/oauth2/v3/userinfo")
        info_req.add_header("Authorization", f"Bearer {access_token}")
        with urllib.request.urlopen(info_req, timeout=10) as resp:
            user_info = json.loads(resp.read().decode("utf-8"))

        email = user_info.get("email")
        name = user_info.get("name") or user_info.get("given_name") or email.split("@")[0]
        google_id = user_info.get("sub", "")

        user_dict = get_or_create_google_user(email=email, name=name, google_id=google_id)
        if not user_dict:
            return render_template("login.html", error="Échec de création ou d'association du compte.", google_client_id=client_id)

        session["user"] = user_dict
        return redirect(url_for("index"))

    except Exception as e:
        print(f"⚠️ Erreur OAuth Google Callback : {e}")
        return render_template("login.html", error="Erreur lors de la validation auprès de Google.", google_client_id=client_id)

@app.route("/api/auth/google/one-tap", methods=["POST"])
def api_google_one_tap():
    """Valide un credential JWT transmis par Google Identity Services (One-Tap / Button)."""
    payload = request.get_json() or {}
    credential = payload.get("credential")
    if not credential:
        return jsonify({"success": False, "message": "Jeton Google manquant."}), 400

    try:
        verify_url = "https://oauth2.googleapis.com/tokeninfo?id_token=" + credential
        with urllib.request.urlopen(verify_url, timeout=10) as resp:
            info = json.loads(resp.read().decode("utf-8"))

        client_id = getattr(config, "GOOGLE_CLIENT_ID", "") or os.getenv("GOOGLE_CLIENT_ID", "").strip()
        if client_id and info.get("aud") != client_id:
            return jsonify({"success": False, "message": "Audience du jeton non valide."}), 403

        email = info.get("email")
        name = info.get("name") or info.get("given_name") or (email.split("@")[0] if email else "")
        google_id = info.get("sub", "")

        if not email:
            return jsonify({"success": False, "message": "Email non fourni par Google."}), 400

        user_dict = get_or_create_google_user(email=email, name=name, google_id=google_id)
        if not user_dict:
            return jsonify({"success": False, "message": "Erreur lors de la connexion."}), 500

        session["user"] = user_dict
        return jsonify({"success": True, "redirect": url_for("index")})

    except Exception as e:
        print(f"⚠️ Erreur One-Tap Google : {e}")
        return jsonify({"success": False, "message": "Jeton Google invalide ou expiré."}), 400

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
    prefs = get_user_preferences(user_id) if user_id else {}
    jobs = get_user_jobs(user_id=user_id, active_only=False)
    stats = calculate_stats(jobs)

    target_profs = prefs.get("target_profiles", [])
    profile_label = " · ".join(target_profs) if target_profs else "Non configuré"

    return jsonify({
        "jobs": jobs,
        "stats": stats,
        "is_scraping": is_scraping,
        "is_configured": prefs.get("is_configured", False),
        "target_profiles": target_profs,
        "profile": profile_label,
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
        if new_password:
            msg = "Profil et mot de passe enregistrés avec succès ! Vous pouvez désormais vous connecter soit avec votre email et ce mot de passe, soit via Google."
        return jsonify({"success": True, "message": msg})
    return jsonify({"success": False, "message": msg}), 400

@app.route("/api/user/email/request-change", methods=["POST"])
@login_required
def api_request_email_change():
    """Déclenche la demande de changement d'email et envoie un lien sécurisé."""
    user = session.get("user")
    user_id = user["id"]
    payload = request.get_json() or {}
    new_email = payload.get("new_email", "").strip()

    ok, msg, token = create_email_change_request(user_id, new_email)
    if not ok:
        return jsonify({"success": False, "message": msg}), 400

    base_url = request.host_url.rstrip("/")
    if "railway.app" in base_url and base_url.startswith("http://"):
        base_url = "https://" + base_url.split("://", 1)[1]

    em_ok, em_msg = send_email_change_confirmation(new_email, user.get("name", ""), token, base_url)
    if not em_ok:
        cancel_email_change_request(user_id)
        return jsonify({"success": False, "message": f"Échec d'envoi de l'email : {em_msg}"}), 500

    return jsonify({
        "success": True,
        "message": f"Un lien de confirmation a été envoyé à {new_email}. Veuillez consulter votre boîte de réception pour valider la modification.",
        "pending_email": new_email
    })

@app.route("/api/user/email/pending-change", methods=["GET"])
@login_required
def api_get_pending_email_change():
    """Vérifie si une demande de changement d'email est en attente."""
    user = session.get("user")
    user_id = user["id"]
    pending = get_pending_email_change(user_id)
    return jsonify({"success": True, "pending": pending})

@app.route("/api/user/email/cancel-change", methods=["POST"])
@login_required
def api_cancel_email_change():
    """Annule la demande de changement d'email en cours."""
    user = session.get("user")
    user_id = user["id"]
    cancel_email_change_request(user_id)
    return jsonify({"success": True, "message": "Demande de modification annulée avec succès."})

@app.route("/verify-email-change", methods=["GET"])
def verify_email_change():
    """Valide le token de changement d'email lors du clic sur le lien."""
    token = request.args.get("token", "").strip()
    if not token:
        return render_template("verify_email_result.html", success=False, message="Lien de confirmation manquant ou invalide.")

    ok, msg, user_dict = verify_and_apply_email_change(token)
    if ok and user_dict:
        if "user" in session:
            session["user"]["email"] = user_dict["email"]
            session.modified = True
        return render_template("verify_email_result.html", success=True, message=msg, new_email=user_dict["email"])
    else:
        return render_template("verify_email_result.html", success=False, message=msg)


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

@app.route("/api/telegram/webhook", methods=["POST"])
def api_telegram_webhook():
    """Point d'entrée du Webhook officiel Telegram."""
    update = request.get_json(silent=True) or {}
    if update:
        try:
            process_telegram_update(update)
        except Exception as e:
            print(f"⚠️ Webhook processing error: {e}")
    return jsonify({"ok": True})

_cron_lock = threading.Lock()
_is_cron_running = False

@app.route("/api/cron/run", methods=["GET", "POST"])
def api_trigger_cron():
    """Point d'entrée du Cron autonome (appelable par cron-job.org ou manuellement)."""
    global _is_cron_running
    key = request.args.get("key") or request.headers.get("X-Cron-Key") or (request.get_json(silent=True) or {}).get("key")
    configured_key = getattr(config, "CRON_SECRET", "WadifaPulseCron2026") or "WadifaPulseCron2026"

    if not key or key.strip() != configured_key.strip():
        return jsonify({"success": False, "message": "Accès refusé : Clé de déclenchement cron non valide."}), 403

    if _is_cron_running:
        return jsonify({"success": True, "message": "Le pipeline de veille et diffusion est déjà en cours."}), 200

    from main import main as execute_daily_pipeline

    def background_task():
        global _is_cron_running
        with _cron_lock:
            _is_cron_running = True
            try:
                print("🚀 [CRON TRIGGER] Lancement du pipeline de veille en tâche de fond...")
                execute_daily_pipeline()
                print("✅ [CRON TRIGGER] Pipeline de veille achevé avec succès.")
            except Exception as e:
                print(f"❌ [CRON TRIGGER] Erreur pendant l'exécution : {e}")
            finally:
                _is_cron_running = False

    t = threading.Thread(target=background_task, daemon=True)
    t.start()

    return jsonify({
        "success": True,
        "message": "Pipeline de veille et diffusion lancé avec succès en tâche de fond.",
        "status": "running"
    }), 200

@app.route("/api/user/telegram/link-init", methods=["POST"])
@login_required
def api_telegram_link_init():
    """Initialise une session de liaison Telegram 1-Clic et génère le deep-link."""
    user = session.get("user")
    user_id = user["id"]
    token = create_telegram_link_token(user_id)
    bot_username = config.TELEGRAM_BOT_USERNAME or "WadifaPulse_bot"
    deep_link = f"https://t.me/{bot_username}?start=wp_{token}"
    tg_link = f"tg://resolve?domain={bot_username}&start=wp_{token}"
    return jsonify({
        "success": True,
        "token": token,
        "bot_username": bot_username,
        "deep_link": deep_link,
        "tg_link": tg_link
    })

@app.route("/api/user/telegram/link-status", methods=["GET"])
@login_required
def api_telegram_link_status():
    """Vérifie si le deep-link Telegram a été validé et renvoie l'état."""
    token = request.args.get("token", "").strip()
    if not token:
        return jsonify({"success": False, "connected": False}), 400

    st = get_telegram_link_status(token)
    if not st.get("connected"):
        # Fallback pour le développement local ou si le webhook n'a pas encore répondu
        if check_telegram_updates_for_token(token):
            st = get_telegram_link_status(token)

    return jsonify({
        "success": True,
        "connected": st.get("connected", False),
        "chat_id": st.get("chat_id", ""),
        "user_name": st.get("user_name", "")
    })

@app.route("/api/user/telegram/disconnect", methods=["POST"])
@login_required
def api_telegram_disconnect():
    """Dissocie le compte Telegram de l'utilisateur."""
    user = session.get("user")
    user_id = user["id"]
    ok = disconnect_user_telegram(user_id)
    return jsonify({"success": ok, "message": "Compte Telegram dissocié avec succès." if ok else "Erreur lors de la dissociation."})


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
