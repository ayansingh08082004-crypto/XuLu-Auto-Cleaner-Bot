import re


def clean_text(
    text,
    words=None,
    tag="",
    settings=None,
    add_branding=True
):

    if text is None:
        text = ""

    if words is None:
        words = []

    # DEFAULT SETTINGS
    if settings is None:
        settings = {
            "cleaner": True,
            "links": True,
            "tags": True,
            "hashtags": True
        }

    cleaned = text

    # 🔥 CLEANER MASTER SWITCH
    if settings.get("cleaner", True):

        # 🔗 REMOVE LINKS
        if settings.get("links", True):
            cleaned = re.sub(
                r'https?://\S+|www\.\S+',
                '',
                cleaned
            )

        # @️⃣ REMOVE TAGS
        if settings.get("tags", True):
            cleaned = re.sub(
                r'@\w+',
                '',
                cleaned
            )

        # #️⃣ REMOVE HASHTAGS
        if settings.get("hashtags", True):
            cleaned = re.sub(
                r'#\w+',
                '',
                cleaned
            )

        # 🧹 REMOVE CUSTOM WORDS
        for w in words:

            w = w.strip()

            if w:

                pattern = re.compile(
                    re.escape(w),
                    re.IGNORECASE
                )

                cleaned = pattern.sub(
                    '',
                    cleaned
                )

    # ✨ CLEAN EXTRA SPACES
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)

    cleaned = re.sub(r' +', ' ', cleaned)

    cleaned = cleaned.strip()

    # 🏷 ADD BRANDING
    if add_branding and tag:
        cleaned += f"\n\n{tag}"

    return cleaned
