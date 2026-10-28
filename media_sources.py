"""Recognize shared media links without a site picker or network requests."""

import re
from urllib.parse import urlsplit, urlunsplit


SOURCE_DOMAINS = {
    "YouTube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "TikTok": ("tiktok.com", "tiktokv.com"),
    "Instagram": ("instagram.com",),
}
SOURCE_HOME = {
    "YouTube": "https://www.youtube.com/",
    "TikTok": "https://www.tiktok.com/",
    "Instagram": "https://www.instagram.com/",
}
LINK_PATTERN = re.compile(
    r'''(?ix)(?:https?://|(?<![\w@])(?:[a-z0-9-]+\.)*
    (?:youtube\.com|youtu\.be|youtube-nocookie\.com|tiktok\.com|tiktokv\.com|
       instagram\.com)/)[^\s<>"',;，]+''')


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
    return url


def is_supported_url(url):
    """Restrict remote media to the advertised services; allow local fixtures."""
    try:
        parsed = urlsplit(url)
        return parsed.scheme.lower() in ("http", "https") and (
            detect_source(url) is not None or parsed.hostname in ("localhost", "127.0.0.1", "::1"))
    except ValueError:
        return False


def extract_media_links(text):
    return [normalize_media_url(match.group(0).rstrip(").]}>\"'!?.,;»"))
            for match in LINK_PATTERN.finditer(text)]
