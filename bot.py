import asyncio
import uuid
import re
import pycountry
import os
import aiohttp
import json
import tempfile
import html
from datetime import datetime, timezone, timedelta
from forcejoin import (
    check_access,
    get_missing_channels,
    build_force_join_keyboard,
    build_group_force_join_keyboard,
)
from flask import Flask
from threading import Thread
from aiogram.enums import ChatType
from aiogram import Bot, Dispatcher, types, F
BOT_CHANNEL = os.getenv("BOT_CHANNEL", "@YourChannel")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL")
WELCOME_IMAGE_URL = "https://i.postimg.cc/G2mZky3k/xulu-welcome111.jpg"
GOODBYE_IMAGE_URL = "https://i.postimg.cc/d11ky4b0/xuly-bye-bye.jpg"
OWNER_USERNAME = os.getenv("OWNER_USERNAME")
OWNER_URL = os.getenv("OWNER_URL")

from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    FSInputFile,
    ReplyParameters
)

from aiogram.filters import Command

from tmdb import (
    search_movies,
    get_images,
    get_movie_details,
    IMAGE_URL
)
from config import BOT_TOKEN, DEV_CONTACT
from cleaner import clean_text
from queue_worker import add_to_queue
from database import (
    set_tag,
    get_tag,
    add_word,
    get_words,
    delete_word,
    remove_tag,
    add_user,
    add_pm_user,
    has_started_bot,
    get_all_users,
    get_settings,
    toggle_setting,
    save_group_message,
    get_user_group_messages,
    delete_group_message_record,

    # 📦 DATA EXPORT / IMPORT
    export_remove_words,
    export_tag,
    export_settings,
    import_remove_words,
    import_tag,
    import_settings
)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
OWNER_ID = 6144504707
broadcast_mode = set()

tmdb_sessions = {}
tmdb_message_map = {}
remove_pages = {}
# =========================================================
# 📦 DATA EXPORT / IMPORT
# =========================================================

upload_waiting = {}
upload_timeout_tasks = {}

# =========================================================
# 👋 WELCOME / GOODBYE SYSTEM
# =========================================================

@dp.message(F.new_chat_members)
async def welcome_goodbye(message: types.Message):
    print(
        f"[WELCOME DEBUG] chat={message.chat.id} "
        f"users={[u.id for u in message.new_chat_members]}"
    )

    chat = message.chat

    # Telegram ek hi service message me multiple users
    # add kar sakta hai, isliye sabhi members handle karenge.
    for user in message.new_chat_members:

        first_name = user.first_name or "Unknown"
        last_name = user.last_name or ""

        full_name = (
            f"{first_name} {last_name}"
            if last_name
            else first_name
        )

        username = (
            f"@{user.username}"
            if user.username
            else "Not set"
        )

        # Clickable Telegram mention
        mention = user.mention_html(
            name=full_name
        )

        # Actual Telegram group name
        group_name = html.escape(
            chat.title or "our group"
        )

        # -------------------------------------------------
        # 👋 WELCOME TEXT
        # -------------------------------------------------

        welcome_text = (
            f"❤️ <b>Welcome, {mention}!</b>\n\n"

            f"We're really happy to have you here in "
            f"<b>{group_name}</b>.\n\n"

            "Take your time, enjoy the community, and "
            "please keep the group friendly for everyone. ✨\n\n"

            f"👤 <b>Name:</b> {html.escape(full_name)}\n"
            f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
            f"🔗 <b>Username:</b> <b>{html.escape(username)}</b>\n\n"

            "We hope you have a wonderful time with us! 🫶"
        )

        # -------------------------------------------------
        # 🔘 BUTTONS
        # -------------------------------------------------

        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Updates",
                        url=UPDATES_CHANNEL
                    ),
                    InlineKeyboardButton(
                        text="Owner",
                        url=OWNER_URL
                    )
                ]
            ]
        )

        # -------------------------------------------------
        # 📸 SEND WELCOME AS REPLY TO TELEGRAM
        #    "You added..." / "User joined..." MESSAGE
        # -------------------------------------------------

        await bot.send_photo(
            chat_id=chat.id,
            photo=WELCOME_IMAGE_URL,
            caption=welcome_text,
            parse_mode="HTML",
            reply_markup=buttons,
            reply_parameters=ReplyParameters(
                message_id=message.message_id
            )
        )


# =========================================================
# 🥺 GOODBYE SYSTEM
# =========================================================

@dp.message(F.left_chat_member)
async def goodbye_member(message: types.Message):

    chat = message.chat
    user = message.left_chat_member

    if not user:
        return

    first_name = user.first_name or "Unknown"
    last_name = user.last_name or ""

    full_name = (
        f"{first_name} {last_name}"
        if last_name
        else first_name
    )

    username = (
        f"@{user.username}"
        if user.username
        else "Not set"
    )

    # Clickable Telegram mention
    mention = user.mention_html(
        name=full_name
    )

    # Actual Telegram group name
    group_name = html.escape(
        chat.title or "our group"
    )

    # -----------------------------------------------------
    # 🥺 GOODBYE TEXT
    # -----------------------------------------------------

    goodbye_text = (
        f"🥺 <b>Goodbye, {mention}!</b>\n\n"

        f"We're sad to see you leave "
        f"<b>{group_name}</b>. 💔\n\n"

        f"👤 <b>Name:</b> {html.escape(full_name)}\n"
        f"🆔 <b>User ID:</b> <code>{user.id}</code>\n"
        f"🔗 <b>Username:</b> <b>{html.escape(username)}</b>\n\n"

        "We hope you had a good time with us. "
        "Take care, and we hope you'll come back "
        "and join us again soon. 🫶"
    )

    # -----------------------------------------------------
    # 🔘 BUTTONS
    # -----------------------------------------------------

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Updates",
                    url=UPDATES_CHANNEL
                ),
                InlineKeyboardButton(
                    text="Owner",
                    url=OWNER_URL
                )
            ]
        ]
    )

    # -----------------------------------------------------
    # 📸 SEND GOODBYE AS REPLY TO TELEGRAM
    #    "You removed..." / "User left..." MESSAGE
    # -----------------------------------------------------

    await bot.send_photo(
        chat_id=chat.id,
        photo=GOODBYE_IMAGE_URL,
        caption=goodbye_text,
        parse_mode="HTML",
        reply_markup=buttons,
        reply_parameters=ReplyParameters(
            message_id=message.message_id
        )
    )
    

def data_type_keyboard(mode):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🧹 Remove Words",
                    callback_data=f"{mode}_remove_words"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷️ Branding",
                    callback_data=f"{mode}_branding"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data=f"{mode}_settings"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=f"{mode}_cancel"
                )
            ]
        ]
    )


# =========================================================
# 📤 /exportdata
# =========================================================

@dp.message(Command("exportdata"))
async def exportdata_command(msg: types.Message):

    if msg.chat.type != ChatType.PRIVATE:
        return

    await msg.answer(
        "📤 <b>Select Data to Export</b>\n\n"
        "Choose what you want to export:",
        parse_mode="HTML",
        reply_markup=data_type_keyboard("export")
    )


# =========================================================
# 📥 /uploaddata
# =========================================================

@dp.message(Command("uploaddata"))
async def uploaddata_command(msg: types.Message):

    if msg.chat.type != ChatType.PRIVATE:
        return

    await msg.answer(
        "📥 <b>Select Data to Upload</b>\n\n"
        "Choose what you want to restore:",
        parse_mode="HTML",
        reply_markup=data_type_keyboard("upload")
    )


# =========================================================
# 📤 EXPORT CALLBACKS
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("export_"))
async def export_data_callback(callback: CallbackQuery):

    user_id = callback.from_user.id
    data_type = callback.data.replace("export_", "", 1)

    if data_type == "cancel":

        await callback.message.edit_text(
            "❌ Export cancelled."
        )

        await callback.answer()
        return

    try:

        if data_type == "remove_words":

            data = export_remove_words(user_id)
            filename = "xulu_remove_words.json"
            title = "🧹 Remove Words"

        elif data_type == "branding":

            data = export_tag(user_id)
            filename = "xulu_branding.json"
            title = "🏷️ Branding"

        elif data_type == "settings":

            data = export_settings(user_id)
            filename = "xulu_settings.json"
            title = "⚙️ Settings"

        else:

            await callback.answer(
                "❌ Invalid data type.",
                show_alert=True
            )
            return

        # ---------------------------------------------
        # CREATE TEMP JSON FILE
        # ---------------------------------------------

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8"
        ) as file:

            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

            file_path = file.name

        try:

            document = FSInputFile(
                file_path,
                filename=filename
            )

            await callback.message.answer_document(
                document=document,
                caption=(
                    f"📦 <b>{title} Backup</b>\n\n"
                    "Your exported data is ready.\n"
                    "You can use this file with "
                    "<code>/uploaddata</code> later."
                ),
                parse_mode="HTML"
            )

        finally:

            try:
                os.remove(file_path)
            except Exception:
                pass

        await callback.answer(
            "✅ Export completed."
        )

    except Exception as e:

        print(
            f"Export error [{user_id}]:",
            e
        )

        await callback.answer(
            "❌ Export failed.",
            show_alert=True
        )

# =========================================================
# ⏳ UPLOAD SESSION TIMEOUT
# =========================================================

async def expire_upload_session(
    user_id: int,
    data_type: str
):

    try:

        await asyncio.sleep(60)

        # Only expire if this is still
        # the same upload session
        if upload_waiting.get(user_id) == data_type:

            upload_waiting.pop(
                user_id,
                None
            )

            upload_timeout_tasks.pop(
                user_id,
                None
            )

    except asyncio.CancelledError:

        pass

    except Exception as e:

        print(
            f"Upload timeout error [{user_id}]:",
            e
        )
        
# =========================================================
# 📥 UPLOAD CALLBACKS
# =========================================================

@dp.callback_query(lambda c: c.data.startswith("upload_"))
async def upload_data_callback(callback: CallbackQuery):

    user_id = callback.from_user.id
    data_type = callback.data.replace("upload_", "", 1)

    if data_type == "cancel":

        upload_waiting.pop(
            user_id,
            None
        )

        old_task = upload_timeout_tasks.pop(
            user_id,
            None
        )

        if old_task:
            old_task.cancel()

        await callback.message.edit_text(
            "❌ Upload cancelled."
        )

        await callback.answer()
        return

    allowed_types = (
        "remove_words",
        "branding",
        "settings"
    )

    if data_type not in allowed_types:

        await callback.answer(
            "❌ Invalid data type.",
            show_alert=True
        )
        return

    upload_waiting[user_id] = data_type

    # Cancel previous upload timeout
    old_task = upload_timeout_tasks.get(user_id)

    if old_task:
        old_task.cancel()

    # Start new 60-second upload session
    upload_timeout_tasks[user_id] = asyncio.create_task(
        expire_upload_session(
            user_id,
            data_type
        )
    )

    names = {
        "remove_words": "🧹 Remove Words",
        "branding": "🏷️ Branding",
        "settings": "⚙️ Settings"
    }

    upload_text = (
        f"📥 <b>{names[data_type]} Upload</b>\n\n"
        "Please send your exported <code>.json</code> "
        "file now.\n\n"
        "⏳ You have <b>60 seconds</b> to upload the file.\n"
        "⚠️ After 60 seconds, the upload session will expire.\n\n"
        "You can also send the file as a reply "
        "to this message."
    )
    
    if callback.message.caption is not None:

        await callback.message.edit_caption(
            caption=upload_text,
            parse_mode="HTML"
        )

    else:

        await callback.message.edit_text(
            text=upload_text,
            parse_mode="HTML"
        )

    await callback.answer()


