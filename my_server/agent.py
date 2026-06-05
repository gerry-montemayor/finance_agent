import asyncio
import inspect
import os
import sys
import warnings

warnings.filterwarnings("ignore", category=FutureWarning, module="yfinance")
warnings.filterwarnings("ignore", ".*utcnow.*")

import anthropic
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from finance_tools.portfolio import (
    add_holding,
    read_holdings,
    read_transactions,
    refresh_portfolio,
    remove_holding,
)
from finance_tools.research import (
    find_trending_tickers,
    get_news,
    get_sentiment,
    get_stock_news,
    get_stock_overview,
)

SYSTEM_PROMPT = """You are a financial research and portfolio assistant. You help users research stocks, follow market news, and manage their portfolio.

Use tools to gather real data before answering. Be concise and actionable."""

TOOLS = [
    {
        "name": "get_stock_overview",
        "description": "Get a stock's current price and daily performance from Google Finance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. 'AAPL'"},
                "exchange": {"type": "string", "description": "Exchange: 'NASDAQ', 'NYSE', 'NYSE ARCA'"},
            },
            "required": ["ticker", "exchange"],
        },
    },
    {
        "name": "get_sentiment",
        "description": "Get analyst sentiment for a stock: consensus rating, score, and number of analysts.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. 'AAPL'"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_news",
        "description": "Search Google News and scrape MarketWatch for headlines on a given topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "News topic, e.g. 'stock market', 'Fed rate decision', 'NVDA earnings'"},
            },
            "required": [],
        },
    },
    {
        "name": "get_stock_news",
        "description": "Get recent news headlines for a specific stock from Finviz.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. 'AAPL'"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "find_trending_tickers",
        "description": "Find the most active and trending stocks right now from Yahoo Finance.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_holdings",
        "description": "Read current portfolio holdings from Google Sheets.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "add_holding",
        "description": "Add a stock to the portfolio. Logs the transaction and updates the sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol, e.g. 'AAPL'"},
                "shares": {"type": "number", "description": "Number of shares purchased"},
                "buy_price": {"type": "number", "description": "Price per share paid. Defaults to current market price."},
            },
            "required": ["ticker", "shares"],
        },
    },
    {
        "name": "refresh_portfolio",
        "description": "Refresh live prices and recalculate gain/loss for all holdings.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "remove_holding",
        "description": "Remove a stock from the portfolio and log it as a Sell.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol to remove"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "read_transactions",
        "description": "Read the full buy/sell transaction history from Google Sheets.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

_TOOL_FN = {
    "get_stock_overview": get_stock_overview,
    "get_sentiment": get_sentiment,
    "get_news": get_news,
    "get_stock_news": get_stock_news,
    "find_trending_tickers": find_trending_tickers,
    "read_holdings": read_holdings,
    "add_holding": add_holding,
    "refresh_portfolio": refresh_portfolio,
    "remove_holding": remove_holding,
    "read_transactions": read_transactions,
}


def _call_tool(name: str, inputs: dict) -> str:
    fn = _TOOL_FN[name]
    if inspect.iscoroutinefunction(fn):
        return asyncio.run(fn(**inputs))
    return fn(**inputs)


def main():
    console = Console()
    client = anthropic.Anthropic()
    messages = []

    console.print(Panel("Finance Agent", subtitle="ask about stocks or your portfolio • 'quit' to exit", style="bold green"))

    while True:
        try:
            user_input = Prompt.ask("\n[bold cyan]You[/bold cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            console.print("[dim]Goodbye![/dim]")
            break

        messages.append({"role": "user", "content": user_input})

        while True:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if hasattr(block, "text"):
                        console.print("\n[bold green]Agent[/bold green]")
                        console.print(Markdown(block.text))
                break

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        args = ", ".join(f"{k}={v!r}" for k, v in block.input.items())
                        console.print(Text(f"  → {block.name}({args})", style="dim yellow"))
                        try:
                            result = _call_tool(block.name, block.input)
                        except Exception as e:
                            result = f"Error: {e}"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    main()
