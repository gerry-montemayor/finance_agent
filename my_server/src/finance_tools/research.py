import asyncio
import os
from typing import Annotated

import arcadepy
import yfinance as yf

from finance_tools import app

_USER_ID = os.environ["ARCADE_USER_ID"]


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


def _news_search(client: arcadepy.Arcade, query: str, n_results: int = 10) -> str:
    result = client.tools.execute(
        tool_name="GoogleNews.SearchNews",
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

    result = client.tools.execute(
        tool_name="GoogleFinance.GetStockSummary",
        input={"ticker_symbol": ticker_upper, "exchange_identifier": exchange},
        user_id=_USER_ID,
    )
    data = result.output and result.output.value
    if not data:
        return f"No data found for {ticker_upper} on {exchange}."

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
def get_sentiment(
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
async def get_news(
    topic: Annotated[str, "News topic to search, e.g. 'stock market', 'Fed rate decision', 'inflation'"] = "stock market news today",
) -> Annotated[str, "Recent news from MarketWatch and Google News for the given topic"]:
    """Search Google News and scrape MarketWatch for headlines on a given topic."""
    client = _arcade()

    marketwatch_md, google_results = await asyncio.gather(
        asyncio.to_thread(_scrape, client, "https://www.marketwatch.com/investing"),
        asyncio.to_thread(_news_search, client, topic, 10),
    )

    sections = []
    if len(marketwatch_md) > 200:
        sections.append(f"## MarketWatch\n\n{marketwatch_md[:3000]}")
    if google_results:
        sections.append(f"## Google News: {topic}\n\n{google_results}")

    return "\n\n---\n\n".join(sections) if sections else "No news found."


@app.tool
def get_stock_news(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
) -> Annotated[str, "Recent news headlines for the stock from Finviz"]:
    """Scrape Finviz for aggregated news headlines about a stock."""
    ticker_upper = ticker.upper()
    content = _scrape(_arcade(), f"https://finviz.com/search?p={ticker_upper}")
    if len(content) < 200:
        return f"No news found for {ticker_upper}."
    return f"## Finviz News: {ticker_upper}\n\n{content}"


@app.tool
def find_trending_tickers() -> Annotated[str, "Most active and trending stocks right now"]:
    """Scrape Yahoo Finance for the most active and trending tickers today."""
    content = _scrape(_arcade(), "https://finance.yahoo.com/trending-tickers/")
    if len(content) < 200:
        return "No trending data found."
    return f"## Yahoo Trending Tickers\n\n{content}"
