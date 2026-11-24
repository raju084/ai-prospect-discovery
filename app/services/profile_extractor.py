import re
from typing import List, Dict, Any, Optional
from app.schemas import PlatformProfile
from app.utils.validators import is_valid_email, is_valid_phone, EMAIL_REGEX, PHONE_REGEX
from app.utils.normalizers import normalize_name, normalize_url, normalize_whatsapp_link


class ProfileExtractor:
    """
    Extracts deep metadata, cross-platform handles, and contact channels
    from web page content and search snippets.
    """

    HANDLE_PATTERNS = [
        re.compile(r"(?:twitter|x\.com|@)\s*[:=]?\s*@?([a-zA-Z0-9_]{3,20})", re.IGNORECASE),
        re.compile(r"(?:ig|instagram)\s*[:=]?\s*@?([a-zA-Z0-9_.-]{3,30})", re.IGNORECASE),
        re.compile(r"(?:linkedin\.com/in/|linkedin:?\s*)([a-zA-Z0-9_-]{3,50})", re.IGNORECASE),
    ]

    def extract_handles(self, text: str) -> List[str]:
        handles = []
        if not text:
            return handles
        for pattern in self.HANDLE_PATTERNS:
            matches = pattern.findall(text)
            for m in matches:
                clean = m.strip().lstrip("@")
                if clean and clean.lower() not in ("gmail", "yahoo", "outlook", "contact", "info"):
                    handles.append(clean.lower())
        return list(set(handles))

    def enrich_profile(self, profile: PlatformProfile, html_or_snippet: str) -> PlatformProfile:
        """
        Scans snippet or page text to extract additional contact signals and handles.
        """
        if not html_or_snippet:
            return profile

        # Extract emails
        emails = EMAIL_REGEX.findall(html_or_snippet)
        for e in emails:
            if is_valid_email(e) and e.lower() not in profile.emails:
                profile.emails.append(e.lower())

        # Extract phones
        phones = PHONE_REGEX.findall(html_or_snippet)
        for p in phones:
            if is_valid_phone(p) and p.strip() not in profile.phones:
                profile.phones.append(p.strip())

        # Extract WhatsApp links
        wa_matches = re.findall(r"(?:https?://wa\.me/\d+|chat\.whatsapp\.com/[a-zA-Z0-9]+)", html_or_snippet)
        for w in wa_matches:
            normalized_wa = normalize_whatsapp_link(w)
            if normalized_wa and normalized_wa not in profile.whatsapp_links:
                profile.whatsapp_links.append(normalized_wa)

        return profile


profile_extractor = ProfileExtractor()
