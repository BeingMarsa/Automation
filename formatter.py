"""Caption and title formatter for Instagram Reels.

Takes YouTube video title and description and creates an optimized, engaging
Instagram caption adhering to Instagram length constraints and conventions.
"""

from __future__ import annotations

import re
from config import config

# Common YouTube-specific patterns to clean up if CLEAN_YOUTUBE_LINKS is enabled
YT_CLEANUP_PATTERNS = [
    r"(?i)subscribe\s+(to\s+the\s+channel|for\s+more|now)[^\n]*",
    r"(?i)hit\s+the\s+(bell\s+icon|like\s+button)[^\n]*",
    r"(?i)don'?t\s+forget\s+to\s+subscribe[^\n]*",
    r"(?i)link\s+in\s+the\s+description[^\n]*",
]


def clean_description(description: str) -> str:
    """Clean YouTube-specific calls to action from the description."""
    if not description:
        return ""

    cleaned = description
    for pattern in YT_CLEANUP_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned)

    # Normalize excessive blank lines (more than 2 consecutive newlines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_hashtags(text: str) -> list[str]:
    """Extract existing hashtags from text."""
    if not text:
        return []
    return re.findall(r"#\w+", text)


def format_caption(
    title: str,
    description: str = "",
    custom_hashtags: str | None = None,
    max_length: int | None = None,
    clean_yt_text: bool | None = None,
) -> str:
    """Format the YouTube title and description into an Instagram Reel caption.

    Structure:
    [Title]

    [Description (truncated if necessary)]

    [Hashtags]
    """
    max_len = max_length if max_length is not None else config.max_caption_length
    should_clean = clean_yt_text if clean_yt_text is not None else config.clean_youtube_links
    tags_to_add = custom_hashtags if custom_hashtags is not None else config.custom_hashtags

    title = (title or "").strip()
    raw_desc = (description or "").strip()

    if should_clean:
        desc = clean_description(raw_desc)
    else:
        desc = raw_desc

    # Extract any existing hashtags from title and description
    extracted = extract_hashtags(title) + extract_hashtags(desc)

    # Collect custom hashtags
    hashtags_list = []
    if tags_to_add:
        for tag in tags_to_add.split():
            clean_tag = tag if tag.startswith("#") else f"#{tag}"
            if clean_tag not in hashtags_list:
                hashtags_list.append(clean_tag)

    for tag in extracted:
        if tag not in hashtags_list:
            hashtags_list.append(tag)

    hashtags_str = " ".join(hashtags_list).strip()

    # Clean hashtags out of desc so they aren't repeated twice
    desc_cleaned_tags = re.sub(r"#\w+", "", desc)
    desc = re.sub(r"\n{3,}", "\n\n", desc_cleaned_tags).strip()

    parts = []
    if title:
        parts.append(title)

    # Check length remaining for description
    fixed_len = len(title) + (len(hashtags_str) + 2 if hashtags_str else 0) + 4  # padding for newlines
    available_desc_len = max_len - fixed_len

    if desc and available_desc_len > 30:
        if len(desc) > available_desc_len:
            # Truncate at nearest word boundary
            truncated = desc[: available_desc_len - 3]
            last_space = truncated.rfind(" ")
            if last_space > 0:
                truncated = truncated[:last_space]
            desc = truncated + "..."
        parts.append(desc)
    elif desc and available_desc_len <= 30:
        # Not enough space for description
        pass

    if hashtags_str:
        parts.append(hashtags_str)

    caption = "\n\n".join(parts)
    # Ensure hard limit is not exceeded
    if len(caption) > max_len:
        caption = caption[: max_len - 3] + "..."

    return caption.strip()
