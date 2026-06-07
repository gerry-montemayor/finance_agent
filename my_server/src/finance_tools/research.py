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


@app.tool
def get_stock_overview(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
    exchange: Annotated[str, "Exchange, e.g. 'NASDAQ', 'NYSE'"] = "NASDAQ",
) -> Annotated[str, "Current price, daily movement, and recent news headlines for a stock"]:
    """Get a stock's current price, daily performance from Google Finance, and recent news headlines from Yahoo Finance."""
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

    overview = (
        f"## {data.get('title', ticker_upper)} ({ticker_upper})\n\n"
        f"**Price:** {data.get('currency', 'USD')} {price:.2f}\n"
        f"**Day Change:** {direction} {change_val:+.2f} ({change_pct:+.2f}%)\n"
        f"**Exchange:** {data.get('exchange', exchange)}\n"
        f"**As of:** {data.get('date', '')}"
    )

    news_lines = []
    for item in yf.Ticker(ticker_upper).news[:5]:
        c = item.get("content", {})
        title = c.get("title", "")
        provider = c.get("provider", {}).get("displayName", "")
        pub_date = c.get("pubDate", "")
        if title:
            news_lines.append(f"- **{title}** — *{provider}, {pub_date}*")

    news_section = "\n\n### Recent News\n" + "\n".join(news_lines) if news_lines else ""
    return overview + news_section



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
def get_news(
    topic: Annotated[str, "News topic to search, e.g. 'stock market', 'Fed rate decision', 'inflation'"] = "stock market news today",
) -> Annotated[str, "Recent news from MarketWatch and Google News for the given topic"]:
    """Search Google News and scrape MarketWatch investing page for headlines on a given topic."""
    client = _arcade()

    google_result = client.tools.execute(
        tool_name="GoogleNews.SearchNewsStories",
        input={"keywords": topic, "limit": 10},
        user_id=_USER_ID,
    )
    marketwatch_md = _scrape(_arcade(), "https://www.marketwatch.com/investing")

    articles = (google_result.output.value or {}).get("news_results", [])
    lines = [f"## Google News: {topic}\n"]
    for a in articles:
        title = a.get("title", "")
        link = a.get("link", "")
        source = a.get("source", "")
        date = a.get("date", "")
        headline = f"[{title}]({link})" if link else title
        meta = " — ".join(filter(None, [source, date]))
        lines.append(f"- {headline}" + (f" *({meta})*" if meta else ""))

    if len(marketwatch_md) > 200:
        lines.append(f"\n## MarketWatch\n\n{marketwatch_md[:3000]}")

    return "\n".join(lines) if lines else "No news found."


@app.tool
def get_stock_news(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
    max_items: Annotated[int, "Maximum number of news items to return"] = 10,
) -> Annotated[str, "Recent news headlines and summaries for the stock from Yahoo Finance"]:
    """Get recent news headlines and summaries for a stock directly from Yahoo Finance via yfinance."""
    ticker_upper = ticker.upper()
    news = yf.Ticker(ticker_upper).news

    if not news:
        return f"No news found for {ticker_upper}."

    lines = [f"## {ticker_upper} News\n"]
    for item in news[:max_items]:
        c = item.get("content", {})
        title = c.get("title", "")
        summary = c.get("summary", "")
        pub_date = c.get("pubDate", "")
        provider = c.get("provider", {}).get("displayName", "")
        url = (c.get("canonicalUrl") or {}).get("url", "")

        lines.append(f"### {title}")
        if provider or pub_date:
            lines.append(f"*{provider} — {pub_date}*")
        if summary:
            lines.append(f"{summary}")
        if url:
            lines.append(f"[Read more]({url})")
        lines.append("")

    return "\n".join(lines)


@app.tool
async def get_stock_profile(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
) -> Annotated[str, "Combined fundamentals, technicals, and key metrics from yfinance and Finviz"]:
    """Get a comprehensive stock profile combining yfinance fundamentals with Finviz technicals and performance data."""
    ticker_upper = ticker.upper()
    client = _arcade()

    yf_ticker = yf.Ticker(ticker_upper)
    info, finviz_md = await asyncio.gather(
        asyncio.to_thread(lambda: yf_ticker.info),
        asyncio.to_thread(_scrape, client, f"https://finviz.com/quote.ashx?t={ticker_upper}"),
    )

    # yfinance section
    name = info.get("longName", ticker_upper)
    sector = info.get("sector", "")
    industry = info.get("industry", "")
    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    mkt_cap = info.get("marketCap", 0)
    mkt_cap_str = f"${mkt_cap/1e12:.2f}T" if mkt_cap >= 1e12 else f"${mkt_cap/1e9:.1f}B"

    earnings_dates = []
    try:
        cal = await asyncio.to_thread(lambda: yf_ticker.calendar)
        earnings_dates = cal.get("Earnings Date", [])
    except Exception:
        pass
    next_earnings = earnings_dates[0].strftime("%Y-%m-%d") if earnings_dates else "N/A"

    eps_fwd = info.get("forwardEps")
    eps_trail = info.get("trailingEps")
    rev_growth = info.get("revenueGrowth")
    earn_growth = info.get("earningsGrowth")
    target_mean = info.get("targetMeanPrice")
    target_high = info.get("targetHighPrice")
    target_low = info.get("targetLowPrice")
    rec_key = info.get("recommendationKey", "N/A").replace("_", " ").title()
    num_analysts = info.get("numberOfAnalystOpinions", "N/A")
    free_cf = info.get("freeCashflow", 0)
    free_cf_str = f"${free_cf/1e9:.1f}B" if free_cf else "N/A"

    yf_section = f"""## {name} ({ticker_upper})
    **Sector:** {sector} | **Industry:** {industry}
    **Price:** ${price:.2f} | **Market Cap:** {mkt_cap_str}

    ### Valuation
    | Metric | Value |
    |---|---|
    | Trailing P/E | {info.get('trailingPE', 'N/A')} |
    | Forward P/E | {info.get('forwardPE', 'N/A')} |
    | PEG Ratio | {info.get('pegRatio', 'N/A')} |
    | Price/Book | {info.get('priceToBook', 'N/A')} |
    | EV/EBITDA | {info.get('enterpriseToEbitda', 'N/A')} |

    ### Earnings & Growth
    | Metric | Value |
    |---|---|
    | EPS (TTM) | {eps_trail} |
    | EPS (Forward) | {eps_fwd} |
    | Revenue Growth (YoY) | {f'{rev_growth:.1%}' if rev_growth else 'N/A'} |
    | Earnings Growth (YoY) | {f'{earn_growth:.1%}' if earn_growth else 'N/A'} |
    | Free Cash Flow | {free_cf_str} |
    | Next Earnings Date | {next_earnings} |

    ### Analyst Targets ({num_analysts} analysts)
    | | Price |
    |---|---|
    | Mean Target | ${target_mean} |
    | High Target | ${target_high} |
    | Low Target | ${target_low} |
    | Recommendation | {rec_key} |"""

    # finviz section
    finviz_section = ""
    if len(finviz_md) > 200:
        finviz_section = f"\n\n---\n\n## Finviz: Technicals & Performance\n\n{finviz_md}"

    return yf_section + finviz_section


@app.tool
def find_trending_tickers() -> Annotated[str, "Most active and trending stocks right now"]:
    """Scrape Yahoo Finance for the most active and trending tickers today."""
    content = _scrape(_arcade(), "https://finance.yahoo.com/trending-tickers/")
    if len(content) < 200:
        return "No trending data found."
    return f"## Yahoo Trending Tickers\n\n{content}"