# =========================================================
# 📥 RECEIVE UPLOADED JSON FILE
# =========================================================

@dp.message(
    lambda msg:
        msg.chat.type == ChatType.PRIVATE
        and msg.document is not None
        and msg.from_user.id in upload_waiting
)
async def receive_data_file(msg: types.Message):

    user_id = msg.from_user.id

    data_type = upload_waiting.get(user_id)

    if not data_type:
        await add_to_queue(msg, process)
        return

    document = msg.document

    if not document.file_name.lower().endswith(".json"):

        await msg.reply(
            "❌ Please send a valid <code>.json</code> "
            "backup file.",
            parse_mode="HTML"
        )

        return

    try:

        file = await bot.get_file(
            document.file_id
        )

        temp_path = tempfile.mktemp(
            suffix=".json"
        )

        await bot.download_file(
            file.file_path,
            temp_path
        )

        try:

            with open(
                temp_path,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

        finally:

            try:
                os.remove(temp_path)
            except Exception:
                pass

        if not isinstance(data, dict):

            await msg.reply(
                "❌ Invalid backup file."
            )

            return

        # ---------------------------------------------
        # VERIFY FILE TYPE
        # ---------------------------------------------

        expected_type = data_type

        if data.get("type") != expected_type:

            await msg.reply(
                "❌ This file does not match the "
                "selected data type.\n\n"
                f"Selected: <code>{expected_type}</code>\n"
                f"File: <code>{data.get('type', 'unknown')}</code>",
                parse_mode="HTML"
            )

            return

        # ---------------------------------------------
        # IMPORT
        # ---------------------------------------------

        success = False

        if data_type == "remove_words":

            success = import_remove_words(
                user_id,
                data.get("words", [])
            )

        elif data_type == "branding":

            success = import_tag(
                user_id,
                data.get("tag", "")
            )

        elif data_type == "settings":

            success = import_settings(
                user_id,
                data
            )

        if not success:

            await msg.reply(
                "❌ Could not import this backup."
            )

            return

        upload_waiting.pop(
            user_id,
            None
        )

        old_task = upload_timeout_tasks.pop(
            user_id,
            None
        )

        if old_task:
            old_task.cancel()

        names = {
            "remove_words": "🧹 Remove Words",
            "branding": "🏷️ Branding",
            "settings": "⚙️ Settings"
        }

        await msg.reply(
            f"✅ <b>{names[data_type]} imported successfully.</b>\n\n"
            "Your MongoDB data has been updated.",
            parse_mode="HTML"
        )

    except json.JSONDecodeError:

        await msg.reply(
            "❌ The uploaded file contains invalid JSON."
        )

    except Exception as e:

        print(
            f"Import error [{user_id}]:",
            e
        )

        await msg.reply(
            "❌ Import failed. Please check the backup file."
        )

def get_language_name(lang_code):
    if not lang_code:
        return "Original / Clean"

    try:
        language = pycountry.languages.get(alpha_2=lang_code)
        if language:
            return language.name
    except Exception:
        pass

    return lang_code.upper()

# =========================================================
# LANGUAGE FILTER HELPERS
# =========================================================

def get_mode_images(session, mode):
    """
    Return images for the current TMDB mode.
    Keeps Clean Landscape completely separate.
    """

    images_data = session["images"]

    if mode == "poster":
        return images_data["posters"]

    if mode == "backdrop":
        return [
            img
            for img in images_data["backdrops"]
            if img.get("iso_639_1") is not None
        ]

    if mode == "logo":
        return images_data["logos"]

    if mode == "clean":
        return [
            img
            for img in images_data["backdrops"]
            if img.get("iso_639_1") is None
        ]

    return []


def get_available_languages(images):
    """
    Get only languages actually available
    in the supplied TMDB images.
    """

    languages = set()

    for image in images:

        lang = image.get("iso_639_1")

        if lang:
            languages.add(lang)

    return sorted(
        languages,
        key=lambda code: get_language_name(code).lower()
    )


def get_language_filtered_images(images, language):
    """
    Filter images by TMDB language code.
    """

    if language == "all":
        return images

    return [
        image
        for image in images
        if image.get("iso_639_1") == language
    ]


def build_language_keyboard(
    search_id,
    mode,
    images
):
    """
    Build dynamic language-selection keyboard.
    Only languages available in TMDB images are shown.
    """

    buttons = []

    # -----------------------------------------------------
    # ALL LANGUAGES
    # -----------------------------------------------------

    buttons.append([
        InlineKeyboardButton(
            text="All Languages",
            callback_data=f"tmdb_lang_{mode}_{search_id}_all"
        )
    ])

    # -----------------------------------------------------
    # CLEAN POSTERS
    # Only for Poster mode
    # -----------------------------------------------------

    if mode == "poster":

        clean_posters = [
            image
            for image in images
            if image.get("iso_639_1") is None
        ]

        if clean_posters:

            buttons.append([
                InlineKeyboardButton(
                    text="Clean Posters",
                    callback_data=f"tmdb_cleanposter_{search_id}"
                )
            ])

    # =========================================================
    # TMDB CLEAN POSTERS
    # =========================================================

    @dp.callback_query(
        lambda c: c.data.startswith("tmdb_cleanposter_")
    )
    async def tmdb_cleanposter(callback: CallbackQuery):

        search_id = callback.data.replace(
            "tmdb_cleanposter_",
            ""
        )

        session = tmdb_sessions.get(search_id)

        if not session:
            await callback.answer(
                "Session Expired",
                show_alert=True
            )
            return

        clean_posters = [
            image
            for image in session["images"]["posters"]
            if image.get("iso_639_1") is None
        ]

        if not clean_posters:
            await callback.answer(
                "No Clean Posters Found",
                show_alert=True
            )
            return

        session["mode"] = "poster"
        session["language_filter"] = "clean"
        session["index"] = 0

        await show_tmdb_image(
            callback,
            session,
            clean_posters,
            "Clean Poster"
        )

    # -----------------------------------------------------
    # AVAILABLE LANGUAGES
    # -----------------------------------------------------

    languages = get_available_languages(images)

    row = []

    for lang in languages:

        language_name = get_language_name(lang)

        row.append(
            InlineKeyboardButton(
                text=language_name,
                callback_data=f"tmdb_lang_{mode}_{search_id}_{lang}"
            )
        )

        # Keep keyboard clean
        # Maximum 2 language buttons per row.
        if len(row) == 2:

            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # -----------------------------------------------------
    # BACK
    # -----------------------------------------------------

    buttons.append([
        InlineKeyboardButton(
            text="Back",
            callback_data=f"tmdb_typeback_{search_id}"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


async def show_language_selection(
    callback,
    session,
    mode,
    images
):
    """
    Show the language-selection step
    without changing the existing image viewer.
    """

    session["language_filter"] = None
    session["language_step"] = True

    keyboard = build_language_keyboard(
        session["search_id"],
        mode,
        images
    )

    title = (
        session["selected"].get("title")
        or session["selected"].get("name")
        or "Unknown"
    )

    text = (
        "<b>Select Your Preferred Language</b>\n\n"
        "This title has artwork available in multiple "
        "languages. Choose a language below to view "
        "the available artwork in your preferred language.\n\n"
        "<b>Select your favourite language to explore "
        "the artwork, or choose All Languages to view "
        "all available languages together.</b>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await callback.answer()
    

async def show_tmdb_image(callback, session, images, label):

    session["current_images"] = images

    index = session["index"]

    image = images[index]

    image_url = IMAGE_URL + image["file_path"]

    movie = session["selected"]

    title = movie.get("title") or movie.get("name")

    date = movie.get("release_date") or movie.get("first_air_date") or ""

    year = date[:4] if date else ""

    width = image.get("width", "?")
    height = image.get("height", "?")

    lang = image.get("iso_639_1")

    language = get_language_name(lang)

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="<",
                    callback_data=f"tmdb_prev_{session['search_id']}"
                ),
                InlineKeyboardButton(
                    text=f"{index+1}/{len(images)}",
                    callback_data="ignore"
                ),
                InlineKeyboardButton(
                    text=">",
                    callback_data=f"tmdb_next_{session['search_id']}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Image",
                    url=image_url
                ),
                InlineKeyboardButton(
                    text="Download",
                    callback_data=f"tmdb_download_{session['search_id']}"
                ),
                InlineKeyboardButton(
                    text="Info",
                    callback_data=f"tmdb_info_{session['search_id']}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data=(
                        f"tmdb_langback_{session['search_id']}"
                        if session.get("language_step", False)
                        else f"tmdb_back_{session['search_id']}"
                    )
                ),
                InlineKeyboardButton(
                    text="Close",
                    callback_data="tmdb_close"
                )
            ]
        ]
    )

    text = (
        f"<b>{label}</b>\n\n"
        f"Title       : <code>{title} ({year})</code>\n"
        f"Language    : <code>{language}</code>\n"
        f"Resolution  : <code>{width} × {height}</code>\n"
        f"Image       : <code>{index + 1}/{len(images)}</code>\n\n"
        f"<b>Image URL :</b> {image_url}\n\n"
        f"<blockquote><b>CC : {BOT_CHANNEL}</b></blockquote>"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=keyboard,
        disable_web_page_preview=False
    )
    await callback.answer()

