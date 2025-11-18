import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from database import db, create_document, get_documents
from schemas import Chapter, Book, GlossaryEntry, BibliographyEntry

app = FastAPI(title="Sacred Circuits API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Sacred Circuits API running"}

# ------------------------------
# Models for import payload
# ------------------------------
class ImportManifest(BaseModel):
    book: Book
    chapters: List[Chapter]
    glossary: Optional[List[GlossaryEntry]] = None
    bibliography: Optional[List[BibliographyEntry]] = None
    ready_for_import: Optional[bool] = True
    manifest_version: Optional[str] = None

# ------------------------------
# Utilities
# ------------------------------
import re

def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text).strip("-")
    return text

# ------------------------------
# Book Endpoints
# ------------------------------
@app.get("/api/book", response_model=Book | Dict[str, Any])
def get_book():
    try:
        items = get_documents("book", {}, limit=1)
        if items:
            it = items[0]
            it.pop("_id", None)
            return it
        return {"title": "Sacred Circuits: The Odyssey", "author": "Unknown"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/book", status_code=201)
def create_book(book: Book):
    try:
        inserted_id = create_document("book", book)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------
# Chapter Endpoints
# ------------------------------
@app.get("/api/chapters", response_model=List[Chapter])
def list_chapters(tag: Optional[str] = None, theme: Optional[str] = None, q: Optional[str] = None):
    """Return chapters with optional filters, ordered by 'order'."""
    filter_query: Dict[str, Any] = {}
    if tag:
        filter_query["tags"] = {"$in": [tag]}
    if theme:
        filter_query["themes"] = {"$in": [theme]}
    if q:
        filter_query["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"subtitle": {"$regex": q, "$options": "i"}},
            {"location": {"$regex": q, "$options": "i"}},
        ]
    try:
        items = get_documents("chapter", filter_query)
        items.sort(key=lambda x: x.get("order", 0))
        normalized = []
        for it in items:
            it.pop("_id", None)
            it.setdefault("tags", [])
            it.setdefault("themes", [])
            it.setdefault("media", [])
            ci = it.get("cover_image")
            if isinstance(ci, str):
                it["cover_image"] = {"url": ci, "concept": None, "alt_text": None}
            normalized.append(it)
        return normalized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{slug}", response_model=Chapter)
def get_chapter(slug: str):
    try:
        items = get_documents("chapter", {"slug": slug}, limit=1)
        if not items:
            raise HTTPException(status_code=404, detail="Chapter not found")
        it = items[0]
        it.pop("_id", None)
        it.setdefault("tags", [])
        it.setdefault("themes", [])
        it.setdefault("media", [])
        ci = it.get("cover_image")
        if isinstance(ci, str):
            it["cover_image"] = {"url": ci, "concept": None, "alt_text": None}
        return it
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChapterCreate(Chapter):
    pass

@app.post("/api/chapters", status_code=201)
def create_chapter(chapter: ChapterCreate):
    try:
        if not getattr(chapter, "slug", None):
            slug = f"chapter-{chapter.order}-{slugify(chapter.title)}"
            chapter_dict = chapter.model_dump()
            chapter_dict["slug"] = slug
        else:
            chapter_dict = chapter.model_dump()
        inserted_id = create_document("chapter", chapter_dict)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------
# Glossary & Bibliography Endpoints
# ------------------------------
@app.get("/api/glossary", response_model=List[GlossaryEntry])
def get_glossary():
    try:
        items = get_documents("glossary", {})
        for it in items:
            it.pop("_id", None)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/bibliography", response_model=List[BibliographyEntry])
def get_bibliography():
    try:
        items = get_documents("bibliography", {})
        for it in items:
            it.pop("_id", None)
        return items
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------
# Import Endpoint
# ------------------------------
@app.post("/api/import", status_code=201)
def import_manifest(payload: ImportManifest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available for import")
    try:
        # Upsert book: keep only one
        db["book"].delete_many({})
        book_doc = payload.book.model_dump()
        db["book"].insert_one(book_doc)

        # Replace chapters
        db["chapter"].delete_many({})
        chapter_docs = []
        for ch in payload.chapters:
            data = ch.model_dump()
            if not data.get("slug"):
                data["slug"] = f"chapter-{data.get('order', 0)}-{slugify(data.get('title',''))}"
            ci = data.get("cover_image")
            if isinstance(ci, str):
                data["cover_image"] = {"url": ci, "concept": None, "alt_text": None}
            chapter_docs.append(data)
        if chapter_docs:
            db["chapter"].insert_many(chapter_docs)

        # Optional: glossary & bibliography
        if payload.glossary is not None:
            db["glossary"].delete_many({})
            if payload.glossary:
                db["glossary"].insert_many([g.model_dump() for g in payload.glossary])
        if payload.bibliography is not None:
            db["bibliography"].delete_many({})
            if payload.bibliography:
                db["bibliography"].insert_many([b.model_dump() for b in payload.bibliography])

        # Save manifest meta
        db["manifest"].delete_many({})
        db["manifest"].insert_one({
            "ready_for_import": bool(payload.ready_for_import),
            "manifest_version": payload.manifest_version or "1.0",
            "imported_at": __import__("datetime").datetime.utcnow(),
            "counts": {
                "chapters": len(chapter_docs),
                "glossary": 0 if payload.glossary is None else len(payload.glossary),
                "bibliography": 0 if payload.bibliography is None else len(payload.bibliography),
            }
        })

        return {"status": "ok", "chapters": len(chapter_docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ------------------------------
# System Test
# ------------------------------
@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
