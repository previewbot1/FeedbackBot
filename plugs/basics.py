import asyncio
import logging
import os
import platform
import psutil
import shutil
import pytz
import subprocess
from datetime import datetime
from time import time
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid, PeerIdInvalid, UserIsBlocked, InputUserDeactivated, UserDeactivatedBan, ChatWriteForbidden, ChatAdminRequired, RPCError
from formats import script, faq_script
from utils.database import add_user, add_log_usage
from plugs.sudo import Bot_cmds

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]

ADMIN_COMMANDS = {
    "addservice", "editservice", "removeservice", "listservices", "cleanservices",
    "users", "send", "broadcast", "logs", "commands", "getcmds",
    "keyword", "keywords", "delkeyword", "clearkeywords",
    "save", "listcallbacks", "delcallback", "clearcallbacks"
}

start_time = time()
spam_block = {}
START_RATE_LIMIT_SECONDS = 15
SYSTEM_RATE_LIMIT_SECONDS = 15
PING_RATE_LIMIT_SECONDS = 15
ALIVE_RATE_LIMIT_SECONDS = 15
ID_RATE_LIMIT_SECONDS = 15
INFO_RATE_LIMIT_SECONDS = 15
CLOSE_RATE_LIMIT_SECONDS = 15
HELP_RATE_LIMIT_SECONDS = 60

def add_user_context(user_id):
    return {"user_id": user_id}

def add_system_context():
    return {"user_id": "System"}

def format_time(seconds):
    minutes, sec = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {sec}s"

def get_size(size_bytes):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} PB"

