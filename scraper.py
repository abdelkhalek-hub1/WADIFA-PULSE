import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime
import config

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

ARABIC_MONTHS = {
    "يناير": 1, "فبراير": 2, "مارس": 3, "أبريل": 4, "ابريل": 4,
    "ماي": 5, "مايو": 5, "يونيو": 6, "يوليوز": 7, "يوليو": 7,
    "غشت": 8, "أغسطس": 8, "شتنبر": 9, "سبتمبر": 9,
    "أكتوبر": 10, "اكتوبر": 10, "نونبر": 11, "نوفمبر": 11,
    "دجنبر": 12, "ديسمبر": 12,
}

def parse_date(date_str: str) -> date | None:
    """يحوّل نص التاريخ (أرقام أو أشهر باللغة العربية) إلى كائن date للمقارنة الدقيقة."""
    if not date_str:
        return None
    
    clean_str = date_str.strip()

    # 1. البحث عن صيغة نصية بالأشهر العربية (مثال: 8 نونبر 2026 أو 30 أكتوبر 2026)
    ar_match = re.search(r'(\d{1,2})\s+([^\d\s\-\:\/]+)\s+(\d{4})', clean_str)
    if ar_match:
        d = int(ar_match.group(1))
        m_name = ar_match.group(2).strip()
        y = int(ar_match.group(3))
        m = ARABIC_MONTHS.get(m_name)
        if m:
            try:
                return date(y, m, d)
            except ValueError:
                pass

    # 2. البحث عن الصيغة القياسية بالأرقام DD/MM/YYYY أو DD-MM-YYYY
    num_match = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', clean_str)
    if num_match:
        d, m, y = map(int, num_match.groups())
        try:
            return date(y, m, d)
        except ValueError:
            pass

    # 3. البحث عن صيغة YYYY-MM-DD
    iso_match = re.search(r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})', clean_str)
    if iso_match:
        y, m, d = map(int, iso_match.groups())
        try:
            return date(y, m, d)
        except ValueError:
            pass

    return None

def is_profile_match(full_text: str) -> tuple[bool, list[str]]:
    """يتحقق ما إذا كان العرض يطابق تخصص Développement Digital / Web Full Stack / Informatique."""
    text_lower = full_text.lower()
    hits = []
    
    # تحقق من الكلمات المفتاحية
    for kw in config.SEARCH_KEYWORDS:
        if kw.lower() in text_lower:
            hits.append(kw)

    # تحقق من الدبلومات
    dip_hits = []
    for dip in config.TARGET_DIPLOMAS:
        if dip.lower() in text_lower:
            dip_hits.append(dip)

    primary_tech_kws = [
        "معلوميات", "تطوير", "رقمي", "ويب", "برمجة", "نظم المعلومات", "الشبكات",
        "informatique", "developpement", "web", "digital", "full stack", "fullstack", "logiciel", "reseaux"
    ]
    
    has_tech_kw = any(tk in hits for tk in primary_tech_kws)
    matched = has_tech_kw and len(hits) > 0
    all_hits = list(set(hits + dip_hits))
    
    return matched, all_hits

# ========================================================
# 1. محرك سحب عروض wadifa-info.com
# ========================================================
def extract_wadifa_details(desc: str):
    """يستخرج آخر أجل والشهادات والتخصصات من نص wadifa-info."""
    deadline_date = None
    deadline_str = ""
    diplomas_str = ""
    specialties_str = ""

    deadline_match = re.search(r'آخر أجل(?: للترشيح)?\s*:\s*([^\.،\n]+)', desc)
    if deadline_match:
        deadline_str = deadline_match.group(1).strip()
        deadline_date = parse_date(deadline_str)
    else:
        date_cand = parse_date(desc)
        if date_cand:
            deadline_date = date_cand
            deadline_str = deadline_date.strftime("%d/%m/%Y")

    dip_match = re.search(r'الشهادات المطلوبة\s*:\s*([^\.،\n]+(?:\.|\n|$))', desc)
    if dip_match:
        diplomas_str = dip_match.group(1).strip().rstrip('.')

    spec_match = re.search(r'التخصصات\s*:\s*([^\.،\n]+(?:\.|\n|$))', desc)
    if spec_match:
        specialties_str = spec_match.group(1).strip().rstrip('.')

    return deadline_date, deadline_str, diplomas_str, specialties_str

