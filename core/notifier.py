import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import urllib.parse
import urllib.request
import json
import html
import re
import os
import time
from datetime import date
from . import config

WEEKDAY_FR_MAP = {
    0: "lundi",
    1: "mardi",
    2: "mercredi",
    3: "jeudi",
    4: "vendredi",
    5: "samedi",
    6: "dimanche"
}

def safe_url(url: str) -> str:
    """Encode proprement les caractères arabes ou spéciaux dans l'URL pour Telegram."""
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        encoded_path = urllib.parse.quote(parsed.path, safe="/:")
        encoded_query = urllib.parse.quote(parsed.query, safe="=&?_-%")
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, encoded_path, encoded_query, parsed.fragment))
    except Exception:
        return url.strip()

def send_telegram_message(jobs: list[dict], sheet_url: str = "") -> bool:
    """Envoie une notification Telegram propre et formatée en français."""
    if not config.TELEGRAM_ENABLED:
        return False

    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print(f"[ATTENTION] Configuration Telegram incomplète : BOT_TOKEN={'Défini' if config.TELEGRAM_BOT_TOKEN else 'Vide'}, CHAT_ID='{config.TELEGRAM_CHAT_ID}'.")
        print("[INFO] Vérifiez que TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID sont ajoutés dans Settings > Secrets and variables > Actions.")
        return False

    today_str = date.today().strftime("%d/%m/%Y")
    target_sheet = safe_url(sheet_url or config.SPREADSHEET_URL)

    lines = [
        "📢 <b>Concours Fonction Publique Maroc</b>",
        f"🎯 <b>Profil :</b> {html.escape(config.PROFILE_NAME)}",
        f"📅 <b>Date :</b> {today_str}",
        f"📊 <b>Total concours actifs :</b> {len(jobs)}",
        "🌐 <b>Sources :</b> emploi-public.ma + wadifa-info.com",
        "------------------------------------"
    ]

    for i, j in enumerate(jobs[:5], 1):
        source_name = "emploi-public.ma" if "emploi-public" in j.get("source", "") else "wadifa-info.com"
        grade_esc = html.escape(str(j.get("grade", "")))
        org_esc = html.escape(str(j.get("organism", "")))
        deadline_esc = html.escape(str(j.get("deadline_str", "")))
        days = j.get("days_left", 0)
        clean_link = safe_url(j.get("link", ""))

        lines.append(
            f"{i}️⃣ <b>{grade_esc}</b>\n"
            f"🏛 <b>Organisme :</b> {org_esc} ({source_name})\n"
            f"⏳ <b>Date limite :</b> {deadline_esc} (reste {days} j)\n"
            f"🔗 <a href=\"{clean_link}\">Voir l'offre et postuler</a>\n"
        )

    if len(jobs) > 5:
        lines.append(f"➕ <i>+ {len(jobs) - 5} autres concours disponibles dans le tableau.</i>\n")

    if target_sheet:
        lines.append(f"📋 <a href=\"{target_sheet}\"><b>Accéder au Google Sheet complet</b></a>")

    message_text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": str(config.TELEGRAM_CHAT_ID).strip(),
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        response = urllib.request.urlopen(req, timeout=15)
        if response.status == 200:
            print("✅ Notification Telegram envoyée avec succès sur votre téléphone !")
            return True
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        # En cas d'erreur HTML, repli immédiat sur texte brut sécurisé
        try:
            raw_text = "\n".join([re.sub(r'<[^>]+>', '', l) for l in lines])
            payload_raw = {"chat_id": str(config.TELEGRAM_CHAT_ID).strip(), "text": raw_text}
            data_raw = json.dumps(payload_raw).encode("utf-8")
            req2 = urllib.request.Request(url, data=data_raw, headers={"Content-Type": "application/json"})
            resp2 = urllib.request.urlopen(req2, timeout=10)
            if resp2.status == 200:
                print("✅ Notification Telegram envoyée avec succès (mode texte brut) !")
                return True
        except Exception:
            pass
        print(f"❌ Erreur Telegram ({e.code}) : {err_body}")
        return False
    except Exception as e:
        print(f"❌ Erreur Telegram : {e}")
        return False

def send_whatsapp_message(jobs: list[dict], sheet_url: str = "") -> bool:
    """Envoie un message WhatsApp via CallMeBot en français."""
    if not config.WHATSAPP_ENABLED:
        return False

    if not config.WHATSAPP_PHONE or not config.WHATSAPP_API_KEY:
        return False

    today_str = date.today().strftime("%d/%m/%Y")
    
    lines = [
        f"📢 *Concours Fonction Publique Maroc*",
        f"🎯 *Profil :* {config.PROFILE_NAME}",
        f"📅 *Date :* {today_str}",
        f"📊 *Concours actifs :* {len(jobs)}",
        f"🌐 *Sources :* emploi-public.ma + wadifa-info.com",
        "------------------------------------"
    ]

    for i, j in enumerate(jobs[:5], 1):
        source_name = "emploi-public" if "emploi-public" in j.get("source", "") else "wadifa-info"
        lines.append(
            f"{i}️⃣ *{j['grade']}*\n"
            f"🏛 *Organisme :* {j['organism']} ({source_name})\n"
            f"⏳ *Délai :* {j['deadline_str']} (reste {j['days_left']} j)\n"
            f"🔗 *Lien :* {j['link']}\n"
        )

    if len(jobs) > 5:
        lines.append(f"➕ *+ {len(jobs) - 5} autres offres dans le tableau.*\n")

    target_sheet = sheet_url or config.SPREADSHEET_URL
    if target_sheet:
        lines.append(f"📋 *Lien Google Sheets complet :*\n{target_sheet}")

    message_text = "\n".join(lines)
    encoded_text = urllib.parse.quote(message_text)
    api_url = f"https://api.callmebot.com/whatsapp.php?phone={config.WHATSAPP_PHONE}&text={encoded_text}&apikey={config.WHATSAPP_API_KEY}"

    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        response = urllib.request.urlopen(req, timeout=15)
        print("✅ Notification WhatsApp envoyée !")
        return True
    except Exception as e:
        print(f"❌ Erreur WhatsApp : {e}")
        return False

