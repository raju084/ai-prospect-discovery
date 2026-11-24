import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class ProspectDiscoveryRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural-language prospect discovery query",
        examples=["Football lovers in Washington DC in USA"],
    )

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        clean = v.strip()
        if not clean:
            raise ValueError("Query string cannot be empty or whitespace only.")
        if len(clean) < 3:
            raise ValueError("Query string must be at least 3 characters long.")
        if len(clean) > 500:
            raise ValueError("Query string cannot exceed 500 characters.")
        # Strip potential control characters to prevent prompt injection and logging exploits
        clean = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", clean)
        return clean


class SocialLinkItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    platform: str = Field(
        ...,
        description="Platform name (LinkedIn, X, YouTube, Instagram, WhatsApp, Facebook, Email, Threads)",
        examples=["LinkedIn"],
    )
    link: str = Field(
        ...,
        description="Direct verified URL or contact link (e.g. mailto:..., https://wa.me/...)",
        examples=["https://www.linkedin.com/in/john-smith"],
    )


class ProspectItem(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(
        ...,
        description="Prospect full name or business entity name",
        examples=["John Smith"],
    )
    location: Optional[str] = Field(
        None,
        description="Geographical location formatted as City, State, Country when available",
        examples=["Washington DC, USA"],
    )
    social_link: List[SocialLinkItem] = Field(
        default_factory=list,
        description="Consolidated list of verified public profiles and contact channels",
    )


class ProspectDiscoveryResponse(BaseModel):
    success: bool = Field(True, description="Indicates whether the request was successful")
    query: str = Field(..., description="Original input query")
    total_prospects: int = Field(..., description="Total count of discovered and deduplicated prospects")
    prospects: List[ProspectItem] = Field(default_factory=list, description="List of prospect records")


class LocationDetails(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    def to_formatted_string(self) -> str:
        # If city and country exist and state is redundant (e.g. Washington DC), format as 'City, Country'
        if self.city and self.country:
            if not self.state or self.state.lower() in ("district of columbia", self.city.lower()):
                return f"{self.city}, {self.country}"
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else ""


class QueryIntent(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    interest: str = Field(..., description="Target interest, hobby, or domain")
    audience: str = Field(..., description="Target persona or audience title")
    location: LocationDetails = Field(default_factory=LocationDetails, description="Geographical parameters")
    target_type: str = Field("individual", description="'individual' or 'business'")


class PlatformProfile(BaseModel):
    platform: str
    profile_url: str
    name: str
    username: Optional[str] = None
    bio: Optional[str] = None
    snippet: Optional[str] = None
    location: Optional[str] = None
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    whatsapp_links: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
