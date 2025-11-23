# 📱 Telegram Bot Setup Guide

## ✅ Telegram Bot তৈরি হয়েছে!

এখন stats Telegram-এ দেখবেন, browser-এ নয়।

---

## 🔧 Setup করুন:

### **Step 1: Telegram Bot Token নিন**

1. Telegram-এ **@BotFather** খুঁজুন
2. `/newbot` command দিন
3. Bot name দিন (যেমন: `My Copy Trading Bot`)
4. Bot username দিন (যেমন: `my_copy_trading_bot`)
5. **Token** copy করুন (যেমন: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### **Step 2: Chat ID নিন**

1. আপনার bot-এ একটি message পাঠান
2. Browser-এ যান:
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   (Replace `<YOUR_TOKEN>` আপনার token দিয়ে)
3. Response-এ `"chat":{"id":123456789}` খুঁজুন
4. এই `id` হলো আপনার Chat ID

### **Step 3: .env ফাইলে যোগ করুন**

`.env` ফাইলে এই দুটি line যোগ করুন:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### **Step 4: Package Install করুন**

```bash
pip install python-telegram-bot
```

---

## 🚀 এখন ব্যবহার করুন:

1. **Bot run করুন:**
   ```bash
   python main.py
   ```

2. **Telegram-এ stats দেখুন:**
   - Bot automatically startup message পাঠাবে
   - Trade হলে notification পাঠাবে
   - `/stats` command দিয়ে stats দেখতে পারবেন

---

## 📱 Telegram Commands:

- `/start` - Bot info দেখুন
- `/stats` - Current stats দেখুন
- `/status` - Bot status দেখুন

---

## ✅ Done!

এখন সব stats Telegram-এ দেখবেন। Browser dashboard আর দরকার নেই! 🎉

