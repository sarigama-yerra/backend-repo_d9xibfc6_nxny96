import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from datetime import datetime

BASE_URL = "https://oddyssey.nikoskatsaounis.com/"
INDEX_URL = urljoin(BASE_URL, "index.html")

SLUG_RE = re.compile(r"[^a-z0-9]+")

def slugify(text: str) -> str:
    s = text.lower()
    s = SLUG_RE.sub("-", s).strip("-")
    return s

def fetch(url: str) -> str:
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.text

def extract_chapter_links(index_html: str):
    soup = BeautifulSoup(index_html, "html.parser")
    links = []
    for a in soup.select(".chapter-list a[href]"):
        href = a.get("href").strip()
        text = a.get_text(strip=True)
        if href.lower().startswith("chapter_") and href.lower().endswith(".html"):
            links.append((text, urljoin(BASE_URL, href), href))
    # Ensure stable order by filename numeric part
    def key_fn(item):
        _text, _abs, rel = item
        m = re.search(r"chapter_(\d+)\.html", rel)
        return int(m.group(1)) if m else 999
    links.sort(key=key_fn)
    return links

def html_to_text_block(soup: BeautifulSoup) -> str:
    content_div = soup.select_one(".content")
    if not content_div:
        # fallback to body content without nav
        content_div = soup.body or soup
    parts: list[str] = []
    # Iterate through children preserving section breaks and placeholders
    for el in content_div.descendants:
        if getattr(el, 'name', None) == 'p':
            txt = el.get_text(" ", strip=False)
            if txt:
                parts.append(txt.strip())
        elif getattr(el, 'name', None) in ('h2','h3'):
            parts.append(f"\n\n{el.get_text(strip=True)}\n")
        elif getattr(el, 'name', None) == 'div' and 'section-break' in (el.get('class') or []):
            parts.append("\n***\n")
        elif getattr(el, 'name', None) == 'div' and 'image-placeholder' in (el.get('class') or []):
            data_id = el.get('data-image-id') or 'image'
            parts.append(f"\n[IMAGE_PLACEHOLDER:{data_id}]\n")
    # Join with double newlines between paragraphs
    body = "\n\n".join([p for p in parts if p is not None and str(p).strip() != ""]).strip()
    return body

def extract_title(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        # Strip leading "CHAPTER X:" prefix while keeping rest
        t = h1.get_text(strip=True)
        # In case title like: "CHAPTER 1: ATHENS — Growing Up Digital"
        return t
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "Untitled Chapter"


def build_manifest():
    index_html = fetch(INDEX_URL)
    chapter_links = extract_chapter_links(index_html)

    chapters = []
    for _label, abs_url, rel in chapter_links:
        html = fetch(abs_url)
        soup = BeautifulSoup(html, "html.parser")
        title = extract_title(soup)
        # compute order from filename
        m = re.search(r"chapter_(\d+)\.html", rel)
        order = int(m.group(1)) if m else len(chapters) + 1
        body = html_to_text_block(soup)
        # ensure body is plain text (no control chars)
        body = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", body)
        ch = {
            "order": order,
            "title": title,
            "body": body,
            "tags": [],
            "themes": [],
            "metadata": {
                "source_url": abs_url,
                "scraped_at": datetime.utcnow().isoformat()+"Z",
            },
            "slug": f"chapter-{order}-{slugify(title)}",
        }
        chapters.append(ch)

    # Book metadata from index page
    soup = BeautifulSoup(index_html, "html.parser")
    book_title = "Sacred Circuits: The Odyssey"
    subtitle_el = soup.select_one(".subtitle")
    subtitle = subtitle_el.get_text(strip=True) if subtitle_el else None
    author_el = soup.select_one(".author")
    author = author_el.get_text(strip=True).replace("by ", "") if author_el else "Unknown"

    book = {
        "title": book_title,
        "author": author,
        "subtitle": subtitle,
        "genre": ["Memoir", "Travel"],
        "tags": ["Odyssey", "Digital Age", "Psychedelics", "Travel"],
        "publication_date": None,
    }

    manifest = {
        "book": book,
        "chapters": chapters,
        "ready_for_import": True,
        "manifest_version": "1.0",
    }
    return manifest


def main():
    manifest = build_manifest()
    # Validate round-trip JSON
    data = json.dumps(manifest, ensure_ascii=False)
    json.loads(data)
    # write out
    with open("cleaned_import_manifest.json", "w", encoding="utf-8") as f:
        f.write(data)
    print("Wrote cleaned_import_manifest.json with", len(manifest["chapters"]), "chapters")

    # Post to local backend import endpoint
    try:
        resp = requests.post(
            "http://localhost:8000/api/import",
            headers={"Content-Type": "application/json"},
            data=data.encode("utf-8"),
            timeout=30,
        )
        print("Import status:", resp.status_code, resp.text[:2000])
    except Exception as e:
        print("Failed to POST to backend:", e)


if __name__ == "__main__":
    main()
