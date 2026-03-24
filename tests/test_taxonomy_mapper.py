"""
Tests for taxonomy_mapper module.

Focuses on GID validation and lookup_shopify_category behavior.
"""

import pytest
import json
import os
import re
from unittest.mock import patch, MagicMock

from src.taxonomy_mapper import (
    lookup_shopify_category,
    is_valid_shopify_gid,
    load_mapping_cache,
    save_mapping_cache,
)


# ============================================================================
# GID VALIDATION TESTS
# ============================================================================

class TestIsValidShopifyGid:
    """Tests for the is_valid_shopify_gid helper function."""

    def test_valid_gid_simple(self):
        """Valid GID with simple ID like 'ap'."""
        assert is_valid_shopify_gid("gid://shopify/TaxonomyCategory/ap") is True

    def test_valid_gid_nested(self):
        """Valid GID with nested ID like 'ap-2-3-7'."""
        assert is_valid_shopify_gid("gid://shopify/TaxonomyCategory/ap-2-3-7") is True

    def test_valid_gid_two_level(self):
        """Valid GID with two-level ID like 'ha-1'."""
        assert is_valid_shopify_gid("gid://shopify/TaxonomyCategory/ha-1") is True

    def test_placeholder_gid_rejected(self):
        """Placeholder GID 'gid://shopify/123' must be rejected."""
        assert is_valid_shopify_gid("gid://shopify/123") is False

    def test_none_rejected(self):
        """None value must be rejected."""
        assert is_valid_shopify_gid(None) is False

    def test_empty_string_rejected(self):
        """Empty string must be rejected."""
        assert is_valid_shopify_gid("") is False

    def test_string_none_rejected(self):
        """String 'None' must be rejected."""
        assert is_valid_shopify_gid("None") is False

    def test_missing_prefix(self):
        """GID without gid://shopify/TaxonomyCategory/ prefix is invalid."""
        assert is_valid_shopify_gid("ap-2-3-7") is False

    def test_wrong_type_prefix(self):
        """GID with wrong Shopify type is invalid."""
        assert is_valid_shopify_gid("gid://shopify/Product/12345") is False

    def test_empty_after_prefix(self):
        """GID with nothing after TaxonomyCategory/ is invalid."""
        assert is_valid_shopify_gid("gid://shopify/TaxonomyCategory/") is False


# ============================================================================
# LOOKUP SHOPIFY CATEGORY TESTS
# ============================================================================

class TestLookupShopifyCategory:
    """Tests for lookup_shopify_category function."""

    def test_full_path_lookup(self):
        """Lookup by full Department > Category > Subcategory path."""
        mappings = {
            "Pet Supplies > Dogs > Food": {
                "shopify_id": "gid://shopify/TaxonomyCategory/ap-2-3-3",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Food"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "Food", mappings)
        assert result is not None
        assert result["shopify_id"] == "gid://shopify/TaxonomyCategory/ap-2-3-3"

    def test_category_fallback(self):
        """Falls back to Department > Category when subcategory not found."""
        mappings = {
            "Pet Supplies > Dogs": {
                "shopify_id": "gid://shopify/TaxonomyCategory/ap-2-3",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies > Dog Supplies"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "UnknownSub", mappings)
        assert result is not None
        assert result["shopify_id"] == "gid://shopify/TaxonomyCategory/ap-2-3"

    def test_department_fallback(self):
        """Falls back to just Department when category not found."""
        mappings = {
            "Pet Supplies": {
                "shopify_id": "gid://shopify/TaxonomyCategory/ap-2",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Unknown", "Unknown", mappings)
        assert result is not None
        assert result["shopify_id"] == "gid://shopify/TaxonomyCategory/ap-2"

    def test_no_mapping_found(self):
        """Returns None when no mapping exists."""
        result = lookup_shopify_category("Nonexistent", "Cat", "Sub", {})
        assert result is None

    def test_placeholder_gid_rejected(self):
        """Placeholder GID gid://shopify/123 must be rejected at lookup time."""
        mappings = {
            "Pet Supplies > Dogs > Food": {
                "shopify_id": "gid://shopify/123",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies > Dog Supplies"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "Food", mappings)
        assert result is None

    def test_placeholder_gid_skipped_falls_to_next_level(self):
        """When full path has invalid GID, falls back to category level."""
        mappings = {
            "Pet Supplies > Dogs > Food": {
                "shopify_id": "gid://shopify/123",
                "shopify_category": "Bad mapping"
            },
            "Pet Supplies > Dogs": {
                "shopify_id": "gid://shopify/TaxonomyCategory/ap-2-3",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies > Dog Supplies"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "Food", mappings)
        assert result is not None
        assert result["shopify_id"] == "gid://shopify/TaxonomyCategory/ap-2-3"

    def test_all_levels_invalid_returns_none(self):
        """When all levels have invalid GIDs, returns None."""
        mappings = {
            "Pet Supplies > Dogs > Food": {
                "shopify_id": "gid://shopify/123",
                "shopify_category": "Bad"
            },
            "Pet Supplies > Dogs": {
                "shopify_id": "gid://shopify/456",
                "shopify_category": "Bad"
            },
            "Pet Supplies": {
                "shopify_id": "gid://shopify/789",
                "shopify_category": "Bad"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "Food", mappings)
        assert result is None

    def test_empty_subcategory(self):
        """When subcategory is empty, skips full path lookup."""
        mappings = {
            "Pet Supplies > Dogs": {
                "shopify_id": "gid://shopify/TaxonomyCategory/ap-2-3",
                "shopify_category": "Animals & Pet Supplies > Pet Supplies > Dog Supplies"
            }
        }
        result = lookup_shopify_category("Pet Supplies", "Dogs", "", mappings)
        assert result is not None
        assert result["shopify_id"] == "gid://shopify/TaxonomyCategory/ap-2-3"
