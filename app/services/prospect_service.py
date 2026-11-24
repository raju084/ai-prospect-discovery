import asyncio
import logging
from typing import List
from app.schemas import (
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
    PlatformProfile,
    QueryIntent,
)
from app.services.query_service import query_service
from app.services.relevance_service import relevance_service
from app.services.deduplication_service import deduplication_service
from app.platforms import PLATFORM_REGISTRY

logger = logging.getLogger(__name__)


class ProspectService:
    """
    Main orchestrator for prospect discovery.
    1. Understands query intent via LLM / deterministic NLP.
    2. Generates platform-specific search dorks.
    3. Concurrently queries all supported discovery platforms.
    4. Evaluates prospect relevance.
    5. Deduplicates and consolidates cross-platform profiles.
    6. Returns structured response.
    """

    async def discover_prospects(self, request: ProspectDiscoveryRequest) -> ProspectDiscoveryResponse:
        query_text = request.query
        logger.info(f"Starting prospect discovery for query: '{query_text}'")

        # Step 1: Understand natural-language query intent
        intent: QueryIntent = await query_service.parse_query(query_text)
        logger.info(
            f"Parsed intent: interest='{intent.interest}', audience='{intent.audience}', "
            f"location='{intent.location.to_formatted_string()}', target_type='{intent.target_type}'"
        )

        # Step 2: Generate platform search queries
        platform_queries = query_service.generate_platform_queries(intent)

        # Step 3: Concurrently discover prospects across platforms
        tasks = []
        for plat_key, platform_instance in PLATFORM_REGISTRY.items():
            search_q = platform_queries.get(plat_key, query_text)
            tasks.append(self._safe_discover(platform_instance, search_q, intent))

        platform_results = await asyncio.gather(*tasks, return_exceptions=True)

        raw_profiles: List[PlatformProfile] = []
        for res in platform_results:
            if isinstance(res, list):
                raw_profiles.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Platform discovery error: {res}")

        logger.info(f"Discovered {len(raw_profiles)} raw candidate profiles across platforms")

        # Step 4: Relevance evaluation and filtering
        relevant_profiles = await relevance_service.filter_relevant_profiles(raw_profiles, intent)
        logger.info(f"{len(relevant_profiles)} profiles passed relevance filtering")

        # Step 5: Duplicate detection & profile consolidation
        consolidated_prospects = deduplication_service.consolidate(relevant_profiles)
        logger.info(f"Consolidated into {len(consolidated_prospects)} unique prospect records")

        return ProspectDiscoveryResponse(
            success=True,
            query=query_text,
            total_prospects=len(consolidated_prospects),
            prospects=consolidated_prospects
        )

    async def _safe_discover(self, platform_instance, search_query: str, intent: QueryIntent) -> List[PlatformProfile]:
        try:
            return await platform_instance.discover(search_query, intent)
        except Exception as e:
            logger.error(f"Error executing discovery on {platform_instance.platform_name}: {e}")
            return []


prospect_service = ProspectService()
