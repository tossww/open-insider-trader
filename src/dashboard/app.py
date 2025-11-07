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
from ai.analyzer import BacktestAnalyzer
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

# Initialize AI analyzer
try:
    ai_analyzer = BacktestAnalyzer()
except ValueError as e:
    print(f"Warning: AI analyzer not available - {e}")
    ai_analyzer = None


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


def get_plotly_layout_template():
    """
    Get reusable Plotly dark theme layout settings.

    Returns:
        Dict with layout configuration
    """
    return {
        'plot_bgcolor': '#1e1e1e',
        'paper_bgcolor': '#1e1e1e',
        'font': {'color': 'white'},
        'xaxis': {'gridcolor': '#404040'},
        'yaxis': {'gridcolor': '#404040'},
        'legend': {'bgcolor': '#1e1e1e', 'bordercolor': '#404040'}
    }


def create_returns_histogram(result, period_days=21):
    """
    Create returns distribution histogram for specified period.

    Args:
        result: BacktestResult object
        period_days: Holding period in days

    Returns:
        Plotly figure
    """
    if not result or not result.trades:
        return go.Figure()

    # Extract net returns
    returns = [t.net_return * 100 for t in result.trades]  # Convert to percentage

    # Create histogram
    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=returns,
        nbinsx=30,
        name='Returns',
        marker_color='#00ff00',
        opacity=0.7
    ))

    # Add vertical line at 0% (break-even)
    fig.add_vline(
        x=0,
        line_dash="dash",
        line_color="white",
        annotation_text="Break-even",
        annotation_position="top"
    )

    # Apply dark theme
    layout = get_plotly_layout_template()
    layout.update({
        'title': f"Returns Distribution ({period_days}d holding period)",
        'xaxis_title': "Net Return (%)",
        'yaxis_title': "Number of Trades",
        'showlegend': False
    })
    fig.update_layout(**layout)

    return fig


def create_equity_curve_chart(result, period_days=21):
    """
    Create equity curve chart comparing strategy vs SPY.

    Args:
        result: BacktestResult object
        period_days: Holding period in days

    Returns:
        Plotly figure
    """
    if not result or not result.trades:
        return go.Figure()

    # Sort trades by entry date
    sorted_trades = sorted(result.trades, key=lambda t: t.entry_date)

    # Calculate cumulative returns for strategy
    strategy_dates = []
    strategy_cumulative = [0]  # Start at 0%

    cumulative_return = 0
    for trade in sorted_trades:
        strategy_dates.append(trade.entry_date)
        strategy_dates.append(trade.exit_date)

        # Entry point (no change in cumulative)
        strategy_cumulative.append(cumulative_return)

        # Exit point (add this trade's return)
        cumulative_return += trade.net_return
        strategy_cumulative.append(cumulative_return)

    # Calculate cumulative returns for SPY (benchmark)
    # Use average SPY return from result for each trade
    spy_dates = []
    spy_cumulative = [0]

    cumulative_spy = 0
    avg_spy = result.avg_spy_return if result.avg_spy_return is not None else 0

    for trade in sorted_trades:
        spy_dates.append(trade.entry_date)
        spy_dates.append(trade.exit_date)

        # Entry point
        spy_cumulative.append(cumulative_spy)

        # Exit point - use average SPY return as approximation
        cumulative_spy += avg_spy
        spy_cumulative.append(cumulative_spy)

    # Convert to percentage
    strategy_cumulative_pct = [r * 100 for r in strategy_cumulative]
    spy_cumulative_pct = [r * 100 for r in spy_cumulative]

    # Create figure
    fig = go.Figure()

    # Strategy line
    fig.add_trace(go.Scatter(
        x=strategy_dates,
        y=strategy_cumulative_pct,
        mode='lines',
        name='Strategy',
        line=dict(color='#00ff00', width=2),
        hovertemplate='<b>Strategy</b><br>Date: %{x}<br>Cumulative Return: %{y:.2f}%<extra></extra>'
    ))

    # SPY line
    fig.add_trace(go.Scatter(
        x=spy_dates,
        y=spy_cumulative_pct,
        mode='lines',
        name='S&P 500',
        line=dict(color='#0066cc', width=2),
        hovertemplate='<b>S&P 500</b><br>Date: %{x}<br>Cumulative Return: %{y:.2f}%<extra></extra>'
    ))

    # Apply dark theme
    layout = get_plotly_layout_template()
    layout.update({
        'title': f"Equity Curve - Strategy vs S&P 500 ({period_days}d)<br><sub>Trade-to-trade progression (not continuous daily equity)</sub>",
        'xaxis_title': "Date",
        'yaxis_title': "Cumulative Return (%)",
        'hovermode': 'x unified'
    })
    fig.update_layout(**layout)

    return fig


