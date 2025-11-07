"""
Signal Scorer

Calculate composite scores for insider trading signals.
Combines: executive_weight × dollar_weight × cluster_weight × market_cap_weight
"""

import yaml
import math
from typing import List, Dict, Any


class SignalScorer:
    """Calculate composite scores for signals."""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize scorer with configuration.

        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Dollar weight config
        self.dollar_base = config['dollar_weight']['base_amount']
        self.dollar_log_multiplier = config['dollar_weight']['log_multiplier']

        # Market cap weight config
        self.market_cap_baseline_pct = config['market_cap_weight']['baseline_pct']
        self.market_cap_log_multiplier = config['market_cap_weight']['log_multiplier']
        self.market_cap_min_weight = config['market_cap_weight']['min_weight']
        self.market_cap_max_weight = config['market_cap_weight']['max_weight']

        # Scoring config
        self.min_signal_score = config['scoring']['min_signal_score']

    def calculate_dollar_weight(self, total_value: float) -> float:
        """
        Calculate dollar weight using logarithmic scaling.

        Formula: 1.0 + log_multiplier × log10(value / base_amount)

        Examples:
            $100K -> 1.0
            $200K -> 1.15
            $500K -> 1.35
            $1M -> 1.5
            $5M -> 1.85
            $10M -> 2.0

        Args:
            total_value: Trade value in USD

        Returns:
            Dollar weight (>= 1.0)
        """
        if total_value <= 0:
            return 1.0

        # Logarithmic scaling
        ratio = total_value / self.dollar_base
        if ratio <= 1.0:
            return 1.0

        weight = 1.0 + self.dollar_log_multiplier * math.log10(ratio)
        return weight

    def calculate_market_cap_weight(self, trade_pct_of_market_cap: float) -> float:
        """
        Calculate market cap weight using logarithmic scaling.

        Formula: 1.0 + log_multiplier × log10(trade_pct / baseline_pct)
        Clamped to [min_weight, max_weight]

        Examples:
            0.00001% -> 1.0 (baseline)
            0.0001% -> 1.5
            0.001% -> 2.0
            0.01% -> 2.5
            0.1%+ -> 3.0 (capped)

        Args:
            trade_pct_of_market_cap: Trade as % of market cap (decimal, e.g., 0.0001 = 0.01%)

        Returns:
            Market cap weight [min_weight, max_weight]
        """
        if trade_pct_of_market_cap is None or trade_pct_of_market_cap <= 0:
            # Default to baseline if no market cap data
            return 1.0

        # Logarithmic scaling
        ratio = trade_pct_of_market_cap / self.market_cap_baseline_pct
        if ratio <= 1.0:
            weight = self.market_cap_min_weight
        else:
            weight = 1.0 + self.market_cap_log_multiplier * math.log10(ratio)

        # Clamp to [min, max]
        weight = max(self.market_cap_min_weight, min(self.market_cap_max_weight, weight))
        return weight

    def calculate_composite_score(self, transaction: Dict[str, Any]) -> Dict[str, float]:
        """
        Calculate composite score for a transaction.

        Required fields in transaction:
            - executive_weight
            - total_value
            - cluster_weight
            - trade_pct_of_market_cap (optional)

        Returns:
            Dictionary with:
                - executive_weight
                - dollar_weight
                - cluster_weight
                - market_cap_weight
                - composite_score
                - is_actionable
        """
        # Get executive weight (already calculated)
        executive_weight = transaction.get('executive_weight', 0.3)

        # Calculate dollar weight
        total_value = transaction.get('total_value', 0)
        dollar_weight = self.calculate_dollar_weight(total_value)

        # Get cluster weight (already calculated)
        cluster_weight = transaction.get('cluster_weight', 1.0)

        # Calculate market cap weight
        trade_pct = transaction.get('trade_pct_of_market_cap')
        market_cap_weight = self.calculate_market_cap_weight(trade_pct)

        # Composite score: multiply all weights
        composite_score = (
            executive_weight *
            dollar_weight *
            cluster_weight *
            market_cap_weight
        )

        # Determine if actionable
        is_actionable = composite_score >= self.min_signal_score

        return {
            'executive_weight': executive_weight,
            'dollar_weight': dollar_weight,
            'cluster_weight': cluster_weight,
            'market_cap_weight': market_cap_weight,
            'composite_score': composite_score,
            'is_actionable': is_actionable
        }

    def score_signals(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score all transactions and add score fields.

        Args:
            transactions: List of transaction dictionaries

        Returns:
            Same transactions with added score fields
        """
        scored_transactions = []

        for txn in transactions:
            # Calculate score
            score_info = self.calculate_composite_score(txn)

            # Add score fields to transaction
            txn.update(score_info)

            scored_transactions.append(txn)

        # Sort by composite score (descending)
        scored_transactions.sort(key=lambda t: t['composite_score'], reverse=True)

        return scored_transactions

    def get_score_summary(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary statistics about scores.

        Args:
            transactions: List of scored transactions

        Returns:
            Dictionary with score statistics
        """
        if not transactions:
            return {
                'total_signals': 0,
                'actionable_signals': 0,
                'avg_score': 0,
                'max_score': 0,
                'min_score': 0
            }

        scores = [txn['composite_score'] for txn in transactions]
        actionable = [txn for txn in transactions if txn.get('is_actionable', False)]

        return {
            'total_signals': len(transactions),
            'actionable_signals': len(actionable),
            'avg_score': sum(scores) / len(scores),
            'max_score': max(scores),
            'min_score': min(scores)
        }


# Convenience function
def score_signals(
    transactions: List[Dict[str, Any]],
    config_path: str = 'config.yaml'
) -> List[Dict[str, Any]]:
    """
    Quick function to score signals without creating scorer instance.

    Args:
        transactions: List of transaction dictionaries
        config_path: Path to configuration file

    Returns:
        Scored transactions sorted by composite score
    """
    scorer = SignalScorer(config_path)
    return scorer.score_signals(transactions)
