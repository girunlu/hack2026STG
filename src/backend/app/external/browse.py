"""Web search for the follow-up assistant — keyless, bounded, and never a substitute for the data.

The chatbot answers most questions from the client's own facts. When a question has no route there at
all ("is NVIDIA worth investing?"), the advisor still wants an answer, and the honest one is a *search
result*, not a model's memory: this module retrieves public pages and hands them to the LLM, which may
only summarise what those pages say.

Three rules keep it honest:

* the search is keyless (DuckDuckGo Lite) so the prototype needs no paid account, and it is switched
  off by ``URO_NEWS_OFFLINE`` — the same flag that disables market news, so a deterministic test run
  never reaches the network through this path either;
* a synthesis may not contain a figure that is not in the retrieved snippets, and it must name the
  results it used; anything else falls back to listing the sources themselves;
* every answer carries its URLs, and the caller labels it as a web result rather than bank data.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from ..i18n import DEFAULT_LANG

logger = logging.getLogger(__name__)

PROVIDER = "duckduckgo-lite"
# The keyless news feeds the market layer uses, as the second web source.
NEWS_PROVIDER = "news-feeds"
_ENDPOINT = "https://lite.duckduckgo.com/lite/"
_TIMEOUT = 10.0
_USER_AGENT = "Mozilla/5.0 (compatible; UNRISKOMEGA-Prototype/1.0; hackathon demo)"


def offline() -> bool:
    """Whether web access is disabled for this process.

    Shares ``URO_NEWS_OFFLINE`` with the market-news layer — one switch for "this run must not touch
    the network" — and adds ``URO_WEB_OFFLINE`` for turning only this path off.
    """
    for name in ("URO_WEB_OFFLINE", "URO_NEWS_OFFLINE"):
        if os.environ.get(name, "").strip().lower() not in ("", "0", "false", "no"):
            return True
    return False


class _LiteParser(HTMLParser):
    """Collect result links and their snippets from DuckDuckGo Lite's flat result table.

    ``HTMLParser`` rather than a regex: the snippets contain nested markup, and a pattern that works
    on today's layout silently produces garbage on a slightly different one.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._href: str | None = None
        self._buffer: list[str] = []
        self._in_link = False
        self._in_snippet = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = (dict(attrs).get("class") or "")
        if tag == "a" and "result-link" in classes:
            self._in_link = True
            self._href = dict(attrs).get("href") or ""
            self._buffer = []
        elif tag == "td" and "result-snippet" in classes:
            self._in_snippet = True
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_link:
            title = " ".join("".join(self._buffer).split())
            if title:
                self.rows.append({"title": title, "url": _resolve(self._href or ""), "snippet": ""})
            self._in_link = False
        elif tag == "td" and self._in_snippet:
            snippet = " ".join("".join(self._buffer).split())
            if snippet and self.rows and not self.rows[-1]["snippet"]:
                self.rows[-1]["snippet"] = snippet
            self._in_snippet = False

    def handle_data(self, data: str) -> None:
        if self._in_link or self._in_snippet:
            self._buffer.append(data)


def _resolve(href: str) -> str:
    """The real target of a result link: DuckDuckGo redirects through ``/l/?uddg=…``."""
    if not href:
        return ""
    if "uddg=" in href:
        query = parse_qs(urlparse(href).query)
        target = (query.get("uddg") or [""])[0]
        if target:
            return unquote(target)
    if href.startswith("//"):
        return f"https:{href}"
    return href


