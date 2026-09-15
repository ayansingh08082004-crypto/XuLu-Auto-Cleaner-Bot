from pymongo import MongoClient
import os
from datetime import datetime, timezone


# =========================================================
# MONGODB CONNECTION
# =========================================================

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

db = client["xulu_bot"]

users_col = db["users"]
tags_col = db["tags"]
words_col = db["words"]
settings_col = db["settings"]

# =========================================================
# 👥 USERS SYSTEM
# =========================================================

def add_user(
    user_id,
    first_name=None,
    last_name=None,
    username=None,
    pm_started=False
):
    """
    Create or update a user.

    Existing MongoDB data is preserved.
    Nothing is deleted.
    """

    update_data = {
        "user_id": user_id,
        "updated_at": datetime.now(timezone.utc)
    }

    # Only update profile fields when values are available.
    if first_name is not None:
        update_data["first_name"] = first_name

    if last_name is not None:
        update_data["last_name"] = last_name

    if username is not None:
        update_data["username"] = username

    # This is ONLY set when the user actually interacts
    # with the bot in Private Message.
    if pm_started:
        update_data["pm_started"] = True

    users_col.update_one(
        {"user_id": user_id},
        {
            "$set": update_data
        },
        upsert=True
    )


def add_pm_user(
    user_id,
    first_name=None,
    last_name=None,
    username=None
):
    """
    Save/update a Telegram user who has interacted
    with the bot in Private Message.

    pm_started is permanently marked True after
    the user starts/interacts with the bot in PM.
    """

    add_user(
        user_id=user_id,
        first_name=first_name,
        last_name=last_name,
        username=username,
        pm_started=True
    )


def has_started_bot(user_id):
    """
    Check whether the user has started/interacted
    with the bot in Private Message.
    """

    user = users_col.find_one(
        {
            "user_id": user_id,
            "pm_started": True
        },
        {
            "_id": 1
        }
    )

    return user is not None


def get_user(user_id):
    """
    Get complete user information.
    """

    return users_col.find_one(
        {"user_id": user_id}
    )


def get_all_users():
    """
    Return all saved user IDs.

    Existing behavior is preserved.
    """

    users = users_col.find(
        {},
        {
            "user_id": 1
        }
    )

    return [
        user["user_id"]
        for user in users
        if "user_id" in user
    ]


# =========================================================
# 🏷 TAG SYSTEM
# =========================================================

def set_tag(user_id, tag):

    tags_col.update_one(
        {"user_id": user_id},
        {"$set": {"tag": tag}},
        upsert=True
    )


def get_tag(user_id):

    data = tags_col.find_one(
        {"user_id": user_id}
    )

    if data:
        return data.get("tag", "")

    return ""


def remove_tag(user_id):

    tags_col.delete_one(
        {"user_id": user_id}
    )


# =========================================================
# 🧹 REMOVE WORDS
# =========================================================

def add_word(user_id, word):

    data = words_col.find_one(
        {"user_id": user_id}
    )

    if data:
        words = data.get("words", [])
    else:
        words = []

    if word not in words:
        words.append(word)

    words_col.update_one(
        {"user_id": user_id},
        {"$set": {"words": words}},
        upsert=True
    )


def get_words(user_id):

    data = words_col.find_one(
        {"user_id": user_id}
    )

    if data:
        return data.get("words", [])

    return []


def delete_word(user_id, word):

    data = words_col.find_one(
        {"user_id": user_id}
    )

    if not data:
        return False

    words = data.get("words", [])

    if word in words:
        words.remove(word)

        words_col.update_one(
            {"user_id": user_id},
            {"$set": {"words": words}}
        )

        return True

    return False


# =========================================================
# ⚙️ SETTINGS SYSTEM
# =========================================================

def get_settings(user_id):

    data = settings_col.find_one(
        {"user_id": user_id}
    )

    # DEFAULT SETTINGS
    if not data:

        default_settings = {
            "user_id": user_id,
            "cleaner": True,
            "links": True,
            "tags": True,
            "hashtags": True,
            "caption_template": ""
        }

        settings_col.insert_one(
            default_settings
        )

        return default_settings

    return data


def toggle_setting(user_id, key):

    settings = get_settings(user_id)

    new_value = not settings.get(
        key,
        True
    )

    settings_col.update_one(
        {"user_id": user_id},
        {"$set": {key: new_value}}
    )

    return new_value