def get_system_info(start_time):
    logger_context = add_system_context()
    system_info = {
        "bot_uptime": "N/A",
        "os_info": "N/A",
        "python_version": "N/A",
        "cpu_usage": "N/A",
        "cpu_cores": "N/A",
        "mem_percent": "N/A",
        "process_count": "N/A",
        "bot_cpu": "N/A",
        "bot_mem": "N/A",
        "thread_count": "N/A",
        "system_uptime": "N/A",
        "load_avg": "N/A",
        "boot_time": "N/A",
        "total_ram": "N/A",
        "used_ram": "N/A",
        "available_ram": "N/A",
        "swap_used": "N/A",
        "swap_total": "N/A",
        "total_disk": "N/A",
        "used_disk": "N/A",
        "net_sent": "N/A",
        "net_recv": "N/A",
        "interface_name": "N/A",
        "system_temp": "N/A",
        "fan_rpm": "N/A",
        "battery_percent": "N/A",
        "battery_status": "N/A",
        "gpu_usage": "N/A",
        "gpu_mem_usage": "N/A",
        "gpu_temp": "N/A",
        "gpu_fan": "N/A"
    }

    try:
        system_info["bot_uptime"] = format_time(time() - start_time)
    except Exception as e:
        logger.error(f"Failed to calculate bot uptime: {e}", extra=logger_context)

    try:
        system_info["os_info"] = platform.system()
        system_info["python_version"] = platform.python_version()
    except Exception as e:
        logger.error(f"Failed to get platform info: {e}", extra=logger_context)

    try:
        system_info["cpu_usage"] = psutil.cpu_percent(interval=0.1)
        system_info["cpu_cores"] = psutil.cpu_count(logical=True)
    except Exception as e:
        logger.error(f"Failed to get CPU info: {e}", extra=logger_context)

    try:
        mem = psutil.virtual_memory()
        system_info["mem_percent"] = mem.percent
    except Exception as e:
        logger.error(f"Failed to get memory info: {e}", extra=logger_context)

    try:
        system_info["process_count"] = len(psutil.pids())
    except Exception as e:
        logger.error(f"Failed to get process count: {e}", extra=logger_context)

    try:
        process = psutil.Process()
        system_info["bot_cpu"] = process.cpu_percent(interval=0.1)
        system_info["bot_mem"] = get_size(process.memory_info().rss)
        system_info["thread_count"] = process.num_threads()
    except Exception as e:
        logger.error(f"Failed to get bot process info: {e}", extra=logger_context)

    try:
        with open('/proc/uptime', 'r') as f:
            system_info["system_uptime"] = format_time(float(f.readline().split()[0]))
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to get system uptime: {e}", extra=logger_context)

    try:
        with open('/proc/loadavg', 'r') as f:
            system_info["load_avg"] = ", ".join(f.readline().split()[:3])
    except (OSError, ValueError) as e:
        logger.warning(f"Failed to get load average: {e}", extra=logger_context)

    try:
        system_info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.warning(f"Failed to get boot time: {e}", extra=logger_context)

    try:
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.readlines()
            total = int(meminfo[0].split()[1]) * 1024
            available = int(meminfo[2].split()[1]) * 1024
            system_info["total_ram"] = get_size(total)
            system_info["available_ram"] = get_size(available)
            system_info["used_ram"] = get_size(total - available)
    except (OSError, ValueError, IndexError) as e:
        logger.warning(f"Failed to get RAM info: {e}", extra=logger_context)

    try:
        swap = psutil.swap_memory()
        system_info["swap_used"] = get_size(swap.used)
        system_info["swap_total"] = get_size(swap.total)
    except Exception as e:
        logger.warning(f"Failed to get swap info: {e}", extra=logger_context)

    try:
        total_disk, used_disk, _ = shutil.disk_usage("/")
        system_info["total_disk"] = get_size(total_disk)
        system_info["used_disk"] = get_size(used_disk)
    except Exception as e:
        logger.warning(f"Failed to get disk usage: {e}", extra=logger_context)

    try:
        net_io = psutil.net_io_counters(pernic=True)
        primary_interface = next(iter(net_io), None)
        if primary_interface:
            system_info["net_sent"] = get_size(net_io[primary_interface].bytes_sent)
            system_info["net_recv"] = get_size(net_io[primary_interface].bytes_recv)
            system_info["interface_name"] = primary_interface
    except Exception as e:
        logger.warning(f"Failed to get network info: {e}", extra=logger_context)

    try:
        temps = psutil.sensors_temperatures()
        cpu_temp = temps.get('coretemp', [None])[0].current if 'coretemp' in temps else None
        system_info["system_temp"] = f"{cpu_temp:.1f} °C" if cpu_temp else "N/A"
    except Exception as e:
        logger.warning(f"Failed to get temperature: {e}", extra=logger_context)

    try:
        fans = psutil.sensors_fans()
        fan_speed = fans.get('fan1', [None])[0].current if 'fan1' in fans else None
        system_info["fan_rpm"] = f"{fan_speed} RPM" if fan_speed else "N/A"
    except Exception as e:
        logger.warning(f"Failed to get fan speed: {e}", extra=logger_context)

    try:
        battery = psutil.sensors_battery()
        system_info["battery_percent"] = f"{battery.percent:.1f}%" if battery else "N/A"
        system_info["battery_status"] = "Plugged" if battery and battery.power_plugged else "Unplugged" if battery else "N/A"
    except Exception as e:
        logger.warning(f"Failed to get battery info: {e}", extra=logger_context)

    try:
        nvidia_output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,utilization.memory,temperature.gpu,fan.speed", "--format=csv"],
            timeout=5
        ).decode().strip()
        gpu_data = nvidia_output.split("\n")[1].split(", ")
        system_info["gpu_usage"] = gpu_data[0].replace(" %", "%")
        system_info["gpu_mem_usage"] = gpu_data[1].replace(" %", "%")
        system_info["gpu_temp"] = f"{gpu_data[2]} °C"
        system_info["gpu_fan"] = f"{gpu_data[3].replace(' %', '')} RPM"
    except (subprocess.SubprocessError, IndexError, FileNotFoundError) as e:
        logger.warning(f"Failed to get GPU info: {e}", extra=logger_context)

    try:
        return (
            f"💻 System Overview\n\n"
            f"<blockquote>"
            f"🖥️ <b>OS:</b> {system_info['os_info']}\n"
            f"🐍 <b>Python Version:</b> {system_info['python_version']}\n"
            f"⏰ <b>Bot Uptime:</b> {system_info['bot_uptime']}\n"
            f"🔄 <b>System Uptime:</b> {system_info['system_uptime']}\n"
            f"🕒 <b>Boot Time:</b> {system_info['boot_time']}\n"
            f"🖥️ <b>CPU Usage:</b> {system_info['cpu_usage']}%\n"
            f"🧩 <b>CPU Cores:</b> {system_info['cpu_cores']}\n"
            f"📊 <b>Load Average:</b> {system_info['load_avg']}\n"
            f"💾 <b>RAM Usage:</b> {system_info['used_ram']} / {system_info['total_ram']} ({system_info['mem_percent']}%)\n"
            f"🧠 <b>Swap Usage:</b> {system_info['swap_used']} / {system_info['swap_total']}\n"
            f"📖 <b>Disk Usage:</b> {system_info['used_disk']} / {system_info['total_disk']}\n"
            f"📈 <b>Process Count:</b> {system_info['process_count']}\n"
            f"🧵 <b>Thread Count (Bot):</b> {system_info['thread_count']}\n"
            f"🖥️ <b>Bot CPU Usage:</b> {system_info['bot_cpu']}%\n"
            f"💾 <b>Bot Memory Usage:</b> {system_info['bot_mem']}\n"
            f"🌐 <b>Network Interface:</b> {system_info['interface_name']}\n"
            f"📤 <b>Network Sent:</b> {system_info['net_sent']}\n"
            f"📥 <b>Network Received:</b> {system_info['net_recv']}\n"
            f"🌡️ <b>System Temperature:</b> {system_info['system_temp']}\n"
            f"🌀 <b>Fan Speed:</b> {system_info['fan_rpm']}\n"
            f"🔋 <b>Battery Level:</b> {system_info['battery_percent']}\n"
            f"⚡️ <b>Battery Status:</b> {system_info['battery_status']}\n"
            f"🎮 <b>GPU Usage:</b> {system_info['gpu_usage']}\n"
            f"🧠 <b>GPU Memory Usage:</b> {system_info['gpu_mem_usage']}\n"
            f"🌡️ <b>GPU Temperature:</b> {system_info['gpu_temp']}\n"
            f"🌀 <b>GPU Fan Speed:</b> {system_info['gpu_fan']}"
            f"</blockquote>"
        )
    except Exception as e:
        logger.error(f"Failed to format system info: {e}", extra=logger_context)
        return "❌ Failed to retrieve system information."

