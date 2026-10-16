import os
from datetime import date
from dotenv import load_dotenv

# Résolution absolue du répertoire racine du projet
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Charger les variables d'environnement depuis le fichier .env à la racine
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()

# ==========================================
# 1. Profil de recherche (Target Profile)
# ==========================================
PROFILE_NAME = "Développement Digital Web Full Stack"

SEARCH_KEYWORDS = [
    # Arabe
    "معلوميات",
    "تطوير",
    "رقمي",
    "ويب",
    "برمجة",
    "نظم المعلومات",
    "الشبكات",
    "الأنظمة والشبكات",
    "مطور",
    "تقني من الدرجة الثالثة",
    # Français
    "informatique",
    "developpement",
    "developpement digital",
    "web",
    "full stack",
    "fullstack",
    "logiciel",
    "reseaux",
    "technologies de l'information",
    "systemes d'information",
    "dts",
    "dut",
    "bts",
]

TARGET_DIPLOMAS = [
    "تقني متخصص",
    "تقني من الدرجة الثالثة",
    "دبلوم التقني المتخصص",
    "شهادة التقني العالي",
    "الدبلوم الجامعي للتكنولوجيا",
    "إجازة",
    "licence",
    "dts",
    "dut",
    "bts",
    "bac+2",
    "bac+3",
]

# ==========================================
# 2. Canaux de Notification (Alerts)
# ==========================================

# Gmail SMTP
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

# Telegram Bot
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# WhatsApp (CallMeBot)
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")

# ==========================================
# 3. Synchronisation Google Sheets
# ==========================================
GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
GOOGLE_SHEET_WEBHOOK_URL = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "")

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", os.path.join(BASE_DIR, "service_account.json"))
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SA_KEY", "")

# ==========================================
# 4. Base de Données (PostgreSQL / Supabase)
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ==========================================
# 5. Fichiers et Chemins Locaux
# ==========================================
HISTORY_FILE = os.path.join(BASE_DIR, "seen_jobs.json")
EXCEL_OUTPUT = os.path.join(BASE_DIR, "concours_actifs.xlsx")
HTML_OUTPUT = os.path.join(BASE_DIR, "concours_actifs.html")
