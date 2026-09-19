"""B2 — follow-up Q&A over the R2/R3 evidence bundle.

Deterministic, LLM-free retrieval layer. Every answer is grounded in the assembled
``BriefingFacts`` bundle; if the data does not contain the answer, the response says
so explicitly and lists what is unavailable.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..domain import index, metrics
from ..external import browse
from ..i18n import DEFAULT_LANG, t
from ..text import compact

# How many public pages an unrouteable question may be answered from.
WEB_RESULTS_MAX = 4

from ..compose import facts as facts_module
from .render import engine_number


# -------------------------------------------------------------------------------- keyword families

# Both languages in one tuple per family: the brief hands us English example questions while the
# product ships German too, so classifying only one language fails half the demo.
PERFORMANCE_KEYWORDS = ("rendite", "performance", "perform", "entwicklung", "gewinn", "verlust", "+/-", "wachstum",
                        "return", "gain", "loss", "growth", "develop", "up or down")
RISK_KEYWORDS = ("risiko", "volatilität", "var", "value at risk", "risk", "volatility")
CONCENTRATION_KEYWORDS = ("klumpen", "konzentration", "grösste position", "anteil", "top-position",
                          "concentration", "largest position", "biggest position", "share of", "weight")
ALLOCATION_KEYWORDS = ("allokation", "strategie", "abweichung", "soll", "ziel", "saa",
                       "allocation", "strategy", "deviation", "target", "rebalanc")
RULE_KEYWORDS = ("regel", "verstoss", "verletz", "limite", "suitability",
                 "rule", "violation", "breach", "limit")
FX_KEYWORDS = ("währung", "usd", "dollar", "fremdwährung", "abgesichert", "chf", "eur",
               "currency", "fx", "foreign", "hedg")
LIQUIDITY_KEYWORDS = ("liquidität", "kauf", "immobilie", "bedarf", "fällig",
                      "liquidity", "cash", "property", "maturit") 
COST_KEYWORDS = ("kosten", "prc", "produktrisiko", "cost", "product risk")
NEWS_KEYWORDS = ("markt", "news", "schlagzeile", "medien", "market", "headline")
ESG_KEYWORDS = ("esg", "nachhaltig", "sustainab")
PROPOSAL_KEYWORDS = ("beratung", "vorschlag", "entwurf", "offen", "proposal", "consultation", "draft",
                     "open")
DATA_QUALITY_KEYWORDS = ("daten", "lücke", "veraltet", "unbekannt", "fehlt", "data", "gap", "stale",
                         "missing")
RISK_PROFILE_KEYWORDS = ("risikoprofil", "kundenprofil", "risikoklasse", "risk profile", "client profile")

# "Which positions drive the risk?" is a different question from "how risky is the portfolio?".
# The brief lists it as one of its five examples, and answering it with volatility/VaR would be true
# but unresponsive — so a risk word *plus* a position/contribution word routes to the contribution
# series first.
RISK_CONTRIBUTION_KEYWORDS = (
    "contribution", "contribute", "contributing", "beitrag", "beitragen", "tragen", "treiber",
    "driver", "risikobeitrag", "risk contribution", "position", "positionen", "holding", "wertschrift",
)

# Sector/region questions ("What is the client's total semiconductor exposure?") are answered from
# the exposure buckets, not from findings. The question must name a term the data actually carries
# AND ask for an exposure — otherwise "oil" in "why is oil falling" would be answered with weights.
EXPOSURE_KEYWORDS = (
    "exposure", "exposed", "exposition", "exponiert", "how much", "how high", "wie hoch", "wie viel",
    "total", "share of", "anteil", "weighted", "gewichtet", "holdings in", "hold in",
)

# Sub-industry and everyday words the delivered vocabulary does not carry. Every mapping is *declared*
# in the answer ("the data carries no separate semiconductor bucket; the closest is Information
# Technology"), so nothing is overclaimed: semiconductors are a sub-industry of Information Technology
# in the 12 GICS sectors this data uses.
INDUSTRY_SYNONYMS = {
    "semiconductor": "Information Technology",
    "semiconductors": "Information Technology",
    "chip": "Information Technology",
    "chips": "Information Technology",
    "halbleiter": "Information Technology",
    "tech": "Information Technology",
    "technology": "Information Technology",
    "technologie": "Information Technology",
    "software": "Information Technology",
    "pharma": "Health Care",
    "healthcare": "Health Care",
    "health care": "Health Care",
    "gesundheit": "Health Care",
    "bank": "Financials",
    "banks": "Financials",
    "banken": "Financials",
    "financials": "Financials",
    "oil": "Energy",
    "gas": "Energy",
    "energie": "Energy",
    "energy": "Energy",
    "real estate": "Real Estate",
    "immobilien": "Real Estate",
    "utilities": "Utilities",
    "utility": "Utilities",
    "versorger": "Utilities",
    "raw materials": "Materials",
    "rohstoffe": "Materials",
    "materials": "Materials",
    "industrials": "Industrials",
    "industrial": "Industrials",
    "consumer staples": "Consumer Staples",
    "consumer discretionary": "Consumer Discretionary",
    "telecom": "Telecommunication Services",
    "telecommunication": "Telecommunication Services",
    "communication services": "Communication Services",
}

# Questions about what the client *said* are answered from ClientNotes, verbatim — never paraphrased.
NOTES_KEYWORDS = (
    "previously", "previously raised", "has the client", "mentioned", "concern", "preference",
    "note", "notes", "asked about", "wants", "want", "avoid", "prefer", "wishes",
    "früher", "bereits", "schon einmal", "notiz", "notizen", "bedenken", "präferenz", "wunsch", "sorge",
    "vermeiden", "möchte",
)

# "Which open proposal is most relevant?" wants the draft (or the newest closed one), not the action list.
PROPOSAL_FOLLOWUP_KEYWORDS = ("open", "relevant", "follow", "pending", "which proposal",
                              "offen", "relevant", "wichtig", "nachfassen", "welcher vorschlag")

# Words that appear in every question and would match every note.
NOTE_STOPWORDS = frozenset({
    "about", "there", "their", "which", "client", "previously", "raised", "concerns", "should",
    "would", "could", "notes", "please", "before", "already", "haben", "wurde", "welche", "seiner",
})

# Numeric question prefix
NUMERIC_PREFIXES = ("wie hoch", "wie gross", "wie viel", "welcher anteil", "welche quote")

# The SAA vocabulary an allocation question must name, in both languages. "allocation" on its own is
# deliberately not enough: "the private equity allocation of the client's holiday home" matched that
# word and was answered with the strategy's and the service's names — a confident answer to a different
# question. A question that names an asset class, the strategy, a target or a deviation is answered from
# the portfolio's own SAA rows; anything else is declared unanswerable.
SAA_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "Shares": ("shares", "share", "equities", "equity share", "aktien", "aktie"),
    "Bonds": ("bonds", "bond", "fixed income", "obligationen", "obligation", "zinswerte"),
    "Liquidity": ("liquidity", "cash", "liquidität", "liquiditaet"),
    "Real estate": ("real estate", "immobilien", "immobilie", "property"),
    "Specialties andCommodities": ("commodities", "commodity", "rohstoffe", "rohstoff", "specialties"),
}

ALLOCATION_SUBJECT_KEYWORDS = (
    "strategie", "strategy", "strategisch", "strategic", "soll", "ziel", "target",
    "abweichung", "deviation", "saa", "asset allocation", "aufteilung", "gewichtung",
)

# Asset-class words. Combined with a currency they ask for a cross-tabulation the data does not carry
# (it holds the asset-class dimension and the currency dimension, not their crossing), so the currency
# answer says exactly that instead of letting the currency figure stand in for the asset class.
ASSET_CLASS_WORDS = (
    "share", "shares", "equity", "equities", "aktie", "aktien", "bond", "bonds", "obligation",
    "obligationen", "commodit", "rohstoff", "immobil", "property", "real estate", "cash",
    "liquidity", "liquidität",
)

# The three codes the dataset maps by hand (``index.Dataset._currency_group``). They let a question
# about a currency the portfolio does not hold be answered as "no exposure in X" instead of being
# answered with a different currency's number.
KNOWN_CURRENCY_GROUPS = {"CHF": "Swiss francs", "EUR": "Euro", "USD": "US-Dollar"}


# Instrument candidate questions: buy/sell/switch recommendations
INSTRUMENT_KEYWORDS = ("buy", "sell", "switch", "recommend", "securities", "which security",
                       "kaufen", "verkaufen", "umschichten", "empfehlen", "wertpapiere",
                       "welche wertpapiere", "vorschlag", "instrument")


def _classify(question: str) -> tuple[str, list[str]]:
    """Classify the question by keyword family. Returns (category, matched_keywords)."""
    q_lower = question.lower()

    # Checked before the plain "risk" family: a question that names positions and risk is asking
    # which holdings carry the risk, not how large the portfolio volatility is.
    if any(kw in q_lower for kw in RISK_KEYWORDS) and any(kw in q_lower for kw in RISK_CONTRIBUTION_KEYWORDS):
        matched = [kw for kw in RISK_CONTRIBUTION_KEYWORDS if kw in q_lower]
        return "risk_contribution", matched

    # The generic "risk" word is tried last, for the same reason ``risk_contribution`` is tried first:
    # "What is the concentration risk?" and "Wie hoch ist das Währungsrisiko?" name a family
    # explicitly, and letting the bare word "risk" win answered them with portfolio volatility and
    # value-at-risk instead — a correct answer to a question nobody asked.
    families = [
        ("risk_profile", RISK_PROFILE_KEYWORDS),
        ("performance", PERFORMANCE_KEYWORDS),
        ("concentration", CONCENTRATION_KEYWORDS),
        ("allocation", ALLOCATION_KEYWORDS),
        ("rules", RULE_KEYWORDS),
        ("fx", FX_KEYWORDS),
        ("liquidity", LIQUIDITY_KEYWORDS),
        ("costs", COST_KEYWORDS),
        ("news", NEWS_KEYWORDS),
        ("esg", ESG_KEYWORDS),
        ("proposals", PROPOSAL_KEYWORDS),
        ("data_quality", DATA_QUALITY_KEYWORDS),
        ("risk", RISK_KEYWORDS),
    ]
    
    for category, keywords in families:
        matched = [kw for kw in keywords if kw in q_lower]
        if matched:
            return category, matched
    
    return "unknown", []


def _is_unsupported(question: str) -> str | None:
    """Questions whose answer this data cannot support — refuse rather than answer something else.

    The source data has no position cost basis and no position history, so per-position performance
    attribution is impossible. Matching "performance" and returning the portfolio return instead is
    a plausible-looking wrong answer, which is worse than a refusal.
    """
    q = question.lower()
    if ("attribution" in q
            or ("performance" in q and any(w in q for w in ("per position", "position-level",
                                                             "which position", "each position",
                                                             "je position", "pro position")))):
        return "attribution"
    return None


def _is_numeric_question(question: str) -> bool:
    """Check if the question asks for a specific numeric value."""
    q_lower = question.lower()
    return any(q_lower.startswith(prefix) for prefix in NUMERIC_PREFIXES)


def _format_pct(value: float | None, decimals: int = 2, lang: str = "en") -> str:
    """Format a percentage value (0-1 or 0-100)."""
    if value is None:
        return t("qa.not_available", lang)
    if 0 <= value <= 1:
        return f"{value * 100:.{decimals}f}%"
    return f"{value:.{decimals}f}%"


def _format_money(value: float | None, currency: str = "CHF", lang: str = "en") -> str:
    """Format a monetary amount Swiss-style (1'234.56), the convention everywhere else."""
    if value is None:
        return t("qa.not_available", lang)
    return f"{value:,.2f}".replace(",", "'") + f" {currency}"


def _find_portfolio(facts: dict, portfolio_nr: str | None) -> dict | None:
    """Find the portfolio in the facts bundle, optionally scoped."""
    portfolios = facts.get("portfolios") or []
    if not portfolios:
        return None
    if portfolio_nr:
        return next((p for p in portfolios if p.get("nr") == portfolio_nr), None)
    return portfolios[0] if len(portfolios) == 1 else None


def _answer_performance(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about performance/returns."""
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    
    evidence = []
    parts = []
    
    # Return 12m
    ret_12m = portfolio.get("return_12m_pct")
    if ret_12m is not None:
        evidence.append({
            "label": t("qa.perf_12m_label", lang),
            "value": ret_12m,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].PerformanceHistory"
        })
        parts.append(t("qa.perf_12m", lang, value=_format_pct(ret_12m, lang=lang)))
    
    # Return 3m
    ret_3m = portfolio.get("return_3m_pct")
    if ret_3m is not None:
        evidence.append({
            "label": t("qa.perf_3m_label", lang),
            "value": ret_3m,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].PerformanceHistory"
        })
        parts.append(t("qa.perf_3m", lang, value=_format_pct(ret_3m, lang=lang)))
    
    if not parts:
        return t("qa.perf_unavailable", lang), [], [t("qa.reason_perf_missing", lang)]
    
    return " ".join(parts), evidence, []


def _answer_risk(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about risk metrics."""
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    
    evidence = []
    parts = []
    
    # Volatility
    vola = portfolio.get("volatility")
    if vola is not None:
        evidence.append({
            "label": t("qa.vola_label", lang),
            "value": vola,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].Volatility"
        })
        parts.append(t("qa.risk_vola", lang, value=_format_pct(vola, lang=lang)))
    
    # VaR
    var = portfolio.get("value_at_risk")
    if var is not None:
        evidence.append({
            "label": "Value at Risk",
            "value": var,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].ValueAtRisk"
        })
        parts.append(t("qa.risk_var", lang, value=_format_pct(var, lang=lang)))
    
    # Risk profile
    risk_profile = facts.get("client", {}).get("risk_profile")
    if risk_profile:
        max_vola = risk_profile.get("max_vola")
        if max_vola is not None:
            evidence.append({
                "label": t("qa.max_vola_label", lang),
                "value": max_vola,
                "source": "clients.json",
                "path": f"clients[{facts['client']['ref']}].RiskProfile.MaxVola"
            })
            parts.append(t("qa.risk_max_vola", lang, value=_format_pct(max_vola, lang=lang)))
    
    if not parts:
        return t("qa.risk_unavailable", lang), [], [t("qa.reason_risk_missing", lang)]
    
    return " ".join(parts), evidence, []


