import hashlib
from urllib.parse import urljoin

import trafilatura
from trafilatura.settings import Document

from brief.contracts import Source
from brief.crawl.fetch import normalize_url

EXTRACTION_VERSION = "trafilatura-v2"


def source_id(url: str) -> str:
    return "src_" + hashlib.sha256(url.encode()).hexdigest()[:20]


def extract_page(body: bytes, url: str) -> tuple[Source | None, list[str]]:
    tree = trafilatura.load_html(body)
    if tree is None:
        return None, []
    links = []
    primary_links = tree.xpath('//main//a[@href]/@href | //article//a[@href]/@href | //*[@role="main"]//a[@href]/@href')
    for href in (primary_links + tree.xpath("//a[@href]/@href"))[:1000]:
        try:
            link = normalize_url(urljoin(url, href.strip()))
        except ValueError:
            continue
        if link not in links:
            links.append(link)
    document = trafilatura.bare_extraction(
        body,
        url=url,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        with_metadata=True,
    )
    assert document is None or isinstance(document, Document)
    content = document.text if document else None
    # Precision mode can reduce product catalogs to prices. Use Trafilatura's recall
    # mode for short, link-heavy pages so product/resource names remain evidence.
    if sum(c.isalpha() for c in (content or "")) < 150 and len(links) >= 5:
        recalled = trafilatura.bare_extraction(
            body, url=url, include_comments=False, favor_recall=True, with_metadata=True
        )
        assert recalled is None or isinstance(recalled, Document)
        if recalled and len(recalled.text or "") > len(content or ""):
            document, content = recalled, recalled.text
    if document is None or not content or len(content.strip()) < 40:
        # Navigation, empty app shells and error pages are not usable source evidence.
        return None, links
    title_nodes = tree.xpath("//title/text()") or tree.xpath("//h1//text()")
    title = " ".join(" ".join(title_nodes).split()) or (document.title if document else None)
    if not title:
        title = url
    descriptions = tree.xpath(
        '//meta[translate(@name,"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz")="description"]/@content'
    )
    if not descriptions:
        descriptions = tree.xpath('//meta[@property="og:description"]/@content')
    description = " ".join((descriptions[0] if descriptions else (document.description or "")).split())
    source = Source(
        id=source_id(url),
        url=url,
        title=title[:500],
        description=description[:1500],
        content=content.strip()[:12000],
    )
    return source, links
