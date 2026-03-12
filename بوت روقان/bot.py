#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              🤖 بوت ديسكورد الكامل - ملف واحد              ║
║                                                              ║
║  الأوامر:                                                   ║
║   !play / !stop / !pause / !resume  - موسيقى               ║
║   !toaudio [رابط]                   - تحويل فيديو→MP3      ║
║   !prayer [مدينة]                   - أوقات الصلاة          ║
║   !bc [رسالة]                       - إذاعة للـ DM          ║
║   !b / !tm / !k                     - باند/تايم أوت/كيك    ║
║   !warn / !unwarn / !warns          - التحذيرات            ║
║   !n [نيك نيم]                      - منشن بالنيك نيم      ║
╚══════════════════════════════════════════════════════════════╝

التثبيت:
    pip install discord.py yt-dlp aiohttp PyNaCl

الاستخدام:
    python bot.py
"""

# ══════════════════════════════════════════════════════════════
#  تثبيت المكتبات تلقائياً إذا مو موجودة
# ══════════════════════════════════════════════════════════════
import subprocess, sys, os, shutil, platform

def _install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

for _lib in ["discord.py", "yt-dlp", "aiohttp", "PyNaCl"]:
    _import_name = _lib.replace(".py","").replace("-","_").split("[")[0]
    try:
        __import__(_import_name)
    except ImportError:
        print(f"📦 جاري تثبيت {_lib}...")
        _install(_lib)

# ══════════════════════════════════════════════════════════════
#  كشف FFmpeg تلقائياً
# ══════════════════════════════════════════════════════════════
def find_ffmpeg():
    # أولاً: في PATH
    if shutil.which("ffmpeg"):
        return shutil.which("ffmpeg")

    _here = os.path.dirname(os.path.abspath(__file__))

    # مسارات ويندوز — الأولوية لمجلد bin بجانب bot.py
    win_paths = [
        # ← مجلد bin بجانب bot.py مباشرة (وضعت مجلد bin هنا)
        os.path.join(_here, "bin", "ffmpeg.exe"),
        # بجانب bot.py مباشرة
        os.path.join(_here, "ffmpeg.exe"),
        # داخل مجلد ffmpeg
        os.path.join(_here, "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(_here, "ffmpeg", "ffmpeg.exe"),
        # مسارات النظام الشائعة
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.expanduser("~"), "ffmpeg", "bin", "ffmpeg.exe"),
    ]
    unix_paths = [
        "/usr/bin/ffmpeg",
        "/usr/local/bin/ffmpeg",
        "/opt/homebrew/bin/ffmpeg",
    ]

    for p in (win_paths if platform.system() == "Windows" else unix_paths):
        if os.path.isfile(p):
            return p
    return None

FFMPEG_PATH = find_ffmpeg()

if FFMPEG_PATH:
    print(f"✅ FFmpeg موجود: {FFMPEG_PATH}")
else:
    print("⚠️  FFmpeg غير موجود في النظام!")
    print("   الحل: حمّل ffmpeg من https://www.gyan.dev/ffmpeg/builds/")
    print("   وضع ffmpeg.exe بجانب bot.py مباشرة ثم أعد التشغيل")

# ══════════════════════════════════════════════════════════════
#  استيراد المكتبات
# ══════════════════════════════════════════════════════════════
import discord
from discord.ext import commands, tasks
import asyncio
import aiohttp
import yt_dlp
import json
import datetime

# ╔══════════════════════════════════════════════════════════════╗
# ║                     ⚙️  الإعدادات                           ║
# ╚══════════════════════════════════════════════════════════════╝

TOKEN  = ""   # ← ضع توكن البوت هنا
PREFIX = "!"

# إعدادات أوقات الصلاة التلقائية (اختياري)
PRAYER_CHANNEL_ID = None   # ← ضع ID قناة الصلاة (مثال: 1234567890)
PRAYER_CITY       = "Jeddah"
PRAYER_COUNTRY    = "SA"

# ملف حفظ التحذيرات
WARNINGS_FILE = "warnings.json"

# ══════════════════════════════════════════════════════════════
#  إعدادات FFmpeg و yt-dlp
# ══════════════════════════════════════════════════════════════
_ffmpeg_extra = {"executable": FFMPEG_PATH} if FFMPEG_PATH else {}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
    **_ffmpeg_extra,
}

YDL_STREAM_OPTS = {
    "format": "bestaudio[ext=webm]/bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,
}
if FFMPEG_PATH:
    YDL_STREAM_OPTS["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

YDL_DOWNLOAD_OPTS = {
    "format": "bestaudio/best",
    "outtmpl": "downloads/%(id)s.%(ext)s",
    "postprocessors": [{
        "key": "FFmpegExtractAudio",
        "preferredcodec": "mp3",
        "preferredquality": "192",
    }],
    "quiet": True,
    "no_warnings": True,
}
if FFMPEG_PATH:
    YDL_DOWNLOAD_OPTS["ffmpeg_location"] = os.path.dirname(FFMPEG_PATH)

# ╔══════════════════════════════════════════════════════════════╗
# ║                  🗃️  مساعدات التحذيرات                     ║
# ╚══════════════════════════════════════════════════════════════╝

def load_warnings() -> dict:
    if not os.path.exists(WARNINGS_FILE):
        return {}
    with open(WARNINGS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_warnings(data: dict) -> None:
    with open(WARNINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ╔══════════════════════════════════════════════════════════════╗
# ║                    🤖 تهيئة البوت                           ║
# ╚══════════════════════════════════════════════════════════════╝

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)

# ╔══════════════════════════════════════════════════════════════╗
# ║               🔔 أحداث البوت  (Events)                     ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.event
async def on_ready():
    print("\n" + "═" * 50)
    print(f"  🤖  البوت شغال:  {bot.user.name}")
    print(f"  🆔  ID:          {bot.user.id}")
    print(f"  🌐  سيرفرات:     {len(bot.guilds)}")
    print(f"  🎵  FFmpeg:      {'✅ ' + FFMPEG_PATH if FFMPEG_PATH else '❌ غير موجود'}")
    print("═" * 50 + "\n")
    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.listening, name="!help")
    )
    if PRAYER_CHANNEL_ID:
        auto_prayer_notify.start()


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ ما عندك صلاحية تسوي هذا الأمر!")
    elif isinstance(error, commands.CommandNotFound):
        pass
    elif isinstance(error, commands.CommandInvokeError):
        orig = error.original
        err_str = str(orig).lower()
        if any(k in err_str for k in ["ffmpeg", "davey", "nacl", "voice"]):
            await ctx.send(
                "❌ **مشكلة في FFmpeg أو PyNaCl!**\n"
                "```\n"
                "الحل:\n"
                "1. حمّل FFmpeg من:\n"
                "   https://www.gyan.dev/ffmpeg/builds/\n"
                "2. فك الضغط وضع ffmpeg.exe بجانب bot.py\n"
                "3. pip install PyNaCl\n"
                "4. أعد تشغيل البوت\n"
                "```"
            )
        else:
            await ctx.send(f"❌ خطأ: {str(orig)[:200]}")
    else:
        await ctx.send(f"❌ خطأ: {str(error)[:150]}")


# ╔══════════════════════════════════════════════════════════════╗
# ║                    📋 أمر المساعدة                          ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.command(name="help", aliases=["مساعدة"])
async def help_cmd(ctx):
    ffmpeg_status = "✅ شغال" if FFMPEG_PATH else "❌ غير موجود - ضع ffmpeg.exe بجانب bot.py"
    embed = discord.Embed(
        title="📋 قائمة الأوامر الكاملة",
        color=0x5865F2,
        timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.add_field(
        name="🎵 الموسيقى",
        value=(
            "`!play [رابط أو اسم]` — تشغيل موسيقى\n"
            "`!stop` — إيقاف وقطع الاتصال\n"
            "`!pause` — إيقاف مؤقت\n"
            "`!resume` — استكمال\n"
            "`!toaudio [رابط]` — تحويل فيديو → MP3"
        ), inline=False,
    )
    embed.add_field(
        name="🕌 أوقات الصلاة",
        value="`!prayer [مدينة] [دولة]` — عرض الأوقات\nمثال: `!prayer Riyadh SA`",
        inline=False,
    )
    embed.add_field(name="📢 الإذاعة",   value="`!bc [الرسالة]` — يرسل رسالة لـ DM كل الأعضاء", inline=False)
    embed.add_field(
        name="🔨 الإدارة",
        value=(
            "`!b [ID] [سبب]` — باند\n"
            "`!tm [ID] [سبب]` — تايم أوت ساعة\n"
            "`!k [ID] [سبب]` — كيك\n"
            "`!unban [ID]` — رفع الباند"
        ), inline=False,
    )
    embed.add_field(
        name="⚠️ التحذيرات",
        value=(
            "`!warn [ID] [سبب]` — تحذير\n"
            "`!unwarn [ID]` — إزالة آخر تحذير\n"
            "`!warns [ID]` — عرض التحذيرات"
        ), inline=False,
    )
    embed.add_field(
        name="✏️ النيك نيم",
        value=(
            "`!n [نيك نيم]` — بحث ومنشن عضو بالنيك نيم\n"
            "`!setnick @عضو [نيك]` — تغيير نيك نيم عضو"
        ), inline=False,
    )
    embed.set_footer(text=f"FFmpeg: {ffmpeg_status}")
    await ctx.send(embed=embed)


# ╔══════════════════════════════════════════════════════════════╗
# ║                  🎵 الموسيقى  (Music)                       ║
# ╚══════════════════════════════════════════════════════════════╝

async def _get_audio_info(url: str) -> dict:
    loop = asyncio.get_event_loop()

    # إذا مو رابط → بحث يوتيوب مباشر
    search_url = url if url.startswith("http") else f"ytsearch1:{url}"

    with yt_dlp.YoutubeDL(YDL_STREAM_OPTS) as ydl:
        info = await loop.run_in_executor(
            None, lambda: ydl.extract_info(search_url, download=False)
        )

    # معالجة نتائج البحث
    if "entries" in info:
        entries = [e for e in (info["entries"] or []) if e]
        if not entries:
            raise ValueError("ما لقيت نتائج! جرب رابط يوتيوب مباشر.")
        info = entries[0]

    if not info:
        raise ValueError("ما قدرت أجيب معلومات الفيديو.")

    return info


@bot.command(name="play", aliases=["p", "شغل"])
async def play(ctx, *, url: str = None):
    if not url:
        await ctx.send("❌ اكتب رابط أو اسم الأغنية!\nمثال: `!play فيروز`")
        return

    if not FFMPEG_PATH:
        await ctx.send(
            "❌ **FFmpeg مو موجود!**\n"
            "1. حمّله من: https://www.gyan.dev/ffmpeg/builds/\n"
            "2. فك الضغط وضع `ffmpeg.exe` بجانب `bot.py` مباشرة\n"
            "3. أعد تشغيل البوت"
        )
        return

    if not ctx.author.voice:
        await ctx.send("❌ لازم تكون في قناة صوت أولاً!")
        return

    channel = ctx.author.voice.channel

    if ctx.voice_client is None:
        try:
            await channel.connect()
        except Exception as e:
            await ctx.send(f"❌ فشل الاتصال بالقناة: {e}")
            return
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()

    msg = await ctx.send("🔍 جاري البحث...")

    try:
        info      = await _get_audio_info(url)
        audio_url = info["url"]
        title     = info.get("title", "Unknown")
        duration  = info.get("duration", 0)
        thumbnail = info.get("thumbnail", "")
        webpage   = info.get("webpage_url", url)

        source = discord.FFmpegPCMAudio(audio_url, **FFMPEG_OPTIONS)
        ctx.voice_client.play(discord.PCMVolumeTransformer(source, volume=0.8))

        mins, secs = divmod(int(duration), 60)
        embed = discord.Embed(title="▶️ يشتغل الحين", color=0x1DB954, url=webpage)
        embed.add_field(name="🎵 الأغنية", value=title,                 inline=False)
        embed.add_field(name="⏱️ المدة",   value=f"{mins}:{secs:02d}", inline=True)
        embed.add_field(name="📻 القناة",  value=channel.mention,       inline=True)
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text=f"طلب من: {ctx.author.display_name}")
        await msg.edit(content=None, embed=embed)

    except yt_dlp.utils.DownloadError as e:
        await msg.edit(content=f"❌ فشل تحميل الفيديو. تأكد من الرابط.\n`{str(e)[:100]}`")
    except Exception as e:
        await msg.edit(content=f"❌ خطأ: {str(e)[:150]}")


@bot.command(name="stop", aliases=["وقف"])
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        await ctx.send("⏹️ تم إيقاف الموسيقى.")
    else:
        await ctx.send("❌ البوت مو في قناة صوت!")


@bot.command(name="pause", aliases=["بوز"])
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("⏸️ إيقاف مؤقت.")
    else:
        await ctx.send("❌ ما في شيء يشتغل!")


@bot.command(name="resume", aliases=["استكمل"])
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("▶️ تم الاستكمال.")
    else:
        await ctx.send("❌ ما في شيء متوقف!")


# ══════════════════════════════════════════════════════════════
#  تحويل فيديو → MP3
# ══════════════════════════════════════════════════════════════

@bot.command(name="toaudio", aliases=["convert", "mp3", "تحويل"])
async def to_audio(ctx, url: str = None):
    if not url:
        await ctx.send("❌ أرسل رابط الفيديو!\nمثال: `!toaudio https://youtu.be/XXXXXXX`")
        return

    if not FFMPEG_PATH:
        await ctx.send("❌ **FFmpeg مو موجود!**\nحمّله وضع `ffmpeg.exe` بجانب `bot.py`")
        return

    msg = await ctx.send("⏳ جاري التحقق من الفيديو...")
    os.makedirs("downloads", exist_ok=True)

    try:
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True}) as ydl:
            info = await loop.run_in_executor(
                None, lambda: ydl.extract_info(url, download=False)
            )
        title    = info.get("title", "audio")
        duration = info.get("duration", 0)

        if duration > 900:
            await msg.edit(content="❌ الفيديو أطول من 15 دقيقة!")
            return

        await msg.edit(content=f"🔄 جاري التحويل...\n🎵 **{title}**")

        with yt_dlp.YoutubeDL(YDL_DOWNLOAD_OPTS) as ydl:
            await loop.run_in_executor(None, lambda: ydl.download([url]))

        mp3_file = None
        for fname in os.listdir("downloads"):
            if fname.endswith(".mp3"):
                mp3_file = os.path.join("downloads", fname)
                break

        if not mp3_file:
            await msg.edit(content="❌ فشل إيجاد الملف بعد التحويل!")
            return

        size_mb = os.path.getsize(mp3_file) / (1024 * 1024)
        if size_mb > 25:
            await msg.edit(content=f"❌ الملف كبير جداً ({size_mb:.1f} MB). الحد 25MB.")
            os.remove(mp3_file)
            return

        await msg.edit(content=f"✅ تم! جاري الرفع... ({size_mb:.1f} MB)")
        safe = "".join(c for c in title if c.isalnum() or c in " _-")[:50]
        mins, secs = divmod(int(duration), 60)
        await ctx.send(
            content=f"🎵 **{title}**\n⏱️ {mins}:{secs:02d}",
            file=discord.File(mp3_file, filename=f"{safe}.mp3"),
        )
        await msg.delete()
        os.remove(mp3_file)

    except discord.HTTPException:
        await msg.edit(content="❌ الملف كبير جداً لإرساله!")
    except Exception as e:
        await msg.edit(content=f"❌ فشل التحويل: {str(e)[:120]}")


# ╔══════════════════════════════════════════════════════════════╗
# ║               🕌 أوقات الصلاة  (Prayer Times)              ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.command(name="prayer", aliases=["salah", "صلاة", "اوقات"])
async def prayer_times(ctx, city: str = "Jeddah", country: str = "SA"):
    msg = await ctx.send(f"🕌 جاري جلب أوقات الصلاة لـ **{city}**...")
    try:
        today   = datetime.date.today()
        api_url = (
            f"https://api.aladhan.com/v1/timingsByCity"
            f"?city={city}&country={country}&method=4"
            f"&date={today.day}-{today.month}-{today.year}"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    await msg.edit(content="❌ فشل جلب البيانات. تأكد من اسم المدينة.")
                    return
                data = await resp.json()

        timings   = data["data"]["timings"]
        date_info = data["data"]["date"]["readable"]
        hijri     = data["data"]["date"]["hijri"]
        hijri_str = f"{hijri['day']} {hijri['month']['ar']} {hijri['year']}هـ"

        prayers = {
            "🌅 الفجر":  timings["Fajr"],
            "🌞 الشروق": timings["Sunrise"],
            "☀️ الظهر":  timings["Dhuhr"],
            "🌤️ العصر": timings["Asr"],
            "🌇 المغرب": timings["Maghrib"],
            "🌙 العشاء": timings["Isha"],
        }

        embed = discord.Embed(
            title=f"🕌 أوقات الصلاة — {city}",
            description=f"📅 {date_info}\n🌙 {hijri_str}",
            color=0x2ecc71,
            timestamp=datetime.datetime.utcnow(),
        )
        for name, time in prayers.items():
            embed.add_field(name=name, value=f"**{time}**", inline=True)
        embed.set_footer(text="المصدر: aladhan.com | الطريقة: أم القرى")
        await msg.edit(content=None, embed=embed)

    except asyncio.TimeoutError:
        await msg.edit(content="❌ انتهت مهلة الاتصال. جرب مرة ثانية.")
    except Exception as e:
        await msg.edit(content=f"❌ خطأ: {str(e)[:100]}")


@tasks.loop(minutes=1)
async def auto_prayer_notify():
    if not PRAYER_CHANNEL_ID:
        return
    channel = bot.get_channel(PRAYER_CHANNEL_ID)
    if not channel:
        return
    now = datetime.datetime.now().strftime("%H:%M")
    try:
        api_url = (
            f"https://api.aladhan.com/v1/timingsByCity"
            f"?city={PRAYER_CITY}&country={PRAYER_COUNTRY}&method=4"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                data = await resp.json()
        timings = data["data"]["timings"]
        prayer_map = {
            "Fajr": "الفجر 🌅",   "Dhuhr": "الظهر 🌞",
            "Asr":  "العصر 🌤️", "Maghrib": "المغرب 🌇",
            "Isha": "العشاء 🌙",
        }
        for key, name in prayer_map.items():
            if timings.get(key, "")[:5] == now:
                await channel.send(
                    f"@everyone\n🕌 **حان وقت صلاة {name}**\n"
                    f"السلام عليكم ورحمة الله وبركاته 🤍"
                )
    except Exception:
        pass

@auto_prayer_notify.before_loop
async def before_prayer():
    await bot.wait_until_ready()


# ╔══════════════════════════════════════════════════════════════╗
# ║               📢 الإذاعة للـ DM  (Broadcast)               ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.command(name="bc", aliases=["broadcast", "اذاعة"])
@commands.has_permissions(administrator=True)
async def broadcast(ctx, *, message: str = None):
    if not message:
        await ctx.send("❌ اكتب الرسالة!\nمثال: `!bc مرحبا بالجميع 👋`")
        return

    members = [m for m in ctx.guild.members if not m.bot]
    confirm = await ctx.send(
        f"📢 **تأكيد الإرسال**\n"
        f"سيتم إرسال الرسالة التالية لـ **{len(members)}** عضو:\n"
        f"```{message[:400]}```\n"
        f"✅ للتأكيد | ❌ للإلغاء — (30 ثانية)"
    )
    await confirm.add_reaction("✅")
    await confirm.add_reaction("❌")

    def check(reaction, user):
        return (
            user == ctx.author
            and str(reaction.emoji) in ("✅", "❌")
            and reaction.message.id == confirm.id
        )

    try:
        reaction, _ = await bot.wait_for("reaction_add", timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await confirm.edit(content="⏰ انتهى الوقت — تم إلغاء الإرسال.")
        return

    if str(reaction.emoji) == "❌":
        await confirm.edit(content="❌ تم إلغاء الإرسال.")
        return

    embed = discord.Embed(
        title=f"📢 رسالة من {ctx.guild.name}",
        description=message, color=0x3498db,
        timestamp=datetime.datetime.utcnow(),
    )
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)
    embed.set_footer(text=f"أرسلها: {ctx.author.display_name}")

    progress = await ctx.send("📤 جاري الإرسال...")
    success = failed = 0

    for i, member in enumerate(members, 1):
        try:
            await member.send(embed=embed)
            success += 1
        except Exception:
            failed += 1
        if i % 10 == 0:
            await progress.edit(content=f"📤 جاري الإرسال... {i}/{len(members)}")
        await asyncio.sleep(0.6)

    result = discord.Embed(title="✅ اكتمل الإرسال", color=0x2ecc71, timestamp=datetime.datetime.utcnow())
    result.add_field(name="✅ نجح",     value=f"**{success}** عضو", inline=True)
    result.add_field(name="❌ فشل",     value=f"**{failed}** (DM مغلق)", inline=True)
    result.add_field(name="📊 المجموع", value=f"**{len(members)}**", inline=True)
    await progress.edit(content=None, embed=result)


# ╔══════════════════════════════════════════════════════════════╗
# ║              🔨 الإدارة  (Moderation)                       ║
# ╚══════════════════════════════════════════════════════════════╝

async def resolve_member(ctx, member_id: str):
    try:
        mid = int(
            member_id.strip()
            .replace("<@", "").replace(">", "").replace("!", "")
        )
        member = ctx.guild.get_member(mid)
        if not member:
            member = await ctx.guild.fetch_member(mid)
        return member
    except Exception:
        return None


def _mod_embed(title, color, member, reason, moderator):
    embed = discord.Embed(title=title, color=color, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 العضو",   value=f"{member.mention} `{member.id}`", inline=False)
    embed.add_field(name="📝 السبب",   value=reason, inline=False)
    embed.add_field(name="🛡️ المشرف", value=moderator.mention, inline=False)
    embed.set_thumbnail(url=member.display_avatar.url)
    return embed


async def _dm_member(member, title, reason, color):
    try:
        e = discord.Embed(
            title=title, description=f"**السبب:** {reason}",
            color=color, timestamp=datetime.datetime.utcnow()
        )
        await member.send(embed=e)
    except Exception:
        pass


@bot.command(name="b", aliases=["ban", "باند"])
@commands.has_permissions(ban_members=True)
async def ban(ctx, member_id: str = None, *, reason: str = "لم يُذكر سبب"):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!b [ID] [السبب]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ ما قدرت أجد العضو."); return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ رتبة العضو أعلى أو تساوي رتبتك!"); return
    await _dm_member(member, f"🔨 تم حظرك من {ctx.guild.name}", reason, 0xe74c3c)
    try:
        await member.ban(reason=reason)
        await ctx.send(embed=_mod_embed("🔨 تم الحظر", 0xe74c3c, member, reason, ctx.author))
    except discord.Forbidden:
        await ctx.send("❌ ما عندي صلاحية!")


@bot.command(name="unban", aliases=["رفع_باند"])
@commands.has_permissions(ban_members=True)
async def unban(ctx, member_id: str = None):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!unban [ID]`"); return
    try:
        user = await bot.fetch_user(int(member_id.strip()))
        await ctx.guild.unban(user)
        await ctx.send(f"✅ تم رفع الحظر عن **{user}**")
    except Exception as e:
        await ctx.send(f"❌ خطأ: {e}")


@bot.command(name="tm", aliases=["timeout", "mute", "تايم"])
@commands.has_permissions(moderate_members=True)
async def timeout_cmd(ctx, member_id: str = None, *, reason: str = "لم يُذكر سبب"):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!tm [ID] [السبب]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ ما قدرت أجد العضو."); return
    until = discord.utils.utcnow() + datetime.timedelta(hours=1)
    try:
        await member.timeout(until, reason=reason)
        embed = _mod_embed("⏰ تايم أوت", 0xf39c12, member, reason, ctx.author)
        embed.add_field(name="⏱️ المدة", value="ساعة واحدة", inline=True)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عندي صلاحية!")


@bot.command(name="k", aliases=["kick", "طرد"])
@commands.has_permissions(kick_members=True)
async def kick(ctx, member_id: str = None, *, reason: str = "لم يُذكر سبب"):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!k [ID] [السبب]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ ما قدرت أجد العضو."); return
    if member.top_role >= ctx.author.top_role:
        await ctx.send("❌ رتبة العضو أعلى أو تساوي رتبتك!"); return
    await _dm_member(member, f"👢 تم طردك من {ctx.guild.name}", reason, 0xe67e22)
    try:
        await member.kick(reason=reason)
        await ctx.send(embed=_mod_embed("👢 تم الطرد", 0xe67e22, member, reason, ctx.author))
    except discord.Forbidden:
        await ctx.send("❌ ما عندي صلاحية!")


# ╔══════════════════════════════════════════════════════════════╗
# ║              ⚠️  التحذيرات  (Warnings)                      ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.command(name="warn", aliases=["تحذير"])
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member_id: str = None, *, reason: str = "لم يُذكر سبب"):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!warn [ID] [السبب]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ العضو غير موجود."); return

    warnings = load_warnings()
    gid, uid = str(ctx.guild.id), str(member.id)
    warnings.setdefault(gid, {}).setdefault(uid, [])
    warnings[gid][uid].append({
        "reason":  reason,
        "by":      str(ctx.author.id),
        "by_name": str(ctx.author),
        "date":    datetime.datetime.utcnow().isoformat(),
    })
    save_warnings(warnings)
    total = len(warnings[gid][uid])

    await _dm_member(
        member, f"⚠️ تلقيت تحذيراً في {ctx.guild.name}",
        f"{reason}\n**مجموع تحذيراتك:** {total}", 0xf1c40f,
    )
    embed = discord.Embed(title="⚠️ تم التحذير", color=0xf1c40f, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 العضو",            value=f"{member.mention} `{member.id}`", inline=False)
    embed.add_field(name="📝 السبب",            value=reason, inline=False)
    embed.add_field(name="🛡️ المشرف",          value=ctx.author.mention, inline=True)
    embed.add_field(name="📊 مجموع التحذيرات", value=f"**{total}**", inline=True)
    embed.set_thumbnail(url=member.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="unwarn", aliases=["إزالة_تحذير"])
@commands.has_permissions(manage_messages=True)
async def unwarn(ctx, member_id: str = None):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!unwarn [ID]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ العضو غير موجود."); return
    warnings = load_warnings()
    gid, uid = str(ctx.guild.id), str(member.id)
    user_warns = warnings.get(gid, {}).get(uid, [])
    if not user_warns:
        await ctx.send(f"✅ **{member.display_name}** ما عنده تحذيرات!"); return
    warnings[gid][uid].pop()
    save_warnings(warnings)
    embed = discord.Embed(title="✅ تم إزالة التحذير", color=0x2ecc71, timestamp=datetime.datetime.utcnow())
    embed.add_field(name="👤 العضو",              value=member.mention,                    inline=True)
    embed.add_field(name="📊 التحذيرات المتبقية", value=f"**{len(warnings[gid][uid])}**", inline=True)
    await ctx.send(embed=embed)


@bot.command(name="warns", aliases=["warnings", "تحذيرات"])
@commands.has_permissions(manage_messages=True)
async def show_warns(ctx, member_id: str = None):
    if not member_id:
        await ctx.send("❌ الاستخدام: `!warns [ID]`"); return
    member = await resolve_member(ctx, member_id)
    if not member:
        await ctx.send("❌ العضو غير موجود."); return
    warnings   = load_warnings()
    user_warns = warnings.get(str(ctx.guild.id), {}).get(str(member.id), [])
    embed = discord.Embed(
        title=f"📋 تحذيرات {member.display_name}",
        color=0xe67e22, timestamp=datetime.datetime.utcnow()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    if not user_warns:
        embed.description = "✅ لا توجد تحذيرات"
    else:
        embed.description = f"**المجموع: {len(user_warns)} تحذير**"
        for i, w in enumerate(user_warns[-5:], 1):
            embed.add_field(
                name=f"تحذير #{i}",
                value=(
                    f"📝 {w['reason']}\n"
                    f"🛡️ {w.get('by_name','مجهول')}\n"
                    f"📅 {w.get('date','')[:10]}"
                ),
                inline=False,
            )
    await ctx.send(embed=embed)


# ╔══════════════════════════════════════════════════════════════╗
# ║             ✏️  النيك نيم  (Nickname)                       ║
# ╚══════════════════════════════════════════════════════════════╝

@bot.command(name="n", aliases=["nick", "mention", "منشن"])
async def mention_by_nick(ctx, *, nickname: str = None):
    if not nickname:
        await ctx.send("❌ الاستخدام: `!n [النيك نيم]`"); return
    query = nickname.lower()
    found = [
        m for m in ctx.guild.members
        if query in m.display_name.lower() or query in m.name.lower()
    ]
    if not found:
        await ctx.send(f"❌ ما لقيت أي عضو بالاسم **{nickname}**"); return

    if len(found) == 1:
        m = found[0]
        embed = discord.Embed(title="🔍 تم إيجاد العضو", color=0x3498db)
        embed.add_field(name="👤 العضو", value=m.mention, inline=True)
        embed.add_field(name="🆔 ID",    value=f"`{m.id}`", inline=True)
        embed.set_thumbnail(url=m.display_avatar.url)
        await ctx.send(embed=embed)
        await ctx.send(f"📣 {m.mention}")
        return

    embed = discord.Embed(
        title=f"🔍 نتائج البحث: {nickname}",
        description=f"وجدت **{len(found)}** عضو. أرسل رقم العضو:",
        color=0x9b59b6,
    )
    for i, m in enumerate(found[:10], 1):
        embed.add_field(name=f"{i}. {m.display_name}", value=f"{m.mention} | `{m.id}`", inline=False)
    embed.set_footer(text="أرسل الرقم خلال 30 ثانية")
    await ctx.send(embed=embed)

    def check(msg):
        return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.isdigit()

    try:
        reply  = await bot.wait_for("message", timeout=30.0, check=check)
        choice = int(reply.content)
        if 1 <= choice <= len(found):
            await ctx.send(f"📣 {found[choice - 1].mention}")
        else:
            await ctx.send("❌ رقم غير صحيح!")
    except asyncio.TimeoutError:
        await ctx.send("⏰ انتهى الوقت!")


@bot.command(name="setnick", aliases=["changenick"])
@commands.has_permissions(manage_nicknames=True)
async def set_nick(ctx, member: discord.Member = None, *, new_nick: str = None):
    if not member or not new_nick:
        await ctx.send("❌ الاستخدام: `!setnick @العضو [النيك الجديد]`"); return
    try:
        old = member.display_name
        await member.edit(nick=new_nick)
        embed = discord.Embed(title="✏️ تم تغيير النيك نيم", color=0x2ecc71)
        embed.add_field(name="👤 العضو",  value=member.mention, inline=False)
        embed.add_field(name="📛 القديم", value=old,            inline=True)
        embed.add_field(name="✨ الجديد", value=new_nick,       inline=True)
        await ctx.send(embed=embed)
    except discord.Forbidden:
        await ctx.send("❌ ما عندي صلاحية تغيير نيك نيم هذا العضو!")


# ╔══════════════════════════════════════════════════════════════╗
# ║                   🚀  تشغيل البوت                           ║
# ╚══════════════════════════════════════════════════════════════╝

if __name__ == "__main__":
    if TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("\n" + "⚠️ " * 20)
        print("  ضع توكن البوت الحقيقي في المتغير TOKEN !")
        print("  السطر 68 في الكود:  TOKEN = 'YOUR_BOT_TOKEN_HERE'")
        print("⚠️ " * 20 + "\n")
    else:
        bot.run(TOKEN)