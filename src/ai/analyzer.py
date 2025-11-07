"""
AI-powered analysis of backtesting results using Anthropic Claude.

Provides BUY/NO BUY recommendations based on strategy performance,
risk metrics, and statistical significance.
"""

import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from anthropic import Anthropic
from dotenv import load_dotenv

from backtesting.metrics import RiskMetrics


# Load environment variables
load_dotenv()


@dataclass
class AIRecommendation:
    """AI analysis recommendation output."""

    recommendation: str  # BUY, NO BUY, or CAUTIOUS
    rationale: List[str]  # Key findings
    risk_factors: List[str]  # Risk considerations
    confidence: str  # High, Medium, or Low
    raw_response: str  # Full AI response


class BacktestAnalyzer:
    """Analyze backtesting results using Claude Sonnet."""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize analyzer with Anthropic API key.

        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-20250514"  # Sonnet 4.5

    def _build_analysis_prompt(
        self,
        strategy_metrics: RiskMetrics,
        benchmark_metrics: RiskMetrics,
        alpha: float,
        holding_days: int,
        total_signals: int,
        period_label: str
    ) -> str:
        """
        Build the analysis prompt for Claude.

        Args:
            strategy_metrics: Performance metrics for the insider trading strategy
            benchmark_metrics: Performance metrics for S&P 500
            alpha: Strategy return minus benchmark return
            holding_days: Holding period in days
            total_signals: Total number of signals tested
            period_label: Human-readable period label (e.g., "21 days")

        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a quantitative analyst evaluating a backtesting strategy that follows insider trading signals from C-level executives.

**Strategy Overview:**
- Signal criteria: C-level executive purchases of $100K+ in clustered trades (2+ executives within 7 days)
- Holding period: {period_label} ({holding_days} trading days)
- Sample size: {total_signals} signals tested
- Transaction costs: 0.6% round-trip (realistic retail trading costs)

**Strategy Performance:**
- Average Return: {strategy_metrics.avg_return:.2%}
- Total Return: {strategy_metrics.total_return:.2%}
- Sharpe Ratio: {strategy_metrics.sharpe_ratio:.2f}
- Max Drawdown: {strategy_metrics.max_drawdown:.2%}
- Calmar Ratio: {strategy_metrics.calmar_ratio:.2f}
- Win Rate: {strategy_metrics.win_rate:.1%}
- Profit Factor: {f"{strategy_metrics.profit_factor:.2f}" if strategy_metrics.profit_factor is not None else "N/A"}

**S&P 500 Benchmark:**
- Average Return: {benchmark_metrics.avg_return:.2%}
- Sharpe Ratio: {benchmark_metrics.sharpe_ratio:.2f}
- Max Drawdown: {benchmark_metrics.max_drawdown:.2%}

**Alpha (Excess Return):**
{alpha:+.2%} vs S&P 500

**Your Task:**
Provide a clear, actionable recommendation for whether a retail trader should use this strategy.

Respond in exactly this format:

RECOMMENDATION: [BUY / NO BUY / CAUTIOUS]

RATIONALE:
- [Key finding 1]
- [Key finding 2]
- [Key finding 3]

RISK FACTORS:
- [Risk 1]
- [Risk 2]

CONFIDENCE: [High / Medium / Low]

**Guidelines:**
1. BUY = Strategy shows statistically significant alpha with acceptable risk
2. NO BUY = Strategy underperforms or has excessive risk
3. CAUTIOUS = Strategy shows promise but has concerns (sample size, drawdown, etc.)
4. Be objective and data-driven
5. Consider transaction costs are already factored in
6. Sample size of {total_signals} trades - is this sufficient for statistical significance?
7. Consider risk-adjusted returns (Sharpe/Calmar), not just raw returns
"""
        return prompt

    def analyze(
        self,
        strategy_metrics: RiskMetrics,
        benchmark_metrics: RiskMetrics,
        alpha: float,
        holding_days: int,
        total_signals: int,
        period_label: str = None
    ) -> AIRecommendation:
        """
        Analyze backtesting results and generate recommendation.

        Args:
            strategy_metrics: Strategy performance metrics
            benchmark_metrics: Benchmark performance metrics
            alpha: Excess return vs benchmark
            holding_days: Holding period in days
            total_signals: Number of signals tested
            period_label: Human-readable period (e.g., "3 weeks")

        Returns:
            AIRecommendation with BUY/NO BUY/CAUTIOUS and detailed rationale
        """
        if period_label is None:
            period_label = f"{holding_days} days"

        prompt = self._build_analysis_prompt(
            strategy_metrics,
            benchmark_metrics,
            alpha,
            holding_days,
            total_signals,
            period_label
        )

        # Call Claude API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.3,  # Lower temperature for more consistent analysis
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        # Extract text from response
        raw_response = response.content[0].text

        # Parse response into structured format
        return self._parse_response(raw_response)

    def _parse_response(self, response: str) -> AIRecommendation:
        """
        Parse Claude's response into structured AIRecommendation.

        Args:
            response: Raw response text from Claude

        Returns:
            Parsed AIRecommendation
        """
        lines = response.strip().split('\n')

        recommendation = "CAUTIOUS"  # Default
        rationale = []
        risk_factors = []
        confidence = "Medium"  # Default

        current_section = None

        for line in lines:
            line = line.strip()

            if line.startswith('RECOMMENDATION:'):
                recommendation = line.split(':', 1)[1].strip()
            elif line.startswith('CONFIDENCE:'):
                confidence = line.split(':', 1)[1].strip()
            elif line.startswith('RATIONALE:'):
                current_section = 'rationale'
            elif line.startswith('RISK FACTORS:'):
                current_section = 'risk_factors'
            elif line.startswith('-') and current_section:
                # Extract bullet point content
                content = line.lstrip('-').strip()
                if content:
                    if current_section == 'rationale':
                        rationale.append(content)
                    elif current_section == 'risk_factors':
                        risk_factors.append(content)

        return AIRecommendation(
            recommendation=recommendation,
            rationale=rationale,
            risk_factors=risk_factors,
            confidence=confidence,
            raw_response=response
        )

    def analyze_multi_period(
        self,
        results: Dict[int, tuple[RiskMetrics, RiskMetrics, float]],
        total_signals: int
    ) -> Dict[int, AIRecommendation]:
        """
        Analyze multiple holding periods and generate recommendations for each.

        Args:
            results: Dict mapping holding_days to (strategy_metrics, benchmark_metrics, alpha)
            total_signals: Total number of signals tested

        Returns:
            Dict mapping holding_days to AIRecommendation
        """
        recommendations = {}

        for holding_days, (strat_metrics, bench_metrics, alpha) in results.items():
            period_label = self._format_period_label(holding_days)

            recommendation = self.analyze(
                strategy_metrics=strat_metrics,
                benchmark_metrics=bench_metrics,
                alpha=alpha,
                holding_days=holding_days,
                total_signals=total_signals,
                period_label=period_label
            )

            recommendations[holding_days] = recommendation

        return recommendations

    @staticmethod
    def _format_period_label(days: int) -> str:
        """Convert days to human-readable label."""
        if days == 1:
            return "1 day"
        elif days <= 5:
            return f"{days} days"
        elif days <= 10:
            return f"{days} days (~{days // 5} week{'s' if days >= 10 else ''})"
        elif days <= 30:
            return f"{days} days (~{days // 7} weeks)"
        elif days <= 90:
            return f"{days} days (~{days // 30} month{'s' if days >= 60 else ''})"
        elif days <= 365:
            return f"{days} days (~{days // 30} months)"
        else:
            years = days // 365
            return f"{days} days (~{years} year{'s' if years > 1 else ''})"
