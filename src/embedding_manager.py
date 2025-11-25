"""
Embedding Manager for Semantic Search

This module handles OpenAI embeddings for Shopify taxonomy semantic search.
Uses text-embedding-3-large for highest accuracy in tax-critical category assignment.

Key Features:
- Generate embeddings for all Shopify categories
- Cache embeddings to disk (~120MB)
- Auto-regenerate when taxonomy changes
- Semantic search for top K most relevant categories
"""

import os
import pickle
import logging
import numpy as np
from typing import List, Dict, Tuple
from datetime import datetime
from openai import OpenAI


def generate_embeddings_for_taxonomy(
    shopify_categories: List[Dict],
    api_key: str,
    model: str = "text-embedding-3-large"
) -> List[Dict]:
    """
    Generate embeddings for all Shopify categories using OpenAI API.

    Args:
        shopify_categories: List of Shopify category dicts with 'fullName' and 'id'
        api_key: OpenAI API key
        model: Embedding model to use (default: text-embedding-3-large)

    Returns:
        List of dicts with 'category' and 'embedding' keys

    Cost: ~$0.03 for 11,764 categories (235K tokens @ $0.13/1M)
    Time: ~30 seconds (batch processing)
    """
    client = OpenAI(api_key=api_key)

    # Prepare category texts
    texts = [cat['fullName'] for cat in shopify_categories]

    logging.info(f"Generating embeddings for {len(texts)} categories using {model}...")

    # Batch embed (OpenAI handles up to 2048 inputs per call)
    all_embeddings = []
    batch_size = 2048

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]

        logging.info(f"  Processing batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}...")

        response = client.embeddings.create(
            model=model,
            input=batch_texts
        )

        batch_embeddings = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embeddings)

        logging.info(f"  ✅ Generated embeddings for {i+len(batch_texts)}/{len(texts)} categories")

    # Combine categories with their embeddings
    results = []
    for cat, embedding in zip(shopify_categories, all_embeddings):
        results.append({
            'category': cat,
            'embedding': np.array(embedding, dtype=np.float32)  # Save memory
        })

    return results


def save_embeddings_cache(cache_data: Dict, cache_path: str) -> None:
    """
    Save embeddings cache to disk.

    Args:
        cache_data: Dict with version, hash, model, created_at, embeddings
        cache_path: Path to save cache file (e.g., cache/shopify_embeddings.pkl)
    """
    # Ensure cache directory exists
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    with open(cache_path, 'wb') as f:
        pickle.dump(cache_data, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Get file size for logging
    file_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
    logging.info(f"💾 Saved embeddings cache: {cache_path} ({file_size_mb:.1f} MB)")


def load_embeddings_cache(cache_path: str) -> Dict:
    """
    Load embeddings cache from disk.

    Args:
        cache_path: Path to cache file

    Returns:
        Cache dict with version, hash, model, created_at, embeddings
        Returns None if file doesn't exist or is invalid
    """
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'rb') as f:
            cache_data = pickle.load(f)

        # Validate cache structure
        required_keys = ['version', 'shopify_taxonomy_hash', 'embedding_model', 'embeddings']
        if not all(key in cache_data for key in required_keys):
            logging.warning(f"⚠️  Invalid cache structure in {cache_path}")
            return None

        file_size_mb = os.path.getsize(cache_path) / (1024 * 1024)
        logging.info(f"📂 Loaded embeddings cache: {cache_path} ({file_size_mb:.1f} MB)")

        return cache_data

    except Exception as e:
        logging.error(f"❌ Failed to load embeddings cache: {e}")
        return None


