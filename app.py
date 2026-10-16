import os
import json
import threading
from flask import Flask, render_template, jsonify, request, send_file
import config
from scraper import fetch_all_jobs
from database import init_db, save_jobs, get_all_jobs, toggle_favorite, update_status, get_stats
from sheets_manager import sync_all_storage
from notifier import send_telegram_message, send_email_notification

app = Flask(__name__, template_folder="templates")
init_db()

# État du scraping en arrière-plan
is_scraping = False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/jobs", methods=["GET"])
def api_get_jobs():
    jobs = get_all_jobs(active_only=False)
    stats = get_stats()
    return jsonify({
        "jobs": jobs,
        "stats": stats,
        "is_scraping": is_scraping,
        "profile": config.PROFILE_NAME
    })

@app.route("/api/scrape", methods=["POST"])
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
                save_jobs(jobs)
                sheet_url = sync_all_storage(jobs)
                # Envoi des alertes si demandé
                send_telegram_message(jobs, sheet_url)
                send_email_notification(jobs, sheet_url)
        finally:
            is_scraping = False

    t = threading.Thread(target=run_worker)
    t.start()
    return jsonify({"success": True, "message": "Scraping lancé en arrière-plan."})

@app.route("/api/favorite", methods=["POST"])
def api_favorite():
    data = request.get_json() or {}
    job_id = data.get("id")
    if not job_id:
        return jsonify({"success": False, "message": "ID manquant"}), 400
    
    new_status = toggle_favorite(job_id)
    return jsonify({"success": True, "is_favorite": new_status})

@app.route("/api/status", methods=["POST"])
def api_update_status():
    data = request.get_json() or {}
    job_id = data.get("id")
    status = data.get("status", "a_postuler")
    if not job_id:
        return jsonify({"success": False, "message": "ID manquant"}), 400
    
    update_status(job_id, status)
    return jsonify({"success": True, "status": status})

@app.route("/api/export/excel", methods=["GET"])
def api_download_excel():
    if os.path.exists(config.EXCEL_OUTPUT):
        return send_file(config.EXCEL_OUTPUT, as_attachment=True)
    return jsonify({"success": False, "message": "Fichier Excel non disponible."}), 404

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🌐 Interface Web Wadifa Bot lancée avec succès !")
    print("👉 Ouvrez votre navigateur sur : http://127.0.0.1:5000")
    print("=" * 60 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