def send_email_notification(jobs: list[dict], sheet_url: str = "") -> bool:
    """Envoie un rapport complet par email en français."""
    if not config.EMAIL_ENABLED:
        return False

    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD or not config.EMAIL_RECIPIENT:
        print(f"[ATTENTION] Configuration Email incomplète : SENDER='{config.EMAIL_SENDER}', RECIPIENT='{config.EMAIL_RECIPIENT}', PASSWORD={'Défini' if config.EMAIL_PASSWORD else 'Vide'}.")
        print("[INFO] Vérifiez que EMAIL_SENDER, EMAIL_PASSWORD et EMAIL_RECIPIENT sont bien ajoutés dans Settings > Secrets and variables > Actions.")
        return False

    today_str = date.today().strftime("%d/%m/%Y")
    target_sheet = sheet_url or config.SPREADSHEET_URL

    rows_html = ""
    for j in jobs:
        days = j["days_left"]
        badge_color = "#dc2626" if days <= 3 else ("#d97706" if days <= 7 else "#16a34a")
        badge_bg = "#fee2e2" if days <= 3 else ("#fef3c7" if days <= 7 else "#dcfce7")
        source_color = "#1d4ed8" if "emploi-public" in j.get("source", "") else "#15803d"
        source_name = "emploi-public (Officiel)" if "emploi-public" in j.get("source", "") else "wadifa-info"

        rows_html += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 12px; font-weight: bold; color: #1e293b;">{j['organism']}</td>
            <td style="padding: 12px; color: #334155;">{j['grade']}</td>
            <td style="padding: 12px; color: #0284c7; font-size: 13px;">{j['diplomas']}</td>
            <td style="padding: 12px; color: #047857; font-size: 13px;">{j['specialties']}</td>
            <td style="padding: 12px; font-weight: bold;">{j['deadline_str']}</td>
            <td style="padding: 12px;">
                <span style="background-color: {badge_bg}; color: {badge_color}; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px;">
                    {days} jour(s)
                </span>
            </td>
            <td style="padding: 12px; font-size: 12px; font-weight: bold; color: {source_color};">{source_name}</td>
            <td style="padding: 12px;">
                <a href="{j['link']}" target="_blank" style="background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 6px 12px; border-radius: 6px; font-size: 13px; display: inline-block;">
                    Postuler 🔗
                </a>
            </td>
        </tr>
        """

    sheet_button_html = ""
    if target_sheet:
        sheet_button_html = f"""
        <div style="text-align: center; margin: 25px 0;">
            <a href="{target_sheet}" target="_blank" style="background-color: #15803d; color: white; padding: 14px 28px; text-decoration: none; font-size: 15px; font-weight: bold; border-radius: 8px; box-shadow: 0 4px 10px rgba(21, 128, 61, 0.25);">
                Consulter le Tableau Google Sheets en Direct
            </a>
        </div>
        """

    empty_table_row = '<tr><td colspan="8" style="text-align:center; padding: 20px;">Aucun nouveau concours aujourd&#39;hui.</td></tr>'
    table_body_html = rows_html if jobs else empty_table_row

    html_body = f"""
    <!DOCTYPE html>
    <html dir="ltr" lang="fr">
    <head>
        <meta charset="utf-8">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #1e293b;">
        <div style="max-width: 950px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #15803d, #047857); padding: 25px 30px; color: #ffffff;">
                <h1 style="margin: 0 0 10px 0; font-size: 22px;">Concours Fonction Publique Maroc — {config.PROFILE_NAME}</h1>
                <p style="margin: 0; opacity: 0.95; font-size: 14px;">
                    Date de veille : {today_str} | Concours actifs trouvés : <strong>{len(jobs)}</strong> | Sources : <strong>emploi-public.ma + wadifa-info.com</strong>
                </p>
            </div>

            <div style="padding: 25px;">
                <p style="font-size: 15px; line-height: 1.6;">
                    Bonjour Abdelkhalek,<br>
                    Voici les concours de la fonction publique actuellement ouverts, dont les délais de candidature sont valides et correspondant à votre profil <strong>{config.PROFILE_NAME}</strong> :
                </p>

                {sheet_button_html}

                <table style="width: 100%; border-collapse: collapse; text-align: left; margin-top: 15px; font-size: 13px;">
                    <thead>
                        <tr style="background-color: #f1f5f9; color: #475569;">
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Organisme</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Poste</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Diplôme</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Spécialité</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Date limite</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Délai</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Source</th>
                            <th style="padding: 12px; border-bottom: 2px solid #cbd5e1;">Lien</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_body_html}
                    </tbody>
                </table>

                <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 12px; color: #64748b; text-align: center;">
                    Ce message a été généré et envoyé automatiquement par votre système autonome de veille emploi.
                </div>
            </div>
        </div>
    </body>
    </html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[{len(jobs)} Concours Actifs] Opportunités Fonction Publique Maroc — {today_str}"
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = config.EMAIL_RECIPIENT

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if os.path.exists(config.EXCEL_OUTPUT):
        try:
            with open(config.EXCEL_OUTPUT, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename=concours_actifs_{today_str.replace('/', '_')}.xlsx")
            msg.attach(part)
        except Exception:
            pass

    try:
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT)
        else:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
            server.starttls()

        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, [config.EMAIL_RECIPIENT], msg.as_string())
        server.quit()
        print("✅ Notification Email envoyée avec succès !")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de l'envoi de l'email : {e}")
        return False


