import json
import os
from datetime import date

from core import (
    config,
    fetch_all_jobs,
    sync_all_storage,
    send_whatsapp_message,
    send_email_notification,
    send_telegram_message,
    get_all_jobs,
    save_jobs,
    record_daily_history,
)

def load_history() -> dict:
    """Charge l'historique des concours déjà notifiés pour éviter les doublons."""
    if os.path.exists(config.HISTORY_FILE):
        try:
            with open(config.HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"seen_ids": [], "last_run": ""}
    return {"seen_ids": [], "last_run": ""}

def save_history(seen_ids: list[str]):
    """Enregistre l'historique mis à jour."""
    data = {
        "seen_ids": list(set(seen_ids)),
        "last_run": date.today().isoformat()
    }
    with open(config.HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("=" * 65)
    print("Moteur de surveillance autonome de l'emploi public au Maroc")
    print(f"Profil ciblé : {config.PROFILE_NAME}")
    print("=" * 65)

    # 1. Scraping et filtrage des concours valides
    jobs = fetch_all_jobs()

    if not jobs:
        print("[INFO] Aucun concours actif correspondant trouvé pour le moment.")
        sync_all_storage([])
        return

    # 2. Vérification des nouvelles offres vs base de données & historique local
    history = load_history()
    seen_ids = set(history.get("seen_ids", []))
    try:
        db_existing = get_all_jobs()
        for ej in db_existing:
            seen_ids.add(ej["id"])
    except Exception:
        pass

    new_jobs = [j for j in jobs if j["id"] not in seen_ids]
    urgent_count = sum(1 for j in jobs if j.get("days_left", 99) <= 3)
    today_str = date.today().strftime("%d/%m/%Y")

    # Sauvegarde dans Supabase / SQLite et enregistrement dans l'historique
    save_jobs(jobs)
    record_daily_history(
        run_date=today_str,
        total_jobs=len(jobs),
        new_jobs=len(new_jobs),
        urgent_jobs=urgent_count,
        sources="emploi-public.ma + wadifa-info.com",
        jobs_snapshot=jobs
    )
    print(f"\nStatistiques : {len(jobs)} concours actifs | {len(new_jobs)} nouveaux | Historique quotidien mis à jour")

    # 3. Synchronisation Google Sheets, Excel et Dashboard HTML
    print("\nSynchronisation des fichiers et Google Sheets...")
    sheet_url = sync_all_storage(jobs)

    # 4. Envoi des notifications (Telegram, Email, WhatsApp)
    if new_jobs or not seen_ids:
        print("\nDiffusion des notifications d'alerte en cours...")
        
        # Telegram
        send_telegram_message(jobs, sheet_url)

        # WhatsApp (si configuré)
        if config.WHATSAPP_ENABLED:
            send_whatsapp_message(jobs, sheet_url)

        # Email
        send_email_notification(jobs, sheet_url)
    else:
        print("\n[INFO] Aucun nouveau concours aujourd'hui, les données ont été synchronisées.")

    # 5. Mise à jour de l'historique
    all_current_ids = [j["id"] for j in jobs]
    save_history(list(seen_ids.union(all_current_ids)))

    print("\n[SUCCES] Pipeline de veille et synchronisation achevé avec succès.")
    print("=" * 65)

if __name__ == "__main__":
    main()
