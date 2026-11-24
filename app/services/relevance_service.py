import logging
import re
from typing import List
from app.schemas import PlatformProfile, QueryIntent
from app.config import settings
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class RelevanceService:
    """
    Evaluates prospect relevance against the user's intent:
      - Interest relevance (connection to sport, industry, or domain)
      - Location relevance (geographical affinity)
      - Audience / Profession relevance (e.g. founder, lover, owner)
      - Authenticity (filters out non-people or spam placeholders)
    """

    async def filter_relevant_profiles(
        self,
        profiles: List[PlatformProfile],
        intent: QueryIntent
    ) -> List[PlatformProfile]:
        if not profiles:
            return []

        relevant: List[PlatformProfile] = []

        for p in profiles:
            score = self._calculate_heuristic_score(p, intent)
            if score >= settings.MIN_RELEVANCE_SCORE:
                relevant.append(p)
            else:
                logger.debug(f"Filtered out low relevance profile: {p.name} (score: {score})")

        return relevant

    def _calculate_heuristic_score(self, profile: PlatformProfile, intent: QueryIntent) -> float:
        """
        Calculates a relevance score between 0.0 and 1.0.
        """
        text = f"{profile.name} {profile.bio} {profile.snippet} {profile.profile_url}".lower()

        score = 0.0
        # 1. Interest Match (weight: 0.40)
        interest_tokens = [t.lower() for t in re.findall(r"\w+", intent.interest) if len(t) > 2]
        if interest_tokens:
            matches = sum(1 for token in interest_tokens if token in text)
            score += 0.40 * (matches / len(interest_tokens))
        else:
            score += 0.20

        # 2. Audience / Role Match (weight: 0.30)
        audience_tokens = [t.lower() for t in re.findall(r"\w+", intent.audience) if len(t) > 2]
        if audience_tokens:
            matches = sum(1 for token in audience_tokens if token in text)
            score += 0.30 * min(1.0, (matches / len(audience_tokens)))
        else:
            score += 0.15

        # 3. Location Match (weight: 0.30)
        loc = intent.location
        loc_components = [p.lower() for p in [loc.city, loc.state, loc.country] if p]
        if loc_components:
            matches = sum(1 for c in loc_components if c in text)
            score += 0.30 * (matches / len(loc_components))
        else:
            # If no location specified in query, grant full location credit
            score += 0.30

        return min(1.0, score)


relevance_service = RelevanceService()
