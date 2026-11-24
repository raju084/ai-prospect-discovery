from typing import List
from app.platforms.base import BasePlatform
from app.schemas import PlatformProfile, QueryIntent
from app.services.search_service import search_service
from app.utils.normalizers import normalize_name, normalize_url, normalize_whatsapp_link


class WhatsAppPlatform(BasePlatform):
    platform_name: str = "WhatsApp"

    async def discover(self, search_query: str, intent: QueryIntent) -> List[PlatformProfile]:
        results = await search_service.search(search_query, platform_filter="WhatsApp", max_results=5)
        profiles = []

        for r in results:
            url = normalize_url(r.get("link", ""))
            title = r.get("title", "")
            snippet = r.get("snippet", "")

            name = normalize_name(title)
            if not name:
                continue

            contacts = self.extract_contacts(f"{url} {snippet}")
            # Ensure at least one whatsapp link exists
            wa_link = normalize_whatsapp_link(url)
            if wa_link and wa_link not in contacts["whatsapp_links"]:
                contacts["whatsapp_links"].append(wa_link)

            if contacts["whatsapp_links"] or contacts["phones"]:
                primary_link = contacts["whatsapp_links"][0] if contacts["whatsapp_links"] else url
                profiles.append(
                    PlatformProfile(
                        platform=self.platform_name,
                        profile_url=primary_link,
                        name=name,
                        bio=snippet,
                        snippet=snippet,
                        location=intent.location.to_formatted_string(),
                        emails=contacts["emails"],
                        phones=contacts["phones"],
                        whatsapp_links=contacts["whatsapp_links"]
                    )
                )

        return profiles
