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

MAX_PRICE   = 2
MAX_MINUTES = 15

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
        name_match  = re.search(r'Located in \*\*([^*]+)\*\*', line)
        price_match = re.search(r'price \*\*(\d+)/', line)
        ts_match    = re.search(r'<t:(\d+):[^>]*>', line)
        if not price_match or not ts_match:
            continue
        name       = name_match.group(1).strip() if name_match else "?"
        price      = int(price_match.group(1))
        minutes_ago = (now - int(ts_match.group(1))) / 60
        items.append({"name": name, "price": price, "minutes_ago": round(minutes_ago, 1)})
    return items

async def main():
    client = discord.Client()
    result = {"response": None}

    @client.event
    async def on_ready():
        print(f"✅ Giriş: {client.user}")
        guild = client.get_guild(GUILD_ID)
        ch    = client.get_channel(COMMAND_CHANNEL_ID)
        if not guild or not ch:
            print("❌ Sunucu/kanal bulunamadı")
            await client.close()
            return

        # Önce dinlemeyi başlat, sonra komutu gönder
        async def wait_and_process():
            try:
                def check_msg(msg):
                    return (
                        msg.channel.id == COMMAND_CHANNEL_ID and
                        msg.author.id  == LOCATOR_BOT_ID and
                        len(msg.embeds) > 0
                    )

                # Komutu gönder
                cmds = await guild.application_commands()
                search_cmd = next(
                    (c for c in cmds if c.name == "search" and c.application_id == LOCATOR_BOT_ID),
                    next((c for c in cmds if c.name == "search"), None)
                )
                if not search_cmd:
                    print("❌ /search bulunamadı!")
                    await client.close()
                    return

                # Dinleme task'ını başlat
                listen_task = asyncio.ensure_future(
                    client.wait_for("message", check=check_msg, timeout=45)
                )

                # Kısa bekle sonra komutu gönder
                await asyncio.sleep(1)
                await search_cmd(ch, input="fire escape", sorting="Low to High", accessible="Accessible")
                print("✅ /search gönderildi, cevap bekleniyor...")

                # Cevabı bekle
                response = await listen_task
                result["response"] = response
                print("✅ Cevap alındı!")

            except asyncio.TimeoutError:
                print("⚠️ 45 saniyede cevap gelmedi.")
            except Exception as e:
                print(f"❌ Hata: {e}")
            finally:
                await client.close()

        asyncio.ensure_future(wait_and_process())

    await client.start(DISCORD_TOKEN)

    # Cevabı işle
    if result["response"]:
        all_items = []
        for embed in result["response"].embeds:
            all_items.extend(parse_embed(embed))

        print(f"📦 {len(all_items)} item parse edildi")

        fresh   = [i for i in all_items if i["minutes_ago"] <= MAX_MINUTES]
        matched = [i for i in fresh if i["price"] >= MAX_PRICE]

        print(f"⏱️ Son {MAX_MINUTES}dk: {len(fresh)} | 💰 Kriter: {len(matched)}")

        if matched:
            lines = [
                f"🔥 <b>{i['name']}</b> → <b>{i['price']}/1</b> | ⏱ {int(i['minutes_ago'])} dk önce"
                for i in sorted(matched, key=lambda x: x["price"])
            ]
            send_telegram(
                f"🚨 <b>Fire Escape Uyarısı!</b>\n{len(matched)} item bulundu:\n\n" + "\n".join(lines)
            )
        else:
            print("ℹ️ Kritere uyan item yok.")
            if fresh:
                print(f"   En ucuz taze: {min(fresh, key=lambda x: x['price'])['name']} → {min(fresh, key=lambda x: x['price'])['price']}/1")

asyncio.run(main())

