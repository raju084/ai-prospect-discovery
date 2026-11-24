import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas import (
    ProspectDiscoveryRequest,
    ProspectDiscoveryResponse,
    PlatformProfile,
    QueryIntent,
    LocationDetails
)
from app.services.query_service import query_service
from app.services.deduplication_service import deduplication_service
from app.services.relevance_service import relevance_service
from app.utils.normalizers import normalize_name, normalize_url, normalize_whatsapp_link
from app.utils.validators import is_valid_email, is_valid_phone, is_valid_platform_profile_url


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ==========================================
# 1. Utility Validators and Normalizers Tests
# ==========================================

def test_normalize_name():
    assert normalize_name("Marcus Vance | LinkedIn") == "Marcus Vance"
    assert normalize_name("Elena Rostova (@elena_dc) on Threads") == "Elena Rostova"
    assert normalize_name("David Alpert - Managing Partner") == "David Alpert"
    assert normalize_name("Smith, John") == "John Smith"
    assert normalize_name("⚡ Jayesh Patel 🏏") == "Jayesh Patel"


def test_normalize_url():
    url = "https://www.linkedin.com/in/marcus-vance/?utm_source=share&utm_medium=member_desktop"
    normalized = normalize_url(url)
    assert "utm_source" not in normalized
    assert normalized == "https://www.linkedin.com/in/marcus-vance"


def test_normalize_whatsapp():
    assert normalize_whatsapp_link("+1 (202) 555-0143") == "https://wa.me/12025550143"
    assert normalize_whatsapp_link("https://wa.me/12025550143?text=Hi") == "https://wa.me/12025550143"


def test_email_and_phone_validation():
    assert is_valid_email("marcus.vance@gmail.com") is True
    assert is_valid_email("invalid-email") is False
    assert is_valid_email("example@example.com") is False  # Blacklisted placeholder
    assert is_valid_email("user@domain.com") is False

    assert is_valid_phone("+1-202-555-0143") is True
    assert is_valid_phone("123") is False


def test_platform_profile_url_validation():
    # Valid individual profiles
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/in/marcus-vance") is True
    assert is_valid_platform_profile_url("X", "https://x.com/marcusvance_dc") is True
    assert is_valid_platform_profile_url("YouTube", "https://www.youtube.com/@ElenaDCFootballCoaching") is True
    assert is_valid_platform_profile_url("Instagram", "https://www.instagram.com/marcusv_football") is True
    assert is_valid_platform_profile_url("Threads", "https://www.threads.net/@elena_dcfootball") is True

    # Generic or login pages should be rejected
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/feed") is False
    assert is_valid_platform_profile_url("LinkedIn", "https://www.linkedin.com/login") is False
    assert is_valid_platform_profile_url("Instagram", "https://www.instagram.com/explore") is False
    assert is_valid_platform_profile_url("X", "https://x.com/home") is False


# ==========================================
# 2. Query Understanding Tests
# ==========================================

@pytest.mark.asyncio
async def test_query_understanding_washington_football():
    intent = await query_service.parse_query("Football lovers in Washington DC in USA")
    assert intent.interest.lower() == "football"
    assert "washington" in intent.location.city.lower()
    assert intent.location.country.upper() == "USA"
    assert intent.target_type == "individual"


@pytest.mark.asyncio
async def test_query_understanding_nyc_agencies():
    intent = await query_service.parse_query("Digital marketing agency owners in New York USA")
    assert "marketing" in intent.interest.lower()
    assert "new york" in intent.location.city.lower()
    assert intent.target_type == "business"


@pytest.mark.asyncio
async def test_query_understanding_london_startups():
    intent = await query_service.parse_query("Startup founders in London UK")
    assert "startup" in intent.interest.lower()
    assert "london" in intent.location.city.lower()
    assert intent.location.country.upper() == "UK"


@pytest.mark.asyncio
async def test_query_understanding_ahmedabad_cricket():
    intent = await query_service.parse_query("Cricket lovers in Ahmedabad India")
    assert intent.interest.lower() == "cricket"
    assert "ahmedabad" in intent.location.city.lower()
    assert intent.location.country.lower() == "india"


@pytest.mark.asyncio
async def test_query_understanding_dubai_restaurants():
    intent = await query_service.parse_query("Restaurant owners in Dubai UAE")
    assert "restaurant" in intent.interest.lower()
    assert "dubai" in intent.location.city.lower()
    assert intent.location.country.upper() == "UAE"


# ==========================================
# 3. Deduplication and Consolidation Tests
# ==========================================

