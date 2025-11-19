import json, re
from pathlib import Path

CTRL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

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

def sanitize_strings(obj):
    if isinstance(obj, dict):
        return {k: sanitize_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_strings(x) for x in obj]
    if isinstance(obj, str):
        return clean_str(obj)
    return obj

def transform_chapter(ch):
    ch = dict(ch)
    if "number" in ch:
        ch["number"] = to_int(ch["number"])
    if "order" in ch:
        ch["order"] = to_int(ch["order"]) or ch.get("number", 0)
    else:
        ch["order"] = ch.get("number", 0)
    if not ch.get("slug"):
        base = (ch.get("title") or f"chapter-{ch['order']}").lower()
        ch["slug"] = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    else:
        ch["slug"] = clean_str(ch["slug"])  # type: ignore
    if ch.get("title"):
        ch["title"] = clean_str(ch["title"])  # type: ignore
    else:
        ch["title"] = f"Chapter {ch['order']}"
    if isinstance(ch.get("summary"), str):
        ch["summary"] = clean_str(ch["summary"])  # type: ignore
    else:
        ch["summary"] = ""
    tags = ch.get("tags", [])
    if not isinstance(tags, list):
        tags = [tags]
    ch["tags"] = [clean_str(str(t)) for t in tags if t is not None]
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
    ch.pop("content", None)
    ch.pop("paragraphs", None)
    ch.pop("text", None)
    return ch

def main():
    src = Path("import_manifest.json")
    dst = Path("cleaned_import_manifest.json")
    try:
        raw = json.load(open(src, "rb"))
    except json.JSONDecodeError:
        data = open(src, "rb").read()
        cleaned_bytes = re.sub(b"[\x00-\x08\x0b\x0c\x0e-\x1f]", b"", data)
        raw = json.loads(cleaned_bytes)
    raw = sanitize_strings(raw)
    # unify structure: move nested book/chapter if needed
    if isinstance(raw, dict) and "chapters" in raw and isinstance(raw["chapters"], list):
        raw["chapters"] = [transform_chapter(ch) for ch in raw["chapters"]]
    elif isinstance(raw, dict) and "book" in raw and isinstance(raw["book"], dict) and "chapters" in raw["book"]:
        chs = raw["book"]["chapters"]
        if isinstance(chs, list):
            raw["book"]["chapters"] = [transform_chapter(ch) for ch in chs]
    dst.write_text(json.dumps(raw, ensure_ascii=False))
    print(f"Wrote {dst}")

if __name__ == "__main__":
    main()
