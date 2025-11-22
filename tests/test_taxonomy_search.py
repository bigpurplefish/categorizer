"""
Tests for src/taxonomy_search.py

Tests Shopify taxonomy search functions and caching.
"""

import pytest
import json
import sys
import logging
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src import taxonomy_search


# ============================================================================
# TAXONOMY CACHE TESTS
# ============================================================================

class TestLoadTaxonomyCache:
    """Tests for load_taxonomy_cache() function."""

    def test_load_cache_nonexistent(self, temp_dir):
        """Test loading cache when file doesn't exist returns empty dict."""
        cache_path = temp_dir / "nonexistent.json"
        result = taxonomy_search.load_taxonomy_cache(str(cache_path))
        assert result == {}

    def test_load_cache_valid_file(self, temp_taxonomy_cache_file):
        """Test loading cache from valid file."""
        result = taxonomy_search.load_taxonomy_cache(str(temp_taxonomy_cache_file))
        assert "Pavers and Hardscaping" in result
        assert result["Pavers and Hardscaping"] == "gid://shopify/TaxonomyCategory/aa_321"

    def test_load_cache_corrupted_json(self, temp_dir, caplog):
        """Test loading cache with corrupted JSON returns empty dict."""
        cache_path = temp_dir / "corrupted.json"
        cache_path.write_text("{ invalid json }")

        with caplog.at_level(logging.WARNING):
            result = taxonomy_search.load_taxonomy_cache(str(cache_path))

        assert result == {}
        assert "Failed to parse taxonomy file" in caplog.text

    def test_load_cache_io_error(self, temp_dir, caplog, monkeypatch):
        """Test handling of IO errors when loading cache."""
        cache_path = temp_dir / "test.json"
        cache_path.write_text("{}")

        def mock_open_error(*args, **kwargs):
            raise IOError("Read error")

        with caplog.at_level(logging.WARNING):
            monkeypatch.setattr("builtins.open", mock_open_error)
            result = taxonomy_search.load_taxonomy_cache(str(cache_path))

        assert result == {}
        assert "Failed to read taxonomy file" in caplog.text

    def test_load_cache_unexpected_error(self, temp_dir, caplog):
        """Test handling of unexpected errors when loading cache."""
        cache_path = temp_dir / "test.json"
        # Create a file that exists
        cache_path.write_text('{}')

        with caplog.at_level(logging.WARNING):
            # Mock json.load to raise an unexpected error
            with patch("json.load", side_effect=ValueError("Unexpected error")):
                result = taxonomy_search.load_taxonomy_cache(str(cache_path))

        assert result == {}
        assert "Unexpected error loading taxonomy" in caplog.text

    def test_load_cache_default_path(self, monkeypatch):
        """Test loading cache with default path (current directory)."""
        monkeypatch.chdir("/tmp")
        result = taxonomy_search.load_taxonomy_cache()
        assert result == {}  # File won't exist, should return empty dict


