import os
from datetime import date
from dotenv import load_dotenv

# Charger les variables d'environnement depuis le fichier .env si présent
load_dotenv()

# ==========================================
# 1. إعدادات البروفايل (Profil de recherche)
# ==========================================
PROFILE_NAME = "Développement Digital Web Full Stack"

SEARCH_KEYWORDS = [
    # العربية
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
    # الفرنسية
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
# 2. إعدادات الإشعارات (Notifications)
# ==========================================

# أ) البريد الإلكتروني (Gmail SMTP)
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "true").lower() == "true"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 465))
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")

# ب) تيليغرام (Telegram Bot - البديل الأسهل والأسرع 100% مجاني ومباشر)
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ج) واتساب (CallMeBot)
WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "false").lower() == "true"
WHATSAPP_PHONE = os.getenv("WHATSAPP_PHONE", "")
WHATSAPP_API_KEY = os.getenv("WHATSAPP_API_KEY", "")

# ==========================================
# 3. إعدادات Google Sheets
# ==========================================
GOOGLE_SHEETS_ENABLED = os.getenv("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"

# الطريقة الأسهل بدون Google Cloud: عبر Google Apps Script Webhook
GOOGLE_SHEET_WEBHOOK_URL = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "")

# الطريقة التقليدية (Service Account):
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "")
SPREADSHEET_URL = os.getenv("SPREADSHEET_URL", "")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GCP_SA_KEY", "")

# ==========================================
# 4. مسارات الملفات المحلية (Local Output)
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HISTORY_FILE = os.path.join(BASE_DIR, "seen_jobs.json")
EXCEL_OUTPUT = os.path.join(BASE_DIR, "concours_actifs.xlsx")
HTML_OUTPUT = os.path.join(BASE_DIR, "concours_actifs.html")
