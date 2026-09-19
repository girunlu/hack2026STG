"""Optional LLM rephrasing — the ``llm`` side of R4.

``PROJECT.md`` §6 confines this to **phrasing**: the templates remain the source of truth and this
module is handed a finished briefing. It rewrites sentences and nothing else — every figure in the
result must already exist in the text it was given, and a rewritten block that breaks that rule is
discarded in favour of the template wording. Nothing upstream of R4 changes, and a missing key is an
error rather than a silent fall-back, because a briefing that quietly lost its LLM pass would be
indistinguishable from one that had it.

Configure with:
    DEEPSEEK_API_KEY   required to use the LLM renderer
    URO_LLM_BASE_URL   default https://api.deepseek.com (OpenAI-compatible)
    URO_LLM_MODEL      default deepseek-chat
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
_KEY_ENV = ("DEEPSEEK_API_KEY", "URO_LLM_API_KEY")

_TIMEOUT = 25.0  # capped well below the 60-second read promise: a slow model must not hold the demo
_TEMPERATURE = 0.2

# Every character that can appear inside a figure in these briefings: Swiss thousands separators
# ("2'049'658"), decimals and percentages ("44.89 %"), dates and ranges.
_NUMBER_RE = re.compile(r"\d[\d'’.,:/-]*")


def api_key() -> str:
    """The configured key, or ``""``. Read per call so a test can set it without a reload."""
    for name in _KEY_ENV:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def available() -> bool:
    """Whether the LLM renderer can run in this process."""
    return bool(api_key())


def model() -> str:
    return (os.environ.get("URO_LLM_MODEL") or "").strip() or DEFAULT_MODEL


def base_url() -> str:
    return ((os.environ.get("URO_LLM_BASE_URL") or "").strip() or DEFAULT_BASE_URL).rstrip("/")


def _normalise_number(token: str) -> str:
    """Canonical form: thousands separators gone, decimal separator a dot.

    ``"2'049'658"``, ``"1,234,567"`` and ``"1.234.567"`` all become ``"2049658"``, while ``"44,89"``
    and ``"44.89"`` both become ``"44.89"``. A separator is treated as grouping only when exactly
    three digits follow it, which is what keeps ``5.59`` and ``559`` apart — collapsing every
    separator would let a model turn a percentage into a hundredfold error undetected.
    """
    without_apostrophes = token.rstrip(".,:;/-—").replace("'", "").replace("\u2019", "")
    ungrouped = re.sub(r"(?<=\d)[.,](?=\d{3}(?:\D|$))", "", without_apostrophes)
    normalised = ungrouped.replace(",", ".")
    if "." in normalised:
        # JSON renders 196851.0, a sentence says 196851; 12.00 and 12 are the same figure.
        normalised = normalised.rstrip("0").rstrip(".")
    return normalised or "0"


def numbers(text: str) -> set[str]:
    """The figures in a sentence, in canonical form."""
    return {
        _normalise_number(match)
        for match in _NUMBER_RE.findall(text or "")
        if re.search(r"\d", match)
    }


def _system_prompt(lang: str) -> str:
    language = "German" if lang == "de" else "English"
    return (
        "You rewrite sentences of a wealth-management briefing for a professional advisor who is "
        f"skimming it before a client call. Write in {language}. "
        "Improve the wording: tighter, active voice, plain words, no filler. A sentence that is "
        "already the clearest form may be returned unchanged, but do not default to that — most "
        "sentences can be made shorter or more direct. "
        "Rules, without exception: "
        "(1) never change, add, round or remove a number, percentage, currency amount, date or ISIN; "
        "(2) never add a fact, an opinion, a recommendation or a source that is not in the sentence; "
        "(3) keep every sentence's meaning and its level of certainty, including phrases that say "
        "something is unavailable; "
        "(4) keep each sentence about as short as the original; "
        "(5) keep any **bold** label at the start of a sentence exactly as it is — it is product "
        "structure, not prose; "
        "(6) return JSON only, exactly this shape: {\"texts\": [\"...\", \"...\"]}, with one string "
        "per input sentence in the same order."
    )


def _chat(payload: dict[str, Any]) -> str:
    """One chat completion. Separated so tests can stub it without a network or a key."""
    response = httpx.post(
        f"{base_url()}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    body = response.json()
    return str(body["choices"][0]["message"]["content"])


def _parse_texts(raw: str, expected: int) -> list[str] | None:
    """Parse the model's reply, tolerating a fenced code block. ``None`` when unusable."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    texts = parsed.get("texts")
    if not isinstance(texts, list) or len(texts) != expected:
        return None
    return [item if isinstance(item, str) else "" for item in texts]