def get_or_regenerate_embeddings(
    shopify_categories: List[Dict],
    api_key: str,
    force_refresh: bool = False,
    model: str = "text-embedding-3-large",
    cache_path: str = "cache/shopify_embeddings.pkl",
    status_fn=None
) -> List[Dict]:
    """
    Load embeddings from cache, or regenerate if taxonomy/model changed.

    Args:
        shopify_categories: Full Shopify taxonomy
        api_key: OpenAI API key
        force_refresh: Force regeneration even if cache is valid
        model: Embedding model to use
        cache_path: Path to cache file
        status_fn: Optional status callback function

    Returns:
        List of embeddings dicts with 'category' and 'embedding' keys

    Cache invalidation triggers:
    - force_refresh=True
    - Taxonomy hash mismatch (Shopify updated categories)
    - Embedding model changed (upgrade)
    - Cache file missing or invalid
    """
    from .taxonomy_mapper import compute_taxonomy_hash

    def log_and_status(status_fn, message):
        """Helper to log and update status."""
        logging.info(message)
        if status_fn:
            status_fn(message)

    current_hash = compute_taxonomy_hash(shopify_categories)

    # Try to load cache
    if not force_refresh:
        cached = load_embeddings_cache(cache_path)

        if cached:
            # Validate cache
            cache_hash = cached.get('shopify_taxonomy_hash')
            cache_model = cached.get('embedding_model')

            if cache_hash == current_hash and cache_model == model:
                num_embeddings = len(cached['embeddings'])
                log_and_status(status_fn, f"✅ Using cached embeddings ({num_embeddings} categories)")
                return cached['embeddings']

            # Cache invalid
            if cache_hash != current_hash:
                log_and_status(status_fn, "⚠️  Taxonomy changed - regenerating embeddings...")
            elif cache_model != model:
                log_and_status(status_fn, f"⚠️  Model changed ({cache_model} → {model}) - regenerating embeddings...")
        else:
            log_and_status(status_fn, "📝 No embedding cache found - generating embeddings...")
    else:
        log_and_status(status_fn, "🔄 Force refresh enabled - regenerating embeddings...")

    # Generate embeddings (one-time $0.03 cost)
    log_and_status(status_fn, f"🔄 Generating embeddings for {len(shopify_categories)} categories...")
    log_and_status(status_fn, f"   Model: {model}")
    log_and_status(status_fn, f"   Cost: ~$0.03 (one-time)")
    log_and_status(status_fn, f"   Time: ~30 seconds...")

    embeddings = generate_embeddings_for_taxonomy(shopify_categories, api_key, model)

    # Save to cache
    cache_data = {
        'version': '1.0',
        'shopify_taxonomy_hash': current_hash,
        'embedding_model': model,
        'created_at': datetime.now().isoformat(),
        'embeddings': embeddings
    }
    save_embeddings_cache(cache_data, cache_path)

    log_and_status(status_fn, f"✅ Generated and cached {len(embeddings)} embeddings")

    return embeddings


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        a: First vector (numpy array)
        b: Second vector (numpy array)

    Returns:
        Similarity score between -1 and 1 (higher = more similar)
    """
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def find_relevant_categories(
    product: Dict,
    our_category: str,
    cached_embeddings: List[Dict],
    api_key: str,
    model: str = "text-embedding-3-large",
    top_k: int = 50
) -> List[Dict]:
    """
    Find top K most relevant Shopify categories using semantic search.

    Args:
        product: Product dict with title, descriptionHtml, etc.
        our_category: Our internal taxonomy category (e.g., "Landscape and Construction > Pavers")
        cached_embeddings: Pre-computed embeddings for all Shopify categories
        api_key: OpenAI API key
        model: Embedding model to use (must match cached embeddings)
        top_k: Number of top matches to return

    Returns:
        List of top K most relevant Shopify category dicts

    Cost: ~$0.000007 per search (50 tokens @ $0.13/1M)
    Time: ~200ms (API call + similarity computation)
    """
    client = OpenAI(api_key=api_key)

    # Build search query with product context
    # Include our category, product title, and description snippet
    description = product.get('descriptionHtml', '') or product.get('description_1', '')
    if len(description) > 500:
        description = description[:500] + "..."

    query = f"""Category: {our_category}
Product: {product.get('title', '')}
Description: {description}"""

    logging.debug(f"🔍 Semantic search query: {query[:200]}...")

    # Generate query embedding
    response = client.embeddings.create(
        model=model,
        input=[query]
    )
    query_embedding = np.array(response.data[0].embedding, dtype=np.float32)

    # Compute cosine similarity with all cached embeddings
    similarities: List[Tuple[float, Dict]] = []
    for item in cached_embeddings:
        cat_embedding = item['embedding']
        similarity = cosine_similarity(query_embedding, cat_embedding)
        similarities.append((similarity, item['category']))

    # Sort by similarity (highest first) and return top K
    similarities.sort(reverse=True, key=lambda x: x[0])
    top_categories = [cat for _, cat in similarities[:top_k]]

    # Log top matches
    logging.info(f"🔍 Semantic search found {len(top_categories)} relevant categories")
    logging.info(f"   Top match: {top_categories[0]['fullName']} (similarity: {similarities[0][0]:.3f})")
    if len(top_categories) > 1:
        logging.info(f"   2nd match: {top_categories[1]['fullName']} (similarity: {similarities[1][0]:.3f})")
    if len(top_categories) > 2:
        logging.info(f"   3rd match: {top_categories[2]['fullName']} (similarity: {similarities[2][0]:.3f})")

    return top_categories
