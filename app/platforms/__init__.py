from typing import Dict
from app.platforms.base import BasePlatform
from app.platforms.google import GooglePlatform
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.facebook import FacebookPlatform
from app.platforms.instagram import InstagramPlatform
from app.platforms.x_platform import XPlatform
from app.platforms.youtube import YouTubePlatform
from app.platforms.whatsapp import WhatsAppPlatform
from app.platforms.threads import ThreadsPlatform

# Registry of supported platforms
PLATFORM_REGISTRY: Dict[str, BasePlatform] = {
    "google": GooglePlatform(),
    "linkedin": LinkedInPlatform(),
    "facebook": FacebookPlatform(),
    "instagram": InstagramPlatform(),
    "x": XPlatform(),
    "youtube": YouTubePlatform(),
    "whatsapp": WhatsAppPlatform(),
    "threads": ThreadsPlatform(),
}

__all__ = [
    "BasePlatform",
    "GooglePlatform",
    "LinkedInPlatform",
    "FacebookPlatform",
    "InstagramPlatform",
    "XPlatform",
    "YouTubePlatform",
    "WhatsAppPlatform",
    "ThreadsPlatform",
    "PLATFORM_REGISTRY",
]
