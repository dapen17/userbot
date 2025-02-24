import asyncio
import re
from telethon import events, errors
from datetime import datetime
from collections import defaultdict

# Menyimpan status per akun dan grup
active_groups = defaultdict(lambda: defaultdict(bool))  # {group_id: {user_id: status}}
active_bc_interval = defaultdict(lambda: defaultdict(bool))  # {user_id: {type: status}}
blacklist = set()
usernames_history = defaultdict(list)
message_count = defaultdict(int)  # {tanggal: jumlah_pesan}
auto_replies = defaultdict(str)  # {user_id: pesan_auto_reply}

def parse_interval(interval_str):
    """Konversi format [10s, 1m, 2h, 1d] menjadi detik."""
    match = re.match(r'^(\d+)([smhd])$', interval_str)
    if not match:
        return None
    value, unit = match.groups()
    value = int(value)
    return value * {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[unit]

def get_today_date():
    """Mengembalikan tanggal hari ini dalam format YYYY-MM-DD."""
    return datetime.now().strftime("%Y-%m-%d")

async def configure_event_handlers(client, user_id):
    """Konfigurasi semua fitur bot untuk user_id tertentu."""

    @client.on(events.NewMessage(pattern=r'^\\ping$'))
    async def ping_handler(event):
        """Tes koneksi bot."""
        await event.reply("\U0001F3D3 Pong! Bot aktif.")
        message_count[get_today_date()] += 1

    @client.on(events.NewMessage(pattern=r'^\\bcstar (.+)$'))
    async def broadcast_handler(event):
        """Broadcast pesan ke semua chat kecuali blacklist."""
        custom_message = event.pattern_match.group(1)
        await event.reply(f"\u2705 Memulai broadcast ke semua chat: {custom_message}")
        async for dialog in client.iter_dialogs():
            if dialog.id in blacklist:
                continue
            try:
                await client.send_message(dialog.id, custom_message)
                message_count[get_today_date()] += 1
            except Exception as e:
                print(f"Gagal mengirim pesan ke {dialog.name}: {e}")

    @client.on(events.NewMessage(pattern=r'^\\bcstargr(\d+) (\d+[smhd]) (.+)$'))
    async def broadcast_group_handler(event):
        """Broadcast pesan hanya ke grup dengan interval tertentu."""
        group_number = event.pattern_match.group(1)
        interval_str, custom_message = event.pattern_match.groups()[1:]
        interval = parse_interval(interval_str)

        if not interval:
            await event.reply("\u26A0 Format waktu salah! Gunakan format 10s, 1m, 2h, dll.")
            return

        if active_bc_interval[user_id][f"group{group_number}"]:
            await event.reply(f"\u26A0 Broadcast ke grup {group_number} sudah berjalan.")
            return

        active_bc_interval[user_id][f"group{group_number}"] = True
        await event.reply(f"\u2705 Memulai broadcast ke grup {group_number} dengan interval {interval_str}: {custom_message}")
        while active_bc_interval[user_id][f"group{group_number}"]:
            async for dialog in client.iter_dialogs():
                if dialog.is_group and dialog.id not in blacklist:
                    try:
                        await client.send_message(dialog.id, custom_message)
                        message_count[get_today_date()] += 1
                    except Exception as e:
                        print(f"Gagal mengirim pesan ke {dialog.name}: {e}")
            await asyncio.sleep(interval)

    @client.on(events.NewMessage(pattern=r'^\\stopbcstargr(\d+)$'))
    async def stop_broadcast_group_handler(event):
        """Hentikan broadcast grup."""
        group_number = event.pattern_match.group(1)
        if active_bc_interval[user_id][f"group{group_number}"]:
            active_bc_interval[user_id][f"group{group_number}"] = False
            await event.reply(f"\u2705 Broadcast ke grup {group_number} dihentikan.")
        else:
            await event.reply(f"\u26A0 Tidak ada broadcast grup {group_number} yang berjalan.")

    @client.on(events.NewMessage(pattern=r'^\\setreply (.+)$'))
    async def set_auto_reply(event):
        """Mengatur pesan balasan otomatis."""
        reply_message = event.pattern_match.group(1)
        auto_replies[user_id] = reply_message
        await event.reply(f"\u2705 Auto-reply diatur: {reply_message}")

    @client.on(events.NewMessage(incoming=True))
    async def auto_reply_handler(event):
        """Menangani auto-reply untuk setiap pesan masuk tanpa mengutip pesan."""
        if event.is_private and user_id in auto_replies and auto_replies[user_id]:
            try:
                await client.send_message(event.chat_id, auto_replies[user_id])
                await client.send_read_acknowledge(event.chat_id)  # Tandai pesan sebagai telah dibaca
                message_count[get_today_date()] += 1
            except Exception as e:
                print(f"Gagal mengirim auto-reply: {e}")

    @client.on(events.NewMessage(pattern=r'^\\help$'))
    async def help_handler(event):
        """Tampilkan daftar perintah."""
        help_text = (
            "\U0001F4AC Daftar Perintah:\n"
            "\\ping - Cek status bot\n"
            "\\bcstar <pesan> - Kirim broadcast ke semua chat\n"
            "\\bcstargr<nomor> <interval> <pesan> - Kirim broadcast ke grup tertentu\n"
            "\\stopbcstargr<nomor> - Hentikan broadcast ke grup tertentu\n"
            "\\setreply <pesan> - Set auto-reply untuk chat masuk\n"
            "\\help - Menampilkan daftar perintah"
        )
        await event.reply(help_text)
