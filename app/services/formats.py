"""Output frame sizes and the social platforms each one targets."""

# Every vertical platform shares one 1080x1920 file, so we render per aspect, not per platform.
ASPECT_SIZES = {
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}

PLATFORMS = [
    {"id": "tiktok", "label": "TikTok", "aspect": "9:16", "max_sec": 600},
    {"id": "youtube_shorts", "label": "YouTube Shorts", "aspect": "9:16", "max_sec": 180},
    {"id": "reels", "label": "Reels Facebook/Instagram", "aspect": "9:16", "max_sec": 180},
    {"id": "youtube", "label": "YouTube / Facebook ngang", "aspect": "16:9", "max_sec": None},
    {"id": "square", "label": "Bài đăng vuông", "aspect": "1:1", "max_sec": None},
    {"id": "feed_portrait", "label": "Bài đăng dọc Instagram/Facebook", "aspect": "4:5", "max_sec": None},
]


def output_size(aspect, source_width=None, source_height=None):
    if aspect == "source":
        return source_width, source_height
    return ASPECT_SIZES[aspect]


def aspect_ratio(aspect):
    width, height = ASPECT_SIZES[aspect]
    return width / height


def aspect_tag(aspect):
    return "src" if aspect == "source" else aspect.replace(":", "x")


def platforms_for(aspect):
    return [p["label"] for p in PLATFORMS if p["aspect"] == aspect]


def caption_margin(aspect):
    # TikTok, Shorts and Reels cover roughly the bottom 35% of a vertical frame with UI.
    return 0.35 if aspect == "9:16" else 0.08
