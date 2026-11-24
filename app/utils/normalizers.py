import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from typing import Optional


# Regex to strip platform suffixes and noise from title strings
TITLE_CLEANUP_REGEX = re.compile(
    r"\s*(?:[\|\-\–\—\•]\s*|\bon\s+)(LinkedIn|Facebook|Instagram|Twitter|X|YouTube|Threads|WhatsApp|TikTok|Pinterest|Official|Profile|Channel|Bio).*$",
    re.IGNORECASE
)

HANDLE_IN_PARENS_REGEX = re.compile(r"\s*\(@?[a-zA-Z0-9_.]+\)")
# Matches emojis, dingbats, miscellaneous symbols
SYMBOL_EMOJI_REGEX = re.compile(
    r"[\U00010000-\U0010ffff]|[\u2600-\u27ff]|[\u2300-\u23ff]|[\u2b00-\u2bff]|[\u200d\ufe0f]",
    flags=re.UNICODE
)


def normalize_name(raw_name: str) -> str:
    """
    Cleans raw page titles, usernames, or snippet headers into a clean human/business name.
    e.g. 'John Smith | LinkedIn' -> 'John Smith'
    e.g. 'Elena Rostova (@elena_dc) on Threads' -> 'Elena Rostova'
    e.g. 'David Alpert - Managing Partner' -> 'David Alpert'
    """
    if not raw_name or not isinstance(raw_name, str):
        return ""

    # Remove emojis and symbols
    cleaned = SYMBOL_EMOJI_REGEX.sub("", raw_name)

    # Strip platform title suffixes
    cleaned = TITLE_CLEANUP_REGEX.sub("", cleaned)
    # Strip handles in parentheses
    cleaned = HANDLE_IN_PARENS_REGEX.sub("", cleaned)

    # Strip title/role separator if present (e.g. "Name - Title")
    if " - " in cleaned:
        cleaned = cleaned.split(" - ")[0].strip()

    # Remove extra quotes, brackets
    cleaned = re.sub(r'["\']', "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # If format is "Lastname, Firstname", convert to "Firstname Lastname"
    if "," in cleaned and len(cleaned.split(",")) == 2:
        parts = [p.strip() for p in cleaned.split(",")]
        if all(part.isalpha() for part in parts):
            cleaned = f"{parts[1]} {parts[0]}"

    return cleaned.strip()


def normalize_url(url: str) -> str:
    """
    Normalizes profile URLs by removing tracking query parameters (utm_*, ref, etc.)
    and stripping trailing slashes.
    """
    if not url or not isinstance(url, str):
        return ""

    url = url.strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        if url.startswith("mailto:") or url.startswith("tel:"):
            return url
        url = "https://" + url

    try:
        parsed = urlparse(url)
        clean_scheme = "https" if parsed.scheme in ("http", "https") else parsed.scheme
        path = parsed.path.rstrip("/")

        # Keep only essential query parameters if any
        if parsed.query:
            query_params = parse_qs(parsed.query)
            filtered_params = {
                k: v for k, v in query_params.items()
                if not k.startswith("utm_") and k not in ("ref", "fbclid", "gclid", "source")
            }
            new_query = urlencode(filtered_params, doseq=True) if filtered_params else ""
        else:
            new_query = ""

        normalized = urlunparse((clean_scheme, parsed.netloc.lower(), path, "", new_query, ""))
        return normalized
    except Exception:
        return url


def normalize_whatsapp_link(raw_contact: str) -> Optional[str]:
    """
    Normalizes phone numbers or WhatsApp chat strings into a standardized https://wa.me/<digits> link.
    """
    if not raw_contact:
        return None

    raw_contact = raw_contact.strip()
    if "chat.whatsapp.com/" in raw_contact:
        return normalize_url(raw_contact)

    # Extract clean digits
    digits = re.sub(r"\D", "", raw_contact)
    if 7 <= len(digits) <= 15:
        return f"https://wa.me/{digits}"
    return None


def normalize_location(city: Optional[str] = None, state: Optional[str] = None, country: Optional[str] = None) -> str:
    """Format geographical entities consistently as 'City, State, Country'."""
    elements = []
    if city and city.strip():
        elements.append(city.strip().title())
    if state and state.strip():
        elements.append(state.strip().title())
    if country and country.strip():
        elements.append(country.strip().upper() if len(country.strip()) <= 3 else country.strip().title())

    return ", ".join(elements)