class TestSaveTaxonomyCache:
    """Tests for save_taxonomy_cache() function."""

    def test_save_cache_creates_file(self, temp_dir):
        """Test saving cache creates a new file."""
        cache_path = temp_dir / "new_cache.json"
        test_cache = {
            "Category A": "gid://shopify/TaxonomyCategory/123",
            "Category B": "gid://shopify/TaxonomyCategory/456"
        }

        taxonomy_search.save_taxonomy_cache(test_cache, str(cache_path))

        assert cache_path.exists()
        with open(cache_path, 'r') as f:
            loaded = json.load(f)
        assert loaded == test_cache

    def test_save_cache_overwrites_existing(self, temp_taxonomy_cache_file):
        """Test saving cache overwrites existing file."""
        new_cache = {
            "New Category": "gid://shopify/TaxonomyCategory/999"
        }

        taxonomy_search.save_taxonomy_cache(new_cache, str(temp_taxonomy_cache_file))

        with open(temp_taxonomy_cache_file, 'r') as f:
            loaded = json.load(f)
        assert loaded == new_cache
        assert "Pavers and Hardscaping" not in loaded

    def test_save_cache_io_error(self, temp_dir, caplog, monkeypatch):
        """Test handling of IO errors when saving cache."""
        cache_path = temp_dir / "test.json"

        def mock_open_error(*args, **kwargs):
            raise IOError("Write error")

        with caplog.at_level(logging.ERROR):
            monkeypatch.setattr("builtins.open", mock_open_error)
            taxonomy_search.save_taxonomy_cache({}, str(cache_path))

        assert "Failed to write taxonomy file" in caplog.text

    def test_save_cache_unexpected_error(self, temp_dir, caplog, monkeypatch):
        """Test handling of unexpected errors when saving cache."""
        cache_path = temp_dir / "test.json"

        def mock_open_error(*args, **kwargs):
            raise ValueError("Unexpected error")

        with caplog.at_level(logging.ERROR):
            monkeypatch.setattr("builtins.open", mock_open_error)
            taxonomy_search.save_taxonomy_cache({}, str(cache_path))

        assert "Unexpected error saving taxonomy" in caplog.text

    def test_save_cache_default_path(self, monkeypatch, temp_dir):
        """Test saving cache with default path (cache directory)."""
        monkeypatch.chdir(str(temp_dir))
        test_cache = {"Test": "gid://shopify/TaxonomyCategory/123"}

        taxonomy_search.save_taxonomy_cache(test_cache)

        expected_path = temp_dir / "cache" / "product_taxonomy.json"
        assert expected_path.exists()


# ============================================================================
# SEARCH SHOPIFY TAXONOMY TESTS
# ============================================================================