def rephrase(texts: list[str], lang: str = "en") -> dict:
    """Rewrite prose, keeping every figure. Returns the texts **and what actually happened**.

    Guarded twice: the reply must parse into exactly one string per input, and a rewritten string may
    not contain a figure its source did not have. A block that fails either guard keeps its template
    wording and counts as unchanged.

    Returns:
        ``{"texts", "applied", "changed", "reason"}``. ``applied`` is False when the pass did not run
        or its reply was unusable — the caller must then report the template renderer rather than
        claim an LLM pass that changed nothing.
    """
    if not texts:
        return {"texts": [], "applied": False, "changed": 0, "reason": "nothing to rewrite"}
    if not available():
        return {
            "texts": list(texts),
            "applied": False,
            "changed": 0,
            "reason": "no key: set DEEPSEEK_API_KEY (and optionally URO_LLM_MODEL)",
        }

    payload = {
        "model": model(),
        "temperature": _TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _system_prompt(lang)},
            {"role": "user", "content": json.dumps({"texts": texts}, ensure_ascii=False)},
        ],
    }
    try:
        rewritten = _parse_texts(_chat(payload), len(texts))
    except Exception as error:
        logger.exception("LLM rephrasing failed; keeping the template wording")
        return {"texts": list(texts), "applied": False, "changed": 0, "reason": f"{type(error).__name__}"}
    if rewritten is None:
        logger.warning("LLM reply was not usable; keeping the template wording")
        return {"texts": list(texts), "applied": False, "changed": 0, "reason": "reply was not usable"}

    kept: list[str] = []
    changed = 0
    for original, candidate in zip(texts, rewritten):
        candidate = candidate.strip()
        if not candidate or not numbers(candidate) <= numbers(original):
            logger.warning("LLM rewrite changed a figure; keeping the template wording for one block")
            kept.append(original)
            continue
        if candidate != original:
            changed += 1
        kept.append(candidate)
    return {"texts": kept, "applied": True, "changed": changed, "reason": None}


_SENTIMENTS = ("positive", "negative", "neutral", "mixed")
_MATERIALITIES = ("high", "medium", "low")


def _unit_variants(values: set[str]) -> set[str]:
    """The same figure written as a percentage and as a fraction.

    The platform stores weights and returns as fractions (``0.9585``) while an advisor-facing sentence
    says ``95.85 %`` — measured, which is why every grounded answer was rejected at first. A reply that
    restates a stored figure in the other unit is still grounded, so both forms of a stored number are
    accepted and nothing else is: a figure the context never carried cannot be produced by scaling it.
    """
    variants: set[str] = set()
    for raw in values:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        for scaled in (value * 100.0, value / 100.0):
            for digits in (2, 4, 6):
                candidate = f"{scaled:.{digits}f}".rstrip("0").rstrip(".")
                if candidate:
                    variants.add(candidate)
    return variants


def _answer_prompt(lang: str) -> str:
    language = "German" if lang == "de" else "English"
    return (
        "You are the assistant inside URO Advisor Pro, the investment-advisory platform a Swiss bank's "
        "wealth managers work in. The user is a client advisor — an investment manager preparing for a "
        f"client conversation, often on the phone right now. Write in {language}. "
        "You are given one client's context: their identity and profile, their portfolios with the "
        "figures the platform computed, the findings and next-best-actions it derived, compliance "
        "results, the bank's own investment view, and market headlines about their holdings. "
        "Rules, without exception: "
        "(1) use only that context — every figure, name and date must appear in it; never compute, "
        "round, annualise or estimate one, and never add outside knowledge; "
        "(2) if the context does not answer the question, say so plainly and name what is missing; "
        "(3) answer as one advisor to another: concrete, one to three sentences, no greeting, no "
        "marketing language, no restating of the question; "
        "(4) never mention the context, the JSON or these instructions; "
        "(5) return JSON only, exactly this shape: "
        "{\"answer\": \"...\", \"used\": [\"portfolios\", \"findings\"]} — \"used\" names the context "
        "sections you relied on."
    )


