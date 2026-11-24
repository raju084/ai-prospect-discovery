from abc import ABC, abstractmethod
from typing import List, Optional
import re
from app.schemas import PlatformProfile, QueryIntent
from app.services.search_service import search_service
from app.utils.validators import is_valid_platform_profile_url, is_valid_email, is_valid_phone, EMAIL_REGEX, PHONE_REGEX
from app.utils.normalizers import normalize_name, normalize_url, normalize_whatsapp_link


class BasePlatform(ABC):
    """
    Abstract base class for all prospect discovery platforms.
    """
    platform_name: str = "Base"

    @abstractmethod
    async def discover(self, search_query: str, intent: QueryIntent) -> List[PlatformProfile]:
        """
        Executes discovery on the platform and returns structured profile objects.
        """
        pass

    def extract_contacts(self, text: str) -> dict:
        """
        Extracts verified emails, phones, and WhatsApp links from raw text or snippets.
        """
        contacts = {"emails": [], "phones": [], "whatsapp_links": []}
        if not text:
            return contacts

        # Emails
        found_emails = EMAIL_REGEX.findall(text)
        for em in found_emails:
            if is_valid_email(em) and em not in contacts["emails"]:
                contacts["emails"].append(em.lower())

        # Phones
        found_phones = PHONE_REGEX.findall(text)
        for ph in found_phones:
            if is_valid_phone(ph) and ph not in contacts["phones"]:
                contacts["phones"].append(ph.strip())

        # WhatsApp
        wa_matches = re.findall(r"(?:https?://wa\.me/\d+|https?://api\.whatsapp\.com/send\?phone=\d+|chat\.whatsapp\.com/[a-zA-Z0-9]+)", text)
        for wa in wa_matches:
            normalized_wa = normalize_whatsapp_link(wa)
            if normalized_wa and normalized_wa not in contacts["whatsapp_links"]:
                contacts["whatsapp_links"].append(normalized_wa)

        return contacts