# =========================================================
# 📥 DOWNLOAD CURRENT POSTER
# =========================================================

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_download_")
)
async def tmdb_download(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_download_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # CURRENT IMAGE
    # -----------------------------------------------------

    images = session.get("current_images", [])

    if not images:
        await callback.answer(
            "Image unavailable.",
            show_alert=True
        )
        return

    index = session.get("index", 0)

    if index < 0 or index >= len(images):
        index = 0

    image = images[index]

    image_url = IMAGE_URL + image["file_path"]

    temp_path = None
    downloading_msg = None

    try:

        # -------------------------------------------------
        # SHOW DOWNLOADING MESSAGE
        # -------------------------------------------------

        downloading_msg = await bot.send_message(
            callback.message.chat.id,
            "<b>Downloading...</b>",
            parse_mode="HTML"
        )

        await callback.answer()

        # -------------------------------------------------
        # DOWNLOAD TO TEMP STORAGE
        # -------------------------------------------------

        import urllib.request

        fd, temp_path = tempfile.mkstemp(
            suffix=".jpg"
        )

        os.close(fd)

        await asyncio.to_thread(
            urllib.request.urlretrieve,
            image_url,
            temp_path
        )

        # -------------------------------------------------
        # MOVIE DETAILS
        # -------------------------------------------------

        movie = session["selected"]

        title = (
            movie.get("title")
            or movie.get("name")
            or "Unknown"
        )

        date = (
            movie.get("release_date")
            or movie.get("first_air_date")
            or ""
        )

        year = date[:4] if date else ""

        cc = BOT_CHANNEL

        caption = (
            "✅ <b>Download Complete</b>\n\n"
            f"<b>Title :</b> "
            f"{html.escape(str(title))} "
            f"({html.escape(str(year))})\n\n"
            f"<blockquote><b>CC : "
            f"{html.escape(str(cc))}</b></blockquote>"
        )

        # -------------------------------------------------
        # SEND POSTER TO USER
        # -------------------------------------------------

        await bot.send_photo(
            callback.message.chat.id,
            photo=FSInputFile(temp_path),
            caption=caption,
            parse_mode="HTML"
        )

        # -------------------------------------------------
        # DELETE "DOWNLOADING..." MESSAGE
        # -------------------------------------------------

        try:
            if downloading_msg:
                await downloading_msg.delete()
        except Exception:
            pass

        # -------------------------------------------------
        # DELETE SERVER FILE AFTER 30 SECONDS
        # -------------------------------------------------

        async def delete_later(path):

            try:

                await asyncio.sleep(30)

                if path and os.path.exists(path):
                    os.remove(path)

            except Exception as e:

                print(
                    "Poster cleanup error:",
                    e
                )

        asyncio.create_task(
            delete_later(temp_path)
        )

        # Cleanup task now owns the file
        temp_path = None

    except Exception as e:

        print(
            "Poster download error:",
            e
        )

        # Delete downloading message on failure
        try:
            if downloading_msg:
                await downloading_msg.delete()
        except Exception:
            pass

        await callback.answer(
            "❌ Download failed.",
            show_alert=True
        )

        # Delete temp file on failure
        if temp_path and os.path.exists(temp_path):

            try:
                os.remove(temp_path)
            except Exception:
                pass

# =========================================================
# 📤 IMGYX FILE HOSTING
# =========================================================

IMGYX_BASE_URL = "https://imgyx.pages.dev"
IMGYX_UPLOAD_URL = f"{IMGYX_BASE_URL}/api/upload"
IMGYX_MAX_SIZE = 20 * 1024 * 1024  # 20 MB

# Active upload sessions
imgyx_upload_waiting = set()
imgyx_upload_timeout_tasks = {}
imgyx_upload_chat_ids = {}
imgyx_upload_prompt_messages = {}
imgyx_upload_command_messages = {}


# =========================================================
# ⏳ IMGYX UPLOAD SESSION TIMEOUT
# =========================================================

async def imgyx_upload_timeout(
    session_key,
    chat_id,
    prompt_message_id,
    mention
):

    try:

        await asyncio.sleep(60)

        if session_key in imgyx_upload_waiting:

            imgyx_upload_waiting.discard(
                session_key
            )

            imgyx_upload_chat_ids.pop(
                session_key,
                None
            )

            imgyx_upload_prompt_messages.pop(
                session_key,
                None
            )

            try:

                await bot.send_message(
                    chat_id,
                    f"⏳ {mention}, <b>your upload session has expired.</b>\n\n"
                    "Please use <code>/upload</code> again "
                    "to upload a file.",
                    parse_mode="HTML",
                    reply_to_message_id=prompt_message_id
                )

            except Exception as e:

                print(
                    "ImgyX expiry reply error:",
                    e
                )

    except asyncio.CancelledError:
        pass

    except Exception as e:

        print(
            "ImgyX upload timeout error:",
            e
        )

    finally:

        imgyx_upload_timeout_tasks.pop(
            session_key,
            None
        )

        imgyx_upload_chat_ids.pop(
            session_key,
            None
        )

        imgyx_upload_prompt_messages.pop(
            session_key,
            None
        )


# =========================================================
# 📤 /upload COMMAND
# =========================================================

@dp.message(Command("upload"))
async def upload_command(msg: types.Message):

    if not await check_access(
        bot,
        msg
    ):
        return

    user_id = msg.from_user.id
    chat_id = msg.chat.id
    session_key = (user_id, chat_id)

    # -----------------------------------------------------
    # REPLY-BASED UPLOAD
    # -----------------------------------------------------

    target = msg.reply_to_message

    if target and (
        target.photo
        or target.document
    ):

        # Save the /upload command message
        # so the final result can reply to it.
        imgyx_upload_command_messages[
            session_key
        ] = msg.message_id

        await process_imgyx_upload(
            msg,
            target
        )

        return

    # -----------------------------------------------------
    # CANCEL OLD SESSION
    # -----------------------------------------------------

    old_task = imgyx_upload_timeout_tasks.pop(
        session_key,
        None
    )

    if old_task:
        old_task.cancel()

    imgyx_upload_waiting.discard(
        session_key
    )

    imgyx_upload_prompt_messages.pop(
        session_key,
        None
    )

    # -----------------------------------------------------
    # START NEW 60 SECOND SESSION
    # -----------------------------------------------------

    imgyx_upload_waiting.add(
        session_key
    )

    imgyx_upload_chat_ids[
        session_key
    ] = chat_id

    # Save the user's /upload command
    imgyx_upload_command_messages[
        session_key
    ] = msg.message_id

    # -----------------------------------------------------
    # MENTION
    # -----------------------------------------------------

    mention = msg.from_user.mention_html()

    # -----------------------------------------------------
    # SEND UPLOAD PROMPT
    # -----------------------------------------------------

    prompt_msg = await msg.reply(
        "📤 <b>Send the photo or file you want to upload.</b>\n\n"
        "⏳ You have <b>60 seconds</b> to send it.\n"
        "After 60 seconds, this upload session will expire.",
        parse_mode="HTML"
    )

    # Save prompt message ID
    imgyx_upload_prompt_messages[
        session_key
    ] = prompt_msg.message_id

    # -----------------------------------------------------
    # START TIMEOUT
    # -----------------------------------------------------

    timeout_task = asyncio.create_task(
        imgyx_upload_timeout(
            session_key,
            chat_id,
            prompt_msg.message_id,
            mention
        )
    )

    imgyx_upload_timeout_tasks[
        session_key
    ] = timeout_task


# =========================================================
# 📤 PROCESS IMGYX UPLOAD
# =========================================================

async def process_imgyx_upload(
    command_msg: types.Message,
    target_msg: types.Message
):

    user_id = command_msg.from_user.id
    chat_id = command_msg.chat.id
    session_key = (user_id, chat_id)
    is_session_upload = (
        target_msg is command_msg
        and session_key in imgyx_upload_chat_ids
    )
    mention = command_msg.from_user.mention_html()

    upload_command_message_id = (
        imgyx_upload_command_messages.get(
            session_key
        )
    )

    temp_path = None
    uploading_msg = None

    try:

        is_direct_session_upload = (
            command_msg == target_msg
            and command_msg.reply_to_message is None
            and not command_msg.caption
        )

        # -------------------------------------------------
        # REMOVE ACTIVE SESSION
        # -------------------------------------------------

        imgyx_upload_waiting.discard(
            session_key
        )

        imgyx_upload_chat_ids.pop(
            session_key,
            None
        )

        old_task = imgyx_upload_timeout_tasks.pop(
            session_key,
            None
        )

        if old_task:
            old_task.cancel()

        prompt_message_id = imgyx_upload_prompt_messages.pop(
            session_key,
            None
        )

        if prompt_message_id:

            try:

                await bot.delete_message(
                    chat_id,
                    prompt_message_id
                )

            except Exception:
                pass

        # -------------------------------------------------
        # GET PHOTO / DOCUMENT
        # -------------------------------------------------

        document = target_msg.document
        photo = target_msg.photo

        if not document and not photo:

            await command_msg.reply(
                "❌ <b>Please send a photo or file to upload.</b>",
                parse_mode="HTML"
            )

            return

        # -------------------------------------------------
        # FILE DETAILS
        # -------------------------------------------------

        if document:

            file_id = document.file_id

            file_name = (
                document.file_name
                or f"file_{document.file_unique_id}"
            )

            file_size = (
                document.file_size
                or 0
            )

            mime_type = (
                document.mime_type
                or "application/octet-stream"
            )

        else:

            # Highest quality Telegram photo
            photo_file = photo[-1]

            file_id = photo_file.file_id

            file_name = (
                f"photo_{photo_file.file_unique_id}.jpg"
            )

            file_size = (
                photo_file.file_size
                or 0
            )

            mime_type = "image/jpeg"

        # -------------------------------------------------
        # INITIAL 20 MB CHECK
        # -------------------------------------------------

        if file_size > IMGYX_MAX_SIZE:

            await command_msg.reply(
                "❌ <b>File is too large.</b>\n\n"
                "The maximum file size is <b>20 MB</b>.",
                parse_mode="HTML"
            )

            return

        # -------------------------------------------------
        # SHOW UPLOADING MESSAGE
        # -------------------------------------------------

        uploading_msg = await command_msg.reply(
            "⏳ <b>Uploading...</b>",
            parse_mode="HTML"
        )

        # -------------------------------------------------
        # GET TELEGRAM FILE
        # -------------------------------------------------

        file = await bot.get_file(
            file_id
        )

        # -------------------------------------------------
        # CREATE TEMP FILE
        # -------------------------------------------------

        suffix = os.path.splitext(
            file_name
        )[1]

        if not suffix:
            suffix = ".tmp"

        fd, temp_path = tempfile.mkstemp(
            suffix=suffix
        )

        os.close(fd)

        # -------------------------------------------------
        # DOWNLOAD FROM TELEGRAM
        # -------------------------------------------------

        await bot.download_file(
            file.file_path,
            temp_path
        )

        # -------------------------------------------------
        # FINAL SIZE CHECK
        # -------------------------------------------------

        actual_size = os.path.getsize(
            temp_path
        )

        if actual_size > IMGYX_MAX_SIZE:

            try:
                await uploading_msg.delete()
            except Exception:
                pass

            await command_msg.reply(
                "❌ <b>File is too large.</b>\n\n"
                "The maximum file size is <b>20 MB</b>.",
                parse_mode="HTML"
            )

            return

        # -------------------------------------------------
        # UPLOAD TO IMGYX
        # -------------------------------------------------

        timeout = aiohttp.ClientTimeout(
            total=120
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            with open(
                temp_path,
                "rb"
            ) as file_object:

                form = aiohttp.FormData()

                form.add_field(
                    "file",
                    file_object,
                    filename=file_name,
                    content_type=mime_type
                )

                async with session.post(
                    IMGYX_UPLOAD_URL,
                    data=form
                ) as response:

                    response_text = (
                        await response.text()
                    )

                    # -------------------------------------
                    # 20 MB ERROR
                    # -------------------------------------

                    if response.status == 413:

                        try:
                            await uploading_msg.delete()
                        except Exception:
                            pass

                        await command_msg.reply(
                            "❌ <b>File is too large.</b>\n\n"
                            "ImgyX only accepts files up to "
                            "<b>20 MB</b>.",
                            parse_mode="HTML"
                        )

                        return

                    # -------------------------------------
                    # RATE LIMIT
                    # -------------------------------------

                    if response.status == 429:

                        try:
                            await uploading_msg.delete()
                        except Exception:
                            pass

                        await command_msg.reply(
                            "⚠️ <b>Upload limit reached.</b>\n\n"
                            "Please try again later.",
                            parse_mode="HTML"
                        )

                        return

                    # -------------------------------------
                    # SERVER ERROR
                    # -------------------------------------

                    if response.status in (
                        500,
                        502
                    ):

                        try:
                            await uploading_msg.delete()
                        except Exception:
                            pass

                        await command_msg.reply(
                            "❌ <b>Upload service is temporarily "
                            "unavailable.</b>\n\n"
                            "Please try again later.",
                            parse_mode="HTML"
                        )

                        return

                    # -------------------------------------
                    # OTHER NON-SUCCESS STATUS
                    # -------------------------------------

                    if not 200 <= response.status < 300:

                        print(
                            "ImgyX upload error:",
                            response.status,
                            response_text
                        )

                        try:
                            await uploading_msg.delete()
                        except Exception:
                            pass

                        await command_msg.reply(
                            "❌ <b>Upload failed.</b>\n\n"
                            "Please try again later.",
                            parse_mode="HTML"
                        )

                        return

                    # -------------------------------------
                    # PARSE RESPONSE
                    # -------------------------------------

                    try:

                        result = json.loads(
                            response_text
                        )

                    except Exception:

                        print(
                            "Invalid ImgyX response:",
                            response_text
                        )

                        try:
                            await uploading_msg.delete()
                        except Exception:
                            pass

                        await command_msg.reply(
                            "❌ <b>Upload failed.</b>\n\n"
                            "The hosting service returned "
                            "an invalid response.",
                            parse_mode="HTML"
                        )

                        return

        # -------------------------------------------------
        # GET IMGYX RESPONSE DATA
        # -------------------------------------------------

        file_id_imgyx = result.get(
            "id"
        )

        raw_url = result.get(
            "url"
        )

        preview_url = result.get(
            "preview_url"
        )

        if not file_id_imgyx and not raw_url:

            print(
                "Invalid ImgyX upload response:",
                result
            )

            try:
                await uploading_msg.delete()
            except Exception:
                pass

            await command_msg.reply(
                "❌ <b>Upload failed.</b>\n\n"
                "Could not get the uploaded file link.",
                parse_mode="HTML"
            )

            return

        # -------------------------------------------------
        # BUILD DIRECT LINK
        # -------------------------------------------------

        if raw_url:

            if raw_url.startswith("http"):

                direct_link = raw_url

            else:

                direct_link = (
                    IMGYX_BASE_URL
                    + raw_url
                )

        else:

            direct_link = (
                f"{IMGYX_BASE_URL}/{file_id_imgyx}"
            )

        # -------------------------------------------------
        # BUILD PREVIEW LINK
        # -------------------------------------------------

        if preview_url:

            if preview_url.startswith("http"):

                preview_link = preview_url

            else:

                preview_link = (
                    IMGYX_BASE_URL
                    + preview_url
                )

        else:

            preview_link = (
                f"{IMGYX_BASE_URL}/p/{file_id_imgyx}"
            )

        # -------------------------------------------------
        # GET FILE INFO
        # -------------------------------------------------

        views = 0

        info_name = file_name
        info_size = actual_size
        info_mime = mime_type

        if file_id_imgyx:

            try:

                async with aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(
                        total=30
                    )
                ) as info_session:

                    async with info_session.get(
                        f"{IMGYX_BASE_URL}/api/info",
                        params={
                            "id": file_id_imgyx
                        }
                    ) as info_response:

                        if info_response.status == 200:

                            info = (
                                await info_response.json()
                            )

                            info_name = (
                                info.get("file_name")
                                or info_name
                            )

                            info_size = (
                                info.get("size")
                                or info_size
                            )

                            info_mime = (
                                info.get("mimetype")
                                or info_mime
                            )

                            views = (
                                info.get("views")
                                or 0
                            )

            except Exception as e:

                print(
                    "ImgyX info error:",
                    e
                )

        # -------------------------------------------------
        # FORMAT FILE SIZE
        # -------------------------------------------------

        def format_file_size(size):

            try:

                size = float(size)

                if size >= 1024 * 1024:

                    return (
                        f"{size / (1024 * 1024):.2f} MB"
                    )

                if size >= 1024:

                    return (
                        f"{size / 1024:.2f} KB"
                    )

                return f"{int(size)} B"

            except Exception:

                return "Unknown"

        size_text = format_file_size(
            info_size
        )

        image_link_text = ""

        if str(info_mime).startswith("image/"):
            image_link_text = (
                f"<b>Image Link:</b>\n"
                f"{direct_link}\n\n"
            )

        # -------------------------------------------------
        # DELETE UPLOADING MESSAGE
        # -------------------------------------------------

        try:

            if uploading_msg:
                await uploading_msg.delete()

        except Exception:
            pass

        # -------------------------------------------------
        # BUTTONS — SAME LINE
        # -------------------------------------------------

        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Direct Link",
                        url=direct_link
                    ),
                    InlineKeyboardButton(
                        text="Preview",
                        url=preview_link
                    )
                ]
            ]
        )

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        safe_name = html.escape(
            str(info_name)
        )

        safe_mime = html.escape(
            str(info_mime)
        )

        safe_cc = html.escape(
            str(BOT_CHANNEL)
        )

        result_text = (
            f"{mention}, <b>Upload Complete ✅</b>\n\n"
            f"<b>File:</b> "
            f"<code>{safe_name}</code>\n"
            f"<b>Size:</b> "
            f"<code>{size_text}</code>\n"
            f"<b>Type:</b> "
            f"<code>{safe_mime}</code>\n"
            f"{image_link_text}"
            f"<blockquote><b>CC : "
            f"{safe_cc}</b></blockquote>"
        )

        if is_direct_session_upload:

            try:
                await command_msg.delete()
            except Exception:
                pass

        # Delete user's file only when it was sent
        # after /upload session prompt.
        # Reply-based and caption-based uploads are kept.
        if is_session_upload:

            try:
                await target_msg.delete()
            except Exception as e:
                print(
                    "ImgyX user file delete error:",
                    e
                )

        await bot.send_message(
            chat_id,
            result_text,
            parse_mode="HTML",
            reply_markup=buttons,
            disable_web_page_preview=False,
            reply_to_message_id=upload_command_message_id
        )

        imgyx_upload_command_messages.pop(
            session_key,
            None
)

    except Exception as e:

        imgyx_upload_command_messages.pop(
            session_key,
            None
        )

        print(
            "ImgyX upload error:",
            e
        )

        try:

            if uploading_msg:
                await uploading_msg.delete()

        except Exception:
            pass

        await command_msg.reply(
            "❌ <b>Upload failed.</b>\n\n"
            "Something went wrong while uploading "
            "your file. Please try again.",
            parse_mode="HTML"
        )

    finally:

        # -------------------------------------------------
        # DELETE RENDER TEMP FILE
        # -------------------------------------------------

        if temp_path and os.path.exists(
            temp_path
        ):

            try:

                os.remove(
                    temp_path
                )

            except Exception as e:

                print(
                    "ImgyX temp file cleanup error:",
                    e
                )