def fetch_wadifa_info_jobs() -> list[dict]:
    """يجلب ويحلل العروض من بوابة wadifa-info.com."""
    url = "https://www.wadifa-info.com/rss"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    try:
        response = urllib.request.urlopen(req, timeout=15)
        xml_data = response.read()
    except Exception as e:
        print(f"⚠️ خطأ أثناء جلب wadifa-info: {e}")
        return []

    root = ET.fromstring(xml_data)
    items = root.findall(".//item")
    today = date.today()
    parsed_jobs = []

    for item in items:
        raw_title = item.find("title").text or ""
        link = item.find("link").text or ""
        desc = item.find("description").text or ""

        organism = "غير محدد"
        grade = raw_title.strip()
        if "—" in raw_title:
            parts = raw_title.split("—")
            grade = parts[0].strip()
            organism = parts[1].strip()
        elif " - " in raw_title:
            parts = raw_title.split(" - ")
            grade = parts[0].strip()
            organism = parts[1].strip()

        deadline_date, deadline_str, diplomas_str, specialties_str = extract_wadifa_details(desc)

        # 1. فلترة الأجل
        if deadline_date:
            days_left = (deadline_date - today).days
            if days_left < 0:
                continue
        else:
            days_left = 999

        # 2. فلترة التخصص
        full_text = f"{raw_title} {desc} {specialties_str} {diplomas_str}"
        is_match, matched_kws = is_profile_match(full_text)
        if not is_match:
            continue

        job_id = link.strip() or f"{grade}_{organism}_{deadline_str}"

        parsed_jobs.append({
            "id": job_id,
            "title": raw_title.strip(),
            "grade": grade,
            "organism": organism,
            "deadline_date": deadline_date.isoformat() if deadline_date else "غير محدد",
            "deadline_str": deadline_str or (deadline_date.strftime("%d/%m/%Y") if deadline_date else "راجع الإعلان"),
            "days_left": days_left,
            "diplomas": diplomas_str or "تقني متخصص / ديبلوم جامعي",
            "specialties": specialties_str or "تطوير الويب / المعلوميات والرقمنة",
            "link": link.strip(),
            "source": "wadifa-info.com",
            "date_found": today.strftime("%d/%m/%Y"),
            "matched_keywords": matched_kws,
            "description": desc.strip(),
        })

    return parsed_jobs

# ========================================================
# 2. محرك سحب عروض emploi-public.ma (البوابة الرسمية)
# ========================================================
def fetch_emploi_public_detail(detail_url: str) -> dict:
    """يجلب صفحة تفاصيل المباراة من emploi-public لاستخراج التخصص والشروط الدقيقة."""
    req = urllib.request.Request(detail_url, headers={"User-Agent": USER_AGENT})
    try:
        response = urllib.request.urlopen(req, timeout=12)
        html = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return {}

    specialty = ""
    diploma = ""

    # استخراج التخصص من: <span>تخصص :</span> <strong>- شبكات المعلوميات</strong>
    spec_match = re.search(r'<span>تخصص\s*:?</span>\s*<strong>([^<]+)</strong>', html)
    if spec_match:
        specialty = spec_match.group(1).strip().lstrip("-").strip()

    # استخراج الدرجة
    grade_match = re.search(r'<span>الدرجة\s*:?</span>\s*<strong>([^<]+)</strong>', html)
    if grade_match:
        diploma = grade_match.group(1).strip()

    # رابط قرار فتح المباراة PDF إن وجد
    pdf_match = re.search(r'href="([^"]+/arrete/[^"]+)"', html)
    pdf_link = f"https://www.emploi-public.ma{pdf_match.group(1)}" if pdf_match else ""

    return {
        "specialty": specialty,
        "diploma": diploma,
        "pdf_link": pdf_link,
        "raw_html": html
    }