def send_telegram_direct(chat_id: str, bot_token: str = None, message: str = "") -> tuple[bool, str]:
    """Envoie un message Telegram direct vers un chat_id donné avec un bot_token personnalisé ou celui par défaut."""
    token = (bot_token or "").strip() or config.TELEGRAM_BOT_TOKEN
    c_id = str(chat_id or "").strip()

    if not token or not c_id:
        return False, "Chat ID ou Bot Token manquant."

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": c_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        response = urllib.request.urlopen(req, timeout=12)
        if response.status == 200:
            return True, "Message envoyé avec succès."
        return False, f"Code réponse: {response.status}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        try:
            raw_text = re.sub(r'<[^>]+>', '', message)
            payload_raw = {"chat_id": c_id, "text": raw_text}
            req2 = urllib.request.Request(url, data=json.dumps(payload_raw).encode("utf-8"), headers={"Content-Type": "application/json"})
            resp2 = urllib.request.urlopen(req2, timeout=10)
            if resp2.status == 200:
                return True, "Message envoyé (texte brut)."
        except Exception:
            pass
        if "chat not found" in err_body.lower() or "blocked by the user" in err_body.lower():
            return False, "Veuillez d'abord ouvrir notre bot @WadifaBbot sur Telegram et cliquer sur 'Démarrer' (/start) pour autoriser l'envoi."
        return False, f"Erreur Telegram ({e.code}): {err_body}"
    except Exception as e:
        return False, str(e)


def _send_via_brevo_api(api_key: str, sender: str, recipient: str, subject: str, html_body: str, text_body: str = "") -> tuple[bool, str]:
    """Envoie un email via l'API REST HTTPS de Brevo (Port 443 - 300 emails/jour gratuits, zéro blocage)."""
    try:
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "api-key": api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        sender_email = sender or config.EMAIL_SENDER or "wadifa.pulse.contact@gmail.com"
        payload = {
            "sender": {"email": sender_email, "name": "Wadifa Pulse"},
            "to": [{"email": recipient}],
            "subject": subject,
            "htmlContent": html_body
        }
        if text_body:
            payload["textContent"] = text_body
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201, 202):
                print(f"✅ [BREVO SUCCESS] Email délivré à {recipient} via HTTPS API.")
                return True, "Email envoyé avec succès via Brevo HTTPS."
            return False, f"Brevo API returned status {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        print(f"❌ [BREVO HTTP {e.code}] {err_msg}")
        return False, f"Brevo HTTP {e.code}: {err_msg}"
    except Exception as e:
        print(f"❌ [BREVO ERROR] {e}")
        return False, f"Erreur Brevo API: {e}"

def _send_via_resend_api(api_key: str, sender: str, recipient: str, subject: str, html_body: str, text_body: str = "") -> tuple[bool, str]:
    """Envoie un email via l'API REST HTTPS de Resend (Port 443 - 3000 emails/mois gratuits, zéro blocage)."""
    try:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": "application/json"
        }
        sender_email = sender or "Wadifa Pulse <wadifa.pulse.contact@gmail.com>"
        payload = {
            "from": sender_email,
            "to": [recipient],
            "subject": subject,
            "html": html_body
        }
        if text_body:
            payload["text"] = text_body
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status in (200, 201, 202):
                print(f"✅ [RESEND SUCCESS] Email délivré à {recipient} via HTTPS API.")
                return True, "Email envoyé avec succès via Resend HTTPS."
            return False, f"Resend API returned status {resp.status}"
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8") if e.fp else str(e)
        print(f"❌ [RESEND HTTP {e.code}] {err_msg}")
        return False, f"Resend HTTP {e.code}: {err_msg}"
    except Exception as e:
        print(f"❌ [RESEND ERROR] {e}")
        return False, f"Erreur Resend API: {e}"

def send_email_direct(recipient: str, subject: str, html_body: str, text_body: str = "") -> tuple[bool, str]:
    """Envoie un email direct vers un destinataire spécifique via Brevo/Resend HTTPS ou SMTP."""
    dest = (recipient or "").strip()
    if not dest or "@" not in dest:
        return False, "Adresse email destinataire invalide."

    # 1. Priorité aux APIs HTTPS (Port 443 - Jamais bloqué par Railway / Cloud)
    brevo_key = os.getenv("BREVO_API_KEY", "").strip()
    if brevo_key:
        ok_b, msg_b = _send_via_brevo_api(brevo_key, config.EMAIL_SENDER, dest, subject, html_body, text_body)
        if ok_b:
            return True, msg_b
        print(f"⚠️ [BREVO WARN] Basculement suite à : {msg_b}")

    resend_key = os.getenv("RESEND_API_KEY", "").strip()
    if resend_key:
        ok_r, msg_r = _send_via_resend_api(resend_key, config.EMAIL_SENDER, dest, subject, html_body, text_body)
        if ok_r:
            return True, msg_r
        print(f"⚠️ [RESEND WARN] Basculement suite à : {msg_r}")

    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
        return False, "Serveur SMTP non configuré (EMAIL_SENDER ou EMAIL_PASSWORD manquant)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = dest
    if text_body:
        msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Tentative d'envoi avec basculement automatique de port (465 SSL <-> 587 STARTTLS)
    ports_to_try = [465, 587] if config.SMTP_PORT == 465 else [587, 465]
    last_error = "Échec de connexion au serveur SMTP."

    for port in ports_to_try:
        try:
            print(f"📧 [EMAIL ATTEMPT] Envoi vers {dest} via {config.SMTP_SERVER}:{port}...")
            if port == 465:
                server = smtplib.SMTP_SSL(config.SMTP_SERVER, port, timeout=4)
            else:
                server = smtplib.SMTP(config.SMTP_SERVER, port, timeout=4)
                server.starttls()

            clean_pw = config.EMAIL_PASSWORD.replace(" ", "").strip() if config.EMAIL_PASSWORD else ""
            server.login(config.EMAIL_SENDER, clean_pw)
            server.sendmail(config.EMAIL_SENDER, [dest], msg.as_string())
            server.quit()
            print(f"✅ [EMAIL SUCCESS] Email délivré à {dest} via port {port}.")
            return True, "Email envoyé avec succès."
        except Exception as e:
            last_error = str(e)
            print(f"⚠️ [EMAIL WARN] Échec sur port {port}: {e}")

    print(f"❌ [EMAIL FAILED] Impossible d'envoyer l'email à {dest} après tentative sur ports 465 et 587: {last_error}")
    return False, last_error