# =========================================================
# 📤 PHOTO / DOCUMENT AFTER /upload
# =========================================================

@dp.message(
    lambda msg:
        (
            msg.photo is not None
            or msg.document is not None
        )
        and (
            msg.from_user.id,
            msg.chat.id
        ) in imgyx_upload_waiting
)
async def imgxy_session_upload(
    msg: types.Message
):

    if not await check_access(
        bot,
        msg
    ):
        return

    await process_imgyx_upload(
        msg,
        msg
    )


# =========================================================
# 📤 PHOTO / DOCUMENT WITH /upload IN CAPTION
# =========================================================

@dp.message(
    lambda msg:
        (
            msg.photo is not None
            or msg.document is not None
        )
        and msg.caption
        and "/upload" in msg.caption.lower()
)
async def imgxy_caption_upload(
    msg: types.Message
):

    if not await check_access(
        bot,
        msg
    ):
        return

    await process_imgyx_upload(
        msg,
        msg
    )
    

# 🔥 DM CLEAN SESSION
user_sessions = {}
summary_tasks = {}

app = Flask('')


@app.route('/')
def home():
    return "Bot is running!"


def run_web():
    import os

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )

# 🔹 SAFE REPLY
async def safe_reply(msg, text):
    try:
        await msg.reply(text)
    except:
        pass

# 🔹 WELCOME (FULL PRO)
@dp.message(Command("start"))
async def start(msg: types.Message):
    # Save/update PM user information first
    add_pm_user(
        user_id=msg.from_user.id,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
        username=msg.from_user.username
    )

    # Then check Force Join
    if not await check_access(bot, msg):
        return

    add_user(msg.from_user.id)

    mention = msg.from_user.mention_html()

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="settings"
                ),
                InlineKeyboardButton(
                    text="🧹 Remove Words",
                    callback_data="remove"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Branding",
                    callback_data="branding"
                ),
                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Help",
                    callback_data="help"
                )
            ]
        ]
    )

    await msg.answer_photo(
        photo="https://i.postimg.cc/6QJRkyyZ/bot-start-banner.png",
        caption=(
            f"👋 Hello {mention}\n\n"
            "Welcome to —͟͟͞͞<b>𝐗𝐔 𝐋𝐔 ᥫ᭡ 𝐀𝐮𝐭𝐨 𝐂𝐥𝐞𝐚𝐧𝐞𝐫 𝐁𝐨𝐭</b>\n\n"
            "⚡ <b>A powerful Telegram automation tool</b> to clean, control, and rebrand your content.\n\n"

            "━━━━━━━━━━━━━━━━━━━\n"
            "✨ <b>Features:</b>\n"
            "• <b>Remove links, tags, hashtags</b>\n"
            "• <b>Custom word & sentence filter</b>\n"
            "• <b>Auto branding system</b>\n"
            "• <b>Poster search & download</b>\n"
            "• <b>Bulk processing supported</b>\n"
            "• <b>Smart cleaning engine</b>\n\n"

            "━━━━━━━━━━━━━━━━━━━\n"
            "⚙️ <b>Quick Commands:</b>\n"
            "• <code>/settag your text</code> — Set branding\n"
            "• <code>/remove your text</code> — Add custom filter\n"
            "• <code>/removetag</code> — Remove branding\n"
            "• <code>/p</code> or <code>/poster</code> — Search & download posters\n\n"

            "━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <b>Need Help?</b>\n"
            f"👨‍💻 <b>Contact Developer:</b> {DEV_CONTACT}"
        ),
        parse_mode="HTML",
        reply_markup=buttons
    )

@dp.message(Command("settings"))
async def settings_command(msg: types.Message):
    if not await check_access(bot, msg):
        return

    mention = msg.from_user.mention_html()

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="settings"
                ),
                InlineKeyboardButton(
                    text="🧹 Remove Words",
                    callback_data="remove"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Branding",
                    callback_data="branding"
                ),
                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Help",
                    callback_data="help"
                )
            ]
        ]
    )

    await msg.answer_photo(
        photo="https://i.postimg.cc/6QJRkyyZ/bot-start-banner.png",
        caption=(
            f"👋 Hello {mention}\n\n"
            "Welcome to —͟͟͞͞<b>𝐗𝐔 𝐋𝐔 ᥫ᭡ 𝐀𝐮𝐭𝐨 𝐂𝐥𝐞𝐚𝐧𝐞𝐫 𝐁𝐨𝐭</b>\n\n"
            "⚙️ Settings Panel\n\n"
            "Use the same controls available in /start."
        ),
        parse_mode="HTML",
        reply_markup=buttons
    )

@dp.message(Command("settag"))
async def settag(msg: types.Message):
    if not await check_access(bot, msg):
        return
    tag = msg.text.replace("/settag ", "").strip()

    if tag:
        set_tag(msg.chat.id, tag)
        await msg.reply("✅ Branding tag saved successfully.")
    else:
        await msg.reply("Usage: /settag your text")


@dp.message(Command("removetag"))
async def removetag(msg: types.Message):
    if not await check_access(bot, msg):
        return
    remove_tag(msg.chat.id)
    await msg.reply("✅ Branding tag removed.")


@dp.message(Command("remove"))
async def remove_word_command(msg: types.Message):
    if not await check_access(bot, msg):
        return
    word = msg.text.replace("/remove ", "").strip()

    if word:
        add_word(msg.chat.id, word)
        await msg.reply("✅ Word/sentence added to remove filter.")
    else:
        await msg.reply("Usage: /remove text")

@dp.message(Command("removesetwords"))
async def remove_saved_word(msg: types.Message):
    if not await check_access(bot, msg):
        return

    word = msg.text.replace("/removesetwords ", "").strip()

    if not word:
        await msg.reply(
            "Usage: /removesetwords your text"
        )
        return

    removed = delete_word(msg.chat.id, word)

    if removed:
        await msg.reply(
            "✅ Word/Sentence removed from filter successfully."
        )
    else:
        await msg.reply(
            "❌ Word/Sentence not found in your filter list."
        )


