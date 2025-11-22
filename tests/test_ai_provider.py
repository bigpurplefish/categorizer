"""
Tests for src/ai_provider.py

Tests AI provider abstraction layer that routes requests to Claude or OpenAI.
"""

import pytest
import json
import os
from unittest.mock import Mock, patch, mock_open, MagicMock
from src.ai_provider import (
    load_cache,
    save_cache,
    compute_product_hash,
    load_markdown_file,
    enhance_product,
    generate_collection_description,
    batch_enhance_products,
    CACHE_FILE
)


class TestLoadCache:
    """Test load_cache function."""

    def test_load_cache_file_not_exists(self):
        """Test loading cache when file doesn't exist."""
        with patch('os.path.exists', return_value=False):
            cache = load_cache()
            assert cache == {"cache_version": "1.0", "products": {}}

    def test_load_cache_valid_file(self, tmp_path):
        """Test loading valid cache file."""
        cache_data = {
            "cache_version": "1.0",
            "products": {
                "product1": {"department": "Pet Supplies"}
            }
        }
        cache_file = tmp_path / "test_cache.json"
        cache_file.write_text(json.dumps(cache_data))

        with patch('src.ai_provider.CACHE_FILE', str(cache_file)):
            with patch('os.path.exists', return_value=True):
                cache = load_cache()
                assert cache == cache_data

    def test_load_cache_corrupted_json(self, tmp_path):
        """Test loading corrupted JSON returns empty cache."""
        cache_file = tmp_path / "test_cache.json"
        cache_file.write_text("{ invalid json")

        with patch('src.ai_provider.CACHE_FILE', str(cache_file)):
            with patch('os.path.exists', return_value=True):
                cache = load_cache()
                assert cache == {"cache_version": "1.0", "products": {}}

    def test_load_cache_io_error(self):
        """Test loading cache when file read fails."""
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', side_effect=IOError("Read error")):
                cache = load_cache()
                assert cache == {"cache_version": "1.0", "products": {}}


class TestSaveCache:
    """Test save_cache function."""

    def test_save_cache_success(self, tmp_path):
        """Test saving cache successfully."""
        cache_data = {
            "cache_version": "1.0",
            "products": {"product1": {"department": "Pet Supplies"}}
        }
        cache_file = tmp_path / "test_cache.json"

        with patch('src.ai_provider.CACHE_FILE', str(cache_file)):
            save_cache(cache_data)

            # Verify file was created and contents are correct
            assert cache_file.exists()
            loaded = json.loads(cache_file.read_text())
            assert loaded == cache_data

    def test_save_cache_io_error(self):
        """Test saving cache when write fails."""
        cache_data = {"cache_version": "1.0", "products": {}}

        with patch('builtins.open', side_effect=IOError("Write error")):
            # Should not raise, just log error
            save_cache(cache_data)


class TestComputeProductHash:
    """Test compute_product_hash function."""

    def test_compute_hash_basic(self):
        """Test basic hash computation."""
        product = {"title": "Test Product", "body_html": "<p>Description</p>"}
        hash1 = compute_product_hash(product)

        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA256 hex length

    def test_compute_hash_consistent(self):
        """Test that same product produces same hash."""
        product = {"title": "Test Product", "body_html": "<p>Description</p>"}
        hash1 = compute_product_hash(product)
        hash2 = compute_product_hash(product)

        assert hash1 == hash2

    def test_compute_hash_different_products(self):
        """Test that different products produce different hashes."""
        product1 = {"title": "Product 1", "body_html": "<p>Description 1</p>"}
        product2 = {"title": "Product 2", "body_html": "<p>Description 2</p>"}

        hash1 = compute_product_hash(product1)
        hash2 = compute_product_hash(product2)

        assert hash1 != hash2

    def test_compute_hash_missing_fields(self):
        """Test hash computation with missing fields."""
        product = {}
        hash_result = compute_product_hash(product)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64

    def test_compute_hash_with_unicode(self):
        """Test hash computation with unicode characters."""
        product = {"title": "Test® Product™", "body_html": "<p>Description™</p>"}
        hash_result = compute_product_hash(product)

        assert isinstance(hash_result, str)
        assert len(hash_result) == 64


