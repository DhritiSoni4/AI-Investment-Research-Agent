from typing import Any

import httpx

from app.infrastructure.tools.models import ToolFailure, ToolSource


class SecEdgarTool:
    """Read filing metadata from SEC EDGAR; callers must supply an accountable User-Agent."""

    publisher = "U.S. Securities and Exchange Commission"

    def __init__(self, timeout_seconds: float, user_agent: str) -> None:
        self._client = httpx.Client(
            timeout=timeout_seconds,
            headers={"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"},
        )

    def close(self) -> None:
        self._client.close()

    def latest_filings(self, ticker: str) -> tuple[list[dict[str, Any]], list[ToolSource]]:
        try:
            ticker_response = self._client.get("https://www.sec.gov/files/company_tickers.json")
            ticker_response.raise_for_status()
            records = ticker_response.json().values()
            record = next((item for item in records if item.get("ticker", "").upper() == ticker.upper()), None)
            if record is None:
                raise ToolFailure(f"SEC EDGAR has no issuer mapping for {ticker}")
            cik = str(record["cik_str"]).zfill(10)
            response = self._client.get(f"https://data.sec.gov/submissions/CIK{cik}.json")
            response.raise_for_status()
            recent = response.json().get("filings", {}).get("recent", {})
        except (httpx.HTTPError, ValueError) as error:
            raise ToolFailure("SEC EDGAR filing search is unavailable") from error

        filings: list[dict[str, Any]] = []
        for form, accession, date, document in zip(
            recent.get("form", []), recent.get("accessionNumber", []), recent.get("filingDate", []), recent.get("primaryDocument", []), strict=False
        ):
            if form not in {"10-K", "10-Q"}:
                continue
            accession_compact = accession.replace("-", "")
            url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_compact}/{document}"
            filings.append({"form": form, "accession": accession, "filing_date": date, "url": url})
            if len(filings) == 4:
                break
        return filings, [ToolSource(title="SEC EDGAR filings", url=f"https://data.sec.gov/submissions/CIK{cik}.json", publisher=self.publisher)]
