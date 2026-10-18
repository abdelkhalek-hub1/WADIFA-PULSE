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
    register_user,
    get_user_settings,
    update_user_settings,
    get_user_preferences,
    update_user_preferences,
    get_user_jobs,
    toggle_user_favorite,
    update_user_job_status,
    get_all_active_users_for_alert,
    update_user_account,
    verify_user_otp,
    resend_user_otp,
    create_telegram_link_token,
    get_telegram_link_status,
    consume_telegram_link_token,
    disconnect_user_telegram,
    get_or_create_google_user,
    create_email_change_request,
    verify_and_apply_email_change,
    get_pending_email_change,
    cancel_email_change_request,
    delete_user_account,
)
from .security import (
    is_disposable_email,
    generate_otp_code,
    get_otp_expiry,
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
    send_telegram_direct,
    send_email_direct,
    filter_jobs_for_user_prefs,
    dispatch_all_user_alerts,
    send_otp_email,
    process_telegram_update,
    check_telegram_updates_for_token,
    send_email_change_confirmation,
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
    "register_user",
    "get_user_settings",
    "update_user_settings",
    "get_user_preferences",
    "update_user_preferences",
    "get_user_jobs",
    "toggle_user_favorite",
    "update_user_job_status",
    "get_all_active_users_for_alert",
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