class TestLoadMarkdownFile:
    """Test load_markdown_file function."""

    def test_load_markdown_success(self, tmp_path):
        """Test loading markdown file successfully."""
        content = "# Test Document\n\nThis is a test."
        file_path = tmp_path / "test.md"
        file_path.write_text(content)

        result = load_markdown_file(str(file_path))
        assert result == content

    def test_load_markdown_file_not_found(self):
        """Test loading non-existent file returns empty string."""
        result = load_markdown_file("/nonexistent/file.md")
        assert result == ""

    def test_load_markdown_io_error(self):
        """Test loading file with IO error returns empty string."""
        with patch('builtins.open', side_effect=IOError("Read error")):
            result = load_markdown_file("test.md")
            assert result == ""

    def test_load_markdown_with_encoding(self, tmp_path):
        """Test loading markdown with UTF-8 encoding."""
        content = "# Test® Document™\n\n© Copyright"
        file_path = tmp_path / "test.md"
        file_path.write_text(content, encoding='utf-8')

        result = load_markdown_file(str(file_path))
        assert result == content


class TestEnhanceProduct:
    """Test enhance_product function."""

    @patch('src.ai_provider.claude_api')
    def test_enhance_with_claude(self, mock_claude_api):
        """Test enhancing product with Claude provider."""
        product = {"title": "Test Product"}
        taxonomy_doc = "# Taxonomy"
        voice_tone_doc = "# Voice"
        cfg = {
            "AI_PROVIDER": "claude",
            "CLAUDE_API_KEY": "test-key",
            "CLAUDE_MODEL": "claude-sonnet-4-5-20250929"
        }

        mock_claude_api.enhance_product_with_claude.return_value = {
            **product,
            "product_type": "Pet Supplies",
            "tags": ["Dogs", "Food"]
        }

        result = enhance_product(product, taxonomy_doc, voice_tone_doc, cfg)

        mock_claude_api.enhance_product_with_claude.assert_called_once()
        assert result["product_type"] == "Pet Supplies"

    @patch('src.ai_provider.openai_api')
    def test_enhance_with_openai(self, mock_openai_api):
        """Test enhancing product with OpenAI provider."""
        product = {"title": "Test Product"}
        taxonomy_doc = "# Taxonomy"
        voice_tone_doc = "# Voice"
        cfg = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-5"
        }

        mock_openai_api.enhance_product_with_openai.return_value = {
            **product,
            "product_type": "Pet Supplies",
            "tags": ["Dogs", "Food"]
        }

        result = enhance_product(product, taxonomy_doc, voice_tone_doc, cfg)

        mock_openai_api.enhance_product_with_openai.assert_called_once()
        assert result["product_type"] == "Pet Supplies"

    def test_enhance_missing_api_key_claude(self):
        """Test error when Claude API key is missing."""
        product = {"title": "Test Product"}
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": ""}

        with pytest.raises(ValueError, match="Claude API key not configured"):
            enhance_product(product, "", "", cfg)

    def test_enhance_missing_api_key_openai(self):
        """Test error when OpenAI API key is missing."""
        product = {"title": "Test Product"}
        cfg = {"AI_PROVIDER": "openai", "OPENAI_API_KEY": ""}

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            enhance_product(product, "", "", cfg)

    def test_enhance_unknown_provider(self):
        """Test error when provider is unknown."""
        product = {"title": "Test Product"}
        cfg = {"AI_PROVIDER": "unknown", "UNKNOWN_API_KEY": "test"}

        with pytest.raises(ValueError, match="Unknown AI provider"):
            enhance_product(product, "", "", cfg)

    @patch('src.ai_provider.claude_api')
    def test_enhance_with_audience_config_single(self, mock_claude_api):
        """Test enhancing with single audience configuration."""
        product = {"title": "Test Product"}
        cfg = {
            "AI_PROVIDER": "claude",
            "CLAUDE_API_KEY": "test-key",
            "AUDIENCE_COUNT": 1,
            "AUDIENCE_1_NAME": "Homeowners"
        }

        mock_claude_api.enhance_product_with_claude.return_value = product

        enhance_product(product, "", "", cfg)

        # Verify audience_config was passed (positional arg 6)
        call_args = mock_claude_api.enhance_product_with_claude.call_args
        audience_config = call_args[0][6]  # 7th positional argument
        assert audience_config["count"] == 1
        assert audience_config["audience_1_name"] == "Homeowners"

    @patch('src.ai_provider.claude_api')
    def test_enhance_with_audience_config_dual(self, mock_claude_api):
        """Test enhancing with dual audience configuration."""
        product = {"title": "Test Product"}
        cfg = {
            "AI_PROVIDER": "claude",
            "CLAUDE_API_KEY": "test-key",
            "AUDIENCE_COUNT": 2,
            "AUDIENCE_1_NAME": "Homeowners",
            "AUDIENCE_2_NAME": "Contractors",
            "AUDIENCE_TAB_1_LABEL": "For Home",
            "AUDIENCE_TAB_2_LABEL": "For Work"
        }

        mock_claude_api.enhance_product_with_claude.return_value = product

        enhance_product(product, "", "", cfg)

        # Verify audience_config was passed (positional arg 6)
        call_args = mock_claude_api.enhance_product_with_claude.call_args
        audience_config = call_args[0][6]  # 7th positional argument
        assert audience_config["count"] == 2
        assert audience_config["audience_1_name"] == "Homeowners"
        assert audience_config["audience_2_name"] == "Contractors"