BILINGUAL_GRADE_SYNONYMS = {
    "technicien spécialisé": ["تقني", "الدرجة الثالثة", "سلم 9", "technicien", "dts", "dut", "bts"],
    "technicien": ["تقني", "technicien", "سلم 9", "سلم 8"],
    "3ème grade": ["الدرجة الثالثة", "سلم 9", "3ème", "3eme"],
    "ingénieur": ["مهندس", "الدرجة الأولى", "ingenieur", "1er", "سلم 11"],
    "administrateur": ["متصرف", "administrateur"],
    "2ème grade": ["الدرجة الثانية", "سلم 11", "2ème", "2eme"],
    "4ème grade": ["الدرجة الرابعة", "سلم 8", "4ème", "4eme"],
    "adjoint": ["مساعد", "adjoint"],
}

BILINGUAL_PROFILE_SYNONYMS = {
    "développement digital": ["تطوير", "ويب", "برمجة", "رقمي", "web", "digital", "full stack", "fullstack", "informatique", "معلوميات"],
    "web": ["ويب", "web", "تطوير الويب", "site"],
    "full stack": ["full stack", "fullstack", "تطوير"],
    "systèmes et réseaux": ["شبكات", "شبكات المعلوميات", "أنظمة", "réseaux", "reseau", "systeme", "systems"],
    "cybersécurité": ["cyber", "sécurité", "securite", "أمن", "أمن الأنظمة", "حماية"],
    "data": ["data", "données", "donnees", "بيانات", "ذكاء"],
    "intelligence artificielle": ["ذكاء", "ai", "intelligence"],
    "informatique": ["معلوميات", "معلومات", "نظم المعلومات", "informatique", "تطوير", "برمجة"],
    "gestion": ["تدبير", "تسيير", "gestion", "management"],
    "comptabilité": ["محاسبة", "comptabilité", "comptabilite", "finance", "مالية"],
    "droit": ["قانون", "حقوق", "droit", "juridique"],
    "ressources humaines": ["موارد بشرية", "rh", "ressources humaines"],
    "agriculture": ["فلاحة", "فلاحي", "زراعة", "زراعي", "مياه وغابات", "صيد بحري", "بيطرة", "بيطري", "إنتاج نباتي", "agronomie", "agriculture", "agroalimentaire", "halieutique", "eaux et forêts", "vétérinaire"],
    "santé": ["صحة", "تمريض", "ممرض", "طبي", "صيدلة", "مختبر", "biologie", "santé", "infirmier", "médical", "pharmacie", "laboratoire"],
    "génie civil": ["بناء", "أشغال عمومية", "هندسة مدنية", "طبوغرافيا", "معمار", "génie civil", "bâtiment", "travaux publics", "btp", "topographie", "architecture"],
    "électromécanique": ["كهرباء", "ميكانيك", "صيانة", "كهروميكانيك", "طاقة", "électromécanique", "électricité", "mécanique", "maintenance", "énergie"],
    "éducation": ["تعليم", "تربية", "تدريس", "أستاذ", "education", "enseignement", "langues", "français", "anglais"],
}

def filter_jobs_for_user_prefs(jobs: list[dict], user_prefs: dict) -> list[dict]:
    """Filtre la liste globale des concours selon les critères bilingues (Arabe / Français) d'un utilisateur."""
    target_profiles = [p.lower().strip() for p in user_prefs.get("target_profiles", []) if p.strip()]
    target_grades = [g.lower().strip() for g in user_prefs.get("target_grades", []) if g.strip()]
    keywords = [k.lower().strip() for k in user_prefs.get("keywords", []) if k.strip()]

    # Si l'utilisateur n'a configuré aucun critère, renvoyer une liste vide
    if not target_profiles and not target_grades and not keywords:
        return []

    # Construire la liste étendue des synonymes pour les grades
    grade_tokens = set()
    for tg in target_grades:
        grade_tokens.add(tg)
        for syn_k, syn_list in BILINGUAL_GRADE_SYNONYMS.items():
            if syn_k in tg or tg in syn_k:
                grade_tokens.update(syn_list)

    # Construire la liste étendue des synonymes pour profils et mots-clés
    profile_tokens = set()
    for prof in target_profiles:
        profile_tokens.add(prof)
        for p_k, p_list in BILINGUAL_PROFILE_SYNONYMS.items():
            if p_k in prof or prof in p_k:
                profile_tokens.update(p_list)

    for kw in keywords:
        profile_tokens.add(kw)
        for p_k, p_list in BILINGUAL_PROFILE_SYNONYMS.items():
            if p_k in kw or kw in p_k:
                profile_tokens.update(p_list)

    matched_jobs = []
    for j in jobs:
        title = str(j.get("title", "")).lower()
        grade = str(j.get("grade", "")).lower()
        organism = str(j.get("organism", "")).lower()
        diplomas = str(j.get("diplomas", "")).lower()
        specialties = str(j.get("specialties", "")).lower()
        description = str(j.get("description", "")).lower()
        full_text = f"{title} {grade} {organism} {diplomas} {specialties} {description}"

        # 1. Vérification du grade
        grade_ok = True
        if target_grades:
            grade_ok = any(tok in grade or tok in full_text for tok in grade_tokens)

        # 2. Vérification des profils et mots-clés
        kw_ok = True
        if target_profiles or keywords:
            kw_ok = any(tok in full_text for tok in profile_tokens)

        if grade_ok and kw_ok:
            matched_jobs.append(j)

    return matched_jobs


