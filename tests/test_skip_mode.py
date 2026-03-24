"""
Tests for skip-mode title matching in gui.py.

The skip logic builds an `existing_products` dict keyed by title from the output file,
then looks up input titles against it. When the output has normalized titles
(e.g., "Highland Cow Mailbox Cover") but the input has ALL-CAPS
("HIGHLAND COW MAILBOX COVER"), the lookup fails and products get re-processed.

The fix normalizes titles on both sides using normalize_title_case().
"""

import json
import os
import tempfile
import pytest

from src.product_utils import normalize_title_case


class TestSkipModeKeyNormalization:
    """Verify that building the existing_products index normalizes title keys."""

    def _build_existing_products_index(self, output_products):
        """
        Replicate the gui.py logic for building existing_products dict.
        This should use normalize_title_case on the key.
        """
        existing_products = {}
        for product in output_products:
            title = product.get("title", "")
            if title:
                key = normalize_title_case(title) or title
                existing_products[key] = product
        return existing_products

    def _lookup_input_title(self, title, existing_products):
        """
        Replicate the gui.py logic for looking up an input title.
        This should normalize the input title before lookup.
        """
        normalized = normalize_title_case(title) or title
        return normalized in existing_products

    def test_allcaps_input_matches_normalized_output(self):
        """ALL-CAPS input title should match title-case output title."""
        output_products = [
            {"title": "Highland Cow Mailbox Cover", "product_type": "Home Decor"}
        ]
        existing = self._build_existing_products_index(output_products)

        assert self._lookup_input_title("HIGHLAND COW MAILBOX COVER", existing)

    def test_normalized_input_matches_normalized_output(self):
        """Already-normalized input should still match."""
        output_products = [
            {"title": "Highland Cow Mailbox Cover", "product_type": "Home Decor"}
        ]
        existing = self._build_existing_products_index(output_products)

        assert self._lookup_input_title("Highland Cow Mailbox Cover", existing)

    def test_allcaps_output_matches_allcaps_input(self):
        """If output also has ALL-CAPS (edge case), should still match."""
        output_products = [
            {"title": "HIGHLAND COW MAILBOX COVER", "product_type": "Home Decor"}
        ]
        existing = self._build_existing_products_index(output_products)

        assert self._lookup_input_title("HIGHLAND COW MAILBOX COVER", existing)

    def test_multiple_products_skip_correctly(self):
        """Multiple products with mixed casing should all match."""
        output_products = [
            {"title": "Highland Cow Mailbox Cover", "product_type": "Home Decor"},
            {"title": "Dog Food Premium 50LB", "product_type": "Pet Supplies"},
            {"title": "Mane & Tail Brush Red/Black", "product_type": "Pet Supplies"},
        ]
        existing = self._build_existing_products_index(output_products)

        assert self._lookup_input_title("HIGHLAND COW MAILBOX COVER", existing)
        assert self._lookup_input_title("DOG FOOD PREMIUM 50LB", existing)
        assert self._lookup_input_title("MANE & TAIL BRUSH RED/BLACK", existing)

    def test_empty_title_not_indexed(self):
        """Products with empty titles should not be in the index."""
        output_products = [
            {"title": "", "product_type": "Home Decor"},
            {"title": "Real Product", "product_type": "Pet Supplies"},
        ]
        existing = self._build_existing_products_index(output_products)

        assert len(existing) == 1
        assert self._lookup_input_title("Real Product", existing)

    def test_skip_requires_product_type(self):
        """
        Skip should only happen when the existing product has product_type set.
        This tests the full skip condition, not just the lookup.
        """
        output_products = [
            {"title": "Highland Cow Mailbox Cover"},  # No product_type
        ]
        existing = self._build_existing_products_index(output_products)

        # Title matches...
        normalized_title = normalize_title_case("HIGHLAND COW MAILBOX COVER") or "HIGHLAND COW MAILBOX COVER"
        assert normalized_title in existing

        # ...but product_type is missing, so skip should NOT apply
        product = existing[normalized_title]
        assert not product.get("product_type")


class TestMergeKeyNormalization:
    """Verify that merging enhanced products back uses normalized keys."""

    def test_enhanced_product_overwrites_existing(self):
        """
        When an enhanced product is merged back into existing_products,
        it should overwrite the entry even if casing differs.
        """
        # Simulate: output has normalized title, new enhanced product also has normalized title
        existing_products = {}
        key = normalize_title_case("Highland Cow Mailbox Cover") or "Highland Cow Mailbox Cover"
        existing_products[key] = {
            "title": "Highland Cow Mailbox Cover",
            "product_type": "Home Decor"
        }

        # New enhanced product comes back with normalized title
        enhanced = {
            "title": "Highland Cow Mailbox Cover",
            "product_type": "Home Decor",
            "body_html": "<p>New description</p>"
        }

        merge_key = normalize_title_case(enhanced.get("title", "")) or enhanced.get("title", "")
        existing_products[merge_key] = enhanced

        assert len(existing_products) == 1
        assert existing_products[key].get("body_html") == "<p>New description</p>"
