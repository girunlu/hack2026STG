"""R4 — storyline composer, template renderer.

Turns the ``BriefingFacts`` bundle into the briefing object of ``notes-task/PROJECT.md`` §5.3: the three
required sections, the four answers, and a traceability index so a juror can point at any sentence and
see the field it came from.

Two renderers are interchangeable by contract: ``template`` (this module, no key required) and ``llm``
(phrasing only — it may never compute a number or add a fact). The LLM pass runs *on top of* the
template result, so the deterministic output stays the source of truth and a failed rewrite costs
nothing; asking for ``llm`` without a key raises rather than silently degrading.

Readability is enforced, not hoped for: ``WORD_BUDGET`` words is ~60 seconds of reading, so the lowest
severity blocks are dropped until the briefing fits, and every drop is disclosed in the section instead
of being silently discarded.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..fields import RATIO, label as field_label
from ..i18n import DEFAULT_LANG, t
from ..text import compact
from . import format as fmt

TEMPLATE = "template"
LLM = "llm"
RENDERERS = (TEMPLATE, LLM)
WORDS_PER_SECOND = 3.33  # ≈200 words/minute: the brief's 60-second target
WORD_BUDGET = 210
MAX_MARKET_ITEMS = 2
MAX_ACTIONS = 3
# Anticipated client questions are a preparation aid, not part of the 60-second read.
CLIENT_QUESTIONS_MAX = 3
MAX_PORTFOLIO_BLOCKS = 2
MAX_DRIFT_BLOCKS = 1
NAME_LIMIT = 46
TITLE_LIMIT = 88

# The brief names its three sections in English; the product is bilingual, so the title comes from the
# catalogue while the ``id`` stays stable for every consumer (UI anchors, T1 snapshots).
SECTION_KEYS = {
    "recent_development": "section.recent_development",
    "health_check": "section.health_check",
    "outlook_actions": "section.outlook_actions",
}

SEVERITY_RANK = {"high": 3, "medium": 2, "low": 1}

RULE_TITLE_PREFIXES = ("Regelverletzung: ", "Regelverstoss: ", "Rule violation: ")


class EvidenceIndex:
    """Every claim's provenance, keyed so a block can reference it and the UI can resolve it."""

    def __init__(self) -> None:
        self._entries: dict[str, dict] = {}

    def add(self, entry_id: str, label: str, value: Any, source: str, path: str,
            unit: str | None = None) -> str:
        """Register one evidence entry.

        ``unit="ratio"`` gives the card a display text in the same unit as the sentence it supports
        (``12.73%`` beside "volatility 12.73%"); the numeric ``value`` is never rescaled, so consumers
        keep computing with the raw fraction.
        """
        numeric = isinstance(value, (int, float)) and not isinstance(value, bool)
        self._entries[entry_id] = {
            "label": label,
            "value": value if not isinstance(value, (dict, list)) else None,
            "value_text": _readable(value) or (fmt.fraction(value) if unit == RATIO and numeric else None),
            "source": source,
            "path": path,
        }
        return entry_id

    def from_finding(self, finding: dict) -> list[str]:
        """Register a finding's own evidence entries plus the finding itself."""
        finding_id = str(finding.get("id"))
        refs = [self.add(f"finding:{finding_id}", str(finding.get("title") or finding_id), None, "R3", "")]
        for position, evidence in enumerate(finding.get("evidence") or []):
            refs.append(self.add(
                f"finding:{finding_id}#{position}",
                str(evidence.get("label") or "Evidenz"),
                evidence.get("value"),
                str(evidence.get("source") or ""),
                str(evidence.get("path") or ""),
                str(evidence.get("unit") or "") or None,
            ))
        return refs

    def as_dict(self) -> dict:
        return dict(self._entries)


