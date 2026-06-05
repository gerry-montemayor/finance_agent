import json
import os
from datetime import datetime
from typing import Annotated

import arcadepy
import yfinance as yf

from finance_tools import app

_USER_ID = os.environ["ARCADE_USER_ID"]
_client = arcadepy.Arcade(api_key=os.environ["ARCADE_API_KEY"])

_HOLDINGS_HEADERS = {
    "A": "Ticker", "B": "Name", "C": "Shares", "D": "Avg Cost",
    "E": "Current Price", "F": "Market Value", "G": "Total Cost",
    "H": "Gain/Loss $", "I": "Gain/Loss %", "J": "Last Updated",
}
_TRANSACTIONS_HEADERS = {
    "A": "Date", "B": "Ticker", "C": "Action",
    "D": "Shares", "E": "Price", "F": "Total",
}


def _sheet_id() -> str:
    return os.environ["GOOGLE_SHEETS_ID"]


def _get_sheet_data(tab: str) -> dict:
    result = _client.tools.execute(
        tool_name="GoogleSheets.GetSpreadsheet",
        input={"spreadsheet_id": _sheet_id(), "sheet_id_or_name": tab},
        user_id=_USER_ID,
    )
    sheets = (result.output.value or {}).get("sheets", [])
    return sheets[0].get("data", {}) if sheets else {}


def _get_next_row(data: dict) -> int:
    if not data:
        return 2
    return max(int(k) for k in data.keys()) + 1


def _cell_value(row_data: dict, col: str) -> str:
    return str(row_data.get(col, {}).get("formattedValue", ""))


def _cell_num(row_data: dict, col: str) -> float:
    cell = row_data.get(col, {})
    val = cell.get("effectiveValue") or cell.get("userEnteredValue", 0)
    try:
        return float(val or 0)
    except (ValueError, TypeError):
        return 0.0


def _write_rows(tab: str, data: dict) -> None:
    _client.tools.execute(
        tool_name="GoogleSheets.UpdateCells",
        input={"spreadsheet_id": _sheet_id(), "sheet_id_or_name": tab, "data": json.dumps(data)},
        user_id=_USER_ID,
    )


def _write_cell(col: str, row: int, value: str) -> None:
    _client.tools.execute(
        tool_name="GoogleSheets.WriteToCell",
        input={"spreadsheet_id": _sheet_id(), "column": col, "row": row, "value": value, "sheet_name": "Holdings"},
        user_id=_USER_ID,
    )


def _write_summary_stats(data: dict) -> None:
    header_row = min(data.keys(), key=int) if data else "1"
    total_invested, total_value, performances = 0.0, 0.0, {}

    for k, row in data.items():
        if k == header_row:
            continue
        ticker = _cell_value(row, "A").upper()
        if not ticker:
            continue
        shares = _cell_num(row, "C")
        avg_cost = _cell_num(row, "D")
        market_value = _cell_num(row, "F")
        gain_loss_pct = _cell_num(row, "I")
        if not shares:
            continue
        total_invested += round(shares * avg_cost, 2)
        total_value += market_value
        performances[ticker] = gain_loss_pct

    if not performances:
        return

    best = max(performances, key=lambda t: performances[t])
    worst = min(performances, key=lambda t: performances[t])

    for row_num, value in [
        (2, str(round(total_invested, 2))),
        (3, str(round(total_value, 2))),
        (4, str(round(total_value - total_invested, 2))),
        (5, f"{best} ({performances[best]:+.2f}%)"),
        (6, f"{worst} ({performances[worst]:+.2f}%)"),
        (7, str(len(performances))),
    ]:
        _write_cell("M", row_num, value)


def _fetch_price(ticker: str) -> dict:
    info = yf.Ticker(ticker).info
    price = info.get("currentPrice") or info.get("regularMarketPrice", 0.0)
    return {
        "name": info.get("longName", ticker),
        "price": round(float(price), 2),
        "change": round(float(info.get("regularMarketChange", 0.0)), 2),
        "change_pct": round(float(info.get("regularMarketChangePercent", 0.0)), 4),
        "currency": info.get("currency", "USD"),
    }


def _format_table(data: dict) -> str:
    if not data:
        return "No data found."
    cols = sorted({col for row in data.values() for col in row.keys()})
    lines = []
    for row_num in sorted(data.keys(), key=int):
        row = data[row_num]
        lines.append(" | ".join(_cell_value(row, col) for col in cols))
        if row_num == min(data.keys(), key=int):
            lines.append(" | ".join("---" for _ in cols))
    return "\n".join(lines)


@app.tool
def read_holdings() -> Annotated[str, "Current portfolio holdings as a Markdown table"]:
    """Read all current holdings from the portfolio Google Sheet."""
    return _format_table(_get_sheet_data("Holdings"))


