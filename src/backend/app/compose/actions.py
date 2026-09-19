"""R5 — next best actions.

Deterministic candidate generation from R3's findings. This is where the product earns its keep: an
advisor under time pressure needs a short, ordered, defensible to-do list, not a summary.

The LLM may rephrase these sentences but never computes a number and never adds an action (``PROJECT.md``
§6). Every action carries the evidence of the finding it came from, so the UI can trace it back, and
every action references the finding it derives from via ``finding_refs``.

Two rules are domain-specific and non-negotiable:

* when the client has a near-term liquidity need, no action may push them into less liquid holdings;
* a violation is phrased as "clarify with the client", never as "fix the risk" — the violation is the
  risk engine's own statement and is display-only (``PROJECT.md`` §7 rule 5).
"""

from __future__ import annotations

from .format import fraction as fmt_fraction
from ..i18n import t
from ..text import compact
from .render import SEVERITY_RANK, binding_detail, engine_number, evidence_value, findings_of, rule_label

MAX_ACTIONS = 5

# Which finding types deserve an action (the tuple doubles as the relevance order).
ACTIONABLE = (
    "liquidity_event",
    "rule_violation",
    "concentration",
    "sector_concentration",
    "allocation_drift",
    "reinvestment",
    "preference_conflict",
    "fx_exposure",
    "risk_alignment",
    "open_proposal",
    "pending_task",
    "missing_data",
)

ACTION_LABEL_LIMIT = 90
RATIONALE_LIMIT = 120


def _number(finding: dict, *keywords: str) -> float | None:
    value = evidence_value(finding, *keywords)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None

def _enforce_limit(label: str) -> str:
    """Ensure the composed label fits within ACTION_LABEL_LIMIT."""
    return compact(label, ACTION_LABEL_LIMIT)


def _rule_violation_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    left, right, label, unit = binding_detail(finding, lang)
    name = label or compact(rule_label(finding), 50)
    if left is not None and right is not None:
        rationale = t(
            "action.rule_violation_rationale_with_values",
            lang,
            left=engine_number(left, unit),
            right=engine_number(right, unit)
        )
    else:
        rationale = t("action.rule_violation_rationale", lang)
    return _enforce_limit(t("action.rule_violation_label", lang, name=name)), rationale


def _concentration_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    weight = _number(finding, "weight", "gewicht", "top")
    if weight is not None:
        rationale = t("action.concentration_rationale_with_weight", lang, weight=fmt_fraction(weight))
    else:
        rationale = t("action.concentration_rationale", lang)
    return _enforce_limit(t("action.concentration_label", lang, title=compact(finding.get('title'), 70))), rationale


def _sector_concentration_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    weight = _number(finding, "weight", "gewicht", "top")
    if weight is not None:
        rationale = t("action.sector_concentration_rationale_with_weight", lang, weight=fmt_fraction(weight))
    else:
        rationale = t("action.sector_concentration_rationale", lang)
    return _enforce_limit(t("action.sector_concentration_label", lang, title=compact(finding.get('title'), 70))), rationale


def _allocation_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    target = _number(finding, "target", "soll", "ziel")
    actual = _number(finding, "actual", "portfolio", "effektiv")
    if target is not None and actual is not None:
        rationale = t("action.allocation_rationale_with_values", lang, actual=fmt_fraction(actual), target=fmt_fraction(target))
    else:
        rationale = t("action.allocation_rationale", lang)
    return _enforce_limit(t("action.allocation_label", lang, title=compact(finding.get('title'), 70))), rationale

def _fx_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    weight = _number(finding, "weight", "anteil", "usd")
    if weight is not None:
        rationale = t("action.fx_rationale_with_weight", lang, weight=fmt_fraction(weight))
    else:
        rationale = t("action.fx_rationale", lang)
    return _enforce_limit(t("action.fx_label", lang, title=compact(finding.get('title'), 60))), rationale


