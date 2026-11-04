"""
core/intelligence/research/arxiv_client.py — Evidence-based arXiv scientific paper research client.
"""
from __future__ import annotations

import logging
import ssl
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("JARVIS.ArxivClient")

_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


@dataclass
class ArxivPaper:
    """Structured representation of a peer-reviewed or pre-print arXiv publication."""
    title: str
    authors: List[str]
    summary: str
    url: str
    published_date: str
    arxiv_id: str
    categories: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "authors": self.authors,
            "summary": self.summary,
            "url": self.url,
            "published_date": self.published_date,
            "arxiv_id": self.arxiv_id,
            "categories": self.categories,
        }

    def citation(self) -> str:
        author_str = self.authors[0] + " et al." if len(self.authors) > 1 else (self.authors[0] if self.authors else "Unknown")
        year = self.published_date[:4] if len(self.published_date) >= 4 else "n.d."
        return f"{author_str} ({year}). \"{self.title}\". arXiv:{self.arxiv_id} [<{self.url}>]"


class ArxivClient:
    """Queries the open arXiv Export API and extracts verified paper metadata."""

    def __init__(self, timeout: int = 12):
        self._timeout = timeout
        self._ssl_context = self._create_ssl_context()

    def _create_ssl_context(self) -> ssl.SSLContext:
        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            try:
                return ssl.create_default_context()
            except Exception:
                return ssl._create_unverified_context()

    def search(self, query: str, max_results: int = 5) -> List[ArxivPaper]:
        """
        Executes a targeted keyword query against the official arXiv API.
        Returns parsed ArxivPaper records with real titles, authors, and abstracts.
        """
        clean_query = query.strip()
        if not clean_query:
            return []

        # Construct safe query parameters
        encoded_query = urllib.parse.quote_plus(clean_query)
        url = (
            f"https://export.arxiv.org/api/query?"
            f"search_query=all:{encoded_query}&start=0&max_results={max_results}"
            f"&sortBy=relevance&sortOrder=descending"
        )

        headers = {
            "User-Agent": "JARVIS-008/1.0 (Autonomous Agent Research Client; mailto:contact@jarvis.ai)"
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=self._ssl_context, timeout=self._timeout) as resp:
                xml_data = resp.read()
                return self._parse_atom_response(xml_data)
        except Exception as e:
            logger.warning("arXiv API request failed for '%s': %s", clean_query, e)
            return []

    def _parse_atom_response(self, xml_bytes: bytes) -> List[ArxivPaper]:
        papers: List[ArxivPaper] = []
        try:
            root = ET.fromstring(xml_bytes)
            entries = root.findall("atom:entry", _ATOM_NS)

            for entry in entries:
                # Title
                title_elem = entry.find("atom:title", _ATOM_NS)
                title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Untitled"

                # Authors
                authors: List[str] = []
                for author_elem in entry.findall("atom:author", _ATOM_NS):
                    name_elem = author_elem.find("atom:name", _ATOM_NS)
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())

                # Abstract / Summary
                summary_elem = entry.find("atom:summary", _ATOM_NS)
                summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""

                # Canonical URL / ID
                id_elem = entry.find("atom:id", _ATOM_NS)
                raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                url = raw_id
                # Extract clean arxiv_id e.g. "2401.12345"
                arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

                # Published date
                pub_elem = entry.find("atom:published", _ATOM_NS)
                published = pub_elem.text.strip() if pub_elem is not None and pub_elem.text else ""

                # Categories
                categories: List[str] = []
                for cat in entry.findall("atom:category", _ATOM_NS):
                    term = cat.get("term")
                    if term:
                        categories.append(term)

                papers.append(
                    ArxivPaper(
                        title=title,
                        authors=authors or ["Anonymous"],
                        summary=summary,
                        url=url,
                        published_date=published,
                        arxiv_id=arxiv_id,
                        categories=categories,
                    )
                )
        except Exception as e:
            logger.error("Failed to parse arXiv Atom response: %s", e)

        return papers


_arxiv_client_instance: Optional[ArxivClient] = None


def get_arxiv_client() -> ArxivClient:
    global _arxiv_client_instance
    if _arxiv_client_instance is None:
        _arxiv_client_instance = ArxivClient()
    return _arxiv_client_instance

