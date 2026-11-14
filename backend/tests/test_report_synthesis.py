from typing import Any

import pytest

from app.services.report_synthesis import (
    EvidenceItem,
    ReportError,
    build_evidence,
    synthesize_report,
)

ARTIFACTS: list[dict[str, Any]] = [
    {
        "agent_name": "financial_analysis",
        "status": "completed",
        "output": {
            "ticker": "NVDA",
            "revenue": 130_497_000_000,
            "return_on_equity": 0.25,
            "cash": None,
        },
        "sources": [{"title": "Financial statements", "url": "https://y/f", "publisher": "Yahoo"}],
    },
    {
        "agent_name": "news",
        "status": "completed",
        "output": {
            "categories": {
                "ai": [{"title": "NVDA ships new chip", "url": "https://n/1"}],
                "other": [],
            }
        },
        "sources": [{"title": "NVDA ships new chip", "url": "https://n/1", "publisher": "Wire"}],
    },
    {"agent_name": "sec_filings", "status": "failed", "output": {"error": "x"}, "sources": []},
]


class FakeModel:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def generate(self, ticker: str, evidence: list[EvidenceItem]) -> dict[str, Any]:
        return self.payload


def _ids(evidence: list[EvidenceItem], needle: str) -> int:
    return next(e.id for e in evidence if needle in e.text)


def test_evidence_skips_failed_artifacts_and_nulls() -> None:
    evidence = build_evidence(ARTIFACTS)
    assert [e.id for e in evidence] == [1, 2, 3]
    assert not any("cash" in e.text for e in evidence)
    assert evidence[2].source_url == "https://n/1"


def test_grounded_claims_survive_and_ungrounded_are_dropped() -> None:
    evidence = build_evidence(ARTIFACTS)
    rev, roe, news = (
        _ids(evidence, "revenue"),
        _ids(evidence, "return_on_equity"),
        _ids(evidence, "News"),
    )
    payload = {
        "rating": "positive",
        "confidence": 0.6,
        "summary": "Strong fundamentals.",
        "bull_case": [
            {"text": "Revenue reached $130.5B.", "evidence_ids": [rev]},
            {"text": "ROE is 25%.", "evidence_ids": [roe]},
            {"text": "Revenue reached $200B.", "evidence_ids": [rev]},  # wrong number
            {"text": "Margins are expanding.", "evidence_ids": []},  # uncited
            {"text": "Cited a fake source.", "evidence_ids": [99]},
        ],
        "bear_case": [{"text": "News flow is product-driven.", "evidence_ids": [news]}],
        "risks": [],
    }
    result = synthesize_report(FakeModel(payload), "NVDA", evidence)
    assert [c.text for c in result.report.bull_case] == ["Revenue reached $130.5B.", "ROE is 25%."]
    assert len(result.report.bear_case) == 1
    assert {d.reason.split(":")[0] for d in result.dropped} == {
        "number not in cited evidence",
        "no valid evidence cited",
    }
    assert result.grounding_rate == 0.5  # 3 of 6 claims survive


def test_number_must_be_in_the_cited_item_not_just_any_item() -> None:
    evidence = build_evidence(ARTIFACTS)
    news, roe = _ids(evidence, "News"), _ids(evidence, "return_on_equity")
    payload = {
        "rating": "neutral",
        "confidence": 0.5,
        "summary": "s",
        "bull_case": [{"text": "Revenue reached $130.5B.", "evidence_ids": [news, roe]}],
    }
    result = synthesize_report(FakeModel(payload), "NVDA", evidence)
    assert result.report.bull_case == [] and result.grounding_rate == 0.0


def test_malformed_model_output_and_empty_evidence_raise() -> None:
    evidence = build_evidence(ARTIFACTS)
    with pytest.raises(ReportError):
        synthesize_report(FakeModel({"rating": "moon"}), "NVDA", evidence)
    with pytest.raises(ReportError):
        synthesize_report(FakeModel({}), "NVDA", [])
