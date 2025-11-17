import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Chapter

app = FastAPI(title="Multimedia Autobiography API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Multimedia Autobiography API running"}

@app.get("/api/chapters", response_model=List[Chapter])
def list_chapters(tag: Optional[str] = None):
    """Return all chapters, optionally filtered by tag, ordered by 'order'."""
    filter_query = {"tags": {"$in": [tag]}} if tag else {}
    try:
        items = get_documents("chapter", filter_query)
        # Sort by 'order'
        items.sort(key=lambda x: x.get("order", 0))
        # Convert MongoDB ObjectId and missing fields gracefully
        normalized = []
        for it in items:
            it.pop("_id", None)
            # Ensure missing list fields exist
            it.setdefault("tags", [])
            it.setdefault("media", [])
            normalized.append(it)
        return normalized
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChapterCreate(Chapter):
    pass

@app.post("/api/chapters", status_code=201)
def create_chapter(chapter: ChapterCreate):
    """Create a new chapter document."""
    try:
        inserted_id = create_document("chapter", chapter)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
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
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