class TestSearchShopifyTaxonomy:
    """Tests for search_shopify_taxonomy() function."""

    @patch('src.taxonomy_search.requests.post')
    def test_exact_match(self, mock_post, mock_shopify_taxonomy_response):
        """Test finding exact taxonomy match."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.search_shopify_taxonomy(
            "Home & Garden > Lawn & Garden > Pavers and Hardscaping",
            api_url,
            headers
        )

        assert result == "gid://shopify/TaxonomyCategory/aa_321"

    @patch('src.taxonomy_search.requests.post')
    def test_contains_match(self, mock_post, mock_shopify_taxonomy_response):
        """Test finding taxonomy with contains match."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.search_shopify_taxonomy(
            "Pavers",  # Part of "Pavers and Hardscaping"
            api_url,
            headers
        )

        assert result is not None
        assert "TaxonomyCategory" in result

    @patch('src.taxonomy_search.requests.post')
    def test_keyword_match(self, mock_post, mock_shopify_taxonomy_response):
        """Test finding taxonomy with keyword match."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.search_shopify_taxonomy(
            "Hardscaping Garden",  # Keywords present in taxonomy
            api_url,
            headers
        )

        assert result is not None

    @patch('src.taxonomy_search.requests.post')
    def test_no_match(self, mock_post, mock_shopify_taxonomy_empty_response, caplog):
        """Test when no taxonomy match is found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_empty_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result = taxonomy_search.search_shopify_taxonomy(
                "Nonexistent Category",
                api_url,
                headers
            )

        assert result is None
        assert "No taxonomy results" in caplog.text

    @patch('src.taxonomy_search.requests.post')
    def test_graphql_error(self, mock_post, mock_shopify_taxonomy_error_response, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_error_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.search_shopify_taxonomy(
                "Test Category",
                api_url,
                headers
            )

        assert result is None
        assert "GraphQL errors in taxonomy search" in caplog.text

    @patch('src.taxonomy_search.requests.post')
    def test_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.search_shopify_taxonomy(
                "Test Category",
                api_url,
                headers
            )

        assert result is None
        assert "Network error searching taxonomy" in caplog.text

    @patch('src.taxonomy_search.requests.post')
    def test_unexpected_error(self, mock_post, caplog):
        """Test handling of unexpected errors."""
        mock_post.side_effect = ValueError("Unexpected error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.search_shopify_taxonomy(
                "Test Category",
                api_url,
                headers
            )

        assert result is None
        assert "Unexpected error searching taxonomy" in caplog.text

    @patch('src.taxonomy_search.requests.post')
    def test_pagination(self, mock_post):
        """Test taxonomy search with pagination."""
        # First page response
        first_page = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/1",
                                    "fullName": "Category 1",
                                    "name": "Category 1"
                                }
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor_123"
                        }
                    }
                }
            }
        }

        # Second page response
        second_page = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {
                                "node": {
                                    "id": "gid://shopify/TaxonomyCategory/2",
                                    "fullName": "Test Match Category",
                                    "name": "Test Match"
                                }
                            }
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None
                        }
                    }
                }
            }
        }

        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = first_page

        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = second_page

        mock_post.side_effect = [mock_response_1, mock_response_2]

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.search_shopify_taxonomy(
            "Test Match Category",
            api_url,
            headers
        )

        assert result == "gid://shopify/TaxonomyCategory/2"
        assert mock_post.call_count == 2

    @patch('src.taxonomy_search.requests.post')
    def test_with_status_fn(self, mock_post, mock_shopify_taxonomy_response, mock_status_fn):
        """Test search with status function callback."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        taxonomy_search.search_shopify_taxonomy(
            "Pavers and Hardscaping",
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert len(mock_status_fn.messages) > 0
        assert any("Searching taxonomy" in msg for msg in mock_status_fn.messages)


# ============================================================================
# FETCH SHOPIFY TAXONOMY FROM GITHUB TESTS
# ============================================================================

class TestFetchShopifyTaxonomyFromGithub:
    """Tests for fetch_shopify_taxonomy_from_github() function."""

    @patch('src.taxonomy_search.requests.get')
    def test_successful_fetch(self, mock_get, temp_dir, monkeypatch):
        """Test successful fetch from GitHub."""
        monkeypatch.chdir(str(temp_dir))

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """gid://shopify/TaxonomyCategory/aa_1 : Animals & Pet Supplies
gid://shopify/TaxonomyCategory/aa_2 : Home & Garden
gid://shopify/TaxonomyCategory/aa_3 : Home & Garden > Lawn & Garden"""
        mock_get.return_value = mock_response

        result = taxonomy_search.fetch_shopify_taxonomy_from_github()

        assert len(result) == 3
        assert result[0]['id'] == "gid://shopify/TaxonomyCategory/aa_1"
        assert result[0]['fullName'] == "Animals & Pet Supplies"
        assert mock_get.called

    @patch('src.taxonomy_search.requests.get')
    def test_uses_cache(self, mock_get, temp_dir, monkeypatch, caplog):
        """Test that function uses cached taxonomy if available and recent."""
        monkeypatch.chdir(str(temp_dir))

        # Create a recent cache file
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "shopify_taxonomy_cache.json"
        cache_data = {
            'cached_at': datetime.now().isoformat(),
            'categories': [
                {'id': 'gid://shopify/TaxonomyCategory/test', 'fullName': 'Test Category'}
            ]
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

        with caplog.at_level(logging.INFO):
            result = taxonomy_search.fetch_shopify_taxonomy_from_github()

        assert len(result) == 1
        assert "Using cached taxonomy" in caplog.text
        assert not mock_get.called

    @patch('src.taxonomy_search.requests.get')
    def test_cache_expired(self, mock_get, temp_dir, monkeypatch):
        """Test that expired cache is refreshed."""
        monkeypatch.chdir(str(temp_dir))

        # Create an old cache file (40 days ago)
        cache_file = temp_dir / "shopify_taxonomy_cache.json"
        old_date = datetime.now() - timedelta(days=40)
        cache_data = {
            'cached_at': old_date.isoformat(),
            'categories': [{'id': 'old', 'fullName': 'Old'}]
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "gid://shopify/TaxonomyCategory/new : New Category"
        mock_get.return_value = mock_response

        result = taxonomy_search.fetch_shopify_taxonomy_from_github()

        assert len(result) == 1
        assert result[0]['id'] == "gid://shopify/TaxonomyCategory/new"
        assert mock_get.called

    @patch('src.taxonomy_search.requests.get')
    def test_network_error_uses_stale_cache(self, mock_get, temp_dir, monkeypatch, caplog):
        """Test that stale cache is used as fallback on network error."""
        monkeypatch.chdir(str(temp_dir))

        # Create a stale cache
        cache_dir = temp_dir / "cache"
        cache_dir.mkdir()
        cache_file = cache_dir / "shopify_taxonomy_cache.json"
        old_date = datetime.now() - timedelta(days=40)
        cache_data = {
            'cached_at': old_date.isoformat(),
            'categories': [{'id': 'stale', 'fullName': 'Stale Category'}]
        }
        with open(cache_file, 'w') as f:
            json.dump(cache_data, f)

        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with caplog.at_level(logging.WARNING):
            result = taxonomy_search.fetch_shopify_taxonomy_from_github()

        assert len(result) == 1
        assert "Using stale cache as fallback" in caplog.text

    @patch('src.taxonomy_search.requests.get')
    def test_network_error_no_cache(self, mock_get, temp_dir, monkeypatch, caplog):
        """Test handling of network error with no cache available."""
        monkeypatch.chdir(str(temp_dir))

        import requests
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.fetch_shopify_taxonomy_from_github()

        assert result == []
        assert "Failed to fetch taxonomy from GitHub" in caplog.text

    @patch('src.taxonomy_search.requests.get')
    def test_creates_cache_file(self, mock_get, temp_dir, monkeypatch):
        """Test that successful fetch creates cache file."""
        monkeypatch.chdir(str(temp_dir))

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = "gid://shopify/TaxonomyCategory/test : Test"
        mock_get.return_value = mock_response

        taxonomy_search.fetch_shopify_taxonomy_from_github()

        cache_file = temp_dir / "cache" / "shopify_taxonomy_cache.json"
        assert cache_file.exists()


# ============================================================================
# GET TAXONOMY ID TESTS
# ============================================================================

class TestGetTaxonomyId:
    """Tests for get_taxonomy_id() function."""

    def test_cached_taxonomy_id(self, sample_taxonomy_cache, caplog):
        """Test getting taxonomy ID from cache."""
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.INFO):
            result, updated_cache = taxonomy_search.get_taxonomy_id(
                "Pavers and Hardscaping",
                sample_taxonomy_cache,
                api_url,
                headers
            )

        assert result == "gid://shopify/TaxonomyCategory/aa_321"
        assert "Using cached taxonomy ID" in caplog.text
        assert updated_cache == sample_taxonomy_cache  # Cache unchanged

    @patch('src.taxonomy_search.search_shopify_taxonomy')
    @patch('src.taxonomy_search.save_taxonomy_cache')
    def test_not_cached_successful_search(self, mock_save, mock_search, sample_taxonomy_cache, temp_dir, caplog):
        """Test getting taxonomy ID when not cached, successful API search."""
        mock_search.return_value = "gid://shopify/TaxonomyCategory/new_123"

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        cache_path = temp_dir / "cache.json"

        with caplog.at_level(logging.INFO):
            result, updated_cache = taxonomy_search.get_taxonomy_id(
                "New Category",
                sample_taxonomy_cache,
                api_url,
                headers,
                cache_file_path=str(cache_path)
            )

        assert result == "gid://shopify/TaxonomyCategory/new_123"
        assert "Cached taxonomy mapping" in caplog.text
        assert "New Category" in updated_cache
        assert mock_save.called

    @patch('src.taxonomy_search.search_shopify_taxonomy')
    @patch('src.taxonomy_search.save_taxonomy_cache')
    def test_not_cached_no_match(self, mock_save, mock_search, sample_taxonomy_cache, temp_dir, caplog):
        """Test getting taxonomy ID when not cached and no match found."""
        mock_search.return_value = None

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}
        cache_path = temp_dir / "cache.json"

        with caplog.at_level(logging.WARNING):
            result, updated_cache = taxonomy_search.get_taxonomy_id(
                "Nonexistent Category",
                sample_taxonomy_cache,
                api_url,
                headers,
                cache_file_path=str(cache_path)
            )

        assert result is None
        assert "No taxonomy match found" in caplog.text
        assert "Nonexistent Category" in updated_cache
        assert updated_cache["Nonexistent Category"] is None  # Cached as None
        assert mock_save.called

    def test_empty_category_name(self, sample_taxonomy_cache):
        """Test handling of empty category name."""
        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result, updated_cache = taxonomy_search.get_taxonomy_id(
            "",
            sample_taxonomy_cache,
            api_url,
            headers
        )

        assert result is None
        assert updated_cache == sample_taxonomy_cache

    @patch('src.taxonomy_search.search_shopify_taxonomy')
    def test_hierarchical_fallback(self, mock_search, sample_taxonomy_cache):
        """Test fallback strategy for hierarchical categories."""
        # First call fails, second call succeeds
        mock_search.side_effect = [
            None,  # "Category > Subcategory" fails
            "gid://shopify/TaxonomyCategory/found_789"  # "Subcategory" succeeds
        ]

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result, updated_cache = taxonomy_search.get_taxonomy_id(
            "Category > Subcategory",
            {},  # Empty cache
            api_url,
            headers
        )

        assert result == "gid://shopify/TaxonomyCategory/found_789"
        assert mock_search.call_count >= 2

    @patch('src.taxonomy_search.search_shopify_taxonomy')
    def test_last_word_fallback(self, mock_search, sample_taxonomy_cache):
        """Test fallback strategy using last word."""
        # First call fails, last word succeeds
        mock_search.side_effect = [
            None,  # "Multi Word Category Name" fails
            "gid://shopify/TaxonomyCategory/name_456"  # "Name" succeeds
        ]

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result, updated_cache = taxonomy_search.get_taxonomy_id(
            "Multi Word Category Name",
            {},  # Empty cache
            api_url,
            headers
        )

        assert result == "gid://shopify/TaxonomyCategory/name_456"

    @patch('src.taxonomy_search.search_shopify_taxonomy')
    def test_with_status_fn(self, mock_search, sample_taxonomy_cache, mock_status_fn):
        """Test get_taxonomy_id with status function callback."""
        mock_search.return_value = "gid://shopify/TaxonomyCategory/test_123"

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        taxonomy_search.get_taxonomy_id(
            "Test Category",
            {},
            api_url,
            headers,
            status_fn=mock_status_fn
        )

        assert len(mock_status_fn.messages) > 0
        assert any("Looking up" in msg or "taxonomy" in msg.lower() for msg in mock_status_fn.messages)


