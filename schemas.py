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
from typing import Optional, List, Literal

# Example schemas (kept for reference):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# --------------------------------------------------
# Novel Multimedia Website Schemas
# --------------------------------------------------

MediaType = Literal["image", "video", "audio"]

class MediaItem(BaseModel):
    """Represents a single media item attached to a chapter."""
    type: MediaType = Field(..., description="Type of media: image, video, or audio")
    url: HttpUrl = Field(..., description="Direct URL to the media file")
    caption: Optional[str] = Field(None, description="Short caption or description")
    thumbnail: Optional[HttpUrl] = Field(None, description="Optional thumbnail image for videos/audio")
    duration_seconds: Optional[int] = Field(None, ge=0, description="Duration for audio/video")

class Chapter(BaseModel):
    """A chapter in the autobiographical novel, with rich media."""
    title: str = Field(..., description="Chapter title")
    subtitle: Optional[str] = Field(None, description="Optional subtitle or tagline")
    body: str = Field(..., description="Main manuscript text for this chapter (Markdown supported)")
    order: int = Field(0, ge=0, description="Ordering index for chapter sequence")
    cover_image: Optional[HttpUrl] = Field(None, description="Cover image for the chapter")
    tags: List[str] = Field(default_factory=list, description="Tags for filtering and discovery")
    media: List[MediaItem] = Field(default_factory=list, description="Attached media for this chapter")

# Note: The Flames database viewer can read these schemas via the /schema endpoint
# and help with CRUD in development environments.
