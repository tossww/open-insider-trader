"""
Executive Position Classifier

Maps insider officer titles to executive weights for signal scoring.
Uses fuzzy matching to handle title variations.
"""

import yaml
from typing import Optional


class ExecutiveClassifier:
    """Classify executive positions and assign weights."""

    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize classifier with executive weights from config.

        Args:
            config_path: Path to configuration file
        """
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        self.executive_weights = config['executive_weights']
        self.default_weight = 0.3  # Default for unmatched titles

    def get_weight(self, officer_title: Optional[str]) -> float:
        """
        Get executive weight for a given officer title.

        Args:
            officer_title: The officer's title (e.g., "CEO", "Vice President")

        Returns:
            Weight between 0.0 and 1.0
            - 1.0 for CEO/CFO/President/Chairman
            - 0.5 for VPs
            - 0.3 for other officers
            - 0.0 for null/missing titles

        Logic:
            1. Return 0.0 if title is None or empty
            2. Try exact match (case-insensitive)
            3. Try fuzzy match (check if config title appears in officer title)
            4. If multiple matches, take max weight
            5. Default to 0.3 if no match
        """
        if not officer_title:
            return 0.0

        # Normalize title
        title_lower = officer_title.strip().lower()

        # Try exact match first (case-insensitive)
        for config_title, weight in self.executive_weights.items():
            if title_lower == config_title.lower():
                return weight

        # Try fuzzy match - check if any config title appears in the officer title
        matched_weights = []
        for config_title, weight in self.executive_weights.items():
            # Check both directions: config in title, or title in config
            if (config_title.lower() in title_lower or
                title_lower in config_title.lower()):
                matched_weights.append(weight)

        # If multiple matches, take max (e.g., "Executive Vice President" matches both "VP" and "EVP")
        if matched_weights:
            return max(matched_weights)

        # No match - return default weight
        return self.default_weight

    def classify(self, officer_title: Optional[str]) -> dict:
        """
        Classify an officer title with full details.

        Args:
            officer_title: The officer's title

        Returns:
            Dictionary with:
                - title: Original title
                - weight: Computed weight
                - tier: Classification tier (C-Suite, VP, Other, Unknown)
        """
        weight = self.get_weight(officer_title)

        # Determine tier
        if not officer_title:
            tier = 'Unknown'
        elif weight >= 1.0:
            tier = 'C-Suite'
        elif weight >= 0.5:
            tier = 'VP'
        elif weight > 0.0:
            tier = 'Other'
        else:
            tier = 'Unknown'

        return {
            'title': officer_title,
            'weight': weight,
            'tier': tier
        }


# Convenience function for quick weight lookup
def get_executive_weight(officer_title: Optional[str], config_path: str = 'config.yaml') -> float:
    """
    Quick function to get executive weight without creating classifier instance.

    Args:
        officer_title: The officer's title
        config_path: Path to configuration file

    Returns:
        Weight between 0.0 and 1.0
    """
    classifier = ExecutiveClassifier(config_path)
    return classifier.get_weight(officer_title)
