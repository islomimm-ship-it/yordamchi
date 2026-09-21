# Sarhisob ULTRA Bot

Telegram orqali **kreditlar, xarajatlar, vazifalar, maqsadlar, muhim eslatmalar**
va **ish/sog'liq/sport rejalarini** kuzatuvchi bot. Barcha amallar **tugmalar**
orqali bajariladi — ID yoki maxsus format yozish shart emas.

Har kuni belgilangan vaqtda (standart 08:00, Toshkent vaqti) bot to'liq kunlik
sarhisobni avtomatik yuboradi.

## ⚠️ Xavfsizlik haqida eslatma

Bot tokenini **hech qachon** kod ichiga yozmang. U faqat muhit o'zgaruvchisi
(`BOT_TOKEN`) orqali beriladi. Agar token qачонdir ochiq joyda (chat, skrinshot,
GitHub'da ommaviy repo) ko'ringan bo'lsa — @BotFather orqali darhol bekor qilib,
yangisini oling (`/mybots` → botni tanlang → API Token → Revoke current token).

## 1. Botni Telegram'da yaratish / tokenni olish

1. Telegram'da [@BotFather](https://t.me/BotFather) ga yozing
2. Yangi bot uchun `/newbot`, mavjud bot tokenini olish uchun `/mybots` →
   botingizni tanlang → "API Token"
3. Tokenni saqlab qo'ying — bu faqat Railway'ning Variables bo'limiga kiritiladi

## 2. Kompyuterda ishga tushirish

```bash
pip install -r requirements.txt
export BOT_TOKEN="SIZNING_TOKENINGIZ"
python bot.py
```

## 3. GitHub'ga yuklash (kod yangilanganda)

Agar avval repo yaratgan bo'lsangiz (masalan "yordamchi"):

1. GitHub'da repo sahifangizga kiring
2. Eski `bot.py` faylini oching, qalam (✏️) belgisini bosib tahrirlash rejimiga
   o'ting, ichidagi barcha matnni o'chirib, yangi `bot.py` mazmunini joylashtiring
   — YOKI eski faylni o'chirib (Delete file), yangisini "Add file → Upload files"
   orqali yuklang
3. Pastda "Commit changes" tugmasini bosing

**Railway avtomatik payqaydi va botni qayta deploy qiladi** — hech qanday qo'shimcha
amal shart emas, chunki Railway GitHub repo'ga ulangan (har safar `main` branch
o'zgarganda o'zi qayta ishga tushadi).

## 4. Railway'da BOT_TOKEN'ni yangilash (agar tokenni almashtirgan bo'lsangiz)

1. Railway loyihangizga kiring → servis (bot) ustiga bosing
2. "Variables" bo'limiga o'ting
3. `BOT_TOKEN` qatori ustida uch nuqta (⋮) → "Edit" → yangi tokenni kiriting → saqlang
4. Railway avtomatik qayta ishga tushadi

## 5. Botdan foydalanish (hammasi tugmalar orqali)

`/start` bosgach pastda doimiy menyu chiqadi:

**Bosh menyu:** 💳 Kreditlar | 💸 Xarajatlar | 📋 Vazifalar | 🎯 Maqsadlar |
📌 Muhimlar | 🗓 Rejalar | ⚙️ Sozlamalar | 📅 Bugungi holat

- **💳 Kreditlar** — kredit/qarz qo'shish (kimga, summa, har oyning nechinchi
  kunida to'lanadi — tugmadan tanlanadi), ro'yxatni ko'rish, qisman yoki to'liq
  to'lov kiritish (tugma orqali kerakli kreditni tanlaysiz).
- **💸 Xarajatlar** — xarajat qo'shish (summa + toifa tugmadan tanlanadi),
  **📊 Oylik xarajatlarim** (◀️▶️ tugmalari bilan boshqa oylarni ham ko'rish),
  **💰 Limit belgilash** — oylik byudjet chegarasi, oshib ketsa ogohlantiradi.
- **📋 Vazifalar** — kunlik vazifa qo'shish, ro'yxatni ko'rish, bajarilganini
  tugma bilan belgilash (muddati o'tgan bajarilmagan vazifalar avtomatik
  "bajarilmadi" deb belgilanadi).
- **🎯 Maqsadlar** — maqsad qo'shish (muddat bilan yoki muddatsiz), ro'yxat,
  erishilganini tugma bilan belgilash.
- **📌 Muhimlar** — muhim eslatmalar qo'shish/ko'rish/o'chirish (har kuni
  ertalabki xabarda ham ko'rinadi).
- **🗓 Rejalar** — 🏛 Davlat ishi / 💊 Sog'liq / ⚽ Sport bo'yicha takrorlanuvchi
  rejalar (masalan "Vitamin D ichish — har kuni ertalab").
- **⚙️ Sozlamalar** — kunlik xabar vaqtini o'zgartirish.
- **📅 Bugungi holat** — hozirgi to'liq sarhisobni darhol ko'rsatadi.

Har qanday jarayonda "❌ Bekor qilish" tugmasi bilan chiqib ketishingiz mumkin.

## 6. Ma'lumotlar qayerda saqlanadi?

Barcha ma'lumotlar `sarhisob_ultra.db` (SQLite) faylida saqlanadi. Railway'da bu
fayl konteyner ichida turadi — agar loyihani o'chirib qayta yaratsangiz, eski
ma'lumotlar yo'qoladi. Uzoq muddatli foydalanish uchun Railway'ning "Volume"
xizmatidan foydalanish tavsiya etiladi (ixtiyoriy, so'rasangiz shuni ham
sozlab beraman).