def _exposure_terms(question: str) -> list[tuple[str, str]]:
    """(dimension, canonical label) for every sector/region term the question names.

    The vocabulary is the data's own: the 11–12 industry groups and the country names carried by the
    securities, plus the declared synonym map for words the data has no bucket for.
    """
    from ..domain import index

    dataset = index.get()
    vocabulary: dict[str, tuple[str, str]] = {}
    for security in dataset.securities:
        for field, dimension in (("IndustryName", "industry"), ("SAA_IndustryName", "industry"),
                                 ("CountryName", "country"),
                                 ("CurrencyGroupName", "currency"), ("SAA_CurrencyGroupName", "currency")):
            value = security.get(field)
            if value:
                vocabulary.setdefault(str(value).lower(), (dimension, str(value)))
    for term, label in INDUSTRY_SYNONYMS.items():
        vocabulary.setdefault(term, ("industry", label))

    q_lower = question.lower()
    found: list[tuple[str, str]] = []
    for term in sorted(vocabulary, key=len, reverse=True):
        if re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", q_lower):
            entry = vocabulary[term]
            if entry not in found:
                found.append(entry)
    return found


def _answer_exposure(facts: dict, question: str, portfolio: dict | None, terms: list[tuple[str, str]], lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer a sector/region exposure question from the value-weighted exposure buckets."""
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]

    from ..domain import index, metrics

    found = index.get().portfolio(facts["client"]["ref"], portfolio["nr"])
    if not found:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    _, raw = found

    dimension, label = terms[0]
    rows = metrics.exposure(raw, dimension, split_funds=True, lang=lang)
    row = next((item for item in rows if str(item["category"]).lower() == label.lower()), None)
    weight = row["weight"] if row else 0.0
    value = row["value"] if row else 0.0
    currency = raw.get("PortfolioCurrency") or facts["client"].get("reporting_currency") or ""

    # A synonym match means the data has no bucket of that name: say so instead of implying one.
    mapped = any(
        term in question.lower() and INDUSTRY_SYNONYMS[term] == label and term.lower() != label.lower()
        for term in INDUSTRY_SYNONYMS
    )
    note = t("qa.exposure_synonym", lang, label=label) if mapped else ""

    evidence = [{
        "label": t("qa.exposure_label", lang, label=label),
        "value": weight,
        "source": "clients.json",
        "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}].SecurityPositions",
    }]
    if weight <= 0:
        return t("qa.exposure_zero", lang, label=label) + note, evidence, []
    return (
        t("qa.exposure_answer", lang, label=label, pct=_format_pct(weight, lang=lang),
          value=_format_money(value, currency, lang=lang)) + note,
        evidence,
        [],
    )


def _answer_notes(facts: dict, question: str, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Quote what the client's notes actually say about the question's topic.

    The brief asks "Has the client previously raised concerns about volatility?" — the answer lives in
    ``ClientNotes`` and is quoted verbatim, never paraphrased. When no note mentions the topic, that is
    said plainly and the notes that do exist are listed, so the advisor can judge for themselves.
    """
    from ..domain import crm, index

    client = index.get().client(facts["client"]["ref"])
    if not client:
        return t("qa.no_client", lang), [], [t("qa.reason_no_client", lang)]

    notes = crm.distinct_notes(client)
    if not notes:
        return t("qa.notes_none", lang), [], [t("qa.reason_notes_none", lang)]

    q_lower = question.lower()
    words = [w for w in re.findall(r"[A-Za-zÄÖÜäöüß]{5,}", q_lower) if w not in NOTE_STOPWORDS]
    hits = [note for note in notes if any(w in str(note.get("text", "")).lower() for w in words)]

    # "What does the client want to avoid?" rarely quotes the note's own words ("No direct positions in
    # fossil fuels, please") — so for a question about *preferences* fall back to R3's note-derived
    # findings, which already judged which note applies to which holding, and quote the note they cite.
    # Deliberately not triggered by "concerns about volatility": that asks about a topic, and inventing
    # an unrelated preference note would be a plausible-looking answer to a different question.
    wants_preference = any(w in q_lower for w in ("avoid", "prefer", "vermeiden", "präferenz",
                                                  "wunsch", "want to", "restrict"))
    if not hits and wants_preference:
        derived = [
            finding for finding in (facts.get("findings") or [])
            if finding["type"] in ("preference_conflict", "liquidity_event", "pending_task")
        ]
        seen: set[str] = set()
        note_refs: list[dict] = []
        for finding in derived:
            for entry in finding["evidence"]:
                if str(entry.get("label", "")).lower() not in ("note", "notiz", "kundennotiz"):
                    continue
                text = str(entry.get("value"))
                if text in seen:
                    continue
                seen.add(text)
                note_refs.append(entry)
        if note_refs:
            quoted = " ".join(f"\u201c{entry['value']}\u201d" for entry in note_refs[:2])
            evidence = [
                {"label": t("qa.notes_label", lang), "value": entry["value"],
                 "source": entry.get("source", "clients.json"), "path": entry.get("path", "")}
                for entry in note_refs[:2]
            ]
            return t("qa.notes_answer", lang, count=len(notes), quoted=quoted), evidence, []

    if hits:
        evidence = [
            {"label": t("qa.notes_label", lang), "value": note["text"], "source": "clients.json", "path": note["path"]}
            for note in hits[:3]
        ]
        quoted = " ".join(f"\u201c{note['text']}\u201d" for note in hits[:3])
        return t("qa.notes_answer", lang, count=len(notes), quoted=quoted), evidence, []

    evidence = [
        {"label": t("qa.notes_label", lang), "value": note["text"], "source": "clients.json", "path": note["path"]}
        for note in notes[:5]
    ]
    listed = " ".join(f"\u201c{note['text']}\u201d" for note in notes[:5])
    return (
        t("qa.notes_no_match", lang, count=len(notes), listed=listed),
        evidence,
        [t("qa.reason_notes_no_match", lang)],
    )


def _answer_proposal_followup(facts: dict, question: str, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Which proposal matters for this conversation: an open draft first, else the newest closed one."""
    from ..domain import index

    client = index.get().client(facts["client"]["ref"])
    if not client:
        return t("qa.no_client", lang), [], [t("qa.reason_no_client", lang)]

    proposals = client.get("Proposals") or []
    if not proposals:
        return t("qa.proposal_none", lang), [], [t("qa.reason_proposal_none", lang)]

    ref = facts["client"]["ref"]
    path = f"clients[{ref}].Proposals"
    drafts = [p for p in proposals if p.get("ProposalStatusName") == "Entwurf"]
    if drafts:
        draft = sorted(drafts, key=lambda p: str(p.get("ProposedDateUTC") or ""), reverse=True)[0]
        evidence = [{
            "label": t("qa.proposal_label", lang, status=draft.get("ProposalStatusName")),
            "value": draft.get("ProposalId"),
            "source": "clients.json",
            "path": f"{path}[{draft.get('ProposalId')}].ProposalStatusName",
        }]
        stamp = str(draft.get("ProposedDateUTC") or "")[:10]
        # Three of the five drafts in the data carry no ProposedDateUTC; say so instead of printing a
        # placeholder date (PROJECT-NOTES.md §5 landmine 5).
        if stamp:
            text = t("qa.proposal_open", lang, count=len(drafts), date=stamp,
                     positions=len(draft.get("SecurityPositions") or []))
        else:
            text = t("qa.proposal_open_undated", lang, count=len(drafts),
                     positions=len(draft.get("SecurityPositions") or []))
        return text, evidence, []

    newest = max(
        proposals,
        key=lambda p: str(p.get("FinalizedDateUTC") or p.get("ProposedDateUTC") or ""),
    )
    stamp = str(newest.get("FinalizedDateUTC") or newest.get("ProposedDateUTC") or "")[:10]
    evidence = [{
        "label": t("qa.proposal_label", lang, status=newest.get("ProposalStatusName")),
        "value": newest.get("ProposalId"),
        "source": "clients.json",
        "path": f"{path}[{newest.get('ProposalId')}].ProposalStatusName",
    }]
    return t("qa.proposal_closed", lang, count=len(proposals), date=stamp or t("qa.not_available", lang)), evidence, []


def _answer_risk_contribution(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer "which positions drive the risk?" from the cleaned contribution series.

    ``ContributionVolatility`` is the only position-level risk figure this data carries — there is no
    position history, so it is *risk* contribution and never performance contribution. It is read
    through :func:`app.domain.metrics.risk_contributions`, so a figure that cannot be true is
    withheld and declared instead of being quoted.
    """
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]

    from ..domain import index, metrics

    found = index.get().portfolio(facts["client"]["ref"], portfolio["nr"])
    if not found:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    _, raw = found

    risk = metrics.risk_contributions(raw)
    volatility = risk["volatility"] or 0.0
    if not risk["available"] or not risk["rows"] or not volatility:
        return (
            t("qa.risk_contribution_unavailable", lang),
            [],
            [t("qa.reason_risk_contribution", lang, reason=risk["reason"] or t("qa.not_available", lang))],
        )

    evidence: list[dict] = []
    parts: list[str] = []
    for rank, row in enumerate(sorted(risk["rows"], key=lambda item: item["contribution"], reverse=True)[:3], start=1):
        share = round(row["contribution"] / volatility * 100, 1)
        evidence.append({
            "label": t("qa.risk_contribution_label", lang, name=row["name"]),
            "value": row["contribution"],
            "source": "clients.json",
            "path": (
                f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}]"
                f".SecurityPositions[{row['index']}].ContributionVolatility"
            ),
        })
        parts.append(t("qa.risk_contribution_item", lang, rank=rank, name=row["name"], share=share))

    unavailable = [t("qa.risk_contribution_dropped", lang)] if risk["dropped"] else []
    return " ".join(parts), evidence, unavailable


