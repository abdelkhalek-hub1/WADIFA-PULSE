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
from datetime import date
from . import config

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


def send_email_direct(recipient: str, subject: str, html_body: str) -> tuple[bool, str]:
    """Envoie un email direct vers un destinataire spécifique via le serveur SMTP configuré."""
    dest = (recipient or "").strip()
    if not dest or "@" not in dest:
        return False, "Adresse email destinataire invalide."

    if not config.EMAIL_SENDER or not config.EMAIL_PASSWORD:
        return False, "Serveur SMTP non configuré (EMAIL_SENDER ou EMAIL_PASSWORD manquant)."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.EMAIL_SENDER
    msg["To"] = dest
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
        else:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=15)
            server.starttls()

        server.login(config.EMAIL_SENDER, config.EMAIL_PASSWORD)
        server.sendmail(config.EMAIL_SENDER, [dest], msg.as_string())
        server.quit()
        return True, "Email envoyé avec succès."
    except Exception as e:
        return False, str(e)


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

    today_str = date.today().strftime("%d/%m/%Y")

    for u in users:
        user_jobs = filter_jobs_for_user_prefs(jobs, u)
        user_name = u.get("name") or "Candidat"
        user_email = u.get("notification_email") or u.get("email")
        target_sheet = safe_url(u.get("google_sheet_url") or config.SPREADSHEET_URL)

        # 1. Alerte Telegram personnalisée
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
            else:
                summary["errors"].append(f"Telegram {u['email']}: {tg_err}")

        # 2. Alerte Email personnalisée
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


def send_otp_email(recipient: str, otp_code: str, user_name: str = "") -> tuple[bool, str]:
    """Envoie un code de vérification OTP à 6 chiffres par email."""
    dest = (recipient or "").strip()
    if not dest or "@" not in dest:
        return False, "Adresse email destinataire invalide."

    name_display = html.escape(user_name.strip()) if user_name else "Candidat"
    subject = f"[{otp_code}] Votre code de vérification — Wadifa Pulse"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="utf-8"></head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f8fafc; padding: 25px; margin: 0; color: #1e293b;">
        <div style="max-width: 540px; margin: 0 auto; background: #ffffff; border-radius: 16px; border: 1px solid #e2e8f0; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.04);">
            <div style="background: linear-gradient(135deg, #15803d, #064e3b); padding: 25px 30px; color: #ffffff;">
                <div style="font-size: 11px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase; opacity: 0.85;">Wadifa Pulse · Sécurité & Authentification</div>
                <h1 style="margin: 8px 0 0 0; font-size: 20px; font-weight: 800;">Vérification de votre adresse email</h1>
            </div>
            
            <div style="padding: 30px; text-align: center;">
                <p style="font-size: 15px; color: #334155; margin-top: 0; text-align: left;">
                    Bonjour <strong>{name_display}</strong>,
                </p>
                <p style="font-size: 14px; color: #64748b; line-height: 1.6; text-align: left;">
                    Merci de vous être inscrit sur Wadifa Pulse. Pour activer votre compte et accéder à votre espace de veille personnalisé, veuillez saisir le code de vérification suivant :
                </p>

                <div style="margin: 30px 0;">
                    <div style="display: inline-block; background-color: #f0fdf4; border: 2px dashed #16a34a; border-radius: 12px; padding: 16px 36px;">
                        <span style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #14532d;">
                            {otp_code}
                        </span>
                    </div>
                </div>

                <p style="font-size: 12px; color: #dc2626; font-weight: 600; margin-bottom: 25px;">
                    ⏳ Ce code expire dans 15 minutes.
                </p>

                <div style="border-top: 1px solid #e2e8f0; padding-top: 20px; font-size: 11px; color: #94a3b8; text-align: left; line-height: 1.5;">
                    Si vous n'êtes pas à l'origine de cette inscription, ignorez simplement ce message. Votre sécurité est notre priorité absolue.<br>
                    <strong>Wadifa Pulse</strong> · Observatoire Autonome de Recrutement
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return send_email_direct(recipient=dest, subject=subject, html_body=html_content)


