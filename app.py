import os
import json
import threading
from functools import wraps
from datetime import date
from flask import Flask, render_template, jsonify, request, send_file, redirect, url_for, session
import config
from scraper import fetch_all_jobs
from database import (
    init_db, save_jobs, get_all_jobs, toggle_favorite, update_status,
    get_stats, authenticate_user, record_daily_history, get_daily_history
)
from sheets_manager import sync_all_storage
from notifier import send_telegram_message, send_email_notification

app = Flask(__name__, template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "wadifa-secret-super-key-2026-xyz-morocco")

# Initialisation de la base Supabase / SQLite
init_db()

is_scraping = False

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
# Tableau de Bord Principal (Protégé)
# ==========================================
@app.route("/")
@login_required
def index():
    user = session.get("user", {})
    return render_template("index.html", user=user)

@app.route("/api/jobs", methods=["GET"])
@login_required
def api_get_jobs():
    jobs = get_all_jobs(active_only=False)
    stats = get_stats()
    return jsonify({
        "jobs": jobs,
        "stats": stats,
        "is_scraping": is_scraping,
        "profile": config.PROFILE_NAME,
        "user": session.get("user", {})
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
    global is_scraping
    if is_scraping:
        return jsonify({"success": False, "message": "Scraping déjà en cours..."}), 400

    def run_worker():
        global is_scraping
        try:
            is_scraping = True
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
                    sources="emploi-public.ma + wadifa-info.com"
                )
                
                # 3. Synchronisation Sheets et alertes
                sheet_url = sync_all_storage(jobs)
                send_telegram_message(jobs, sheet_url)
                send_email_notification(jobs, sheet_url)
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
    
    new_status = toggle_favorite(job_id)
    return jsonify({"success": True, "is_favorite": new_status})

@app.route("/api/status", methods=["POST"])
@login_required
def api_update_status():
    data = request.get_json() or {}
    job_id = data.get("id")
    status = data.get("status", "a_postuler")
    if not job_id:
        return jsonify({"success": False, "message": "ID manquant"}), 400
    
    update_status(job_id, status)
    return jsonify({"success": True, "status": status})

@app.route("/api/export/excel", methods=["GET"])
@login_required
def api_download_excel():
    if os.path.exists(config.EXCEL_OUTPUT):
        return send_file(config.EXCEL_OUTPUT, as_attachment=True)
    return jsonify({"success": False, "message": "Fichier Excel non disponible."}), 404

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("🌐 WadifaBot sécurisé avec Supabase PostgreSQL & Authentification")
    print("👉 Connectez-vous sur : http://127.0.0.1:5000/login")
    print("=" * 65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
