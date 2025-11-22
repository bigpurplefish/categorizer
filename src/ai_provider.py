"""
AI Provider abstraction layer - supports both Claude and OpenAI APIs.
Routes requests to the appropriate provider based on configuration.
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime
from typing import Dict, List

from .config import log_and_status
from . import claude_api
from . import openai_api


# Cache file location
CACHE_FILE = "cache/enhanced_cache.json"


def load_cache() -> Dict:
    """Load the AI enhancement cache from disk."""
    if not os.path.exists(CACHE_FILE):
        return {"cache_version": "1.0", "products": {}}

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load AI cache: {e}")
        return {"cache_version": "1.0", "products": {}}


def save_cache(cache: Dict):
    """Save the AI enhancement cache to disk."""
    try:
        # Ensure cache directory exists
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save AI cache: {e}")


def compute_product_hash(product: Dict) -> str:
    """Compute a hash of the product's title and body_html to detect changes."""
    title = product.get('title', '')
    body_html = product.get('body_html', '')
    content = f"{title}||{body_html}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def load_markdown_file(file_path: str) -> str:
    """Load a markdown file and return its contents."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"Markdown file not found: {file_path}")
        return ""
    except Exception as e:
        logging.error(f"Error loading markdown file {file_path}: {e}")
        return ""


def enhance_product(
    product: Dict,
    taxonomy_doc: str,
    voice_tone_doc: str,
    cfg: Dict,
    shopify_categories: List[Dict] = None,
    status_fn=None,
    taxonomy_mappings: Dict = None
) -> Dict:
    """
    Enhance a single product using configured AI provider.

    Args:
        product: Product dictionary
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown content
        cfg: Configuration dictionary (contains provider, API keys, models)
        shopify_categories: List of Shopify taxonomy categories (deprecated, use taxonomy_mappings)
        status_fn: Optional status update function
        taxonomy_mappings: Pre-computed taxonomy mappings (our taxonomy -> Shopify taxonomy)

    Returns:
        Enhanced product dictionary

    Raises:
        Exception: If API call fails or response is invalid
    """
    provider = cfg.get("AI_PROVIDER", "claude").lower()

    # Extract audience configuration from cfg
    audience_config = None
    audience_count = cfg.get("AUDIENCE_COUNT", 1)
    if audience_count == 2:
        audience_1_name = cfg.get("AUDIENCE_1_NAME", "").strip()
        audience_2_name = cfg.get("AUDIENCE_2_NAME", "").strip()
        tab_1_label = cfg.get("AUDIENCE_TAB_1_LABEL", "").strip()
        tab_2_label = cfg.get("AUDIENCE_TAB_2_LABEL", "").strip()

        # Only create config if both audience names are provided
        if audience_1_name and audience_2_name:
            audience_config = {
                "count": 2,
                "audience_1_name": audience_1_name,
                "audience_2_name": audience_2_name,
                "tab_1_label": tab_1_label,
                "tab_2_label": tab_2_label
            }
    elif audience_count == 1:
        # Single audience mode
        audience_1_name = cfg.get("AUDIENCE_1_NAME", "").strip()
        if audience_1_name:
            audience_config = {
                "count": 1,
                "audience_1_name": audience_1_name
            }

    if provider == "openai":
        # Use OpenAI
        api_key = cfg.get("OPENAI_API_KEY", "").strip()
        model = cfg.get("OPENAI_MODEL", "gpt-5")

        if not api_key:
            error_msg = "OpenAI API key not configured. Add your API key in Settings dialog."
            logging.error(error_msg)
            raise ValueError(error_msg)

        return openai_api.enhance_product_with_openai(
            product,
            taxonomy_doc,
            voice_tone_doc,
            shopify_categories or [],
            api_key,
            model,
            status_fn,
            audience_config,
            taxonomy_mappings
        )

    elif provider == "claude":
        # Use Claude (default)
        api_key = cfg.get("CLAUDE_API_KEY", "").strip()
        model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

        if not api_key:
            error_msg = "Claude API key not configured. Add your API key in Settings dialog."
            logging.error(error_msg)
            raise ValueError(error_msg)

        return claude_api.enhance_product_with_claude(
            product,
            taxonomy_doc,
            voice_tone_doc,
            api_key,
            model,
            status_fn,
            audience_config,
            taxonomy_mappings
        )

    else:
        error_msg = f"Unknown AI provider: {provider}. Must be 'claude' or 'openai'."
        logging.error(error_msg)
        raise ValueError(error_msg)


def generate_collection_description(
    collection_title: str,
    department: str,
    product_samples: List[str],
    voice_tone_doc: str,
    cfg: Dict,
    status_fn=None
) -> str:
    """
    Generate a collection description using configured AI provider.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions from this collection
        voice_tone_doc: Voice and tone guidelines markdown content
        cfg: Configuration dictionary (contains provider, API keys, models)
        status_fn: Optional status update function

    Returns:
        Generated collection description (plain text)

    Raises:
        Exception: If API call fails
    """
    provider = cfg.get("AI_PROVIDER", "claude").lower()

    if provider == "openai":
        # Use OpenAI
        api_key = cfg.get("OPENAI_API_KEY", "").strip()
        model = cfg.get("OPENAI_MODEL", "gpt-5")

        if not api_key:
            error_msg = "OpenAI API key not configured. Add your API key in Settings dialog."
            logging.error(error_msg)
            raise ValueError(error_msg)

        return openai_api.generate_collection_description(
            collection_title,
            department,
            product_samples,
            voice_tone_doc,
            api_key,
            model,
            status_fn
        )

    elif provider == "claude":
        # Use Claude (default)
        api_key = cfg.get("CLAUDE_API_KEY", "").strip()
        model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

        if not api_key:
            error_msg = "Claude API key not configured. Add your API key in Settings dialog."
            logging.error(error_msg)
            raise ValueError(error_msg)

        return claude_api.generate_collection_description(
            collection_title,
            department,
            product_samples,
            voice_tone_doc,
            api_key,
            model,
            status_fn
        )

    else:
        error_msg = f"Unknown AI provider: {provider}. Must be 'claude' or 'openai'."
        logging.error(error_msg)
        raise ValueError(error_msg)


def batch_enhance_products(
    products: List[Dict],
    cfg: Dict,
    status_fn,
    taxonomy_path: str = "/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md",
    voice_tone_path: str = "docs/VOICE_AND_TONE_GUIDELINES.md",
    force_refresh_cache: bool = False,
    force_refresh_taxonomy: bool = False
) -> List[Dict]:
    """
    Enhance multiple products with configured AI provider using caching.

    Routes to batch API if USE_BATCH_MODE is enabled for 50% cost savings.

    Args:
        products: List of product dictionaries
        cfg: Configuration dictionary
        status_fn: Status update function
        taxonomy_path: Path to taxonomy markdown file
        voice_tone_path: Path to voice and tone guidelines markdown file
        force_refresh_cache: If True, bypass AI enhancement cache and re-process all products
        force_refresh_taxonomy: If True, force regenerate taxonomy mapping with AI

    Returns:
        List of enhanced product dictionaries

    Raises:
        Exception: Stops immediately on API failure
    """
    provider = cfg.get("AI_PROVIDER", "claude").lower()
    use_batch_mode = cfg.get("USE_BATCH_MODE", False)

    # Validate provider and API key
    if provider == "openai":
        api_key = cfg.get("OPENAI_API_KEY", "").strip()
        model = cfg.get("OPENAI_MODEL", "gpt-5")
        provider_name = "OpenAI"
    elif provider == "claude":
        api_key = cfg.get("CLAUDE_API_KEY", "").strip()
        model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        provider_name = "Claude"
    else:
        error_msg = f"Unknown AI provider: {provider}. Must be 'claude' or 'openai'."
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise ValueError(error_msg)

    if not api_key:
        error_msg = f"{provider_name} API key not configured. Add your API key in Settings dialog."
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise ValueError(error_msg)

    # Load taxonomy and voice/tone documents
    log_and_status(status_fn, f"Loading taxonomy document: {taxonomy_path}")
    taxonomy_doc = load_markdown_file(taxonomy_path)
    if not taxonomy_doc:
        error_msg = f"Failed to load taxonomy document: {taxonomy_path}"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise FileNotFoundError(error_msg)

    log_and_status(status_fn, f"Loading voice and tone guidelines: {voice_tone_path}")
    voice_tone_doc = load_markdown_file(voice_tone_path)
    if not voice_tone_doc:
        error_msg = f"Failed to load voice/tone document: {voice_tone_path}"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise FileNotFoundError(error_msg)

    log_and_status(status_fn, f"✅ Loaded enhancement documents")

    # Check if batch mode is enabled
    if use_batch_mode:
        log_and_status(status_fn, f"🚀 Batch mode enabled: 50% cost savings")
        log_and_status(status_fn, f"🤖 Using {provider_name} ({model}) - Batch API\n")

        # Route to batch API functions
        if provider == "openai":
            # Load Shopify categories for OpenAI
            shopify_categories = []
            try:
                from .taxonomy_search import fetch_shopify_taxonomy_from_github
                log_and_status(status_fn, f"Loading Shopify product taxonomy...")
                shopify_categories = fetch_shopify_taxonomy_from_github(status_fn)
                log_and_status(status_fn, f"")
            except Exception as e:
                logging.warning(f"Failed to fetch Shopify taxonomy: {e}")

            return openai_api.enhance_products_with_openai_batch(
                products,
                taxonomy_doc,
                voice_tone_doc,
                shopify_categories,
                api_key,
                model,
                completion_window=cfg.get("BATCH_COMPLETION_WINDOW", "24h"),
                poll_interval=cfg.get("BATCH_POLL_INTERVAL", 60),
                status_fn=status_fn,
                audience_config=None
            )
        elif provider == "claude":
            return claude_api.enhance_products_with_claude_batch(
                products,
                taxonomy_doc,
                voice_tone_doc,
                api_key,
                model,
                poll_interval=cfg.get("BATCH_POLL_INTERVAL", 60),
                status_fn=status_fn,
                audience_config=None
            )

    # Standard mode (not batch)
    log_and_status(status_fn, f"🤖 Using {provider_name} ({model})\n")

    # Initialize intelligent Shopify taxonomy mapping
    taxonomy_mappings = None
    try:
        from .taxonomy_search import fetch_shopify_taxonomy_from_github
        from .taxonomy_mapper import get_or_create_taxonomy_mapping

        log_and_status(status_fn, f"Loading Shopify product taxonomy...")
        shopify_categories = fetch_shopify_taxonomy_from_github(status_fn)

        if shopify_categories:
            log_and_status(status_fn, f"✅ Loaded {len(shopify_categories)} Shopify categories")

            # Get or create intelligent taxonomy mapping (cached, only regenerates if taxonomies changed)
            taxonomy_mappings = get_or_create_taxonomy_mapping(
                our_taxonomy_path=taxonomy_path,
                shopify_categories=shopify_categories,
                api_key=api_key,
                provider=provider,
                model=model,
                status_fn=status_fn,
                force_remap=force_refresh_taxonomy
            )

            log_and_status(status_fn, f"✅ Taxonomy mapping ready ({len(taxonomy_mappings)} categories)")
            log_and_status(status_fn, f"")
        else:
            logging.warning("Failed to load Shopify taxonomy - category matching will be disabled")
    except Exception as e:
        logging.warning(f"Failed to initialize taxonomy mapping: {e}")
        taxonomy_mappings = None

    # Load cache
    cache = load_cache()
    cached_products = cache.get("products", {})

    # Handle force refresh cache
    if force_refresh_cache:
        logging.info("⚠️  Force refresh AI cache enabled - bypassing all cached data")
        log_and_status(status_fn, "⚠️  Force refresh AI cache enabled - re-processing all products")
        cached_products = {}  # Clear cache in memory (will re-process everything)

    enhanced_products = []
    enhanced_count = 0
    cached_count = 0

    total = len(products)

    logging.info("=" * 80)
    logging.info(f"STARTING BATCH AI ENHANCEMENT")
    logging.info(f"Provider: {provider_name}")
    logging.info(f"Model: {model}")
    logging.info(f"Total products to process: {total}")
    if force_refresh_cache:
        logging.info(f"Force Refresh Cache: ENABLED")
    if force_refresh_taxonomy:
        logging.info(f"Force Refresh Taxonomy: ENABLED")
    logging.info("=" * 80)

    for i, product in enumerate(products, 1):
        title = product.get('title', f'Product {i}')
        log_and_status(
            status_fn,
            f"Processing product {i}/{total}: {title[:60]}...",
            ui_msg=f"Enhancing with {provider_name}: {i}/{total}"
        )

        # Check cache
        product_hash = compute_product_hash(product)
        cache_key = product.get('id', product.get('handle', title))

        if cache_key in cached_products:
            cached_data = cached_products[cache_key]
            if cached_data.get('input_hash') == product_hash:
                # Use cached enhancement
                log_and_status(status_fn, f"  ♻️  Using cached enhancement")

                enhanced_product = product.copy()
                enhanced_product['product_type'] = cached_data.get('department', '')

                tags = []
                if cached_data.get('category'):
                    tags.append(cached_data['category'])
                if cached_data.get('subcategory'):
                    tags.append(cached_data['subcategory'])

                enhanced_product['tags'] = tags
                enhanced_product['body_html'] = cached_data.get('enhanced_description', product.get('body_html', ''))

                # Restore Shopify category ID from cache
                enhanced_product['shopify_category_id'] = cached_data.get('shopify_category_id', None)

                enhanced_products.append(enhanced_product)
                cached_count += 1
                continue

        # Not in cache or changed - enhance with AI
        try:
            enhanced_product = enhance_product(
                product,
                taxonomy_doc,
                voice_tone_doc,
                cfg,
                shopify_categories=None,  # Deprecated - using taxonomy_mappings now
                status_fn=status_fn,
                taxonomy_mappings=taxonomy_mappings
            )

            # Save to cache
            cached_products[cache_key] = {
                "enhanced_at": datetime.now().isoformat(),
                "input_hash": product_hash,
                "provider": provider,
                "model": model,
                "department": enhanced_product.get('product_type', ''),
                "category": enhanced_product.get('tags', [])[0] if enhanced_product.get('tags') else '',
                "subcategory": enhanced_product.get('tags', [])[1] if len(enhanced_product.get('tags', [])) > 1 else '',
                "enhanced_description": enhanced_product.get('body_html', ''),
                "shopify_category_id": enhanced_product.get('shopify_category_id', None)
            }
            enhanced_count += 1

            enhanced_products.append(enhanced_product)

        except Exception as e:
            # AI API failed - stop processing immediately
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, "=" * 80, "error")
            log_and_status(status_fn, f"❌ {provider_name} API ENHANCEMENT FAILED", "error")
            log_and_status(status_fn, "=" * 80, "error")
            log_and_status(status_fn, f"Product that failed: {title}", "error")
            log_and_status(status_fn, f"Product index: {i}/{total}", "error")
            log_and_status(status_fn, f"Error: {str(e)}", "error")
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, "Processing stopped to prevent data issues.", "error")
            log_and_status(status_fn, "Check the log file for detailed error information.", "error")
            log_and_status(status_fn, "=" * 80, "error")

            # Save cache before stopping
            cache["products"] = cached_products
            save_cache(cache)

            # Re-raise to stop processing
            raise

        # Rate limiting: ~10 requests per minute for Claude, similar for OpenAI
        if i % 5 == 0 and i < total:
            log_and_status(status_fn, f"  ⏸️  Rate limit pause (5 products processed)...")
            time.sleep(6)  # 6 second pause every 5 products

        log_and_status(status_fn, "")  # Empty line between products

    # Save cache
    cache["products"] = cached_products
    save_cache(cache)

    # Summary
    logging.info("=" * 80)
    logging.info(f"BATCH AI ENHANCEMENT COMPLETE")
    logging.info(f"Provider: {provider_name}")
    logging.info(f"Newly enhanced: {enhanced_count}")
    logging.info(f"Used cache: {cached_count}")
    logging.info(f"Total processed: {total}")
    logging.info("=" * 80)

    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, f"{provider_name} ENHANCEMENT SUMMARY")
    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, f"✅ Newly enhanced: {enhanced_count}")
    log_and_status(status_fn, f"♻️  Used cache: {cached_count}")
    log_and_status(status_fn, f"📊 Total processed: {total}")

    return enhanced_products
