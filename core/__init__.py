"""
Wadifa Pulse - Package d'Architecture Centrale
Moteur Autonome de Veille et de Suivi de l'Emploi Public au Maroc
"""

from . import config
from .database import (
    get_db,
    init_db,
    save_jobs,
    get_all_jobs,
    authenticate_user,
    record_daily_history,
    get_daily_history,
    get_stats,
    calculate_stats,
    toggle_favorite,
    update_status,
)
from .scraper import (
    fetch_all_jobs,
    fetch_emploi_public_jobs,
    fetch_wadifa_info_jobs,
)
from .notifier import (
    send_telegram_message,
    send_email_notification,
    send_whatsapp_message,
)
from .storage import (
    sync_all_storage,
    export_to_excel_or_csv,
    update_google_sheets_webhook,
)

__all__ = [
    "config",
    "get_db",
    "init_db",
    "save_jobs",
    "get_all_jobs",
    "authenticate_user",
    "record_daily_history",
    "get_daily_history",
    "get_stats",
    "calculate_stats",
    "toggle_favorite",
    "update_status",
    "fetch_all_jobs",
    "fetch_emploi_public_jobs",
    "fetch_wadifa_info_jobs",
    "send_telegram_message",
    "send_email_notification",
    "send_whatsapp_message",
    "sync_all_storage",
    "export_to_excel_or_csv",
    "update_google_sheets_webhook",
]