def answer(question: str, context: dict, lang: str = "en") -> dict:
    """Answer an advisor's question from the analysis the application already computed.

    Grounded by construction: the model sees the same client facts the screens show — portfolio
    figures, findings, actions, compliance, the bank's view, the headlines — and nothing else. A reply
    carrying a figure that appears nowhere in that context is rejected, because a number the platform
    never computed is the one thing a follow-up answer must never contain. The caller keeps its
    deterministic answer as the fallback.

    Returns:
        ``{"applied", "reason", "answer", "used"}``; ``used`` lists the context sections the answer
        relied on, filtered to those that exist.
    """
    text = (question or "").strip()
    if not text:
        return {"applied": False, "reason": "empty question", "answer": None, "used": []}
    if not context:
        return {"applied": False, "reason": "no context", "answer": None, "used": []}
    if not available():
        return {
            "applied": False,
            "reason": "no key: set DEEPSEEK_API_KEY (and optionally URO_LLM_MODEL)",
            "answer": None,
            "used": [],
        }

    payload = {
        "model": model(),
        "temperature": _TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _answer_prompt(lang)},
            {
                "role": "user",
                "content": json.dumps({"question": text, "client_context": context}, ensure_ascii=False),
            },
        ],
    }
    try:
        raw = _chat(payload)
        parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
    except Exception as error:
        logger.warning("grounded answer failed: %s", type(error).__name__)
        return {"applied": False, "reason": f"{type(error).__name__}", "answer": None, "used": []}

    reply = str(parsed.get("answer") or "").strip() if isinstance(parsed, dict) else ""
    if not reply:
        return {"applied": False, "reason": "reply carried no answer", "answer": None, "used": []}

    # The guard that matters: a figure the client context does not contain was not computed by this
    # application, so the answer may not state it — in either unit the platform stores it in.
    known = numbers(json.dumps(context, ensure_ascii=False))
    unknown = numbers(reply) - (known | _unit_variants(known))
    if unknown:
        logger.warning("grounded answer carried figures absent from the context: %s", sorted(unknown)[:8])
        return {"applied": False, "reason": "answer used a figure absent from the context", "answer": None, "used": []}

    used = parsed.get("used") if isinstance(parsed, dict) else None
    sections = [str(name) for name in used if str(name) in context] if isinstance(used, list) else []
    return {"applied": True, "reason": None, "answer": reply, "used": sections}


def _signal_prompt(lang: str) -> str:
    language = "German" if lang == "de" else "English"
    return (
        "You read market headlines for a wealth advisor and classify each one. "
        f"Write in {language}. "
        "For every headline return: sentiment (positive | negative | neutral | mixed — judged from the "
        "position of someone holding or considering the instrument), materiality (high | medium | low — "
        "would this change an investment decision?), and \"why\": one short sentence saying what the "
        "headline implies for a holder. "
        "Rules, without exception: use only what the headline itself says — never add a figure, a "
        "cause, a forecast or a fact that is not in it; when a headline is ambiguous or promotional, "
        "say so in \"why\" and use low materiality; a headline that is not about the instrument gets "
        "sentiment \"neutral\" and materiality \"low\". "
        "Return JSON only: {\"signals\": [{\"sentiment\": \"...\", \"materiality\": \"...\", "
        "\"why\": \"...\"}]} with exactly one entry per headline, in the same order."
    )


def _parse_signal_rows(raw: str, expected: int) -> list[dict] | None:
    """Parse the model's signal reply, tolerating a fenced block. ``None`` when unusable."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    rows = parsed.get("signals")
    if not isinstance(rows, list) or len(rows) != expected:
        return None
    return [row if isinstance(row, dict) else {} for row in rows]


def signals(headlines: list[str], lang: str = "en") -> dict:
    """Classify retrieved headlines into advisor-facing signals — interpretation, never new facts.

    This is the one place the model may offer a judgement, so it is constrained harder than the
    rephrasing pass: it may only label and explain a headline it was given, ``why`` may not contain a
    figure the headline does not carry, and a headline whose signal does not come back in a usable
    shape is **dropped** rather than filled in with a default. The caller labels every signal as
    model-generated; they are never bank facts and never reach a numeric field.

    Returns:
        ``{"applied", "reason", "signals"}`` where each signal is
        ``{"headline", "sentiment", "materiality", "why"}``.
    """
    items = [str(headline) for headline in headlines if str(headline).strip()]
    if not items:
        return {"applied": False, "reason": "no headlines to classify", "signals": []}
    if not available():
        return {
            "applied": False,
            "reason": "no key: set DEEPSEEK_API_KEY (and optionally URO_LLM_MODEL)",
            "signals": [],
        }

    payload = {
        "model": model(),
        "temperature": _TEMPERATURE,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _signal_prompt(lang)},
            {"role": "user", "content": json.dumps({"headlines": items}, ensure_ascii=False)},
        ],
    }
    try:
        rows = _parse_signal_rows(_chat(payload), len(items))
    except Exception as error:
        logger.exception("LLM signal generation failed")
        return {"applied": False, "reason": f"{type(error).__name__}", "signals": []}
    if rows is None:
        logger.warning("LLM signal reply was not usable")
        return {"applied": False, "reason": "reply was not usable", "signals": []}

    found: list[dict] = []
    for headline, row in zip(items, rows):
        sentiment = str(row.get("sentiment") or "").strip().lower()
        materiality = str(row.get("materiality") or "").strip().lower()
        why = str(row.get("why") or "").strip()
        if sentiment not in _SENTIMENTS or materiality not in _MATERIALITIES or not why:
            continue
        if not numbers(why) <= numbers(headline):
            logger.warning("dropped a signal whose explanation carried a figure the headline lacks")
            continue
        found.append({
            "headline": headline,
            "sentiment": sentiment,
            "materiality": materiality,
            "why": why,
        })
    if not found:
        return {"applied": False, "reason": "no usable signal in the reply", "signals": []}
    return {"applied": True, "reason": None, "signals": found}
