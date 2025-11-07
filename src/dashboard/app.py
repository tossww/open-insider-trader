"""
Main Dash application for Open InsiderTrader dashboard.

Visualizes backtesting results with interactive charts and AI analysis.
"""

import sys
from pathlib import Path
from datetime import datetime
import sqlite3

import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from backtesting.backtest_engine import BacktestEngine, Signal
from backtesting.metrics import MetricsCalculator
import yaml


# Load config
with open('config.yaml', 'r') as f:
    CONFIG = yaml.safe_load(f)


def load_backtest_results(db_path: str = 'data/insider_trades.db'):
    """
    Load signals and run backtest.

    Returns:
        Tuple of (signals, results_dict, metrics_dict)
    """
    # Load signals from database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    query = """
    SELECT
        c.ticker,
        t.filing_date,
        t.trade_date,
        i.name as insider_name,
        i.officer_title,
        t.total_value,
        fs.composite_score,
        fs.cluster_size
    FROM filtered_signals fs
    JOIN insider_transactions t ON fs.transaction_id = t.id
    JOIN companies c ON t.company_id = c.id
    JOIN insiders i ON t.insider_id = i.id
    WHERE fs.composite_score >= ?
    ORDER BY fs.composite_score DESC
    LIMIT ?
    """

    min_score = CONFIG['scoring']['min_signal_score']
    limit = CONFIG['scoring']['top_n_signals']

    cursor = conn.execute(query, (min_score, limit))
    rows = cursor.fetchall()
    conn.close()

    signals = []
    for row in rows:
        signals.append(Signal(
            ticker=row['ticker'],
            filing_date=datetime.fromisoformat(row['filing_date']),
            trade_date=datetime.fromisoformat(row['trade_date']),
            insider_name=row['insider_name'],
            officer_title=row['officer_title'] or 'Unknown',
            total_value=row['total_value'],
            composite_score=row['composite_score'],
            cluster_size=row['cluster_size']
        ))

    if not signals:
        return [], {}, {}

    # Run backtest
    engine = BacktestEngine(
        commission_pct=CONFIG['backtesting']['commission_pct'],
        slippage_pct=CONFIG['backtesting']['slippage_pct']
    )

    holding_periods = CONFIG['backtesting']['holding_periods']
    results = engine.backtest_multiple_periods(signals, holding_periods)

    # Add benchmark comparison for each period
    print("\nCalculating S&P 500 benchmark comparison...")
    for period, result in results.items():
        if result.total_trades > 0:
            results[period] = engine.add_benchmark_comparison(
                result,
                CONFIG['backtesting']['benchmark_ticker']
            )

    # Calculate metrics for each period
    calculator = MetricsCalculator(risk_free_rate=CONFIG['backtesting']['risk_free_rate'])
    metrics = {}

    for period, result in results.items():
        if result.total_trades > 0:
            returns = [t.net_return for t in result.trades]
            metrics[period] = calculator.calculate_metrics(returns, period if period != -1 else 252)
        else:
            metrics[period] = None

    return signals, results, metrics


# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Open InsiderTrader - Backtest Results"
)

# Load data
signals, backtest_results, metrics_results = load_backtest_results()


# Layout components
def create_header():
    """Create dashboard header."""
    return dbc.Container([
        html.H1("🎯 Open InsiderTrader", className="text-center mt-4 mb-2"),
        html.H4("Insider Trading Signal Backtesting", className="text-center text-muted mb-4"),
        html.Hr()
    ], fluid=True)


def create_summary_cards():
    """Create performance summary cards."""
    if not backtest_results:
        return html.Div("No data available", className="text-center text-muted")

    # Use 21-day period as primary metric
    primary_period = 21
    result = backtest_results.get(primary_period)

    if not result or result.total_trades == 0:
        return html.Div("No results for 21-day period", className="text-center text-muted")

    metric = metrics_results.get(primary_period)

    # Alpha card color logic
    alpha_value = result.alpha if result.alpha is not None else 0
    alpha_color = "text-success" if alpha_value > 0 else "text-danger" if alpha_value < 0 else "text-warning"

    cards = dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total Signals", className="text-muted"),
                    html.H3(f"{result.total_trades}", className="text-info")
                ])
            ], className="mb-3")
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Avg Return (21d)", className="text-muted"),
                    html.H3(f"{result.avg_net_return:.2%}", className="text-success" if result.avg_net_return > 0 else "text-danger")
                ])
            ], className="mb-3")
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("S&P 500 (21d)", className="text-muted"),
                    html.H3(
                        f"{result.avg_spy_return:.2%}" if result.avg_spy_return is not None else "N/A",
                        className="text-info"
                    )
                ])
            ], className="mb-3")
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("🎯 Alpha (21d)", className="text-muted"),
                    html.H3(
                        f"{result.alpha:.2%}" if result.alpha is not None else "N/A",
                        className=alpha_color
                    )
                ])
            ], className="mb-3")
        ], width=3),
    ])

    return cards


def create_performance_table():
    """Create performance table by holding period."""
    if not backtest_results:
        return html.Div("No data available")

    data = []
    for period in sorted(backtest_results.keys(), key=lambda x: x if x != -1 else 999999):
        result = backtest_results[period]
        metric = metrics_results.get(period)

        if result.total_trades == 0:
            continue

        period_label = f"{period}d" if period != -1 else "max"

        data.append({
            'Period': period_label,
            'Trades': result.total_trades,
            'Strategy': f"{result.avg_net_return:.2%}",
            'S&P 500': f"{result.avg_spy_return:.2%}" if result.avg_spy_return is not None else "N/A",
            'Alpha': f"{result.alpha:.2%}" if result.alpha is not None else "N/A",
            'Win %': f"{result.win_rate:.1%}",
            'Total Return': f"{result.total_net_return:.2%}",
            'Sharpe': f"{metric.sharpe_ratio:.2f}" if metric and metric.sharpe_ratio < 1000 else "N/A",
            'Max DD': f"{metric.max_drawdown:.2%}" if metric else "N/A"
        })

    df = pd.DataFrame(data)

    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=[{'name': col, 'id': col} for col in df.columns],
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'backgroundColor': '#303030',
            'color': 'white'
        },
        style_header={
            'backgroundColor': '#1e1e1e',
            'fontWeight': 'bold',
            'color': 'white'
        },
        style_data_conditional=[
            {
                'if': {'column_id': 'Strategy'},
                'color': '#00ff00',
                'fontWeight': 'bold'
            },
            {
                'if': {'column_id': 'Alpha'},
                'color': '#00ff00',
                'fontWeight': 'bold'
            }
        ]
    )

    return dbc.Container([
        html.H4("📊 Performance by Holding Period", className="mt-4 mb-3"),
        table
    ], fluid=True)


def create_trades_table():
    """Create individual trades table."""
    if not backtest_results:
        return html.Div("No data available")

    # Use 21-day period
    result = backtest_results.get(21)
    if not result or not result.trades:
        return html.Div("No trades available")

    data = []
    for trade in sorted(result.trades, key=lambda t: t.net_return, reverse=True):
        data.append({
            'Ticker': trade.ticker,
            'Entry Date': trade.entry_date.strftime('%Y-%m-%d'),
            'Exit Date': trade.exit_date.strftime('%Y-%m-%d'),
            'Days Held': trade.holding_days,
            'Entry Price': f"${trade.entry_price:.2f}",
            'Exit Price': f"${trade.exit_price:.2f}",
            'Net Return': f"{trade.net_return:.2%}",
            'Signal Score': f"{trade.signal_score:.2f}"
        })

    df = pd.DataFrame(data)

    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=[{'name': col, 'id': col} for col in df.columns],
        page_size=20,
        sort_action='native',
        filter_action='native',
        style_table={'overflowX': 'auto'},
        style_cell={
            'textAlign': 'left',
            'padding': '10px',
            'backgroundColor': '#303030',
            'color': 'white',
            'minWidth': '100px'
        },
        style_header={
            'backgroundColor': '#1e1e1e',
            'fontWeight': 'bold',
            'color': 'white'
        },
        style_data_conditional=[
            {
                'if': {
                    'filter_query': '{Net Return} contains "-"',
                    'column_id': 'Net Return'
                },
                'color': '#ff4444'
            },
            {
                'if': {
                    'filter_query': '{Net Return} not contains "-"',
                    'column_id': 'Net Return'
                },
                'color': '#00ff00'
            }
        ]
    )

    return dbc.Container([
        html.H4("📋 Individual Trades (21-day holding period)", className="mt-4 mb-3"),
        table
    ], fluid=True)


# App layout
app.layout = html.Div([
    create_header(),
    dbc.Container([
        create_summary_cards(),
        create_performance_table(),
        html.Hr(className="my-4"),
        create_trades_table()
    ], fluid=True, className="px-4")
])


def run_dashboard(host='127.0.0.1', port=8050, debug=True):
    """Run the Dash app."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_dashboard()
