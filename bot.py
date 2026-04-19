"""
Fire Escape Monitor - GitHub Actions versiyonu
Bir kere çalışır, kontrol eder, kapanır.
GitHub Actions her 10 dakikada tetikler.
"""

import discord
import asyncio
import re
import time
import requests
import os
from datetime import datetime

DISCORD_TOKEN      = os.environ["DISCORD_TOKEN"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

GUILD_ID           = 1144379322677862591
COMMAND_CHANNEL_ID = 1283016812212256798
LOCATOR_BOT_ID     = 1264987788156211200

MAX_PRICE   = 2
MAX_MINUTES = 10

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram bildirimi gönderildi")
        else:
            print(f"❌ Telegram hatası: {r.text}")
    except Exception as e:
        print(f"❌ Telegram bağlantı hatası: {e}")

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

        price_match = re.search(r'price \*\*(\d+)/', line)
        if not price_match:
            continue
        price = int(price_match.group(1))

        ts_match = re.search(r'<t:(\d+):[^>]*>', line)
        if not ts_match:
            continue
        timestamp = int(ts_match.group(1))
        minutes_ago = (now - timestamp) / 60

        items.append({
            "name": name,
            "price": price,
            "minutes_ago": round(minutes_ago, 1),
        })

    return items

async def main():
    client = discord.Client()

    @client.event
    async def on_ready():
        print(f"✅ Discord'a giriş yapıldı: {client.user}")
        try:
            guild = client.get_guild(GUILD_ID)
            ch    = client.get_channel(COMMAND_CHANNEL_ID)

            if not guild or not ch:
                print("❌ Sunucu/kanal bulunamadı")
                await client.close()
                return

            # /search komutunu gönder
            cmds = await guild.application_commands()
            search_cmd = next(
                (c for c in cmds if c.name == "search" and c.application_id == LOCATOR_BOT_ID),
                next((c for c in cmds if c.name == "search"), None)
            )

            if not search_cmd:
                print("❌ /search komutu bulunamadı!")
                await client.close()
                return

            await search_cmd(ch, input="fire escape", sorting="Low to High", accessible="Accessible")
            print("✅ /search gönderildi, cevap bekleniyor...")

            # Locator'ın cevabını bekle
            def check_msg(msg):
                return (
                    msg.channel.id == COMMAND_CHANNEL_ID and
                    msg.author.id  == LOCATOR_BOT_ID and
                    len(msg.embeds) > 0
                )

            try:
                response = await asyncio.wait_for(
                    client.wait_for("message", check=check_msg),
                    timeout=30
                )
            except asyncio.TimeoutError:
                print("⚠️ Locator 30 saniyede cevap vermedi.")
                await client.close()
                return

            # Parse et
            all_items = []
            for embed in response.embeds:
                all_items.extend(parse_embed(embed))

            print(f"📦 {len(all_items)} item parse edildi")

            # Önce zaman filtresi, sonra fiyat
            fresh   = [i for i in all_items if i["minutes_ago"] <= MAX_MINUTES]
            matched = [i for i in fresh if i["price"] <= MAX_PRICE]

            print(f"⏱️  Son {MAX_MINUTES} dk: {len(fresh)} item | 💰 Fiyat kriteri: {len(matched)} item")

            if matched:
                lines = []
                for i in sorted(matched, key=lambda x: x["price"]):
                    mins = int(i["minutes_ago"])
                    lines.append(f"🔥 <b>{i['name']}</b> → <b>{i['price']}/1</b> | ⏱ {mins} dakika önce")

                msg = (
                    f"🚨 <b>Fire Escape Uyarısı!</b>\n"
                    f"{len(matched)} kritere uyan item:\n\n"
                    + "\n".join(lines)
                )
                send_telegram(msg)
            else:
                print("ℹ️ Kritere uyan item yok.")

        except Exception as e:
            print(f"❌ Hata: {e}")
        finally:
            await client.close()

    await client.start(DISCORD_TOKEN)

asyncio.run(main())