def _reinvestment_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    # Labels are localized, so the keyword set carries both languages (same convention as _number callers).
    target = _number(finding, "cash target", "cash-ziel")
    actual = _number(finding, "cash actual", "cash effektiv")
    if target is not None and actual is not None:
        rationale = t("action.reinvestment_rationale_with_values", lang,
                      actual=fmt_fraction(actual), target=fmt_fraction(target))
    else:
        rationale = t("action.reinvestment_rationale", lang)
    return t("action.reinvestment_label", lang, title=compact(finding.get('title'), 60)), rationale


def _pending_task_action(finding: dict, lang: str = "en") -> tuple[str, str]:
    # The title already says "open item"; the label says it again, so the note text carries the action.
    note = evidence_value(finding, "note", "notiz")
    return (
        t("action.pending_task_label", lang, title=compact(note or finding.get('title'), 60)),
        t("action.pending_task_rationale", lang),
    )


def _build_from_finding(finding: dict, lang: str = "en") -> tuple[str, str] | None:
    finding_type = str(finding.get("type"))
    title = compact(finding.get("title"), 70)
    detail = compact(finding.get("detail"), RATIONALE_LIMIT)
    if finding_type == "rule_violation":
        return _rule_violation_action(finding, lang)
    if finding_type == "concentration":
        return _concentration_action(finding, lang)
    if finding_type == "sector_concentration":
        return _sector_concentration_action(finding, lang)
    if finding_type == "allocation_drift":
        return _allocation_action(finding, lang)
    if finding_type == "reinvestment":
        return _reinvestment_action(finding, lang)
    if finding_type == "pending_task":
        return _pending_task_action(finding, lang)
    if finding_type == "fx_exposure":
        return _fx_action(finding, lang)
    if finding_type == "preference_conflict":
        # The finding title already says "Conflict: ..."; the label prefix must not repeat it.
        # Strip the "Conflict: " / "Konflikt: " prefix so the composed label reads cleanly.
        title_no_prefix = title
        for prefix in ("Conflict: ", "Konflikt: "):
            if title.startswith(prefix):
                title_no_prefix = title[len(prefix):]
                break
        label = t("action.preference_label", lang, title=title_no_prefix)
        return (compact(label, ACTION_LABEL_LIMIT), t("action.preference_rationale", lang))
    if finding_type == "liquidity_event":
        constraint = t("action.liquidity_constraint", lang)
        return (
            t("action.liquidity_label", lang),
            t("action.liquidity_rationale", lang, detail=detail, constraint=constraint),
        )
    if finding_type == "open_proposal":
        return (
            t("action.open_proposal_label", lang, title=title),
            t("action.open_proposal_rationale", lang),
        )
    if finding_type == "risk_alignment":
        return (
            t("action.risk_profile_label", lang, title=title),
            t("action.risk_profile_rationale", lang),
        )
    if finding_type == "missing_data":
        return (
            t("action.data_gap_label", lang, title=title),
            t("action.data_gap_rationale", lang, detail=detail),
        )
    return None


def _priority_key(candidate: dict) -> tuple[int, int, float, str]:
    return (
        0 if candidate["type"] == "liquidity_event" else 1,
        -SEVERITY_RANK.get(str(candidate["severity"]), 0),
        -candidate["score"],
        str(candidate["type"]),
    )


