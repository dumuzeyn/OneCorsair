"""Recognize shared media links without a site picker or network requests."""

import re
from urllib.parse import urlsplit, urlunsplit


SOURCE_DOMAINS = {
    "YouTube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "TikTok": ("tiktok.com", "tiktokv.com"),
    "Instagram": ("instagram.com",),
    "Likee": ("likee.video", "like.video"),
}
SOURCE_HOME = {
    "YouTube": "https://www.youtube.com/",
    "TikTok": "https://www.tiktok.com/",
    "Instagram": "https://www.instagram.com/",
    "Likee": "https://likee.video/",
}
LINK_PATTERN = re.compile(
    r'''(?ix)(?:https?://|(?<![\w@])(?:[a-z0-9-]+\.)*
    (?:youtube\.com|youtu\.be|youtube-nocookie\.com|tiktok\.com|tiktokv\.com|
       instagram\.com|likee\.video|like\.video)/)[^\s<>"',;，]+''')


def detect_source(url):
    try:
        host = (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower()
    except ValueError:
        return None
    for source, domains in SOURCE_DOMAINS.items():
        if any(host == domain or host.endswith("." + domain) for domain in domains):
            return source
    return None


def normalize_media_url(url):
    url = url.strip()
    if "://" not in url and detect_source(url):
        url = "https://" + url
    parsed = urlsplit(url)
    # TikTok's direct-video extractor expects www; keep vm/vt short links intact
    # so the engine can resolve their redirects using the same cookie settings.
    if parsed.hostname in ("tiktok.com", "m.tiktok.com"):
        url = urlunsplit((parsed.scheme, "www.tiktok.com", parsed.path, parsed.query, parsed.fragment))
    elif detect_source(url) == "Likee" and re.fullmatch(r"/@[^/]+/?", parsed.path):
        # Likee's profile matcher treats a trailing query as part of the username.
        # Profile identity is the path; share/marketing parameters are not needed.
        url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return url


def extract_media_links(text):
    return [normalize_media_url(match.group(0).rstrip(").]}>\"'!?.,;»"))
            for match in LINK_PATTERN.finditer(text)]
