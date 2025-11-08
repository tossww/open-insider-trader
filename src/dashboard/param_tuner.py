"""
Interactive Parameter Testing Dashboard for Open InsiderTrader.

Allows users to:
- Adjust filtering parameters with sliders
- Toggle executive level filters
- Preview signal count and top signals in real-time
- Export results to CSV
- Launch backtest with selected parameters
"""

import sys
from pathlib import Path
from datetime import datetime
import sqlite3
import json

import dash
from dash import dcc, html, dash_table, ctx
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from src.processors.signal_filters import SignalFilters
from src.processors.cluster_detector import ClusterDetector
from src.processors.signal_scorer import SignalScorer
from src.processors.executive_classifier import ExecutiveClassifier
import yaml


# Load default config
with open('config.yaml', 'r') as f:
    DEFAULT_CONFIG = yaml.safe_load(f)


def load_all_transactions(db_path: str = 'data/insider_trades.db'):
    """
    Load all transactions from database for filtering.

    Returns:
        DataFrame with all transactions and metadata
    """
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
        WHERE it.transaction_code = 'P'  -- Only direct purchases (exclude option exercises)
        ORDER BY it.filing_date DESC
    """

    df = pd.read_sql_query(query, conn)
    conn.close()

    return df


def apply_filters(df, min_trade_value, min_market_cap_pct, exec_levels, min_signal_score):
    """
    Apply filters to transaction dataframe.

    Args:
        df: Transaction dataframe
        min_trade_value: Minimum dollar value
        min_market_cap_pct: Minimum trade as % of market cap
        exec_levels: List of executive levels to include ('C-Suite', 'VP', 'All')
        min_signal_score: Minimum composite score

    Returns:
        Tuple of (filtered_df, stats_dict)
    """
    stats = {
        'total_transactions': len(df),
        'after_dollar_filter': 0,
        'after_exec_filter': 0,
        'after_market_cap_filter': 0,
        'after_score_filter': 0
    }

    # Initialize executive classifier
    classifier = ExecutiveClassifier('config.yaml')

    # Step 1: Dollar value filter
    # Fill NaN total_value with 0 to avoid filtering them out when min=0
    df_filtered = df.copy()
    df_filtered['total_value'] = df_filtered['total_value'].fillna(0)
    df_filtered = df_filtered[df_filtered['total_value'] >= min_trade_value].copy()
    stats['after_dollar_filter'] = len(df_filtered)

    # Step 2: Executive level filter
    df_filtered['exec_weight'] = df_filtered['officer_title'].apply(
        lambda x: classifier.get_weight(x)
    )

    # Check if "Include All Executives" is selected
    if 'All' in exec_levels:
        # Keep ALL transactions, no executive filtering
        pass
    elif 'C-Suite' in exec_levels and 'VP' not in exec_levels:
        # Only C-Suite (weight = 1.0)
        df_filtered = df_filtered[df_filtered['exec_weight'] == 1.0]
    elif 'VP' in exec_levels and 'C-Suite' not in exec_levels:
        # Only VP (weight = 0.5)
        df_filtered = df_filtered[df_filtered['exec_weight'] == 0.5]
    elif 'C-Suite' in exec_levels and 'VP' in exec_levels:
        # C-Suite + VP (weight >= 0.5)
        df_filtered = df_filtered[df_filtered['exec_weight'] >= 0.5]
    else:
        # No checkboxes selected - default to keeping all
        pass

    stats['after_exec_filter'] = len(df_filtered)

    # Step 3: Market cap % filter
    if min_market_cap_pct > 0:
        df_filtered['market_cap_pct'] = (
            df_filtered['total_value'] / df_filtered['market_cap_usd']
        )
        df_filtered = df_filtered[
            (df_filtered['market_cap_pct'] >= min_market_cap_pct) |
            (df_filtered['market_cap_usd'].isna())
        ]

    stats['after_market_cap_filter'] = len(df_filtered)

    # Step 4: Calculate composite scores
    # For simplicity, we'll calculate a basic score here
    # (In production, this would use the full SignalScorer)

    # Dollar weight (log scale) - handle zero/low values
    base_amount = 100000
    # Clip dollar_weight to minimum 0.0 to prevent negative scores
    df_filtered['dollar_weight'] = np.maximum(
        0.0,
        1 + 0.5 * np.log10(np.clip(df_filtered['total_value'], 1, None) / base_amount)
    )

    # Market cap weight
    if min_market_cap_pct > 0 and 'market_cap_pct' in df_filtered.columns:
        baseline_pct = 0.00001
        df_filtered['market_cap_weight'] = np.clip(
            1 + 0.5 * np.log10(df_filtered['market_cap_pct'] / baseline_pct),
            0.5,
            3.0
        )
    else:
        df_filtered['market_cap_weight'] = 1.0

    # Composite score (simplified - no clustering yet)
    df_filtered['composite_score'] = (
        df_filtered['exec_weight'] *
        df_filtered['dollar_weight'] *
        df_filtered['market_cap_weight']
    )

    # Fill any NaN scores with 0
    df_filtered['composite_score'] = df_filtered['composite_score'].fillna(0)

    # Step 5: Score filter
    df_filtered = df_filtered[df_filtered['composite_score'] >= min_signal_score]
    stats['after_score_filter'] = len(df_filtered)

    # Sort by score
    df_filtered = df_filtered.sort_values('composite_score', ascending=False)

    return df_filtered, stats


# Initialize app
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.DARKLY],
    title="Parameter Tuner - Open InsiderTrader"
)

# Load initial data
all_transactions_df = load_all_transactions()


# Layout components
def create_header():
    """Create dashboard header."""
    return dbc.Container([
        html.H1("🎛️ Parameter Tuning Dashboard", className="text-center mt-4 mb-2"),
        html.H4("Test Filter Settings Before Backtesting", className="text-center text-muted mb-4"),
        html.Hr()
    ], fluid=True)


def create_controls():
    """Create parameter control panel."""
    return dbc.Container([
        html.H4("⚙️ Filter Parameters", className="mb-4"),

        dbc.Row([
            # Left column: Sliders
            dbc.Col([
                # Min Trade Value Slider
                html.Div([
                    html.Label("Minimum Trade Value", className="fw-bold mb-2"),
                    dcc.Slider(
                        id='min-trade-value-slider',
                        min=0,
                        max=500000,
                        step=10000,
                        value=DEFAULT_CONFIG['filtering']['min_trade_value'],
                        marks={
                            0: '$0',
                            50000: '$50K',
                            100000: '$100K',
                            250000: '$250K',
                            500000: '$500K'
                        },
                        tooltip={"placement": "bottom", "always_visible": True}
                    ),
                    html.Div(id='min-trade-value-display', className="text-muted mt-2")
                ], className="mb-4"),

                # Min Signal Score Slider
                html.Div([
                    html.Label("Minimum Signal Score", className="fw-bold mb-2"),
                    dcc.Slider(
                        id='min-signal-score-slider',
                        min=0,
                        max=5.0,
                        step=0.1,
                        value=DEFAULT_CONFIG['scoring']['min_signal_score'],
                        marks={
                            0: '0',
                            1.0: '1.0',
                            2.0: '2.0',
                            3.0: '3.0',
                            5.0: '5.0'
                        },
                        tooltip={"placement": "bottom", "always_visible": True}
                    ),
                    html.Div(id='min-signal-score-display', className="text-muted mt-2")
                ], className="mb-4"),

                # Min Market Cap % Slider
                html.Div([
                    html.Label("Minimum Trade as % of Market Cap", className="fw-bold mb-2"),
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
                    html.Div(id='min-market-cap-pct-display', className="text-muted mt-2")
                ], className="mb-4"),
            ], width=8),

            # Right column: Checkboxes
            dbc.Col([
                html.Label("Executive Levels", className="fw-bold mb-3"),
                dbc.Checklist(
                    id='exec-level-checklist',
                    options=[
                        {'label': ' C-Suite Only (CEO, CFO, President, Chairman)', 'value': 'C-Suite'},
                        {'label': ' Include VPs (EVP, SVP, VP)', 'value': 'VP'},
                        {'label': ' Include All Executives', 'value': 'All'}
                    ],
                    value=['C-Suite'],  # Default to C-Suite only
                    className="mb-3"
                ),

                html.Hr(className="my-4"),

                # Action buttons
                html.Div([
                    dbc.Button(
                        "🔄 Refresh Signals",
                        id='refresh-button',
                        color="primary",
                        className="me-2 mb-2",
                        size="lg"
                    ),
                    dbc.Button(
                        "📥 Export CSV",
                        id='export-button',
                        color="success",
                        className="me-2 mb-2",
                        size="lg"
                    ),
                    dbc.Button(
                        "🚀 Run Backtest",
                        id='backtest-button',
                        color="warning",
                        className="mb-2",
                        size="lg"
                    ),
                ], className="d-grid gap-2")
            ], width=4)
        ])
    ], fluid=True, className="mb-4")


def create_funnel_chart(stats):
    """
    Create funnel chart showing filtering stages.

    Args:
        stats: Dictionary with filtering statistics

    Returns:
        Plotly figure
    """
    # Funnel data
    stages = [
        'Total Transactions',
        f'≥ ${stats.get("min_trade_value", 0):,.0f}',
        'Executive Filter',
        'Market Cap %',
        'Min Score'
    ]

    values = [
        stats.get('total_transactions', 0),
        stats.get('after_dollar_filter', 0),
        stats.get('after_exec_filter', 0),
        stats.get('after_market_cap_filter', 0),
        stats.get('after_score_filter', 0)
    ]

    # Calculate percentages
    percentages = []
    if values[0] > 0:
        percentages = [f"{(v/values[0]*100):.1f}%" for v in values]
    else:
        percentages = ['0%'] * len(values)

    # Create funnel
    fig = go.Figure(go.Funnel(
        y=stages,
        x=values,
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(
            color=['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        ),
        connector={"line": {"color": "white", "width": 2}}
    ))

    fig.update_layout(
        title="Signal Filtering Funnel",
        plot_bgcolor='#1e1e1e',
        paper_bgcolor='#1e1e1e',
        font={'color': 'white'},
        height=400
    )

    return fig


# App layout
app.layout = html.Div([
    create_header(),
    create_controls(),

    # Hidden div to store filter stats
    dcc.Store(id='filter-stats-store'),
    dcc.Store(id='filtered-signals-store'),

    # Signal count cards
    dbc.Container([
        html.H4("📊 Signal Preview", className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Total Transactions", className="text-muted"),
                        html.H3(id='total-transactions-card', className="text-info")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("After Filters", className="text-muted"),
                        html.H3(id='after-filters-card', className="text-success")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Pass Rate", className="text-muted"),
                        html.H3(id='pass-rate-card', className="text-warning")
                    ])
                ])
            ], width=3),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Status", className="text-muted"),
                        html.H3("✅ Ready", id='status-card', className="text-success")
                    ])
                ])
            ], width=3),
        ], className="mb-4")
    ], fluid=True),

    # Funnel chart
    dbc.Container([
        dcc.Graph(id='funnel-chart')
    ], fluid=True, className="mb-4"),

    # Top signals table
    dbc.Container([
        html.H4("🎯 Top Signals Preview", className="mb-3"),
        html.Div(id='top-signals-table')
    ], fluid=True, className="mb-4"),

    # Download component (hidden)
    dcc.Download(id="download-csv")
])


# Callbacks
@app.callback(
    [
        Output('filter-stats-store', 'data'),
        Output('filtered-signals-store', 'data'),
        Output('total-transactions-card', 'children'),
        Output('after-filters-card', 'children'),
        Output('pass-rate-card', 'children'),
        Output('funnel-chart', 'figure'),
        Output('top-signals-table', 'children')
    ],
    [
        Input('refresh-button', 'n_clicks'),
        Input('min-trade-value-slider', 'value'),
        Input('min-signal-score-slider', 'value'),
        Input('min-market-cap-pct-slider', 'value'),
        Input('exec-level-checklist', 'value')
    ],
    prevent_initial_call=False
)
def update_signals(n_clicks, min_trade_value, min_signal_score, min_market_cap_pct, exec_levels):
    """Update signal preview based on parameter changes."""

    # Apply filters
    filtered_df, stats = apply_filters(
        all_transactions_df,
        min_trade_value,
        min_market_cap_pct,
        exec_levels or [],
        min_signal_score
    )

    # Store stats for later use
    stats['min_trade_value'] = min_trade_value

    # Calculate pass rate
    pass_rate = 0
    if stats['total_transactions'] > 0:
        pass_rate = (stats['after_score_filter'] / stats['total_transactions']) * 100

    # Create funnel chart
    funnel_fig = create_funnel_chart(stats)

    # Create top signals table
    top_n = 20
    table_data = []

    for idx, row in filtered_df.head(top_n).iterrows():
        table_data.append({
            'Ticker': row['ticker'],
            'Insider': row['insider_name'],
            'Title': row['officer_title'] or 'Unknown',
            'Filing Date': row['filing_date'],
            'Trade Value': f"${row['total_value']:,.0f}",
            'Score': f"{row['composite_score']:.2f}",
            'Exec Weight': f"{row['exec_weight']:.1f}"
        })

    if table_data:
        table = dash_table.DataTable(
            data=table_data,
            columns=[{'name': col, 'id': col} for col in table_data[0].keys()],
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
            }
        )
    else:
        table = html.Div("No signals match the current filters", className="text-center text-muted")

    # Convert filtered_df to JSON for storage
    filtered_signals_json = filtered_df.to_json(date_format='iso', orient='split')

    return (
        stats,
        filtered_signals_json,
        f"{stats['total_transactions']:,}",
        f"{stats['after_score_filter']:,}",
        f"{pass_rate:.1f}%",
        funnel_fig,
        table
    )


@app.callback(
    Output('download-csv', 'data'),
    Input('export-button', 'n_clicks'),
    State('filtered-signals-store', 'data'),
    prevent_initial_call=True
)
def export_csv(n_clicks, filtered_signals_json):
    """Export filtered signals to CSV."""
    if not filtered_signals_json:
        return None

    # Load filtered signals from JSON
    filtered_df = pd.read_json(filtered_signals_json, orient='split')

    # Select columns for export
    export_cols = [
        'ticker', 'insider_name', 'officer_title', 'filing_date', 'trade_date',
        'total_value', 'composite_score', 'exec_weight', 'dollar_weight', 'market_cap_weight'
    ]

    export_df = filtered_df[export_cols]

    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'insider_signals_{timestamp}.csv'

    return dcc.send_data_frame(export_df.to_csv, filename, index=False)


@app.callback(
    Output('status-card', 'children'),
    Input('backtest-button', 'n_clicks'),
    [
        State('min-trade-value-slider', 'value'),
        State('min-signal-score-slider', 'value'),
        State('min-market-cap-pct-slider', 'value'),
        State('exec-level-checklist', 'value'),
        State('filter-stats-store', 'data')
    ],
    prevent_initial_call=True
)
def run_backtest(n_clicks, min_trade_value, min_signal_score, min_market_cap_pct, exec_levels, stats):
    """Save parameters and provide backtest instructions."""
    # Save current parameters to a temp config file
    import tempfile
    import shutil

    # Load current config
    with open('config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Update with new parameters
    config['filtering']['min_trade_value'] = int(min_trade_value)
    config['filtering']['min_market_cap_pct'] = float(min_market_cap_pct)
    config['scoring']['min_signal_score'] = float(min_signal_score)

    # Save to temp config
    temp_config_path = 'config_tuned.yaml'
    with open(temp_config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False)

    print("\n" + "="*80)
    print("📋 BACKTEST INSTRUCTIONS")
    print("="*80)
    print(f"✅ Saved tuned parameters to: {temp_config_path}")
    print(f"\n📊 Current Settings:")
    print(f"   Min Trade Value: ${min_trade_value:,}")
    print(f"   Min Signal Score: {min_signal_score}")
    print(f"   Min Market Cap %: {min_market_cap_pct}")
    print(f"   Executive Levels: {', '.join(exec_levels) if exec_levels else 'None'}")
    print(f"\n🎯 Signals Captured: {stats.get('after_score_filter', 0)}")
    print("\n🚀 To run backtest with these parameters:")
    print("   1. Copy config_tuned.yaml to config.yaml")
    print("   2. Run: python3 scripts/generate_signals.py --store-db")
    print("   3. Run: python3 scripts/run_backtest.py")
    print("   4. Run: python3 scripts/run_dashboard.py")
    print("="*80 + "\n")

    return "✅ Ready"


def run_param_tuner(host='127.0.0.1', port=8051, debug=True):
    """Run the parameter tuning dashboard."""
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_param_tuner()
