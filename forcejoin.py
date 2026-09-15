import os

from aiogram import Bot, types
from aiogram.enums import ChatType
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import has_started_bot


# =========================================================
# FORCE JOIN CHANNELS
# =========================================================

FORCE_CHANNELS = [
    ch.strip()
    for ch in os.getenv("FORCE_CHANNELS", "").split(",")
    if ch.strip()
]


# =========================================================
# GET MISSING CHANNELS
# =========================================================

async def get_missing_channels(bot: Bot, user_id: int):
    """
    Return only the channels that the user has not joined.
    """

    missing = []

    for channel in FORCE_CHANNELS:

        try:
            member = await bot.get_chat_member(
                chat_id=channel,
                user_id=user_id
            )

            # User is considered joined in these states.
            if member.status not in (
                "member",
                "administrator",
                "creator",
                "restricted",
            ):
                missing.append(channel)

        except Exception as e:
            print(
                f"[FORCE JOIN] Membership check failed "
                f"for {channel}: {e}"
            )

            # If Telegram cannot verify the membership,
            # fail safely and require the user to join.
            missing.append(channel)

    return missing


# =========================================================
# GET CHANNEL TITLE
# =========================================================

async def get_channel_title(
    bot: Bot,
    channel: str
):
    """
    Get the actual Telegram channel title.

    Example:
        @MyChannel
    becomes:
        My Channel
    """

    try:

        chat = await bot.get_chat(
            chat_id=channel
        )

        if chat.title:
            return chat.title

    except Exception as e:

        print(
            f"[FORCE JOIN] Unable to get title "
            f"for {channel}: {e}"
        )

    # Fallback
    return channel.replace("@", "").strip()


# =========================================================
# BUILD DM FORCE JOIN KEYBOARD
# =========================================================

async def build_force_join_keyboard(
    bot: Bot,
    missing_channels
):
    """
    Build Force Join buttons for Private Chat.

    Button text uses the actual channel title,
    not the @username.
    """

    buttons = []

    for channel in missing_channels[:10]:

        channel_name = await get_channel_title(
            bot,
            channel
        )

        username = channel.replace(
            "@",
            ""
        ).strip()

        buttons.append([
            InlineKeyboardButton(
                text=f"➕ Join - {channel_name}",
                url=f"https://t.me/{username}"
            )
        ])

    # Verify button
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Verify Membership",
            callback_data="forcejoin_verify"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================================================
# BUILD GROUP FORCE JOIN KEYBOARD
# =========================================================

async def build_group_force_join_keyboard(
    bot: Bot,
    missing_channels
):
    """
    Build the Force Join buttons shown after
    pressing '🔗 Force Join' inside a group.
    """

    buttons = []

    for channel in missing_channels[:10]:

        channel_name = await get_channel_title(
            bot,
            channel
        )

        username = channel.replace(
            "@",
            ""
        ).strip()

        buttons.append([
            InlineKeyboardButton(
                text=f"➕ Join - {channel_name}",
                url=f"https://t.me/{username}"
            )
        ])

    # Verify button
    buttons.append([
        InlineKeyboardButton(
            text="🔄 Verify Membership",
            callback_data="forcejoin_verify"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# =========================================================
# SEND PRIVATE FORCE JOIN MESSAGE
# =========================================================

async def send_force_join(
    bot: Bot,
    message: types.Message,
    missing_channels=None
):
    """
    Send Force Join message in Private Chat.
    """

    user_id = message.from_user.id

    if missing_channels is None:

        missing_channels = await get_missing_channels(
            bot,
            user_id
        )

    # User has joined everything
    if not missing_channels:
        return True

    keyboard = await build_force_join_keyboard(
        bot,
        missing_channels
    )

    count = len(missing_channels)

    channel_word = (
        "channel"
        if count == 1
        else "channels"
    )

    text = (
        "⚠️ <b>Join Required</b>\n\n"
        f"You need to join <b>{count} {channel_word}</b> "
        "before using this bot.\n\n"
        "Join all required channels below, "
        "then tap <b>Verify Membership</b>.\n\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🔒 Your access will be checked automatically."
    )

    await message.reply(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

    return False


# =========================================================
# PRIVATE ACCESS CHECK
# =========================================================

async def private_check(
    bot: Bot,
    message: types.Message
):

    # Only run this check in PM.
    if message.chat.type != ChatType.PRIVATE:
        return True

    missing = await get_missing_channels(
        bot,
        message.from_user.id
    )

    # Everything is joined.
    if not missing:
        return True

    # User is missing one or more channels.
    await send_force_join(
        bot,
        message,
        missing
    )

    return False


# =========================================================
# GROUP ACCESS CHECK
# =========================================================

async def group_check(
    bot: Bot,
    message: types.Message
):

    # Ignore groups other than Group/Supergroup.
    if message.chat.type not in (
        ChatType.GROUP,
        ChatType.SUPERGROUP
    ):
        return True

    user_id = message.from_user.id

    # =====================================================
    # STEP 1
    # USER MUST HAVE STARTED BOT IN PM
    # =====================================================

    if not has_started_bot(user_id):

        me = await bot.get_me()

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🚀 Start Bot in PM",
                        url=(
                            f"https://t.me/"
                            f"{me.username}"
                            f"?start=group_access"
                        )
                    )
                ]
            ]
        )

        await message.reply(
            "⚠️ <b>Start the bot in Private Message first.</b>\n\n"
            "Tap the button below to open the bot in PM.",
            parse_mode="HTML",
            reply_markup=keyboard
        )

        return False

    # =====================================================
    # STEP 2
    # PM STARTED → CHECK CHANNEL MEMBERSHIP
    # =====================================================

    missing = await get_missing_channels(
        bot,
        user_id
    )

    # User has joined everything.
    if not missing:
        return True

    # =====================================================
    # STEP 3
    # PM STARTED BUT CHANNELS ARE MISSING
    # =====================================================

    me = await bot.get_me()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Start Bot in PM",
                    url=(
                        f"https://t.me/"
                        f"{me.username}"
                        f"?start=group_access"
                    )
                ),
                InlineKeyboardButton(
                    text="🔗 Join Channels",
                    callback_data="group_forcejoin"
                )
            ]
        ]
    )

    await message.reply(
        "⚠️ <b>Channel Membership Required</b>\n\n"
        "You have started the bot in PM, but you haven't "
        "joined all required channels yet.\n\n"
        "Use <b>Join Channels</b> below to see the required "
        "channels.",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    return False


# =========================================================
# CENTRAL ACCESS CHECK
# =========================================================

async def check_access(
    bot: Bot,
    message: types.Message
):
    """
    Central access-control function.

    PRIVATE:
        Force Join check.

    GROUP:
        PM-start check + channel membership check.
    """

    # -----------------------------------------------------
    # GROUP / SUPERGROUP
    # -----------------------------------------------------

    if not await group_check(
        bot,
        message
    ):
        return False

    # -----------------------------------------------------
    # PRIVATE CHAT
    # -----------------------------------------------------

    if message.chat.type == ChatType.PRIVATE:

        if not await private_check(
            bot,
            message
        ):
            return False

    # -----------------------------------------------------
    # ACCESS GRANTED
    # -----------------------------------------------------

    return True
