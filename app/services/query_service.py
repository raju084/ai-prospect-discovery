import re
import logging
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
        prompt = (
            f'You are an AI Prospect Discovery parameter extractor.\n'
            f'Analyze the following natural-language search query:\n"{query}"\n\n'
            f'Extract:\n'
            f'1. interest: Primary topic or domain (e.g. "Football", "Digital marketing", "Startups", "Cricket")\n'
            f'2. audience: Target persona (e.g. "Football lovers", "Digital marketing agency owners", "Startup founders")\n'
            f'3. location: Object with "city", "state", and "country"\n'
            f'4. target_type: "individual" or "business"\n\n'
            f'Output strictly valid JSON with keys: interest, audience, location (city, state, country), target_type.'
        )
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
        suffixes = ["lovers", "fans", "enthusiasts", "owners", "agency owners", "founders", "professionals", "players"]
        for suffix in suffixes:
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

    def generate_platform_queries(self, intent: QueryIntent) -> dict:
        """
        Generates platform-specific search dorks optimized for each social platform.
        """
        loc_str = intent.location.city or intent.location.state or intent.location.country or ""
        interest = intent.interest
        audience = intent.audience

        # Format location dork clause
        loc_clause = f'"{loc_str}"' if loc_str else ""
        interest_clause = f'"{interest}"'

        def build_dork(site_prefix: str, extra_flag: str = "") -> str:
            terms = f"{site_prefix} {interest_clause}"
            if loc_clause:
                terms += f" {loc_clause}"
            if extra_flag:
                terms += f" {extra_flag}"
            return terms.strip()

        return {
            "google": f'{audience} {loc_str} profile OR contact'.strip(),
            "linkedin": build_dork("site:linkedin.com/in/"),
            "x": build_dork("(site:x.com OR site:twitter.com)", "-inurl:status"),
            "youtube": build_dork("site:youtube.com/@"),
            "instagram": build_dork("site:instagram.com", "-inurl:explore"),
            "facebook": build_dork("site:facebook.com"),
            "threads": build_dork("site:threads.net/@"),
            "whatsapp": build_dork('("wa.me/" OR "chat.whatsapp.com")'),
        }


query_service = QueryService()