def create_drawdown_chart(result, period_days=21):
    """
    Create drawdown chart showing peak-to-trough declines.

    Args:
        result: BacktestResult object
        period_days: Holding period in days

    Returns:
        Plotly figure
    """
    if not result or not result.trades:
        return go.Figure()

    # Sort trades by entry date
    sorted_trades = sorted(result.trades, key=lambda t: t.entry_date)

    # Calculate cumulative returns and drawdowns for strategy
    strategy_dates = []
    strategy_cumulative = []
    strategy_drawdown = []

    cumulative_return = 0
    peak = 0

    for trade in sorted_trades:
        # Entry point
        strategy_dates.append(trade.entry_date)
        strategy_cumulative.append(cumulative_return)

        # Calculate drawdown at entry
        if cumulative_return > peak:
            peak = cumulative_return
        drawdown = (cumulative_return - peak) * 100  # Convert to percentage
        strategy_drawdown.append(drawdown)

        # Exit point
        cumulative_return += trade.net_return
        strategy_dates.append(trade.exit_date)
        strategy_cumulative.append(cumulative_return)

        # Calculate drawdown at exit
        if cumulative_return > peak:
            peak = cumulative_return
        drawdown = (cumulative_return - peak) * 100
        strategy_drawdown.append(drawdown)

    # Calculate cumulative returns and drawdowns for SPY
    # Use average SPY return from result for each trade
    spy_dates = []
    spy_cumulative = []
    spy_drawdown = []

    cumulative_spy = 0
    spy_peak = 0
    avg_spy = result.avg_spy_return if result.avg_spy_return is not None else 0

    for trade in sorted_trades:
        # Entry point
        spy_dates.append(trade.entry_date)
        spy_cumulative.append(cumulative_spy)

        if cumulative_spy > spy_peak:
            spy_peak = cumulative_spy
        spy_dd = (cumulative_spy - spy_peak) * 100
        spy_drawdown.append(spy_dd)

        # Exit point - use average SPY return as approximation
        cumulative_spy += avg_spy
        spy_dates.append(trade.exit_date)
        spy_cumulative.append(cumulative_spy)

        if cumulative_spy > spy_peak:
            spy_peak = cumulative_spy
        spy_dd = (cumulative_spy - spy_peak) * 100
        spy_drawdown.append(spy_dd)

    # Create figure
    fig = go.Figure()

    # Strategy drawdown (area chart)
    fig.add_trace(go.Scatter(
        x=strategy_dates,
        y=strategy_drawdown,
        mode='lines',
        name='Strategy Drawdown',
        line=dict(color='#ff0000', width=0),
        fill='tozeroy',
        fillcolor='rgba(255, 0, 0, 0.3)',
        hovertemplate='<b>Strategy</b><br>Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>'
    ))

    # SPY drawdown
    fig.add_trace(go.Scatter(
        x=spy_dates,
        y=spy_drawdown,
        mode='lines',
        name='S&P 500 Drawdown',
        line=dict(color='#0066cc', width=0),
        fill='tozeroy',
        fillcolor='rgba(0, 102, 204, 0.3)',
        hovertemplate='<b>S&P 500</b><br>Date: %{x}<br>Drawdown: %{y:.2f}%<extra></extra>'
    ))

    # Mark maximum drawdown point for strategy
    if strategy_drawdown:
        max_dd_idx = strategy_drawdown.index(min(strategy_drawdown))
        max_dd_value = strategy_drawdown[max_dd_idx]
        max_dd_date = strategy_dates[max_dd_idx]

        fig.add_trace(go.Scatter(
            x=[max_dd_date],
            y=[max_dd_value],
            mode='markers',
            name='Max Drawdown',
            marker=dict(color='white', size=10, symbol='x'),
            hovertemplate=f'<b>Max Drawdown</b><br>Date: {max_dd_date.strftime("%Y-%m-%d")}<br>Drawdown: {max_dd_value:.2f}%<extra></extra>'
        ))

    # Apply dark theme
    layout = get_plotly_layout_template()
    layout.update({
        'title': f"Drawdown Analysis ({period_days}d holding period)",
        'xaxis_title': "Date",
        'yaxis_title': "Drawdown (%)",
        'hovermode': 'x unified'
    })
    fig.update_layout(**layout)

    return fig


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
            'Signal Score': f"{trade.signal_score:.2f}",
            '_return_numeric': trade.net_return
        })

    df = pd.DataFrame(data)

    table = dash_table.DataTable(
        data=df.to_dict('records'),
        columns=[{'name': col, 'id': col} for col in df.columns if col != '_return_numeric'],
        hidden_columns=['_return_numeric'],
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
                    'filter_query': '{_return_numeric} < 0',
                    'column_id': 'Net Return'
                },
                'color': '#ff4444'
            },
            {
                'if': {
                    'filter_query': '{_return_numeric} >= 0',
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


def create_ai_analysis_panel():
    """Create AI analysis panel with BUY/NO BUY recommendation."""
    if not backtest_results or not ai_analyzer:
        if not ai_analyzer:
            return dbc.Container([
                html.Hr(className="my-4"),
                html.H4("🤖 AI Analysis", className="mt-4 mb-3"),
                dbc.Alert("AI analyzer not configured. Set ANTHROPIC_API_KEY in .env file.", color="warning")
            ], fluid=True)
        return html.Div()

    # Use 21-day period as primary metric
    primary_period = 21
    result = backtest_results.get(primary_period)
    metric = metrics_results.get(primary_period)

    if not result or result.total_trades == 0 or not metric:
        return html.Div()

    # Generate AI recommendation
    try:
        # Create a simple benchmark metrics object using SPY returns from result
        from backtesting.metrics import RiskMetrics

        # Create benchmark metrics using SPY data from backtest result
        spy_avg_return = result.avg_spy_return if result.avg_spy_return is not None else 0
        benchmark_metrics = RiskMetrics(
            total_return=spy_avg_return * result.total_trades,
            avg_return=spy_avg_return,
            median_return=spy_avg_return,
            std_return=0.01,  # Placeholder - real value would come from SPY price data
            sharpe_ratio=metric.sharpe_ratio * 0.5,  # Rough approximation
            max_drawdown=metric.max_drawdown * 0.8,  # SPY typically has lower drawdown
            calmar_ratio=metric.calmar_ratio * 0.5,
            win_rate=0.6,  # SPY is generally positive over time
            profit_factor=None,
            skewness=0.0,
            kurtosis=0.0
        )

        recommendation = ai_analyzer.analyze(
            strategy_metrics=metric,
            benchmark_metrics=benchmark_metrics,
            alpha=result.alpha if result.alpha is not None else 0,
            holding_days=primary_period,
            total_signals=result.total_trades,
            period_label=f"{primary_period} days"
        )

        # Determine card color based on recommendation
        rec_colors = {
            'BUY': 'success',
            'NO BUY': 'danger',
            'CAUTIOUS': 'warning'
        }
        card_color = rec_colors.get(recommendation.recommendation, 'secondary')

        # Determine emoji
        rec_emojis = {
            'BUY': '✅',
            'NO BUY': '❌',
            'CAUTIOUS': '⚠️'
        }
        emoji = rec_emojis.get(recommendation.recommendation, '🤖')

        return dbc.Container([
            html.Hr(className="my-4"),
            html.H4("🤖 AI Analysis (Claude Sonnet 4.5)", className="mt-4 mb-3"),

            dbc.Card([
                dbc.CardHeader([
                    html.H3([
                        f"{emoji} RECOMMENDATION: {recommendation.recommendation}"
                    ], className=f"text-{card_color} mb-0")
                ], className="py-3"),
                dbc.CardBody([
                    # Rationale section
                    html.H5("📊 Key Findings", className="mt-3 mb-2"),
                    html.Ul([
                        html.Li(finding, className="mb-2")
                        for finding in recommendation.rationale
                    ], className="text-light"),

                    # Risk factors section
                    html.H5("⚠️ Risk Factors", className="mt-4 mb-2"),
                    html.Ul([
                        html.Li(risk, className="mb-2")
                        for risk in recommendation.risk_factors
                    ], className="text-light"),

                    # Confidence badge
                    html.Div([
                        html.H5("Confidence Level: ", className="d-inline me-2"),
                        dbc.Badge(
                            recommendation.confidence,
                            color="success" if recommendation.confidence == "High" else
                                  "warning" if recommendation.confidence == "Medium" else "secondary",
                            className="fs-6"
                        )
                    ], className="mt-4")
                ], className="py-4")
            ], color="dark", outline=True, className="mb-4")
        ], fluid=True)

    except Exception as e:
        print(f"Error generating AI analysis: {e}")
        return dbc.Container([
            html.Hr(className="my-4"),
            html.H4("🤖 AI Analysis", className="mt-4 mb-3"),
            dbc.Alert(f"Error generating analysis: {str(e)}", color="danger")
        ], fluid=True)


def create_performance_charts():
    """Create performance visualization charts."""
    if not backtest_results:
        return html.Div("No data available")

    # Use 21-day period
    result = backtest_results.get(21)
    if not result or not result.trades:
        return html.Div("No charts available")

    # Generate charts
    equity_curve = create_equity_curve_chart(result, period_days=21)
    returns_hist = create_returns_histogram(result, period_days=21)
    drawdown_chart = create_drawdown_chart(result, period_days=21)

    return dbc.Container([
        html.Hr(className="my-4"),
        html.H4("📈 Performance Charts", className="mt-4 mb-3"),

        # Equity curve (full width)
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure=equity_curve, config={'displayModeBar': True})
            ], width=12)
        ], className="mb-4"),

        # Returns histogram and drawdown chart (side by side)
        dbc.Row([
            dbc.Col([
                dcc.Graph(figure=returns_hist, config={'displayModeBar': True})
            ], width=6),
            dbc.Col([
                dcc.Graph(figure=drawdown_chart, config={'displayModeBar': True})
            ], width=6)
        ])
    ], fluid=True)


# App layout
app.layout = html.Div([
    create_header(),
    dbc.Container([
        create_summary_cards(),
        create_ai_analysis_panel(),  # AI analysis after summary cards
        create_performance_table(),
        html.Hr(className="my-4"),
        create_trades_table(),
        create_performance_charts()
    ], fluid=True, className="px-4")
])


def run_dashboard(host='127.0.0.1', port=8050, debug=True):
    """Run the Dash app."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_dashboard()
