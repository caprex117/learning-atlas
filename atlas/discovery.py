"""On-demand public feeds. URLs are fixed; document/user URLs are never fetched."""
from datetime import datetime, timezone
import re

import httpx
import feedparser

SOURCES = {"pandas · versiones": ("github", "https://api.github.com/repos/pandas-dev/pandas/releases"),
           "Streamlit · versiones": ("github", "https://api.github.com/repos/streamlit/streamlit/releases"),
           "arXiv · aprendizaje automático": ("rss", "https://rss.arxiv.org/rss/cs.LG")}


def fetch_feed(source, *, transport=None):
    kind, url = SOURCES[source]
    with httpx.Client(timeout=15, follow_redirects=False, transport=transport) as client:
        with client.stream("GET", url, headers={"User-Agent": "LearningAtlas/1.0 (personal learning tracker)",
                                               "Accept": "application/vnd.github+json" if kind == "github" else "application/rss+xml"}) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 3_000_000:
                    raise ValueError("La fuente excede el límite de lectura.")
    if kind == "github":
        import json
        rows = [{"title": r.get("name") or r["tag_name"], "url": r["html_url"], "published": r.get("published_at", ""),
                 "summary": "Nueva versión publicada en el repositorio oficial.", "kind": "topic"}
                for r in json.loads(body) if not r.get("draft") and not r.get("prerelease")][:8]
    else:
        feed = feedparser.parse(bytes(body))
        if not feed.entries and not feed.feed.get("title"):
            raise ValueError("La fuente no devolvió entradas legibles.")
        rows = [{"title": r.title, "url": r.link, "published": r.get("published", ""),
                 "summary": re.sub(r"<[^>]+>", "", r.get("summary", ""))[:500], "kind": "paper"} for r in feed.entries[:8]]
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "source": source, "items": rows}
