import discord
from discord import Intents
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import json
import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import os

# インテント設定
intents = Intents.default()
intents.message_content = True  # メッセージ内容のインテントを有効にする

bot = commands.Bot(command_prefix="!", intents=intents)  # intentsを渡してBotインスタンスを作成

# 設定
TOKEN = os.getenv("DISCORD_TOKEN")
DATA_FILE = "notifications.json"
JST = ZoneInfo("Asia/Tokyo")  # 日本時間に統一

print(f"Message Content Intent: {intents.message_content}")

def load_notifications():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_notifications(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


scheduler = AsyncIOScheduler(timezone=JST)
notifications = load_notifications()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()
    scheduler.start()

    schedule_notifications()

@bot.tree.command(name="set_notification", description="通知を設定する")
async def set_notification(interaction: discord.Interaction, date: str, time: str, message: str):
    try:
        datetime.datetime.strptime(date, "%m-%d")
        datetime.datetime.strptime(time, "%H:%M")
    except ValueError:
        await interaction.response.send_message("日付または時刻の形式が正しくありません。例: 02-17 10:00", ephemeral=True)
        return

    user_id = str(interaction.user.id)
    notifications[user_id] = {"date": date, "time": time, "message": message, "channel": interaction.channel.id}
    save_notifications(notifications)
    await interaction.response.send_message(f"✅ {interaction.user.mention} の通知を {date} の {time} に設定しました！", ephemeral=True)
    
    # 非同期関数を使わずに同期的に呼び出し
    schedule_notifications()

@bot.tree.command(name="list_notifications", description="登録されている通知リストを表示")
async def list_notifications(interaction: discord.Interaction):
    """ 登録されている通知リストを表示 """
    if not notifications:
        await interaction.response.send_message("登録されている通知はありません。", ephemeral=True)
        return

    msg = "**登録されている通知:**\n"
    for user_id, info in notifications.items():
        user = await bot.fetch_user(int(user_id))  # fetch_userを使用してユーザー情報を取得
        username = user.name if user else "Unknown User"
        msg += f"{username}: {info['date']} {info['time']} - {info['message']}\n"
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="remove_notification", description="自分の通知設定を削除")
async def remove_notification(interaction: discord.Interaction):
    """ 自分の通知設定を削除 """
    user_id = str(interaction.user.id)
    if user_id in notifications:
        del notifications[user_id]
        save_notifications(notifications)
        await interaction.response.send_message(f"🗑 {interaction.user.mention} の通知設定を削除しました。", ephemeral=True)
    else:
        await interaction.response.send_message("あなたの通知設定は登録されていません。", ephemeral=True)


async def send_notification_message(user_id, info):
    print(f"Sending notification to {user_id} at {info['time']}")  # 追加: ログ表示
    channel = bot.get_channel(info["channel"])
    if channel:
        print(f"Channel found: {channel.name} ({channel.id})")
    else:
        print(f"Channel not found for ID: {info['channel']}")

    try:
        user = await bot.fetch_user(int(user_id))  # fetch_userを使用してユーザーを取得
    except discord.NotFound:
        print(f"Error: User with ID {user_id} not found.")
        return

    if channel and user:
        message = info["message"].replace("{user}", user.mention)
        await channel.send(message)


def schedule_notifications():
    scheduler.remove_all_jobs()
    now = datetime.datetime.now(JST)
    for user_id, info in notifications.items():
        date_time_str = f"{now.year}-{info['date']} {info['time']}"
        try:
            notification_time = datetime.datetime.strptime(date_time_str, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
            print(notification_time)
            if notification_time < now:
                notification_time = notification_time.replace(year=now.year + 1)
            scheduler.add_job(send_notification_message, 'date', run_date=notification_time, args=[user_id, info])
        except ValueError:
            pass


bot.run(TOKEN)
