from typing import List
from app.platforms.base import BasePlatform
from app.schemas import PlatformProfile, QueryIntent
from app.services.search_service import search_service
from app.utils.validators import is_valid_platform_profile_url
from app.utils.normalizers import normalize_name, normalize_url


class XPlatform(BasePlatform):
    platform_name: str = "X"

    async def discover(self, search_query: str, intent: QueryIntent) -> List[PlatformProfile]:
        results = await search_service.search(search_query, platform_filter="X", max_results=5)
        profiles = []

        for r in results:
            url = normalize_url(r.get("link", ""))
            title = r.get("title", "")
            snippet = r.get("snippet", "")

            if not is_valid_platform_profile_url("X", url):
                continue

            name = normalize_name(title)
            if not name:
                continue

            contacts = self.extract_contacts(snippet)
            profiles.append(
                PlatformProfile(
                    platform=self.platform_name,
                    profile_url=url,
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
