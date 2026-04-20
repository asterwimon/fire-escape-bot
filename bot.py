import discord
import asyncio
import re
import time
import requests
import os

DISCORD_TOKEN      = os.environ["DISCORD_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

GUILD_ID           = 1144379322677862591
COMMAND_CHANNEL_ID = 1283016812212256798
LOCATOR_BOT_ID     = 1264987788156211200

MAX_MINUTES = 480

PRODUCTS = [
    ("fire escape", 0.5), ("glowy block", 0.5), ("xenoid block", 0.5),
    ("megaphone", 4000.0), ("vip entrance", 45.0), ("display block", 5.0),
    ("digivend machine", 36.0), ("vending machine", 17.0),
    ("thermonuclear blast", 40.0), ("laser grid seed", 0.25),
    ("shifty block", 140.0), ("atm machine", 17.0),
    ("tavern sign", 4.0), ("pillar", 2.0),
]

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
        print("✅ Telegram OK" if r.status_code == 200 else f"❌ Telegram: {r.text}")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")

def calc_unit_price(left: int, right: int) -> float:
    return right / left if left > 0 else float('inf')

def parse_embed(embed: discord.Embed):
    items = []
    text = (embed.description or "") + "\n" + "\n".join(f.value for f in embed.fields)
    now = int(time.time())

    for line in text.split("\n"):
        if "Located in" not in line: continue
        name_match = re.search(r'Located in \*\*([^*]+)\*\*', line)
        name = name_match.group(1).strip() if name_match else "?"

        m_emoji = re.search(r'price \*\*(\d+)/<:', line)
        m_slash = re.search(r'price \*\*(\d+)/(\d+)', line)
        m_plain = re.search(r'price \*\*(\d+)', line)

        if m_emoji: left, right = int(m_emoji.group(1)), 1
        elif m_slash: left, right = int(m_slash.group(1)), int(m_slash.group(2))
        elif m_plain: left, right = 1, int(m_plain.group(1))
        else: continue

        ts_match = re.search(r'<t:(\d+):[^>]*>', line)
        if not ts_match: continue
        minutes_ago = (now - int(ts_match.group(1))) / 60

        items.append({
            "name": name, "unit_price": calc_unit_price(left, right),
            "minutes_ago": round(minutes_ago, 1),
            "display": f"{left}/{right}" if left != 1 else str(right)
        })
    return items

async def main():
    client = discord.Client(intents=discord.Intents.default())
    results = {}

    @client.event
    async def on_ready():
        print(f"✅ Giriş: {client.user}")
        guild = client.get_guild(GUILD_ID)
        ch = client.get_channel(COMMAND_CHANNEL_ID)
        
        if not guild or not ch:
            print("❌ Hata: Sunucu/Kanal bulunamadı."); await client.close(); return

        try:
            for i, (p_name, p_price) in enumerate(PRODUCTS):
                print(f"🔍 {p_name} aranıyor...")
                cmds = await guild.application_commands()
                search_cmd = next((c for c in cmds if c.name == "search" and c.application_id == LOCATOR_BOT_ID), 
                                  next((c for c in cmds if c.name == "search"), None))
                
                if search_cmd:
                    try:
                        await search_cmd(ch, input=p_name, sorting="Low to High", accessible="Accessible")
                        msg = await client.wait_for(
                            "message", 
                            check=lambda m: m.channel.id == COMMAND_CHANNEL_ID and m.author.id == LOCATOR_BOT_ID and m.embeds,
                            timeout=30
                        )
                        found = [it for it in parse_embed(msg.embeds[0]) if it["minutes_ago"] <= MAX_MINUTES and it["unit_price"] <= p_price]
                        if found: results[p_name] = found
                    except asyncio.TimeoutError:
                        print(f"⚠️ {p_name} için zaman aşımı.")
                    except Exception as e:
                        print(f"⚠️ {p_name} hatası: {e}")
                
                # Ürünler arası 6 saniye bekleme
                if i < len(PRODUCTS) - 1:
                    print("⏳ 6 saniye bekleniyor...")
                    await asyncio.sleep(6)

            if results:
                msg_body = "🚨 <b>Kritere uyanlar:</b>\n\n"
                for n, its in results.items():
                    msg_body += f"📦 <b>{n.upper()}</b>\n"
                    for it in sorted(its, key=lambda x: x["unit_price"]):
                        msg_body += f" 🔥 {it['name']} → <b>{it['display']}</b> | ⏱ {int(it['minutes_ago'])} dk\n"
                    msg_body += "\n"
                send_telegram(msg_body)
            else:
                print("ℹ️ Uygun ürün bulunamadı.")
        finally:
            await client.close()

    try:
        await client.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"Sistem kapandı: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
