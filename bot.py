import os
import json
import asyncio
from telethon import TelegramClient, events, errors
from features import configure_event_handlers  # Import fitur tambahan

# Load konfigurasi dari file
CONFIG_FILE = 'config.json'
if not os.path.exists(CONFIG_FILE):
    raise FileNotFoundError(f"File konfigurasi '{CONFIG_FILE}' tidak ditemukan.")

with open(CONFIG_FILE, 'r') as f:
    config = json.load(f)

api_id = config.get('api_id')
api_hash = config.get('api_hash')
bot_token = config.get('bot_token')

if not api_id or not api_hash or not bot_token:
    raise ValueError("API ID, API Hash, dan Bot Token harus diisi di config.json.")

# Direktori untuk menyimpan sesi
SESSION_DIR = 'sessions'
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

# Inisialisasi bot utama
bot_client = TelegramClient('bot_session', api_id, api_hash)

# Dictionary untuk menyimpan sesi pengguna sementara
user_sessions = {}  # Struktur: {user_id: {'client': TelegramClient, 'phone': str}}

@bot_client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply(
        "Selamat datang di bot multi-login! 😊\n"
        "Masukkan nomor telepon Anda dengan mengetik:\n"
        "`/login <Nomor Telepon>` (contoh: /login +628123456789)"
    )

@bot_client.on(events.NewMessage(pattern='/login (.+)'))
async def login(event):
    sender = await event.get_sender()
    user_id = sender.id
    phone = event.pattern_match.group(1)

    if user_id in user_sessions and user_sessions[user_id]["phone"] == phone:
        await event.reply("⚠️ Anda sudah login dengan nomor ini. Tidak perlu login lagi.")
        return

    session_file = os.path.join(SESSION_DIR, f'{user_id}_{phone.replace("+", "")}.session')
    user_client = TelegramClient(session_file, api_id, api_hash)

    await user_client.connect()

    if not await user_client.is_user_authorized():
        try:
            await user_client.send_code_request(phone)
            user_sessions[user_id] = {"client": user_client, "phone": phone}
            await event.reply("✅ Kode OTP telah dikirim! Masukkan kode dengan mengetik:\n`/verify <Kode>`")
        except errors.FloodWaitError as e:
            await event.reply(f"⚠️ Tunggu {e.seconds} detik sebelum mencoba lagi.")
        except Exception as e:
            await event.reply(f"⚠️ Gagal mengirim kode OTP: {e}")
    else:
        # Jika pengguna sudah login
        user_sessions[user_id] = {"client": user_client, "phone": phone}
        await configure_event_handlers(user_client, user_id)
        await event.reply("✅ Akun Anda sudah aktif dan fitur diaktifkan.")

@bot_client.on(events.NewMessage(pattern='/verify (.+)'))
async def verify(event):
    sender = await event.get_sender()
    user_id = sender.id
    code = event.pattern_match.group(1)

    if user_id not in user_sessions:
        await event.reply("⚠️ Anda belum login. Gunakan perintah `/login` terlebih dahulu.")
        return

    user_client = user_sessions[user_id]["client"]
    phone = user_sessions[user_id]["phone"]

    try:
        await user_client.sign_in(phone, code)
        await event.reply(f"✅ Verifikasi berhasil untuk nomor {phone}! Anda sekarang dapat menggunakan fitur.")

        # Aktifkan fitur untuk sesi pengguna
        await configure_event_handlers(user_client, user_id)
    except Exception as e:
        await event.reply(f"⚠️ Gagal memverifikasi kode untuk nomor {phone}: {e}")

@bot_client.on(events.NewMessage(pattern='/help'))
async def help_command(event):
    await event.reply(
        "📋 **Daftar Perintah untuk Bot Multi-Login:**\n\n"
        "`/start` - Mulai interaksi dengan bot.\n"
        "`/login <Nomor>` - Masukkan nomor telepon Anda untuk login.\n"
        "`/verify <Kode>` - Verifikasi kode OTP.\n"
        "`/help` - Tampilkan daftar perintah."
    )

async def main():
    # Mulai bot
    await bot_client.start(bot_token=bot_token)
    print("Bot berjalan!")
    await bot_client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
