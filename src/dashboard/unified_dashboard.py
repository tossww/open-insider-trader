"""
Unified Dashboard for Open InsiderTrader.

Combines parameter tuning with live backtest results - adjust filters and see
performance impact immediately.
"""

import sys
from pathlib import Path
from datetime import datetime
import sqlite3

import dash
from dash import dcc, html, dash_table, ctx
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from backtesting.backtest_engine import BacktestEngine, Signal
from backtesting.metrics import MetricsCalculator
from processors.executive_classifier import ExecutiveClassifier
import yaml


# Load default config
with open('config.yaml', 'r') as f:
    DEFAULT_CONFIG = yaml.safe_load(f)


def load_all_transactions(db_path: str = 'data/insider_trades.db'):
    """Load all purchase transactions from database."""
    conn = sqlite3.connect(db_path)

    query = """
        SELECT
            it.id,
            it.trade_date,
            it.filing_date,
            it.transaction_code,
            it.shares,
            it.price_per_share,
            it.total_value,
            c.ticker,
            c.name as company_name,
            i.name as insider_name,
            i.officer_title,
            mc.market_cap_usd
        FROM insider_transactions it
        JOIN companies c ON it.company_id = c.id
        JOIN insiders i ON it.insider_id = i.id
        LEFT JOIN market_caps mc ON (
            mc.company_id = c.id
            AND DATE(mc.date) = DATE(it.filing_date)
        )
        WHERE it.transaction_code IN ('P', 'M')
        ORDER BY it.filing_date DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()
    return df


def apply_filters_and_backtest(df, min_trade_value, min_market_cap_pct, exec_levels, min_signal_score):
    """
    Apply filters, calculate scores, run backtest, and create ticker-level results.

    Returns:
        Tuple of (ticker_results_df, avg_performance_dict, stats, all_results, all_metrics)
    """
    stats = {
        'total_transactions': len(df),
        'after_dollar_filter': 0,
        'after_exec_filter': 0,
        'after_market_cap_filter': 0,
        'after_score_filter': 0
    }

    # Initialize classifier
    classifier = ExecutiveClassifier('config.yaml')

    # Filter 1: Dollar value
    df_filtered = df[df['total_value'] >= min_trade_value].copy()
    stats['after_dollar_filter'] = len(df_filtered)

    if len(df_filtered) == 0:
        return pd.DataFrame(), {}, stats, {}, {}

    # Filter 2: Executive level
    df_filtered['exec_weight'] = df_filtered['officer_title'].apply(
        lambda x: classifier.get_weight(x)
    )

    if 'C-Suite' in exec_levels and 'VP' not in exec_levels:
        df_filtered = df_filtered[df_filtered['exec_weight'] == 1.0]
    elif 'VP' in exec_levels and 'C-Suite' not in exec_levels:
        df_filtered = df_filtered[df_filtered['exec_weight'] == 0.5]
    elif 'C-Suite' in exec_levels and 'VP' in exec_levels:
        df_filtered = df_filtered[df_filtered['exec_weight'] >= 0.5]
    else:
        df_filtered = df_filtered[df_filtered['exec_weight'] > 0]

    stats['after_exec_filter'] = len(df_filtered)

    if len(df_filtered) == 0:
        return pd.DataFrame(), {}, stats, {}, {}

    # Filter 3: Market cap %
    if min_market_cap_pct > 0:
        df_filtered['market_cap_pct'] = (
            df_filtered['total_value'] / df_filtered['market_cap_usd']
        )
        df_filtered = df_filtered[
            (df_filtered['market_cap_pct'] >= min_market_cap_pct) |
            (df_filtered['market_cap_usd'].isna())
        ]

    stats['after_market_cap_filter'] = len(df_filtered)

    # Calculate scores
    base_amount = 100000
    df_filtered['dollar_weight'] = 1 + 0.5 * np.log10(
        df_filtered['total_value'] / base_amount
    )

    if min_market_cap_pct > 0 and 'market_cap_pct' in df_filtered.columns:
        baseline_pct = 0.00001
        df_filtered['market_cap_weight'] = np.clip(
            1 + 0.5 * np.log10(df_filtered['market_cap_pct'] / baseline_pct),
            0.5,
            3.0
        )
    else:
        df_filtered['market_cap_weight'] = 1.0

    df_filtered['composite_score'] = (
        df_filtered['exec_weight'] *
        df_filtered['dollar_weight'] *
        df_filtered['market_cap_weight']
    )

    # Filter 4: Score threshold
    df_filtered = df_filtered[df_filtered['composite_score'] >= min_signal_score]
    stats['after_score_filter'] = len(df_filtered)

    if len(df_filtered) == 0:
        return pd.DataFrame(), {}, stats, {}, {}

    # Sort by score
    df_filtered = df_filtered.sort_values('composite_score', ascending=False)

    # Run backtest for each ticker
    engine = BacktestEngine(
        commission_pct=DEFAULT_CONFIG['backtesting']['commission_pct'],
        slippage_pct=DEFAULT_CONFIG['backtesting']['slippage_pct']
    )

    holding_periods = [1, 5, 21, 252]  # 1d, 1w, 1m, 1y
    period_labels = {1: '1d', 5: '1w', 21: '1m', 252: '1y'}

    ticker_results = []
    all_signals = []

    for ticker in df_filtered['ticker'].unique():
        ticker_df = df_filtered[df_filtered['ticker'] == ticker]

        # Create signals for this ticker
        ticker_signals = []
        for _, row in ticker_df.iterrows():
            signal = Signal(
                ticker=row['ticker'],
                filing_date=pd.to_datetime(row['filing_date']),
                trade_date=pd.to_datetime(row['trade_date']),
                insider_name=row['insider_name'],
                officer_title=row['officer_title'] or 'Unknown',
                total_value=row['total_value'],
                composite_score=row['composite_score'],
                cluster_size=1
            )
            ticker_signals.append(signal)
            all_signals.append(signal)

        # Backtest this ticker across periods
        ticker_row = {'Ticker': ticker, 'Signals': len(ticker_signals)}

        for period in holding_periods:
            label = period_labels[period]
            result = engine.backtest_signals(ticker_signals, holding_days=period)

            if result.total_trades > 0:
                # Add benchmark comparison
                result = engine.add_benchmark_comparison(result, DEFAULT_CONFIG['backtesting']['benchmark_ticker'])

                ticker_row[f'{label}_gain'] = f"{result.avg_net_return:.2%}"
                ticker_row[f'{label}_spy'] = f"{result.avg_spy_return:.2%}" if result.avg_spy_return is not None else "N/A"
                ticker_row[f'{label}_alpha'] = f"{result.alpha:+.2%}" if result.alpha is not None else "N/A"
            else:
                ticker_row[f'{label}_gain'] = 'N/A'
                ticker_row[f'{label}_spy'] = 'N/A'
                ticker_row[f'{label}_alpha'] = 'N/A'

        ticker_results.append(ticker_row)

    # Calculate overall average performance
    avg_performance = {}
    for period in holding_periods:
        label = period_labels[period]
        result = engine.backtest_signals(all_signals, holding_days=period)

        if result.total_trades > 0:
            result = engine.add_benchmark_comparison(result, DEFAULT_CONFIG['backtesting']['benchmark_ticker'])
            avg_performance[label] = {
                'strategy': result.avg_net_return * 100,
                'spy': result.avg_spy_return * 100 if result.avg_spy_return is not None else 0,
                'alpha': result.alpha * 100 if result.alpha is not None else 0
            }

    ticker_df_results = pd.DataFrame(ticker_results)

    # Run full backtest for additional metrics
    all_periods = [1, 5, 21, 63, 126, 252]
    all_results = engine.backtest_multiple_periods(all_signals, all_periods)

    # Add benchmark comparison
    for period, result in all_results.items():
        if result.total_trades > 0:
            all_results[period] = engine.add_benchmark_comparison(
                result,
                DEFAULT_CONFIG['backtesting']['benchmark_ticker']
            )

    # Calculate metrics
    calculator = MetricsCalculator(risk_free_rate=DEFAULT_CONFIG['backtesting']['risk_free_rate'])
    all_metrics = {}

    for period, result in all_results.items():
        if result.total_trades > 0:
            returns = [t.net_return for t in result.trades]
            all_metrics[period] = calculator.calculate_metrics(returns, period if period != -1 else 252)
        else:
            all_metrics[period] = None

    return ticker_df_results, avg_performance, stats, all_results, all_metrics


# Load initial data
all_transactions_df = load_all_transactions()

# Initialize result cache (parameters -> results)
# Cache key: (min_trade_value, min_market_cap_pct, exec_levels_tuple, min_signal_score)
result_cache = {}

# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Unified Dashboard - Open InsiderTrader"
)


def create_header():
    """Create dashboard header."""
    return dbc.Container([
        html.H1("🎯 Open InsiderTrader - Unified Dashboard", className="text-center mt-4 mb-2"),
        html.H4("Tune Parameters & See Live Backtest Results", className="text-center text-muted mb-4"),
        html.Hr()
    ], fluid=True)


def create_parameter_controls():
    """Create parameter control panel."""
    return dbc.Card([
        dbc.CardHeader([
            html.H4("⚙️ Filter Parameters", className="mb-0")
        ]),
        dbc.CardBody([
            dbc.Row([
                # Left: Sliders
                dbc.Col([
                    html.Div([
                        html.Label("Minimum Trade Value", className="fw-bold mb-2"),
                        dcc.Slider(
                            id='min-trade-value-slider',
                            min=25000,
                            max=500000,
                            step=25000,
                            value=DEFAULT_CONFIG['filtering']['min_trade_value'],
                            marks={
                                25000: '$25K',
                                100000: '$100K',
                                250000: '$250K',
                                500000: '$500K'
                            },
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ], className="mb-4"),

                    html.Div([
                        html.Label("Minimum Signal Score", className="fw-bold mb-2"),
                        dcc.Slider(
                            id='min-signal-score-slider',
                            min=0.5,
                            max=5.0,
                            step=0.1,
                            value=DEFAULT_CONFIG['scoring']['min_signal_score'],
                            marks={
                                0.5: '0.5',
                                1.0: '1.0',
                                2.0: '2.0',
                                3.0: '3.0',
                                5.0: '5.0'
                            },
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ], className="mb-4"),

                    html.Div([
                        html.Label("Minimum Market Cap %", className="fw-bold mb-2"),
                        dcc.Slider(
                            id='min-market-cap-pct-slider',
                            min=0,
                            max=0.001,
                            step=0.00001,
                            value=DEFAULT_CONFIG['filtering']['min_market_cap_pct'],
                            marks={
                                0: 'Off',
                                0.00001: '0.00001%',
                                0.0001: '0.0001%',
                                0.001: '0.001%'
                            },
                            tooltip={"placement": "bottom", "always_visible": True}
                        ),
                    ]),
                ], width=8),

                # Right: Checkboxes + Button
                dbc.Col([
                    html.Label("Executive Levels", className="fw-bold mb-3"),
                    dbc.Checklist(
                        id='exec-level-checklist',
                        options=[
                            {'label': ' C-Suite Only', 'value': 'C-Suite'},
                            {'label': ' Include VPs', 'value': 'VP'},
                            {'label': ' All Executives', 'value': 'All'}
                        ],
                        value=['C-Suite'],
                        className="mb-4"
                    ),

                    dbc.Button(
                        "🔄 Update Results",
                        id='update-button',
                        color="primary",
                        size="lg",
                        className="w-100"
                    ),

                    html.Div([
                        html.Small("Tip: Adjust parameters and click Update to see performance change",
                                   className="text-muted mt-2 d-block")
                    ])
                ], width=4)
            ])
        ])
    ], className="mb-4")


def create_ticker_table(ticker_df):
    """Create ticker-level results table."""
    if ticker_df.empty:
        return dbc.Alert("No signals match current filters. Try relaxing parameters.", color="warning")

    # Build conditional styling rules for color coding
    style_conditions = [
        # Ticker column - bold green, left aligned
        {
            'if': {'column_id': 'Ticker'},
            'fontWeight': 'bold',
            'color': '#00ff00',
            'textAlign': 'left'
        },
        # Signals column - cyan
        {
            'if': {'column_id': 'Signals'},
            'color': '#00ddff',
            'fontWeight': 'bold'
        }
    ]

    # Color code all gain columns (green/red based on positive/negative)
    for period in ['1d', '1w', '1m', '1y']:
        # Gain columns - red if negative, green otherwise (default positive)
        style_conditions.extend([
            {
                'if': {
                    'filter_query': f'{{{period}_gain}} contains "-"',
                    'column_id': f'{period}_gain'
                },
                'color': '#ff4444',
                'fontWeight': 'bold'
            }
        ])
        # Green for non-N/A, non-negative (applied after red rule)
        style_conditions.append({
            'if': {'column_id': f'{period}_gain'},
            'color': '#00ff00',
            'fontWeight': 'bold'
        })

        # SPY columns - red if negative, green otherwise
        style_conditions.extend([
            {
                'if': {
                    'filter_query': f'{{{period}_spy}} contains "-"',
                    'column_id': f'{period}_spy'
                },
                'color': '#ff4444'
            }
        ])
        # Green for SPY (applied after red rule)
        style_conditions.append({
            'if': {'column_id': f'{period}_spy'},
            'color': '#00ff00'
        })

        # Alpha columns - green if positive (+), red if negative (-), with highlight background
        style_conditions.extend([
            {
                'if': {
                    'filter_query': f'{{{period}_alpha}} contains "-"',
                    'column_id': f'{period}_alpha'
                },
                'color': '#ff4444',
                'fontWeight': 'bold',
                'backgroundColor': '#3d1a1a'  # Dark red background
            },
            {
                'if': {
                    'filter_query': f'{{{period}_alpha}} contains "+"',
                    'column_id': f'{period}_alpha'
                },
                'color': '#00ff00',
                'fontWeight': 'bold',
                'backgroundColor': '#1a3d1a'  # Dark green background
            },
            {
                'if': {
                    'filter_query': f'{{{period}_alpha}} = "N/A"',
                    'column_id': f'{period}_alpha'
                },
                'backgroundColor': '#2d2d2d',  # Slightly different gray for N/A
                'color': '#888888'
            }
        ])

    return dbc.Card([
        dbc.CardHeader(html.H4("📊 Ticker-Level Results")),
        dbc.CardBody([
            dash_table.DataTable(
                data=ticker_df.to_dict('records'),
                columns=[{'name': col, 'id': col} for col in ticker_df.columns],
                style_table={'overflowX': 'auto'},
                style_cell={
                    'textAlign': 'center',
                    'padding': '10px',
                    'backgroundColor': '#303030',
                    'color': 'white',
                    'fontSize': '13px'
                },
                style_header={
                    'backgroundColor': '#1e1e1e',
                    'fontWeight': 'bold',
                    'color': 'white',
                    'fontSize': '14px'
                },
                style_data_conditional=style_conditions,
                page_size=20,
                sort_action='native',
                filter_action='native'
            )
        ])
    ], className="mb-4")


def create_comparison_charts(avg_perf):
    """Create 4 comparison charts showing strategy vs S&P 500."""
    if not avg_perf:
        empty_fig = go.Figure()
        empty_fig.update_layout(template='plotly_dark', title='No data')
        return [empty_fig] * 4

    periods = list(avg_perf.keys())
    strategy_returns = [avg_perf[p]['strategy'] for p in periods]
    spy_returns = [avg_perf[p]['spy'] for p in periods]
    alphas = [avg_perf[p]['alpha'] for p in periods]

    # Chart 1: Bar comparison of returns
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(name='Strategy', x=periods, y=strategy_returns, marker_color='#00ff00'))
    fig1.add_trace(go.Bar(name='S&P 500', x=periods, y=spy_returns, marker_color='#0066cc'))
    fig1.update_layout(
        template='plotly_dark',
        title='Average Returns: Strategy vs S&P 500',
        xaxis_title='Holding Period',
        yaxis_title='Return (%)',
        barmode='group',
        height=350
    )

    # Chart 2: Alpha bars
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=periods, y=alphas, marker_color='#ffaa00'))
    fig2.update_layout(
        template='plotly_dark',
        title='Alpha vs S&P 500',
        xaxis_title='Holding Period',
        yaxis_title='Alpha (%)',
        height=350
    )

    # Chart 3: Line comparison
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=periods, y=strategy_returns, mode='lines+markers',
        name='Strategy', line=dict(color='#00ff00', width=3), marker=dict(size=10)
    ))
    fig3.add_trace(go.Scatter(
        x=periods, y=spy_returns, mode='lines+markers',
        name='S&P 500', line=dict(color='#0066cc', width=3), marker=dict(size=10)
    ))
    fig3.update_layout(
        template='plotly_dark',
        title='Performance Trend Over Holding Periods',
        xaxis_title='Holding Period',
        yaxis_title='Return (%)',
        height=350
    )

    # Chart 4: Waterfall of alpha contribution
    fig4 = go.Figure()
    fig4.add_trace(go.Waterfall(
        x=periods,
        y=alphas,
        connector={"line": {"color": "rgb(63, 63, 63)"}},
        increasing={"marker": {"color": "#00ff00"}},
        decreasing={"marker": {"color": "#ff4444"}}
    ))
    fig4.update_layout(
        template='plotly_dark',
        title='Alpha Waterfall',
        xaxis_title='Holding Period',
        yaxis_title='Alpha (%)',
        height=350
    )

    return [fig1, fig2, fig3, fig4]


def create_performance_table(results, metrics):
    """Create summary performance comparison table."""
    if not results:
        return html.Div()

    data = []
    period_map = {5: '5D', 21: '1M', 63: '3M', 126: '6M', 252: '1Y', 504: '2Y'}

    for period in sorted(results.keys()):
        result = results[period]
        metric = metrics.get(period)

        if result.total_trades == 0:
            continue

        period_label = period_map.get(period, f"{period}d")

        data.append({
            'Period': period_label,
            'Trades': result.total_trades,
            'Avg Return': f"{result.avg_net_return:.2%}",
            'SPY': f"{result.avg_spy_return:.2%}" if result.avg_spy_return is not None else "N/A",
            'Alpha': f"{result.alpha:+.2%}" if result.alpha is not None else "N/A",
            'Win %': f"{result.win_rate:.1%}",
            'Sharpe': f"{metric.sharpe_ratio:.2f}" if metric and metric.sharpe_ratio < 1000 else "N/A",
            'Max DD': f"{metric.max_drawdown:.2%}" if metric else "N/A"
        })

    if not data:
        return html.Div()

    df = pd.DataFrame(data)

    return dbc.Container([
        html.H4("📊 Multi-Period Performance Summary", className="mt-4 mb-3"),
        dash_table.DataTable(
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
                    'if': {'column_id': 'Avg Return'},
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
    ], fluid=True)


def create_detailed_trades_table(results):
    """Create detailed trade-by-trade table with all periods."""
    if not results:
        return html.Div()

    # Get all trades from the first period that has data
    first_result = None
    for period in sorted(results.keys()):
        if results[period].total_trades > 0:
            first_result = results[period]
            break

    if not first_result:
        return html.Div()

    # Build trade dictionary mapping (ticker, entry_date) to trade info
    trades_map = {}
    for trade in first_result.trades:
        key = (trade.ticker, trade.entry_date)
        trades_map[key] = {
            'Ticker': trade.ticker,
            'Entry Date': trade.entry_date.strftime('%Y-%m-%d'),
            'Signal Score': f"{trade.signal_score:.2f}",
        }

    # Add returns for each period
    period_map = {5: '5D', 21: '1M', 63: '3M', 126: '6M', 252: '1Y', 504: '2Y'}

    for period in sorted(results.keys()):
        result = results[period]
        if result.total_trades == 0:
            continue

        period_label = period_map.get(period, f"{period}d")

        # Create columns for this period
        for trade in result.trades:
            key = (trade.ticker, trade.entry_date)
            if key in trades_map:
                # Strategy return
                trades_map[key][f'{period_label} Return'] = f"{trade.net_return:.2%}"

                # SPY benchmark return
                spy_return = trade.spy_return if hasattr(trade, 'spy_return') and trade.spy_return is not None else None
                trades_map[key][f'{period_label} SPY'] = f"{spy_return:.2%}" if spy_return is not None else "N/A"

                # Alpha
                if spy_return is not None:
                    alpha = trade.net_return - spy_return
                    trades_map[key][f'{period_label} Alpha'] = f"{alpha:+.2%}"
                else:
                    trades_map[key][f'{period_label} Alpha'] = "N/A"

    # Convert to list for DataFrame
    trades_data = list(trades_map.values())

    if not trades_data:
        return html.Div()

    df = pd.DataFrame(trades_data)

    # Calculate averages row
    avg_row = {'Ticker': 'AVERAGE', 'Entry Date': '', 'Signal Score': ''}

    for period in sorted(results.keys()):
        if results[period].total_trades == 0:
            continue

        period_label = period_map.get(period, f"{period}d")
        result = results[period]

        # Average return
        avg_row[f'{period_label} Return'] = f"{result.avg_net_return:.2%}"

        # Average SPY
        avg_spy = result.avg_spy_return if result.avg_spy_return is not None else None
        avg_row[f'{period_label} SPY'] = f"{avg_spy:.2%}" if avg_spy is not None else "N/A"

        # Average Alpha
        alpha = result.alpha if result.alpha is not None else None
        avg_row[f'{period_label} Alpha'] = f"{alpha:+.2%}" if alpha is not None else "N/A"

    # Add average row at the end
    df = pd.concat([df, pd.DataFrame([avg_row])], ignore_index=True)

    return dbc.Container([
        html.H4("📋 Detailed Trade-by-Trade Returns", className="mt-4 mb-3"),
        html.P("Returns shown for each holding period: 5D, 1M, 3M, 6M, 1Y, 2Y. Last row shows averages.",
               className="text-muted"),
        dash_table.DataTable(
            data=df.to_dict('records'),
            columns=[{'name': col, 'id': col} for col in df.columns],
            style_table={'overflowX': 'auto'},
            style_cell={
                'textAlign': 'left',
                'padding': '8px',
                'backgroundColor': '#303030',
                'color': 'white',
                'fontSize': '12px',
                'minWidth': '80px'
            },
            style_header={
                'backgroundColor': '#1e1e1e',
                'fontWeight': 'bold',
                'color': 'white',
                'fontSize': '13px'
            },
            style_data_conditional=[
                # Highlight average row
                {
                    'if': {'filter_query': '{Ticker} = "AVERAGE"'},
                    'backgroundColor': '#1e1e1e',
                    'fontWeight': 'bold',
                    'borderTop': '2px solid white'
                },
                # Color positive returns green
                {
                    'if': {
                        'filter_query': '{5D Return} contains "%" && {5D Return} > 0',
                    },
                    'column_id': '5D Return',
                    'color': '#00ff00'
                },
                {
                    'if': {
                        'filter_query': '{1M Return} contains "%" && {1M Return} > 0',
                    },
                    'column_id': '1M Return',
                    'color': '#00ff00'
                },
                {
                    'if': {
                        'filter_query': '{3M Return} contains "%" && {3M Return} > 0',
                    },
                    'column_id': '3M Return',
                    'color': '#00ff00'
                },
                {
                    'if': {
                        'filter_query': '{6M Return} contains "%" && {6M Return} > 0',
                    },
                    'column_id': '6M Return',
                    'color': '#00ff00'
                },
                {
                    'if': {
                        'filter_query': '{1Y Return} contains "%" && {1Y Return} > 0',
                    },
                    'column_id': '1Y Return',
                    'color': '#00ff00'
                },
                {
                    'if': {
                        'filter_query': '{2Y Return} contains "%" && {2Y Return} > 0',
                    },
                    'column_id': '2Y Return',
                    'color': '#00ff00'
                },
                # Color negative returns red
                {
                    'if': {
                        'filter_query': '{5D Return} contains "%" && {5D Return} < 0',
                    },
                    'column_id': '5D Return',
                    'color': '#ff4444'
                },
                {
                    'if': {
                        'filter_query': '{1M Return} contains "%" && {1M Return} < 0',
                    },
                    'column_id': '1M Return',
                    'color': '#ff4444'
                },
                {
                    'if': {
                        'filter_query': '{3M Return} contains "%" && {3M Return} < 0',
                    },
                    'column_id': '3M Return',
                    'color': '#ff4444'
                },
                {
                    'if': {
                        'filter_query': '{6M Return} contains "%" && {6M Return} < 0',
                    },
                    'column_id': '6M Return',
                    'color': '#ff4444'
                },
                {
                    'if': {
                        'filter_query': '{1Y Return} contains "%" && {1Y Return} < 0',
                    },
                    'column_id': '1Y Return',
                    'color': '#ff4444'
                },
                {
                    'if': {
                        'filter_query': '{2Y Return} contains "%" && {2Y Return} < 0',
                    },
                    'column_id': '2Y Return',
                    'color': '#ff4444'
                },
            ],
            page_size=50,
            sort_action='native',
            filter_action='native'
        )
    ], fluid=True)


def create_equity_curve(result_21d):
    """Create equity curve chart."""
    if not result_21d or not result_21d.trades:
        return go.Figure()

    sorted_trades = sorted(result_21d.trades, key=lambda t: t.entry_date)

    # Strategy equity
    strategy_dates = []
    strategy_cumulative = []
    cumulative_return = 0

    for trade in sorted_trades:
        strategy_dates.append(trade.entry_date)
        strategy_cumulative.append(cumulative_return * 100)

        cumulative_return += trade.net_return
        strategy_dates.append(trade.exit_date)
        strategy_cumulative.append(cumulative_return * 100)

    # SPY equity
    spy_dates = []
    spy_cumulative = []
    cumulative_spy = 0
    avg_spy = result_21d.avg_spy_return if result_21d.avg_spy_return is not None else 0

    for trade in sorted_trades:
        spy_dates.append(trade.entry_date)
        spy_cumulative.append(cumulative_spy * 100)

        cumulative_spy += avg_spy
        spy_dates.append(trade.exit_date)
        spy_cumulative.append(cumulative_spy * 100)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=strategy_dates,
        y=strategy_cumulative,
        mode='lines',
        name='Strategy',
        line=dict(color='#00ff00', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=spy_dates,
        y=spy_cumulative,
        mode='lines',
        name='S&P 500',
        line=dict(color='#0066cc', width=2)
    ))

    fig.update_layout(
        title="Equity Curve - Strategy vs S&P 500 (21d)",
        xaxis_title="Date",
        yaxis_title="Cumulative Return (%)",
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font={'color': 'white'},
        xaxis={'gridcolor': '#404040'},
        yaxis={'gridcolor': '#404040'},
        legend={'bgcolor': '#1e1e1e'},
        hovermode='x unified',
        height=400
    )

    return fig


# App layout
app.layout = html.Div([
    create_header(),

    dbc.Container([
        create_parameter_controls(),

        # Store for results
        dcc.Store(id='backtest-results-store'),
        dcc.Store(id='stats-store'),

        # Progress indicator
        html.Div(id='progress-container', children=[], className="mb-3"),

        # Stores for multi-step processing
        dcc.Store(id='processing-state', data={'step': 0, 'total_steps': 0, 'current_ticker': ''}),
        dcc.Interval(id='progress-interval', interval=500, n_intervals=0, disabled=True),

        # Loading spinner
        dcc.Loading(
            id="loading",
            type="default",
            children=[
                # Ticker results table
                html.Div(id='ticker-table-container', children=[
                    dbc.Alert([
                        html.H4("👋 Welcome!", className="alert-heading"),
                        html.P("Adjust the parameters above and click 'Update Results' to see ticker-level performance."),
                        html.Hr(),
                        html.P([
                            html.Strong("Tip: "),
                            "Start with default settings, then experiment with thresholds to optimize alpha."
                        ], className="mb-0")
                    ], color="info")
                ], className="mb-4"),

                # Average comparison charts
                dbc.Card([
                    dbc.CardHeader(html.H4("📈 Average Performance: Strategy vs S&P 500")),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([dcc.Graph(id='chart-1')], width=6),
                            dbc.Col([dcc.Graph(id='chart-2')], width=6)
                        ]),
                        dbc.Row([
                            dbc.Col([dcc.Graph(id='chart-3')], width=6),
                            dbc.Col([dcc.Graph(id='chart-4')], width=6)
                        ])
                    ])
                ], className="mb-4")
            ]
        )
    ], fluid=True)
])


@app.callback(
    [
        Output('backtest-results-store', 'data'),
        Output('stats-store', 'data'),
        Output('ticker-table-container', 'children'),
        Output('chart-1', 'figure'),
        Output('chart-2', 'figure'),
        Output('chart-3', 'figure'),
        Output('chart-4', 'figure'),
        Output('progress-container', 'children')
    ],
    [
        Input('update-button', 'n_clicks'),
    ],
    [
        State('min-trade-value-slider', 'value'),
        State('min-signal-score-slider', 'value'),
        State('min-market-cap-pct-slider', 'value'),
        State('exec-level-checklist', 'value')
    ],
    prevent_initial_call=True,
    running=[
        (Output('update-button', 'disabled'), True, False),
    ]
)
def update_dashboard(n_clicks, min_trade_value, min_signal_score, min_market_cap_pct, exec_levels):
    """Update dashboard with new backtest results based on parameters."""

    import time
    start_time = time.time()

    # Create cache key from parameters
    exec_levels_sorted = tuple(sorted(exec_levels or ['C-Suite']))
    cache_key = (min_trade_value, min_market_cap_pct, exec_levels_sorted, min_signal_score)

    # Check cache first
    if cache_key in result_cache:
        print("\n" + "="*80)
        print("⚡ CACHE HIT - Returning cached results instantly!")
        print("="*80)
        print(f"Parameters: Trade≥${min_trade_value:,} | Score≥{min_signal_score} | Exec={exec_levels}")
        print("="*80 + "\n")

        cached_result = result_cache[cache_key]
        ticker_df = cached_result['ticker_df']
        avg_perf = cached_result['avg_perf']
        stats = cached_result['stats']

        # Create outputs from cache
        ticker_table = create_ticker_table(ticker_df)
        fig1, fig2, fig3, fig4 = create_comparison_charts(avg_perf)
        results_data = {'has_results': not ticker_df.empty}

        # Instant progress message
        if not ticker_df.empty:
            total_signals = stats.get('after_score_filter', len(ticker_df))
            progress_msg = dbc.Alert([
                html.H5(f"⚡ Loaded from Cache!", className="alert-heading mb-2"),
                html.P([
                    f"Displaying ",
                    html.Strong(f"{total_signals} signals"),
                    f" across ",
                    html.Strong(f"{len(ticker_df)} tickers"),
                    f" (instant retrieval)"
                ], className="mb-0")
            ],
                color="info",
                dismissable=True,
                duration=4000
            )
        else:
            progress_msg = dbc.Alert(
                "⚠️ No signals found with current filters.",
                color="warning",
                dismissable=True
            )

        return results_data, stats, ticker_table, fig1, fig2, fig3, fig4, progress_msg

    # Cache miss - compute results
    print("\n" + "="*80)
    print("🔄 DASHBOARD UPDATE STARTED")
    print("="*80)
    print(f"Parameters: Trade≥${min_trade_value:,} | Score≥{min_signal_score} | Exec={exec_levels}")

    # Quick filter to estimate signal count
    df_quick = all_transactions_df.copy()
    df_quick = df_quick[df_quick['total_value'] >= min_trade_value]
    print(f"📊 Estimated signals to process: ~{len(df_quick)} transactions")
    print(f"⏱️  Estimated time: ~{len(df_quick)//2 * 2}-{len(df_quick)//2 * 3} seconds")
    print("="*80 + "\n")

    # Apply filters and run backtest
    ticker_df, avg_perf, stats, results, metrics = apply_filters_and_backtest(
        all_transactions_df,
        min_trade_value,
        min_market_cap_pct,
        exec_levels or ['C-Suite'],
        min_signal_score
    )

    # Store in cache
    result_cache[cache_key] = {
        'ticker_df': ticker_df,
        'avg_perf': avg_perf,
        'stats': stats
    }
    print(f"💾 Results cached for parameters: {cache_key}")

    elapsed_time = time.time() - start_time

    print("\n" + "="*80)
    print(f"✅ DASHBOARD UPDATE COMPLETE - {elapsed_time:.1f} seconds")
    print(f"📈 Found {len(ticker_df)} tickers with signals")
    print("="*80 + "\n")

    # Create ticker table
    ticker_table = create_ticker_table(ticker_df)

    # Create 4 comparison charts
    fig1, fig2, fig3, fig4 = create_comparison_charts(avg_perf)

    # Store data (simplified - not storing full objects)
    results_data = {
        'has_results': not ticker_df.empty
    }

    # Progress message (shows after completion)
    if not ticker_df.empty:
        total_signals = stats.get('after_score_filter', len(ticker_df))
        progress_msg = dbc.Alert([
            html.H5(f"✅ Backtest Complete!", className="alert-heading mb-2"),
            html.P([
                f"Analyzed ",
                html.Strong(f"{total_signals} signals"),
                f" across ",
                html.Strong(f"{len(ticker_df)} tickers"),
                f" in {elapsed_time:.1f} seconds"
            ], className="mb-0")
        ],
            color="success",
            dismissable=True,
            duration=5000
        )
    else:
        progress_msg = dbc.Alert(
            "⚠️ No signals found with current filters. Try relaxing the parameters.",
            color="warning",
            dismissable=True
        )

    return results_data, stats, ticker_table, fig1, fig2, fig3, fig4, progress_msg


def run_unified_dashboard(host='127.0.0.1', port=8052, debug=True):
    """Run the unified dashboard."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_unified_dashboard()
