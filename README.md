# Shaxsiy Yordamchi Bot

## Fayllar tarkibi
- `bot.py` — asosiy bot kodi
- `requirements.txt` — kerakli kutubxonalar
- `Procfile` — Railway'ga qaysi buyruq bilan ishga tushirishni aytadi
- `.gitignore` — GitHub'ga yuklanmasligi kerak bo'lgan fayllar

## 1. GitHub'ga yuklash
1. Repositoriyangizdagi **eskirgan barcha fayllarni o'chiring** (bot.py, requirements.txt va h.k.) — eski va yangi fayllar aralashib qolmasligi uchun.
2. Shu papkadagi 4 ta faylni ("Add file" → "Upload files") repoga yuklang: `bot.py`, `requirements.txt`, `Procfile`, `.gitignore`
3. Commit qiling ("Commit changes").

## 2. Telegram bot yaratish (agar hali qilmagan bo'lsangiz)
1. Telegram'da **@BotFather** ga yozing.
2. `/newbot` yuboring, nom bering.
3. Sizga beriladigan **tokenni** saqlab qo'ying.

## 3. Railway'da BOT_TOKEN sozlash
1. Railway loyihangizga kiring → **Variables** bo'limi.
2. Yangi o'zgaruvchi qo'shing:
   - Name: `BOT_TOKEN`
   - Value: BotFather bergan haqiqiy token
3. Saqlang — Railway avtomatik qayta deploy qiladi.

## 4. Deploy holatini tekshirish
- **Deployments** bo'limida oxirgi deploy yashil ✅ ("Active") bo'lishi kerak.
- Agar qizil ❌ ("Failed") bo'lsa — o'sha deploy'ni bosing → **View logs** → oxirgi xato matnini menga tashlang.

## 5. Botni sinash
Telegram'da botingizga o'ting va yozing:
```
/start
/help
```
Agar javob kelsa — bot ishlayapti.

## Barcha buyruqlar
- `/todo_add`, `/todo_list`, `/todo_done` — vazifalar
- `/remind <daqiqa> <matn>` — eslatma
- `/note_add`, `/note_list` — yozuvlar
- `/expense_add <summa> <kategoriya>`, `/expense_report` — xarajatlar
- `/shopping_add`, `/shopping_list`, `/shopping_clear` — xarid ro'yxati
- `/habit_add`, `/habit_done`, `/habit_list` — odatlar
- `/water_on`, `/water_off` — suv ichish eslatmasi

## Muhim eslatma
Kod ichida token **yozilmagan** — u faqat Railway'ning Variables bo'limidan o'qiladi (`os.environ.get("BOT_TOKEN")`). Shuning uchun agar `BOT_TOKEN` o'rnatilmagan bo'lsa, bot aniq xato xabari bilan to'xtaydi: "BOT_TOKEN topilmadi!" — bu Railway loglarida ko'rinadi.
