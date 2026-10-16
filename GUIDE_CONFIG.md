# 📖 الدليل الشامل للإعداد السريع (Telegram, WhatsApp, Google Sheets)

---

## 1️⃣ تفعيل إشعارات الهاتف عبر Telegram Bot (أحسن وأسهل خيار مجاني 100%)

إذا ما بغيتيش تخدم بـ CallMeBot ديال واتساب، **Telegram Bot** هو أفضل بديل فـ العالم:
* رسمي، مجاني مدى الحياة، وما فيه حتى شي تقييد.
* كيوصلك إشعار فوري فيه صوت فـ التيليفون ديالك مع الروابط منسقة.

### الخطوات (فـ دقيقة واحدة):
1. افتح تطبيق **Telegram** فـ هاتفك.
2. فـ خانة البحث اكتب: **`@BotFather`** (عندو علامة زرقاء ✓).
3. ضغط على **Start** واكتب له:
   ```text
   /newbot
   ```
4. غادي يطلب منك تسمي البوت ديالك (مثلاً: `Wadifa Notifier`).
5. ثم اكتب اسم مستخدم ينتهي بـ bot (مثلاً: `my_wadifa_job_bot`).
6. غادي يعطيك كود طويل سميتو **Token** (مثال: `7123456789:AAFn_XXXXXXX...`).
7. دابا دخل للبحث فـ تيليغرام واكتب: **`@userinfobot`** وضغط Start، غادي يعطيك الـ **Id** ديالك (مثال: `987654321`).
8. دخل لـ البوت اللي صاوبتي وضغط **Start** باش يقدر يصيفط ليك.
9. افتح ملف `.env` وحط فيه التوكن والأيدي:
   ```env
   TELEGRAM_ENABLED=true
   TELEGRAM_BOT_TOKEN=7123456789:AAFn_XXXXXXX...
   TELEGRAM_CHAT_ID=987654321
   ```

---

## 2️⃣ تفعيل WhatsApp (CallMeBot) — إن أردته

إذا بغيتي واتساب:
1. أرسل من هاتفك في واتساب رسالة إلى: **`+34 941 86 07 41`**
2. اكتب له:
   ```text
   I allow callmebot to send me messages
   ```
3. سيعطيك كود `API Key`.
4. ضعه في `.env`:
   ```env
   WHATSAPP_ENABLED=true
   WHATSAPP_PHONE=2126XXXXXXXX
   WHATSAPP_API_KEY=123456
   ```

---

## 3️⃣ تفعيل Google Sheets (طريقة سهلة جداً فـ دقيقة واحدة وبدون Google Cloud)

باش ما تحتاجش تدخل لـ Google Cloud Console وتصاوب Service Account معقد:

1. افتح صفحة جديدة في: [sheets.new](https://sheets.new)
2. في القائمة الفوقانية، اضغط على: **Extensions (الإضافات)** ➔ **Apps Script**.
3. امسح أي كود موجود وضع هذا الكود البسيط مكانه:

```javascript
function doPost(e) {
  var data = JSON.parse(e.postData.contents);
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.clear();
  sheet.appendRow(["الحالة", "المؤسسة / الإدارة", "المنصب والدرجة", "الشهادات المطلوبة", "التخصص", "آخر أجل", "الأيام المتبقية", "المصدر", "رابط الإعلان"]);
  for (var i = 0; i < data.jobs.length; i++) {
    var j = data.jobs[i];
    var status = j.days_left <= 3 ? "🚨 عاجل" : (j.days_left <= 7 ? "⏳ قريب" : "🟢 صالح");
    sheet.appendRow([status, j.organism, j.grade, j.diplomas, j.specialties, j.deadline_str, j.days_left, j.source, j.link]);
  }
  return ContentService.createTextOutput("OK");
}
```

4. في أعلى اليمين اضغط على الزر الأزرق **Deploy (نشر)** ➔ **New deployment (نشر جديد)**.
5. اضغط على رمز الترس ⚙️ واختر **Web app (تطبيق ويب)**.
6. في خانة **Who has access (من يمكنه الوصول)**: اختر **Anyone (أي شخص)**.
7. اضغط **Deploy** وانسخ الرابط الذي سينتهي بـ `/exec`.
8. ضعه في ملف `.env`:
   ```env
   GOOGLE_SHEETS_ENABLED=true
   GOOGLE_SHEET_WEBHOOK_URL=https://script.google.com/macros/s/AKfycbx.../exec
   SPREADSHEET_URL=https://docs.google.com/spreadsheets/d/حط_رابط_الشيت_ديالك_هنا/edit
   ```

---

## 4️⃣ تشغيل التجربة (Lancer le test)

الآن افتح Terminal ونفذ:
```powershell
python main.py
```
ستلاحظ أن البرنامج:
1. جلب العروض من `emploi-public.ma` و `wadifa-info.com`.
2. استخرج المناصب الخاصة بـ **Full Stack / Informatique**.
3. حدّث جدول **Google Sheets** أونلاين.
4. أنشأ ملف **HTML** و **Excel** محلياً.
5. أرسل التنبيه مباشرة إلى هاتفك عبر **Telegram** أو **WhatsApp** أو **Email**!
