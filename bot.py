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

# Her ürün: (arama adı, max fiyat eşiği para/item olarak)
# 2/1 = 0.5 para/item, 1/1 = 1.0, 45 = 45.0
PRODUCTS = [
    ("fire escape",   0.5),
    ("glowy block",   0.5),
    ("xenoid block",  0.5),
    ("megaphone",     4000.0),
    ("vip entrance",  45.0),
    ("display block", 5.0),
    ("digivend machine", 36.0),
    ("vending machine", 17.0),
    ("thermonuclear blast", 40.0),
    ("laser grid seed", 0.25),
    ("shifty block", 140.0),
    ("atm machine", 17.0),
    ("tavern sign", 4.0),
    ("pillar",        2.0),
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
    """Gerçek birim fiyat: sağ / sol (para / item)"""
    if left == 0:
        return float('inf')
    return right / left

def parse_embed(embed: discord.Embed):
    items = []
    text = ""
    if embed.description:
        text += embed.description + "\n"
    for field in embed.fields:
        text += field.value + "\n"

    now = int(time.time())
    for line in text.split("\n"):
        line = line.strip()
        if "Located in" not in line:
            continue

        name_match = re.search(r'Located in \*\*([^*]+)\*\*', line)
        name = name_match.group(1).strip() if name_match else "?"

        # Price formatları: "35/<:WorldLock:...>" veya "1/<:WorldLock:...>" veya "35"
        # Sol/sağ sayıyı çek
        price_match = re.search(r'price \*\*(\d+)/(\d+)', line)
        if price_match:
            left  = int(price_match.group(1))
            right = int(price_match.group(2))
        else:
            # Sadece tek sayı: "price **35**" veya "price **35/<:..."
            price_match2 = re.search(r'price \*\*(\d+)', line)
            if not price_match2:
                continue
            left  = 1
            right = int(price_match2.group(1))

        unit_price = calc_unit_price(left, right)

        ts_match = re.search(r'<t:(\d+):[^>]*>', line)
        if not ts_match:
            continue
        minutes_ago = (now - int(ts_match.group(1))) / 60

        items.append({
            "name":       name,
            "left":       left,
            "right":      right,
            "unit_price": unit_price,
            "minutes_ago": round(minutes_ago, 1),
            "display":    f"{left}/{right}" if left != 1 else str(right),
        })
    return items

async def search_product(client, guild, ch, product_name, max_unit_price):
    print(f"\n🔍 Aranıyor: {product_name}")

    cmds = await guild.application_commands()
    search_cmd = next(
        (c for c in cmds if c.name == "search" and c.application_id == LOCATOR_BOT_ID),
        next((c for c in cmds if c.name == "search"), None)
    )
    if not search_cmd:
        print("❌ /search bulunamadı!")
        return []

    def check_msg(msg):
        return (
            msg.channel.id == COMMAND_CHANNEL_ID and
            msg.author.id  == LOCATOR_BOT_ID and
            len(msg.embeds) > 0
        )

    listen_task = asyncio.ensure_future(
        client.wait_for("message", check=check_msg, timeout=45)
    )

    await asyncio.sleep(1)
    await search_cmd(ch, input=product_name, sorting="Low to High", accessible="Accessible")
    print(f"✅ /search '{product_name}' gönderildi")

    try:
        response = await listen_task
    except asyncio.TimeoutError:
        print(f"⚠️ '{product_name}' için cevap gelmedi.")
        return []

    all_items = []
    for embed in response.embeds:
        all_items.extend(parse_embed(embed))

    print(f"📦 {len(all_items)} item parse edildi")

    fresh   = [i for i in all_items if i["minutes_ago"] <= MAX_MINUTES]
    matched = [i for i in fresh if i["unit_price"] <= max_unit_price]

    print(f"⏱️ Son {MAX_MINUTES}dk: {len(fresh)} | 💰 Kriter: {len(matched)}")
    return matched

async def main():
    client  = discord.Client()
    results = {}  # product_name -> matched items

    @client.event
    async def on_ready():
        print(f"✅ Giriş: {client.user}")
        guild = client.get_guild(GUILD_ID)
        ch    = client.get_channel(COMMAND_CHANNEL_ID)
        if not guild or not ch:
            print("❌ Sunucu/kanal bulunamadı")
            await client.close()
            return

        async def run_all():
            for i, (product_name, max_price) in enumerate(PRODUCTS):
                matched = await search_product(client, guild, ch, product_name, max_price)
                if matched:
                    results[product_name] = matched
                # Her ürün arasında 6 saniye bekle (son üründe bekleme)
                if i < len(PRODUCTS) - 1:
                    print(f"⏳ 6 saniye bekleniyor...")
                    await asyncio.sleep(6)

            await client.close()

        asyncio.ensure_future(run_all())

    await client.start(DISCORD_TOKEN)

    # Tüm sonuçları Telegram'a gönder
    if results:
        msg_lines = ["🚨 <b>Uyarı! Kritere uyan itemlar bulundu:</b>\n"]
        for product_name, items in results.items():
            msg_lines.append(f"📦 <b>{product_name.upper()}</b>")
            for i in sorted(items, key=lambda x: x["unit_price"]):
                msg_lines.append(
                    f"  🔥 {i['name']} → <b>{i['display']}</b> | ⏱ {int(i['minutes_ago'])} dk önce"
                )
            msg_lines.append("")
        send_telegram("\n".join(msg_lines))
    else:
        print("ℹ️ Hiçbir üründe kriter karşılanmadı.")

asyncio.run(main())
