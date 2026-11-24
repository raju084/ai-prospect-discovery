import logging
from typing import List, Dict, Optional
from difflib import SequenceMatcher
from app.schemas import PlatformProfile, ProspectItem, SocialLinkItem
from app.utils.validators import is_valid_url
from app.utils.normalizers import normalize_name, normalize_url

logger = logging.getLogger(__name__)


class DeduplicationService:
    """
    Consolidates multiple profiles belonging to the same individual
    into a single unified prospect record.
    Matches across identity signals:
      - Exact and high-confidence normalized full name
      - Common verified email address (deterministic)
      - Common phone number or WhatsApp handle (deterministic)
      - Location affinity check to prevent merging false homonyms.
    """

    def consolidate(self, profiles: List[PlatformProfile]) -> List[ProspectItem]:
        if not profiles:
            return []

        clusters: List[List[PlatformProfile]] = []

        for profile in profiles:
            merged = False
            for cluster in clusters:
                if self._is_same_entity(profile, cluster):
                    cluster.append(profile)
                    merged = True
                    break

            if not merged:
                clusters.append([profile])

        # Convert clusters to unified ProspectItem records
        prospects: List[ProspectItem] = []
        for cluster in clusters:
            prospect = self._build_prospect_from_cluster(cluster)
            if prospect:
                prospects.append(prospect)

        return prospects

    def _is_same_entity(self, candidate: PlatformProfile, cluster: List[PlatformProfile]) -> bool:
        """
        Determines whether candidate profile belongs to the existing cluster.
        """
        cand_name = normalize_name(candidate.name).lower()
        if not cand_name:
            return False

        for existing in cluster:
            exist_name = normalize_name(existing.name).lower()

            # 1. Deterministic Match: Common email
            common_emails = set(candidate.emails).intersection(set(existing.emails))
            if common_emails:
                return True

            # 2. Deterministic Match: Common phone or WhatsApp
            common_phones = set(candidate.phones).intersection(set(existing.phones))
            if common_phones:
                return True
            common_wa = set(candidate.whatsapp_links).intersection(set(existing.whatsapp_links))
            if common_wa:
                return True

            # 3. High-Confidence Name Match
            name_sim = SequenceMatcher(None, cand_name, exist_name).ratio()
            if name_sim >= 0.88 or cand_name == exist_name:
                # Check location compatibility
                if self._are_locations_compatible(candidate.location, existing.location):
                    return True

        return False

    def _are_locations_compatible(self, loc1: Optional[str], loc2: Optional[str]) -> bool:
        if not loc1 or not loc2:
            return True  # If either is absent, permit clustering based on name/contacts
        l1, l2 = loc1.lower(), loc2.lower()
        words1 = set(l1.replace(",", " ").split())
        words2 = set(l2.replace(",", " ").split())
        return bool(words1.intersection(words2))

    def _build_prospect_from_cluster(self, cluster: List[PlatformProfile]) -> Optional[ProspectItem]:
        if not cluster:
            return None

        # Choose best name (cleanest, longest)
        names = [p.name for p in cluster if p.name]
        best_name = max(names, key=len) if names else "Unknown Prospect"
        best_name = normalize_name(best_name)

        # Consolidate location
        locations = [p.location for p in cluster if p.location]
        best_location = locations[0] if locations else None

        # Consolidate social links
        social_links_map: Dict[str, str] = {}
        all_emails: List[str] = []
        all_phones: List[str] = []
        all_wa_links: List[str] = []

        for p in cluster:
            plat = p.platform
            # If platform is Google, don't output generic google search as social link
            if plat != "Google" and p.profile_url and is_valid_url(p.profile_url):
                if plat not in social_links_map:
                    social_links_map[plat] = normalize_url(p.profile_url)

            # Collect contacts
            for em in p.emails:
                if em not in all_emails:
                    all_emails.append(em)
            for ph in p.phones:
                if ph not in all_phones:
                    all_phones.append(ph)
            for wa in p.whatsapp_links:
                if wa not in all_wa_links:
                    all_wa_links.append(wa)

        social_links: List[SocialLinkItem] = [
            SocialLinkItem(platform=plat, link=link)
            for plat, link in social_links_map.items()
        ]

        # Add Email to social_link array without duplicating
        for em in all_emails:
            link = f"mailto:{em}"
            if not any(item.platform == "Email" and item.link == link for item in social_links):
                social_links.append(SocialLinkItem(platform="Email", link=link))

        # Add WhatsApp to social_link array without duplicating
        for wa in all_wa_links:
            if not any(item.platform == "WhatsApp" and item.link == wa for item in social_links):
                social_links.append(SocialLinkItem(platform="WhatsApp", link=wa))

        # Add Phone to social_link array if not already represented in WhatsApp
        for ph in all_phones:
            link = f"tel:{ph}"
            if not any(item.platform in ("Phone", "WhatsApp") and ph in item.link for item in social_links):
                social_links.append(SocialLinkItem(platform="Phone", link=link))

        # Deduplicate any duplicate (platform, link) entries
        seen_pairs = set()
        unique_links = []
        for item in social_links:
            pair = (item.platform, item.link)
            if pair not in seen_pairs:
                seen_pairs.add(pair)
                unique_links.append(item)

        return ProspectItem(
            name=best_name,
            location=best_location,
            social_link=unique_links
        )


deduplication_service = DeduplicationService()