@app.tool
def add_holding(
    ticker: Annotated[str, "Stock ticker symbol, e.g. 'AAPL'"],
    shares: Annotated[float, "Number of shares purchased"],
    buy_price: Annotated[float, "Price per share you paid. Defaults to current market price."] = 0.0,
) -> Annotated[str, "Confirmation that the holding was added"]:
    """Add a stock to the portfolio. Fetches current price via yfinance and logs the transaction."""
    ticker_upper = ticker.upper()

    stock = _fetch_price(ticker_upper)
    if not stock["price"]:
        return f"Could not find price data for {ticker_upper}."

    current_price = stock["price"]
    avg_cost = buy_price if buy_price > 0 else current_price
    total_cost = round(shares * avg_cost, 2)
    market_value = round(shares * current_price, 2)
    gain_loss = round(market_value - total_cost, 2)
    gain_loss_pct = round((gain_loss / total_cost) if total_cost else 0, 4)

    holdings_data = _get_sheet_data("Holdings")
    header_row = min(holdings_data.keys(), key=int) if holdings_data else "1"
    occupied = {k for k, row in holdings_data.items() if k != header_row and _cell_value(row, "A")}
    next_row = max((int(k) for k in occupied), default=1) + 1

    _write_rows("Holdings", {
        str(next_row): {
            "A": ticker_upper, "B": stock["name"], "C": shares, "D": avg_cost,
            "E": current_price, "F": market_value, "G": total_cost,
            "H": gain_loss, "I": gain_loss_pct,
            "J": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
    })

    tx_data = _get_sheet_data("Transactions")
    _write_rows("Transactions", {
        str(_get_next_row(tx_data)): {
            "A": datetime.now().strftime("%Y-%m-%d"), "B": ticker_upper,
            "C": "Buy", "D": shares, "E": avg_cost, "F": total_cost,
        }
    })

    refresh_portfolio()
    return (
        f"Added {ticker_upper} ({stock['name']}) — "
        f"{shares} shares @ ${avg_cost:.2f} (current: ${current_price:.2f}). "
        f"G/L: ${gain_loss:+.2f} ({gain_loss_pct:+.2f}%)"
    )


@app.tool
def refresh_portfolio() -> Annotated[str, "Updated prices and gain/loss for all holdings"]:
    """Refresh the entire portfolio, fetches live prices for all holdings, recalculates market value and gain/loss, and updates summary stats."""
    data = _get_sheet_data("Holdings")
    if not data:
        return "No holdings to refresh."

    updates = {}
    summary = []
    header_row = min(data.keys(), key=int)

    for row_num, row in data.items():
        if row_num == header_row:
            continue
        ticker = _cell_value(row, "A").upper()
        if not ticker:
            continue
        shares = _cell_num(row, "C")
        avg_cost = _cell_num(row, "D")
        if not shares:
            continue

        stock = _fetch_price(ticker)
        price = stock["price"]
        market_value = round(shares * price, 3)
        total_cost = round(shares * avg_cost, 3)
        gain_loss = round(market_value - total_cost, 3)
        gain_loss_pct = round((gain_loss / total_cost) if total_cost else 0, 4)

        updates[row_num] = {
            "E": price, "F": market_value, "G": total_cost,
            "H": gain_loss, "I": gain_loss_pct,
            "J": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        summary.append(
            f"**{ticker}** ${price:.2f}  MV: ${market_value:.2f}  G/L: ${gain_loss:+.2f} ({gain_loss_pct:+.2f}%)"
        )

    if updates:
        _write_rows("Holdings", updates)

    _write_summary_stats(_get_sheet_data("Holdings"))
    return "## Price Refresh\n\n" + "\n".join(summary)


@app.tool
def remove_holding(
    ticker: Annotated[str, "Stock ticker symbol to remove, e.g. 'AAPL'"],
) -> Annotated[str, "Confirmation that the holding was removed"]:
    """Remove a stock from the portfolio and log it as a Sell in Transactions."""
    ticker_upper = ticker.upper()
    data = _get_sheet_data("Holdings")
    row_num, row_data = None, None

    for k, row in data.items():
        if _cell_value(row, "A").upper() == ticker_upper:
            row_num, row_data = k, row
            break

    if row_num is None:
        return f"{ticker_upper} not found in holdings."

    removed_int = int(row_num)
    rows_below = sorted(
        [(k, row) for k, row in data.items() if int(k) > removed_int and _cell_value(row, "A")],
        key=lambda x: int(x[0]),
    )

    if rows_below:
        shift_updates = {
            str(int(k) - 1): {col: row.get(col, {}).get("userEnteredValue", "") for col in "ABCDEFGHIJ"}
            for k, row in rows_below
        }
        _write_rows("Holdings", shift_updates)
        _write_rows("Holdings", {str(max(int(k) for k, _ in rows_below)): {col: "" for col in "ABCDEFGHIJ"}})
    else:
        _write_rows("Holdings", {row_num: {col: "" for col in "ABCDEFGHIJ"}})

    stock = _fetch_price(ticker_upper)
    shares = _cell_num(row_data, "C")
    price = stock["price"]

    tx_data = _get_sheet_data("Transactions")
    _write_rows("Transactions", {
        str(_get_next_row(tx_data)): {
            "A": datetime.now().strftime("%Y-%m-%d"), "B": ticker_upper,
            "C": "Sell", "D": shares, "E": price, "F": round(shares * price, 2),
        }
    })

    _write_summary_stats({k: v for k, v in data.items() if k != row_num})
    return f"Removed {ticker_upper} from holdings and logged Sell @ ${price:.2f}."


@app.tool
def read_transactions() -> Annotated[str, "Full transaction history as a Markdown table"]:
    """Read the full buy/sell transaction history from the portfolio Google Sheet."""
    return _format_table(_get_sheet_data("Transactions"))