def dispatch_all_user_alerts(jobs: list[dict]) -> dict:
    """Distribue les alertes personnalisées à tous les utilisateurs actifs."""
    from .database import get_all_active_users_for_alert
    
    users = get_all_active_users_for_alert()
    summary = {
        "total_users": len(users),
        "telegram_sent": 0,
        "email_sent": 0,
        "errors": []
    }

    if not users:
        print("[INFO] Aucun utilisateur avec alertes actives trouvé.")
        return summary

    today_dt = date.today()
    today_str = today_dt.strftime("%d/%m/%Y")
    today_day_fr = WEEKDAY_FR_MAP.get(today_dt.weekday(), "lundi")

    for u in users:
        # 1. Vérification des jours de réception configurés par l'utilisateur
        user_days = [d.lower().strip() for d in u.get("alert_days", []) if d.strip()]
        if user_days and today_day_fr not in user_days:
            continue

        user_jobs = filter_jobs_for_user_prefs(jobs, u)
        if not user_jobs:
            # Ne pas envoyer de message vide s'il n'y a pas d'offres pertinentes aujourd'hui
            continue

        user_name = u.get("name") or "Candidat"
        user_email = u.get("notification_email") or u.get("email")
        target_sheet = safe_url(u.get("google_sheet_url") or config.SPREADSHEET_URL)

        # 2. Alerte Telegram personnalisée
        if u.get("telegram_enabled") and u.get("telegram_chat_id"):
            lines = [
                f"📢 <b>Wadifa Pulse — Alertes Personnalisées</b>",
                f"👤 <b>Bonjour {html.escape(user_name)}</b>",
                f"📅 <b>Date :</b> {today_str}",
                f"📊 <b>Concours correspondant à votre profil :</b> {len(user_jobs)}",
                "------------------------------------"
            ]
            for i, j in enumerate(user_jobs[:5], 1):
                clean_link = safe_url(j.get("link", ""))
                lines.append(
                    f"{i}️⃣ <b>{html.escape(str(j.get('grade', '')))}</b>\n"
                    f"🏛 {html.escape(str(j.get('organism', '')))}\n"
                    f"⏳ Limite : {html.escape(str(j.get('deadline_str', '')))} ({j.get('days_left', 0)} jours restants)\n"
                    f"🔗 <a href=\"{clean_link}\">Consulter l'offre</a>\n"
                )
            if len(user_jobs) > 5:
                lines.append(f"➕ <i>+ {len(user_jobs) - 5} autres offres sélectionnées sur votre tableau de bord.</i>\n")
            if target_sheet:
                lines.append(f"📋 <a href=\"{target_sheet}\"><b>Voir mon Google Sheets</b></a>")

            tg_ok, tg_err = send_telegram_direct(
                chat_id=u["telegram_chat_id"],
                bot_token=u.get("telegram_bot_token"),
                message="\n".join(lines)
            )
            if tg_ok:
                summary["telegram_sent"] += 1
                time.sleep(0.04) # Smooth rate-limiting (25 msg/sec) pour supporter des milliers d'utilisateurs
            else:
                summary["errors"].append(f"Telegram {u['email']}: {tg_err}")

        # 3. Alerte Email personnalisée
        if u.get("email_alerts_enabled") and user_email:
            rows_html = ""
            for j in user_jobs:
                days = j.get("days_left", 0)
                badge_color = "#dc2626" if days <= 3 else ("#d97706" if days <= 7 else "#16a34a")
                badge_bg = "#fee2e2" if days <= 3 else ("#fef3c7" if days <= 7 else "#dcfce7")
                rows_html += f"""
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 10px; font-weight: bold; color: #1e293b;">{j.get('organism', '')}</td>
                    <td style="padding: 10px; color: #334155;">{j.get('grade', '')}</td>
                    <td style="padding: 10px; color: #0284c7; font-size: 12px;">{j.get('diplomas', '')}</td>
                    <td style="padding: 10px; color: #047857; font-size: 12px;">{j.get('specialties', '')}</td>
                    <td style="padding: 10px; font-weight: bold;">{j.get('deadline_str', '')}</td>
                    <td style="padding: 10px;">
                        <span style="background-color: {badge_bg}; color: {badge_color}; padding: 3px 8px; border-radius: 10px; font-weight: bold; font-size: 11px;">
                            {days} j
                        </span>
                    </td>
                    <td style="padding: 10px;">
                        <a href="{j.get('link', '#')}" target="_blank" style="background-color: #15803d; color: #ffffff; text-decoration: none; padding: 5px 10px; border-radius: 5px; font-size: 12px; display: inline-block;">
                            Postuler
                        </a>
                    </td>
                </tr>
                """

            mail_body = f"""
            <!DOCTYPE html>
            <html lang="fr">
            <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; padding: 20px; color: #1e293b;">
                <div style="max-width: 800px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0;">
                    <div style="background: linear-gradient(135deg, #15803d, #047857); padding: 20px; color: #ffffff;">
                        <h2 style="margin: 0; font-size: 18px;">Wadifa Pulse — Vos Concours Ciblés du Jour</h2>
                        <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 13px;">Date : {today_str} | {len(user_jobs)} opportunité(s) correspondant à vos critères</p>
                    </div>
                    <div style="padding: 20px;">
                        <p style="font-size: 14px;">Bonjour <strong>{html.escape(user_name)}</strong>,</p>
                        <p style="font-size: 13px; color: #475569;">Voici les concours actuellement ouverts correspondant précisément à vos préférences de veille :</p>
                        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 12px; margin-top: 15px;">
                            <thead>
                                <tr style="background-color: #f1f5f9; color: #475569;">
                                    <th style="padding: 10px;">Organisme</th>
                                    <th style="padding: 10px;">Poste</th>
                                    <th style="padding: 10px;">Diplôme</th>
                                    <th style="padding: 10px;">Spécialité</th>
                                    <th style="padding: 10px;">Date limite</th>
                                    <th style="padding: 10px;">Délai</th>
                                    <th style="padding: 10px;">Lien</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows_html if user_jobs else '<tr><td colspan="7" style="text-align:center; padding: 20px; color: #64748b;">Aucun nouveau concours correspondant à vos critères aujourd&#39;hui.</td></tr>'}
                            </tbody>
                        </table>
                        <div style="margin-top: 25px; padding-top: 15px; border-top: 1px solid #e2e8f0; font-size: 11px; color: #94a3b8; text-align: center;">
                            Notification générée par Wadifa Pulse. Vous pouvez modifier vos alertes à tout moment dans vos Paramètres.
                        </div>
                    </div>
                </div>
            </body>
            </html>
            """
            subject = f"[{len(user_jobs)} Concours Trouvés] Votre Veille Wadifa Pulse — {today_str}"
            em_ok, em_err = send_email_direct(user_email, subject, mail_body)
            if em_ok:
                summary["email_sent"] += 1
            else:
                summary["errors"].append(f"Email {user_email}: {em_err}")

    return summary


