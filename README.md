# Shaxsiy Yordamchi Bot

## 1. Telegram bot yaratish
1. Telegram'da **@BotFather** ga yozing.
2. `/newbot` buyrug'ini yuboring va bot nomini tanlang.
3. Sizga **token** beriladi (masalan: `123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11`).

## 2. Kompyuterda sozlash
```bash
# Papkaga o'ting
cd yordamchi_bot

# Virtual muhit yaratish (tavsiya etiladi)
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

## 3. Tokenni kiritish
`bot.py` faylini oching va quyidagi qatorni toping:
```python
BOT_TOKEN = "BU_YERGA_OZ_TOKENINGIZNI_QOYING"
```
O'rniga BotFather bergan tokeningizni qo'ying.

## 4. Botni ishga tushirish
```bash
python bot.py
```
Terminalda "Bot ishga tushdi..." degan xabarni ko'rsangiz — tayyor. Endi Telegram'da botingizga o'ting va `/start` yozing.

## 5. Barcha buyruqlar
Botga `/help` yozing — barcha mavjud buyruqlar chiqadi:
- `/todo_add`, `/todo_list`, `/todo_done` — vazifalar
- `/remind` — eslatma
- `/note_add`, `/note_list` — yozuvlar
- `/expense_add`, `/expense_report` — xarajatlar
- `/shopping_add`, `/shopping_list`, `/shopping_clear` — xarid ro'yxati
- `/habit_add`, `/habit_done`, `/habit_list` — odatlar
- `/water_on`, `/water_off` — suv ichish eslatmasi

## 6. Doimiy ishlashi uchun (server)
Kompyuteringizni o'chirsangiz bot ham to'xtaydi. Doimiy ishlashi uchun:
- Arzon VPS (masalan DigitalOcean, Timeweb) sotib oling
- Yoki `screen`/`tmux` yoki `systemd` service qilib background'da qoldiring:
```bash
nohup python bot.py &
```

## 7. Keyingi qadamlar (kengaytirish)
Agar xohlasangiz, quyidagilarni ham qo'shsa bo'ladi:
- AI orqali savol-javob (Anthropic/OpenAI API bilan)
- Ob-havo va valyuta kursi
- Fayllarni saqlash/qidirish
- Ovozli xabarlarni matnga aylantirish

Shu narsalarni qo'shishni xohlasangiz — ayting, kodini yozib beraman.

## Muhim eslatma
`bot.db` fayli — bu SQLite bazasi, barcha ma'lumotlaringiz (vazifalar, yozuvlar, xarajatlar va h.k.) shu faylda saqlanadi. Uni yo'qotmang, zaxira nusxasini olib turing.
