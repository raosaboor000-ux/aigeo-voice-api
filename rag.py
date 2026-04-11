"""
Scrape aigeo360.com, chunk text, and retrieve with BM25 (keyword-style ranking).
"""
from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from rank_bm25 import BM25Okapi

DEFAULT_BASE = "https://aigeo360.com"
USER_AGENT = "AI-Geo-Voice-Assistant/1.0 (+https://aigeo360.com; contact: info@aigeo360.com)"
REQUEST_TIMEOUT = 25.0
CRAWL_DELAY_SEC = 0.4


@dataclass
class Chunk:
    text: str
    url: str
    title: str


def _same_site(url: str, base_netloc: str) -> bool:
    try:
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return False
        host = (p.netloc or "").lower().removeprefix("www.")
        base = base_netloc.lower().removeprefix("www.")
        return host == base or host.endswith("." + base)
    except Exception:
        return False


def _normalize_url(url: str, base: str) -> Optional[str]:
    url = urldefrag(url.strip())[0]
    if not url:
        return None
    abs_url = urljoin(base, url)
    p = urlparse(abs_url)
    if p.scheme not in ("http", "https"):
        return None
    path = p.path or "/"
    if path.lower().endswith(
        (".pdf", ".zip", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp", ".mp4", ".mp3")
    ):
        return None
    if "wp-json" in path or "feed" in path.lower():
        return None
    return abs_url


def _visible_text_from_html(html: str, url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.find("title")
    title = title_el.get_text(strip=True) if title_el else url
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return title, text.strip()


def _chunk_text(text: str, max_chars: int = 520, overlap: int = 80) -> list[str]:
    if not text:
        return []
    paragraphs = re.split(r"\n\s*\n+", text)
    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(buf) + len(para) + 1 <= max_chars:
            buf = f"{buf}\n\n{para}".strip() if buf else para
            continue
        if buf:
            chunks.append(buf)
        if len(para) <= max_chars:
            buf = para
        else:
            start = 0
            while start < len(para):
                end = min(start + max_chars, len(para))
                piece = para[start:end].strip()
                if piece:
                    chunks.append(piece)
                start = end - overlap if end < len(para) else end
            buf = ""
    if buf:
        chunks.append(buf)
    return chunks


def tokenize(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


class SiteRAG:
    def __init__(self, base_url: str = DEFAULT_BASE):
        self.base_url = base_url.rstrip("/") + "/"
        self.base_netloc = urlparse(self.base_url).netloc
        self.chunks: list[Chunk] = []
        self._bm25: Optional[BM25Okapi] = None
        self._tokenized: list[list[str]] = []
        self.last_error: Optional[str] = None
        self.last_indexed_at: Optional[float] = None

    def is_ready(self) -> bool:
        return bool(self.chunks and self._bm25 is not None)

    def status(self) -> dict:
        return {
            "base_url": self.base_url,
            "chunk_count": len(self.chunks),
            "ready": self.is_ready(),
            "last_error": self.last_error,
            "last_indexed_at": self.last_indexed_at,
        }

    def crawl_and_index(
        self,
        max_pages: int = 45,
        max_depth: int = 2,
    ) -> int:
        self.last_error = None
        visited: set[str] = set()
        queue: deque[tuple[str, int]] = deque([(self.base_url.rstrip("/") + "/", 0)])
        all_chunks: list[Chunk] = []

        headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}

        with httpx.Client(follow_redirects=True, timeout=REQUEST_TIMEOUT, headers=headers) as client:
            while queue and len(visited) < max_pages:
                url, depth = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                html_text = ""
                try:
                    time.sleep(CRAWL_DELAY_SEC)
                    r = client.get(url)
                    r.raise_for_status()
                    ctype = (r.headers.get("content-type") or "").lower()
                    if "text/html" not in ctype and "application/xhtml" not in ctype:
                        continue
                    html_text = r.text
                    page_title, body = _visible_text_from_html(html_text, url)
                    for piece in _chunk_text(body):
                        if len(piece) < 40:
                            continue
                        all_chunks.append(Chunk(text=piece, url=url, title=page_title))
                except Exception as e:
                    self.last_error = f"{url}: {e}"
                    continue

                if depth >= max_depth or not html_text:
                    continue
                try:
                    soup = BeautifulSoup(html_text, "lxml")
                    for a in soup.find_all("a", href=True):
                        href = a.get("href")
                        if not href:
                            continue
                        nxt = _normalize_url(href, url)
                        if not nxt or not _same_site(nxt, self.base_netloc):
                            continue
                        if nxt not in visited and len(visited) + len(queue) < max_pages * 3:
                            queue.append((nxt, depth + 1))
                except Exception:
                    continue

        self.chunks = all_chunks
        self._tokenized = [tokenize(c.text + " " + c.title) for c in self.chunks]
        if self._tokenized:
            self._bm25 = BM25Okapi(self._tokenized)
        else:
            self._bm25 = None
        self.last_indexed_at = time.time()
        return len(self.chunks)

    def retrieve(self, query: str, top_k: int = 6) -> list[Chunk]:
        if not self._bm25 or not self.chunks or not query.strip():
            return []
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        scores = self._bm25.get_scores(q_tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out: list[Chunk] = []
        for i in ranked[:top_k]:
            if scores[i] <= 0:
                continue
            out.append(self.chunks[i])
        if not out and ranked:
            for i in ranked[:top_k]:
                out.append(self.chunks[i])
        return out[:top_k]
