"""
Cluster Detector

Groups insider transactions by company and time window to detect
coordinated buying (multiple executives buying within N days).
"""

import yaml
from typing import List, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict


class ClusterDetector:
    """Detect clusters of insider buying activity."""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize cluster detector with configuration.

        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.cluster_window_days = config['filtering']['cluster_window_days']
        self.cluster_weights = config['cluster_weights']

    def detect_clusters(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect clusters and assign cluster weights.

        Clustering logic:
            1. Group by company (ticker)
            2. Within each company, group by filing_date window (N days)
            3. Count unique insiders per cluster
            4. Assign cluster_weight based on count

        Args:
            transactions: List of filtered transaction dictionaries

        Returns:
            Same transactions with added fields:
                - cluster_id: Unique cluster identifier (ticker_YYYYMMDD)
                - cluster_size: Number of unique insiders in cluster
                - cluster_weight: Weight from config based on cluster size
        """
        if not transactions:
            return transactions

        # Sort by company and filing date
        sorted_txns = sorted(
            transactions,
            key=lambda t: (t['ticker'], t['filing_date'])
        )

        # Group into clusters
        clusters = []
        current_cluster = []
        current_ticker = None
        current_window_start = None

        for txn in sorted_txns:
            ticker = txn['ticker']
            filing_date = txn['filing_date']

            # Convert filing_date to datetime if it's a string
            if isinstance(filing_date, str):
                filing_date = datetime.fromisoformat(filing_date.replace('Z', '+00:00'))

            # Start new cluster if:
            # 1. Different company
            # 2. Filing date is outside window
            if (current_ticker is None or
                ticker != current_ticker or
                filing_date > current_window_start + timedelta(days=self.cluster_window_days)):

                # Save previous cluster
                if current_cluster:
                    clusters.append(current_cluster)

                # Start new cluster
                current_cluster = [txn]
                current_ticker = ticker
                current_window_start = filing_date
            else:
                # Add to current cluster
                current_cluster.append(txn)

        # Don't forget last cluster
        if current_cluster:
            clusters.append(current_cluster)

        # Assign cluster IDs and weights
        enriched_transactions = []

        for cluster in clusters:
            # Unique insiders in this cluster
            unique_insiders = set(txn['insider_name'] for txn in cluster)
            cluster_size = len(unique_insiders)

            # Cluster weight from config
            if cluster_size >= 5:
                cluster_weight = self.cluster_weights[5]
            else:
                cluster_weight = self.cluster_weights.get(cluster_size, 1.0)

            # Cluster ID: ticker_YYYYMMDD (using earliest filing date)
            earliest_date = min(
                txn['filing_date'] if isinstance(txn['filing_date'], datetime)
                else datetime.fromisoformat(txn['filing_date'].replace('Z', '+00:00'))
                for txn in cluster
            )
            cluster_id = f"{cluster[0]['ticker']}_{earliest_date.strftime('%Y%m%d')}"

            # Add cluster info to each transaction
            for txn in cluster:
                txn['cluster_id'] = cluster_id
                txn['cluster_size'] = cluster_size
                txn['cluster_weight'] = cluster_weight
                enriched_transactions.append(txn)

        return enriched_transactions

    def get_cluster_summary(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Get summary statistics about clusters.

        Args:
            transactions: List of transactions with cluster info

        Returns:
            Dictionary with cluster statistics
        """
        if not transactions:
            return {
                'total_clusters': 0,
                'total_transactions': 0,
                'avg_cluster_size': 0,
                'max_cluster_size': 0,
                'solo_transactions': 0,
                'clustered_transactions': 0
            }

        # Count unique clusters
        unique_clusters = set(txn['cluster_id'] for txn in transactions if 'cluster_id' in txn)

        # Count cluster sizes
        cluster_sizes = [txn.get('cluster_size', 1) for txn in transactions]
        solo_count = sum(1 for size in cluster_sizes if size == 1)
        clustered_count = sum(1 for size in cluster_sizes if size > 1)

        return {
            'total_clusters': len(unique_clusters),
            'total_transactions': len(transactions),
            'avg_cluster_size': sum(cluster_sizes) / len(cluster_sizes) if cluster_sizes else 0,
            'max_cluster_size': max(cluster_sizes) if cluster_sizes else 0,
            'solo_transactions': solo_count,
            'clustered_transactions': clustered_count
        }


# Convenience function
def detect_clusters(
    transactions: List[Dict[str, Any]],
    config_path: str = 'config.yaml'
) -> List[Dict[str, Any]]:
    """
    Quick function to detect clusters without creating detector instance.

    Args:
        transactions: List of filtered transaction dictionaries
        config_path: Path to configuration file

    Returns:
        Transactions with cluster info added
    """
    detector = ClusterDetector(config_path)
    return detector.detect_clusters(transactions)
