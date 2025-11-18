"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Literal, Dict, Any

# --------------------------------------------------
# Legacy examples (kept for reference)
# --------------------------------------------------
class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# --------------------------------------------------
# Sacred Circuits Manuscript Schemas
# --------------------------------------------------
MediaType = Literal["image", "video", "audio"]

class CoverImage(BaseModel):
    url: Optional[HttpUrl] = Field(None, description="Cover image URL (optional, can be added later)")
    concept: Optional[str] = Field(None, description="Concept prompt/idea for the cover image")
    alt_text: Optional[str] = Field(None, description="Alt text for accessibility")

class MediaItem(BaseModel):
    type: MediaType = Field(..., description="Type of media: image, video, or audio")
    url: HttpUrl = Field(..., description="Direct URL to the media file")
    caption: Optional[str] = Field(None, description="Short caption or description")
    thumbnail: Optional[HttpUrl] = Field(None, description="Optional thumbnail image for videos/audio")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Duration for audio/video")

class Chapter(BaseModel):
    order: int = Field(0, ge=0, description="Ordering index for chapter sequence")
    title: str = Field(..., description="Chapter title")
    subtitle: Optional[str] = Field(None, description="Optional subtitle or timeframe")
    location: Optional[str] = Field(None, description="Primary location for this chapter")
    body: str = Field(..., description="Full chapter text (keep original line breaks)")
    word_count: Optional[int] = Field(None, ge=0, description="Word count for the chapter")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering and discovery")
    themes: List[str] = Field(default_factory=list, description="Themes for filtering")
    cover_image: Optional[CoverImage] = Field(None, description="Cover image metadata")
    media: List[MediaItem] = Field(default_factory=list, description="Attached media for this chapter")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Source/created/edited/status metadata")
    slug: Optional[str] = Field(None, description="URL-friendly unique slug for the chapter")

class Book(BaseModel):
    title: str
    author: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    genre: List[str] = Field(default_factory=list)
    total_word_count: Optional[int] = None
    total_chapters: Optional[int] = None
    tags: List[str] = Field(default_factory=list)
    language: Optional[str] = None
    series: Optional[Dict[str, Any]] = None
    publication_date: Optional[str] = None

class GlossaryEntry(BaseModel):
    term: str
    definition: str
    aliases: List[str] | None = None

class BibliographyEntry(BaseModel):
    citation: str
    url: Optional[HttpUrl] = None
    notes: Optional[str] = None
