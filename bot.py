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

MAX_MINUTES = 480 # 15 yerine 480 yaptık, istersen değiştirebilirsin

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
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        print("✅ Telegram OK" if r.status_code == 200 else f"❌ Telegram: {r.text}")
    except Exception as e:
        print(f"❌ Telegram hatası: {e}")

def calc_unit_price(left: int, right: int) -> float:
    if left == 0: return float('inf')
    return right / left

def parse_embed(embed: discord.Embed):
    items = []
    text = ""
    if embed.description: text += embed.description + "\n"
    for field in embed.fields: text += field.value + "\n"

    now = int(time.time())
    for line in text.split("\n"):
        line = line.strip()
        if "Located in" not in line: continue

        name_match = re.search(r'Located in \*\*([^*]+)\*\*', line)
        name = name_match.group(1).strip() if name_match else "?"

        # Fiyat çekme mantığını güçlendirdik
        # 1. Format: 35/<:emoji:id> (35 tane 1 WL)
        match_emoji = re.search(r'price \*\*(\d+)/<:', line)
        # 2. Format: 1/2 (1 tane 2 WL)
        match_slash = re.search(r'price \*\*(\d+)/(\d+)', line)
        
        if match_emoji:
            left, right = int(match_emoji.group(1)), 1
        elif match_slash:
            left, right = int(match_slash.group(1)), int(match_slash.group(2))
        else:
            # 3. Format: price **35** (1 tane 35 WL)
            match_plain = re.search(r'price \*\*(\d+)', line)
            if not match_plain: continue
            left, right = 1, int(match_plain.group(1))

        unit_price = calc_unit_price(left, right)
        ts_match = re.search(r'<t:(\d+):[^>]*>', line)
        if not ts_match: continue
        minutes_ago = (now - int(ts_match.group(1))) / 60

        items.append({
            "name": name, "left": left, "right": right,
            "unit_price": unit_price, "minutes_ago": round(minutes_ago, 1),
            "display": f"{left}/{right}" if left != 1 else str(right),
        })
    return items

async def search_product(client, guild, ch, product_name, max_unit_price):
    print(f"\n🔍 Aranıyor: {product_name}")
    cmds = await guild.application_commands()
    search_cmd = next((c for c in cmds if (c.name == "search" and c.application_id == LOCATOR_BOT_ID)), 
                      next((c for c in cmds if c.name == "search"), None))
    
    if not search_cmd:
        print("❌ /search bulunamadı!")
        return []

    def check_msg(msg):
        return msg.channel.id == COMMAND_CHANNEL_ID and msg.author.id == LOCATOR_BOT_ID and len(msg.embeds) > 0

    try:
        await search_cmd(ch, input=product_name, sorting="Low to High", accessible="Accessible")
        response = await client.wait_for("message", check=check_msg, timeout=40)
        
        all_items = []
        for embed in response.embeds:
            all_items.extend(parse_embed(embed))
        
        fresh = [i for i in all_items if i["minutes_ago"] <= MAX_MINUTES]
        matched = [i for i in fresh if i["unit_price"] <= max_unit_price]
        print(f"📦 Bulunan: {len(all_items)} | Uygun: {len(matched)}")
        return matched
    except Exception as e:
        print(f"⚠️ Hata: {e}")
        return []

async def main():
    client = discord.Client()
    results = {}

    @client.event
    async def on_ready():
        print(f"✅ Giriş: {client.user}")
        guild = client.get_guild(GUILD_ID)
        ch = client.get_channel(COMMAND_CHANNEL_ID)
        
        if not guild or not ch:
            print("❌ Bağlantı hatası")
            await client.close()
            return

        for i, (p_name, p_price) in enumerate(PRODUCTS):
            found = await search_product(client, guild, ch, p_name, p_price)
            if found:
                results[p_name] = found
            if i < len(PRODUCTS) - 1:
                await asyncio.sleep(10) # Ban yememek için 10 sn ideal

        # Sonuçları gönder ve KAPA
        if results:
            msg = "🚨 <b>Kritere uyanlar bulundu:</b>\n\n"
            for name, items in results.items():
                msg += f"📦 <b>{name.upper()}</b>\n"
                for it in sorted(items, key=lambda x: x["unit_price"]):
                    msg += f" 🔥 {it['name']} → <b>{it['display']}</b> | ⏱ {int(it['minutes_ago'])} dk\n"
                msg += "\n"
            send_telegram(msg)
        else:
            print("ℹ️ Uygun ürün yok.")
        
        await client.close()

    try:
        await client.start(DISCORD_TOKEN)
    except Exception as e:
        print(f"Bitti: {e}")

if __name__ == "__main__":
    asyncio.run(main())
