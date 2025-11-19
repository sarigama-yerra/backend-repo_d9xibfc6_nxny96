import json, re
from pathlib import Path
from typing import Any, Dict, List

CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
TRUNCATED_LINE_RE = re.compile(rb"^\s*\.\.\. \(truncated.*\) \.\.\.\s*$")
TRIPLE_DASH_RE = re.compile(rb"^\s*---\s*$")


def clean_str(s: str) -> str:
    if not isinstance(s, str):
        s = str(s)
    return CTRL_CHARS_RE.sub("", s)


def extract_text_from_block(block) -> str:
    if isinstance(block, str):
        return clean_str(block)
    if isinstance(block, (int, float, bool)):
        return clean_str(str(block))
    if isinstance(block, dict):
        parts = []
        for key in ("text", "paragraph"):
            if key in block and isinstance(block[key], (str, int, float, bool)):
                parts.append(clean_str(block[key]))
        if "content" in block:
            c = block["content"]
            if isinstance(c, list):
                parts.extend(extract_text_from_block(x) for x in c)
            elif isinstance(c, (str, int, float, bool, dict)):
                parts.append(extract_text_from_block(c))
        if "children" in block and isinstance(block["children"], list):
            parts.extend(extract_text_from_block(x) for x in block["children"])
        if not parts:
            for v in block.values():
                if isinstance(v, (str, int, float, bool)):
                    parts.append(clean_str(v))
        return "\n".join(p for p in parts if p)
    if isinstance(block, list):
        return "\n\n".join(extract_text_from_block(x) for x in block if x is not None)
    return ""


def to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [clean_str(str(v)) for v in value if v is not None]
    # split common separators
    s = clean_str(str(value))
    parts = re.split(r"[,/|;]", s)
    return [p.strip() for p in parts if p and p.strip()]


def sanitize_strings(obj):
    if isinstance(obj, dict):
        return {k: sanitize_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_strings(x) for x in obj]
    if isinstance(obj, str):
        return clean_str(obj)
    return obj


def transform_chapter(ch: Dict[str, Any]) -> Dict[str, Any]:
    ch = dict(ch)
    if "number" in ch:
        ch["number"] = to_int(ch["number"])
    if "order" in ch:
        ch["order"] = to_int(ch["order"]) or ch.get("number", 0)
    else:
        ch["order"] = ch.get("number", 0)
    # slug
    if not ch.get("slug"):
        base = (ch.get("title") or f"chapter-{ch['order']}")
        base = clean_str(str(base)).lower()
        ch["slug"] = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    else:
        ch["slug"] = clean_str(str(ch["slug"]))
    # title
    if ch.get("title"):
        ch["title"] = clean_str(str(ch["title"]))
    else:
        ch["title"] = f"Chapter {ch['order']}"
    # summary optional normalize
    if isinstance(ch.get("summary"), str):
        ch["summary"] = clean_str(ch["summary"])  # type: ignore
    else:
        ch["summary"] = ch.get("summary") or ""
    # lists
    ch["tags"] = as_list(ch.get("tags"))
    ch["themes"] = as_list(ch.get("themes"))
    # body
    if isinstance(ch.get("body"), str) and ch["body"].strip():
        ch["body"] = clean_str(ch["body"])  # type: ignore
    else:
        content = ch.get("content")
        body_text = extract_text_from_block(content) if content is not None else ""
        if not body_text and "paragraphs" in ch:
            body_text = extract_text_from_block(ch["paragraphs"])  # type: ignore
        if not body_text and "text" in ch:
            body_text = extract_text_from_block(ch["text"])  # type: ignore
        ch["body"] = clean_str(body_text)
    # cleanup noisy fields
    for k in ("content", "paragraphs", "text", "audio_url", "published"):
        ch.pop(k, None)
    return ch


