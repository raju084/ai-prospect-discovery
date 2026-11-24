import re
from urllib.parse import urlparse
from typing import Optional


EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

PHONE_REGEX = re.compile(
    r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}"
)

# Common generic / blacklisted domains and placeholders
BLACKLISTED_EMAILS = {
    "example@example.com", "user@domain.com", "email@example.com",
    "info@example.com", "name@email.com", "test@test.com",
    "noreply@linkedin.com", "support@facebook.com", "contact@domain.com"
}

GENERIC_PLATFORM_PATHS = {
    "linkedin": ["/login", "/feed", "/signup", "/jobs", "/company", "/pulse", "/help", "/about"],
    "instagram": ["/explore", "/accounts", "/developer", "/about", "/terms", "/privacy", "/p/"],
    "facebook": ["/login", "/recover", "/pages", "/groups", "/events", "/policies", "/help"],
    "x": ["/home", "/explore", "/notifications", "/messages", "/i/", "/settings", "/privacy"],
    "youtube": ["/watch", "/feed", "/playlist", "/premium", "/gaming", "/trends"],
    "threads": ["/terms", "/privacy"]
}


def is_valid_url(url: str) -> bool:
    """Check if string is a valid HTTP/HTTPS URL."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def is_valid_email(email: str) -> bool:
    """Validate email address format and filter out placeholders/blacklisted emails."""
    if not email or not isinstance(email, str):
        return False
    email_clean = email.strip().lower()
    if email_clean in BLACKLISTED_EMAILS:
        return False
    if len(email_clean) > 254:
        return False
    if email_clean.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
        return False
    return bool(EMAIL_REGEX.fullmatch(email_clean))


def is_valid_phone(phone: str) -> bool:
    """Validate phone number ensuring appropriate length and format."""
    if not phone or not isinstance(phone, str):
        return False
    clean = re.sub(r"[^\d+]", "", phone.strip())
    # Valid phone numbers usually have between 7 and 15 digits
    digits = re.sub(r"\D", "", clean)
    return 7 <= len(digits) <= 15


def is_valid_platform_profile_url(platform: str, url: str) -> bool:
    """
    Ensure the URL matches a valid individual or creator profile URL
    for the specified platform, filtering out search, login, explore, or generic pages.
    """
    if not is_valid_url(url):
        return False

    platform_lower = platform.lower()
    parsed = urlparse(url.lower().strip())
    netloc = parsed.netloc
    path = parsed.path.rstrip("/")

    # Check blacklist paths
    for p_key, paths in GENERIC_PLATFORM_PATHS.items():
        if p_key in platform_lower or p_key in netloc:
            for bad_path in paths:
                if path.startswith(bad_path) or path == bad_path:
                    return False

    if platform_lower in ("linkedin", "linkedin.com"):
        if "linkedin.com" in netloc:
            return path.startswith("/in/") and len(path) > 4
        return False

    elif platform_lower in ("x", "twitter"):
        if "twitter.com" in netloc or "x.com" in netloc:
            segments = [s for s in path.split("/") if s]
            return len(segments) == 1 and segments[0] not in GENERIC_PLATFORM_PATHS["x"]
        return False

    elif platform_lower in ("instagram", "instagram.com"):
        if "instagram.com" in netloc:
            segments = [s for s in path.split("/") if s]
            return len(segments) == 1 and segments[0] not in GENERIC_PLATFORM_PATHS["instagram"]
        return False

    elif platform_lower in ("youtube", "youtube.com"):
        if "youtube.com" in netloc or "youtu.be" in netloc:
            return any(path.startswith(prefix) for prefix in ["/@", "/channel/", "/c/", "/user/"])
        return False

    elif platform_lower in ("facebook", "facebook.com"):
        if "facebook.com" in netloc:
            segments = [s for s in path.split("/") if s]
            return len(segments) >= 1 and segments[0] not in GENERIC_PLATFORM_PATHS["facebook"]
        return False

    elif platform_lower in ("threads", "threads.net"):
        if "threads.net" in netloc:
            return path.startswith("/@") and len(path) > 2
        return False

    elif platform_lower in ("whatsapp", "wa.me"):
        if "wa.me" in netloc or "api.whatsapp.com" in netloc or "chat.whatsapp.com" in netloc:
            return len(path) > 1
        return False

    return True
