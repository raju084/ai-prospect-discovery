from typing import List
from app.platforms.base import BasePlatform
from app.schemas import PlatformProfile, QueryIntent
from app.services.search_service import search_service
from app.utils.validators import is_valid_platform_profile_url
from app.utils.normalizers import normalize_name, normalize_url


class GooglePlatform(BasePlatform):
    """
    Google is a discovery/search source. The final prospect records should contain
    relevant individual or business profiles, not generic search-result URLs.
    """
    platform_name: str = "Google"

    async def discover(self, search_query: str, intent: QueryIntent) -> List[PlatformProfile]:
        # Google search for publicly indexed profiles and personal websites
        query = f'"{intent.interest}" "{intent.audience}" "{intent.location.to_formatted_string()}" profile OR portfolio OR about'
        results = await search_service.search(query, platform_filter=None, max_results=5)

        profiles = []
        for r in results:
            url = normalize_url(r.get("link", ""))
            title = r.get("title", "")
            snippet = r.get("snippet", "")

            # Filter out non-profile search aggregators
            if any(agg in url for agg in ["wikipedia.org", "tripadvisor.com", "yelp.com", "yellowpages.com"]):
                continue

            name = normalize_name(title)
            if not name or len(name) < 2:
                continue

            contacts = self.extract_contacts(f"{title} {snippet}")

            # Identify if the result is actually a social profile
            identified_platform = "Google"
            for plat_name, domain in [
                ("LinkedIn", "linkedin.com/in/"),
                ("X", "x.com/"),
                ("Instagram", "instagram.com/"),
                ("YouTube", "youtube.com/"),
                ("Facebook", "facebook.com/"),
                ("Threads", "threads.net/"),
            ]:
                if domain in url:
                    identified_platform = plat_name
                    break

            profiles.append(
                PlatformProfile(
                    platform=identified_platform,
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