def build_actions(facts: dict, lang: str = "en") -> list[dict]:
    """Ordered action candidates with priorities, rationale and evidence."""
    candidates: list[dict] = []
    for finding in findings_of(facts, *ACTIONABLE):
        built = _build_from_finding(finding, lang)
        if not built:
            continue
        action_text, rationale = built
        candidates.append({
            "type": finding.get("type"),
            "severity": finding.get("severity"),
            "score": float(finding.get("score") or 0.0),
            "portfolio_id": finding.get("portfolio_id"),
            "action": action_text,
            "rationale": rationale,
            "finding_refs": [str(finding.get("id"))],
            "evidence": list(finding.get("evidence") or []),
        })

    # Add instrument_candidates actions (buys and moves)
    instrument_candidates = facts.get("instrument_candidates") or {}
    moves = instrument_candidates.get("moves") or []
    buys = instrument_candidates.get("buys") or []

    # Prefer moves over buys
    if moves:
        # Find open_proposal finding to cite, with scope discipline
        open_proposal_findings = [f for f in facts.get("findings") or [] if f.get("type") == "open_proposal"]
        if open_proposal_findings:
            # Pick the first move's portfolio_id for scope matching
            move_portfolio_id = moves[0].get("portfolio_id")
            # Find a proposal finding that matches this portfolio (no fallback to avoid scope-leak)
            proposal_finding = next(
                (f for f in open_proposal_findings if f.get("portfolio_id") == move_portfolio_id),
                None
            )
            if proposal_finding:
                # Pick one buy and one sell deliberately
                buy_moves = [m for m in moves if m.get("direction") == "buy"]
                sell_moves = [m for m in moves if m.get("direction") == "sell"]
                
                selected_moves = []
                if buy_moves:
                    selected_moves.append(buy_moves[0])
                if sell_moves:
                    selected_moves.append(sell_moves[0])
                
                # If no mixed direction, take up to 2 from available
                if not selected_moves:
                    selected_moves = moves[:2]
                elif len(selected_moves) < 2:
                    # Fill remaining from same direction
                    remaining = [m for m in moves if m not in selected_moves]
                    selected_moves.extend(remaining[:2 - len(selected_moves)])
                
                # Two name lists, one per direction. A switch label carries two names *and* two
                # direction verbs, so its names get a tighter budget: truncating the composed label
                # instead would cut off the trailing "verkaufen" and turn a sell into a buy.
                is_switch = bool(buy_moves) and bool(sell_moves)
                name_budget = 26 if is_switch else 34
                buy_names = [compact(m.get("name") or m.get("isin"), name_budget)
                             for m in selected_moves if m.get("direction") == "buy"]
                sell_names = [compact(m.get("name") or m.get("isin"), name_budget)
                              for m in selected_moves if m.get("direction") == "sell"]

                if buy_names and sell_names:
                    action_text = t("action.candidates_switch_label", lang,
                                    buy_names=", ".join(buy_names), sell_names=", ".join(sell_names))
                    rationale = t("action.candidates_switch_rationale", lang)
                elif buy_names:
                    # The proposal branch has no underweight class to name, so it uses the
                    # category-free label and the direction-neutral proposal rationale — the
                    # underweight template would ship "{category} by {diff}" unfilled.
                    action_text = t("action.candidates_buy_label_no_category", lang,
                                    names=", ".join(buy_names))
                    rationale = t("action.candidates_switch_rationale", lang)
                else:  # sell only
                    action_text = t("action.candidates_sell_label", lang, names=", ".join(sell_names))
                    rationale = t("action.candidates_sell_rationale", lang)
                action_text = _enforce_limit(action_text)
                
                # Collect evidence from moves (max 4, deduplicated by path)
                evidence = []
                seen_paths = set()
                for move in selected_moves:
                    for ev in move.get("evidence") or []:
                        path = ev.get("path")
                        if path and path not in seen_paths:
                            evidence.append(ev)
                            seen_paths.add(path)
                            if len(evidence) >= 4:
                                break
                    if len(evidence) >= 4:
                        break
                candidates.append({
                    "type": "instrument_candidate",  # New type to avoid collision
                    "severity": proposal_finding.get("severity"),
                    "score": float(proposal_finding.get("score") or 0.0),
                    "portfolio_id": proposal_finding.get("portfolio_id"),
                    "action": action_text,
                    "rationale": rationale,
                    "finding_refs": [str(proposal_finding.get("id"))],
                "evidence": evidence,
            })
    elif buys:
        # Find allocation_drift finding to cite
        drift_findings = [f for f in facts.get("findings") or [] if f.get("type") == "allocation_drift"]
        if drift_findings:
            # Match drift finding to buys' portfolio_id to avoid scope-leak
            buy_portfolio_id = buys[0].get("portfolio_id") if buys else None
            drift_finding = next(
                (f for f in drift_findings if f.get("portfolio_id") == buy_portfolio_id),
                None
            )
            if drift_finding:
                selected_buys = buys[:2]
                # Truncate each name: two full bank instrument names would blow the label limit.
                names = [compact(b.get("name") or b.get("isin"), 34) for b in selected_buys]
                names_str = ", ".join(names)
                # The category comes from the candidate row, never from a bare literal.
                category = selected_buys[0].get("target_category")
                if category:
                    action_text = t("action.candidates_buy_label", lang, names=names_str, category=category)
                    difference = selected_buys[0].get("difference")
                    rationale = t("action.candidates_buy_rationale", lang, category=category,
                                  diff=f"{abs(float(difference)) * 100:.1f}" if difference is not None else "—")
                else:
                    action_text = t("action.candidates_buy_label_no_category", lang, names=names_str)
                    rationale = t("action.candidates_buy_rationale_no_category", lang)

                action_text = compact(action_text, ACTION_LABEL_LIMIT)

                # Evidence from the selected buys, max 4 entries, deduplicated by path.
                evidence = []
                seen_paths = set()
                for buy in selected_buys:
                    for ev in buy.get("evidence") or []:
                        path = ev.get("path")
                        if path and path not in seen_paths:
                            evidence.append(ev)
                            seen_paths.add(path)
                            if len(evidence) >= 4:
                                break
                    if len(evidence) >= 4:
                        break
                candidates.append({
                    # Its own type: `allocation_drift` already produces an action, and the
                    # one-per-type dedupe below would otherwise drop one of the two.
                    "type": "instrument_candidate",
                    "severity": drift_finding.get("severity"),
                    "score": float(drift_finding.get("score") or 0.0),
                    "portfolio_id": drift_finding.get("portfolio_id"),
                    "action": action_text,
                    "rationale": rationale,
                    "finding_refs": [str(drift_finding.get("id"))],
                    "evidence": evidence,
                })

    if any(candidate["type"] == "liquidity_event" for candidate in candidates):
        constraint = t("action.liquidity_constraint", lang)
        for candidate in candidates:
            if candidate["type"] in ("allocation_drift", "concentration") and constraint not in candidate["rationale"]:
                candidate["rationale"] = f"{candidate['rationale']} {t('action.liquidity_constraint_suffix', lang, constraint=constraint)}"

    candidates.sort(key=_priority_key)

    # One action per finding type keeps the list short enough to act on.
    seen: set[str] = set()
    selected: list[dict] = []
    for candidate in candidates:
        if str(candidate["type"]) in seen:
            continue
        seen.add(str(candidate["type"]))
        selected.append(candidate)
        if len(selected) >= MAX_ACTIONS:
            break

    actions: list[dict] = []
    for position, candidate in enumerate(selected, start=1):
        portfolio = next(
            (p for p in facts.get("portfolios") or [] if p.get("id") == candidate.get("portfolio_id")),
            None,
        )
        evidence = list(candidate["evidence"])
        if portfolio and not evidence:
            evidence = [{
                "label": t("action.portfolio_nr", lang, nr=portfolio.get('nr')),
                "value": portfolio.get("aum"),
                "source": "clients.json",
                "path": f"clients[{facts['client']['ref']}].Portfolios[{portfolio.get('nr')}]",
            }]
        actions.append({
            "id": f"a{position}",
            "priority": position,
            "type": candidate.get("type"),
            "action": candidate["action"],
            "rationale": candidate["rationale"],
            "finding_refs": candidate["finding_refs"],
            "evidence": evidence,
            "portfolio_id": candidate.get("portfolio_id"),
        })
    return actions
