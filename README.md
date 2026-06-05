<p align="center">
   <img src="agent_architecture.png" width="450" />
</p>

# Finance Agent

A financial research and portfolio management agent built with the [Arcade](https://arcade.dev) tool platform and Claude. Exposes tools as an MCP server (for Claude Desktop or other MCP clients) and includes a standalone terminal agent you can chat with directly.

## What it does

- **Market research** — real-time stock prices via Google Finance, analyst sentiment, trending tickers, and market/stock news via Google News and MarketWatch
- **Portfolio management** — track holdings and transactions in a Google Sheet; add, remove, and refresh positions
- **Terminal agent** — chat with Claude in your terminal; it decides which tools to call and returns a synthesized answer

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- An [Arcade](https://arcade.dev) account and API key
- An [Anthropic](https://console.anthropic.com) API key (for the terminal agent)
- A Google Sheet (see [Google Sheet Setup](#google-sheet-setup) below)

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd finance_agent/my_server
uv sync
```

### 2. Configure environment variables

Copy the example env file and fill in your keys:

```bash
cp .env.example .env
```

Open `.env` and set:

```
ARCADE_API_KEY=        # from arcade.dev dashboard
ARCADE_USER_ID=        # your email address registered with Arcade
ANTHROPIC_API_KEY=     # from console.anthropic.com
GOOGLE_SHEETS_ID=      # the ID from your Google Sheet URL
```

### 3. Set up the Google Sheet

Click the link below to copy the portfolio template to your Google Drive:

**[Use Portfolio Template](https://docs.google.com/spreadsheets/d/1DV8sJpltHBYdjTt6tywi24SU0p0_3tzteA3FY4C6n5c/template/preview)**

Once you have your copy, grab the sheet ID from the URL:

```
https://docs.google.com/spreadsheets/d/THIS_IS_YOUR_SHEET_ID/edit
```

Paste that ID as `GOOGLE_SHEETS_ID` in your `.env`.

### 4. Authorize Google Sheets

The first time a portfolio tool runs, Arcade will prompt you to authorize access to your Google account. Follow the link it prints in the terminal to complete the OAuth flow.

## Running the terminal agent

```bash
cd my_server
uv run python agent.py
```

You can then ask things like:
- *"What's the price of NVDA?"*
- *"What's the market doing today?"*
- *"Add 10 shares of AAPL to my portfolio"*
- *"Show me my holdings and refresh prices"*

## Running as an MCP server

To use the tools inside Claude Desktop or another MCP client, run the server over stdio:

```bash
cd my_server
uv run python -m finance_tools.server
```

Or configure it in your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "finance-tools": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/finance_agent/my_server", "python", "-m", "finance_tools.server"],
      "env": {
        "ARCADE_API_KEY": "...",
        "ARCADE_USER_ID": "...",
        "GOOGLE_SHEETS_ID": "..."
      }
    }
  }
}
```

## Available tools

| Tool | Description |
|---|---|
| `get_stock_overview` | Live price and daily change from Google Finance |
| `get_sentiment` | Analyst consensus rating and score from yfinance |
| `get_news` | Headlines from Google News and MarketWatch for any topic |
| `get_stock_news` | Recent news for a specific ticker from Finviz |
| `find_trending_tickers` | Most active stocks right now from Yahoo Finance |
| `read_holdings` | Current portfolio positions from Google Sheets |
| `add_holding` | Add a position and log the transaction |
| `remove_holding` | Remove a position and log the sale |
| `refresh_portfolio` | Refresh live prices and recalculate gain/loss for all holdings |
| `read_transactions` | Full buy/sell transaction history |

## Project structure

```
my_server/
  agent.py                  # terminal agent loop
  src/finance_tools/
    __init__.py             # MCPApp instance
    server.py               # MCP server entrypoint
    research.py             # market research tools
    portfolio.py            # portfolio management tools
```
