"""Evidence-grounded investment committee report.

The LLM never sees raw web text and never writes free-form facts. It receives a numbered
evidence list built from tool output, must cite evidence ids for every claim, and its output is
then verified deterministically: claims with unknown citations or numbers that the cited
evidence does not support are dropped. ``grounding_rate`` reports how many claims survived.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, ValidationError

DISCLAIMER = (
    "Model-generated summary of public data for educational purposes. Not investment advice."
)
_REL_TOLERANCE = 0.01
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12}
_NUMBER = re.compile(r"(?<![\w.])(\$?)(-?\d[\d,]*\.?\d*)\s?(%|[kKmMbBtT](?![a-zA-Z]))?")


class ReportError(Exception):
    """The model response could not be turned into a valid report."""


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    id: int
    text: str
    source_title: str
    source_url: str
    publisher: str
    values: tuple[float, ...] = field(default_factory=tuple)


class Claim(BaseModel):
    text: str = Field(min_length=3, max_length=400)
    evidence_ids: list[int] = Field(default_factory=list)


class CommitteeReport(BaseModel):
    rating: Literal["positive", "neutral", "negative"]
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str = Field(max_length=800)
    bull_case: list[Claim] = Field(default_factory=list, max_length=6)
    bear_case: list[Claim] = Field(default_factory=list, max_length=6)
    risks: list[Claim] = Field(default_factory=list, max_length=6)


class DroppedClaim(BaseModel):
    text: str
    reason: str


class VerifiedReport(BaseModel):
    report: CommitteeReport
    grounding_rate: float
    dropped: list[DroppedClaim]
    disclaimer: str = DISCLAIMER


class ReportModel(Protocol):
    def generate(self, ticker: str, evidence: list[EvidenceItem]) -> dict[str, Any]: ...


def build_evidence(artifacts: list[dict[str, Any]]) -> list[EvidenceItem]:
    """Flatten completed agent artifacts into citable facts.

    Each artifact is ``{"agent_name", "status", "output", "sources"}``.
    """
    items: list[EvidenceItem] = []

    def add(text: str, source: dict[str, Any], values: tuple[float, ...] = ()) -> None:
        items.append(
            EvidenceItem(
                id=len(items) + 1,
                text=text,
                source_title=str(source.get("title", "")),
                source_url=str(source.get("url", "")),
                publisher=str(source.get("publisher", "")),
                values=values,
            )
        )

    for artifact in artifacts:
        if artifact.get("status") != "completed":
            continue
        output: dict[str, Any] = artifact.get("output") or {}
        sources: list[dict[str, Any]] = artifact.get("sources") or []
        primary = sources[0] if sources else {}
        agent = str(artifact.get("agent_name"))
        by_url = {s.get("url"): s for s in sources}
        for key, value in output.items():
            if key in {"ticker", "error", "method"} or value in (None, "", [], {}):
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, int | float):
                add(f"{agent}.{key} = {_humanize(float(value))}", primary, (float(value),))
            elif isinstance(value, str):
                add(f"{agent}.{key}: {value[:500]}", primary)
            elif key == "filings" and isinstance(value, list):
                for filing in value:
                    src = by_url.get(filing.get("url"), primary)
                    add(f"SEC filing: {json.dumps(filing, default=str)[:300]}", src)
            elif key == "categories" and isinstance(value, dict):
                for category, articles in value.items():
                    for article in articles:
                        src = by_url.get(article.get("url"), primary)
                        add(f"News ({category}): {article.get('title', '')}", src)
    return items


def _humanize(value: float) -> str:
    magnitude = abs(value)
    for suffix, scale in (("T", 1e12), ("B", 1e9), ("M", 1e6)):
        if magnitude >= scale:
            return f"{value / scale:.2f}{suffix} (raw {value:g})"
    return f"{value:g}"


def _claim_numbers(text: str) -> list[float]:
    numbers: list[float] = []
    for _, digits, suffix in _NUMBER.findall(text):
        try:
            value = float(digits.replace(",", ""))
        except ValueError:
            continue
        if suffix and suffix not in {"%"}:
            value *= _SUFFIX[suffix.lower()]
        elif not suffix and (abs(value) < 10 or 1990 <= value <= 2100):
            continue  # ordinals, counts and calendar years are not quantitative claims
        numbers.append(value)
    return numbers


def _supported(number: float, evidence: list[EvidenceItem]) -> bool:
    for item in evidence:
        for raw in item.values:
            for candidate in (raw, raw * 100.0):  # ratios may be quoted as percentages
                if candidate == 0 and number == 0:
                    return True
                if candidate and abs(number - candidate) <= _REL_TOLERANCE * abs(candidate):
                    return True
    return False


def verify_report(report: CommitteeReport, evidence: list[EvidenceItem]) -> VerifiedReport:
    by_id = {item.id: item for item in evidence}
    dropped: list[DroppedClaim] = []
    kept_total = 0
    seen_total = 0

    def check(claims: list[Claim]) -> list[Claim]:
        nonlocal kept_total, seen_total
        kept: list[Claim] = []
        for claim in claims:
            seen_total += 1
            cited = [by_id[i] for i in dict.fromkeys(claim.evidence_ids) if i in by_id]
            if not cited:
                dropped.append(DroppedClaim(text=claim.text, reason="no valid evidence cited"))
                continue
            ungrounded = [n for n in _claim_numbers(claim.text) if not _supported(n, cited)]
            if ungrounded:
                dropped.append(
                    DroppedClaim(
                        text=claim.text, reason=f"number not in cited evidence: {ungrounded[0]:g}"
                    )
                )
                continue
            kept_total += 1
            kept.append(Claim(text=claim.text, evidence_ids=[item.id for item in cited]))
        return kept

    cleaned = report.model_copy(
        update={
            "bull_case": check(report.bull_case),
            "bear_case": check(report.bear_case),
            "risks": check(report.risks),
        }
    )
    rate = kept_total / seen_total if seen_total else 0.0
    return VerifiedReport(report=cleaned, grounding_rate=round(rate, 3), dropped=dropped)


def synthesize_report(
    model: ReportModel, ticker: str, evidence: list[EvidenceItem]
) -> VerifiedReport:
    if not evidence:
        raise ReportError("No completed evidence is available to synthesize")
    try:
        report = CommitteeReport.model_validate(model.generate(ticker, evidence))
    except ValidationError as error:
        raise ReportError("Model returned a malformed report") from error
    return verify_report(report, evidence)


SYSTEM_PROMPT = (
    "You are an equity research analyst writing for an investment committee. Use ONLY the numbered "
    "evidence provided. Every claim must list the evidence ids that support it. Quote numbers "
    "exactly "
    "as they appear in the evidence. If evidence is thin, say so and lower your confidence. Do not "
    "give personalized advice."
)

REPORT_TOOL: Any = {
    "name": "submit_report",
    "description": "Submit the evidence-cited investment committee report.",
    "input_schema": CommitteeReport.model_json_schema(),
}


class AnthropicReportModel:
    def __init__(self, api_key: str, model: str, max_tokens: int = 2000) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def generate(self, ticker: str, evidence: list[EvidenceItem]) -> dict[str, Any]:
        listing = "\n".join(f"[{item.id}] {item.text}" for item in evidence)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            tools=[REPORT_TOOL],
            tool_choice={"type": "tool", "name": "submit_report"},
            messages=[{"role": "user", "content": f"Ticker: {ticker}\n\nEvidence:\n{listing}"}],
        )
        for block in response.content:
            if block.type == "tool_use":
                return dict(block.input)
        raise ReportError("Model did not return a report")
