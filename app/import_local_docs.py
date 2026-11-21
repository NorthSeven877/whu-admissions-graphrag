"""Import the existing Markdown corpus into GraphRAG's pages format."""
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
import os


def main():
    source = Path(__file__).resolve().parents[2] / "doc"
    destination = Path(os.environ["WHU_DATA"])
    files = sorted(source.rglob("*.md"))
    titles = {}
    for file in files:
        text = file.read_text(encoding="utf-8-sig")
        for title, url in re.findall(r"上一篇[：:]\s*\[([^\]]+)\]\((https?://[^\s)]+)\)", text):
            if urlparse(url).hostname == "aoff.whu.edu.cn":
                titles[title.strip()] = url
    pages = []
    for file in files:
        text = file.read_text(encoding="utf-8-sig").strip()
        title_match = re.search(r"^#+\s+(.+)", text, re.M)
        title = title_match.group(1).strip() if title_match else file.stem
        date = re.search(r"20\d{2}-\d{2}-\d{2}", text)
        # Navigation links point to another article and must stay out of retrieval.
        body = re.split(r"\n上一篇[：:]", text, maxsplit=1)[0].strip()
        if len(body) < 40:
            continue
        pages.append({
            "hash": hashlib.sha256(body.encode()).hexdigest(),
            "url": titles.get(title, ""),
            "source": "aoff",
            "category": file.parent.name,
            "title": title,
            "date": date.group() if date else "",
            "text": body,
            "source_path": str(file.relative_to(source)),
        })
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / "pages.jsonl"
    if target.exists():
        raise FileExistsError(f"Corpus already exists at {target}")
    with target.open("w", encoding="utf-8") as output:
        for page in pages:
            output.write(json.dumps(page, ensure_ascii=False) + "\n")
    print(f"Imported {len(pages)} local documents, {sum(bool(p['url']) for p in pages)} mapped article URLs.")


if __name__ == "__main__":
    main()
