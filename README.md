# MuddatAI Bot

Telegram orqali qarzlaringiz va shaxsiy eslatmalaringizni kuzatib, **har kuni ertalab**
(standart 08:00, Toshkent vaqti) avtomatik eslatib turadigan bot.

## 1. Botni Telegram'da yaratish

Siz allaqachon **@MuddatAI_bot** nomini tanlagansiz. Agar bot hali @BotFather orqali
ro'yxatdan o'tkazilmagan bo'lsa:

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing
2. `/newbot` buyrug'ini yuboring
3. Bot nomini so'rasa: `MuddatAI` (yoki xohlagan nom)
4. Username so'rasa: `MuddatAI_bot`
5. BotFather sizga **token** beradi, masalan: `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   — shu tokenni saqlab qo'ying, hech kimga bermang.

## 2. Kompyuterda ishga tushirish

```bash
# 1) kutubxonalarni o'rnatish
pip install -r requirements.txt

# 2) tokenni muhit o'zgaruvchisiga qo'yish
export BOT_TOKEN="SIZNING_TOKENINGIZ"

# 3) botni ishga tushirish
python bot.py
```

Terminalda `MuddatAI bot ishga tushdi...` degan yozuv chiqsa — bot ishlayapti.
Endi Telegram'da @MuddatAI_bot'ni topib, `/start` bosing.

**Muhim:** Bot faqat kompyuter/server ishlab turgan vaqtda ishlaydi. Kompyuterni
o'chirsangiz, bot ham to'xtaydi va kunlik eslatmalar yuborilmaydi.

## 3. 24/7 ishlashi uchun (serverga joylashtirish)

Botni doim onlayn ushlab turish uchun uni bepul/arzon serverga joylashtirish tavsiya
etiladi. Eng oddiy variantlar:

### Variant A — Railway.app (bepul tarif bor, eng oson)
1. https://railway.app saytida ro'yxatdan o'ting
2. "New Project" → "Deploy from GitHub repo" (kodni avval GitHub'ga yuklang)
3. Environment Variables bo'limiga `BOT_TOKEN` ni qo'shing
4. Start command: `python bot.py`

### Variant B — VPS (masalan, arzon Timeweb, DigitalOcean va h.k.)
```bash
# serverda:
git clone <repo>   # yoki fayllarni yuklang
cd muddatai_bot
pip install -r requirements.txt
export BOT_TOKEN="SIZNING_TOKENINGIZ"

# doimiy ishlashi uchun screen yoki systemd ishlating:
screen -S muddatai
python bot.py
# Ctrl+A, keyin D bosib chiqing (screen fonda ishlayveradi)
```

### Variant C — systemd xizmati (VPS uchun tavsiya etiladi)
`/etc/systemd/system/muddatai.service` fayl yarating:
```ini
[Unit]
Description=MuddatAI Telegram Bot
After=network.target

[Service]
WorkingDirectory=/home/USER/muddatai_bot
Environment="BOT_TOKEN=SIZNING_TOKENINGIZ"
ExecStart=/usr/bin/python3 bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```
Keyin:
```bash
sudo systemctl enable muddatai
sudo systemctl start muddatai
```

## 4. Botdan foydalanish (buyruqlar)

| Buyruq | Vazifasi |
|---|---|
| `/start` | Botni ishga tushirish, tanishtirish |
| `/qarz_oldim Kimdan \| Summa \| Muddat \| Izoh` | Siz oldingiz qarzni qo'shish |
| `/qarz_berdim Kimga \| Summa \| Muddat \| Izoh` | Siz bergan qarzni qo'shish |
| `/qarzlar` | Barcha ochiq qarzlar ro'yxati |
| `/tolandi ID` | Qarzni "to'landi" deb belgilash |
| `/ochir ID` | Qarzni o'chirish |
| `/eslatma Matn` | Oddiy eslatma qo'shish |
| `/eslatmalar` | Eslatmalar ro'yxati |
| `/eslatma_ochir ID` | Eslatmani o'chirish |
| `/bugun` | Hozir qolgan qarz/eslatmalarni ko'rish |
| `/vaqt HH:MM` | Kunlik eslatma vaqtini o'zgartirish (masalan `/vaqt 07:30`) |
| `/yordam` | To'liq yordam matni |

### Misol

```
/qarz_oldim Aziz | 500000 | 25.09.2026 | mashina ta'miri uchun
/qarz_berdim Vali | 300000 | | dўstga qarz berdim
/vaqt 07:30
```

Har kuni soat 07:30 da bot avtomatik ravishda barcha ochiq qarzlaringiz va
eslatmalaringizni ro'yxat qilib yuboradi.

## 5. Ma'lumotlar qayerda saqlanadi?

Barcha ma'lumotlar botni ishga tushirgan joydagi `muddatai.db` (SQLite) faylida
saqlanadi. Bu faylni zaxira nusxalab turishni unutmang, agar serverni almashtirsangiz
shu faylni ham ko'chiring.
