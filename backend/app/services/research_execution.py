from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.research import AgentArtifact, ResearchEvent, ResearchSession
from app.infrastructure.database import SessionLocal
from app.infrastructure.tools.models import ResolvedCompany, ToolFailure, ToolSource
from app.infrastructure.tools.sec_edgar import SecEdgarTool
from app.infrastructure.tools.yahoo_finance import YahooFinanceTool
from app.services.report_synthesis import AnthropicReportModel, build_evidence, synthesize_report


class ResearchAlreadyExecutedError(Exception):
    """Raised when a caller requests an unsafe duplicate execution."""


class ResearchExecutionNotFoundError(Exception):
    """Raised when an execution target does not exist."""


class ResearchTools:
    def __init__(self) -> None:
        settings = get_settings()
        self.finance = YahooFinanceTool(
            timeout_seconds=settings.research_http_timeout_seconds,
            user_agent=settings.research_user_agent,
        )
        self.sec = SecEdgarTool(
            timeout_seconds=settings.research_http_timeout_seconds,
            user_agent=settings.research_user_agent,
        )

    def close(self) -> None:
        self.finance.close()
        self.sec.close()


def request_execution(db: Session, session_id: UUID) -> ResearchSession:
    session = db.get(ResearchSession, session_id)
    if session is None:
        raise ResearchExecutionNotFoundError
    if session.status != "planned":
        raise ResearchAlreadyExecutedError
    session.status = "queued"
    _record_event(
        db,
        session.id,
        "research.queued",
        "Research execution queued",
        "Specialist agents will run with source-attributed tools.",
    )
    db.commit()
    return session


def execute_research(session_id: UUID) -> None:
    """Run deterministic specialist agents in a background worker thread.

    The agents only summarize tool payloads. They do not generate unsupported factual claims.
    """
    db = SessionLocal()
    tools = ResearchTools()
    try:
        session = db.get(ResearchSession, session_id)
        if session is None or session.status != "queued":
            return
        session.status = "running"
        _record_event(
            db,
            session.id,
            "research.running",
            "Research execution started",
            "Resolving the company and collecting primary sources.",
        )
        db.commit()

        try:
            company = tools.finance.resolve_company(session.query)
        except ToolFailure as error:
            session.status = "failed"
            _record_event(
                db, session.id, "research.failed", "Company resolution failed", str(error)
            )
            db.commit()
            return

        session_events: list[
            tuple[str, Callable[[ResolvedCompany], tuple[str, dict[str, Any], list[ToolSource]]]]
        ] = [
            ("company_profile", lambda resolved: _company_profile_agent(tools, resolved)),
            ("financial_analysis", lambda resolved: _financial_analysis_agent(tools, resolved)),
            ("sec_filings", lambda resolved: _sec_filing_agent(tools, resolved)),
            ("news", lambda resolved: _news_agent(tools, resolved)),
            ("sentiment", lambda resolved: _sentiment_agent(tools, resolved)),
        ]
        failures = 0
        for agent_name, agent in session_events:
            _record_event(
                db,
                session.id,
                "agent.started",
                f"{agent_name.replace('_', ' ').title()} started",
                None,
                {"agent": agent_name},
            )
            db.commit()
            try:
                summary, output, sources = agent(company)
                artifact_status = "completed"
            except ToolFailure as error:
                failures += 1
                summary, output, sources = (
                    str(error),
                    {"ticker": company.ticker, "error": str(error)},
                    [],
                )
                artifact_status = "failed"
            db.add(
                AgentArtifact(
                    research_session_id=session.id,
                    agent_name=agent_name,
                    status=artifact_status,
                    summary=summary,
                    output=output,
                    sources=[source.model_dump(mode="json") for source in sources],
                )
            )
            _record_event(
                db,
                session.id,
                f"agent.{artifact_status}",
                f"{agent_name.replace('_', ' ').title()} {artifact_status}",
                summary,
                {"agent": agent_name},
            )
            db.commit()

        failures += _run_committee(db, session, company)
        session.status = "completed" if failures == 0 else "partial_failure"
        _record_event(
            db,
            session.id,
            "research.completed",
            "Research collection finished",
            "All available specialist artifacts are ready."
            if failures == 0
            else "Some source providers were unavailable; inspect affected artifacts.",
        )
        db.commit()
    except Exception as error:  # Defensive worker boundary: persist a safe public failure event.
        db.rollback()
        session = db.get(ResearchSession, session_id)
        if session is not None:
            session.status = "failed"
            _record_event(
                db, session.id, "research.failed", "Research execution failed", type(error).__name__
            )
            db.commit()
    finally:
        tools.close()
        db.close()