def normalize_book(book: Dict[str, Any], chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
    b = dict(book)
    # required
    b["title"] = clean_str(str(b.get("title", "Untitled")))
    b["author"] = clean_str(str(b.get("author", "Unknown")))
    # optional mappings
    if b.get("subtitle"):
        b["subtitle"] = clean_str(str(b["subtitle"]))
    if b.get("description"):
        b["description"] = clean_str(str(b["description"]))
    # genre as list
    b["genre"] = as_list(b.get("genre"))
    # publication date mapping
    if b.get("published_date") and not b.get("publication_date"):
        b["publication_date"] = clean_str(str(b.pop("published_date")))
    # tags list
    b["tags"] = as_list(b.get("tags"))
    # computed
    if chapters:
        b["total_chapters"] = len(chapters)
        total_wc = 0
        for ch in chapters:
            wc = ch.get("word_count")
            try:
                if wc is None:
                    # naive count if absent
                    wc = len((ch.get("body") or "").split())
                total_wc += int(wc)
            except Exception:
                pass
        b["total_word_count"] = total_wc or None
    return b


def preclean_bytes(data: bytes) -> bytes:
    """Pre-clean the raw bytes to strip invalid lines and truncate to JSON body."""
    # Remove control chars except allowed whitespace
    data = re.sub(b"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", data)
    # Drop editorial placeholder lines or standalone markdown separators
    lines = []
    for line in data.splitlines():
        if TRUNCATED_LINE_RE.match(line):
            continue
        if TRIPLE_DASH_RE.match(line):
            # likely markdown separator accidentally injected
            continue
        lines.append(line)
    data = b"\n".join(lines)
    # Keep only outer JSON object boundaries
    start = data.find(b"{")
    end = data.rfind(b"}")
    if start != -1 and end != -1 and end > start:
        data = data[start:end+1]
    return data


def escape_newlines_inside_strings(data: bytes) -> bytes:
    """Replace raw newlines (\n, \r) inside JSON string literals with escaped \n so that json.loads can parse.
    We scan byte-by-byte tracking whether we're inside a string and whether previous char was an escape.
    """
    out = bytearray()
    in_string = False
    escaped = False
    for b in data:
        ch = chr(b)
        if in_string:
            if escaped:
                out.append(b)
                escaped = False
            else:
                if ch == '\\':
                    out.append(b)
                    escaped = True
                elif ch == '"':
                    out.append(b)
                    in_string = False
                elif ch == '\n':
                    out.extend(b"\\n")
                elif ch == '\r':
                    # drop or convert CR
                    out.extend(b"\\n")
                else:
                    out.append(b)
        else:
            if ch == '"':
                out.append(b)
                in_string = True
                escaped = False
            else:
                out.append(b)
    return bytes(out)


def main():
    src = Path("import_manifest.json")
    dst = Path("cleaned_import_manifest.json")
    rb = open(src, "rb").read()
    rb = preclean_bytes(rb)
    # Escape raw newlines inside strings to make it JSON compliant
    rb = escape_newlines_inside_strings(rb)
    # Attempt to load JSON now
    try:
        raw = json.loads(rb)
    except json.JSONDecodeError as e:
        # As a last resort remove any lingering invalid control chars again and try
        rb2 = re.sub(b"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", rb)
        raw = json.loads(rb2)
    raw = sanitize_strings(raw)

    # Expect top-level dict with book/chapters
    if not isinstance(raw, dict):
        raise ValueError("Top-level JSON must be an object with 'book' and 'chapters'")

    chapters_in: List[Dict[str, Any]] = []
    if "chapters" in raw and isinstance(raw["chapters"], list):
        chapters_in = [transform_chapter(ch) for ch in raw["chapters"]]
    elif "book" in raw and isinstance(raw["book"], dict) and "chapters" in raw["book"]:
        chs = raw["book"]["chapters"]
        if isinstance(chs, list):
            chapters_in = [transform_chapter(ch) for ch in chs]

    # book normalization
    if "book" in raw and isinstance(raw["book"], dict):
        raw["book"] = normalize_book(raw["book"], chapters_in)
    else:
        # If missing, synthesize a minimal book
        raw["book"] = normalize_book({
            "title": "Sacred Circuits: The Odyssey",
            "author": "Unknown",
        }, chapters_in)

    # ensure chapters live at top-level key
    raw["chapters"] = chapters_in

    # Drop unexpected top-level keys that could trip validation (keep glossary/bibliography if present)
    allowed_top = {"book", "chapters", "glossary", "bibliography", "ready_for_import", "manifest_version"}
    raw = {k: v for k, v in raw.items() if k in allowed_top}

    # defaults
    raw.setdefault("ready_for_import", True)
    raw.setdefault("manifest_version", "1.0")

    dst.write_text(json.dumps(raw, ensure_ascii=False))
    print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