def _answer_concentration(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about concentration/largest position."""
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    
    # Findings about concentration - prioritize by type first
    findings = facts.get("findings") or []
    concentration_findings = [f for f in findings if f.get("type") == "concentration"]
    
    # If no type match, fall back to title-based matching
    if not concentration_findings:
        concentration_findings = [f for f in findings 
                                   if "konzentration" in str(f.get("title", "")).lower() 
                                   or "klumpen" in str(f.get("title", "")).lower()]
    
    if concentration_findings:
        finding = concentration_findings[0]
        evidence = []
        for ev in finding.get("evidence") or []:
            evidence.append({
                "label": ev.get("label", "Evidenz"),
                "value": ev.get("value"),
                "source": ev.get("source", "R3"),
                "path": ev.get("path", "")
            })
        
        # Extract the concentration value from evidence
        top_weight = None
        top_security = None
        for ev in finding.get("evidence") or []:
            label = str(ev.get("label", "")).lower()
            if "weight" in label or "anteil" in label or "gewicht" in label:
                val = ev.get("value")
                if isinstance(val, (int, float)):
                    top_weight = val
            if "position" in label or "wertpapier" in label or "security" in label or "aktie" in label:
                val = ev.get("value")
                if isinstance(val, str):
                    top_security = val
        
        if top_weight is not None:
            if top_security:
                return t("qa.concentration_top_security", lang, security=top_security, value=_format_pct(top_weight, lang=lang)), evidence, []
            return t("qa.concentration_top", lang, value=_format_pct(top_weight, lang=lang)), evidence, []
    
    return t("qa.concentration_unavailable", lang), [], [t("qa.reason_concentration_missing", lang)]


def _allocation_rows(facts: dict, portfolio: dict) -> list[dict]:
    """The portfolio's actual-vs-target rows from the SAA — the only sanctioned comparison."""
    found = index.get().portfolio(facts["client"]["ref"], portfolio.get("nr"))
    if not found:
        return []
    saa = metrics.saa_deviation(found[1])
    if not saa["available"]:
        return []
    return [row for row in saa["rows"] if row.get("difference") is not None]


def _allocation_evidence(facts: dict, portfolio: dict, row: dict, lang: str) -> list[dict]:
    return [{
        "label": t("qa.rebalance_label", lang, category=row["category"]),
        "value": row["actual"],
        "source": "clients.json",
        "path": (f"clients[{facts['client']['ref']}].Portfolios[{portfolio['nr']}]"
                 f".SAA.Mappings[{row['category']}].TargetPercentage"),
    }]


def _named_saa_category(question: str, rows: list[dict]) -> str | None:
    """The SAA category the question names, if the portfolio carries that row."""
    lowered = question.lower()
    for row in rows:
        for alias in SAA_CATEGORY_ALIASES.get(str(row["category"]), ()):
            if re.search(rf"(?<![a-z]){re.escape(alias)}(?![a-z])", lowered):
                return str(row["category"])
    return None


def _answer_allocation(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about allocation/strategy from the portfolio's own SAA rows.

    A question about the *effect of a rebalancing* is answered from the SAA gaps — what actually moves
    — rather than from the strategy's name, which says nothing about the effect. Every other allocation
    question is answered from those same rows, and only when it names something the portfolio carries
    (an asset class, the strategy, a target, a deviation); otherwise the answer declares itself
    unavailable instead of being filled with adjacent text.
    """
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]

    q_lower = question.lower()
    rows = _allocation_rows(facts, portfolio)

    if any(kw in q_lower for kw in ("rebalanc", "rebalancing", "effect", "affect", "auswirk", "anpassen", "umschicht")):
        ordered = sorted(rows, key=lambda row: abs(row["difference"]), reverse=True)
        if ordered:
            evidence = [item for row in ordered[:3] for item in _allocation_evidence(facts, portfolio, row, lang)]
            moves = " ".join(
                t("qa.rebalance_item", lang, category=row["category"],
                  actual=_format_pct(row["actual"], lang=lang),
                  target=_format_pct(row["target"], lang=lang))
                for row in ordered[:3]
            )
            return t("qa.rebalance_answer", lang, nr=portfolio["nr"], moves=moves), evidence, []

    named = _named_saa_category(question, rows)
    subject = named is not None or any(kw in q_lower for kw in ALLOCATION_SUBJECT_KEYWORDS)
    if not rows or not subject:
        return (t("qa.allocation_unsupported", lang), [],
                [t("qa.reason_allocation_unsupported", lang)])

    if named is not None:
        selected = [row for row in rows if str(row["category"]) == named]
    else:
        selected = [row for row in sorted(rows, key=lambda row: abs(row["difference"]), reverse=True)
                    if row["difference"]][:1]

    parts: list[str] = []
    evidence: list[dict] = []
    if portfolio.get("strategy"):
        parts.append(t("qa.allocation_strategy", lang, strategy=portfolio["strategy"]))
    if portfolio.get("service"):
        parts.append(t("qa.allocation_service", lang, service=portfolio["service"]))
    for row in selected:
        parts.append(t("qa.allocation_deviation", lang, nr=portfolio["nr"], category=row["category"],
                       actual=_format_pct(row["actual"], lang=lang),
                       target=_format_pct(row["target"], lang=lang)))
        evidence.extend(_allocation_evidence(facts, portfolio, row, lang))
    if not selected:
        parts.append(t("qa.allocation_at_target", lang, nr=portfolio["nr"]))

    if not parts:
        return t("qa.allocation_unavailable", lang), [], [t("qa.reason_allocation_missing", lang)]

    return " ".join(parts), evidence, []


def _answer_rules(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about rule violations."""
    violations = facts.get("violations") or []
    client_ref = facts.get("client", {}).get("ref", "unknown")
    
    if not violations:
        # Grounded "no violations" answer with evidence pointing to client ref
        evidence = [{
            "label": "Suitability violations",
            "value": "none",
            "source": "clients.json",
            "path": f"clients[{client_ref}].SuitabilityViolations"
        }]
        return t("qa.rules_none", lang), evidence, []
    
    evidence = []
    parts = []
    
    for violation in violations[:3]:  # Limit to top 3
        rule_desc = violation.get("rule_description") or t("qa.rules_unknown", lang)
        severity = violation.get("severity", t("qa.rules_severity_unknown", lang))
        portfolio_nr = violation.get("portfolio_nr")
        rule_code = violation.get("rule_code", "unknown")
        
        # Main violation evidence
        evidence.append({
            "label": f"Rule violation: {rule_code}",
            "value": severity,
            "source": "clients.json",
            "path": f"clients[{client_ref}].SuitabilityViolations[{rule_code}]"
        })

        # The engine's own comparison, in the engine's own unit. Rows whose two sides are equal are the
        # engine's type guards (a client-type code compared to itself) and carry no information.
        explanation_parts = []
        for val in violation.get("values") or []:
            name = val.get("label") or val.get("field") or t("qa.evidence_default", lang)
            unit = val.get("unit")
            left_val, right_val = val.get("value"), val.get("limit")
            if left_val is None or right_val is None or left_val == right_val:
                continue
            explanation_parts.append(
                f"{name}: {engine_number(left_val, unit)} vs {engine_number(right_val, unit)}")
            step_path = str(val.get("path") or f"clients[{client_ref}].SuitabilityViolations[{rule_code}]")
            evidence.append({
                "label": f"{name} actual",
                "value": left_val,
                "source": val.get("source", "clients.json"),
                "path": f"{step_path}.LeftValue",
            })
            evidence.append({
                "label": f"{name} limit",
                "value": right_val,
                "source": val.get("source", "clients.json"),
                "path": f"{step_path}.RightValue",
            })
        
        # Build answer text
        if portfolio_nr:
            base_text = t("qa.rules_portfolio", lang, nr=portfolio_nr, desc=rule_desc, severity=severity)
        else:
            base_text = t("qa.rules_general", lang, desc=rule_desc, severity=severity)
        
        # Append explanation details if available
        if explanation_parts:
            base_text = base_text.rstrip(".") + " — " + "; ".join(explanation_parts) + "."
        
        parts.append(base_text)
    
    if len(violations) > 3:
        parts.append(t("qa.rules_total", lang, count=len(violations)))
    
    return " ".join(parts), evidence, []


def _requested_currency(question: str, portfolio: dict) -> str | None:
    """The currency the question names, resolved to the group label the exposure rows use.

    The question is matched against the codes and groups this portfolio actually carries (plus its own
    reporting currency) and against the three major codes the dataset itself maps
    (``index.Dataset._currency_group``). Nothing is guessed: an unknown token matches nothing, and the
    caller then reports the exposures the portfolio really has.
    """
    lowered = question.lower()
    tokens: list[tuple[str, str]] = []
    own = str(portfolio.get("currency") or "")
    if own:
        tokens.append((own, own))
    for entry in portfolio.get("position_currencies") or []:
        code = str(entry.get("code") or "")
        group = str(entry.get("group") or "")
        if code:
            tokens.append((code, group or code))
        if group:
            tokens.append((group, group))
    tokens.extend((code, group) for code, group in KNOWN_CURRENCY_GROUPS.items())

    for token, group in tokens:
        if token and re.search(rf"(?<![a-z]){re.escape(token.lower())}(?![a-z])", lowered):
            return group
    return None


def _answer_fx(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about currency exposure from the portfolio's own exposure rows.

    These are the rows F4 renders. The earlier version consulted only ``fx_exposure`` findings, which
    exist above a 30% threshold and never for the portfolio's own currency, so "total bond exposure in
    EUR" was answered with "currency exposure not in the data" while the screen showed the currency
    split — the answer contradicted the page it was on.
    """
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]

    rows = [row for row in (portfolio.get("currency_exposures") or []) if row.get("weight") is not None]
    if not rows:
        return t("qa.fx_unavailable", lang), [], [t("qa.reason_fx_missing", lang)]

    nr = str(portfolio.get("nr") or "")
    ref = facts.get("client", {}).get("ref", "")

    unavailable: list[str] = []
    if any(word in question.lower() for word in ASSET_CLASS_WORDS):
        # An asset class combined with a currency asks for a crossing the data does not carry: it holds
        # the asset-class dimension and the currency dimension separately. Declare that rather than
        # letting the currency figure stand in for the asset class.
        unavailable.append(t("qa.reason_class_currency_missing", lang))

    def label_of(row: dict) -> str:
        return str(row.get("label") or row.get("category") or "")

    def evidence_for(selected: list[dict]) -> list[dict]:
        return [{
            "label": t("qa.fx_currency_label", lang, currency=label_of(row)),
            "value": row["weight"],
            "source": "clients.json",
            "path": (f"clients[{ref}].Portfolios[{nr}].SecurityPositions[*].SAA_CurrencyGroupName and "
                     f"AccountPositions[*].Currency, value-weighted"),
        } for row in selected]

    requested = _requested_currency(question, portfolio)
    if requested:
        match = next((row for row in rows if label_of(row) == requested), None)
        if match is not None:
            return (
                t("qa.fx_currency_weight", lang, nr=nr, currency=requested,
                  value=_format_pct(match["weight"], lang=lang)),
                evidence_for([match]),
                unavailable,
            )
        top = rows[0]
        return (
            t("qa.fx_currency_absent", lang, nr=nr, currency=requested,
              top=label_of(top), value=_format_pct(top["weight"], lang=lang)),
            evidence_for([top]),
            unavailable,
        )

    items = ", ".join(f"{label_of(row)} {_format_pct(row['weight'], lang=lang)}" for row in rows[:4])
    return t("qa.fx_breakdown", lang, nr=nr, items=items), evidence_for(rows[:4]), unavailable


def _answer_liquidity(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about liquidity."""
    evidence = []
    parts = []
    
    # Client liquidity
    liquidity = facts.get("client", {}).get("liquidity")
    if liquidity is not None:
        currency = facts.get("client", {}).get("reporting_currency", "CHF")
        evidence.append({
            "label": t("qa.liquidity_label", lang),
            "value": liquidity,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].LiquidityInDefaultCurrency"
        })
        parts.append(t("qa.liquidity_amount", lang, value=_format_money(liquidity, currency, lang=lang)))
    
    if not parts:
        return t("qa.liquidity_unavailable", lang), [], [t("qa.reason_liquidity_missing", lang)]
    
    return " ".join(parts), evidence, []


def _answer_costs(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about costs/PRC."""
    # Find PRC-related findings
    findings = facts.get("findings") or []
    prc_findings = [f for f in findings if "prc" in str(f.get("title", "")).lower() 
                    or "produktrisiko" in str(f.get("title", "")).lower()]
    
    if prc_findings:
        finding = prc_findings[0]
        evidence = []
        for ev in finding.get("evidence") or []:
            evidence.append({
                "label": ev.get("label", "Evidenz"),
                "value": ev.get("value"),
                "source": ev.get("source", "R3"),
                "path": ev.get("path", "")
            })
        return t("qa.costs_available", lang), evidence, []
    
    # Risk profile max PRC
    risk_profile = facts.get("client", {}).get("risk_profile")
    if risk_profile:
        max_prc = risk_profile.get("max_prc")
        if max_prc is not None:
            evidence = [{
                "label": "Maximales PRC (Risikoprofil)",
                "value": max_prc,
                "source": "clients.json",
                "path": f"clients[{facts['client']['ref']}].RiskProfile.MaxPRC"
            }]
            return t("qa.costs_max_prc", lang, value=max_prc), evidence, []
    
    return t("qa.costs_unavailable", lang), [], [t("qa.reason_prc_missing", lang)]


def _answer_news(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about market news."""
    market_context = facts.get("market_context") or []
    
    if not market_context:
        return t("qa.news_none", lang), [], [t("qa.reason_news_missing", lang)]
    
    evidence = []
    parts = []
    
    for item in market_context[:2]:  # Top 2 headlines
        headline = item.get("headline", "")
        source = item.get("source", "")
        url = item.get("url", "")
        
        evidence.append({
            "label": headline,
            "value": source,
            "source": "X1",
            "path": url
        })
        parts.append(f"{headline} ({source}).")
    
    return " ".join(parts), evidence, []


def _answer_esg(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about ESG."""
    esg_profile = facts.get("client", {}).get("esg_profile")
    
    if esg_profile:
        evidence = [{
            "label": "ESG-Profil",
            "value": esg_profile,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].EsgProfileName"
        }]
        return t("qa.esg_profile", lang, profile=esg_profile), evidence, []
    
    return t("qa.esg_unavailable", lang), [], [t("qa.reason_esg_missing", lang)]


def _answer_instruments(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about instrument candidates (buy/sell/switch recommendations)."""
    candidates = facts.get("instrument_candidates") or {}
    moves = candidates.get("moves") or []
    buys = candidates.get("buys") or []
    
    if not moves and not buys:
        return t("qa.instruments_unavailable", lang), [], [t("qa.reason_no_candidates", lang)]
    
    evidence = []
    parts = []
    
    # Describe proposal moves if any
    if moves:
        buy_moves = [m for m in moves if m.get("direction") == "buy"]
        sell_moves = [m for m in moves if m.get("direction") == "sell"]
        
        if buy_moves:
            names = [m.get("name") or m.get("isin") for m in buy_moves[:3]]
            parts.append(t("qa.instruments_proposal_buys", lang, names=", ".join(names)))
            for m in buy_moves[:3]:
                evidence.extend(m.get("evidence") or [])
        
        if sell_moves:
            names = [m.get("name") or m.get("isin") for m in sell_moves[:3]]
            parts.append(t("qa.instruments_proposal_sells", lang, names=", ".join(names)))
            for m in sell_moves[:3]:
                evidence.extend(m.get("evidence") or [])
    
    # Describe recommendation-list buys if any
    if buys:
        names = [b.get("name") or b.get("isin") for b in buys[:3]]
        parts.append(t("qa.instruments_recommendation_buys", lang, names=", ".join(names)))
        for b in buys[:3]:
            evidence.extend(b.get("evidence") or [])
    
    return " ".join(parts), evidence, []


def _answer_proposals(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about proposals/recommendations."""
    actions = facts.get("actions") or []
    
    if not actions:
        return t("qa.proposals_none", lang), [], [t("qa.reason_proposals_missing", lang)]
    
    evidence = []
    parts = []
    
    for action in actions[:3]:  # Top 3
        action_text = action.get("action", "")
        priority = action.get("priority", "normal")
        
        evidence.append({
            "label": action_text,
            "value": priority,
            "source": "R5",
            "path": f"actions[{action.get('id')}]"
        })
        parts.append(t("qa.proposal_item", lang, action=action_text, priority=priority))
    
    return " ".join(parts), evidence, []


def _answer_risk_profile(facts: dict, question: str, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions specifically about the risk profile."""
    risk_profile = facts.get("client", {}).get("risk_profile")
    
    if risk_profile is None:
        return t("qa.risk_profile_unavailable", lang), [], [t("qa.reason_risk_profile_missing", lang)]
    
    evidence = []
    parts = []
    
    name = risk_profile.get("name")
    if name:
        evidence.append({
            "label": "Risikoprofil Name",
            "value": name,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].RiskProfile.Name"
        })
        parts.append(t("qa.risk_profile_name", lang, name=name))
    
    risk_level = risk_profile.get("risk_level")
    if risk_level is not None:
        evidence.append({
            "label": "Risikostufe",
            "value": risk_level,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].RiskProfile.RiskLevel"
        })
        parts.append(t("qa.risk_profile_level", lang, level=risk_level))
    
    max_vola = risk_profile.get("max_vola")
    if max_vola is not None:
        evidence.append({
            "label": t("qa.max_vola_rp_label", lang),
            "value": max_vola,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].RiskProfile.MaxVola"
        })
        parts.append(t("qa.risk_profile_max_vola", lang, value=_format_pct(max_vola, lang=lang)))
    
    max_prc = risk_profile.get("max_prc")
    if max_prc is not None:
        evidence.append({
            "label": "Maximales PRC",
            "value": max_prc,
            "source": "clients.json",
            "path": f"clients[{facts['client']['ref']}].RiskProfile.MaxPRC"
        })
        parts.append(t("qa.risk_profile_max_prc", lang, value=max_prc))
    
    if not parts:
        return t("qa.risk_profile_fields_missing", lang), [], [t("qa.reason_risk_profile_fields", lang)]
    
    return " ".join(parts), evidence, []


def _answer_data_quality(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer questions about data quality/gaps."""
    unavailable = facts.get("meta", {}).get("unavailable") or []
    
    if not unavailable:
        return t("qa.data_gaps_none", lang), [], []
    
    evidence = []
    parts = []
    
    for gap in unavailable[:5]:  # Limit to 5
        parts.append(gap)
    
    return t("qa.data_gaps_list", lang, gaps=" ".join(parts)), evidence, []


def _answer_numeric(facts: dict, question: str, portfolio: dict | None, lang: str = "en") -> tuple[str, list[dict], list[str]]:
    """Answer numeric questions by extracting the specific metric."""
    if portfolio is None:
        return t("qa.no_portfolio", lang), [], [t("qa.reason_no_portfolio", lang)]
    
    q_lower = question.lower()
    
    # Try to match specific metrics
    if "klumpen" in q_lower or "konzentration" in q_lower or "concentration" in q_lower:
        return _answer_concentration(facts, question, portfolio, lang)
    elif "usd" in q_lower or "dollar" in q_lower or "currency" in q_lower:
        return _answer_fx(facts, question, portfolio, lang)
    elif "vola" in q_lower or "volatilität" in q_lower or "volatility" in q_lower:
        return _answer_risk(facts, question, portfolio, lang)
    elif "rendite" in q_lower or "performance" in q_lower or "return" in q_lower:
        return _answer_performance(facts, question, portfolio, lang)
    elif "var" in q_lower or "value at risk" in q_lower:
        return _answer_risk(facts, question, portfolio, lang)
    elif "liquid" in q_lower or "cash" in q_lower:
        return _answer_liquidity(facts, question, portfolio, lang)
    elif "esg" in q_lower or "nachhaltig" in q_lower or "sustainab" in q_lower:
        return _answer_esg(facts, question, portfolio, lang)
    elif "regel" in q_lower or "rule" in q_lower or "verstoss" in q_lower:
        return _answer_rules(facts, question, portfolio, lang)
    elif "vorschlag" in q_lower or "proposal" in q_lower or "beratung" in q_lower:
        return _answer_proposals(facts, question, portfolio, lang)
    
    return t("qa.numeric_unavailable", lang), [], [t("qa.reason_metric_missing", lang)]


def _answer_web(question: str, lang: str = DEFAULT_LANG) -> dict:
    """Answer an unrouteable question from the public web, and say that it did.

    The bank's data has no route for this question, so the choice is between a bare refusal and a
    sourced web summary. This returns the summary when the model produced one its sources support,
    and the sources themselves when it did not — never unsourced prose.
    """
    result = browse.search(question, limit=WEB_RESULTS_MAX, lang=lang)
    items = result.get("items") or []
    sources = [
        {"title": item.get("title"), "url": item.get("url"), "snippet": item.get("snippet")}
        for item in items
    ]
    if not items:
        return {
            "answer": t("qa.unknown_answer", lang),
            "sources": [],
            "source_kind": "none",
            # The provider's own reasons are what the advisor can act on ("switched off", "no source
            # answered"); the classifier's internal state is not, and reading it under "Not available"
            # told the advisor nothing about their client.
            "unavailable": [str(reason) for reason in (result.get("unavailable") or [])],
        }

    synthesis = browse.synthesize(question, items, lang)
    if synthesis.get("applied"):
        return {
            "answer": t("qa.web_answer", lang, answer=str(synthesis.get("answer") or "")),
            "sources": [sources[index] for index in synthesis.get("used") or []],
            "source_kind": "web",
            "unavailable": [],
        }
    return {
        "answer": t("qa.web_sources_only", lang, count=len(sources)),
        "sources": sources,
        "source_kind": "web",
        "unavailable": [t("qa.web_no_synthesis", lang, reason=str(synthesis.get("reason") or ""))],
    }


# Words that open a question or name the platform itself; never an entity. A capitalised token that is
# neither one of these nor present in the client's context is a proper noun from outside the bank's data.
_ENTITY_STOPWORDS = frozenset({
    "what", "which", "how", "why", "when", "where", "who", "whom", "is", "are", "was", "were", "does",
    "do", "did", "can", "could", "should", "would", "will", "has", "have", "had", "the", "this", "that",
    "these", "those", "there", "and", "or", "for", "with", "from", "about", "into", "tell", "show",
    "give", "explain", "summarise", "summarize", "list", "name", "please", "client", "bank", "data",
    "portfolio", "case", "assessment", "investment", "welche", "welcher", "welches", "wie", "was",
    "warum", "wann", "wo", "wer", "ist", "sind", "war", "waren", "kann", "könnte", "soll", "sollte",
    "wird", "hat", "haben", "hatte", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen",
    "und", "oder", "für", "über", "von", "mit", "zum", "zur", "bitte", "zeig", "zeige", "nenn", "nenne",
    "erklär", "erkläre", "klient", "klientin", "kunde", "kundin", "bank", "daten", "depot", "fall",
})


def _unknown_entities(question: str, context: dict) -> list[str]:
    """Proper nouns the client's data does not carry — the mark of a question about the outside world.

    "Is NVIDIA worth investing?" names NVIDIA, which appears nowhere in this client's context, so the
    answer cannot come from the bank and a public source is the right place to look. "What are the
    strong parts of this case?" names nothing outside the data, so the client's own analysis answers it.
    """
    haystack = json.dumps(context, ensure_ascii=False).lower()
    found = []
    for token in re.findall(r"[A-ZÄÖÜ][\w'&.-]{2,}", question):
        lowered = token.lower()
        if lowered in _ENTITY_STOPWORDS or lowered in haystack:
            continue
        found.append(token)
    return found


_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def _answer_analysis_digest(
    bundle: dict, portfolio: dict | None, lang: str = DEFAULT_LANG
) -> tuple[str, list[dict], list[str]]:
    """What the client's own analysis holds, when the question matches no section of it.

    A question the vocabulary does not cover ("what are the strong parts of this case?", "is the client
    happy?") is not a question for the open web — a generic article about how to build an investment
    case reads as an answer that missed the point. The platform's own answer is the analysis the
    briefing shows, named in its own order of urgency, with the scope stated plainly. Never empty: the
    three briefing sections are always present, and the advisor recognises every item from the screen.
    """
    findings = sorted(
        (bundle.get("findings") or []),
        key=lambda finding: _SEVERITY_RANK.get(str(finding.get("severity") or "").lower(), 9),
    )[:2]
    items = [str(finding.get("title") or "").strip() for finding in findings]
    items += [
        str(action.get("action") or "").strip()
        for action in (bundle.get("actions") or [])[:2]
    ]
    items = [item for item in items if item]
    if not items:
        return t("qa.unknown_answer", lang), [], [t("qa.reason_not_covered", lang)]

    evidence = []
    for finding in findings:
        for entry in finding.get("evidence") or []:
            value = entry.get("value")
            # The QA evidence contract carries scalars. A rule comparison arrives as {"left","right"}
            # — engine numbers that the violations section renders with their units — so it is left out
            # here rather than stringified into something an advisor cannot read as a figure.
            if not isinstance(value, (int, float, str)):
                continue
            evidence.append({
                "label": entry.get("label"),
                "value": entry.get("value"),
                "source": entry.get("source", "R3"),
                "path": entry.get("path", ""),
            })
    return (
        t("qa.digest_lead", lang, items="; ".join(items)),
        evidence,
        [t("qa.reason_not_covered", lang)],
    )


def _context_block(bundle: dict, portfolio: dict | None, lang: str = DEFAULT_LANG) -> dict:
    """The analysis this screen already shows, shaped as the assistant's grounding.

    Only facts the advisor can see on screen: the client profile and tags, each portfolio's figures,
    the findings with their text, the derived actions, compliance results, the bank's own view and the
    headlines about the holdings. Bounded on purpose — a full position ledger would drown the question
    — and every section is named, so the answer can say which one it used.
    """
    client = bundle.get("client") or {}
    client_block: dict[str, Any] = {
        "ref": client.get("ref"),
        "name": client.get("display_name"),
        "type": client.get("type"),
        "is_company": client.get("is_company"),
        "reporting_currency": client.get("reporting_currency"),
        "assets_under_management": client.get("aum"),
        "liquidity": client.get("liquidity"),
        "risk_profile": client.get("risk_profile"),
        "esg_profile": client.get("esg_profile"),
        "tags": [tag.get("name") for tag in (client.get("tags") or [])],
    }
    notes = bundle.get("client_notes") or client.get("notes")
    if isinstance(notes, list) and notes:
        client_block["notes"] = [
            compact(str(note.get("text") if isinstance(note, dict) else note), 160)
            for note in notes[:3]
        ]

    portfolios = []
    for row in bundle.get("portfolios") or []:
        if portfolio is not None and row.get("nr") != portfolio.get("nr"):
            continue
        portfolios.append({
            "nr": row.get("nr"),
            "name": row.get("name"),
            "is_external": row.get("is_external"),
            "currency": row.get("currency"),
            "value": row.get("aum"),
            "return_12m_pct": row.get("return_12m_pct"),
            "return_3m_pct": row.get("return_3m_pct"),
            "volatility": row.get("volatility"),
            "expected_return": row.get("expected_return"),
            "value_at_risk": row.get("value_at_risk"),
            "largest_holding": row.get("top_security"),
            "largest_holding_weight": row.get("top_weight"),
            "currency_exposures": row.get("currency_exposures"),
            "strategy": row.get("strategy"),
            "data_gaps": row.get("data_gaps"),
        })

    findings = [
        {
            "id": finding.get("id"),
            "type": finding.get("type"),
            "severity": finding.get("severity"),
            "title": finding.get("title"),
            "detail": finding.get("detail"),
            "isin": finding.get("isin"),
        }
        for finding in (bundle.get("findings") or [])
    ][:14]

    actions = [
        {"action": action.get("action"), "rationale": action.get("rationale"), "type": action.get("type")}
        for action in (bundle.get("actions") or [])
    ]
    violations = [
        {
            "rule": violation.get("rule_description") or violation.get("rule_code"),
            "level": violation.get("level"),
            "portfolio": violation.get("portfolio_nr"),
        }
        for violation in (bundle.get("violations") or [])
    ][:8]
    candidates = bundle.get("instrument_candidates") or {}
    bank_view = bundle.get("house_view") or {}
    return {
        "client": client_block,
        "portfolios": portfolios,
        "findings": findings,
        "actions": actions,
        "compliance": violations,
        "candidate_instruments": {
            "moves": (candidates.get("moves") or [])[:6],
            "buys": (candidates.get("buys") or [])[:6],
        },
        "bank_view": {
            "source": bank_view.get("source"),
            "as_of": bank_view.get("as_of"),
            "is_mock": bank_view.get("mock"),
            "matches": [
                {k: match.get(k) for k in ("dimension", "category", "stance", "relation", "stance_note")}
                for match in (bank_view.get("matches") or [])[:8]
            ],
        },
        "market_headlines": [
            {
                "headline": item.get("headline"),
                "source": item.get("source"),
                "published": item.get("published"),
                "relevant_because": item.get("relevant_because"),
            }
            for item in (bundle.get("market_context") or [])
        ],
        "declared_gaps": (bundle.get("meta") or {}).get("unavailable") or [],
        "data_as_of": (bundle.get("meta") or {}).get("data_as_of"),
    }


def _answer_from_context(
    bundle: dict,
    portfolio: dict | None,
    question: str,
    lang: str = DEFAULT_LANG,
    context_block: dict | None = None,
) -> dict:
    """Ask the model to answer from the client context, or report why it did not.

    Kept separate from the deterministic router so the two can be compared: when this returns
    ``applied: False`` the caller keeps the routed answer, which is what happens without a key.
    """
    from ..external import llm as llm_module

    if not llm_module.available():
        return {"applied": False, "reason": "no key", "answer": None, "used": []}
    block = context_block if context_block is not None else _context_block(bundle, portfolio, lang)
    return llm_module.answer(question, block, lang)


def answer(client_ref: str, question: str, portfolio_nr: str | None = None, lang: str = "en") -> dict:
    """Answer a follow-up question from the assembled facts bundle.
    
    Returns a dict with:
    - answer: German text, 1-3 sentences
    - evidence: list of evidence entries supporting the answer
    - unavailable: list of unavailable data items
    - matched: dict with findings and sections that were used
    """
    # Assemble the facts bundle
    bundle = facts_module.assemble(client_ref, portfolio_nr, lang=lang)
    
    # A sector/region question is answered from the exposure buckets. It needs both a term the data
    # carries and an exposure wording, so "why is oil falling?" is never answered with portfolio
    # weights — and "what is the total semiconductor exposure?" is (via the declared synonym map).
    exposure_terms = _exposure_terms(question)
    q_lower = question.lower()
    # Rule/violation questions must be checked BEFORE proposal_followup: the word "open" appears in
    # both PROPOSAL_KEYWORDS and PROPOSAL_FOLLOWUP_KEYWORDS, so "Which rule violations are open?"
    # would otherwise route to proposals instead of violations.
    if any(kw in q_lower for kw in RULE_KEYWORDS):
        category, keywords = "rules", [kw for kw in RULE_KEYWORDS if kw in q_lower]
    elif exposure_terms and any(kw in q_lower for kw in EXPOSURE_KEYWORDS):
        category, keywords = "exposure", [label for _, label in exposure_terms]
    elif any(kw in q_lower for kw in NOTES_KEYWORDS):
        category, keywords = "notes", [kw for kw in NOTES_KEYWORDS if kw in q_lower]
    elif any(kw in q_lower for kw in PROPOSAL_KEYWORDS) and any(kw in q_lower for kw in PROPOSAL_FOLLOWUP_KEYWORDS):
        category, keywords = "proposal_followup", [kw for kw in PROPOSAL_FOLLOWUP_KEYWORDS if kw in q_lower]
    elif any(kw in q_lower for kw in INSTRUMENT_KEYWORDS):
        category, keywords = "instruments", [kw for kw in INSTRUMENT_KEYWORDS if kw in q_lower]
    else:
        category, keywords = _classify(question)
    # An instrument question the client's data cannot answer ("should I buy Nestlé?") is exactly the
    # case the advisor wants looked up elsewhere — the platform holds no view on a company that is in
    # neither the holdings, the proposal nor the recommendation list.
    instrument_question = category == "instruments"
    is_numeric = _is_numeric_question(question)
    unsupported = _is_unsupported(question)
    
    # Find the portfolio
    portfolio = _find_portfolio(bundle, portfolio_nr)
    
    # Route to the appropriate answer function
    answer_text = ""
    evidence = []
    unavailable = []
    matched_findings = []
    matched_sections = []
    # Where the answer came from: the bank's data (default) or a public web search, and whether the
    # model phrased it or the deterministic router did.
    source_kind = "data"
    sources: list[dict] = []
    answered_by = "rules"
    unmatched = False
    
    if unsupported == "attribution":
        answer_text = t("qa.unsupported_attribution", lang)
        unavailable.append(t("qa.unsupported_attribution_reason", lang))
        matched_sections.append("recent_development")
    elif category == "exposure":
        # Checked before the numeric path: "Wie hoch ist die Halbleiter-Exposition?" starts with a
        # numeric prefix but is a bucket question, and the numeric extractor has no bucket to read.
        answer_text, evidence, unavailable = _answer_exposure(bundle, question, portfolio, exposure_terms, lang)
        matched_sections.append("health_check")
    elif category == "notes":
        answer_text, evidence, unavailable = _answer_notes(bundle, question, lang)
        matched_sections.append("health_check")
    elif category == "proposal_followup":
        answer_text, evidence, unavailable = _answer_proposal_followup(bundle, question, lang)
        matched_sections.append("outlook_actions")
    elif is_numeric:
        answer_text, evidence, unavailable = _answer_numeric(bundle, question, portfolio, lang)
    elif category == "risk_profile":
        answer_text, evidence, unavailable = _answer_risk_profile(bundle, question, lang)
        matched_sections.append("health_check")
    elif category == "performance":
        answer_text, evidence, unavailable = _answer_performance(bundle, question, portfolio, lang)
        matched_sections.append("recent_development")
    elif category == "risk":
        answer_text, evidence, unavailable = _answer_risk(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
    elif category == "risk_contribution":
        answer_text, evidence, unavailable = _answer_risk_contribution(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
        for f in bundle.get("findings") or []:
            if f.get("type") == "performance_driver":
                matched_findings.append(f.get("id"))
    elif category == "exposure":
        answer_text, evidence, unavailable = _answer_exposure(bundle, question, portfolio, exposure_terms, lang)
        matched_sections.append("health_check")
    elif category == "concentration":
        answer_text, evidence, unavailable = _answer_concentration(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
        # Check for concentration findings
        for f in bundle.get("findings") or []:
            if f.get("type") == "concentration" or "konzentration" in str(f.get("title", "")).lower():
                matched_findings.append(f.get("id"))
    elif category == "allocation":
        answer_text, evidence, unavailable = _answer_allocation(bundle, question, portfolio, lang)
        matched_sections.append("outlook_actions")
    elif category == "rules":
        answer_text, evidence, unavailable = _answer_rules(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
    elif category == "fx":
        answer_text, evidence, unavailable = _answer_fx(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
        # Check for FX findings
        for f in bundle.get("findings") or []:
            if f.get("type") == "fx_exposure" or "währung" in str(f.get("title", "")).lower():
                matched_findings.append(f.get("id"))
    elif category == "liquidity":
        answer_text, evidence, unavailable = _answer_liquidity(bundle, question, portfolio, lang)
        matched_sections.append("recent_development")
    elif category == "costs":
        answer_text, evidence, unavailable = _answer_costs(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
    elif category == "news":
        answer_text, evidence, unavailable = _answer_news(bundle, question, portfolio, lang)
        matched_sections.append("outlook_actions")
    elif category == "esg":
        answer_text, evidence, unavailable = _answer_esg(bundle, question, portfolio, lang)
        matched_sections.append("health_check")
    elif category == "instruments":
        answer_text, evidence, unavailable = _answer_instruments(bundle, question, portfolio, lang)
        matched_sections.append("outlook_actions")
    elif category == "proposals":
        answer_text, evidence, unavailable = _answer_proposals(bundle, question, portfolio, lang)
        matched_sections.append("outlook_actions")
    elif category == "data_quality":
        answer_text, evidence, unavailable = _answer_data_quality(bundle, question, portfolio, lang)
    else:
        # Nothing routed this question, and two very different questions hide behind that: one about
        # *this client* that the vocabulary does not cover ("what are the strong parts of this case?",
        # "is the client happy with the portfolio?"), and one about the world outside the bank's data
        # ("is NVIDIA worth investing?"). The first is answered from the client's own analysis — never
        # from the internet, which cannot know the client and returns an article that reads as an answer
        # that missed the point. The second goes to the web, and that decision is taken below, once the
        # client's own data has had its chance.
        unmatched = True
        answer_text, evidence, unavailable = _answer_analysis_digest(bundle, portfolio, lang)
        matched_sections.append("outlook_actions")
    
    # Prefer the model's wording of this client's own analysis when a key is available. The routed
    # answer is exact but templated, and the advisor asked in their own words; llm.answer rejects any
    # reply carrying a figure the context does not contain, so this can only improve the phrasing.
    context_block = _context_block(bundle, portfolio, lang)
    context_answer = _answer_from_context(bundle, portfolio, question, lang, context_block)
    if context_answer.get("applied"):
        answer_text = str(context_answer.get("answer"))
        answered_by = "llm"
        # It answered from the data, so a route-specific gap no longer applies and the web was unused.
        unavailable = []
        source_kind = "data"
        sources = []

    # The public web answers questions the bank's data cannot *hold* — an instrument the client does not
    # own, a company no recommendation list carries, a market event. It is decided by frame, not by
    # whether the keywords matched:
    #
    #   * an instrument question the data cannot answer goes to the web when the model declines it
    #     ("should I buy Nestlé?") — but NOT when the model never ran: without a key the routed answer
    #     stays in charge, exactly as before;
    #   * an unmatched question goes to the web only if it names something the client's data does not
    #     carry ("is NVIDIA worth investing?"). An unmatched question about *this client* keeps the
    #     analysis digest above, which is the platform's own answer to "what do you know about this
    #     case" — where a web search would return a generic article about investing.
    model_declined = bool(context_answer.get("declined"))
    out_of_frame = instrument_question or (unmatched and bool(_unknown_entities(question, context_block)))
    if not context_answer.get("applied") and out_of_frame and (model_declined or unmatched):
        web = _answer_web(question, lang)
        answer_text = web["answer"]
        sources = web["sources"]
        source_kind = web["source_kind"]
        unavailable = list(web["unavailable"])
        # A public answer has no bank evidence: the digest's rows would name this client's findings
        # next to an answer they do not support, and the sources are this answer's provenance.
        evidence = []

    # Deduplicate evidence by path
    seen_paths = set()
    unique_evidence = []
    for ev in evidence:
        path = ev.get("path", "")
        if path and path not in seen_paths:
            seen_paths.add(path)
            unique_evidence.append(ev)
        elif not path:
            unique_evidence.append(ev)
    
    return {
        "answer": answer_text,
        "answered_by": answered_by,
        "source_kind": source_kind,
        "sources": sources,
        "evidence": unique_evidence,
        "unavailable": unavailable,
        "matched": {
            "findings": matched_findings,
            "sections": matched_sections
        }
    }
