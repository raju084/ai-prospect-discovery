import re
import logging
from typing import Dict, Any, List
from app.schemas import QueryIntent, LocationDetails
from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

# Known geographic dictionaries for robust deterministic fallback parsing
KNOWN_LOCATIONS = {
    "washington dc": {"city": "Washington DC", "state": "District of Columbia", "country": "USA"},
    "washington": {"city": "Washington", "state": "District of Columbia", "country": "USA"},
    "new york": {"city": "New York", "state": "New York", "country": "USA"},
    "london": {"city": "London", "state": "Greater London", "country": "UK"},
    "ahmedabad": {"city": "Ahmedabad", "state": "Gujarat", "country": "India"},
    "dubai": {"city": "Dubai", "state": "Dubai", "country": "UAE"},
    "san francisco": {"city": "San Francisco", "state": "California", "country": "USA"},
    "bangalore": {"city": "Bangalore", "state": "Karnataka", "country": "India"},
    "bengaluru": {"city": "Bengaluru", "state": "Karnataka", "country": "India"},
    "mumbai": {"city": "Mumbai", "state": "Maharashtra", "country": "India"},
    "delhi": {"city": "Delhi", "state": "Delhi", "country": "India"},
    "singapore": {"city": "Singapore", "state": "Singapore", "country": "Singapore"},
    "toronto": {"city": "Toronto", "state": "Ontario", "country": "Canada"},
    "sydney": {"city": "Sydney", "state": "New South Wales", "country": "Australia"},
}

KNOWN_COUNTRIES = {
    "usa": "USA",
    "united states": "USA",
    "us": "USA",
    "uk": "UK",
    "united kingdom": "UK",
    "india": "India",
    "uae": "UAE",
    "united arab emirates": "UAE",
    "canada": "Canada",
    "australia": "Australia",
    "germany": "Germany",
    "france": "France",
}

BUSINESS_KEYWORDS = [
    "agency owners", "business owners", "owners", "founders", "co-founders",
    "ceo", "ceos", "directors", "companies", "firm", "enterprises"
]


