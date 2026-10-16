import os
import json
import csv
import urllib.request
from datetime import date
from . import config

def export_to_html(jobs: list[dict], output_path: str = config.HTML_OUTPUT):
    """Génère un tableau de bord HTML interactif et moderne en français."""
    today_str = date.today().strftime("%d/%m/%Y")
    
    rows_html = ""
    for j in jobs:
        days = j["days_left"]
        if days <= 3:
            badge_class = "badge-danger"
            badge_text = f"🚨 {days} j restant(s)"
        elif days <= 7:
            badge_class = "badge-warning"
            badge_text = f"⏳ {days} j restants"
        else:
            badge_class = "badge-success"
            badge_text = f"🟢 {days} jours"

        source_badge = "source-official" if "emploi-public" in j.get("source", "") else "source-wadifa"
        source_label = "emploi-public.ma (Officiel)" if "emploi-public" in j.get("source", "") else "wadifa-info.com"

        rows_html += f"""
        <tr>
            <td class="font-bold">{j['organism']}</td>
            <td><strong>{j['grade']}</strong></td>
            <td><span class="tag">{j['diplomas']}</span></td>
            <td><span class="tag-spec">{j['specialties']}</span></td>
            <td class="deadline">{j['deadline_str']}</td>
            <td><span class="badge {badge_class}">{badge_text}</span></td>
            <td><span class="source-tag {source_badge}">{source_label}</span></td>
            <td><a href="{j['link']}" target="_blank" class="btn-link">Détails & Postuler 🔗</a></td>
        </tr>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="fr" dir="ltr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Concours Fonction Publique Maroc — {config.PROFILE_NAME}</title>
    <style>
        :root {{
            --primary: #15803d;
            --primary-dark: #166534;
            --bg: #f8fafc;
            --card-bg: #ffffff;
            --text: #1e293b;
            --border: #e2e8f0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 24px;
        }}
        .container {{
            max-width: 1300px;
            margin: 0 auto;
        }}
        .header {{
            background: linear-gradient(135deg, #15803d, #047857);
            color: white;
            padding: 28px 32px;
            border-radius: 14px;
            margin-bottom: 24px;
            box-shadow: 0 4px 15px rgba(21, 128, 61, 0.2);
        }}
        .header h1 {{ margin: 0 0 8px 0; font-size: 1.6rem; }}
        .header p {{ margin: 0; opacity: 0.95; font-size: 1rem; }}
        .stats {{
            display: flex;
            gap: 15px;
            margin-top: 18px;
            flex-wrap: wrap;
        }}
        .stat-box {{
            background: rgba(255, 255, 255, 0.18);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
        }}
        .table-card {{
            background: var(--card-bg);
            border-radius: 12px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            overflow-x: auto;
            border: 1px solid var(--border);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.92rem;
            min-width: 950px;
        }}
        th {{
            background: #f1f5f9;
            color: #475569;
            padding: 14px 16px;
            font-weight: 600;
            border-bottom: 2px solid var(--border);
        }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid var(--border);
            vertical-align: middle;
        }}
        tr:hover {{ background-color: #f8fafc; }}
        .font-bold {{ font-weight: 600; color: #0f172a; }}
        .badge {{
            display: inline-block;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 0.82rem;
            font-weight: 600;
            white-space: nowrap;
        }}
        .badge-success {{ background: #dcfce7; color: #15803d; }}
        .badge-warning {{ background: #fef9c3; color: #a16207; }}
        .badge-danger {{ background: #fee2e2; color: #b91c1c; }}
        .source-tag {{
            display: inline-block;
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .source-official {{ background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; }}
        .source-wadifa {{ background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }}
        .tag {{
            background: #f1f5f9;
            color: #334155;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.82rem;
            display: inline-block;
        }}
        .tag-spec {{
            background: #e0f2fe;
            color: #0369a1;
            padding: 4px 8px;
            border-radius: 6px;
            font-size: 0.82rem;
            display: inline-block;
        }}
        .btn-link {{
            display: inline-block;
            background: #2563eb;
            color: white;
            text-decoration: none;
            padding: 7px 14px;
            border-radius: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            transition: background 0.2s;
            white-space: nowrap;
        }}
        .btn-link:hover {{ background: #1d4ed8; }}
        .deadline {{ font-weight: 700; color: #0f172a; white-space: nowrap; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📋 Concours Fonction Publique Maroc — Offres Actives</h1>
            <p>Profil : <strong>{config.PROFILE_NAME}</strong></p>
            <div class="stats">
                <div class="stat-box">🎯 Total concours actifs : <strong>{len(jobs)}</strong></div>
                <div class="stat-box">🌐 Sources : <strong>emploi-public.ma + wadifa-info.com</strong></div>
                <div class="stat-box">🕒 Mise à jour : <strong>{today_str}</strong></div>
            </div>
        </div>

        <div class="table-card">
            <table>
                <thead>
                    <tr>
                        <th>Organisme / Ministère</th>
                        <th>Poste & Grade</th>
                        <th>Diplôme requis</th>
                        <th>Spécialité</th>
                        <th>Date limite</th>
                        <th>Délai</th>
                        <th>Source</th>
                        <th>Candidature</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html if jobs else '<tr><td colspan="8" style="text-align:center; padding:30px;">Aucun concours actif correspondant trouvé pour le moment.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"📄 Dashboard HTML enregistré : {output_path}")

def export_to_excel_or_csv(jobs: list[dict], output_path: str = config.EXCEL_OUTPUT):
    """Enregistre les concours en fichier Excel (.xlsx) avec en-têtes en français."""
    headers = [
        "Organisme / Ministère", "Poste / Grade", "Diplôme requis",
        "Spécialité", "Date limite", "Jours restants", "Source", "Lien de l'offre", "Date de détection"
    ]
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Concours Actifs"
        ws.append(headers)
        
        for j in jobs:
            ws.append([
                j["organism"],
                j["grade"],
                j["diplomas"],
                j["specialties"],
                j["deadline_str"],
                j["days_left"],
                j.get("source", "emploi-public"),
                j["link"],
                j["date_found"]
            ])
            
        wb.save(output_path)
        print(f"📊 Fichier Excel généré : {output_path}")
    except ImportError:
        csv_path = output_path.replace(".xlsx", ".csv")
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for j in jobs:
                writer.writerow([
                    j["organism"], j["grade"], j["diplomas"], j["specialties"],
                    j["deadline_str"], j["days_left"], j.get("source", "emploi-public"), j["link"], j["date_found"]
                ])
        print(f"📊 Fichier CSV généré : {csv_path}")

def update_google_sheets_webhook(jobs: list[dict]) -> bool:
    """Met à jour Google Sheets via Apps Script Webhook."""
    if not config.GOOGLE_SHEET_WEBHOOK_URL:
        return False
    
    try:
        payload = json.dumps({"jobs": jobs}).encode("utf-8")
        req = urllib.request.Request(
            config.GOOGLE_SHEET_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "text/plain;charset=utf-8",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        resp = urllib.request.urlopen(req, timeout=25)
        print("✅ Google Sheets mis à jour avec succès via Webhook !")
        return True
    except urllib.error.HTTPError as e:
        print(f"⚠️ Erreur Google Sheets Webhook ({e.code}) : {e.reason}")
        return False
    except Exception as e:
        print(f"⚠️ Erreur Google Sheets Webhook : {e}")
        return False

def update_google_sheets_api(jobs: list[dict]) -> str | None:
    """Met à jour Google Sheets via l'API officielle Service Account."""
    if not config.SPREADSHEET_ID:
        return None

    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return None

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = None
    if config.GOOGLE_SERVICE_ACCOUNT_JSON:
        info = json.loads(config.GOOGLE_SERVICE_ACCOUNT_JSON)
        creds = Credentials.from_service_account_info(info, scopes=scopes)
    elif os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(config.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        return None

    try:
        client = gspread.authorize(creds)
        sheet = client.open_by_key(config.SPREADSHEET_ID).sheet1
        sheet.clear()

        headers = [
            "Statut", "Organisme / Ministère", "Poste & Grade", "Diplôme requis",
            "Spécialité", "Date limite", "Jours restants", "Source", "Lien de l'offre", "Mise à jour"
        ]
        
        rows = [headers]
        for j in jobs:
            status = "🚨 Urgent (≤ 3j)" if j["days_left"] <= 3 else ("⏳ Proche (≤ 7j)" if j["days_left"] <= 7 else "🟢 Valide")
            rows.append([
                status, j["organism"], j["grade"], j["diplomas"], j["specialties"],
                j["deadline_str"], j["days_left"], j.get("source", "emploi-public"), j["link"], j["date_found"]
            ])

        sheet.update("A1", rows)
        sheet_url = f"https://docs.google.com/spreadsheets/d/{config.SPREADSHEET_ID}/edit"
        print(f"✅ Google Sheets synchronisé : {sheet_url}")
        return sheet_url
    except Exception as e:
        print(f"❌ Erreur lors de la mise à jour Google Sheets : {e}")
        return None

def sync_all_storage(jobs: list[dict]) -> str | None:
    export_to_html(jobs)
    export_to_excel_or_csv(jobs)
    
    if config.GOOGLE_SHEETS_ENABLED:
        if config.GOOGLE_SHEET_WEBHOOK_URL:
            update_google_sheets_webhook(jobs)
        elif config.SPREADSHEET_ID:
            update_google_sheets_api(jobs)

    return config.SPREADSHEET_URL