class TestGenerateCollectionDescription:
    """Test generate_collection_description function."""

    @patch('src.ai_provider.claude_api')
    def test_generate_with_claude(self, mock_claude_api):
        """Test generating collection description with Claude."""
        cfg = {
            "AI_PROVIDER": "claude",
            "CLAUDE_API_KEY": "test-key",
            "CLAUDE_MODEL": "claude-sonnet-4-5-20250929"
        }

        mock_claude_api.generate_collection_description.return_value = "Test description"

        result = generate_collection_description(
            "Test Collection",
            "Pet Supplies",
            ["Sample 1", "Sample 2"],
            "# Voice",
            cfg
        )

        mock_claude_api.generate_collection_description.assert_called_once()
        assert result == "Test description"

    @patch('src.ai_provider.openai_api')
    def test_generate_with_openai(self, mock_openai_api):
        """Test generating collection description with OpenAI."""
        cfg = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-5"
        }

        mock_openai_api.generate_collection_description.return_value = "Test description"

        result = generate_collection_description(
            "Test Collection",
            "Pet Supplies",
            ["Sample 1", "Sample 2"],
            "# Voice",
            cfg
        )

        mock_openai_api.generate_collection_description.assert_called_once()
        assert result == "Test description"

    def test_generate_missing_api_key_claude(self):
        """Test error when Claude API key is missing."""
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": ""}

        with pytest.raises(ValueError, match="Claude API key not configured"):
            generate_collection_description("Test", "Dept", [], "", cfg)

    def test_generate_missing_api_key_openai(self):
        """Test error when OpenAI API key is missing."""
        cfg = {"AI_PROVIDER": "openai", "OPENAI_API_KEY": ""}

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            generate_collection_description("Test", "Dept", [], "", cfg)

    def test_generate_unknown_provider(self):
        """Test error when provider is unknown."""
        cfg = {"AI_PROVIDER": "invalid"}

        with pytest.raises(ValueError, match="Unknown AI provider"):
            generate_collection_description("Test", "Dept", [], "", cfg)


