"""
Shopify taxonomy search and caching functionality.

This module provides functions to search Shopify's standard product taxonomy
for category matching, with support for multiple search strategies and caching.

Extracted from uploader project for use in categorizer.
"""

import json
import logging
import requests
import os
from datetime import datetime, timedelta


def log_and_status(status_fn, msg: str, level: str = "info", ui_msg: str = None):
    """
    Log a message to log file, console, AND UI status field.

    Args:
        status_fn: Function to update UI status field (can be None)
        msg: Detailed message for log file and console
        level: Log level - "info", "warning", or "error"
        ui_msg: Optional user-friendly message for UI
    """
    if ui_msg is None:
        ui_msg = msg
        if 'https://' in ui_msg and 'Final URL' not in ui_msg:
            ui_msg = ui_msg.split('https://')[0].strip()

    # Always log to file/console first
    if level == "error":
        logging.error(msg)
    elif level == "warning":
        logging.warning(msg)
    else:
        logging.info(msg)

    # Then try to update UI
    if status_fn is not None:
        try:
            status_fn(ui_msg)
        except Exception as e:
            logging.warning(f"status_fn raised while logging message: {e}", exc_info=True)
            # Print to console as fallback
            print(f"[STATUS] {ui_msg}")


def load_taxonomy_cache(cache_file_path: str = None):
    """
    Load taxonomy cache from taxonomy file.

    Args:
        cache_file_path: Optional path to cache file. If None, uses default location.

    Returns:
        Dictionary mapping category names to taxonomy IDs
    """
    if cache_file_path is None:
        # Default to current directory
        cache_file_path = os.path.join(os.getcwd(), "product_taxonomy.json")

    try:
        if os.path.exists(cache_file_path):
            with open(cache_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except json.JSONDecodeError as e:
        logging.warning(f"Failed to parse taxonomy file: {e}. Starting fresh.")
    except IOError as e:
        logging.warning(f"Failed to read taxonomy file: {e}. Starting fresh.")
    except Exception as e:
        logging.warning(f"Unexpected error loading taxonomy: {e}. Starting fresh.")

    return {}


def save_taxonomy_cache(taxonomy_cache, cache_file_path: str = None):
    """
    Save taxonomy cache to taxonomy file.

    Args:
        taxonomy_cache: Dictionary mapping category names to taxonomy IDs
        cache_file_path: Optional path to cache file. If None, uses default location.
    """
    if cache_file_path is None:
        # Default to current directory
        cache_file_path = os.path.join(os.getcwd(), "product_taxonomy.json")

    try:
        with open(cache_file_path, 'w', encoding='utf-8') as f:
            json.dump(taxonomy_cache, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write taxonomy file: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving taxonomy: {e}")


def search_shopify_taxonomy(category_name, api_url, headers, status_fn=None):
    """
    Search Shopify's standard product taxonomy for a category.

    Args:
        category_name: Category name to search for
        api_url: Shopify GraphQL API URL
        headers: API request headers
        status_fn: Optional status update function

    Returns:
        Taxonomy ID (GID format) if found, None otherwise
    """
    try:
        # Use taxonomyCategories to search (API 2025-10)
        # Fetch all categories with pagination
        all_edges = []
        cursor = None
        page_count = 0
        max_pages = 20  # Max 5000 categories (250 per page)

        if status_fn:
            log_and_status(status_fn, f"  Searching taxonomy for: {category_name}")
        else:
            logging.info(f"  Searching taxonomy for: {category_name}")

        while page_count < max_pages:
            # Fixed query for API 2025-10: Use taxonomy.categories instead of taxonomyCategories
            search_query = """
            query searchTaxonomy($cursor: String) {
              taxonomy {
                categories(first: 250, after: $cursor) {
                  edges {
                    node {
                      id
                      fullName
                      name
                    }
                    cursor
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
            """

            variables = {"cursor": cursor} if cursor else {}

            response = requests.post(
                api_url,
                json={"query": search_query, "variables": variables},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            # Check for errors
            if "errors" in result:
                if status_fn:
                    log_and_status(status_fn, f"  GraphQL errors in taxonomy search: {result['errors']}", "error")
                else:
                    logging.error(f"  GraphQL errors in taxonomy search: {result['errors']}")
                return None

            # Fixed path for API 2025-10: data.taxonomy.categories instead of data.taxonomyCategories
            taxonomy_data = result.get("data", {}).get("taxonomy", {}).get("categories", {})
            edges = taxonomy_data.get("edges", [])
            page_info = taxonomy_data.get("pageInfo", {})

            all_edges.extend(edges)
            page_count += 1

            # Check if there are more pages
            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        if status_fn:
            log_and_status(status_fn, f"  Loaded {len(all_edges)} taxonomy categories from {page_count} page(s)")
        else:
            logging.info(f"  Loaded {len(all_edges)} taxonomy categories from {page_count} page(s)")

        edges = all_edges

        if not edges:
            if status_fn:
                log_and_status(status_fn, f"  No taxonomy results")
            else:
                logging.info(f"  No taxonomy results")
            return None

        # ========== MULTI-STRATEGY SEARCH ==========
        # Try multiple search strategies to find the best match
        category_lower = category_name.lower()

        # Strategy 1: Exact match (case-insensitive)
        exact_match = None
        for edge in edges:
            node = edge.get("node", {})
            full_name = node.get("fullName", "")
            if full_name.lower() == category_lower:
                exact_match = node
                break

        if exact_match:
            taxonomy_id = exact_match.get("id")
            full_name = exact_match.get("fullName")
            if status_fn:
                log_and_status(status_fn, f"  ✅ Found exact taxonomy match: {full_name}")
            else:
                logging.info(f"  ✅ Found exact taxonomy match: {full_name}")
            return taxonomy_id

        # Strategy 2: Contains match (search term in fullName)
        contains_matches = []
        for edge in edges:
            node = edge.get("node", {})
            full_name = node.get("fullName", "")
            full_name_lower = full_name.lower()

            if category_lower in full_name_lower:
                contains_matches.append(node)

        if contains_matches:
            # Pick the shortest match (usually most specific)
            best_match = min(contains_matches, key=lambda n: len(n.get("fullName", "")))
            taxonomy_id = best_match.get("id")
            full_name = best_match.get("fullName")
            if status_fn:
                log_and_status(status_fn, f"  ✅ Found contains match: {full_name}")
            else:
                logging.info(f"  ✅ Found contains match: {full_name}")
            return taxonomy_id

        # Strategy 3: Keyword search (extract keywords and find matches)
        # Split category_name by common separators
        keywords = []
        for sep in [" > ", " - ", " / ", " & ", " and "]:
            if sep in category_name:
                parts = category_name.split(sep)
                keywords.extend([p.strip().lower() for p in parts if p.strip()])
                break

        # If no separators found, use individual words (excluding common words)
        if not keywords:
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with'}
            words = category_name.lower().split()
            keywords = [w for w in words if w not in stop_words and len(w) > 2]

        if keywords:
            keyword_matches = []
            for edge in edges:
                node = edge.get("node", {})
                full_name = node.get("fullName", "")
                full_name_lower = full_name.lower()

                # Count how many keywords match
                match_count = sum(1 for kw in keywords if kw in full_name_lower)

                if match_count > 0:
                    keyword_matches.append((node, match_count))

            if keyword_matches:
                # Sort by match count (descending), then by length (ascending)
                keyword_matches.sort(key=lambda x: (-x[1], len(x[0].get("fullName", ""))))
                best_match = keyword_matches[0][0]
                match_count = keyword_matches[0][1]
                taxonomy_id = best_match.get("id")
                full_name = best_match.get("fullName")
                if status_fn:
                    log_and_status(status_fn, f"  ✅ Found keyword match ({match_count}/{len(keywords)} keywords): {full_name}")
                else:
                    logging.info(f"  ✅ Found keyword match ({match_count}/{len(keywords)} keywords): {full_name}")
                return taxonomy_id

        # No match found
        if status_fn:
            log_and_status(status_fn, f"  ⚠️  No taxonomy match found for: {category_name}")
        else:
            logging.info(f"  ⚠️  No taxonomy match found for: {category_name}")
        return None

    except requests.exceptions.RequestException as e:
        if status_fn:
            log_and_status(status_fn, f"  Network error searching taxonomy: {e}", "error")
        else:
            logging.error(f"  Network error searching taxonomy: {e}")
        return None
    except Exception as e:
        if status_fn:
            log_and_status(status_fn, f"  Unexpected error searching taxonomy: {e}", "error")
        else:
            logging.error(f"  Unexpected error searching taxonomy: {e}")
        return None


def fetch_shopify_taxonomy_from_github(status_fn=None):
    """
    Fetch Shopify's official product taxonomy from GitHub repository.

    Uses the canonical taxonomy from:
    https://raw.githubusercontent.com/Shopify/product-taxonomy/main/dist/en/categories.txt

    Format: gid://shopify/TaxonomyCategory/CODE : Category > Path > Here

    Args:
        status_fn: Optional status update function

    Returns:
        List of dicts with 'id' and 'fullName' for each category
    """
    TAXONOMY_URL = "https://raw.githubusercontent.com/Shopify/product-taxonomy/main/dist/en/categories.txt"
    CACHE_FILE = "shopify_taxonomy_cache.json"
    CACHE_DURATION_DAYS = 30  # Shopify updates quarterly, so 30 days is safe

    try:
        # Check if we have a valid cache
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)

                cached_at = datetime.fromisoformat(cache_data.get('cached_at', '2000-01-01'))
                cache_age = datetime.now() - cached_at

                if cache_age < timedelta(days=CACHE_DURATION_DAYS):
                    categories = cache_data.get('categories', [])
                    if categories:
                        if status_fn:
                            log_and_status(status_fn, f"  ✅ Using cached taxonomy ({len(categories)} categories, age: {cache_age.days} days)")
                        else:
                            logging.info(f"  ✅ Using cached taxonomy ({len(categories)} categories, age: {cache_age.days} days)")
                        return categories
            except Exception as e:
                logging.warning(f"Failed to load taxonomy cache: {e}")

        # Fetch fresh taxonomy from GitHub
        if status_fn:
            log_and_status(status_fn, f"  Fetching Shopify taxonomy from GitHub...")
        else:
            logging.info(f"  Fetching Shopify taxonomy from GitHub...")

        response = requests.get(TAXONOMY_URL, timeout=30)
        response.raise_for_status()

        # Parse the taxonomy file
        # Format: gid://shopify/TaxonomyCategory/CODE : Category > Path > Name
        categories = []
        lines = response.text.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line or ':' not in line:
                continue

            parts = line.split(' : ', 1)
            if len(parts) != 2:
                continue

            gid = parts[0].strip()
            full_name = parts[1].strip()

            if gid.startswith('gid://shopify/TaxonomyCategory/'):
                categories.append({
                    'id': gid,
                    'fullName': full_name
                })

        if status_fn:
            log_and_status(status_fn, f"  ✅ Fetched {len(categories)} categories from Shopify GitHub")
        else:
            logging.info(f"  ✅ Fetched {len(categories)} categories from Shopify GitHub")

        # Cache the results
        try:
            cache_data = {
                'cached_at': datetime.now().isoformat(),
                'source': TAXONOMY_URL,
                'version': 'latest',
                'categories': categories
            }
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)
            logging.info(f"Cached taxonomy to {CACHE_FILE}")
        except Exception as e:
            logging.warning(f"Failed to cache taxonomy: {e}")

        return categories

    except Exception as e:
        if status_fn:
            log_and_status(status_fn, f"  ⚠️  Failed to fetch taxonomy from GitHub: {e}", "error")
        else:
            logging.error(f"  Failed to fetch taxonomy from GitHub: {e}")

        # Try to use stale cache as fallback
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
                categories = cache_data.get('categories', [])
                if categories:
                    logging.warning(f"Using stale cache as fallback ({len(categories)} categories)")
                    return categories
            except:
                pass

        return []


def fetch_all_shopify_categories(api_url, headers, status_fn=None):
    """
    Fetch ALL Shopify taxonomy categories and return as a list for AI matching.

    Args:
        api_url: Shopify GraphQL API URL
        headers: API request headers
        status_fn: Optional status update function

    Returns:
        List of dicts with 'id' and 'fullName' for each category
    """
    try:
        all_categories = []
        cursor = None
        page_count = 0
        max_pages = 50  # Allow more pages to get all categories

        if status_fn:
            log_and_status(status_fn, f"  Fetching Shopify product taxonomy categories...")
        else:
            logging.info(f"  Fetching Shopify product taxonomy categories...")

        while page_count < max_pages:
            query = """
            query fetchTaxonomy($cursor: String) {
              taxonomy {
                categories(first: 250, after: $cursor) {
                  edges {
                    node {
                      id
                      fullName
                    }
                  }
                  pageInfo {
                    hasNextPage
                    endCursor
                  }
                }
              }
            }
            """

            variables = {"cursor": cursor} if cursor else {}

            response = requests.post(
                api_url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if "errors" in result:
                if status_fn:
                    log_and_status(status_fn, f"  GraphQL errors: {result['errors']}", "error")
                else:
                    logging.error(f"  GraphQL errors: {result['errors']}")
                return []

            taxonomy_data = result.get("data", {}).get("taxonomy", {}).get("categories", {})
            edges = taxonomy_data.get("edges", [])
            page_info = taxonomy_data.get("pageInfo", {})

            for edge in edges:
                node = edge.get("node", {})
                all_categories.append({
                    "id": node.get("id"),
                    "fullName": node.get("fullName")
                })

            page_count += 1

            if not page_info.get("hasNextPage"):
                break

            cursor = page_info.get("endCursor")

        if status_fn:
            log_and_status(status_fn, f"  ✅ Fetched {len(all_categories)} Shopify categories")
        else:
            logging.info(f"  ✅ Fetched {len(all_categories)} Shopify categories")

        return all_categories

    except Exception as e:
        if status_fn:
            log_and_status(status_fn, f"  Error fetching Shopify categories: {e}", "error")
        else:
            logging.error(f"  Error fetching Shopify categories: {e}")
        return []


def get_taxonomy_id(category_name, taxonomy_cache, api_url, headers, status_fn=None, cache_file_path=None):
    """
    Get the taxonomy ID for a category, using cache or API lookup.

    Uses multi-strategy search with fallbacks:
    1. Try the full category name
    2. If hierarchical (contains " > "), try each part from most specific to least
    3. Try individual keywords

    Args:
        category_name: Category name to look up
        taxonomy_cache: Dictionary of cached taxonomy mappings
        api_url: Shopify GraphQL API URL
        headers: API request headers
        status_fn: Optional status update function
        cache_file_path: Optional path to cache file for saving

    Returns:
        Tuple of (taxonomy_id, updated_cache)
    """
    if not category_name:
        return None, taxonomy_cache

    # Check cache first
    if category_name in taxonomy_cache:
        taxonomy_id = taxonomy_cache[category_name]
        if status_fn:
            log_and_status(status_fn, f"  Using cached taxonomy ID: {taxonomy_id}")
        else:
            logging.info(f"  Using cached taxonomy ID: {taxonomy_id}")
        return taxonomy_id, taxonomy_cache

    # Not in cache - search via API with fallback strategies
    if status_fn:
        log_and_status(status_fn, f"  Looking up Shopify taxonomy for: {category_name}")
    else:
        logging.info(f"  Looking up Shopify taxonomy for: {category_name}")

    # Strategy 1: Try the full category name
    taxonomy_id = search_shopify_taxonomy(category_name, api_url, headers, status_fn)

    # Strategy 2: If no match and category is hierarchical, try each part
    if not taxonomy_id and " > " in category_name:
        parts = [p.strip() for p in category_name.split(" > ") if p.strip()]
        if status_fn:
            log_and_status(status_fn, f"  Trying hierarchical parts: {parts}")
        else:
            logging.info(f"  Trying hierarchical parts: {parts}")

        # Try from most specific (last) to least specific (first)
        for part in reversed(parts):
            if status_fn:
                log_and_status(status_fn, f"  Trying part: {part}")
            else:
                logging.info(f"  Trying part: {part}")
            taxonomy_id = search_shopify_taxonomy(part, api_url, headers, status_fn)
            if taxonomy_id:
                break

    # Strategy 3: If still no match, try just the last word (often the product type)
    if not taxonomy_id:
        words = category_name.split()
        if len(words) > 1:
            last_word = words[-1]
            if status_fn:
                log_and_status(status_fn, f"  Trying last word: {last_word}")
            else:
                logging.info(f"  Trying last word: {last_word}")
            taxonomy_id = search_shopify_taxonomy(last_word, api_url, headers, status_fn)

    if taxonomy_id:
        # Add to cache
        taxonomy_cache[category_name] = taxonomy_id
        save_taxonomy_cache(taxonomy_cache, cache_file_path)
        if status_fn:
            log_and_status(status_fn, f"  ✅ Cached taxonomy mapping: {category_name} -> {taxonomy_id}")
        else:
            logging.info(f"  ✅ Cached taxonomy mapping: {category_name} -> {taxonomy_id}")
    else:
        # Cache the failure to avoid repeated lookups
        taxonomy_cache[category_name] = None
        save_taxonomy_cache(taxonomy_cache, cache_file_path)
        if status_fn:
            log_and_status(status_fn, f"  ⚠️  No taxonomy match found for: {category_name}")
        else:
            logging.warning(f"  ⚠️  No taxonomy match found for: {category_name}")

    return taxonomy_id, taxonomy_cache