def _lite_results(query: str, limit: int) -> list[dict]:
    """DuckDuckGo Lite results, or ``[]``. Retried once: the endpoint refuses connections
    intermittently (measured), and a single refusal is not a reason to lose the advisor's answer."""
    for attempt in (1, 2):
        try:
            response = httpx.get(
                _ENDPOINT,
                params={"q": query},
                timeout=_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
        except Exception as error:
            logger.warning("web search attempt %s failed: %s", attempt, type(error).__name__)
            if attempt == 2:
                return []
            continue

        parser = _LiteParser()
        try:
            parser.feed(response.text)
        except Exception:
            logger.exception("could not parse the search response")
            return []

        seen: set[str] = set()
        found: list[dict] = []
        for row in parser.rows:
            url = row["url"]
            if not url or url in seen:
                continue
            seen.add(url)
            found.append(row)
            if len(found) >= limit:
                break
        if found:
            return found
    return []


def _news_results(query: str, limit: int, lang: str) -> list[dict]:
    """The market layer's keyless news feeds as a web fallback.

    The same Bing → Google → Yahoo chain the briefing uses, asked with the advisor's own words. It
    returns published pages with their publisher, which is exactly what this module needs to hand the
    model: fetchable sources with a title. Not as rich as a search result's snippet, but it is a
    second independent provider, so one provider's bad day does not cost the answer.
    """
    from . import news  # imported here so this module stays importable without the news layer

    result = news.fetch_for_query(query, limit=limit, lang=lang)
    return [
        {
            "title": str(item.get("headline") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "snippet": str(item.get("source") or "").strip(),
        }
        for item in (result.get("items") or [])
        if str(item.get("headline") or "").strip() and str(item.get("url") or "").strip()
    ]


def search(query: str, limit: int = 5, lang: str = DEFAULT_LANG) -> dict:
    """Search public sources. Never raises — a failure is declared, not thrown.

    Two keyless providers, in order: a web search that carries real snippets, then the news feeds the
    market layer already uses. Verified live that the first one intermittently refuses connections, so
    giving up after it would make the assistant feel broken for reasons outside its control.

    Returns:
        ``{"provider", "query", "fetched_at", "items": [{title, url, snippet}], "unavailable": [str]}``.
    """
    result: dict[str, Any] = {
        "provider": None,
        "query": query,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
        "unavailable": [],
    }
    text = (query or "").strip()
    if not text:
        result["unavailable"].append("empty query")
        return result
    if offline():
        result["unavailable"].append("web access is switched off (URO_NEWS_OFFLINE/URO_WEB_OFFLINE)")
        return result

    items = _lite_results(text, limit)
    if items:
        result["provider"] = PROVIDER
        result["items"] = items
        return result
    result["unavailable"].append(f"{PROVIDER} returned no usable result")

    items = _news_results(text, limit, lang)
    if items:
        result["provider"] = NEWS_PROVIDER
        result["items"] = items
        result["unavailable"] = [f"{PROVIDER} unavailable; used the news feeds"]
        return result
    result["unavailable"].append("no source answered")
    return result


def _numbers(text: str) -> set[str]:
    """Figures in a sentence, normalised so ``2'049'658`` and ``2049658`` compare equal."""
    tokens = re.findall(r"\d[\d'’.,:/-]*", text or "")
    return {re.sub(r"(?<=\d)[.,](?=\d{3}(?:\D|$))", "", t).replace("'", "").replace("’", "").replace(",", ".") for t in tokens if re.search(r"\d", t)}


def _prompt(lang: str) -> str:
    language = "German" if lang == "de" else "English"
    return (
        "You answer a wealth advisor's question using ONLY the web search results provided. "
        f"Write in {language}. "
        "Rules, without exception: every claim must be supported by those results; never add a figure, "
        "date, name or fact that is not in them; if the results do not answer the question, say so "
        "plainly instead of guessing; if sources disagree, say so. Two or three sentences. "
        "Return JSON only: {\"answer\": \"...\", \"used\": [0, 2]} where \"used\" lists the indices of "
        "the results your answer relies on."
    )


def synthesize(question: str, results: list[dict], lang: str = DEFAULT_LANG) -> dict:
    """Summarise the retrieved results into an answer, with every claim traceable to one of them.

    A synthesis that invents a figure, omits its sources or returns an unusable shape is rejected and
    reported as unavailable — the caller then shows the sources themselves, which is a smaller truth
    than a confident paragraph that nothing supports.
    """
    from . import llm  # imported here: the LLM is optional and this module must import without it

    if not results:
        return {"applied": False, "reason": "no results to summarise", "answer": None, "used": []}
    if not llm.available():
        return {
            "applied": False,
            "reason": "no key: set DEEPSEEK_API_KEY (and optionally URO_LLM_MODEL)",
            "answer": None,
            "used": [],
        }

    payload = {
        "model": llm.model(),
        "temperature": llm._TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _prompt(lang)},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": question,
                        "results": [
                            {"title": item.get("title"), "snippet": item.get("snippet"), "url": item.get("url")}
                            for item in results
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }

    try:
        raw = llm._chat(payload)
        parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
    except Exception as error:
        logger.warning("web synthesis failed: %s", type(error).__name__)
        return {"applied": False, "reason": f"{type(error).__name__}", "answer": None, "used": []}

    answer = str(parsed.get("answer") or "").strip() if isinstance(parsed, dict) else ""
    used = parsed.get("used") if isinstance(parsed, dict) else None
    if not answer:
        return {"applied": False, "reason": "reply carried no answer", "answer": None, "used": []}
    if not isinstance(used, list) or not used:
        return {"applied": False, "reason": "reply named no sources", "answer": None, "used": []}

    indices: list[int] = []
    for value in used:
        if isinstance(value, int) and 0 <= value < len(results):
            indices.append(value)
    if not indices:
        return {"applied": False, "reason": "reply named no usable source", "answer": None, "used": []}

    supported = set().union(*(_numbers(str(results[i].get("snippet") or "") + " " + str(results[i].get("title") or "")) for i in indices))
    if not _numbers(answer) <= supported:
        logger.warning("web answer carried a figure its sources do not; listing sources instead")
        return {"applied": False, "reason": "answer used a figure absent from its sources", "answer": None, "used": []}

    return {"applied": True, "reason": None, "answer": answer, "used": indices}