async def calculate_latency():
    start = time()
    await asyncio.sleep(0)
    end = time()
    latency = (end - start) * 1000
    return f"{latency:.3f} ms"

@Client.on_message(filters.command("start") & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < START_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for start command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /start again.")
            return
        spam_block[user_id] = now

        try:
            await add_user(user_id)
            logger.info("User added to database", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to add user to database: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to register user. Please try again later.")
            return

        wait_msg = None
        try:
            wait_msg = await safe_reply(message, "🔍 Verifying....")
            await asyncio.sleep(0.8)
            try:
                await safe_delete(wait_msg)
                logger.info("Wait message deleted", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete wait message: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send wait message: {e}", extra=logger_context)
            if wait_msg:
                try:
                    await safe_delete(wait_msg)
                except Exception as de:
                    logger.warning(f"Failed to clean up wait message: {de}", extra=logger_context)

        try:
            current_time = datetime.now(pytz.timezone("Asia/Kolkata"))
            curr_time = current_time.hour
            if curr_time < 12:
                greeting = "Good Morning 🌞"
            elif curr_time < 17:
                greeting = "Good Afternoon 🌓"
            elif curr_time < 21:
                greeting = "Good Evening 🌘"
            else:
                greeting = "Good Night 🌑"
        except Exception as e:
            logger.warning(f"Failed to generate greeting: {e}", extra=logger_context)
            greeting = "Hello"

        user_name = (
            message.from_user.first_name or
            message.from_user.username or
            "User"
        )

        buttons = []
        try:
            if os.getenv("FAQ", "False").lower() == "true":
                buttons.append(InlineKeyboardButton("FAQ", callback_data="faq"))
            if os.getenv("SOURCE_BUTTON", "False").lower() == "true":
                source_url = os.getenv("SOURCE", "https://github.com/")
                if not source_url.startswith(("http://", "https://")):
                    logger.warning("Invalid SOURCE URL provided", extra=logger_context)
                    source_url = "https://github.com/"
                buttons.append(InlineKeyboardButton("SOURCE", url=source_url))
        except Exception as e:
            logger.warning(f"Failed to generate buttons: {e}", extra=logger_context)
            buttons = []

        reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None

        try:
            start_text = script.START_TXT.format(user_name, greeting)
        except (AttributeError, KeyError) as e:
            logger.error(f"Invalid START_TXT format: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to load start message.")
            return

        try:
            await safe_reply(
                message,
                start_text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
            )
            logger.info("Start message sent", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send start message: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send start message.")
            return

        try:
            log_channel = int(os.getenv("LOG"))
            await message.forward(log_channel)
            logger.info("Message forwarded to log channel", extra=logger_context)
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid LOG channel ID: {e}", extra=logger_context)
        except (ChatWriteForbidden, PeerIdInvalid) as e:
            logger.error(f"Cannot forward to log channel: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to forward message to log channel: {e}", extra=logger_context)

        try:
            await add_log_usage(user_id, "start")
            logger.info("Start command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in start_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.")
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for start", extra=logger_context)

async def safe_reply(message: Message, text: str, reply_markup=None, parse_mode=None, quote: bool = False):
    if not message:
        return None
    try:
        return await message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            quote=quote
        )
    except RPCError as e:
        logger.warning(f"[safe_reply] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
        
async def safe_delete(message: Message):
    if not message:
        return
    try:
        await message.delete()
        logger.info("Message deleted", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except RPCError as e:
        logger.warning(f"[safe_delete] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_delete] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

async def safe_forward(message: Message, chat_id: int):
    try:
        await message.forward(chat_id)
        logger.info("Message forwarded", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except (ChatWriteForbidden, PeerIdInvalid) as e:
        logger.error(f"Cannot forward to chat {chat_id}: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"Failed to forward message to chat {chat_id}: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

@Client.on_message(filters.command("ping") & filters.private)
async def ping_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < PING_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for ping command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /ping again.")
            return
        spam_block[user_id] = now

        logger.info("Ping command triggered", extra=logger_context)
        start_t = time()
        rm = None
        try:
            rm = await safe_reply(message, "🏓 Pinging...")
        except Exception as e:
            logger.error(f"Failed to send ping response: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to process ping.")
            return

        end_t = time()
        time_taken_s = (end_t - start_t) * 1000

        try:
            latency = await calculate_latency()
            logger.info(f"Latency calculated: {latency}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to calculate latency: {e}", extra=logger_context)
            latency = "N/A"

        try:
            system_info = get_system_info(start_time)
            logger.info("System info retrieved", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to get system info: {e}", extra=logger_context)
            await safe_edit(rm, "❌ Failed to retrieve system information.")
            return

        try:
            await safe_edit(
                rm,
                f"<blockquote>🏓 Ping Status</blockquote>\n\n"
                f"📡 <b>Response:</b> {time_taken_s:.3f} ms\n"
                f"📶 <b>Latency:</b> {latency}\n\n"
                f"{system_info}",
                parse_mode=enums.ParseMode.HTML
            )
            logger.info("Ping status message updated", extra=logger_context)
        except FloodWait as fw:
            logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            await safe_edit(
                rm,
                f"<blockquote>🏓 Ping Status</blockquote>\n\n"
                f"📡 <b>Response:</b> {time_taken_s:.3f} ms\n"
                f"📶 <b>Latency:</b> {latency}\n\n"
                f"{system_info}",
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to edit ping message: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to update ping status.")
            return

        try:
            await add_log_usage(user_id, "ping")
            logger.info("Ping command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                await safe_delete(rm)
                await safe_delete(message)
                logger.info("Ping messages deleted after 60s", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete ping messages: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in ping_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.")
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for ping", extra=logger_context)

async def safe_edit(message: Message, text: str, parse_mode=None, reply_markup=None):
    if not message:
        return None
    try:
        return await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except RPCError as e:
        logger.warning(f"[safe_edit] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_edit] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
        
async def safe_reply_sticker(message: Message, sticker_id: str):
    if not message:
        return None
    try:
        return await message.reply_sticker(sticker_id)
    except RPCError as e:
        logger.warning(f"[safe_reply_sticker] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply_sticker] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

@Client.on_message(filters.command("alive") & filters.private)
async def check_alive(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < ALIVE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for alive command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /alive again.")
            return
        spam_block[user_id] = now

        logger.info("Alive command triggered", extra=logger_context)
        sticker = None
        text = None
        try:
            sticker = await safe_reply_sticker(message, "CAACAgIAAxkBAAEBVAlmCYqbLub_o5pVUOEwbqhV8kRytgACRBkAAgjh2UlSqev16oISqB4E")
            if not sticker:
                logger.warning("Failed to send sticker", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send sticker: {e}", extra=logger_context)

        try:
            text = await safe_reply(message, "🎉 I'm alive and kicking! 🚀\nUse /start to get going!")
            if not text:
                logger.warning("Failed to send text response", extra=logger_context)
                await safe_reply(message, "❌ Failed to send alive status.")
                return
        except Exception as e:
            logger.error(f"Failed to send text response: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send alive status.")
            return

        try:
            await add_log_usage(user_id, "alive")
            logger.info("Alive command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                if sticker:
                    await safe_delete(sticker)
                if text:
                    await safe_delete(text)
                await safe_delete(message)
                logger.info("Alive messages deleted after 60s", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete alive messages: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in check_alive: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.")
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for alive", extra=logger_context)

@Client.on_message(filters.command("system") & filters.private)
async def send_system_info(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SYSTEM_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for system command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /system again.")
            return
        spam_block[user_id] = now

        try:
            system_info = get_system_info(start_time)
            logger.info("System info retrieved", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to get system info: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to retrieve system information.")
            return

        try:
            latency = await calculate_latency()
            logger.info(f"Latency calculated: {latency}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to calculate latency: {e}", extra=logger_context)
            latency = "N/A"

        try:
            await safe_reply(
                message,
                f"{system_info}\n📶 <b>Latency:</b> {latency}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔒 Close", callback_data="close_system")]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
            logger.info("System info message sent", extra=logger_context)
        except FloodWait as fw:
            logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            await safe_reply(
                message,
                f"{system_info}\n📶 <b>Latency:</b> {latency}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔒 Close", callback_data="close_system")]
                ]),
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send system info message: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send system information.")

        try:
            await add_log_usage(user_id, "system")
            logger.info("System command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in send_system_info: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.")
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for system", extra=logger_context)

@Client.on_callback_query(filters.regex("close_system"))
async def close_system_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SYSTEM_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close_system callback", extra=logger_context)
            await callback_query.answer("🛑 Please wait before closing.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Close system callback triggered", extra=logger_context)
        try:
            await callback_query.message.delete()
            logger.info("System info message closed", extra=logger_context)
        except RPCError as e:
            logger.warning(f"Telegram RPC error in close_system: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message due to Telegram error.", show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in close_system: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message.", show_alert=True)
        else:
            await callback_query.answer("✅ Message closed.", show_alert=False)

    except Exception as e:
        logger.error(f"Fatal error in close_system_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close_system", extra=logger_context)

async def safe_reply_photo(message: Message, photo: str, caption: str, reply_markup=None, parse_mode=None, quote: bool = False):
    if not message:
        return None
    try:
        return await message.reply_photo(
            photo=photo,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            quote=quote
        )
    except RPCError as e:
        logger.warning(f"[safe_reply_photo] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply_photo] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

@Client.on_message(filters.command("id") & filters.private)
async def show_id(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < ID_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for id command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /id again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("ID command triggered", extra=logger_context)
        try:
            user = message.from_user
            first_name = user.first_name or "N/A"
            last_name = user.last_name or "N/A"
            username = f"@{user.username}" if user.username else "N/A"
            dc_id = user.dc_id or "N/A"
            status = user.status.value if user.status else "N/A"
            output = (
                f"<blockquote>🆔 User ID Details</blockquote>\n\n"
                f"👤 <b>Name:</b> {first_name} {last_name}\n"
                f"📛 <b>Username:</b> {username}\n"
                f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
                f"🌍 <b>Data Centre:</b> <code>{dc_id}</code>\n"
                f"📊 <b>Status:</b> {status.title()}\n"
                f"🔗 <b>Profile:</b> <a href='tg://user?id={user_id}'>View</a>"
            )
        except Exception as e:
            logger.error(f"Failed to format user info: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to retrieve user details.", quote=True)
            return

        try:
            await safe_reply(
                message,
                output,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔒 Close", callback_data="close_id")]
                ]),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info("ID details sent", extra=logger_context)
        except FloodWait as fw:
            logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            await safe_reply(
                message,
                output,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔒 Close", callback_data="close_id")]
                ]),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
        except Exception as e:
            logger.error(f"Failed to send ID details: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send user details.", quote=True)
            return

        try:
            await add_log_usage(user_id, "id")
            logger.info("ID command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in show_id: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for id", extra=logger_context)

@Client.on_message(filters.command("info") & filters.private)
async def user_info(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < INFO_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for info command", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before using /info again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Info command triggered", extra=logger_context)
        status_msg = None
        try:
            status_msg = await safe_reply(message, "🔎 Gathering info...")
        except Exception as e:
            logger.error(f"Failed to send status message: {e}", extra=logger_context)

        try:
            target_user_id = user_id
            if message.reply_to_message and message.reply_to_message.from_user:
                target_user_id = message.reply_to_message.from_user.id
            user = await client.get_users(target_user_id)
            first_name = user.first_name or "N/A"
            last_name = user.last_name or "N/A"
            username = f"@{user.username}" if user.username else "N/A"
            dc_id = user.dc_id or "N/A"
            status = user.status.value if user.status else "N/A"
            output = (
                f"🔍 User Profile\n\n"
                f"<blockquote>"
                f"👤 <b>Name:</b> {first_name} {last_name}\n"
                f"📛 <b>Username:</b> {username}\n"
                f"🆔 <b>ID:</b> <code>{target_user_id}</code>\n"
                f"🌍 <b>Data Centre:</b> <code>{dc_id}</code>\n"
                f"📊 <b>Status:</b> {status.title()}\n"
                f"🔗 <b>Profile:</b> <a href='tg://user?id={target_user_id}'>View</a>"
                f"</blockquote>"
            )
            buttons = [
                [InlineKeyboardButton("ℹ️ More Details", callback_data=f"more_info:{target_user_id}")],
                [InlineKeyboardButton("🔒 Close", callback_data="close_info")]
            ]
            reply_markup = InlineKeyboardMarkup(buttons)
        except Exception as e:
            logger.error(f"Failed to retrieve user info: {e}", extra=logger_context)
            await safe_delete(status_msg)
            await safe_reply(message, "❌ Failed to retrieve user profile.", quote=True)
            return

        try:
            if user.photo:
                try:
                    photo = await client.download_media(user.photo.big_file_id)
                    await safe_reply_photo(
                        message,
                        photo=photo,
                        caption=output,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
                    os.remove(photo)
                except Exception as e:
                    logger.warning(f"Failed to send photo: {e}", extra=logger_context)
                    await safe_reply(
                        message,
                        output,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
            else:
                await safe_reply(
                    message,
                    output,
                    reply_markup=reply_markup,
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
            logger.info("User info sent", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send user info: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send user profile.", quote=True)

        try:
            await safe_delete(status_msg)
            logger.info("Status message deleted", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to delete status message: {e}", extra=logger_context)

        try:
            await add_log_usage(user_id, "info")
            logger.info("Info command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in user_info: {e}", extra=logger_context)
        await safe_delete(status_msg)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for info", extra=logger_context)
            

@Client.on_callback_query(filters.regex("close_(id|info|faq|system|wiki|news)"))
async def close_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < CLOSE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close callback", extra=logger_context)
            await callback_query.answer("🛑 Please wait before closing.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Close callback triggered", extra=logger_context)
        try:
            await safe_delete(callback_query.message)
            logger.info("Message closed", extra=logger_context)
            await callback_query.answer("✅ Message closed.", show_alert=False)
        except RPCError as e:
            logger.warning(f"Telegram RPC error in close_callback: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message due to Telegram error.", show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in close_callback: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in close_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close", extra=logger_context)
            

@Client.on_callback_query(filters.regex("faq"))
async def faq_callback(client: Client, callback_query: CallbackQuery):
    user_name = callback_query.from_user.first_name or callback_query.from_user.username or "User"
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data="back_start")]]
    await callback_query.message.edit_text(
        faq_script.FAQ_TXT.format(user_name),
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=enums.ParseMode.HTML
    )
    await callback_query.answer("FAQ displayed!")

@Client.on_callback_query(filters.regex("back_start"))
async def back_start_callback(client: Client, callback_query: CallbackQuery):
    user_name = callback_query.from_user.first_name or callback_query.from_user.username or "User"
    current_time = datetime.now(pytz.timezone("Asia/Kolkata"))
    curr_time = current_time.hour
    if curr_time < 12:
        greeting = "Good Morning 🌞"
    elif curr_time < 17:
        greeting = "Good Afternoon 🌓"
    elif curr_time < 21:
        greeting = "Good Evening 🌘"
    else:
        greeting = "Good Night 🌑"
    buttons = []
    if os.getenv("FAQ", "False").lower() == "true":
        buttons.append(InlineKeyboardButton("FAQ", callback_data="faq"))
    if os.getenv("SOURCE_BUTTON", "False").lower() == "true":
        source_url = os.getenv("SOURCE", "https://github.com/")
        buttons.append(InlineKeyboardButton("SOURCE", url=source_url))
    reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None
    await callback_query.message.edit_text(
        script.START_TXT.format(user_name, greeting),
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.HTML
    )
    await callback_query.answer("@NxMirror 📍")


@Client.on_callback_query(filters.regex(r"more_info:\d+"))
async def more_info_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < INFO_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for more_info callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before viewing more info.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("More info callback triggered", extra=logger_context)
        try:
            target_user_id = int(callback_query.data.split(":")[1])
            user = await client.get_users(target_user_id)
            is_self = "Yes" if user.is_self else "No"
            is_contact = "Yes" if user.is_contact else "No"
            is_mutual_contact = "Yes" if user.is_mutual_contact else "No"
            is_deleted = "Yes" if user.is_deleted else "No"
            is_frozen = "Yes" if user.is_frozen else "No"
            is_bot = "Yes" if user.is_bot else "No"
            is_verified = "Yes" if user.is_verified else "No"
            is_restricted = "Yes" if user.is_restricted else "No"
            is_scam = "Yes" if user.is_scam else "No"
            is_fake = "Yes" if user.is_fake else "No"
            is_support = "Yes" if user.is_support else "No"
            is_premium = "Yes" if user.is_premium else "No"
            is_contacts_only = "Yes" if user.is_contacts_only else "No"
            is_bot_business = "Yes" if user.is_bot_business else "No"
            last_online = user.last_online_date.strftime("%Y-%m-%d %H:%M:%S") if user.last_online_date else "N/A"
            next_offline = user.next_offline_date.strftime("%Y-%m-%d %H:%M:%S") if user.next_offline_date else "N/A"
            language_code = user.language_code or "N/A"
            emoji_status = user.emoji_status.emoji if user.emoji_status else "N/A"
            restrictions = ", ".join([r.reason for r in user.restrictions]) if user.restrictions else "None"
            active_users = user.active_users or "N/A"
            frozen_icon = user.frozen_icon or "N/A"
            output = (
                f"🔍 Additional User Details\n\n"
                f"<blockquote>"
                f"🤖 <b>Bot Account:</b> {is_bot}\n"
                f"👤 <b>Own Account:</b> {is_self}\n"
                f"📇 <b>In Contacts:</b> {is_contact}\n"
                f"🤝 <b>Mutual Contact:</b> {is_mutual_contact}\n"
                f"🗑️ <b>Account Deleted:</b> {is_deleted}\n"
                f"🧊 <b>Account Frozen:</b> {is_frozen}\n"
                f"✅ <b>Verified by Telegram:</b> {is_verified}\n"
                f"🚫 <b>Restricted Account:</b> {is_restricted}\n"
                f"⚠️ <b>Flagged as Scam:</b> {is_scam}\n"
                f"🎭 <b>Flagged as Fake:</b> {is_fake}\n"
                f"🛠️ <b>Telegram Support:</b> {is_support}\n"
                f"⭐ <b>Premium Account:</b> {is_premium}\n"
                f"🔒 <b>Messages from Contacts Only:</b> {is_contacts_only}\n"
                f"💼 <b>Business Bot:</b> {is_bot_business}\n"
                f"📅 <b>Last Online:</b> {last_online}\n"
                f"⏰ <b>Next Offline:</b> {next_offline}\n"
                f"🌐 <b>Language:</b> {language_code}\n"
                f"😀 <b>Emoji Status:</b> {emoji_status}\n"
                f"🚫 <b>Restrictions:</b> {restrictions}\n"
                f"👥 <b>Bot Active Users:</b> {active_users}\n"
                f"🧊 <b>Frozen Icon:</b> {frozen_icon}"
                f"</blockquote>"
            )
            buttons = [
                [InlineKeyboardButton("🔙 Back", callback_data=f"basic_info:{target_user_id}")],
                [InlineKeyboardButton("🔒 Close", callback_data="close_info")]
            ]
            await safe_edit(
                callback_query.message,
                output,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer("More details displayed!")
            logger.info("More info displayed", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to display more info: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to display more details.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in more_info_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for more_info", extra=logger_context)

@Client.on_callback_query(filters.regex(r"basic_info:\d+"))
async def basic_info_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < INFO_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for basic_info callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before viewing basic info.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Basic info callback triggered", extra=logger_context)
        try:
            target_user_id = int(callback_query.data.split(":")[1])
            user = await client.get_users(target_user_id)
            first_name = user.first_name or "N/A"
            last_name = user.last_name or "N/A"
            username = f"@{user.username}" if user.username else "N/A"
            dc_id = user.dc_id or "N/A"
            status = user.status.value if user.status else "N/A"
            output = (
                f"🔍 User Profile\n\n"
                f"<blockquote>"
                f"👤 <b>Name:</b> {first_name} {last_name}\n"
                f"📛 <b>Username:</b> {username}\n"
                f"🆔 <b>ID:</b> <code>{target_user_id}</code>\n"
                f"🌍 <b>Data Centre:</b> <code>{dc_id}</code>\n"
                f"📊 <b>Status:</b> {status.title()}\n"
                f"🔗 <b>Profile:</b> <a href='tg://user?id={target_user_id}'>View</a>"
                f"</blockquote>"
            )
            buttons = [
                [InlineKeyboardButton("ℹ️ More Details", callback_data=f"more_info:{target_user_id}")],
                [InlineKeyboardButton("🔒 Close", callback_data="close_info")]
            ]
            await safe_edit(
                callback_query.message,
                output,
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer("Basic info displayed!")
            logger.info("Basic info displayed", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to display basic info: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to display basic info.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in basic_info_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for basic_info", extra=logger_context)


@Client.on_message(filters.command("help") & filters.private)
async def help_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        logger.info("Help command triggered", extra=logger_context)
        is_admin = user_id in ADMINS

        buttons = [
            [InlineKeyboardButton("📜 User Commands", callback_data="help_user")],
        ]
        if is_admin:
            buttons.append([InlineKeyboardButton("👑 Admin Commands", callback_data="help_admin")])
        buttons.append([InlineKeyboardButton("🔒 Close", callback_data="help_close")])

        output = (
            f"🤖 <b>Welcome to @{client.me.username} Help!</b>\n\n"
            "Explore available commands below. Click a button to view details."
        )
        response_msg = await safe_reply(
            message,
            output,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        if not response_msg:
            await safe_reply(
                message,
                "❌ Failed to send help menu.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return
        logger.info("Help menu sent", extra=logger_context)

        try:
            await add_log_usage(user_id, "help")
            logger.info("Help command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            await safe_delete(response_msg)
            await safe_delete(message)
            logger.info("Help messages deleted after 60s", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to delete messages: {e}", extra=logger_context)

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
        await asyncio.sleep(fw.value)
        await help_command(client, message)  # retry

    except Exception as e:
        logger.error(f"Fatal error in help_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)


@Client.on_callback_query(filters.regex(r"help_(user|admin|close|back)"))
async def help_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)
    data = callback_query.data

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < HELP_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for help callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before interacting.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info(f"Help callback triggered: {data}", extra=logger_context)

        if data == "help_close":
            await safe_delete(callback_query.message)
            await callback_query.answer("✅ Help menu closed!")
            logger.info("Help menu closed", extra=logger_context)
            return

        if data == "help_back":
            buttons = [
                [InlineKeyboardButton("📜 User Commands", callback_data="help_user")],
            ]
            if user_id in ADMINS:
                buttons.append([InlineKeyboardButton("👑 Admin Commands", callback_data="help_admin")])
            buttons.append([InlineKeyboardButton("🔒 Close", callback_data="help_close")])
            await callback_query.message.edit_text(
                f"🤖 <b>Welcome to @{client.me.username} Help!</b>\n\nExplore available commands below. Click a button to view details.",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer()
            logger.info("Returned to help main menu", extra=logger_context)
            return

        is_admin = user_id in ADMINS
        if data == "help_admin" and not is_admin:
            await callback_query.answer("❌ Admin commands are restricted.", show_alert=True)
            logger.warning("Non-admin attempted to view admin commands", extra=logger_context)
            return

        if data == "help_user":
            cmd_list = {k: v for k, v in Bot_cmds.items() if k not in ADMIN_COMMANDS}
            title = "📜 User Commands"
        else:  # help_admin
            cmd_list = {k: v for k, v in Bot_cmds.items() if k in ADMIN_COMMANDS}
            title = "👑 Admin Commands"

        if not cmd_list:
            await callback_query.message.edit_text(
                f"{title}\n\n⚠️ <b>No commands available.</b>",
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help_back")],
                    [InlineKeyboardButton("🔒 Close", callback_data="help_close")]
                ])
            )
            logger.info(f"No {data} commands available", extra=logger_context)
            return

        formatted = "\n".join([f"• <code>/{cmd}</code> - {desc}" for cmd, desc in cmd_list.items()])
        buttons = [
            [InlineKeyboardButton("🔙 Back", callback_data="help_back")],
            [InlineKeyboardButton("🔒 Close", callback_data="help_close")]
        ]
        await callback_query.message.edit_text(
            f"{title}\n\n{formatted}",
            parse_mode=enums.ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        await callback_query.answer()
        logger.info(f"{data} commands displayed", extra=logger_context)

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s in help callback", extra=logger_context)
        await asyncio.sleep(fw.value)
        await callback_query.answer("❌ Retry failed due to rate limits.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in help_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)

    finally:
        spam_block.pop(user_id, None)
        logger.debug("Rate limit cleared for help callback", extra=logger_context)
