"""HTML parsing helpers for the legal crawler."""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin


SKIP_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}


class LegalHTMLParser(HTMLParser):
    """Extract visible text, links, title, and light metadata from HTML."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self.meta: dict[str, str] = {}
        self._tag_stack: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        self._tag_stack.append(tag)
        attrs_dict = {key.lower(): value or "" for key, value in attrs}

        if tag in SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a" and attrs_dict.get("href"):
            self.links.append(urljoin(self.base_url, attrs_dict["href"]))
        if tag == "meta":
            name = attrs_dict.get("name") or attrs_dict.get("property")
            content = attrs_dict.get("content")
            if name and content:
                self.meta[name.lower()] = content.strip()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        if self._skip_depth == 0:
            self.text_parts.append(cleaned)

    @property
    def title(self) -> str:
        title = " ".join(self.title_parts).strip()
        if title:
            return title
        return self.meta.get("og:title", "").strip()

    @property
    def text(self) -> str:
        return "\n".join(self.text_parts).strip()


def parse_html(html: str, base_url: str) -> LegalHTMLParser:
    parser = LegalHTMLParser(base_url=base_url)
    parser.feed(html)
    return parser
