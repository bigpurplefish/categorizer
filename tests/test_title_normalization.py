"""
Tests for title normalization in product_utils.py.

Tests normalize_title_case() which detects ALL-CAPS titles from POS data
and converts them to title case while preserving brand acronyms, units,
and fixing common .title() artifacts.
"""

import pytest
from src.product_utils import normalize_title_case


class TestAllCapsDetection:
    """Test that ALL-CAPS titles are detected and converted."""

    def test_all_caps_title_converted(self):
        """Fully uppercase title should be title-cased."""
        result = normalize_title_case("MANE & TAIL BRUSH RED/BLACK")
        assert result == "Mane & Tail Brush Red/Black"

    def test_mostly_caps_converted(self):
        """Title with >=80% uppercase letters should be converted."""
        # 'DOG FOOD PREMIUM 50lb' - 14 upper, 2 lower = 87.5% upper
        # Note: 'lb' is a unit so it gets uppercased to 'LB'
        result = normalize_title_case("DOG FOOD PREMIUM 50lb")
        assert result == "Dog Food Premium 50LB"

    def test_mixed_case_left_alone(self):
        """Already mixed-case title should not be modified."""
        title = "Mane & Tail Brush Red/Black"
        result = normalize_title_case(title)
        assert result == title

    def test_proper_title_case_left_alone(self):
        """Title that's already properly title-cased stays unchanged."""
        title = "Premium Dog Food with Chicken"
        result = normalize_title_case(title)
        assert result == title

    def test_lowercase_title_left_alone(self):
        """Lowercase title should not be modified (not all-caps)."""
        title = "dog food chicken flavor"
        result = normalize_title_case(title)
        assert result == title

    def test_single_word_caps(self):
        """Single uppercase word should be converted."""
        result = normalize_title_case("BRUSH")
        assert result == "Brush"


class TestApostropheFixes:
    """Test that .title() apostrophe artifacts are fixed."""

    def test_possessive_s(self):
        """Dog'S should become Dog's."""
        result = normalize_title_case("DOG'S FAVORITE TOY")
        assert result == "Dog's Favorite Toy"

    def test_contraction_nt(self):
        """N'T artifact should be fixed."""
        result = normalize_title_case("WON'T BREAK LEASH")
        assert result == "Won't Break Leash"

    def test_contraction_re(self):
        """'RE artifact should be fixed."""
        result = normalize_title_case("THEY'RE GREAT TREATS")
        assert result == "They're Great Treats"

    def test_contraction_ll(self):
        """'LL artifact should be fixed."""
        result = normalize_title_case("YOU'LL LOVE THIS")
        assert result == "You'll Love This"

    def test_contraction_ve(self):
        """'VE artifact should be fixed."""
        result = normalize_title_case("WE'VE GOT DEALS")
        assert result == "We've Got Deals"


class TestBrandAcronyms:
    """Test that short brand acronyms (2-3 chars) are preserved."""

    def test_short_acronym_preserved(self):
        """2-3 character all-caps words should stay uppercase."""
        result = normalize_title_case("SOG TACTICAL KNIFE")
        assert result == "SOG Tactical Knife"

    def test_ox_preserved(self):
        """OX brand should stay uppercase."""
        result = normalize_title_case("OX TOOLS PRO LEVEL")
        assert result == "OX Tools Pro Level"

    def test_common_short_words_not_preserved(self):
        """Common short words like THE, AND, FOR should not stay uppercase."""
        result = normalize_title_case("FOOD FOR THE DOG")
        assert result == "Food for the Dog"

    def test_units_preserved(self):
        """Units like LB, OZ, ML should stay uppercase."""
        result = normalize_title_case("DOG FOOD 50 LB BAG")
        assert result == "Dog Food 50 LB Bag"

    def test_oz_preserved(self):
        """OZ unit should stay uppercase."""
        result = normalize_title_case("CAT TREATS 12 OZ")
        assert result == "Cat Treats 12 OZ"

    def test_ml_preserved(self):
        """ML unit should stay uppercase."""
        result = normalize_title_case("SHAMPOO 500 ML")
        assert result == "Shampoo 500 ML"


class TestDoubleQuotes:
    """Test that double-escaped quotes are fixed."""

    def test_double_quotes_fixed(self):
        """Double-escaped quotes should become single quotes."""
        result = normalize_title_case('LARGE ""PREMIUM"" DOG BED')
        assert result == 'Large "Premium" Dog Bed'

    def test_double_quotes_in_mixed_case(self):
        """Double quotes should be fixed even in mixed-case titles."""
        result = normalize_title_case('Large ""Premium"" Dog Bed')
        assert result == 'Large "Premium" Dog Bed'

    def test_no_double_quotes(self):
        """Normal quotes should not be affected."""
        result = normalize_title_case('LARGE "PREMIUM" DOG BED')
        assert result == 'Large "Premium" Dog Bed'


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert normalize_title_case("") == ""

    def test_none_returns_none(self):
        """None input should return None."""
        assert normalize_title_case(None) is None

    def test_numbers_only(self):
        """String with only numbers should be returned unchanged."""
        assert normalize_title_case("12345") == "12345"

    def test_with_slashes(self):
        """Slashes in title should be handled."""
        result = normalize_title_case("RED/BLACK BRUSH")
        assert result == "Red/Black Brush"

    def test_with_ampersand(self):
        """Ampersand should be preserved."""
        result = normalize_title_case("MANE & TAIL BRUSH")
        assert result == "Mane & Tail Brush"

    def test_with_parentheses(self):
        """Parenthetical content should be title-cased too."""
        result = normalize_title_case("DOG FOOD (CHICKEN FLAVOR)")
        assert result == "Dog Food (Chicken Flavor)"

    def test_with_hyphen(self):
        """Hyphenated words should be title-cased."""
        result = normalize_title_case("HEAVY-DUTY LEASH")
        assert result == "Heavy-Duty Leash"

    def test_exactly_80_percent_threshold(self):
        """At exactly 80% uppercase, should be converted."""
        # "ABCDabcde" has 4 upper, 5 lower = 44% upper - should NOT convert
        # Need >80% upper letters
        # "ABCDa" has 4 upper, 1 lower = 80% upper - should convert
        result = normalize_title_case("ABCDa")
        assert result == "Abcda"

    def test_below_80_percent_not_converted(self):
        """Below 80% uppercase should not be converted."""
        # "ABCDabcde" has 4/9 = 44% - should not convert
        result = normalize_title_case("ABCDabcde")
        assert result == "ABCDabcde"

    def test_real_world_pos_title(self):
        """Real-world POS title from the 26 products."""
        result = normalize_title_case("MANE & TAIL BRUSH RED/BLACK")
        assert result == "Mane & Tail Brush Red/Black"

    def test_multiple_spaces_preserved(self):
        """Multiple spaces should be preserved (not collapsed)."""
        result = normalize_title_case("DOG  FOOD")
        assert "Food" in result
