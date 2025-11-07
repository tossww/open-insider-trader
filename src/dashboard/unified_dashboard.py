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
    Apply filters, calculate scores, and run backtest.

    Returns:
        Tuple of (filtered_df, stats, backtest_results, metrics_results)
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
        return df_filtered, stats, {}, {}

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
        return df_filtered, stats, {}, {}

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
        return df_filtered, stats, {}, {}

    # Sort by score
    df_filtered = df_filtered.sort_values('composite_score', ascending=False)

    # Convert to Signal objects for backtesting
    signals = []
    for _, row in df_filtered.iterrows():
        signals.append(Signal(
            ticker=row['ticker'],
            filing_date=pd.to_datetime(row['filing_date']),
            trade_date=pd.to_datetime(row['trade_date']),
            insider_name=row['insider_name'],
            officer_title=row['officer_title'] or 'Unknown',
            total_value=row['total_value'],
            composite_score=row['composite_score'],
            cluster_size=1  # Simplified - not doing clustering in real-time
        ))

    # Run backtest
    engine = BacktestEngine(
        commission_pct=DEFAULT_CONFIG['backtesting']['commission_pct'],
        slippage_pct=DEFAULT_CONFIG['backtesting']['slippage_pct']
    )

    # All requested periods: 5D, 1M, 3M, 6M, 1Y, 2Y
    holding_periods = [5, 21, 63, 126, 252, 504]
    results = engine.backtest_multiple_periods(signals, holding_periods)

    # Add benchmark comparison
    for period, result in results.items():
        if result.total_trades > 0:
            results[period] = engine.add_benchmark_comparison(
                result,
                DEFAULT_CONFIG['backtesting']['benchmark_ticker']
            )

    # Calculate metrics
    calculator = MetricsCalculator(risk_free_rate=DEFAULT_CONFIG['backtesting']['risk_free_rate'])
    metrics = {}

    for period, result in results.items():
        if result.total_trades > 0:
            returns = [t.net_return for t in result.trades]
            metrics[period] = calculator.calculate_metrics(returns, period if period != -1 else 252)
        else:
            metrics[period] = None

    return df_filtered, stats, results, metrics


# Load initial data
all_transactions_df = load_all_transactions()

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


def create_summary_cards(stats, result_21d):
    """Create performance summary cards."""
    if not result_21d or result_21d.total_trades == 0:
        return dbc.Alert("No signals match current filters. Try relaxing parameters.", color="warning")

    alpha_value = result_21d.alpha if result_21d.alpha is not None else 0
    alpha_color = "success" if alpha_value > 0 else "danger" if alpha_value < 0 else "warning"

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Total Signals", className="text-muted"),
                    html.H3(f"{stats['after_score_filter']}", className="text-info"),
                    html.Small(f"{stats['after_score_filter']/stats['total_transactions']*100:.1f}% pass rate",
                               className="text-muted")
                ])
            ])
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("Avg Return (21d)", className="text-muted"),
                    html.H3(
                        f"{result_21d.avg_net_return:.2%}",
                        className="text-success" if result_21d.avg_net_return > 0 else "text-danger"
                    ),
                    html.Small(f"Win Rate: {result_21d.win_rate:.1%}", className="text-muted")
                ])
            ])
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("S&P 500 (21d)", className="text-muted"),
                    html.H3(
                        f"{result_21d.avg_spy_return:.2%}" if result_21d.avg_spy_return is not None else "N/A",
                        className="text-info"
                    )
                ])
            ])
        ], width=3),

        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H6("🎯 Alpha (21d)", className="text-muted"),
                    html.H3(
                        f"{alpha_value:+.2%}",
                        className=f"text-{alpha_color}"
                    )
                ])
            ])
        ], width=3),
    ], className="mb-4")


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

        # Loading spinner
        dcc.Loading(
            id="loading",
            type="default",
            children=[
                html.Div(id='summary-cards-container', children=[
                    dbc.Alert([
                        html.H4("👋 Welcome!", className="alert-heading"),
                        html.P("Adjust the parameters above and click 'Update Results' to see backtest performance."),
                        html.Hr(),
                        html.P([
                            html.Strong("Tip: "),
                            "Start with default settings, then experiment with lowering thresholds to see how it affects alpha."
                        ], className="mb-0")
                    ], color="info")
                ]),
                html.Div(id='performance-table-container'),
                html.Div(id='detailed-trades-container'),
                html.Div(id='equity-curve-container')
            ]
        )
    ], fluid=True)
])


@app.callback(
    [
        Output('backtest-results-store', 'data'),
        Output('stats-store', 'data'),
        Output('summary-cards-container', 'children'),
        Output('performance-table-container', 'children'),
        Output('detailed-trades-container', 'children'),
        Output('equity-curve-container', 'children')
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
    prevent_initial_call=True
)
def update_dashboard(n_clicks, min_trade_value, min_signal_score, min_market_cap_pct, exec_levels):
    """Update dashboard with new backtest results based on parameters."""

    # Apply filters and run backtest
    filtered_df, stats, results, metrics = apply_filters_and_backtest(
        all_transactions_df,
        min_trade_value,
        min_market_cap_pct,
        exec_levels or ['C-Suite'],
        min_signal_score
    )

    # Get 21-day results for summary
    result_21d = results.get(21)

    # Create components
    summary = create_summary_cards(stats, result_21d)
    summary_table = create_performance_table(results, metrics)
    detailed_table = create_detailed_trades_table(results)
    chart = dcc.Graph(figure=create_equity_curve(result_21d), config={'displayModeBar': True})

    # Store data (simplified - not storing full objects)
    results_data = {
        'has_results': result_21d is not None and result_21d.total_trades > 0
    }

    return results_data, stats, summary, summary_table, detailed_table, chart


def run_unified_dashboard(host='127.0.0.1', port=8052, debug=True):
    """Run the unified dashboard."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_unified_dashboard()