def send_otp_email(recipient: str, otp_code: str, user_name: str = "", base_url: str = "") -> tuple[bool, str]:
    """Envoie un email de vérification OTP au design éditorial distinctif et institutionnel (Direction Gazette)."""
    dest = (recipient or "").strip()
    if not dest or "@" not in dest:
        return False, "Adresse email destinataire invalide."

    name_clean = user_name.strip() if user_name else ""
    greeting_html = f"Bonjour <strong>{html.escape(name_clean)}</strong>," if name_clean else "Bonjour,"
    plain_greeting = f"Bonjour {name_clean}," if name_clean else "Bonjour,"
    subject = f"{otp_code} — Code de vérification Wadifa Pulse"

    domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "wadifapulse.up.railway.app").strip()
    root_url = (base_url or (f"https://{domain}" if not domain.startswith("http") else domain)).rstrip("/")
    verify_url = f"{root_url}/verify-otp?code={otp_code}&email={urllib.parse.quote(dest)}"

    # Version texte brut soignée pour l'accessibilité et les clients sans support HTML
    text_content = f"""WADIFA PULSE
Veille & Emploi Public · Maroc
--------------------------------------------------

Vérifiez votre adresse e-mail

{plain_greeting}

Utilisez le code ci-dessous pour confirmer votre adresse e-mail et activer votre compte Wadifa Pulse :

    CODE : {otp_code}

Ce code est valable pendant 10 minutes.

Vous pouvez également valider votre compte directement via ce lien :
{verify_url}

Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail en toute sécurité. Aucun compte ne sera activé sans ce code.

--------------------------------------------------
Wadifa Pulse · Plateforme indépendante d'information et d'analyse de l'emploi public au Maroc
Rabat, Maroc · Contact : wadifa.pulse.contact@gmail.com
"""

    # Version HTML : Direction Gazette Institutionnelle (Typographique, asymétrique, non-générique)
    html_content = f"""<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" lang="fr">
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>{subject}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td {{ font-family: Arial, Helvetica, sans-serif !important; }}
    </style>
    <![endif]-->
</head>
<body style="margin: 0; padding: 40px 15px; background-color: #F7F7F2; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #202923; line-height: 1.6; -webkit-font-smoothing: antialiased;">
    
    <!-- Preheader masqué pour les clients de messagerie -->
    <div style="display: none; font-size: 1px; color: #F7F7F2; line-height: 1px; max-height: 0px; max-width: 0px; opacity: 0; overflow: hidden;">
        Votre code de vérification Wadifa Pulse est {otp_code}. Valable pendant 10 minutes.
        &#847; &zwnj; &nbsp; &#8199; &shy; &#847; &zwnj; &nbsp; &#8199; &shy; &#847; &zwnj; &nbsp; &#8199; &shy;
    </div>

    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
        <tr>
            <td align="center">
                <!-- Conteneur principal (Architecture sobre, sans fioritures) -->
                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 560px; background-color: #FFFFFF; border: 1px solid #E4EBE4; border-radius: 3px; overflow: hidden; text-align: left;">
                    
                    <!-- Ligne structurelle tricolore (Forest Green + Hairline Champagne Gold) -->
                    <tr>
                        <td height="3" style="background-color: #064E3B; font-size: 1px; line-height: 3px;">&nbsp;</td>
                    </tr>
                    <tr>
                        <td height="1" style="background-color: #B69A62; font-size: 1px; line-height: 1px;">&nbsp;</td>
                    </tr>

                    <!-- En-tête éditorial asymétrique -->
                    <tr>
                        <td style="padding: 28px 36px 20px 36px; border-bottom: 1px solid #E4EBE4;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td valign="middle">
                                        <table border="0" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td valign="middle" style="padding-right: 10px;">
                                                    <img src="{root_url}/static/icon_transparent.png" width="28" height="28" alt="Wadifa Pulse" style="display: block; border: 0;" />
                                                </td>
                                                <td valign="middle">
                                                    <span style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 19px; font-weight: 800; letter-spacing: -0.4px; color: #202923;">Wadifa<span style="color: #064E3B;">Pulse</span></span>
                                                    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 9px; letter-spacing: 1.6px; text-transform: uppercase; color: #717D74; font-weight: 600; margin-top: 2px;">
                                                        Veille & Emploi Public · Maroc
                                                    </div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td align="right" valign="middle">
                                        <span style="font-family: 'SF Mono', Consolas, 'Roboto Mono', Menlo, monospace; font-size: 10px; color: #064E3B; background-color: #F0F4F0; padding: 4px 8px; border-radius: 2px; letter-spacing: 0.8px; font-weight: 600;">
                                            SÉCURITÉ
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Corps de la dépêche -->
                    <tr>
                        <td style="padding: 36px 36px 28px 36px;">
                            <h1 style="font-family: Georgia, 'Times New Roman', -apple-system, serif; font-size: 22px; font-weight: 700; color: #202923; letter-spacing: -0.3px; line-height: 1.3; margin: 0 0 16px 0;">
                                Vérifiez votre adresse e-mail
                            </h1>
                            
                            <p style="font-size: 14px; color: #4A554D; line-height: 1.65; margin: 0 0 24px 0;">
                                {greeting_html}<br />
                                Utilisez le code ci-dessous pour confirmer votre adresse e-mail et activer votre compte Wadifa Pulse :
                            </p>

                            <!-- Bloc Héro OTP (Typographique, asymétrique, ancré par un liseré vert forêt) -->
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #FAFBF9; border: 1px solid #E4EBE4; border-left: 4px solid #064E3B; border-radius: 2px; margin: 10px 0 24px 0;">
                                <tr>
                                    <td style="padding: 20px 24px;">
                                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 10px; font-weight: 700; letter-spacing: 1.5px; text-transform: uppercase; color: #717D74; margin-bottom: 8px;">
                                            Code de vérification temporaire
                                        </div>
                                        <div style="font-family: 'SF Mono', Consolas, 'Roboto Mono', 'Courier New', Courier, monospace; font-size: 38px; font-weight: 800; letter-spacing: 8px; color: #043C2E; line-height: 1.1; margin: 4px 0 8px 0;">
                                            {otp_code}
                                        </div>
                                        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 12px; color: #717D74; margin-top: 6px;">
                                            Ce code expire dans <strong>10 minutes</strong>.
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Action secondaire (Validation en 1 Clic discrète et fonctionnelle) -->
                            <table border="0" cellpadding="0" cellspacing="0" width="100%" style="border-top: 1px solid #E4EBE4; margin-top: 28px; padding-top: 22px;">
                                <tr>
                                    <td>
                                        <p style="font-size: 13px; color: #4A554D; line-height: 1.5; margin: 0 0 12px 0;">
                                            Vous pouvez également confirmer votre compte directement sans saisir le code :
                                        </p>
                                        <table border="0" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td align="left">
                                                    <a href="{verify_url}" target="_blank" style="display: inline-block; background-color: #064E3B; color: #FFFFFF; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13px; font-weight: 600; padding: 11px 22px; border-radius: 3px; text-decoration: none; letter-spacing: 0.3px;">
                                                        Confirmer mon adresse e-mail &rarr;
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                        <div style="font-size: 11px; color: #8F998F; margin-top: 12px; line-height: 1.5;">
                                            Lien direct : <a href="{verify_url}" target="_blank" style="color: #064E3B; text-decoration: underline; word-break: break-all; font-family: monospace; font-size: 11px;">{verify_url}</a>
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- Avertissement de sécurité sobre -->
                            <div style="margin-top: 28px; padding-top: 18px; border-top: 1px solid #F1F5F1; font-size: 12px; color: #8F998F; line-height: 1.5;">
                                Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet e-mail en toute sécurité. Aucun compte ne sera activé sans ce code.
                            </div>
                        </td>
                    </tr>

                    <!-- Pied de page institutionnel -->
                    <tr>
                        <td style="background-color: #F7F7F2; padding: 22px 36px; border-top: 1px solid #E4EBE4; font-size: 11px; color: #717D74; line-height: 1.5;">
                            <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td>
                                        <div style="font-weight: 600; color: #202923; margin-bottom: 2px;">Wadifa Pulse</div>
                                        <div>Plateforme indépendante d'information et d'analyse de l'emploi public au Maroc.</div>
                                        <div style="color: #8F998F; margin-top: 4px;">Rabat, Maroc · Contact : wadifa.pulse.contact@gmail.com</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    return send_email_direct(recipient=dest, subject=subject, html_body=html_content, text_body=text_content)


def process_telegram_update(update: dict) -> tuple[bool, str]:
    """Traite un update Telegram entrant (webhook ou polling) et relie le compte utilisateur."""
    from .database import consume_telegram_link_token
    message = update.get("message") or update.get("edited_message")
    if not message:
        return False, "Pas de message dans l'update."

    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", "")).strip()
    from_user = message.get("from") or {}
    first_name = from_user.get("first_name") or "Candidat"

    if not chat_id:
        return False, "Chat ID introuvable."

    # Si l'utilisateur clique sur le lien deep-link: /start wp_<token>
    if text.startswith("/start wp_"):
        token = text.replace("/start wp_", "").strip()
        ok, user_name = consume_telegram_link_token(token, chat_id, first_name)
        if ok:
            welcome_msg = (
                f"🎉 <b>Félicitations {html.escape(user_name)} !</b>\n\n"
                "Votre compte Telegram est maintenant <b>connecté avec succès</b> à <b>Wadifa Pulse</b>.\n\n"
                "Chaque matin à <b>08:00 (GMT+1)</b>, vous recevrez directement ici en avant-première tous les concours correspondant à votre profil.\n\n"
                "🏛 <i>Wadifa Pulse · Système Autonome de Veille</i>"
            )
            send_telegram_direct(chat_id=chat_id, message=welcome_msg)
            return True, f"Compte {user_name} relié avec succès."
        else:
            err_msg = (
                "⚠️ <b>Lien d'activation expiré ou déjà utilisé.</b>\n\n"
                "Veuillez retourner sur votre tableau de bord Wadifa Pulse et cliquer sur 'Connecter mon Telegram' pour générer un nouveau lien."
            )
            send_telegram_direct(chat_id=chat_id, message=err_msg)
            return False, "Token invalide ou expiré."

    elif text.startswith("/start"):
        welcome_generic = (
            f"👋 <b>Bonjour {html.escape(first_name)} !</b>\n\n"
            "Bienvenue sur le bot officiel de <b>Wadifa Pulse</b>.\n\n"
            "Pour activer vos alertes de concours ciblés en 1 Clic :\n"
            "1. Rendez-vous sur votre espace : <a href=\"https://wadifapulse.up.railway.app/settings\">Paramètres Wadifa Pulse</a>\n"
            "2. Cliquez sur <b>'Connecter mon Telegram'</b>.\n\n"
            "🏛 <i>Wadifa Pulse · Système Autonome de Veille</i>"
        )
        send_telegram_direct(chat_id=chat_id, message=welcome_generic)
        return True, "Message d'accueil envoyé."

    return False, "Commande non gérée."


def check_telegram_updates_for_token(token: str) -> bool:
    """Interroge l'API getUpdates de Telegram pour vérifier si un /start wp_<token> a été reçu."""
    bot_token = config.TELEGRAM_BOT_TOKEN
    if not bot_token:
        return False
    try:
        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?limit=25&timeout=1"
        req = urllib.request.Request(url, headers={"User-Agent": "WadifaPulse/2.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                for upd in data.get("result", []):
                    msg = upd.get("message") or {}
                    text = (msg.get("text") or "").strip()
                    if text == f"/start wp_{token}":
                        process_telegram_update(upd)
                        return True
    except Exception as e:
        print(f"⚠️ check_telegram_updates_for_token: {e}")
    return False


def send_email_change_confirmation(new_email: str, user_name: str, token: str, base_url: str = "") -> tuple[bool, str]:
    """Envoie un email contenant le lien sécurisé de confirmation pour le changement d'adresse email."""
    dest = (new_email or "").strip()
    if not dest or "@" not in dest:
        return False, "Adresse email destinataire invalide."

    root_url = (base_url or "https://wadifapulse.up.railway.app").rstrip("/")
    verify_url = f"{root_url}/verify-email-change?token={token}"
    name_display = html.escape(user_name.strip()) if user_name else "Candidat"
    subject = "🔐 Confirmation de votre nouvelle adresse email — Wadifa Pulse"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmation de changement d'email — Wadifa Pulse</title>
    </head>
    <body style="margin: 0; padding: 30px 15px; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #0f172a; line-height: 1.6;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="table-layout: fixed;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);">
                        
                        <!-- En-tête sobre et officiel avec Logo -->
                        <tr>
                            <td style="padding: 24px 32px 18px 32px; border-bottom: 1px solid #f1f5f9;">
                                <table border="0" cellpadding="0" cellspacing="0" width="100%">
                                    <tr>
                                        <td>
                                            <table border="0" cellpadding="0" cellspacing="0">
                                                <tr>
                                                    <td style="vertical-align: middle; padding-right: 12px;">
                                                        <img src="{root_url}/static/icon_transparent.png" width="34" height="34" alt="Wadifa Pulse" style="display: block; border-radius: 8px;">
                                                    </td>
                                                    <td style="vertical-align: middle;">
                                                        <span style="font-size: 20px; font-weight: 800; letter-spacing: -0.5px; color: #0f172a;">Wadifa<span style="color: #059669;">Pulse</span></span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                        <td align="right">
                                            <span style="display: inline-block; font-size: 11px; font-weight: 600; color: #059669; background-color: #ecfdf5; border: 1px solid #a7f3d0; padding: 4px 10px; border-radius: 20px; letter-spacing: 0.3px;">
                                                Sécurité du Compte
                                            </span>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>

                        <!-- Corps principal -->
                        <tr>
                            <td style="padding: 30px 32px 24px 32px;">
                                <h1 style="margin: 0 0 14px 0; font-size: 20px; font-weight: 700; color: #0f172a; letter-spacing: -0.3px;">
                                    Modification de votre adresse email
                                </h1>
                                <p style="margin: 0 0 10px 0; font-size: 14px; color: #334155;">
                                    Bonjour <strong>{name_display}</strong>,
                                </p>
                                <p style="margin: 0 0 20px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                                    Vous avez demandé à associer l'adresse email <strong>{html.escape(dest)}</strong> à votre compte <strong>Wadifa Pulse</strong>.
                                </p>
                                <p style="margin: 0 0 24px 0; font-size: 14px; color: #475569; line-height: 1.6;">
                                    Pour valider définitivement ce changement et mettre à jour vos identifiants d'accès, cliquez sur le bouton sécurisé ci-dessous :
                                </p>

                                <!-- Bouton de confirmation -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin: 26px 0 24px 0;">
                                    <tr>
                                        <td align="center">
                                            <a href="{verify_url}" target="_blank" style="display: inline-block; background-color: #059669; color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 600; padding: 13px 32px; border-radius: 8px; box-shadow: 0 2px 4px rgba(5, 150, 105, 0.2); letter-spacing: 0.2px;">
                                                ✓ Confirmer mon nouvel email
                                            </a>
                                        </td>
                                    </tr>
                                </table>

                                <!-- Délai d'expiration 24 heures -->
                                <table border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-top: 18px;">
                                    <tr>
                                        <td style="font-size: 12px; color: #b45309; font-weight: 500;">
                                            ⏳ Ce lien sécurisé reste valable pendant <strong>24 heures</strong>.
                                        </td>
                                    </tr>
                                </table>

                                <!-- Lien direct de secours -->
                                <div style="margin-top: 22px; padding-top: 16px; border-top: 1px solid #f1f5f9; font-size: 11px; color: #64748b; line-height: 1.5;">
                                    <span>Lien direct si le bouton ne s'ouvre pas :</span><br>
                                    <a href="{verify_url}" target="_blank" style="color: #059669; text-decoration: underline; word-break: break-all; font-family: monospace; font-size: 11px;">
                                        {verify_url}
                                    </a>
                                </div>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8fafc; padding: 18px 32px; border-top: 1px solid #f1f5f9; font-size: 11px; color: #94a3b8; line-height: 1.5;">
                                <p style="margin: 0 0 5px 0;">
                                    Si vous n'êtes pas à l'origine de cette demande, vous pouvez ignorer cet email en toute sécurité.
                                </p>
                                <p style="margin: 0; color: #cbd5e1;">
                                    © 2026 Wadifa Pulse · Observatoire et Veille Autonome de l'Emploi Public au Maroc.
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    return send_email_direct(dest, subject, html_content)




