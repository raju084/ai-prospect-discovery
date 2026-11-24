from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any


class ProspectDiscoveryRequest(BaseModel):
    query: str = Field(
        ...,
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
        return clean


class SocialLinkItem(BaseModel):
    platform: str = Field(
        ...,
        description="Platform name (LinkedIn, X, YouTube, Instagram, WhatsApp, Facebook, Email, Threads, etc.)",
        examples=["LinkedIn"],
    )
    link: str = Field(
        ...,
        description="Direct verified URL or contact link (e.g. mailto:..., https://wa.me/...)",
        examples=["https://www.linkedin.com/in/john-smith"],
    )


class ProspectItem(BaseModel):
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
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    def to_formatted_string(self) -> str:
        parts = [p for p in [self.city, self.state, self.country] if p]
        return ", ".join(parts) if parts else ""


class QueryIntent(BaseModel):
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