def _run_committee(db: Session, session: ResearchSession, company: ResolvedCompany) -> int:
    """Synthesize the cited committee report. Returns 1 if it was attempted and failed."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        _record_event(
            db,
            session.id,
            "agent.skipped",
            "Investment Committee skipped",
            "ANTHROPIC_API_KEY is not configured.",
        )
        db.commit()
        return 0
    _record_event(
        db,
        session.id,
        "agent.started",
        "Investment Committee started",
        None,
        {"agent": "investment_committee"},
    )
    db.commit()
    db.refresh(session)
    evidence = build_evidence(
        [
            {
                "agent_name": a.agent_name,
                "status": a.status,
                "output": a.output,
                "sources": a.sources,
            }
            for a in session.artifacts
        ]
    )
    try:
        verified = synthesize_report(
            AnthropicReportModel(settings.anthropic_api_key, settings.anthropic_model),
            company.ticker,
            evidence,
        )
    except Exception as error:  # Model/API errors must not discard the collected artifacts.
        _record_event(
            db, session.id, "agent.failed", "Investment Committee failed", type(error).__name__
        )
        db.commit()
        return 1
    cited = {
        i
        for claim in (
            *verified.report.bull_case,
            *verified.report.bear_case,
            *verified.report.risks,
        )
        for i in claim.evidence_ids
    }
    output = verified.model_dump(mode="json")
    output["evidence"] = [
        {
            "id": e.id,
            "text": e.text,
            "source_url": e.source_url,
            "source_title": e.source_title,
            "publisher": e.publisher,
        }
        for e in evidence
        if e.id in cited
    ]
    sources = {
        e.source_url: {"title": e.source_title, "url": e.source_url, "publisher": e.publisher}
        for e in evidence
        if e.id in cited and e.source_url
    }
    db.add(
        AgentArtifact(
            research_session_id=session.id,
            agent_name="investment_committee",
            status="completed",
            summary=verified.report.summary,
            output=output,
            sources=list(sources.values()),
        )
    )
    _record_event(
        db,
        session.id,
        "agent.completed",
        "Investment Committee completed",
        f"Rating {verified.report.rating}; "
        f"{verified.grounding_rate:.0%} of claims verified against evidence.",
        {"agent": "investment_committee", "grounding_rate": verified.grounding_rate},
    )
    db.commit()
    return 0


def _record_event(
    db: Session,
    session_id: UUID,
    event_type: str,
    title: str,
    detail: str | None,
    payload: dict[str, Any] | None = None,
) -> None:
    sequence = db.scalar(
        select(func.coalesce(func.max(ResearchEvent.sequence), 0) + 1).where(
            ResearchEvent.research_session_id == session_id
        )
    )
    db.add(
        ResearchEvent(
            research_session_id=session_id,
            sequence=sequence,
            type=event_type,
            title=title,
            detail=detail,
            payload=payload,
        )
    )


def _company_profile_agent(
    tools: ResearchTools, company: ResolvedCompany
) -> tuple[str, dict[str, Any], list[ToolSource]]:
    profile, sources = tools.finance.profile(company.ticker)
    output = {
        "ticker": company.ticker,
        "company_name": company.name,
        "exchange": company.exchange,
        "industry": profile.get("industry"),
        "sector": profile.get("sector"),
        "website": profile.get("website"),
        "employees": profile.get("fullTimeEmployees"),
        "business_summary": profile.get("longBusinessSummary"),
    }
    return f"Company profile collected for {company.name} ({company.ticker}).", output, sources


def _financial_analysis_agent(
    tools: ResearchTools, company: ResolvedCompany
) -> tuple[str, dict[str, Any], list[ToolSource]]:
    statements, sources = tools.finance.financials(company.ticker)
    financial_data = statements.get("financialData", {})
    income = (statements.get("incomeStatementHistory", {}).get("incomeStatementHistory") or [{}])[0]
    balance = (statements.get("balanceSheetHistory", {}).get("balanceSheetStatements") or [{}])[0]
    cashflow = (statements.get("cashflowStatementHistory", {}).get("cashflowStatements") or [{}])[0]

    def value(item: Any) -> Any:
        return item.get("raw") if isinstance(item, dict) else item

    output = {
        "ticker": company.ticker,
        "currency": income.get("currencyCode"),
        "revenue": value(income.get("totalRevenue")),
        "gross_profit": value(income.get("grossProfit")),
        "operating_income": value(income.get("operatingIncome")),
        "net_income": value(income.get("netIncome")),
        "free_cash_flow": value(
            financial_data.get("freeCashflow") or cashflow.get("totalCashFromOperatingActivities")
        ),
        "cash": value(balance.get("cash")),
        "total_debt": value(financial_data.get("totalDebt")),
        "current_ratio": value(financial_data.get("currentRatio")),
        "return_on_equity": value(financial_data.get("returnOnEquity")),
    }
    return (
        f"Latest available financial statement metrics collected for {company.ticker}.",
        output,
        sources,
    )


def _sec_filing_agent(
    tools: ResearchTools, company: ResolvedCompany
) -> tuple[str, dict[str, Any], list[ToolSource]]:
    filings, sources = tools.sec.latest_filings(company.ticker)
    return (
        f"Found {len(filings)} recent 10-K/10-Q filings for {company.ticker}.",
        {"ticker": company.ticker, "filings": filings},
        sources,
    )


def _news_agent(
    tools: ResearchTools, company: ResolvedCompany
) -> tuple[str, dict[str, Any], list[ToolSource]]:
    articles, sources = tools.finance.news(company.ticker)
    categories: dict[str, list[dict[str, Any]]] = {
        "earnings": [],
        "ai": [],
        "partnerships": [],
        "regulation": [],
        "other": [],
    }
    for article in articles:
        title = article["title"].lower()
        category = (
            "earnings"
            if "earnings" in title
            else "ai"
            if " ai" in title or "artificial intelligence" in title
            else "partnerships"
            if "partner" in title
            else "regulation"
            if any(word in title for word in ("regulat", "antitrust", "lawsuit"))
            else "other"
        )
        categories[category].append(article)
    return (
        f"Collected {len(articles)} recent news articles for {company.ticker}.",
        {"ticker": company.ticker, "categories": categories},
        sources,
    )


def _sentiment_agent(
    tools: ResearchTools, company: ResolvedCompany
) -> tuple[str, dict[str, Any], list[ToolSource]]:
    articles, sources = tools.finance.news(company.ticker)
    positive = ("beat", "growth", "record", "upgrade", "surge", "profit")
    negative = ("miss", "lawsuit", "cut", "decline", "risk", "downgrade")
    scores = {"bullish": 0, "bearish": 0, "neutral": 0}
    for article in articles:
        title = article["title"].lower()
        scores[
            "bullish"
            if any(word in title for word in positive)
            else "bearish"
            if any(word in title for word in negative)
            else "neutral"
        ] += 1
    total = sum(scores.values()) or 1
    output = {
        "ticker": company.ticker,
        "article_count": len(articles),
        **{key: round(value * 100 / total, 1) for key, value in scores.items()},
        "method": "Deterministic headline keyword classification; not analyst sentiment.",
    }
    return (
        f"Headline sentiment classified from {len(articles)} source-attributed articles.",
        output,
        sources,
    )
