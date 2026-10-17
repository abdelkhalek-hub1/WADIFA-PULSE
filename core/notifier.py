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