def get_caption_template(user_id):
    settings = get_settings(user_id)
    return settings.get("caption_template", "")


def set_caption_template(user_id, template):
    settings_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "caption_template": template
            }
        },
        upsert=True
    )


def remove_caption_template(user_id):
    settings_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "caption_template": ""
            }
        },
        upsert=True
    )

# =========================================================
# 📦 DATA EXPORT / IMPORT SYSTEM
# =========================================================

def export_remove_words(user_id):
    """
    Get Remove Words data for export.
    User profile information is NOT included.
    """

    words = get_words(user_id)

    return {
        "type": "remove_words",
        "version": 1,
        "words": words
    }


def export_tag(user_id):
    """
    Get Tag data for export.
    """

    tag = get_tag(user_id)

    return {
        "type": "tag",
        "version": 1,
        "tag": tag
    }


def export_settings(user_id):
    """
    Get Settings data for export.
    """

    settings = get_settings(user_id)

    return {
        "type": "settings",
        "version": 1,
        "cleaner": settings.get("cleaner", True),
        "links": settings.get("links", True),
        "tags": settings.get("tags", True),
        "hashtags": settings.get("hashtags", True)
    }


# =========================================================
# 📥 IMPORT REMOVE WORDS
# =========================================================

def import_remove_words(user_id, words):
    """
    Import Remove Words into the CURRENT user's account.

    Existing words are preserved.
    Duplicate words are ignored.
    """

    if not isinstance(words, list):
        return False

    existing_words = get_words(user_id)

    if not isinstance(existing_words, list):
        existing_words = []

    for word in words:

        if not isinstance(word, str):
            continue

        word = word.strip()

        if not word:
            continue

        if word not in existing_words:
            existing_words.append(word)

    words_col.update_one(
        {"user_id": user_id},
        {
            "$set": {
                "words": existing_words
            }
        },
        upsert=True
    )

    return True


# =========================================================
# 📥 IMPORT TAG
# =========================================================

def import_tag(user_id, tag):
    """
    Import Tag into the CURRENT user's account.
    """

    if not isinstance(tag, str):
        return False

    tag = tag.strip()

    if not tag:
        return False

    set_tag(
        user_id,
        tag
    )

    return True


# =========================================================
# 📥 IMPORT SETTINGS
# =========================================================

def import_settings(user_id, data):
    """
    Import supported Settings into the CURRENT user's account.

    Only known settings are accepted.
    """

    if not isinstance(data, dict):
        return False

    allowed_keys = (
        "cleaner",
        "links",
        "tags",
        "hashtags"
    )

    update_data = {}

    for key in allowed_keys:

        if key in data:

            value = data[key]

            if isinstance(value, bool):
                update_data[key] = value

    if not update_data:
        return False

    settings_col.update_one(
        {"user_id": user_id},
        {
            "$set": update_data
        },
        upsert=True
    )

    return True

# =========================================================
# 🧹 GROUP MESSAGE TRACKING
# =========================================================

group_messages_col = db["group_messages"]


def save_group_message(
    chat_id,
    user_id,
    message_id,
    created_at=None
):
    """
    Save one message reference for purge.
    Same message is stored only once.
    """

    if created_at is None:
        created_at = datetime.now(timezone.utc)

    group_messages_col.update_one(
        {
            "chat_id": chat_id,
            "message_id": message_id
        },
        {
            "$setOnInsert": {
                "chat_id": chat_id,
                "user_id": user_id,
                "message_id": message_id,
                "created_at": created_at
            }
        },
        upsert=True
    )


def get_user_group_messages(
    chat_id,
    user_id,
    since
):
    """
    Get user's messages from a group
    after the specified datetime.
    """

    return list(
        group_messages_col.find(
            {
                "chat_id": chat_id,
                "user_id": user_id,
                "created_at": {
                    "$gte": since
                }
            },
            {
                "_id": 0,
                "message_id": 1
            }
        )
    )


def delete_group_message_record(
    chat_id,
    user_id,
    message_ids
):
    """
    Remove deleted message records from MongoDB.
    """

    if not message_ids:
        return

    group_messages_col.delete_many(
        {
            "chat_id": chat_id,
            "user_id": user_id,
            "message_id": {
                "$in": message_ids
            }
        }
    )
