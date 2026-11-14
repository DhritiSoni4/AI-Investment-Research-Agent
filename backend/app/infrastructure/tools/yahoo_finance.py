from typing import Any

import httpx

from app.infrastructure.tools.models import ResolvedCompany, ToolFailure, ToolSource


class YahooFinanceTool:
    """Small, source-attributed adapter for Yahoo Finance's public query endpoints."""

    publisher = "Yahoo Finance"
    base_url = "https://query1.finance.yahoo.com"

    def __init__(self, timeout_seconds: float, user_agent: str) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept": "application/json"},
        )

    def close(self) -> None:
        self._client.close()

    def resolve_company(self, query: str) -> ResolvedCompany:
        try:
            response = self._client.get(f"{self.base_url}/v1/finance/search", params={"q": query})
            response.raise_for_status()
            quotes = response.json().get("quotes", [])
        except (httpx.HTTPError, ValueError) as error:
            raise ToolFailure("Yahoo Finance company search is unavailable") from error
        quote = next((item for item in quotes if item.get("quoteType") == "EQUITY"), None)
        if quote is None or not quote.get("symbol"):
            raise ToolFailure(f"No publicly listed company was found for '{query}'")
        return ResolvedCompany(
            ticker=quote["symbol"],
            name=quote.get("longname") or quote.get("shortname") or quote["symbol"],
            exchange=quote.get("exchDisp"),
        )

    def profile(self, ticker: str) -> tuple[dict[str, Any], list[ToolSource]]:
        data = self._quote_summary(ticker, "assetProfile,summaryProfile")
        result = data.get("quoteSummary", {}).get("result") or []
        if not result:
            raise ToolFailure(f"Profile data is unavailable for {ticker}")
        profile = result[0].get("assetProfile") or result[0].get("summaryProfile") or {}
        return profile, [self._source(ticker, "Company profile")]

    def financials(self, ticker: str) -> tuple[dict[str, Any], list[ToolSource]]:
        modules = (
            "incomeStatementHistory,balanceSheetHistory,cashflowStatementHistory,financialData"
        )
        data = self._quote_summary(ticker, modules)
        result = data.get("quoteSummary", {}).get("result") or []
        if not result:
            raise ToolFailure(f"Financial statement data is unavailable for {ticker}")
        return result[0], [self._source(ticker, "Financial statements")]

    def news(self, query: str) -> tuple[list[dict[str, Any]], list[ToolSource]]:
        try:
            response = self._client.get(
                f"{self.base_url}/v1/finance/search", params={"q": query, "newsCount": 12}
            )
            response.raise_for_status()
            articles = response.json().get("news", [])
        except (httpx.HTTPError, ValueError) as error:
            raise ToolFailure("Yahoo Finance news search is unavailable") from error
        normalized: list[dict[str, Any]] = []
        seen_titles: set[str] = set()
        for article in articles:
            title = article.get("title", "Untitled article")
            url = article.get("link", "")
            if not url or title.casefold() in seen_titles:
                continue
            seen_titles.add(title.casefold())
            normalized.append(
                {
                    "title": title,
                    "url": url,
                    "publisher": article.get("publisher", self.publisher),
                    "published_at": article.get("providerPublishTime"),
                }
            )
        sources = [self._source(query, "News search")] + [
            ToolSource(title=item["title"], url=item["url"], publisher=item["publisher"])
            for item in normalized
        ]
        return normalized, sources

    def _quote_summary(self, ticker: str, modules: str) -> dict[str, Any]:
        try:
            response = self._client.get(
                f"{self.base_url}/v10/finance/quoteSummary/{ticker}", params={"modules": modules}
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload
        except (httpx.HTTPError, ValueError) as error:
            raise ToolFailure(f"Yahoo Finance data is unavailable for {ticker}") from error

    def _source(self, ticker: str, title: str) -> ToolSource:
        return ToolSource(
            title=title, url=f"https://finance.yahoo.com/quote/{ticker}", publisher=self.publisher
        )