@dp.message(Command("poster", "p"))
async def poster_command(msg: types.Message):
    if not await check_access(bot, msg):
        return

    query = msg.text.split(maxsplit=1)

    if len(query) < 2:
        await msg.reply(
            "Usage:\n/poster movie name"
        )
        return

    movies = await search_movies(query[1])

    # No result - show suggestions
    if not movies:

        suggestions = await search_movies(query[1][:8])

        if suggestions:
            text = (
                "<b>No exact result found</b>\n\n"
                "Did you mean?\n"
            )

            for item in suggestions[:5]:
                title = item.get("title") or item.get("name")
                date = item.get("release_date") or item.get("first_air_date") or ""
                year = date[:4] if date else "----"

                text += f"• <code>{title} ({year})</code>\n"

            text += f"<blockquote><b>CC : {BOT_CHANNEL}</b></blockquote>"

            await msg.reply(
                text,
                parse_mode="HTML"
            )
        else:
            await msg.reply(
                f"No result found for <code>{query[1]}</code>\n\n"
                f"<blockquote><b>CC : {BOT_CHANNEL}</b></blockquote>",
                parse_mode="HTML"
            )

        return

    buttons = []

    search_id = uuid.uuid4().hex[:8]

    tmdb_sessions[search_id] = {
        "search_id": search_id,
        "movies": movies,
        "selected": None,
        "images": None,
        "details": None,
        "mode": None,
        "index": 0,
    }

    for i, movie in enumerate(movies[:10]):

        title = movie.get("title") or movie.get("name")

        date = movie.get("release_date") or movie.get("first_air_date")

        year = date[:4] if date else "----"

        buttons.append([
            InlineKeyboardButton(
                text=f"{title} ({year})",
                callback_data=f"tmdb_movie_{search_id}_{i}"
            )
        ])

    text = (
        "<b>TMDB Search Results</b>\n\n"
        f"Query: <code>{query[1]}</code>\n"
        f"Results: <b>{len(movies[:10])}</b>\n\n"
        "Select a movie or TV series below.\n\n"
        f"<blockquote><b>CC : {BOT_CHANNEL}</b></blockquote>"
    )

    sent = await msg.reply(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    tmdb_message_map[sent.message_id] = search_id

@dp.message(Command("broadcast"))
async def broadcast_command(msg: types.Message):

    # Group me kuch bhi reply mat karo
    if msg.chat.type != "private":
        return

    if msg.from_user.id != OWNER_ID:
        await msg.reply(
            f"Unknown command.\nContact: {DEV_CONTACT}"
        )
        return

    broadcast_mode.add(msg.from_user.id)

    await msg.reply(
        "📢 Send the message, photo, video, sticker, or media you want to broadcast."
    )

# =========================================================
# FORCE JOIN VERIFY
# =========================================================

@dp.callback_query(
    lambda c: c.data == "forcejoin_verify"
)
async def forcejoin_verify(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    # =====================================================
    # FRESH MEMBERSHIP CHECK
    # =====================================================

    missing = await get_missing_channels(
        bot,
        user_id
    )

    # =====================================================
    # ALL CHANNELS JOINED
    # =====================================================

    if not missing:

        try:
            await callback.message.edit_text(
                "✅ <b>Membership Verified</b>\n\n"
                "You have joined all required channels.\n\n"
                "🎉 You can now use the bot normally.",
                parse_mode="HTML"
            )

        except Exception as e:
            print(
                f"[FORCE JOIN] Verify edit error: {e}"
            )

        await callback.answer(
            "✅ Verified! Access granted.",
            show_alert=False
        )

        return

    # =====================================================
    # CHANNELS STILL MISSING
    # =====================================================

    keyboard = await build_force_join_keyboard(
        bot,
        missing
    )

    count = len(missing)

    channel_word = (
        "channel"
        if count == 1
        else "channels"
    )

    text = (
        "⚠️ <b>Join Required</b>\n\n"
        f"You still need to join "
        f"<b>{count} {channel_word}</b>.\n\n"
        "Join all required channels below, "
        "then tap <b>Verify Membership</b> again."
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        print(
            f"[FORCE JOIN] Verify refresh error: {e}"
        )

    await callback.answer(
        "❌ You haven't joined all required channels yet.",
        show_alert=True
    )


# =========================================================
# GROUP FORCE JOIN
# =========================================================

@dp.callback_query(
    lambda c: c.data == "group_forcejoin"
)
async def group_forcejoin(
    callback: CallbackQuery
):

    user_id = callback.from_user.id

    # =====================================================
    # FRESH MEMBERSHIP CHECK
    # =====================================================

    missing = await get_missing_channels(
        bot,
        user_id
    )

    # =====================================================
    # ALL CHANNELS JOINED
    # =====================================================

    if not missing:

        await callback.answer(
            "✅ You have already joined all required channels.",
            show_alert=False
        )

        try:
            await callback.message.edit_text(
                "✅ <b>Membership Verified</b>\n\n"
                "You have joined all required channels.\n"
                "🎉 You can now use the bot normally.",
                parse_mode="HTML"
            )

        except Exception as e:
            print(
                f"[FORCE JOIN] Group verify edit error: {e}"
            )

        return

    # =====================================================
    # SHOW MISSING CHANNELS
    # =====================================================

    keyboard = await build_group_force_join_keyboard(
        bot,
        missing
    )

    count = len(missing)

    channel_word = (
        "channel"
        if count == 1
        else "channels"
    )

    text = (
        "⚠️ <b>Join Required</b>\n\n"
        f"You still need to join "
        f"<b>{count} {channel_word}</b>.\n\n"
        "Join the required channels below, "
        "then tap <b>Verify Membership</b>."
    )

    try:
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        print(
            f"[FORCE JOIN] Group force join edit error: {e}"
        )

    await callback.answer()

#TMDB 
@dp.callback_query(lambda c: c.data.startswith("tmdb_movie_"))
async def tmdb_movie(callback: CallbackQuery):

    parts = callback.data.split("_")

    search_id = parts[2]
    index = int(parts[3])

    session = tmdb_sessions.get(search_id)
    if not session:

        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    movies = session["movies"]

    movie = movies[index]

    session["selected"] = movie
    session["images"] = None
    session["mode"] = None
    session["index"] = 0

    media_type = movie["media_type"]

    images = await get_images(
        media_type,
        movie["id"]
    )

    session["images"] = images

    session["details"] = await get_movie_details(
        media_type,
        movie["id"]
    )

    title = movie.get("title") or movie.get("name")

    date = movie.get("release_date") or movie.get("first_air_date")

    year = ""

    if date:
        year = date[:4]

    poster_count = len(session["images"]["posters"])
    landscapes = [
        img for img in session["images"]["backdrops"]
        if img.get("iso_639_1") is not None
    ]

    backdrop_count = len(landscapes)
    media_type = movie["media_type"]
    tmdb_link = f"https://www.themoviedb.org/{media_type}/{movie['id']}"
    logo_count = len(session["images"]["logos"])

    clean_count = len([
        img for img in session["images"]["backdrops"]
        if img.get("iso_639_1") is None
    ])
    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Posters ({poster_count})",
                    callback_data=f"tmdb_posters_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Landscapes ({backdrop_count})",
                    callback_data=f"tmdb_backdrops_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Logos ({logo_count})",
                    callback_data=f"tmdb_logos_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Clean Landscape ({clean_count})",
                    callback_data=f"tmdb_clean_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data=f"tmdb_search_back_{search_id}"
                ),
                InlineKeyboardButton(
                    text="Close",
                    callback_data="tmdb_close"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        f"{title} ({year})\n\n"
        f"TMDB\n"
        f"{tmdb_link}\n\n"
        f"Select Image Type",
        reply_markup=buttons,
        disable_web_page_preview=True
    )

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("tmdb_posters_"))
async def tmdb_posters(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_posters_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    posters = session["images"]["posters"]

    if not posters:
        await callback.answer(
            "No Posters Found",
            show_alert=True
        )
        return

    session["mode"] = "poster"
    session["index"] = 0
    session["language_filter"] = None

    await show_language_selection(
        callback,
        session,
        "poster",
        posters
    )
    

@dp.callback_query(lambda c: c.data.startswith("tmdb_backdrops_"))
async def tmdb_backdrops(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_backdrops_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    backdrops = [
        img
        for img in session["images"]["backdrops"]
        if img.get("iso_639_1") is not None
    ]

    if not backdrops:
        await callback.answer(
            "No Landscapes Found",
            show_alert=True
        )
        return

    session["mode"] = "backdrop"
    session["index"] = 0
    session["language_filter"] = None

    await show_language_selection(
        callback,
        session,
        "backdrop",
        backdrops
    )
    
@dp.callback_query(lambda c: c.data.startswith("tmdb_logos_"))
async def tmdb_logos(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_logos_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    logos = session["images"]["logos"]

    if not logos:
        await callback.answer(
            "No Logos Found",
            show_alert=True
        )
        return

    session["mode"] = "logo"
    session["index"] = 0
    session["language_filter"] = None

    await show_language_selection(
        callback,
        session,
        "logo",
        logos
    )

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("tmdb_clean_"))
async def tmdb_clean(callback: CallbackQuery):

    search_id = callback.data.replace("tmdb_clean_", "")

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    clean = [
        img for img in session["images"]["backdrops"]
        if img.get("iso_639_1") is None
    ]

    if not clean:
        await callback.answer(
            "No clean landscapes found.",
            show_alert=True
        )
        return

    session["mode"] = "clean"
    session["language_step"] = False
    session["index"] = 0

    await show_tmdb_image(
        callback,
        session,
        clean,
        "Clean Landscape"
    )

# =========================================================
# TMDB LANGUAGE SELECTION
# =========================================================

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_lang_")
)
async def tmdb_language_select(callback: CallbackQuery):

    parts = callback.data.split("_")

    # tmdb_lang_MODE_SEARCHID_LANGUAGE
    mode = parts[2]
    search_id = parts[3]
    language = parts[4]

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    source_images = get_mode_images(
        session,
        mode
    )

    if not source_images:
        await callback.answer(
            "No Images Found",
            show_alert=True
        )
        return

    # -----------------------------------------------------
    # ALL LANGUAGES
    # -----------------------------------------------------

    if language == "all":

        filtered_images = source_images

        session["language_filter"] = None

    # -----------------------------------------------------
    # SPECIFIC LANGUAGE
    # -----------------------------------------------------

    else:

        filtered_images = get_language_filtered_images(
            source_images,
            language
        )

        session["language_filter"] = language

    if not filtered_images:

        await callback.answer(
            "No images found for this language.",
            show_alert=True
        )
        return

    session["mode"] = mode
    session["index"] = 0

    label = {
        "poster": "Poster",
        "backdrop": "Landscape",
        "logo": "Logo"
    }.get(
        mode,
        mode.title()
    )

    await show_tmdb_image(
        callback,
        session,
        filtered_images,
        label
    )

# =========================================================
# BACK TO LANGUAGE SELECTION
# =========================================================

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_langback_")
)
async def tmdb_language_back(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_langback_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    mode = session.get("mode")

    if mode not in (
        "poster",
        "backdrop",
        "logo"
    ):
        await callback.answer(
            "Language selection is not available here.",
            show_alert=True
        )
        return

    images = get_mode_images(
        session,
        mode
    )

    if not images:
        await callback.answer(
            "No Images Found",
            show_alert=True
        )
        return

    await show_language_selection(
        callback,
        session,
        mode,
        images
    )



@dp.callback_query(lambda c: c.data.startswith("tmdb_prev_"))
async def tmdb_prev(callback: CallbackQuery):

    search_id = callback.data.replace("tmdb_prev_", "")

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    mode = session["mode"]
    language_filter = session.get("language_filter")

    images = get_mode_images(
        session,
        mode
    )

    label = {
        "poster": "Poster",
        "backdrop": "Landscape",
        "logo": "Logo",
        "clean": "Clean Landscape"
    }.get(
        mode,
        ""
    )

    # ---------------------------------------------------------
    # CLEAN POSTER
    # ---------------------------------------------------------

    if (
        mode == "poster"
        and language_filter == "clean"
    ):

        images = [
            image
            for image in images
            if image.get("iso_639_1") is None
        ]

    # ---------------------------------------------------------
    # SPECIFIC LANGUAGE
    # ---------------------------------------------------------

    elif language_filter:

        images = get_language_filtered_images(
            images,
            language_filter
        )

    if not images:
        await callback.answer()
        return

    session["index"] -= 1

    if session["index"] < 0:
        session["index"] = len(images) - 1

    await show_tmdb_image(
        callback,
        session,
        images,
        label
    )

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("tmdb_next_"))
async def tmdb_next(callback: CallbackQuery):

    search_id = callback.data.replace("tmdb_next_", "")

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    mode = session["mode"]
    language_filter = session.get("language_filter")

    images = get_mode_images(
        session,
        mode
    )

    label = {
        "poster": "Poster",
        "backdrop": "Landscape",
        "logo": "Logo",
        "clean": "Clean Landscape"
    }.get(
        mode,
        ""
    )

    # ---------------------------------------------------------
    # CLEAN POSTER
    # ---------------------------------------------------------

    if (
        mode == "poster"
        and language_filter == "clean"
    ):

        images = [
            image
            for image in images
            if image.get("iso_639_1") is None
        ]

    # ---------------------------------------------------------
    # SPECIFIC LANGUAGE
    # ---------------------------------------------------------

    elif language_filter:

        images = get_language_filtered_images(
            images,
            language_filter
        )

    if not images:
        await callback.answer()
        return

    session["index"] += 1

    if session["index"] >= len(images):
        session["index"] = 0

    await show_tmdb_image(
        callback,
        session,
        images,
        label
    )

# =========================================================
# BACK TO IMAGE TYPE SELECTION
# =========================================================

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_back_")
)
async def tmdb_back(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_back_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    movie = session.get("selected")

    if not movie:
        await callback.answer(
            "Movie selection is no longer available.",
            show_alert=True
        )
        return

    title = (
        movie.get("title")
        or movie.get("name")
        or "Unknown"
    )

    date = (
        movie.get("release_date")
        or movie.get("first_air_date")
        or ""
    )

    year = date[:4] if date else ""

    media_type = movie.get(
        "media_type",
        "movie"
    )

    tmdb_link = (
        f"https://www.themoviedb.org/"
        f"{media_type}/{movie.get('id')}"
    )

    images = session.get("images") or {}

    poster_count = len(
        images.get("posters", [])
    )

    backdrop_count = len([
        img
        for img in images.get("backdrops", [])
        if img.get("iso_639_1") is not None
    ])

    logo_count = len(
        images.get("logos", [])
    )

    clean_count = len([
        img
        for img in images.get("backdrops", [])
        if img.get("iso_639_1") is None
    ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Posters ({poster_count})",
                    callback_data=f"tmdb_posters_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Landscapes ({backdrop_count})",
                    callback_data=f"tmdb_backdrops_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Logos ({logo_count})",
                    callback_data=f"tmdb_logos_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Clean Landscape ({clean_count})",
                    callback_data=f"tmdb_clean_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data=f"tmdb_search_back_{search_id}"
                ),
                InlineKeyboardButton(
                    text="Close",
                    callback_data="tmdb_close"
                )
            ]
        ]
    )

    session["language_step"] = False
    session["language_filter"] = None
    session["index"] = 0

    await callback.message.edit_text(
        f"{html.escape(title)} ({year})\n\n"
        f"TMDB\n"
        f"{tmdb_link}\n\n"
        f"Select Image Type",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await callback.answer()

# =========================================================
# BACK FROM LANGUAGE SELECTION TO IMAGE TYPE
# =========================================================

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_typeback_")
)
async def tmdb_typeback(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_typeback_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    movie = session.get("selected")

    if not movie:
        await callback.answer(
            "Movie selection is no longer available.",
            show_alert=True
        )
        return

    title = (
        movie.get("title")
        or movie.get("name")
        or "Unknown"
    )

    date = (
        movie.get("release_date")
        or movie.get("first_air_date")
        or ""
    )

    year = date[:4] if date else ""

    media_type = movie.get(
        "media_type",
        "movie"
    )

    tmdb_link = (
        f"https://www.themoviedb.org/"
        f"{media_type}/{movie.get('id')}"
    )

    images = session.get("images") or {}

    poster_count = len(
        images.get("posters", [])
    )

    backdrop_count = len([
        img
        for img in images.get("backdrops", [])
        if img.get("iso_639_1") is not None
    ])

    logo_count = len(
        images.get("logos", [])
    )

    clean_count = len([
        img
        for img in images.get("backdrops", [])
        if img.get("iso_639_1") is None
    ])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Posters ({poster_count})",
                    callback_data=f"tmdb_posters_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Landscapes ({backdrop_count})",
                    callback_data=f"tmdb_backdrops_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"Logos ({logo_count})",
                    callback_data=f"tmdb_logos_{search_id}"
                ),
                InlineKeyboardButton(
                    text=f"Clean Landscape ({clean_count})",
                    callback_data=f"tmdb_clean_{search_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data=f"tmdb_search_back_{search_id}"
                ),
                InlineKeyboardButton(
                    text="Close",
                    callback_data="tmdb_close"
                )
            ]
        ]
    )

    session["language_step"] = False
    session["language_filter"] = None
    session["index"] = 0

    await callback.message.edit_text(
        f"{html.escape(title)} ({year})\n\n"
        f"TMDB\n"
        f"{tmdb_link}\n\n"
        f"Select Image Type",
        reply_markup=keyboard,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

    await callback.answer()

@dp.callback_query(
    lambda c: (
        c.data.startswith("tmdb_info_")
        and not c.data.startswith("tmdb_info_back_")
    )
)
async def tmdb_info(callback: CallbackQuery):

    search_id = callback.data.replace("tmdb_info_", "")

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    details = session.get("details")

    if not details:
        await callback.answer(
            "No information available.",
            show_alert=True
        )
        return

    title = details.get("title") or details.get("name")

    date = details.get("release_date") or details.get("first_air_date") or "Unknown"

    rating = details.get("vote_average", 0)

    votes = details.get("vote_count", 0)

    language = details.get("original_language", "").upper()

    genres = ", ".join(
        g["name"] for g in details.get("genres", [])
    )

    runtime = details.get("runtime")

    seasons = details.get("number_of_seasons")

    episodes = details.get("number_of_episodes")

    overview = details.get("overview", "No overview available.")

    if len(overview) > 350:
        overview = overview[:350] + "..."

    text = (
        f"<b>{html.escape(title)}</b>\n\n"

        f"<b>Rating</b> : <code>{rating}/10</code> "
        f"<code>({votes:,} Votes)</code>\n"

        f"<b>Release</b> : <code>{html.escape(date)}</code>\n"

        f"<b>Language</b> : <code>{html.escape(language)}</code>\n"
    )

    if genres:
        text += (
            f"<b>Genres</b> : "
            f"<code>{html.escape(genres)}</code>\n"
        )

    if runtime:
        text += (
            f"<b>Runtime</b> : "
            f"<code>{runtime} min</code>\n"
        )

    if seasons:
        text += (
            f"<b>Seasons</b> : "
            f"<code>{seasons}</code>\n"
        )

    if episodes:
        text += (
            f"<b>Episodes</b> : "
            f"<code>{episodes}</code>\n"
        )

    text += (
        "\n<blockquote><b>Storyline</b></blockquote>\n"
        f"<blockquote><code>{html.escape(overview)}</code></blockquote>"
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Back",
                    callback_data=f"tmdb_info_back_{search_id}"
                ),
                InlineKeyboardButton(
                    text="Close",
                    callback_data="tmdb_close"
                )
            ]
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

    await callback.answer()