def fetch_emploi_public_jobs(max_pages: int = 3) -> list[dict]:
    """يجلب العروض الرسمية من بوابة التشغيل العمومي emploi-public.ma."""
    base_url = "https://www.emploi-public.ma"
    list_url_template = f"{base_url}/ar/%D9%82%D8%A7%D8%A6%D9%85%D8%A9-%D8%A7%D9%84%D9%85%D8%A8%D8%A7%D8%B1%D9%8A%D8%A7%D8%AA?page={{page}}"
    
    today = date.today()
    parsed_jobs = []

    for page in range(1, max_pages + 1):
        url = list_url_template.format(page=page)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        
        try:
            response = urllib.request.urlopen(req, timeout=15)
            html = response.read().decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"⚠️ خطأ أثناء جلب emploi-public.ma صفحة {page}: {e}")
            break

        # تقطيع البطاقات الإعلانية عبر البحث عن بطاقات card card-scale
        card_blocks = re.findall(r'<a\s+href="(/ar/[^"]+)"\s+class="card card-scale">(.*?)</a>', html, re.DOTALL)
        
        if not card_blocks:
            break

        for link_path, card_html in card_blocks:
            # 1. نوع البطاقة: نتأكد أنها "الإعلان" (وليست "الاستدعاء" أو "النتائج")
            type_match = re.search(r'<div class="card-type[^"]*">\s*([^<]+)\s*</div>', card_html)
            card_type = type_match.group(1).strip() if type_match else ""
            
            if "الإعلان" not in card_type:
                # تجاهل الاستدعاءات والنتائج
                continue

            # 2. العنوان / المنصب
            title_match = re.search(r'<h[23] class="card-title">\s*([^<]+)\s*</h[23]>', card_html)
            title = title_match.group(1).strip() if title_match else ""

            # 3. الإدارة / الوزارة المنظمة
            org_match = re.search(r'<div class="card-text">(?:<i[^>]*></i>)?\s*([^<]+)\s*</div>', card_html)
            organism = org_match.group(1).strip() if org_match else "غير محدد"

            # 4. آخر أجل
            deadline_match = re.search(r'آخر أجل لإيداع ملفات الترشيح\s*:\s*([^\n<]+)', card_html)
            deadline_raw = deadline_match.group(1).strip() if deadline_match else ""
            
            deadline_date = parse_date(deadline_raw)
            if deadline_date:
                days_left = (deadline_date - today).days
                if days_left < 0:
                    # منتهي الأجل
                    continue
            else:
                days_left = 999

            full_link = f"{base_url}{link_path.strip()}"

            # 5. فحص ما إذا كان العنوان يشير إلى تخصص تقني أو معلوميات
            candidate_text = f"{title} {organism}"
            is_match, matched_kws = is_profile_match(candidate_text)

            # إذا كان المنصب هو "تقني" أو "مهندس" بدون تحديد، ندخل لصفحة التفاصيل للتحقق من التخصص الدقيق
            specialty_detail = ""
            diploma_detail = ""
            if not is_match and ("تقني" in title or "متصرف" in title or "مهندس" in title):
                detail_data = fetch_emploi_public_detail(full_link)
                specialty_detail = detail_data.get("specialty", "")
                diploma_detail = detail_data.get("diploma", "")
                
                check_text = f"{title} {organism} {specialty_detail} {diploma_detail}"
                is_match, matched_kws = is_profile_match(check_text)

            if not is_match:
                continue

            job_id = full_link

            parsed_jobs.append({
                "id": job_id,
                "title": title,
                "grade": title,
                "organism": organism,
                "deadline_date": deadline_date.isoformat() if deadline_date else "غير محدد",
                "deadline_str": deadline_date.strftime("%d/%m/%Y") if deadline_date else deadline_raw,
                "days_left": days_left,
                "diplomas": diploma_detail or "تقني متخصص / Bac+2 / Bac+3",
                "specialties": specialty_detail or "تطوير رقمي / ويب / معلوميات",
                "link": full_link,
                "source": "emploi-public.ma",
                "date_found": today.strftime("%d/%m/%Y"),
                "matched_keywords": matched_kws,
                "description": f"مباراة توظيف بـ {organism}. آخر أجل: {deadline_raw}",
            })

    return parsed_jobs

# ========================================================
# 3. الجمع والدمج وإزالة التكرار (Deduplication)
# ========================================================
def normalize_text(text: str) -> str:
    """تنظيف النص للمقارنة بين الموقعين ومنع التكرار."""
    t = text.lower()
    t = re.sub(r'[\s\-_،\.]+', '', t)
    t = t.replace("وزارة", "").replace("الدرجة", "").replace("سلم", "")
    return t

def fetch_all_jobs() -> list[dict]:
    """Récupère et fusionne les concours depuis emploi-public.ma et wadifa-info.com."""
    print("🔍 [1/2] Récupération des concours depuis wadifa-info.com...")
    wadifa_jobs = fetch_wadifa_info_jobs()
    print(f"   ↳ {len(wadifa_jobs)} concours correspondant(s) trouvé(s) sur wadifa-info.com")

    print("🔍 [2/2] Récupération des concours depuis le portail officiel emploi-public.ma...")
    emploi_jobs = fetch_emploi_public_jobs(max_pages=3)
    print(f"   ↳ {len(emploi_jobs)} concours correspondant(s) trouvé(s) sur emploi-public.ma")

    merged_jobs = []
    seen_keys = set()
    all_raw_jobs = emploi_jobs + wadifa_jobs

    for j in all_raw_jobs:
        norm_key = f"{normalize_text(j['organism'])}_{normalize_text(j['grade'])}_{j['deadline_str']}"
        if norm_key in seen_keys:
            continue
        seen_keys.add(norm_key)
        merged_jobs.append(j)

    merged_jobs.sort(key=lambda x: x["days_left"])
    print(f"\n🎯 Total concours valides et correspondants pour {config.PROFILE_NAME} : {len(merged_jobs)}")
    return merged_jobs

if __name__ == "__main__":
    jobs = fetch_all_jobs()
    for i, j in enumerate(jobs, 1):
        print(f"\n[{i}] {j['grade']}")
        print(f"    المؤسسة: {j['organism']}")
        print(f"    المصدر: {j['source']}")
        print(f"    آخر أجل: {j['deadline_str']} (باقي: {j['days_left']} يوم)")
        print(f"    الرابط: {j['link']}")
