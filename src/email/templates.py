"""
HTML email templates for alerts.
"""

from datetime import datetime
from typing import Optional


def render_alert_email(
    ticker: str,
    company_name: str,
    insider_name: str,
    insider_title: Optional[str],
    trade_value: float,
    trade_date: datetime,
    signal_score: int,
    conviction_score: int,
    track_record_score: int,
    conviction_reasons: list,
    track_record_reasons: list,
    deep_dive_url: str
) -> tuple[str, str]:
    """
    Render HTML and plain text email for strong buy signal.

    Args:
        ticker: Stock ticker
        company_name: Company name
        insider_name: Insider's name
        insider_title: Insider's title
        trade_value: Trade value in dollars
        trade_date: Trade date
        signal_score: Total signal score
        conviction_score: Conviction score (0-3)
        track_record_score: Track record score (0-5)
        conviction_reasons: List of conviction factors
        track_record_reasons: List of track record factors
        deep_dive_url: URL to company deep dive

    Returns:
        tuple: (html_content, plain_text_content)
    """

    # Format trade value
    value_str = f"${trade_value:,.0f}" if trade_value >= 1_000_000 else f"${trade_value/1000:.0f}K"

    # Build HTML email
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">

    <!-- Header -->
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 24px;">🔥 STRONG BUY SIGNAL</h1>
        <p style="margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">High-Conviction Insider Purchase Detected</p>
    </div>

    <!-- Main Content -->
    <div style="background: white; padding: 30px; border: 1px solid #e5e7eb; border-top: none; border-radius: 0 0 10px 10px;">

        <!-- Company Info -->
        <div style="margin-bottom: 25px;">
            <h2 style="margin: 0 0 10px 0; font-size: 28px; color: #1f2937;">
                ${ticker} - {company_name}
            </h2>
            <p style="margin: 0; color: #6b7280; font-size: 14px;">
                {trade_date.strftime('%B %d, %Y')}
            </p>
        </div>

        <!-- Insider Info -->
        <div style="background: #f9fafb; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
            <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #374151;">Insider</h3>
            <p style="margin: 0 0 5px 0; font-size: 18px; font-weight: 600; color: #1f2937;">
                {insider_name}
            </p>
            <p style="margin: 0; color: #6b7280; font-size: 14px;">
                {insider_title or 'Executive'}
            </p>
        </div>

        <!-- Trade Details -->
        <div style="background: #ecfdf5; border-left: 4px solid #10b981; padding: 20px; border-radius: 8px; margin-bottom: 25px;">
            <h3 style="margin: 0 0 10px 0; font-size: 16px; color: #065f46;">Trade Value</h3>
            <p style="margin: 0; font-size: 32px; font-weight: bold; color: #059669;">
                {value_str}
            </p>
        </div>

        <!-- Signal Score -->
        <div style="margin-bottom: 25px;">
            <h3 style="margin: 0 0 15px 0; font-size: 16px; color: #374151;">Signal Score: {signal_score}/8</h3>
            <div style="background: #e5e7eb; height: 12px; border-radius: 6px; overflow: hidden;">
                <div style="background: linear-gradient(90deg, #10b981 0%, #059669 100%); height: 100%; width: {(signal_score/8)*100}%; border-radius: 6px;"></div>
            </div>
        </div>

        <!-- Why This Matters -->
        <div style="margin-bottom: 25px;">
            <h3 style="margin: 0 0 15px 0; font-size: 18px; color: #1f2937;">Why This Matters</h3>

            <!-- Conviction Factors -->
            <div style="margin-bottom: 15px;">
                <p style="margin: 0 0 8px 0; font-weight: 600; color: #4b5563; font-size: 14px;">
                    🎯 Conviction ({conviction_score}/3 points):
                </p>
                <ul style="margin: 0; padding-left: 20px; color: #6b7280; font-size: 14px;">
                    {''.join(f'<li>{reason}</li>' for reason in conviction_reasons)}
                </ul>
            </div>

            <!-- Track Record -->
            <div>
                <p style="margin: 0 0 8px 0; font-weight: 600; color: #4b5563; font-size: 14px;">
                    📊 Track Record ({track_record_score}/5 points):
                </p>
                <ul style="margin: 0; padding-left: 20px; color: #6b7280; font-size: 14px;">
                    {''.join(f'<li>{reason}</li>' for reason in track_record_reasons)}
                </ul>
            </div>
        </div>

        <!-- CTA Button -->
        <div style="text-align: center; margin: 30px 0;">
            <a href="{deep_dive_url}" style="display: inline-block; background: #2563eb; color: white; text-decoration: none; padding: 14px 32px; border-radius: 8px; font-weight: 600; font-size: 16px;">
                View Full Analysis →
            </a>
        </div>

        <!-- Footer -->
        <div style="border-top: 1px solid #e5e7eb; padding-top: 20px; margin-top: 30px; text-align: center;">
            <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px;">
                Open Insider Trader
            </p>
            <p style="margin: 0; color: #9ca3af; font-size: 11px;">
                This is not financial advice. Do your own research before making investment decisions.
            </p>
        </div>
    </div>

</body>
</html>
"""

    # Plain text version
    plain = f"""
[STRONG BUY] ${ticker} - High-Conviction Insider Purchase

Insider: {insider_name} ({insider_title or 'Executive'})
Trade Value: {value_str}
Signal Score: {signal_score}/8

Why this matters:
- Conviction ({conviction_score}/3): {', '.join(conviction_reasons)}
- Track Record ({track_record_score}/5): {', '.join(track_record_reasons)}

View Details: {deep_dive_url}

---
Open Insider Trader
This is not financial advice. Do your own research.
"""

    return (html, plain)