# ============================================================================
# FETCH ALL SHOPIFY CATEGORIES TESTS
# ============================================================================

class TestFetchAllShopifyCategories:
    """Tests for fetch_all_shopify_categories() function."""

    @patch('src.taxonomy_search.requests.post')
    def test_successful_fetch(self, mock_post, mock_shopify_taxonomy_response):
        """Test successful fetch of all categories."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_shopify_taxonomy_response
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.fetch_all_shopify_categories(api_url, headers)

        assert len(result) == 2
        assert result[0]['id'] == "gid://shopify/TaxonomyCategory/aa_321"
        assert result[0]['fullName'] == "Home & Garden > Lawn & Garden > Pavers and Hardscaping"

    @patch('src.taxonomy_search.requests.post')
    def test_fetch_with_pagination(self, mock_post):
        """Test fetching categories with multiple pages."""
        # First page
        first_page = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {"node": {"id": "cat1", "fullName": "Category 1"}}
                        ],
                        "pageInfo": {
                            "hasNextPage": True,
                            "endCursor": "cursor_1"
                        }
                    }
                }
            }
        }

        # Second page
        second_page = {
            "data": {
                "taxonomy": {
                    "categories": {
                        "edges": [
                            {"node": {"id": "cat2", "fullName": "Category 2"}}
                        ],
                        "pageInfo": {
                            "hasNextPage": False,
                            "endCursor": None
                        }
                    }
                }
            }
        }

        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = first_page

        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = second_page

        mock_post.side_effect = [mock_response_1, mock_response_2]

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        result = taxonomy_search.fetch_all_shopify_categories(api_url, headers)

        assert len(result) == 2
        assert mock_post.call_count == 2

    @patch('src.taxonomy_search.requests.post')
    def test_graphql_error(self, mock_post, caplog):
        """Test handling of GraphQL errors."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "errors": [{"message": "GraphQL error"}]
        }
        mock_post.return_value = mock_response

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.fetch_all_shopify_categories(api_url, headers)

        assert result == []
        assert "GraphQL errors" in caplog.text

    @patch('src.taxonomy_search.requests.post')
    def test_network_error(self, mock_post, caplog):
        """Test handling of network errors."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

        api_url = "https://test-store.myshopify.com/admin/api/2025-10/graphql.json"
        headers = {"X-Shopify-Access-Token": "test_token"}

        with caplog.at_level(logging.ERROR):
            result = taxonomy_search.fetch_all_shopify_categories(api_url, headers)

        assert result == []
        assert "Error fetching Shopify categories" in caplog.text


# ============================================================================
# LOG STATUS FUNCTION TESTS
# ============================================================================

class TestLogAndStatus:
    """Tests for log_and_status() helper function."""

    def test_log_error_level(self, caplog):
        """Test logging at error level."""
        with caplog.at_level(logging.ERROR):
            taxonomy_search.log_and_status(None, "Error message", level="error")

        assert "Error message" in caplog.text
        assert caplog.records[0].levelname == "ERROR"

    def test_log_warning_level(self, caplog):
        """Test logging at warning level."""
        with caplog.at_level(logging.WARNING):
            taxonomy_search.log_and_status(None, "Warning message", level="warning")

        assert "Warning message" in caplog.text
        assert caplog.records[0].levelname == "WARNING"

    def test_log_info_level(self, caplog):
        """Test logging at info level (default)."""
        with caplog.at_level(logging.INFO):
            taxonomy_search.log_and_status(None, "Info message")

        assert "Info message" in caplog.text
        assert caplog.records[0].levelname == "INFO"

    def test_log_with_url_stripping(self):
        """Test that URLs are stripped from UI messages."""
        status_fn = Mock()
        msg = "Fetching from https://github.com/example/file.json for data"

        taxonomy_search.log_and_status(status_fn, msg)

        # URL should be stripped from UI message
        status_fn.assert_called_once()
        ui_msg = status_fn.call_args[0][0]
        assert "https://" not in ui_msg
        assert "Fetching from" in ui_msg

    def test_log_with_final_url_not_stripped(self):
        """Test that 'Final URL' messages don't get stripped."""
        status_fn = Mock()
        msg = "Final URL: https://github.com/example/file.json"

        taxonomy_search.log_and_status(status_fn, msg)

        # URL should NOT be stripped when 'Final URL' is in message
        status_fn.assert_called_once()
        ui_msg = status_fn.call_args[0][0]
        assert "https://github.com/example/file.json" in ui_msg

    def test_log_status_fn_exception(self, caplog, capsys):
        """Test handling of exceptions in status_fn callback."""
        def failing_status_fn(msg):
            raise ValueError("Status function failed")

        with caplog.at_level(logging.WARNING):
            taxonomy_search.log_and_status(failing_status_fn, "Test message")

        # Should log the exception
        assert "status_fn raised while logging message" in caplog.text

        # Should print to console as fallback
        captured = capsys.readouterr()
        assert "[STATUS] Test message" in captured.out

    def test_log_without_status_fn(self, caplog):
        """Test logging when status_fn is None."""
        with caplog.at_level(logging.INFO):
            taxonomy_search.log_and_status(None, "Test message")

        assert "Test message" in caplog.text
