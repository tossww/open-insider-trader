"""
Signal Generator Pipeline

Orchestrates the full signal generation pipeline:
    1. Load transactions from database
    2. Apply filters (purchases, $100K+, executive, market cap %)
    3. Detect clusters (7-day window, same company)
    4. Calculate scores (exec × dollar × cluster × market_cap)
    5. Rank and return top signals
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.processors.signal_filters import SignalFilters
from src.processors.cluster_detector import ClusterDetector
from src.processors.signal_scorer import SignalScorer


@dataclass
class SignalReport:
    """Report containing signal generation results."""

    # Signals
    signals: List[Dict[str, Any]] = field(default_factory=list)

    # Statistics
    filter_stats: Dict[str, Any] = field(default_factory=dict)
    cluster_stats: Dict[str, Any] = field(default_factory=dict)
    score_stats: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    generated_at: datetime = field(default_factory=datetime.utcnow)
    config_path: str = 'config.yaml'

    @property
    def total_signals(self) -> int:
        """Total number of signals."""
        return len(self.signals)

    @property
    def actionable_signals(self) -> int:
        """Number of actionable signals."""
        return sum(1 for s in self.signals if s.get('is_actionable', False))

    def top_signals(self, n: int = 10) -> List[Dict[str, Any]]:
        """
        Get top N signals by score.

        Args:
            n: Number of signals to return

        Returns:
            List of top N signals
        """
        return self.signals[:n]

    def actionable_only(self) -> List[Dict[str, Any]]:
        """
        Get only actionable signals.

        Returns:
            List of actionable signals
        """
        return [s for s in self.signals if s.get('is_actionable', False)]


class SignalGenerator:
    """Generate high-conviction insider trading signals."""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize signal generator.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path
        self.filters = SignalFilters(config_path)
        self.detector = ClusterDetector(config_path)
        self.scorer = SignalScorer(config_path)

    def generate(self) -> SignalReport:
        """
        Run the full signal generation pipeline.

        Steps:
            1. Load and filter transactions
            2. Detect clusters
            3. Calculate scores
            4. Generate report

        Returns:
            SignalReport with ranked signals and statistics
        """
        # Step 1: Filter transactions
        filtered, filter_stats = self.filters.filter_transactions()

        # Step 2: Detect clusters
        clustered = self.detector.detect_clusters(filtered)
        cluster_stats = self.detector.get_cluster_summary(clustered)

        # Step 3: Score signals
        scored = self.scorer.score_signals(clustered)
        score_stats = self.scorer.get_score_summary(scored)

        # Step 4: Create report
        report = SignalReport(
            signals=scored,
            filter_stats=filter_stats,
            cluster_stats=cluster_stats,
            score_stats=score_stats,
            config_path=self.config_path
        )

        return report

    def generate_and_filter(
        self,
        min_score: Optional[float] = None,
        top_n: Optional[int] = None,
        actionable_only: bool = False
    ) -> SignalReport:
        """
        Generate signals with additional filtering.

        Args:
            min_score: Minimum composite score (overrides config)
            top_n: Return only top N signals
            actionable_only: Return only actionable signals

        Returns:
            SignalReport with filtered signals
        """
        # Generate full report
        report = self.generate()

        # Apply additional filters
        filtered_signals = report.signals

        if min_score is not None:
            filtered_signals = [s for s in filtered_signals if s['composite_score'] >= min_score]

        if actionable_only:
            filtered_signals = [s for s in filtered_signals if s.get('is_actionable', False)]

        if top_n is not None:
            filtered_signals = filtered_signals[:top_n]

        # Update report with filtered signals
        report.signals = filtered_signals

        return report


# Convenience function
def generate_signals(config_path: str = 'config.yaml') -> SignalReport:
    """
    Quick function to generate signals without creating generator instance.

    Args:
        config_path: Path to configuration file

    Returns:
        SignalReport with ranked signals
    """
    generator = SignalGenerator(config_path)
    return generator.generate()
