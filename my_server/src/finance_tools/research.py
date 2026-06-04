import asyncio
import os
from typing import Annotated

import arcadepy
import yfinance as yf

from finance_tools import app

_USER_ID = "gerardom1226@gmail.com"


def _arcade() -> arcadepy.Arcade:
    return arcadepy.Arcade(api_key=os.environ["ARCADE_API_KEY"])


def _scrape(client: arcadepy.Arcade, url: str) -> str:
    result = client.tools.execute(
        tool_name="Firecrawl.ScrapeUrl",
        input={"url": url, "formats": ["markdown"], "only_main_content": True},
        user_id=_USER_ID,
    )
    return (result.output.value or {}).get("markdown", "")


def _search(client: arcadepy.Arcade, query: str, n_results: int = 10) -> str:
    result = client.tools.execute(
        tool_name="GoogleSearch.Search",
        input={"query": query, "n_results": n_results},
        user_id=_USER_ID,
    )
    return result.output.value or ""


@app.tool
def get_stock_overview(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
    exchange: Annotated[str, "Exchange, e.g. 'NASDAQ', 'NYSE'"] = "NASDAQ",
) -> Annotated[str, "Current price and daily movement from Google Finance"]:
    """Get a stock's current price and daily performance from Google Finance."""
    client = _arcade()
    ticker_upper = ticker.upper()

    data = None
    for ex in [exchange, "NASDAQ", "NYSE", "NYSE ARCA"]:
        result = client.tools.execute(
            tool_name="GoogleFinance.GetStockSummary",
            input={"ticker_symbol": ticker_upper, "exchange_identifier": ex},
            user_id=_USER_ID,
        )
        if result.output and result.output.value:
            data = result.output.value
            break

    if not data:
        return f"No data found for {ticker_upper}."

    market = data.get("market", {})
    movement = market.get("price_movement", {})
    price = market.get("extracted_price", data.get("extracted_price", 0))
    direction = movement.get("movement", "")
    change_val = movement.get("value", 0)
    change_pct = movement.get("percentage", 0)

    return (
        f"## {data.get('title', ticker_upper)} ({ticker_upper})\n\n"
        f"**Price:** {data.get('currency', 'USD')} {price:.2f}\n"
        f"**Day Change:** {direction} {change_val:+.2f} ({change_pct:+.2f}%)\n"
        f"**Exchange:** {data.get('exchange', exchange)}\n"
        f"**As of:** {data.get('date', '')}"
    )


@app.tool
def get_analyst_sentiment(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
) -> Annotated[str, "Analyst recommendations and price targets from yfinance"]:
    """Get analyst sentiment for a stock including recommendation, price targets, and consensus score."""
    ticker_upper = ticker.upper()
    info = yf.Ticker(ticker_upper).info

    rec_key = info.get("recommendationKey", "none")
    rec_mean = info.get("recommendationMean")
    num_analysts = info.get("numberOfAnalystOpinions")

    if rec_key == "none" or not num_analysts:
        return f"No analyst coverage found for {ticker_upper}."

    if rec_mean:
        if rec_mean <= 1.5:
            label = "Strong Buy"
        elif rec_mean <= 2.5:
            label = "Buy"
        elif rec_mean <= 3.5:
            label = "Hold"
        elif rec_mean <= 4.5:
            label = "Underperform"
        else:
            label = "Sell"
    else:
        label = rec_key.replace("_", " ").title()

    return (
        f"## {ticker_upper} Analyst Sentiment\n\n"
        f"**Sentiment:** {label}\n"
        f"**Consensus Score:** {rec_mean:.2f} / 5.0\n"
        f"**Analysts:** {num_analysts}"
    )


@app.tool
def get_stock_news(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
) -> Annotated[str, "Recent news headlines for the stock from Finviz"]:
    """Scrape Finviz for aggregated news headlines about a stock."""
    ticker_upper = ticker.upper()
    content = _scrape(_arcade(), f"https://finviz.com/quote.ashx?t={ticker_upper}")
    if len(content) < 200:
        return f"No news found for {ticker_upper}."
    return f"## Finviz News: {ticker_upper}\n\n{content[:4000]}"



@app.tool
def search_web(
    query: Annotated[str, "Search query, e.g. 'AAPL earnings Q2 2026'"],
    n_results: Annotated[int, "Number of results to return"] = 10,
) -> Annotated[str, "Google search results"]:
    """Search the web via Google and return organic results."""
    results = _search(_arcade(), query, n_results)
    if not results:
        return f"No results found for '{query}'."
    return f"## Search: {query}\n\n{results}"


@app.tool
async def stock_deep_research(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
) -> Annotated[str, "Comprehensive research combining news, sentiment, and financials"]:
    """Research a stock across Finviz, Stocktwits, and Google Search in parallel."""
    client = _arcade()
    ticker_upper = ticker.upper()

    finviz_md, stocktwits_md, search_results = await asyncio.gather(
        asyncio.to_thread(_scrape, client, f"https://finviz.com/quote.ashx?t={ticker_upper}"),
        asyncio.to_thread(_scrape, client, f"https://stocktwits.com/symbol/{ticker_upper}"),
        asyncio.to_thread(_search, client, f"{ticker_upper} stock news analysis", 8),
    )

    sections = []

    if len(finviz_md) > 200:
        sections.append(f"## Finviz: {ticker_upper}\n\n{finviz_md[:3000]}")

    if len(stocktwits_md) > 200:
        sections.append(f"## Stocktwits: {ticker_upper}\n\n{stocktwits_md[:3000]}")

    if search_results:
        sections.append(f"## Web Search: {ticker_upper}\n\n{search_results}")

    if not sections:
        return f"No data found for {ticker_upper}."

    return "\n\n---\n\n".join(sections)


@app.tool
def find_trending_tickers() -> Annotated[str, "Most active and trending stocks right now"]:
    """Scrape Finviz and Yahoo Finance for the most active and trending tickers today."""
    client = _arcade()
    sections = []

    finviz_md = _scrape(client, "https://finviz.com/screener.ashx?v=111&s=ta_topgainers")
    if len(finviz_md) > 200:
        sections.append(f"## Finviz Top Gainers\n\n{finviz_md[:3000]}")

    yahoo_md = _scrape(client, "https://finance.yahoo.com/trending-tickers/")
    if len(yahoo_md) > 200:
        sections.append(f"## Yahoo Trending Tickers\n\n{yahoo_md[:3000]}")

    return "\n\n---\n\n".join(sections) if sections else "No trending data found."


@app.tool
def general_deep_research(
    topic: Annotated[str, "Market topic to research, e.g. 'AI semiconductors', 'Fed rates'"] = "stock market today",
) -> Annotated[str, "Broad market overview from Google Search and Finviz"]:
    """Get a broad picture of current market trends via Google Search and Finviz market overview."""
    client = _arcade()
    sections = []

    search_results = _search(client, topic, 10)
    if search_results:
        sections.append(f"## Web Search: {topic}\n\n{search_results}")

    market_md = _scrape(client, "https://finviz.com/map.ashx?t=sec")
    if len(market_md) > 200:
        sections.append(f"## Finviz Market Map\n\n{market_md[:3000]}")

    trending_md = _scrape(client, "https://finance.yahoo.com/trending-tickers/")
    if len(trending_md) > 200:
        sections.append(f"## Trending Tickers\n\n{trending_md[:2000]}")

    return "\n\n---\n\n".join(sections) if sections else "No market data found."