class TestBatchEnhanceProducts:
    """Test batch_enhance_products function."""

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    def test_batch_enhance_basic(self, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test basic batch enhancement."""
        products = [
            {"title": "Product 1", "body_html": "Desc 1"},
            {"title": "Product 2", "body_html": "Desc 2"}
        ]
        cfg = {
            "AI_PROVIDER": "claude",
            "CLAUDE_API_KEY": "test-key",
            "CLAUDE_MODEL": "claude-sonnet-4-5-20250929"
        }
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.side_effect = [
            {**products[0], "product_type": "Pet Supplies", "tags": ["Dogs"]},
            {**products[1], "product_type": "Lawn and Garden", "tags": ["Tools"]}
        ]

        result = batch_enhance_products(products, cfg, status_fn)

        assert len(result) == 2
        assert result[0]["product_type"] == "Pet Supplies"
        assert result[1]["product_type"] == "Lawn and Garden"
        mock_save_cache.assert_called()

    @patch('src.ai_provider.load_markdown_file')
    def test_batch_enhance_missing_taxonomy(self, mock_load_md):
        """Test error when taxonomy document is missing."""
        products = [{"title": "Product 1"}]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        mock_load_md.return_value = ""

        with pytest.raises(FileNotFoundError, match="Failed to load taxonomy document"):
            batch_enhance_products(products, cfg, status_fn)

    @patch('src.ai_provider.load_markdown_file')
    def test_batch_enhance_missing_voice_tone(self, mock_load_md):
        """Test error when voice/tone document is missing."""
        products = [{"title": "Product 1"}]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        # First call returns taxonomy, second returns empty voice/tone
        mock_load_md.side_effect = ["# Taxonomy", ""]

        with pytest.raises(FileNotFoundError, match="Failed to load voice/tone document"):
            batch_enhance_products(products, cfg, status_fn)

    def test_batch_enhance_unknown_provider(self):
        """Test error with unknown provider."""
        products = [{"title": "Product 1"}]
        cfg = {"AI_PROVIDER": "invalid"}
        status_fn = Mock()

        with pytest.raises(ValueError, match="Unknown AI provider"):
            batch_enhance_products(products, cfg, status_fn)

    def test_batch_enhance_missing_api_key(self):
        """Test error when API key is missing."""
        products = [{"title": "Product 1"}]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": ""}
        status_fn = Mock()

        with pytest.raises(ValueError, match="API key not configured"):
            batch_enhance_products(products, cfg, status_fn)

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    @patch('time.sleep')
    def test_batch_enhance_with_rate_limiting(self, mock_sleep, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test that rate limiting pause is applied."""
        products = [{"title": f"Product {i}"} for i in range(6)]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.return_value = {"title": "Enhanced", "product_type": "Dept", "tags": []}

        batch_enhance_products(products, cfg, status_fn)

        # Should have one rate limit pause after 5 products
        mock_sleep.assert_called_once_with(6)

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.load_cache')
    def test_batch_enhance_uses_cache(self, mock_load_cache, mock_load_md):
        """Test that cached products are used."""
        product = {"title": "Product 1", "body_html": "Desc"}
        products = [product]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        # Set up cache with this product
        product_hash = compute_product_hash(product)
        mock_load_cache.return_value = {
            "cache_version": "1.0",
            "products": {
                "Product 1": {
                    "input_hash": product_hash,
                    "department": "Pet Supplies",
                    "category": "Dogs",
                    "subcategory": "Food",
                    "enhanced_description": "<p>Enhanced</p>",
                    "shopify_category_id": "gid://shopify/123"
                }
            }
        }
        mock_load_md.return_value = "# Test Doc"

        result = batch_enhance_products(products, cfg, status_fn)

        assert len(result) == 1
        assert result[0]["product_type"] == "Pet Supplies"
        assert result[0]["tags"] == ["Dogs", "Food"]
        assert result[0]["body_html"] == "<p>Enhanced</p>"
        assert result[0]["shopify_category_id"] == "gid://shopify/123"

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    def test_batch_enhance_saves_to_cache(self, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test that enhanced products are saved to cache."""
        product = {"title": "Product 1", "body_html": "Desc"}
        products = [product]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.return_value = {
            **product,
            "product_type": "Pet Supplies",
            "tags": ["Dogs", "Food"],
            "body_html": "<p>Enhanced</p>",
            "shopify_category_id": "gid://shopify/123"
        }

        batch_enhance_products(products, cfg, status_fn)

        # Verify cache was saved with enhanced data
        save_call_args = mock_save_cache.call_args[0][0]
        cached_product = save_call_args["products"]["Product 1"]
        assert cached_product["department"] == "Pet Supplies"
        assert cached_product["category"] == "Dogs"
        assert cached_product["subcategory"] == "Food"
        assert cached_product["enhanced_description"] == "<p>Enhanced</p>"
        assert cached_product["shopify_category_id"] == "gid://shopify/123"

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    def test_batch_enhance_stops_on_error(self, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test that batch processing stops on first error."""
        products = [
            {"title": "Product 1"},
            {"title": "Product 2"},
            {"title": "Product 3"}
        ]
        cfg = {"AI_PROVIDER": "claude", "CLAUDE_API_KEY": "test-key"}
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"

        # Second product fails
        mock_enhance.side_effect = [
            {**products[0], "product_type": "Dept"},
            Exception("API Error"),
            {**products[2], "product_type": "Dept"}
        ]

        with pytest.raises(Exception, match="API Error"):
            batch_enhance_products(products, cfg, status_fn)

        # Should have processed first product, failed on second, never reached third
        assert mock_enhance.call_count == 2
        mock_save_cache.assert_called()  # Cache should be saved even on error

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    @patch('src.taxonomy_search.fetch_shopify_taxonomy_from_github')
    def test_batch_enhance_with_openai(self, mock_fetch_taxonomy, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test batch enhancement with OpenAI provider."""
        products = [{"title": "Product 1", "body_html": "Desc 1"}]
        cfg = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-5"
        }
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.return_value = {**products[0], "product_type": "Pet Supplies", "tags": ["Dogs"]}
        mock_fetch_taxonomy.return_value = [{"id": "cat1", "name": "Category 1"}]

        result = batch_enhance_products(products, cfg, status_fn)

        assert len(result) == 1
        assert result[0]["product_type"] == "Pet Supplies"
        # Verify Shopify taxonomy was fetched for OpenAI
        mock_fetch_taxonomy.assert_called_once()

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    def test_batch_enhance_openai_shopify_fetch_fails(self, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test OpenAI batch enhancement when Shopify taxonomy fetch fails."""
        products = [{"title": "Product 1", "body_html": "Desc 1"}]
        cfg = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-5"
        }
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.return_value = {**products[0], "product_type": "Pet Supplies", "tags": ["Dogs"]}

        # Mock shopify_api to raise exception when fetching
        shopify_api_mock = MagicMock()
        shopify_api_mock.fetch_shopify_taxonomy_from_github.side_effect = Exception("Fetch failed")

        with patch.dict('sys.modules', {'src.shopify_api': shopify_api_mock}):
            # Should continue despite Shopify fetch failure
            result = batch_enhance_products(products, cfg, status_fn)

        assert len(result) == 1
        assert result[0]["product_type"] == "Pet Supplies"

    @patch('src.ai_provider.load_markdown_file')
    @patch('src.ai_provider.save_cache')
    @patch('src.ai_provider.load_cache')
    @patch('src.ai_provider.enhance_product')
    def test_batch_enhance_openai_shopify_returns_empty(self, mock_enhance, mock_load_cache, mock_save_cache, mock_load_md):
        """Test OpenAI batch enhancement when Shopify taxonomy returns empty list."""
        products = [{"title": "Product 1", "body_html": "Desc 1"}]
        cfg = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "gpt-5"
        }
        status_fn = Mock()

        mock_load_cache.return_value = {"cache_version": "1.0", "products": {}}
        mock_load_md.return_value = "# Test Doc"
        mock_enhance.return_value = {**products[0], "product_type": "Pet Supplies", "tags": ["Dogs"]}

        # Mock shopify_api to return empty list
        shopify_api_mock = MagicMock()
        shopify_api_mock.fetch_shopify_taxonomy_from_github.return_value = []

        with patch.dict('sys.modules', {'src.shopify_api': shopify_api_mock}):
            # Should continue despite empty Shopify taxonomy
            result = batch_enhance_products(products, cfg, status_fn)

        assert len(result) == 1
        assert result[0]["product_type"] == "Pet Supplies"