def _readable(value: Any) -> str | None:
    """Render a non-scalar evidence value as text, so a dict never leaks into a sentence."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return None
    if isinstance(value, dict):
        parts = [f"{key}={_readable(item) or item}" for key, item in value.items() if item is not None]
        return ", ".join(parts)
    if isinstance(value, list):
        return f"{len(value)} Einträge"
    return str(value)


def findings_of(facts: dict, *types: str) -> list[dict]:
    """Findings of the given types, best first (R3 already ordered by score, re-sorted defensively)."""
    wanted = set(types)
    rows = [f for f in facts.get("findings") or [] if f.get("type") in wanted]
    return sorted(rows, key=lambda f: (-float(f.get("score") or 0.0), -SEVERITY_RANK.get(str(f.get("severity")), 0)))


def evidence_value(finding: dict, *keywords: str) -> Any:
    """Value of the first evidence entry whose label mentions one of the keywords, else ``None``."""
    for evidence in finding.get("evidence") or []:
        label = str(evidence.get("label") or "").lower()
        if any(keyword.lower() in label for keyword in keywords):
            value = evidence.get("value")
            if isinstance(value, (dict, list)):
                continue
            return value
    return None


def binding_detail(finding: dict, lang: str = DEFAULT_LANG) -> tuple[float | None, float | None, str | None, str]:
    """The engine's binding comparison, the field it compared, and that field's unit.

    ``ViolationPath`` rows mix type guards (``13.0 vs 13.0``) with the actual comparison
    (``0.1264 vs 0.12``); the meaningful pair is the one where the two sides actually differ. The
    field name is mechanically trimmed and translated (``SimulationVolatilityRuleField`1`` →
    ``Volatility``) so the briefing can name the rule without repeating a paragraph of regulation.

    The unit travels with the pair so the health check and the action catalogue print the same
    number the same way. The engine compares 0–1 volatility fractions, which the reader expects as
    percentages — printing ``0.1264`` in one place and ``12.6384%`` in the next is the defect this
    closes. Contract-class fields (client type, security type) keep their unit-less values.
    """
    best: tuple[float, float] | None = None
    best_label: str | None = None
    best_unit = "value"
    best_delta = 0.0
    for evidence in finding.get("evidence") or []:
        value = evidence.get("value")
        if not isinstance(value, dict):
            continue
        left, right = value.get("left"), value.get("right")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)) or isinstance(left, bool):
            continue
        delta = abs(float(left) - float(right)) / max(abs(float(right)), 1e-9)
        if delta > best_delta:
            best_delta, best = delta, (float(left), float(right))
            best_label = field_label(str(evidence.get("label") or ""), lang)
            best_unit = str(evidence.get("unit") or "value")
    if not best:
        return None, None, None, "value"
    return best[0], best[1], best_label, best_unit


def engine_number(value: float | None, unit: str) -> str:
    """A ``ViolationPath`` number in the unit the engine compared: ``12.64%`` or ``13``."""
    if value is None:
        return "—"
    if unit == RATIO:
        return fmt.fraction(value)
    return fmt.amount(value, 0) if float(value).is_integer() else fmt.amount(value, 2)


def binding_pair(finding: dict, lang: str = DEFAULT_LANG) -> tuple[float | None, float | None]:
    """The left/right values of the binding comparison (see :func:`binding_detail`)."""
    left, right, _, _ = binding_detail(finding, lang)
    return left, right


def relation_label(relation: str, lang: str = DEFAULT_LANG) -> str:
    """A house-view relation in words. The raw value stays the stable key inside ``facts``."""
    if not relation:
        return ""
    return t(f"relation.{str(relation).replace(' ', '_')}", lang)


def rule_label(finding: dict) -> str:
    """A violation's rule name without R3's ``Regelverletzung:`` prefix."""
    title = str(finding.get("title") or "")
    for prefix in RULE_TITLE_PREFIXES:
        if title.startswith(prefix):
            title = title[len(prefix):]
            break
    return compact(title, TITLE_LIMIT)


def _portfolio_label(portfolio: dict) -> str:
    name = portfolio.get("name") or ""
    return f"{portfolio.get('nr')} ({name})" if name else str(portfolio.get("nr"))


def _block(index: EvidenceIndex, text: str, refs: Iterable[str], severity: str | None = None,
           source_kind: str = "portfolio", security_id: int | None = None,
           isin: str | None = None) -> dict:
    """One rendered block.

    ``security_id``/``isin`` are set when the block is *about one instrument*, which is what lets the
    UI offer that instrument's market results next to the sentence. They are omitted, not nulled, for
    blocks that are about the portfolio, a currency or a rule.
    """
    block = {
        "text": fmt.sentence(text),
        "evidence_refs": [ref for ref in refs if ref],
        "severity": severity,
        "source_kind": source_kind,
    }
    if security_id is not None or isin:
        block["security_id"] = security_id
        block["isin"] = isin
    return block


def _note_block(text: str) -> dict:
    return {"text": fmt.sentence(text), "evidence_refs": [], "severity": "low", "source_kind": "gap"}


# --------------------------------------------------------------------------------- sections


def _recent_development(facts: dict, index: EvidenceIndex, lang: str = "en") -> tuple[dict, set[int]]:
    """Build section 1 and return (section, used_security_ids)."""
    blocks: list[dict] = []
    portfolios = list(facts.get("portfolios") or [])

    for portfolio in portfolios[:MAX_PORTFOLIO_BLOCKS]:
        label = _portfolio_label(portfolio)
        twelve, three = portfolio.get("return_12m_pct"), portfolio.get("return_3m_pct")
        avail, avail_days = portfolio.get("return_available_pct"), portfolio.get("return_available_days")
        history_path = f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].PerformanceHistory"
        refs = [
            index.add(
                f"portfolio:{portfolio['nr']}:return_12m_pct",
                t("question.perf_12m", lang),
                portfolio.get("return_12m_pct"),
                "clients.json",
                history_path,
            ),
            index.add(
                f"portfolio:{portfolio['nr']}:return_3m_pct",
                t("question.perf_3m", lang),
                portfolio.get("return_3m_pct"),
                "clients.json",
                history_path,
            ),
        ]
        if avail is not None:
            refs.append(index.add(
                f"portfolio:{portfolio['nr']}:return_available_pct",
                t("question.perf_available", lang),
                avail,
                "clients.json",
                history_path,
            ))
        # A portfolio can have history without a twelve-month figure (a new client), or no series at
        # all — an ex-custody statement is exactly that case. Each case gets its own sentence: never
        # assert a direction next to a missing number.
        if twelve is not None:
            direction = t("block.up", lang) if twelve >= 0 else t("block.down", lang)
            text = (t("block.portfolio_12m_direction", lang, label=label, direction=direction,
                      twelve=fmt.pct(twelve, signed=True), three=fmt.pct(three, signed=True))
                    if three is not None else
                    t("block.portfolio_12m_only", lang, label=label, direction=direction,
                      twelve=fmt.pct(twelve, signed=True)))
        elif three is not None:
            text = t("block.portfolio_3m_only", lang, label=label, three=fmt.pct(three, signed=True))
        elif avail is not None:
            text = t("block.portfolio_available_return", lang, label=label,
                     pct=fmt.pct(avail, signed=True), days=avail_days)
        else:
            text = t("block.portfolio_no_history", lang, label=label)
        blocks.append(_block(index, text, refs))

    if len(portfolios) > MAX_PORTFOLIO_BLOCKS:
        blocks.append(_note_block(t("block.more_portfolios", lang, count=len(portfolios) - MAX_PORTFOLIO_BLOCKS)))

    for finding in findings_of(facts, "performance_driver")[:1]:
        contribution = evidence_value(finding, "contribution")
        # Must match R3's own field label exactly: a looser "volatility" keyword also matches
        # "ContributionVolatility" and would make every driver look like 100% of the risk.
        volatility = evidence_value(finding, "portfolio.volatility")
        share = (
            float(contribution) / float(volatility)
            if isinstance(contribution, (int, float)) and isinstance(volatility, (int, float)) and volatility
            else None
        )
        name = compact(str(finding.get("title") or "").split(" treibt")[0], NAME_LIMIT)
        tail = t("block.risk_contribution", lang, share=fmt.fraction(share)) if share is not None else ""
        blocks.append(_block(
            index,
            f"**{t('block.driver', lang)}:** {name}{tail}",
            index.from_finding(finding),
        ))

    for finding in findings_of(facts, "material_change")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.material_change', lang)}:** {finding.get('title')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "stale_data")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.data_as_of', lang)}:** {finding.get('detail')}",
            index.from_finding(finding),
            "low",
        ))

    # Add first market item to section 1 (if available)
    market_items = facts.get("market_context") or []
    used_security_ids: set[int] = set()
    if market_items:
        item = market_items[0]
        ref = index.add(
            f"news:{item.get('url') or item.get('headline')}",
            str(item.get("headline")),
            item.get("published"),
            str(item.get("source") or t("question.market_source", lang)),
            str(item.get("url") or ""),
        )
        blocks.append(_block(
            index,
            f"**{t('block.market', lang)}:** {compact(item.get('headline'), TITLE_LIMIT)} — {item.get('relevant_because')}",
            [ref], None, "external",
            security_id=item.get("security_id"), isin=item.get("isin"),
        ))
        # Track which security IDs this item mentions
        used_security_ids = set(item.get("linked_security_ids") or [])

    section = {"id": "recent_development", "title": t(SECTION_KEYS["recent_development"], lang), "blocks": blocks}
    return section, used_security_ids


def _health_check(facts: dict, index: EvidenceIndex, lang: str = "en") -> dict:
    blocks: list[dict] = []

    for finding in findings_of(facts, "liquidity_event")[:1]:
        equity = evidence_value(finding, "equity", "eigenkapital")
        suffix = t("block.equity_share", lang, share=fmt.fraction(equity)) if isinstance(equity, (int, float)) else ""
        blocks.append(_block(
            index,
            f"**{t('block.liquidity', lang)}:** {finding.get('title')}{suffix}",
            index.from_finding(finding),
            "high",
        ))

    for finding in findings_of(facts, "rule_violation")[:1]:
        left, right, label, unit = binding_detail(finding, lang)
        if left is not None and right is not None:
            body = t("block.simulation_vs_limit", lang,
                     left=engine_number(left, unit), right=engine_number(right, unit))
        else:
            body = compact(finding.get("title"), NAME_LIMIT)
        named = f" ({label})" if label else ""
        blocks.append(_block(
            index,
            f"**{t('block.rule_violation', lang)}{named}:** {body}",
            index.from_finding(finding),
            "high",
        ))

    drifts = findings_of(facts, "allocation_drift")[:MAX_DRIFT_BLOCKS]
    for finding in drifts:
        blocks.append(_block(
            index,
            f"**{t('block.strategy_deviation', lang)}:** {finding.get('detail')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "reinvestment")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.reinvestment', lang)}:** {finding.get('detail')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "concentration")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.concentration', lang)}:** {finding.get('title')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "sector_concentration")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.sector_concentration', lang)}:** {finding.get('title')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "fx_exposure")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.fx_risk', lang)}:** {finding.get('detail')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "preference_conflict")[:1]:
        industry = evidence_value(finding, "industry", "look-through")
        # Direct holdings label this evidence "Security"; look-through conflicts label it "Fund".
        fund = compact(evidence_value(finding, "fund", "security", "position"), NAME_LIMIT)
        weight = evidence_value(finding, "effective", "weight")
        suffix = f" ({fmt.fraction(weight)})" if isinstance(weight, (int, float)) else ""
        blocks.append(_block(
            index,
            f"**{t('block.preference_conflict', lang)}:** " + t("block.preference_conflict_body", lang,
                fund=fund, share=suffix, industry=industry or t("block.unknown_sector", lang)),
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "risk_alignment")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.risk_profile', lang)}:** " + t("block.risk_profile_observation", lang, title=finding.get('title')),
            index.from_finding(finding),
            "low",
        ))

    for finding in findings_of(facts, "esg_alignment")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.esg_alignment', lang)}:** " + finding.get('detail'),
            index.from_finding(finding),
            str(finding.get('severity')),
        ))

    for finding in findings_of(facts, "open_proposal")[:1]:
        blocks.append(_block(
            index,
            f"**{t('block.open_consultation', lang)}:** {finding.get('title')}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    for finding in findings_of(facts, "pending_task")[:2]:
        note = evidence_value(finding, "note", "notiz")
        blocks.append(_block(
            index,
            f"**{t('block.pending_task', lang)}:** {compact(note or finding.get('title'), TITLE_LIMIT)}",
            index.from_finding(finding),
            str(finding.get("severity")),
        ))

    tags = list((facts.get("client") or {}).get("tags") or [])
    if tags:
        tag_refs = [
            index.add(
                f"client:tag:{position}",
                t("block.tags_label", lang),
                tag.get("name"),
                "clients.json",
                f"clients[{facts['client']['ref']}].Tags[{position}].TagName",
            )
            for position, tag in enumerate(tags)
        ]
        names = ", ".join(
            f"{tag.get('name')} ({tag.get('type')})" if tag.get("type") else str(tag.get("name"))
            for tag in tags
        )
        blocks.append(_block(index, f"**{t('block.tags_label', lang)}:** {names}", tag_refs))

    gap_findings = findings_of(facts, "missing_data")
    if gap_findings:
        refs: list[str] = []
        for finding in gap_findings[:2]:
            refs.extend(index.from_finding(finding))
        titles = "; ".join(compact(f.get("title"), NAME_LIMIT) for f in gap_findings[:2])
        more = t("block.data_gaps_more", lang, count=len(gap_findings) - 2) if len(gap_findings) > 2 else ""
        blocks.append(_block(index, f"**{t('block.data_gaps', lang)}:** {titles}{more}", refs, "low", "gap"))

    if not blocks:
        blocks.append(_note_block(t("block.no_findings", lang)))

    return {"id": "health_check", "title": t(SECTION_KEYS["health_check"], lang), "blocks": blocks}


def _outlook_actions(facts: dict, index: EvidenceIndex, lang: str = "en", used_security_ids: set[int] | None = None) -> dict:
    blocks: list[dict] = []
    house = facts.get("house_view") or {}

    # Section 1 speaks for the largest holding; section 3 widens the view, so it skips any item about
    # an issuer section 1 already used and keeps scanning. A positional slice (`[1:MAX_MARKET_ITEMS]`)
    # examined exactly one item, and in the common case of two headlines about the top holding that
    # meant section 3 lost its market block entirely — measured on 48/48 clients.
    used_ids = used_security_ids or set()
    shown = 0
    for item in (facts.get("market_context") or [])[1:]:
        if shown >= MAX_MARKET_ITEMS - 1:
            break
        if set(item.get("linked_security_ids") or []) & used_ids:
            continue
        ref = index.add(
            f"news:{item.get('url') or item.get('headline')}",
            str(item.get("headline")),
            item.get("published"),
            str(item.get("source") or t("question.market_source", lang)),
            str(item.get("url") or ""),
        )
        blocks.append(_block(
            index,
            f"**{t('block.market', lang)}:** {compact(item.get('headline'), TITLE_LIMIT)} — {item.get('relevant_because')}",
            [ref], None, "external",
            security_id=item.get("security_id"), isin=item.get("isin"),
        ))
        shown += 1
    market_stage = next(
        (row for row in (facts.get("meta") or {}).get("stages") or [] if row.get("id") == "market"),
        None,
    )
    if not facts.get("market_context") and market_stage is not None and market_stage.get("status") != "ok":
        blocks.append(_note_block(str(market_stage.get("note") or t("stage.market_unavailable", lang))))

    matches = list(house.get("matches") or [])
    # "aligned"/"no target" are only worth showing when nothing deviates; otherwise they are noise.
    deviations = [m for m in matches if m.get("relation") not in ("aligned", "stance aligned", "no target")]
    shown = deviations or matches
    if shown:
        for match in shown[:MAX_MARKET_ITEMS]:
            relation = relation_label(str(match.get("relation") or ""), lang)
            ref = index.add(
                f"house_view:{match.get('category')}:{match.get('portfolio_id')}",
                f"{t('block.bank_view_mock', lang)} {match.get('category')}",
                relation,
                str(house.get("source") or t("block.bank_view_mock", lang)),
                str(house.get("source_url") or ""),
            )
            blocks.append(_block(
                index,
                f"**{t('block.bank_view_mock', lang)}:** {match.get('category')} — {relation}",
                [ref], None, "mock",
            ))
    else:
        ref = index.add("house_view:source", t("block.bank_view_mock", lang), house.get("as_of"),
                        str(house.get("source") or t("block.bank_view_mock", lang)), str(house.get("source_url") or ""))
        blocks.append(_block(
            index,
            f"**{t('block.bank_view_mock_dated', lang, date=fmt.date(house.get('as_of')))}:** {t('block.no_bank_deviation', lang)}",
            [ref], None, "mock",
        ))

    actions = list(facts.get("actions") or [])
    for action in actions[:MAX_ACTIONS]:
        refs = [index.add(
            f"action:{action.get('id')}",
            str(action.get("action") or action.get("id")),
            None,
            "R5",
            "",
        )]
        for position, ev in enumerate(action.get("evidence") or []):
            refs.append(index.add(
                f"action:{action.get('id')}#{position}",
                str(ev.get("label") or "Evidenz"),
                ev.get("value"),
                str(ev.get("source") or ""),
                str(ev.get("path") or ""),
            ))
        blocks.append(_block(
            index,
            f"**{action.get('priority')}. {compact(action.get('action'), TITLE_LIMIT)}** — "
            f"{compact(action.get('rationale'), TITLE_LIMIT)}",
            refs,
            "high" if action.get("priority") == 1 else None,
        ))

    if len(actions) > MAX_ACTIONS:
        blocks.append(_note_block(t("block.more_actions", lang, count=len(actions) - MAX_ACTIONS)))

    if not actions and not matches and not facts.get("market_context"):
        blocks.append(_note_block(t("block.no_context_no_action", lang)))

    return {"id": "outlook_actions", "title": t(SECTION_KEYS["outlook_actions"], lang), "blocks": blocks}


# What to sacrifice first when the briefing does not fit the reading budget. Market context and the
# mock house view rank above neutral portfolio colour, because the brief explicitly requires the
# portfolio to be connected to market developments. Gap blocks rank lowest only because the UI also
# renders ``facts.meta.unavailable`` separately, so cutting the block loses no information.
TRIM_RANK = {"gap": 0, "low": 1, "neutral": 2, "context": 3, "medium": 4, "high": 5}


def trim_rank(block: dict) -> int:
    severity = block.get("severity")
    if severity == "high":
        return TRIM_RANK["high"]
    if severity == "medium":
        return TRIM_RANK["medium"]
    if block.get("source_kind") in ("external", "mock"):
        return TRIM_RANK["context"]
    refs = block.get("evidence_refs") or []
    if refs and all(str(ref).startswith("client:tag:") for ref in refs):
        return TRIM_RANK["medium"]  # the brief names tags: they outrank neutral colour in the trim
    if block.get("source_kind") == "gap":
        return TRIM_RANK["gap"]
    if severity == "low":
        return TRIM_RANK["low"]
    return TRIM_RANK["neutral"]


def _trim_plan(sections: list[dict], questions: dict) -> tuple[list[tuple[str, int]], dict[str, int]]:
    """Which blocks to drop, decided once against the English rendering.

    German prose is longer than English, so trimming inside each language would show a German
    reader a different briefing than an English reader. The selection is therefore computed on
    the English words and applied positionally to every language: only the words change, never
    which findings survive.
    """
    dropped_flags = [[False] * len(section["blocks"]) for section in sections]
    counts: dict[str, int] = {}

    def word_count() -> int:
        total = sum(
            len(block["text"].split())
            for section, flags in zip(sections, dropped_flags)
            for block, flag in zip(section["blocks"], flags)
            if not flag
        )
        total += sum(len(str(questions[key]).split())
                     for key in ("what_happened", "situation", "next", "should_do"))
        return total

    while word_count() > WORD_BUDGET:
        candidates: list[tuple[int, int, int]] = []
        for section_position, (section, flags) in enumerate(zip(sections, dropped_flags)):
            alive = sum(1 for flag in flags if not flag)
            if alive <= 1:
                continue
            alive_traceable = sum(1 for block, flag in zip(section["blocks"], flags)
                                  if not flag and block["evidence_refs"])
            for block_position, (block, flag) in enumerate(zip(section["blocks"], flags)):
                if flag:
                    continue
                if block["source_kind"] == "gap" and not block["evidence_refs"]:
                    continue  # the disclosure note itself is kept
                if block["evidence_refs"] and alive_traceable <= 1:
                    continue  # a section must never degenerate into disclosure notes only
                candidates.append((trim_rank(block), -alive, section_position * 100 + block_position))
        if not candidates:
            break
        _, _, packed = min(candidates, key=lambda item: (item[0], item[1], item[2]))
        section_position, block_position = divmod(packed, 100)
        dropped_flags[section_position][block_position] = True
        section_id = sections[section_position]["id"]
        counts[section_id] = counts.get(section_id, 0) + 1

    pairs = [
        (section["id"], block_position)
        for section, flags in zip(sections, dropped_flags)
        for block_position, flag in enumerate(flags)
        if flag
    ]
    return pairs, counts


def _apply_trim(sections: list[dict], pairs: list[tuple[str, int]], counts: dict[str, int],
                lang: str = "en") -> None:
    """Drop the planned block positions and disclose every drop in its section."""
    for section in sections:
        drop = {position for section_id, position in pairs if section_id == section["id"]}
        if drop:
            section["blocks"] = [block for position, block in enumerate(section["blocks"])
                                 if position not in drop]
        if counts.get(section["id"]):
            section["blocks"].append(
                _note_block(t("block.more_observations", lang, count=counts[section["id"]]))
            )


def _questions(facts: dict, index: EvidenceIndex, lang: str = "en") -> dict:
    """The four answers the brief requires, short enough to read at a glance."""
    portfolios = list(facts.get("portfolios") or [])
    twelve = [p.get("return_12m_pct") for p in portfolios if p.get("return_12m_pct") is not None]
    best = max(twelve) if twelve else None
    three = next((p.get("return_3m_pct") for p in portfolios if p.get("return_3m_pct") is not None), None)
    as_of = next((p.get("performance_as_of") for p in portfolios if p.get("performance_as_of")), None)
    scope = f"clients[{facts['client']['ref']}].Portfolios[*].PerformanceHistory"
    twelve_ref = index.add("portfolio:scope:return_12m_pct", t("question.perf_12m", lang), best, "clients.json", scope)
    three_ref = index.add("portfolio:scope:return_3m_pct", t("question.perf_3m", lang), three, "clients.json", scope)
    avail = next((p.get("return_available_pct") for p in portfolios
                  if p.get("return_available_pct") is not None), None)
    avail_days = next((p.get("return_available_days") for p in portfolios
                       if p.get("return_available_days") is not None), None)
    avail_ref = index.add("portfolio:scope:return_available_pct", t("question.perf_available", lang),
                          avail, "clients.json", scope)

    # A portfolio can have history without having a *twelve-month* figure — a newly onboarded client
    # is exactly that case. Never claim there is no history when a shorter window is available.
    what_happened_refs = []
    if best is not None:
        happened = t("question.perf_12m_over", lang, value=fmt.pct(best, signed=True))
        if three is not None:
            happened += t("question.perf_3m_over", lang, value=fmt.pct(three, signed=True))
        happened += t("question.perf_as_of", lang, date=fmt.date(as_of))
        what_happened_refs = [twelve_ref] + ([three_ref] if three is not None else [])
    elif three is not None:
        happened = t("question.perf_3m_only", lang, value=fmt.pct(three, signed=True), date=fmt.date(as_of))
        what_happened_refs = [three_ref]
    elif avail is not None:
        happened = t("question.perf_available_over", lang, value=fmt.pct(avail, signed=True), days=avail_days)
        happened += t("question.perf_as_of", lang, date=fmt.date(as_of))
        what_happened_refs = [avail_ref]
    else:
        happened = t("question.perf_no_history", lang)
        what_happened_refs = [twelve_ref]

    # "What happened" is performance *and* what was actually traded since then.
    for finding in findings_of(facts, "material_change")[:1]:
        clause = t("question.had_change", lang, title=compact(finding.get("title"), NAME_LIMIT))
        happened = f"{happened.rstrip('. ')}. {clause}"
        what_happened_refs = what_happened_refs + index.from_finding(finding)

    situation_bits: list[str] = []
    situation_refs: list[str] = []
    for finding_type, prefix_key in (
        ("liquidity_event", "question.sit_liquidity"),
        ("rule_violation", "question.sit_rule"),
        ("allocation_drift", "question.sit_strategy"),
        ("reinvestment", "question.sit_reinvestment"),
        ("concentration", "question.sit_concentration"),
        ("sector_concentration", "question.sit_sector"),
        ("fx_exposure", "question.sit_currency"),
        ("preference_conflict", "question.sit_preference"),
        ("risk_alignment", "question.sit_risk"),
        ("esg_alignment", "question.sit_esg"),
        ("pending_task", "question.sit_task"),
        ("missing_data", "question.sit_data_gap"),
    ):
        rows = findings_of(facts, finding_type)
        if rows:
            situation_bits.append(f"{t(prefix_key, lang)}: {compact(rows[0].get('title'), NAME_LIMIT)}")
            situation_refs.extend(index.from_finding(rows[0]))
    situation = "; ".join(situation_bits[:4]) if situation_bits else t("question.sit_none", lang)

    next_bits: list[str] = []
    next_refs: list[str] = []
    if facts.get("market_context"):
        next_bits.append(compact(facts["market_context"][0].get("headline"), TITLE_LIMIT))
        # Add market context evidence ref
        market_item = facts["market_context"][0]
        market_ref = index.add(
            f"market:{market_item.get('url') or market_item.get('headline')}",
            str(market_item.get("headline")),
            market_item.get("published"),
            str(market_item.get("source") or t("question.market_source", lang)),
            str(market_item.get("url") or ""),
        )
        next_refs.append(market_ref)
    house = facts.get("house_view") or {}
    matches = list(house.get("matches") or [])
    if matches:
        next_bits.append(t("question.next_bank_view", lang, category=matches[0].get('category'),
                           relation=relation_label(str(matches[0].get('relation') or ""), lang)))
        # Add house view match evidence ref
        house_ref = index.add(
            f"house_view:{matches[0].get('category')}:{matches[0].get('portfolio_id')}",
            f"{t('block.bank_view_mock', lang)} {matches[0].get('category')}",
            relation_label(str(matches[0].get('relation') or ""), lang),
            str(house.get("source") or t("block.bank_view_mock", lang)),
            str(house.get("source_url") or ""),
        )
        next_refs.append(house_ref)
    next_step = "; ".join(next_bits) if next_bits else t("question.next_no_context", lang)

    actions = list(facts.get("actions") or [])
    should_do = compact(actions[0].get("action"), TITLE_LIMIT) if actions else t("question.should_no_action", lang)
    should_do_refs: list[str] = []
    
    # Build a lookup for findings by ID to resolve finding_refs to evidence index keys
    findings_by_id = {str(f.get("id")): f for f in (facts.get("findings") or [])}
    
    if actions:
        # Resolve finding_refs to evidence index keys
        for finding_id in actions[0].get("finding_refs", []):
            found = findings_by_id.get(str(finding_id))
            if found:
                should_do_refs.extend(index.from_finding(found))
    if len(actions) > 1:
        should_do += t("question.should_more", lang, action=compact(actions[1].get('action'), NAME_LIMIT))
        # Resolve finding_refs to evidence index keys
        for finding_id in actions[1].get("finding_refs", []):
            found = findings_by_id.get(str(finding_id))
            if found:
                should_do_refs.extend(index.from_finding(found))

    return {
        "what_happened": fmt.sentence(happened),
        "situation": fmt.sentence(situation),
        "next": fmt.sentence(next_step),
        "should_do": fmt.sentence(should_do),
        "evidence_refs": what_happened_refs,  # Backwards compatibility
        "what_happened_refs": what_happened_refs,
        "situation_refs": situation_refs,
        "next_refs": next_refs,
        "should_do_refs": should_do_refs,
    }


def _client_questions(facts: dict, index: EvidenceIndex, lang: str = "en") -> list[dict]:
    """The questions the client is likely to raise, derived from findings — capped at three.

    The brief asks the advisor to understand *"the likely questions the client may raise"*. Every
    question here is derived from a finding that already exists, so nothing is speculative: no
    finding, no question. Deliberately excluded from the 60-second word count — this is a
    preparation aid beside the briefing, not part of the read.
    """
    rows: list[dict] = []
    for finding_type, key in (
        ("concentration", "client_questions.concentration"),
        ("liquidity_event", "client_questions.liquidity"),
        ("pending_task", "client_questions.task"),
        ("allocation_drift", "client_questions.strategy"),
        ("risk_alignment", "client_questions.risk"),
        ("preference_conflict", "client_questions.preference"),
        ("fx_exposure", "client_questions.fx"),
        ("rule_violation", "client_questions.rule"),
        ("material_change", "client_questions.sold"),
    ):
        matches = findings_of(facts, finding_type)
        if not matches:
            continue
        finding = matches[0]
        if finding_type == "concentration":
            weight = evidence_value(finding, "weight", "gewicht", "top")
            name = compact(str(finding.get("title") or "").rsplit(" in ", 1)[-1], NAME_LIMIT)
            question = t(key, lang,
                         weight=fmt.fraction(weight) if isinstance(weight, (int, float)) else "—",
                         name=name or "—")
        elif finding_type == "material_change":
            question = t(key, lang, name=compact(
                evidence_value(finding, "traded security", "gehandelte position") or "—", NAME_LIMIT))
        elif finding_type == "pending_task":
            # The client's own open request is a question they will ask again.
            note = evidence_value(finding, "note", "notiz")
            question = t(key, lang, text=compact(note or finding.get("title"), 70))
        else:
            question = t(key, lang)
        rows.append({"question": question, "evidence_refs": index.from_finding(finding)})
        if len(rows) >= CLIENT_QUESTIONS_MAX:
            break
    return rows


def _template_briefing(facts: dict, lang: str = "en") -> dict:
    """The deterministic briefing — the template renderer's full output."""
    def build(source: dict, target_lang: str) -> tuple[list[dict], dict, list[dict], EvidenceIndex]:
        local_index = EvidenceIndex()
        recent_dev_section, used_security_ids = _recent_development(source, local_index, target_lang)
        local_sections = [
            recent_dev_section,
            _health_check(source, local_index, target_lang),
            _outlook_actions(source, local_index, target_lang, used_security_ids),
        ]
        local_questions = _questions(source, local_index, target_lang)
        local_client_questions = _client_questions(source, local_index, target_lang)
        return local_sections, local_questions, local_client_questions, local_index

    # The trim plan is computed on the English rendering and applied to every language, so a
    # German reader sees exactly the same findings as an English reader — only the words differ.
    # Findings and actions carry localized prose inside ``facts``, so a non-English request
    # re-assembles an English facts bundle for the plan (cheap: the news layer is cached).
    scope = (facts.get("meta") or {}).get("scope") or {}
    client_ref = str(scope.get("client_ref") or facts["client"]["ref"])
    portfolio_nr = scope.get("portfolio_nr")
    if lang == "en":
        plan_facts = facts
    else:
        from .facts import assemble as assemble_facts

        plan_facts = assemble_facts(client_ref, portfolio_nr, None, "en")
    en_sections, en_questions, en_client_questions, en_index = build(plan_facts, "en")
    pairs, counts = _trim_plan(en_sections, en_questions)
    if lang == "en":
        sections, questions, client_questions, index = en_sections, en_questions, en_client_questions, en_index
    else:
        sections, questions, client_questions, index = build(facts, lang)
    _apply_trim(sections, pairs, counts, lang)
    # After the trim, so only blocks the advisor will actually read are tagged.
    _attach_instruments(sections, facts)

    texts = [block["text"] for section in sections for block in section["blocks"]]
    texts += [str(questions[key]) for key in ("what_happened", "situation", "next", "should_do")]
    words = sum(len(text.split()) for text in texts)

    return {
        "client_ref": facts["client"]["ref"],
        "client_name": facts["client"]["display_name"],
        "renderer": TEMPLATE,
        "lang": lang,
        "sections": sections,
        "questions": questions,
        "client_questions": client_questions,
        "evidence_index": index.as_dict(),
        "word_count": words,
        "read_seconds_estimate": round(words / WORDS_PER_SECOND),
        "trimmed_blocks": counts,
        "generated_from": {
            "data_as_of": facts["meta"].get("data_as_of"),
            "engine_version": facts["meta"].get("engine_version"),
            "finding_count": len(facts.get("findings") or []),
        },
    }


# The four answers and the prose cells the LLM may rewrite. Everything else — section ids, block
# kinds, evidence refs, the evidence index — is traceability the rewrite must not be able to touch.
QUESTION_KEYS = ("what_happened", "situation", "next", "should_do")


def _attach_instruments(sections: list[dict], facts: dict) -> None:
    """Tag every block that is about one instrument with that instrument's id and ISIN.

    A block references the finding it renders (``finding:f3``), and the finding knows the instrument
    when it has one — a concentration, a performance driver. Copying it here rather than at each of the
    ~16 block call sites means a future instrument-level finding gets the market-results link for free.
    Market blocks are tagged where they are built, because a headline is not a finding.
    """
    findings = {
        str(finding.get("id")): finding
        for finding in (facts.get("findings") or [])
        if isinstance(finding, dict)
    }
    if not findings:
        return
    for section in sections:
        for block in section.get("blocks") or []:
            for ref in block.get("evidence_refs") or []:
                text_ref = str(ref)
                if not text_ref.startswith("finding:"):
                    continue
                finding = findings.get(text_ref.split(":", 1)[1].split("#", 1)[0])
                if finding and (finding.get("isin") or finding.get("security_id") is not None):
                    block["security_id"] = finding.get("security_id")
                    block["isin"] = finding.get("isin")
                break


def _prose_slots(briefing: dict) -> list[tuple[dict, str]]:
    """Every rewritable sentence, as ``(container, key)`` pairs, in render order.

    Blocks of ``source_kind == "external"`` are excluded: they quote a published headline, and a model
    asked to "improve the wording" will translate or rephrase it — measured, it turned a German
    headline into English. A quote that no longer matches its source is worse than a clunky sentence,
    so the citation keeps its published words and the label around it stays product text.
    """
    slots: list[tuple[dict, str]] = []
    for section in briefing.get("sections") or []:
        for block in section.get("blocks") or []:
            if block.get("source_kind") == "external":
                continue
            if isinstance(block.get("text"), str) and block["text"].strip():
                slots.append((block, "text"))
    questions = briefing.get("questions")
    if isinstance(questions, dict):
        for key in QUESTION_KEYS:
            if isinstance(questions.get(key), str) and questions[key].strip():
                slots.append((questions, key))
    for row in briefing.get("client_questions") or []:
        if isinstance(row.get("question"), str) and row["question"].strip():
            slots.append((row, "question"))
    return slots


def render(facts: dict, renderer: str = TEMPLATE, lang: str = "en") -> dict:
    """Render the briefing object with either renderer.

    ``llm`` runs the template renderer first and rewrites its sentences afterwards, so a missing key,
    a dead network or a reply that changed a figure can only cost the phrasing — never a number, and
    never the traceability index.
    """
    if renderer not in RENDERERS:
        raise ValueError(f"unknown renderer {renderer!r}: expected one of {', '.join(RENDERERS)}")

    briefing = _template_briefing(facts, lang)
    if renderer == TEMPLATE:
        return briefing

    from ..external import llm as llm_module

    if not llm_module.available():
        raise ValueError(
            "renderer 'llm' needs a key: set DEEPSEEK_API_KEY (and optionally URO_LLM_MODEL or "
            "URO_LLM_BASE_URL). The LLM renderer rephrases only — it never computes a number."
        )

    slots = _prose_slots(briefing)
    result = llm_module.rephrase([container[key] for container, key in slots], lang)
    for (container, key), text in zip(slots, result["texts"]):
        container[key] = text

    # `renderer` names the renderer whose *words* are in the payload. A pass that produced nothing —
    # a failed call, an unusable reply, not one sentence improved — is reported as the template it
    # is, with the reason beside it, instead of claiming an LLM run that changed no text.
    changed = int(result.get("changed") or 0)
    applied = bool(result.get("applied")) and changed > 0
    briefing["renderer"] = LLM if applied else TEMPLATE
    briefing["llm"] = {
        "applied": applied,
        "changed_sentences": changed,
        "sentences": len(slots),
        "model": llm_module.model() if result.get("applied") else None,
        "reason": result.get("reason") if not applied else None,
    }
    # The reading-time contract is measured on the sentences the advisor actually reads, so it is
    # recomputed after the rewrite rather than carried over from the template pass.
    texts = [block["text"] for section in briefing["sections"] for block in section["blocks"]]
    texts += [str(briefing["questions"][key]) for key in QUESTION_KEYS]
    words = sum(len(text.split()) for text in texts)
    briefing["word_count"] = words
    briefing["read_seconds_estimate"] = round(words / WORDS_PER_SECOND)
    return briefing