@dp.callback_query(
    lambda c: c.data.startswith("tmdb_info_back_")
)
async def tmdb_info_back(callback: CallbackQuery):

    search_id = callback.data.replace(
        "tmdb_info_back_",
        ""
    )

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    # Info se exactly wahi image list restore karo
    # jo Info kholne se pehle screen par thi.
    images = session.get("current_images", [])

    if not images:
        await callback.answer(
            "Previous image page is no longer available.",
            show_alert=True
        )
        return

    mode = session.get("mode")

    label = {
        "poster": "Poster",
        "backdrop": "Landscape",
        "logo": "Logo",
        "clean": "Clean Landscape"
    }.get(mode, "")

    # index ko valid rakho
    if session.get("index", 0) >= len(images):
        session["index"] = 0

    await show_tmdb_image(
        callback,
        session,
        images,
        label
    )

    await callback.answer()
    
@dp.callback_query(lambda c: c.data == "tmdb_close")
async def tmdb_close(callback: CallbackQuery):

    await callback.message.delete()

    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("tmdb_search_back_"))
async def tmdb_search_back(callback: CallbackQuery):

    search_id = callback.data.replace("tmdb_search_back_", "")

    session = tmdb_sessions.get(search_id)

    if not session:
        await callback.answer(
            "Session Expired",
            show_alert=True
        )
        return

    movies = session["movies"]

    buttons = []

    for i, movie in enumerate(movies):

        title = movie.get("title") or movie.get("name")

        date = movie.get("release_date") or movie.get("first_air_date") or ""

        year = date[:4] if date else ""

        buttons.append([
            InlineKeyboardButton(
                text=f"{title} ({year})",
                callback_data=f"tmdb_movie_{search_id}_{i}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="Close",
            callback_data="tmdb_close"
        )
    ])

    await callback.message.edit_text(
        "Search Results",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=buttons
        )
    )

    await callback.answer()

# 🔥 PREMIUM INLINE SETTINGS PANEL

@dp.callback_query(lambda c: c.data == "settings")
async def settings_panel(callback: CallbackQuery):

    user_id = callback.message.chat.id

    tag = get_tag(user_id)
    words = get_words(user_id)

    settings = get_settings(user_id)

    cleaner = "🟢 ON" if settings["cleaner"] else "🔴 OFF"
    links = "🟢 ON" if settings["links"] else "🔴 OFF"
    tags = "🟢 ON" if settings["tags"] else "🔴 OFF"
    hashtags = "🟢 ON" if settings["hashtags"] else "🔴 OFF"

    if not tag:
        tag = "Not Set"

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[

            [
                InlineKeyboardButton(
                    text=f"⚡ Cleaner {cleaner}",
                    callback_data="toggle_cleaner"
                )
            ],

            [
                InlineKeyboardButton(
                    text=f"🔗 Links {links}",
                    callback_data="toggle_links"
                ),

                InlineKeyboardButton(
                    text=f"@️⃣ Tags {tags}",
                    callback_data="toggle_tags"
                )
            ],

            [
                InlineKeyboardButton(
                    text=f"#️⃣ Hashtags {hashtags}",
                    callback_data="toggle_hashtags"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🏷 Branding",
                    callback_data="branding"
                ),

                InlineKeyboardButton(
                    text="🧹 Remove Words",
                    callback_data="remove"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📤 Export Settings",
                    callback_data="export_settings"
               ),

                InlineKeyboardButton(
                    text="📥 Upload Settings",
                    callback_data="upload_settings"
                )
            ],

            [
                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="stats"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔙 Back Home",
                    callback_data="back_home"
                )
            ]
        ]
    )

    text = (
         "╔══════════════╗\n"
         "⚙️ XULU CONTROL PANEL\n"
         "╚══════════════╝\n\n"

        f"🏷 Branding:\n{tag}\n\n"

        f"🧹 Remove Filters:\n{len(words)} saved\n\n"

        f"⚡ Cleaner : {cleaner}\n"
        f"🔗 Links : {links}\n"
        f"@️⃣ Tags : {tags}\n"
        f"#️⃣ Hashtags : {hashtags}\n\n"

        "🔥 Premium Inline System"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=buttons
    )

    await callback.answer()

