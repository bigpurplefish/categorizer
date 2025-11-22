"""
Tests for src/product_utils.py - Product formatting and validation utilities
"""

import pytest
import json
from src.product_utils import (
    format_purchase_options_metafield,
    add_metafield_if_not_exists,
    reorder_product_fields,
    should_calculate_shipping_weight,
    is_non_shipped_category,
    remove_weight_data_from_variants,
    PURCHASE_OPTION_LABELS
)


class TestFormatPurchaseOptionsMetafield:
    """Test purchase options formatting"""

    def test_format_single_option(self):
        """Test formatting single purchase option"""
        result = format_purchase_options_metafield([1])
        expected = json.dumps({"1": "Delivery (standard shipping)"})
        assert result == expected

    def test_format_multiple_options(self):
        """Test formatting multiple purchase options"""
        result = format_purchase_options_metafield([1, 2, 3])
        parsed = json.loads(result)
        assert "1" in parsed
        assert "2" in parsed
        assert "3" in parsed
        assert parsed["1"] == "Delivery (standard shipping)"
        assert parsed["2"] == "Store Pickup"
        assert parsed["3"] == "Local Delivery (within service area)"

    def test_format_pickup_only(self):
        """Test formatting customer pickup only"""
        result = format_purchase_options_metafield([5])
        expected = json.dumps({"5": "Customer Pickup Only (bulk items)"})
        assert result == expected


class TestAddMetafieldIfNotExists:
    """Test metafield addition with duplicate detection"""

    def test_add_new_metafield(self):
        """Test adding a new metafield"""
        product = {}
        added = add_metafield_if_not_exists(product, 'custom', 'test_key', 'test_value', 'single_line_text_field')

        assert added is True
        assert 'metafields' in product
        assert len(product['metafields']) == 1
        assert product['metafields'][0]['key'] == 'test_key'
        assert product['metafields'][0]['value'] == 'test_value'

    def test_skip_duplicate_metafield(self):
        """Test skipping duplicate metafield"""
        product = {
            'metafields': [
                {'namespace': 'custom', 'key': 'existing_key', 'value': 'value1', 'type': 'single_line_text_field'}
            ]
        }

        added = add_metafield_if_not_exists(product, 'custom', 'existing_key', 'value2', 'single_line_text_field')

        assert added is False
        assert len(product['metafields']) == 1
        assert product['metafields'][0]['value'] == 'value1'  # Original value unchanged

    def test_add_different_namespace(self):
        """Test adding metafield with different namespace"""
        product = {
            'metafields': [
                {'namespace': 'custom', 'key': 'test_key', 'value': 'value1', 'type': 'single_line_text_field'}
            ]
        }

        added = add_metafield_if_not_exists(product, 'other', 'test_key', 'value2', 'single_line_text_field')

        assert added is True
        assert len(product['metafields']) == 2


class TestReorderProductFields:
    """Test product field reordering"""

    def test_reorder_basic_product(self):
        """Test reordering product with basic fields"""
        product = {
            'images': [],
            'tags': ['tag1'],
            'title': 'Test Product',
            'variants': [],
            'descriptionHtml': '<p>Test</p>',
            'product_type': 'Pet Supplies',
            'vendor': 'Test Vendor',
            'status': 'ACTIVE'
        }

        reordered = reorder_product_fields(product)
        keys = list(reordered.keys())

        # Check single-value fields come first
        assert keys.index('title') < keys.index('tags')
        assert keys.index('descriptionHtml') < keys.index('tags')
        assert keys.index('vendor') < keys.index('tags')
        assert keys.index('status') < keys.index('tags')
        assert keys.index('product_type') < keys.index('tags')

        # Check array field order
        assert keys.index('tags') < keys.index('variants')
        assert keys.index('variants') < keys.index('images')

    def test_reorder_with_all_fields(self):
        """Test reordering product with all fields"""
        product = {
            'media': [],
            'images': [],
            'variants': [],
            'metafields': [],
            'options': [],
            'tags': [],
            'shopify_category_id': 'gid://shopify/TaxonomyCategory/123',
            'product_type': 'Pet Supplies',
            'status': 'ACTIVE',
            'vendor': 'Test Vendor',
            'descriptionHtml': '<p>Test</p>',
            'title': 'Test Product'
        }

        reordered = reorder_product_fields(product)
        keys = list(reordered.keys())

        expected_order = [
            'title', 'descriptionHtml', 'vendor', 'status', 'product_type', 'shopify_category_id',
            'tags', 'options', 'metafields', 'variants', 'images', 'media'
        ]

        assert keys == expected_order


class TestShouldCalculateShippingWeight:
    """Test shipping weight calculation determination"""

    def test_shipped_product(self):
        """Test product with delivery option"""
        assert should_calculate_shipping_weight([1, 2, 3]) is True

    def test_pickup_only_product(self):
        """Test product with only pickup option"""
        assert should_calculate_shipping_weight([5]) is False

    def test_no_delivery_option(self):
        """Test product without delivery option"""
        assert should_calculate_shipping_weight([2, 3, 4]) is False


class TestIsNonShippedCategory:
    """Test non-shipped category detection"""

    def test_aggregates_not_shipped(self):
        """Test that Aggregates are not shipped"""
        assert is_non_shipped_category("Landscape and Construction", "Aggregates") is True

    def test_pavers_not_shipped(self):
        """Test that Pavers and Hardscaping are not shipped"""
        assert is_non_shipped_category("Landscape and Construction", "Pavers and Hardscaping") is True

    def test_other_categories_shipped(self):
        """Test that other categories can be shipped"""
        assert is_non_shipped_category("Pet Supplies", "Dogs") is False
        assert is_non_shipped_category("Lawn and Garden", "Garden Tools") is False


class TestRemoveWeightDataFromVariants:
    """Test weight_data removal from variants"""

    def test_remove_weight_data(self):
        """Test removing weight_data from all variants"""
        product = {
            'variants': [
                {
                    'sku': '123',
                    'weight': 10.0,
                    'weight_data': {
                        'original_weight': 10.0,
                        'final_shipping_weight': 12.0
                    }
                },
                {
                    'sku': '456',
                    'weight': 20.0,
                    'weight_data': {
                        'original_weight': 20.0,
                        'final_shipping_weight': 24.0
                    }
                }
            ]
        }

        result = remove_weight_data_from_variants(product)

        for variant in result['variants']:
            assert 'weight_data' not in variant
            assert 'weight' in variant  # Weight field should remain

    def test_no_variants(self):
        """Test product with no variants"""
        product = {}
        result = remove_weight_data_from_variants(product)
        assert result == {}

    def test_variants_without_weight_data(self):
        """Test variants without weight_data"""
        product = {
            'variants': [
                {'sku': '123', 'weight': 10.0}
            ]
        }
        result = remove_weight_data_from_variants(product)
        assert len(result['variants']) == 1
        assert result['variants'][0]['sku'] == '123'
