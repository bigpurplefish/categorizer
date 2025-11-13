"""
Tests for src/utils.py

Tests image counting, variant detection, and lifestyle image prompt generation.
"""

import pytest
from src.utils import (
    count_images_per_variant,
    get_variants_needing_images,
    build_gemini_lifestyle_prompt_for_variant
)


class TestCountImagesPerVariant:
    """Test count_images_per_variant function."""

    def test_single_variant_multiple_images(self):
        """Test counting images for a single variant with multiple images."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50_LB": 3}

    def test_multiple_variants(self):
        """Test counting images for multiple variants."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #25_LB"},
                {"alt": "Test Product #25_LB"},
                {"alt": "Test Product #25_LB"},
                {"alt": "Test Product #10_LB"},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50_LB": 2, "25_LB": 3, "10_LB": 1}

    def test_no_images(self):
        """Test product with no images."""
        product = {"title": "Test Product", "images": []}
        counts = count_images_per_variant(product)
        assert counts == {}

    def test_missing_images_key(self):
        """Test product without images key."""
        product = {"title": "Test Product"}
        counts = count_images_per_variant(product)
        assert counts == {}

    def test_images_without_alt_text(self):
        """Test images without alt text are skipped."""
        product = {
            "title": "Test Product",
            "images": [
                {"src": "http://example.com/image1.jpg"},
                {"alt": ""},
                {"alt": "Test Product #50_LB"},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50_LB": 1}

    def test_alt_text_without_hash(self):
        """Test alt text without # symbol is skipped."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product"},
                {"alt": "Test Product #50_LB"},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50_LB": 1}

    def test_variant_id_with_spaces(self):
        """Test variant ID extraction with spaces after #."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product # 50 LB "},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50 LB": 1}

    def test_variant_id_with_special_characters(self):
        """Test variant ID with special characters."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB#BG"},
                {"alt": "Test Product #50_LB#BG"},
            ]
        }
        counts = count_images_per_variant(product)
        assert counts == {"50_LB#BG": 2}


class TestGetVariantsNeedingImages:
    """Test get_variants_needing_images function."""

    def test_variant_needs_images(self):
        """Test identifying variant that needs images."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
            ],
            "variants": [
                {"option1": "50 LB", "sku": "123"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)

        assert "50_LB" in result
        assert result["50_LB"]["existing_count"] == 1
        assert result["50_LB"]["images_needed"] == 4
        assert result["50_LB"]["variant_option_value"] == "50 LB"

    def test_variant_has_enough_images(self):
        """Test variant with enough images is not included."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
            ],
            "variants": [
                {"option1": "50 LB", "sku": "123"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)
        assert result == {}

    def test_variant_has_more_than_target(self):
        """Test variant with more than target images is not included."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
            ],
            "variants": [
                {"option1": "50 LB", "sku": "123"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)
        assert result == {}

    def test_multiple_variants_mixed(self):
        """Test multiple variants where some need images and some don't."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #25_LB"},
            ],
            "variants": [
                {"option1": "50 LB", "sku": "123"},
                {"option1": "25 LB", "sku": "124"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)

        assert "50_LB" not in result
        assert "25_LB" in result
        assert result["25_LB"]["images_needed"] == 4

    def test_variant_with_no_images(self):
        """Test variant with zero images."""
        product = {
            "title": "Test Product",
            "images": [],
            "variants": [
                {"option1": "50 LB", "sku": "123"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)

        assert "50_LB" in result
        assert result["50_LB"]["existing_count"] == 0
        assert result["50_LB"]["images_needed"] == 5

    def test_product_without_variants(self):
        """Test product without variants key."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
            ]
        }
        result = get_variants_needing_images(product, target_image_count=5)
        assert result == {}

    def test_product_with_empty_variants(self):
        """Test product with empty variants array."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
            ],
            "variants": []
        }
        result = get_variants_needing_images(product, target_image_count=5)
        assert result == {}

    def test_custom_target_image_count(self):
        """Test with custom target image count."""
        product = {
            "title": "Test Product",
            "images": [
                {"alt": "Test Product #50_LB"},
                {"alt": "Test Product #50_LB"},
            ],
            "variants": [
                {"option1": "50 LB", "sku": "123"}
            ]
        }
        result = get_variants_needing_images(product, target_image_count=3)

        assert "50_LB" in result
        assert result["50_LB"]["images_needed"] == 1

    def test_variant_data_included(self):
        """Test that full variant data is included in result."""
        variant = {"option1": "50 LB", "sku": "123", "price": "10.99"}
        product = {
            "title": "Test Product",
            "images": [{"alt": "Test Product #50_LB"}],
            "variants": [variant]
        }
        result = get_variants_needing_images(product, target_image_count=5)

        assert result["50_LB"]["variant_data"] == variant


class TestBuildGeminiLifestylePromptForVariant:
    """Test build_gemini_lifestyle_prompt_for_variant function."""

    def test_basic_prompt_generation(self):
        """Test basic prompt generation with all fields."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert "Test Product" in prompt
        assert "50 LB" in prompt
        assert "3 unique, photorealistic lifestyle product images" in prompt
        assert "Pet Supplies > Dogs > Dog Food" in prompt

    def test_prompt_contains_required_sections(self):
        """Test that prompt contains all required sections."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=2,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        # Check for all major sections
        assert "Product Details:" in prompt
        assert "Photorealism:" in prompt
        assert "Lifestyle Context:" in prompt
        assert "Subject Demographics" in prompt
        assert "Uniqueness and Storytelling:" in prompt
        assert "Technical Specifications:" in prompt
        assert "Important Guidelines:" in prompt

    def test_prompt_contains_location(self):
        """Test that prompt mentions Newfield, NJ location."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert "Newfield, NJ 08009" in prompt

    def test_prompt_contains_technical_specs(self):
        """Test that prompt contains technical specifications."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert "2048x2048 pixels" in prompt
        assert "Square (1:1)" in prompt

    def test_prompt_with_empty_subcategory(self):
        """Test prompt generation when subcategory is empty."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory=""
        )

        assert "Pet Supplies > Dogs" in prompt
        assert len(prompt) > 0

    def test_prompt_with_single_image_needed(self):
        """Test prompt when only 1 image is needed."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=1,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert "Generate 1 unique, photorealistic lifestyle product images" in prompt

    def test_prompt_with_many_images_needed(self):
        """Test prompt when many images are needed."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=10,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert "Generate 10 unique, photorealistic lifestyle product images" in prompt
        assert "each of the 10 images" in prompt.lower()

    def test_prompt_with_html_description(self):
        """Test that HTML description is included properly."""
        html_desc = "<p>This is a <strong>bold</strong> description with <em>emphasis</em>.</p>"
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description=html_desc,
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        assert html_desc in prompt

    def test_prompt_with_special_characters_in_title(self):
        """Test prompt with special characters in product title."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Purina® Amplify® High-Fat Horse Supplement",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Livestock and Farm",
            category="Horses",
            subcategory="Feed"
        )

        assert "Purina® Amplify® High-Fat Horse Supplement" in prompt
        assert "Livestock and Farm > Horses > Feed" in prompt

    def test_prompt_length_reasonable(self):
        """Test that prompt length is reasonable (not too short or too long)."""
        prompt = build_gemini_lifestyle_prompt_for_variant(
            product_title="Test Product",
            product_description="<p>Test description</p>",
            variant_option_value="50 LB",
            images_needed=3,
            department="Pet Supplies",
            category="Dogs",
            subcategory="Dog Food"
        )

        # Prompt should be comprehensive but not excessive
        assert len(prompt) > 1000  # At least 1000 chars for comprehensive instructions
        assert len(prompt) < 5000  # But not overly verbose