# 🔥 TOGGLE CLEANER
@dp.callback_query(lambda c: c.data == "toggle_cleaner")
async def toggle_cleaner(callback: CallbackQuery):

    toggle_setting(callback.message.chat.id, "cleaner")

    await settings_panel(callback)


# 🔥 TOGGLE LINKS
@dp.callback_query(lambda c: c.data == "toggle_links")
async def toggle_links(callback: CallbackQuery):

    toggle_setting(callback.message.chat.id, "links")

    await settings_panel(callback)


# 🔥 TOGGLE TAGS
@dp.callback_query(lambda c: c.data == "toggle_tags")
async def toggle_tags(callback: CallbackQuery):

    toggle_setting(callback.message.chat.id, "tags")

    await settings_panel(callback)


# 🔥 TOGGLE HASHTAGS
@dp.callback_query(lambda c: c.data == "toggle_hashtags")
async def toggle_hashtags(callback: CallbackQuery):

    toggle_setting(callback.message.chat.id, "hashtags")

    await settings_panel(callback)

# 🔹 REMOVE PANEL
@dp.callback_query(lambda c: c.data == "remove")
async def remove_panel(callback: CallbackQuery):

    user_id = callback.message.chat.id

    remove_pages[user_id] = 0

    await show_remove_page(
        callback,
        0
    )

    await callback.answer()
# =========================================================
# 🔹 REMOVE WORDS PAGINATION
# =========================================================

async def show_remove_page(
    callback: CallbackQuery,
    page: int
):

    user_id = callback.from_user.id

    words = get_words(user_id)

    # -----------------------------------------------------
    # BUILD PAGES BASED ON TELEGRAM CAPTION LIMIT
    # -----------------------------------------------------

    MAX_CAPTION_LENGTH = 1024

    prefix = "🧹 Remove Word Manager\n\n"
    suffix = "\n\n➕ Add:\n/remove your text"

    pages = []
    current_words = []
    current_length = len(prefix) + len(suffix)

    for word in words:

        word_line = f"• <code>{html.escape(word)}</code>\n"

        if (
            current_words
            and current_length + len(word_line) > MAX_CAPTION_LENGTH
        ):
            pages.append(current_words)

            current_words = []
            current_length = len(prefix) + len(suffix)

        current_words.append(word)
        current_length += len(word_line)

    if current_words:
        pages.append(current_words)

    if not pages:
        pages = [[]]

    total_pages = len(pages)

    # -----------------------------------------------------
    # KEEP PAGE INSIDE VALID RANGE
    # -----------------------------------------------------

    page = max(
        0,
        min(page, total_pages - 1)
    )

    remove_pages[user_id] = page

    page_words = pages[page]

    # -----------------------------------------------------
    # WORD DISPLAY
    # -----------------------------------------------------

    if page_words:

        saved_words = "\n".join(
            f"• <code>{html.escape(word)}</code>"
            for word in page_words
        )

    else:

        saved_words = "No remove words saved."

    # -----------------------------------------------------
    # PAGINATION BUTTONS
    # -----------------------------------------------------

    pagination_buttons = []

    if total_pages > 1:

        pagination_buttons.append([
            InlineKeyboardButton(
                text="<",
                callback_data="remove_prev"
            ),
            InlineKeyboardButton(
                text=f"{page + 1}/{total_pages}",
                callback_data="remove_page_info"
            ),
            InlineKeyboardButton(
                text=">",
                callback_data="remove_next"
            )
        ])

    # -----------------------------------------------------
    # MAIN BUTTONS
    # -----------------------------------------------------

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[

            *pagination_buttons,

            [
                InlineKeyboardButton(
                    text="📤 Export",
                    callback_data="export_remove_words"
                ),
                InlineKeyboardButton(
                    text="📥 Upload",
                    callback_data="upload_remove_words"
                )
            ],

            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="back_home"
                ),
                InlineKeyboardButton(
                    text="❌ Close",
                    callback_data="remove_close"
                )
            ]
        ]
    )

    # -----------------------------------------------------
    # FINAL TEXT
    # -----------------------------------------------------

    text = (
        "🧹 Remove Word Manager\n\n"
        f"{saved_words}\n\n"
        "➕ Add:\n"
        "/remove your text"
    )

    await update_remove_words_display(
        callback,
        text,
        buttons
    )

# =========================================================
# ▶️ NEXT PAGE
# =========================================================

@dp.callback_query(lambda c: c.data == "remove_next")
async def remove_next(callback: CallbackQuery):

    user_id = callback.from_user.id

    current_page = remove_pages.get(
        user_id,
        0
    )

    await show_remove_page(
        callback,
        current_page + 1
    )

    await callback.answer()

# =========================================================
# ◀️ PREVIOUS PAGE
# =========================================================

@dp.callback_query(lambda c: c.data == "remove_prev")
async def remove_prev(callback: CallbackQuery):

    user_id = callback.from_user.id

    current_page = remove_pages.get(
        user_id,
        0
    )

    if current_page <= 0:
        await callback.answer(
            "Already on the first page."
        )
        return

    await show_remove_page(
        callback,
        current_page - 1
    )

    await callback.answer()
    
# =========================================================
# ℹ️ PAGE INFO
# =========================================================

@dp.callback_query(lambda c: c.data == "remove_page_info")
async def remove_page_info(callback: CallbackQuery):

    await callback.answer(
        "Use ◀️ and ▶️ to change pages."
    )


# =========================================================
# ❌ CLOSE REMOVE PANEL
# =========================================================

@dp.callback_query(lambda c: c.data == "remove_close")
async def remove_close(callback: CallbackQuery):

    user_id = callback.from_user.id

    remove_pages.pop(
        user_id,
        None
    )

    try:
        await callback.message.delete()
    except Exception as e:
        print(
            "Remove panel close error:",
            e
        )

    await callback.answer()
    
# =========================================================
# 🔹 REMOVE WORDS DISPLAY HELPER
# =========================================================

async def update_remove_words_display(
    callback: CallbackQuery,
    text: str,
    buttons: InlineKeyboardMarkup
):

    # Caption limit cross nahi hui
    if len(text) <= 1024:

        if callback.message.caption is not None:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=buttons,
                parse_mode="HTML"
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=buttons,
                parse_mode="HTML"
            )

        return

    # Caption limit cross ho gayi
    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.message.answer(
        text=text,
        reply_markup=buttons,
        parse_mode="HTML"
    )

# 🔹 BRANDING PANEL
@dp.callback_query(lambda c: c.data == "branding")
async def branding_panel(callback: CallbackQuery):

    user_id = callback.message.chat.id

    tag = get_tag(user_id)

    if not tag:
        tag = "No branding set."

    buttons = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📤 Export",
                callback_data="export_branding"
            ),
            InlineKeyboardButton(
                text="📥 Upload",
                callback_data="upload_branding"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔙 Back",
                callback_data="back_home"
            )
        ]
    ]
)

    text = (
        "🏷 Branding Manager\n\n"

        f"📌 Current Branding:\n<code>{html.escape(tag)}</code>\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Branding Commands\n\n"

        "/settag your text\n"
        "Adds custom branding automatically.\n\n"

        "/removetag\n"
        "Removes current branding.\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "🔥 Example:\n\n"

        "/settag Powered By XuLu"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=buttons,
        parse_mode="HTML"
    )

    await callback.answer()


# 🔹 USER STATS
@dp.callback_query(lambda c: c.data == "stats")
async def stats_panel(callback: CallbackQuery):

    user_id = callback.message.chat.id

    tag = get_tag(user_id)

    words = get_words(user_id)

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Back",
                    callback_data="back_home"
                )
            ]
        ]
    )

    text = (
        "📊 Your Statistics\n\n"

        f"🏷 Branding Active:\n{tag if tag else 'No'}\n\n"

        f"🧹 Remove Filters:\n{len(words)}\n\n"

        "⚡ Cleaner Status: Active\n"
        "🔥 Premium Engine Running"
    )

    await callback.message.edit_caption(
        caption=text,
        reply_markup=buttons
    )

    await callback.answer()

# 🔹 HELP PANEL
@dp.callback_query(lambda c: c.data == "help")
async def help_panel(callback: CallbackQuery):

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Close",
                    callback_data="close_help"
                )
            ]
        ]
    )

    text = (
        "📘 XuLu Auto Cleaner — Full Guide\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ What This Bot Does\n\n"

        "XuLu Auto Cleaner is a premium Telegram automation bot designed to clean and rebrand your content automatically.\n\n"

        "The bot can:\n"
        "• Remove links\n"
        "• Remove @tags\n"
        "• Clean hashtags\n"
        "• Remove custom words/sentences\n"
        "• Add branding automatically\n"
        "• Process media & captions\n"
        "• Work in DM, Groups & Channels\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "🧹 How To Use\n\n"

        "1️⃣ Send any text, photo, video, or document.\n\n"

        "2️⃣ The bot automatically scans your caption/text.\n\n"

        "3️⃣ Links, hashtags, tags, and filtered words are removed instantly.\n\n"

        "4️⃣ Your branding tag is added automatically if enabled.\n\n"

        "5️⃣ Cleaned content is sent back instantly.\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "🏷 Branding System\n\n"

        "Use:\n"
        "/settag your text\n\n"

        "Example:\n"
        "/settag Powered By XuLu\n\n"

        "To remove branding:\n"
        "/removetag\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "🗑 Remove Filter System\n\n"

        "Use:\n"
        "/remove your word\n\n"

        "Example:\n"
        "/remove subscribe\n\n"

        "The bot will automatically remove that word or sentence from future messages.\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Supported Content\n\n"

        "✔ Text\n"
        "✔ Photos\n"
        "✔ Videos\n"
        "✔ Documents\n"
        "✔ Channel Posts\n"
        "✔ Group Messages\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ Need Help?\n\n"

        f"Developer Contact:\n{DEV_CONTACT}\n\n"

        "🔥 XuLu Auto Cleaner Premium System"
    )

    await callback.message.answer(
        text,
        reply_markup=buttons
    )

    await callback.answer()


# 🔹 CLOSE HELP
@dp.callback_query(lambda c: c.data == "close_help")
async def close_help(callback: CallbackQuery):

    try:
        await callback.message.delete()
    except:
        pass

    await callback.answer()


