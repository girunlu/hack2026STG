"""F6 — CRM context source.

In real life this is the bank's CRM. Here it is the ``ClientNotes[]``, ``Tags[]`` and
``IndividualRuleOverrides[]`` of the provided file — thin, and the notes are heavily duplicated
(53 distinct texts across 153 rows), so duplicates are flagged rather than silently repeated.
"""

from __future__ import annotations

from .ingest import day, intnum, listof, num, text


def notes(client: dict) -> list[dict]:
    """Client notes, newest first, with duplicates flagged.

    ``duplicate_of`` is the index of the first occurrence of the same text, so a UI can collapse them
    without losing the fact that the note was recorded more than once.
    """
    seen: dict[str, int] = {}
    rows: list[dict] = []
    for raw in listof(client, "ClientNotes"):
        body = text(raw, "Note").strip()
        first = seen.get(body)
        if first is None:
            seen[body] = len(rows)
        rows.append({
            "index": len(rows),
            "text": body,
            "date": day(raw.get("CreatedByDateUTC")),
            "duplicate_of": first,
            "source": "clients.json",
            "path": f"clients[{text(client, 'ClientRef')}].ClientNotes[{len(rows)}]",
        })
    rows.sort(key=lambda row: (row["date"] or "", -row["index"]), reverse=True)
    return rows


def distinct_notes(client: dict) -> list[dict]:
    """Notes with duplicates collapsed to their most recent occurrence."""
    out: list[dict] = []
    seen: set[str] = set()
    for row in notes(client):
        if row["text"] in seen:
            continue
        seen.add(row["text"])
        out.append({**row, "duplicate_count": sum(1 for n in listof(client, "ClientNotes") if text(n, "Note").strip() == row["text"])})
    return out


def tags(client: dict) -> dict:
    """Client tags split by type; ``Region`` and ``Industry`` render as distinct chip styles."""
    region, industry, other = [], [], []
    for tag in listof(client, "Tags"):
        entry = {
            "name": text(tag, "TagName"),
            "type": text(tag, "TagTypeName"),
            "scope": text(tag, "Scope"),
        }
        if entry["type"] == "Region":
            region.append(entry)
        elif entry["type"] == "Industry":
            industry.append(entry)
        else:
            other.append(entry)
    return {"region": region, "industry": industry, "other": other, "all": region + industry + other}


def overrides(client: dict) -> list[dict]:
    """Individual rule overrides (present on 3 clients, ``null`` on 44)."""
    return [
        {
            "rule_code": text(raw, "RuleCode"),
            "description": text(raw, "Description"),
            "source": "clients.json",
            "path": f"clients[{text(client, 'ClientRef')}].IndividualRuleOverrides",
        }
        for raw in listof(client, "IndividualRuleOverrides")
    ]


def latest_activity(client: dict) -> dict:
    """Newest known activity date: proposals and notes are the only dated evidence available.

    Drives the ``03 - Last Consultation > 12 Months`` filter and the "Letzte Beratung" column. There
    is no contact-log field in the data, which is declared rather than invented.
    """
    candidates: list[tuple[str, str]] = []
    for proposal in listof(client, "Proposals"):
        stamp = day(proposal.get("FinalizedDateUTC")) or day(proposal.get("ProposedDateUTC"))
        if stamp:
            candidates.append((stamp, f"proposal {intnum(proposal, 'ProposalId', -1)}"))
    for note in listof(client, "ClientNotes"):
        stamp = day(note.get("CreatedByDateUTC"))
        if stamp:
            candidates.append((stamp, "note"))
    if not candidates:
        return {"date": None, "source": None, "basis": "no proposals or notes carry a date"}
    stamp, source = max(candidates, key=lambda item: item[0])
    return {
        "date": stamp,
        "source": source,
        "basis": "latest of FinalizedDateUTC/ProposedDateUTC and ClientNotes.CreatedByDateUTC",
        "proposal_count": len(listof(client, "Proposals")),
        "note_count": len(listof(client, "ClientNotes")),
    }


def liquidity_ratio(client: dict) -> float | None:
    """Cash weight of the client, from ``LiquidityInDefaultCurrency`` / AUM."""
    aum = num(client, "AssetsUnderManagementInDefaultCurrency")
    if aum <= 0:
        return None
    return round(num(client, "LiquidityInDefaultCurrency") / aum, 6)