class QueryService:
    """
    Analyzes natural-language queries to extract interest, audience, location,
    and target type using LLM with deterministic NLP fallback.
    Also produces platform-optimized search dorks.
    """

    async def parse_query(self, query: str) -> QueryIntent:
        """
        Parses query using LLM if available, otherwise executes deterministic NLP extraction.
        """
        prompt = f"""
You are an AI Prospect Discovery parameter extractor.
Analyze the following natural-language search query:
"{query}"

Extract:
1. interest: The primary interest, topic, industry, or activity (e.g., "Football", "Digital marketing", "Startups", "Cricket", "Restaurants")
2. audience: The target persona or audience group (e.g., "Football lovers", "Marketing business owners", "Startup founders", "Cricket enthusiasts", "Restaurant owners")
3. location: Object with "city", "state", and "country"
4. target_type: "individual" or "business"

Example 1: "Football lovers in Washington DC in USA"
{{
  "interest": "Football",
  "audience": "Football lovers",
  "location": {{
    "city": "Washington DC",
    "state": "District of Columbia",
    "country": "USA"
  }},
  "target_type": "individual"
}}

Example 2: "Digital marketing agency owners in New York USA"
{{
  "interest": "Digital marketing",
  "audience": "Digital marketing agency owners",
  "location": {{
    "city": "New York",
    "state": "New York",
    "country": "USA"
  }},
  "target_type": "business"
}}

Output strictly valid JSON with keys: interest, audience, location (city, state, country), target_type.
"""
        system_instruction = "You are an expert NLP assistant that extracts prospect parameters into JSON."
        llm_response = await llm_service.generate_json(prompt, system_instruction)

        if llm_response and isinstance(llm_response, dict) and "interest" in llm_response:
            try:
                loc_dict = llm_response.get("location", {})
                loc_details = LocationDetails(
                    city=loc_dict.get("city"),
                    state=loc_dict.get("state"),
                    country=loc_dict.get("country")
                )
                return QueryIntent(
                    interest=llm_response.get("interest", query),
                    audience=llm_response.get("audience", query),
                    location=loc_details,
                    target_type=llm_response.get("target_type", "individual")
                )
            except Exception as e:
                logger.warning(f"Failed to instantiate QueryIntent from LLM response: {e}")

        # Deterministic NLP Fallback
        return self._heuristic_parse(query)

    def _heuristic_parse(self, query: str) -> QueryIntent:
        """
        Deterministic NLP extractor for zero-dependency / offline operations.
        Accurately identifies audience, interest, and geographical entities.
        """
        q_lower = query.lower().strip()

        # Identify location
        found_city = None
        found_state = None
        found_country = None

        # Check multi-word known locations first
        for loc_key, loc_info in sorted(KNOWN_LOCATIONS.items(), key=lambda x: -len(x[0])):
            if re.search(r"\b" + re.escape(loc_key) + r"\b", q_lower):
                found_city = loc_info["city"]
                found_state = loc_info["state"]
                found_country = loc_info["country"]
                break

        # Check countries
        for c_key, c_val in KNOWN_COUNTRIES.items():
            if re.search(r"\b" + re.escape(c_key) + r"\b", q_lower):
                found_country = c_val
                break

        # Target type
        is_business = any(re.search(r"\b" + re.escape(bw) + r"\b", q_lower) for bw in BUSINESS_KEYWORDS)
        target_type = "business" if is_business else "individual"

        # Audience and Interest separation
        # Usually split by "in", "near", "at", "around"
        parts = re.split(r"\s+\b(?:in|near|at|around)\b\s+", query, flags=re.IGNORECASE)
        audience_raw = parts[0].strip() if parts else query

        # Interest extraction
        interest = audience_raw
        for suffix in ["lovers", "fans", "enthusiasts", "owners", "agency owners", "founders", "professionals", "players"]:
            match = re.search(rf"^(.*?)\s+{suffix}", audience_raw, re.IGNORECASE)
            if match:
                interest = match.group(1).strip()
                break

        location_details = LocationDetails(
            city=found_city,
            state=found_state,
            country=found_country
        )

        return QueryIntent(
            interest=interest,
            audience=audience_raw,
            location=location_details,
            target_type=target_type
        )

    def generate_platform_queries(self, intent: QueryIntent) -> Dict[str, str]:
        """
        Generates platform-specific search dorks optimized for each social platform.
        """
        loc_str = intent.location.city or intent.location.state or intent.location.country or ""
        interest = intent.interest
        audience = intent.audience

        # Base terms
        terms = f'"{interest}"'
        if loc_str:
            terms += f' "{loc_str}"'

        return {
            "google": f'{audience} {loc_str} profile OR contact',
            "linkedin": f'site:linkedin.com/in/ "{interest}" "{loc_str}"' if loc_str else f'site:linkedin.com/in/ "{audience}"',
            "x": f'(site:x.com OR site:twitter.com) "{interest}" "{loc_str}" -inurl:status' if loc_str else f'(site:x.com OR site:twitter.com) "{audience}" -inurl:status',
            "youtube": f'site:youtube.com/@ "{interest}" "{loc_str}"' if loc_str else f'site:youtube.com/@ "{audience}"',
            "instagram": f'site:instagram.com "{interest}" "{loc_str}" -inurl:explore' if loc_str else f'site:instagram.com "{audience}" -inurl:explore',
            "facebook": f'site:facebook.com "{interest}" "{loc_str}"' if loc_str else f'site:facebook.com "{audience}"',
            "threads": f'site:threads.net/@ "{interest}" "{loc_str}"' if loc_str else f'site:threads.net/@ "{audience}"',
            "whatsapp": f'("wa.me/" OR "chat.whatsapp.com") "{interest}" "{loc_str}"' if loc_str else f'("wa.me/" OR "chat.whatsapp.com") "{audience}"',
        }


query_service = QueryService()