# 🔹 BACK HOME
@dp.callback_query(lambda c: c.data == "back_home")
async def back_home(callback: CallbackQuery):

    mention = callback.from_user.mention_html()

    buttons = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    callback_data="settings"
                ),
                InlineKeyboardButton(
                    text="🧹 Remove Words",
                    callback_data="remove"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏷 Branding",
                    callback_data="branding"
                ),
                InlineKeyboardButton(
                    text="📊 Stats",
                    callback_data="stats"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❓ Help",
                    callback_data="help"
                )
            ]
        ]
    )

    home_text = (
        f"👋 Hello {mention}\n\n"
        "Welcome to —͟͟͞͞<b>𝐗𝐔 𝐋𝐔 ᥫ᭡ 𝐀𝐮𝐭𝐨 𝐂𝐥𝐞𝐚𝐧𝐞𝐫 𝐁𝐨𝐭</b>\n\n"
        "⚡ <b>A powerful Telegram automation tool</b> to clean, control, and rebrand your content.\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "✨ <b>Features:</b>\n"
        "• <b>Remove links, tags, hashtags</b>\n"
        "• <b>Custom word & sentence filter</b>\n"
        "• <b>Auto branding system</b>\n"
        "• <b>Poster search & download</b>\n"
        "• <b>Movie & TV Series search</b>\n"
        "• <b>Landscapes, Logos & Clean Images</b>\n"
        "• <b>Bulk processing supported</b>\n"
        "• <b>Smart cleaning engine</b>\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚙️ <b>Quick Commands:</b>\n"
        "• <code>/settag your text</code> — Set branding\n"
        "• <code>/remove your text</code> — Add custom filter\n"
        "• <code>/removetag</code> — Remove branding\n"
        "• <code>/poster movie name</code> — Search & download posters\n"
        "• <code>/p movie name</code> — Search & download posters\n\n"

        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ <b>Need Help?</b>\n"
        f"👨‍💻 <b>Contact Developer:</b> {DEV_CONTACT}"
    )

    if callback.message.caption is not None:
        await callback.message.edit_caption(
            caption=home_text,
            reply_markup=buttons,
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            text=home_text,
            reply_markup=buttons,
            parse_mode="HTML"
        )
    
    await callback.answer()

# 🔹 PROCESS FUNCTION
async def process(msg: types.Message):

    user_id = msg.chat.id

    tag = get_tag(user_id)
    words = get_words(user_id)

    text = msg.caption or msg.text or ""

    settings = get_settings(user_id)

    # CLEAN SYSTEM
    if settings["cleaner"]:

        cleaned = clean_text(
            text,
            words,
            tag,
            settings
        )

    else:

        cleaned = text

        if tag:
            cleaned += f"\n\n{tag}"

    # SAFETY FIX
    if cleaned is None:
        cleaned = text

    # 🔥 Detect removed words
    removed_now = []

    for w in words:

        if w.lower() in text.lower():

            removed_now.append(w)

    # 🔥 CHANNEL MODE
    if msg.chat.type == "channel":

        try:
            await msg.delete()
        except:
            pass

        if msg.video:

            await bot.send_video(
                msg.chat.id,
                msg.video.file_id,
                caption=cleaned,
            )

        elif msg.document:

            await bot.send_document(
                msg.chat.id,
                msg.document.file_id,
                caption=cleaned,
            )

        elif msg.photo:

            await bot.send_photo(
                msg.chat.id,
                msg.photo[-1].file_id,
                caption=cleaned,
            )

        elif msg.text:

            await bot.send_message(
                msg.chat.id,
                cleaned
            )

    else:

        # 🔥 DM SUMMARY SYSTEM
        if msg.chat.type == "private":

            if user_id not in user_sessions:

                user_sessions[user_id] = {
                    "files": 0,
                    "tag": tag if tag else "No Branding",
                    "removed": []
                }

            user_sessions[user_id]["files"] += 1

            for w in removed_now:

                if w not in user_sessions[user_id]["removed"]:

                    user_sessions[user_id]["removed"].append(w)

            # Cancel old timer
            old_task = summary_tasks.get(user_id)

            if old_task:
                old_task.cancel()

            # New summary timer
            summary_tasks[user_id] = asyncio.create_task(
                send_summary(user_id)
            )

        # 🔥 SEND CLEANED CONTENT
        if msg.text:

            await msg.reply(cleaned)

        elif msg.video:

            await msg.reply_video(
                msg.video.file_id,
                caption=cleaned,
            )

        elif msg.document:

            await msg.reply_document(
                msg.document.file_id,
                caption=cleaned,
            )

        elif msg.photo:

            await msg.reply_photo(
                msg.photo[-1].file_id,
                caption=cleaned,
            )
            
# 🔹 SEND CLEANING SUMMARY
async def send_summary(user_id):

    try:

        await asyncio.sleep(5)

        data = user_sessions.get(user_id)

        if not data:
            return

        words = data["removed"]

        if words:
            removed_words = "\n".join(
                [f"• {w}" for w in words[:10]]
            )
        else:
            removed_words = "No custom filters."

        text = (
            "✅ Cleaning Session Completed\n\n"

            f"📦 Processed Files:\n"
            f"• {data['files']}\n\n"

            "🗑 Removed:\n"
            "• Links\n"
            "• Tags\n"
            "• Hashtags\n\n"

            f"🏷 Branding Added:\n"
            f"• {data['tag']}\n\n"

            "🧹 Custom Filters:\n"
            f"{removed_words}\n\n"

            "⚡ Status:\n"
            "All files processed successfully.\n\n"

            "<blockquote><b>Powered By @xulubots</b></blockquote>"
        )

        await bot.send_message(
            user_id,
            text,
            parse_mode="HTML"
        )
        
        del user_sessions[user_id]

    except Exception as e:
        print("Summary Error:", e)
            
# =========================================================
# CHANNEL HANDLER
# =========================================================
# Channel posts:
# ❌ Cleaner disabled
# ❌ Broadcast disabled
# =========================================================

@dp.channel_post()
async def channel_handler(msg: types.Message):

    # Channel messages ko cleaner queue me mat bhejo.
    # Channel ke liye broadcast bhi process nahi hoga.

    return


# =========================================================
# 🔹 MAIN HANDLER
# =========================================================

@dp.message(lambda msg: not (msg.text and msg.text.startswith("/")))
async def main_handler(msg: types.Message):

    # =====================================================
    # GROUP / SUPERGROUP
    # =====================================================

    if msg.chat.type in ["group", "supergroup"]:

        # =================================================
        # @ADMIN
        # =================================================

        if msg.text and "@admin" in msg.text.lower():

            admins = await bot.get_chat_administrators(
                msg.chat.id
            )

            admin_users = [
                admin.user
                for admin in admins
                if not admin.user.is_bot
            ]

            user_mention = msg.from_user.mention_html(
                msg.from_user.full_name
            )

            for i in range(
                0,
                len(admin_users),
                4
            ):

                chunk = admin_users[i:i + 4]

                mentions = " • ".join(
                    user.mention_html(
                        user.full_name
                    )
                    for user in chunk
                )

                await msg.reply(
                    f"<b>{user_mention} needs assistance.</b>\n"
                    f"Please check the replied message.\n\n"
                    f"{mentions}",
                    parse_mode="HTML"
                )

        # =================================================
        # IMPORTANT
        # =================================================
        # Normal GC messages:
        # NO Force Join
        #
        # @admin:
        # WORKS
        #
        # Commands:
        # Handled by their own command handlers.
        # =================================================

        return

    # =====================================================
    # PRIVATE CHAT
    # =====================================================

    # Every normal PM message gets Force Join check.

    if not await check_access(
        bot,
        msg
    ):
        return

    # =====================================================
    # SAVE / UPDATE PM USER
    # =====================================================

    add_pm_user(
        user_id=msg.from_user.id,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name,
        username=msg.from_user.username
    )

    # =====================================================
    # 🔥 BROADCAST MODE
    # =====================================================

    if msg.from_user.id in broadcast_mode:

        broadcast_mode.remove(
            msg.from_user.id
        )

        users = get_all_users()

        sent = 0
        failed = 0

        for user_id in users:

            try:

                await bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=msg.chat.id,
                    message_id=msg.message_id
                )

                sent += 1

                await asyncio.sleep(0.05)

            except Exception:

                failed += 1

        await msg.reply(
            f"✅ Broadcast completed\n\n"
            f"📤 Sent: {sent}\n"
            f"❌ Failed: {failed}"
        )

        return

    # =====================================================
    # NORMAL PRIVATE MESSAGE
    # =====================================================

    await add_to_queue(
        msg,
        process
    )

# 🔹 OWNER PANEL
@dp.message(Command("panel"))
async def owner_panel(msg: types.Message):

    # Group me kuch bhi reply mat karo
    if msg.chat.type != "private":
        return

    if msg.from_user.id != OWNER_ID:
        await msg.reply(
            f"Unknown command.\nContact: {DEV_CONTACT}"
        )
        return

    # baaki code...

    panel = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Broadcast",
                    callback_data="admin_broadcast"
                ),
                InlineKeyboardButton(
                    text="👥 Users",
                    callback_data="admin_users"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Bot Stats",
                    callback_data="admin_stats"
                ),
                InlineKeyboardButton(
                    text="⚡ Status",
                    callback_data="admin_status"
                )
            ]
        ]
    )

    await msg.answer(
        "👑 Owner Control Panel",
        reply_markup=panel
    )


# 🔹 ADMIN USERS
@dp.callback_query(lambda c: c.data == "admin_users")
async def admin_users(callback: CallbackQuery):

    users = len(get_all_users())

    await callback.message.answer(
        f"👥 Total Saved Users:\n\n{users}"
    )

    await callback.answer()


# 🔹 ADMIN STATUS
@dp.callback_query(lambda c: c.data == "admin_status")
async def admin_status(callback: CallbackQuery):

    text = (
        "⚡ Bot Status\n\n"
        "🟢 Online\n"
        "🔥 MongoDB Connected\n"
        "🌐 Render Active"
    )

    await callback.message.answer(text)

    await callback.answer()


# 🔹 ADMIN STATS
@dp.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):

    users = len(get_all_users())

    text = (
        "📊 Advanced Bot Statistics\n\n"
        f"👥 Total Users: {users}\n"
        "⚡ System: Active\n"
        "🧹 Cleaner: Running\n"
        "🌐 Database: Connected"
    )

    await callback.message.answer(text)

    await callback.answer()


# 🔹 ADMIN BROADCAST BUTTON
@dp.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):

    if callback.from_user.id != OWNER_ID:
        return

    broadcast_mode.add(callback.from_user.id)

    await callback.message.answer(
        "📢 Send the message you want to broadcast."
    )

    await callback.answer()


# 🔹 UNKNOWN COMMAND
@dp.message(F.text)
async def unknown(msg: types.Message):

    # ========== ADMIN CALL SYSTEM ==========
    if msg.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:

        if msg.text and msg.text.strip().lower() == "@admin":

            try:
                admins = await bot.get_chat_administrators(msg.chat.id)

                admin_users = [
                    admin.user for admin in admins
                    if not admin.user.is_bot
                ]

                user_mention = msg.from_user.mention_html(msg.from_user.full_name)

                for i in range(0, len(admin_users), 4):

                    chunk = admin_users[i:i+4]

                    mentions = " • ".join(
                        user.mention_html(user.full_name)
                        for user in chunk
                    )

                    await msg.reply(
                        f"<b>{user_mention} needs assistance.</b>\n"
                        f"Please check the replied message.\n\n"
                        f"{mentions}",
                        parse_mode="HTML"
                    )

            except Exception as e:
                print(f"Admin call error: {e}")

        return

    # ========== PRIVATE UNKNOWN COMMAND ==========
    if msg.text and msg.text.startswith("/"):

        known_commands = [
            "/start",
            "/settag",
            "/removetag",
            "/remove",
            "/removesetwords",
            "/exportdata",
            "/uploaddata",
            "/upload",
            "/broadcast",
            "/panel",
            "/p",
            "/poster",
            "/settings",
]

        command = msg.text.split()[0].lower()

        if command not in known_commands:
            await msg.reply(
                f"Unknown command.\nContact: {DEV_CONTACT}"
            )


# 🔹 RUN
async def main():

    Thread(target=run_web).start()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