def test_profile_consolidation_same_person():
    profiles = [
        PlatformProfile(
            platform="LinkedIn",
            profile_url="https://www.linkedin.com/in/john-doe",
            name="John Doe",
            location="Washington DC, USA",
            emails=["john.doe@example-domain.com"],
            phones=["+1-202-555-0100"]
        ),
        PlatformProfile(
            platform="X",
            profile_url="https://x.com/johndoe",
            name="John Doe",
            location="Washington DC, USA",
            emails=["john.doe@example-domain.com"]
        ),
        PlatformProfile(
            platform="WhatsApp",
            profile_url="https://wa.me/12025550100",
            name="John Doe",
            location="Washington DC, USA",
            whatsapp_links=["https://wa.me/12025550100"]
        )
    ]

    prospects = deduplication_service.consolidate(profiles)
    assert len(prospects) == 1
    prospect = prospects[0]
    assert prospect.name == "John Doe"
    assert prospect.location == "Washington DC, USA"

    # Verify social links include LinkedIn, X, Email, WhatsApp
    platforms = [link.platform for link in prospect.social_link]
    assert "LinkedIn" in platforms
    assert "X" in platforms
    assert "Email" in platforms
    assert "WhatsApp" in platforms


def test_no_false_merging_different_locations():
    profiles = [
        PlatformProfile(
            platform="LinkedIn",
            profile_url="https://www.linkedin.com/in/john-smith-dc",
            name="John Smith",
            location="Washington DC, USA"
        ),
        PlatformProfile(
            platform="LinkedIn",
            profile_url="https://www.linkedin.com/in/john-smith-london",
            name="John Smith",
            location="London, UK"
        )
    ]

    prospects = deduplication_service.consolidate(profiles)
    assert len(prospects) == 2


# ==========================================
# 4. Relevance Evaluation Tests
# ==========================================

@pytest.mark.asyncio
async def test_relevance_filtering():
    intent = QueryIntent(
        interest="Football",
        audience="Football lovers",
        location=LocationDetails(city="Washington DC", country="USA"),
        target_type="individual"
    )

    relevant_profile = PlatformProfile(
        platform="LinkedIn",
        profile_url="https://www.linkedin.com/in/marcus-vance-dc",
        name="Marcus Vance",
        bio="DC Defenders football fan and DMV flag football captain in Washington DC.",
        location="Washington DC, USA"
    )

    irrelevant_profile = PlatformProfile(
        platform="LinkedIn",
        profile_url="https://www.linkedin.com/in/random-baker",
        name="Chef Jacques",
        bio="Pastry chef specializing in Parisian croissants in Paris France.",
        location="Paris, France"
    )

    filtered = await relevance_service.filter_relevant_profiles([relevant_profile, irrelevant_profile], intent)
    assert len(filtered) == 1
    assert filtered[0].name == "Marcus Vance"


# ==========================================
# 5. FastAPI Endpoints Integration Tests
# ==========================================

@pytest.mark.asyncio
async def test_root_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "UP"


@pytest.mark.asyncio
async def test_invalid_query_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty query
        res = await client.post("/prospect-discovery", json={"query": ""})
        assert res.status_code == 400
        assert res.json()["success"] is False

        # Short query
        res = await client.post("/prospect-discovery", json={"query": "ab"})
        assert res.status_code == 400
        assert res.json()["success"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("test_query", [
    "Football lovers in Washington DC in USA",
    "Digital marketing agency owners in New York USA",
    "Startup founders in London UK",
    "Cricket lovers in Ahmedabad India",
    "Restaurant owners in Dubai UAE"
])
async def test_five_practical_test_cases(test_query: str):
    """
    Validates all 5 mandatory practical test cases from Section 6.
    Ensures response matches the exact required JSON structure.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/prospect-discovery", json={"query": test_query})
        assert res.status_code == 200

        data = res.json()
        assert data["success"] is True
        assert data["query"] == test_query
        assert isinstance(data["total_prospects"], int)
        assert data["total_prospects"] >= 1
        assert isinstance(data["prospects"], list)
        assert len(data["prospects"]) == data["total_prospects"]

        # Validate prospect fields
        for prospect in data["prospects"]:
            assert "name" in prospect and prospect["name"]
            assert "location" in prospect
            assert isinstance(prospect["social_link"], list)
            assert len(prospect["social_link"]) > 0

            # Validate each social link
            for link_obj in prospect["social_link"]:
                assert "platform" in link_obj
                assert "link" in link_obj
                assert link_obj["link"].startswith(("http://", "https://", "mailto:", "tel:"))
