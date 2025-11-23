"""
Intelligent Shopify taxonomy mapping with AI-powered one-time mapping and smart caching.

This module creates a mapping between our internal product taxonomy and Shopify's
standard product taxonomy using AI. The mapping is cached and only regenerated when
either taxonomy changes.

Key Features:
- One-time AI mapping (not per-product)
- Hash-based change detection
- Smart caching (only re-map when taxonomies change)
- High-confidence mappings at the lowest taxonomy level
"""

import json
import logging
import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .config import log_and_status


# Cache file for taxonomy mappings
MAPPING_CACHE_FILE = "cache/taxonomy_mapping.json"


def compute_file_hash(file_path: str) -> str:
    """
    Compute SHA256 hash of a file's contents.

    Args:
        file_path: Path to file

    Returns:
        SHA256 hash as hex string
    """
    if not os.path.exists(file_path):
        return ""

    try:
        with open(file_path, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()
    except Exception as e:
        logging.warning(f"Failed to hash file {file_path}: {e}")
        return ""


def compute_taxonomy_hash(categories: List[Dict]) -> str:
    """
    Compute hash of Shopify taxonomy categories list.

    Args:
        categories: List of Shopify category dicts with 'id' and 'fullName'

    Returns:
        SHA256 hash as hex string
    """
    # Sort categories by fullName for consistent hashing
    sorted_cats = sorted(categories, key=lambda c: c.get('fullName', ''))

    # Create stable string representation
    content = json.dumps([
        {'id': c.get('id'), 'fullName': c.get('fullName')}
        for c in sorted_cats
    ], sort_keys=True)

    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def load_our_taxonomy(taxonomy_path: str) -> List[str]:
    """
    Parse our internal taxonomy from PRODUCT_TAXONOMY.md.

    Extracts all category paths in format:
    "Department > Category > Subcategory"

    Args:
        taxonomy_path: Path to PRODUCT_TAXONOMY.md file

    Returns:
        List of category path strings
    """
    if not os.path.exists(taxonomy_path):
        logging.error(f"Taxonomy file not found: {taxonomy_path}")
        return []

    categories = []
    current_department = None
    current_category = None

    try:
        with open(taxonomy_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse markdown structure
        lines = content.split('\n')

        for line in lines:
            line = line.strip()

            # Department level (## headers)
            if line.startswith('**Product Type:**'):
                # Extract department from **Product Type:** `Department Name`
                start = line.find('`') + 1
                end = line.rfind('`')
                if start > 0 and end > start:
                    current_department = line[start:end]
                    logging.debug(f"Found department: {current_department}")

            # Category level (#### headers)
            elif line.startswith('####') and current_department:
                current_category = line.replace('####', '').strip()
                # Add department > category
                categories.append(f"{current_department} > {current_category}")
                logging.debug(f"Found category: {current_department} > {current_category}")

            # Subcategory level (numbered lists under category)
            elif line and current_department and current_category:
                # Look for subcategory markers like "1. **Slabs**" or "- **Tags:** `Category`, `Subcategory`"
                if line.startswith(('1. ', '2. ', '3. ', '4. ', '5. ', '6. ', '7. ', '8. ', '9. ', '10. ')):
                    # Extract subcategory name
                    subcategory = line.split('.', 1)[1].strip()

                    # Handle different formats
                    if subcategory.startswith('**'):
                        # Format: 1. **Slabs**
                        subcategory = subcategory.replace('**', '').strip()
                    elif 'Tags:' in subcategory:
                        # Format: - **Tags:** `Category`, `Subcategory`
                        continue  # Skip tag lines

                    # Remove any trailing description text
                    if '\n' in subcategory:
                        subcategory = subcategory.split('\n')[0].strip()

                    # Add department > category > subcategory
                    full_path = f"{current_department} > {current_category} > {subcategory}"
                    categories.append(full_path)
                    logging.debug(f"Found subcategory: {full_path}")

        logging.info(f"Parsed {len(categories)} category paths from taxonomy")
        return categories

    except Exception as e:
        logging.error(f"Failed to parse taxonomy file: {e}")
        return []


def load_mapping_cache() -> Optional[Dict]:
    """
    Load cached taxonomy mapping from disk.

    Returns:
        Cached mapping dict or None if cache doesn't exist or is invalid
    """
    if not os.path.exists(MAPPING_CACHE_FILE):
        return None

    try:
        with open(MAPPING_CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)

        # Validate cache structure
        required_keys = ['version', 'shopify_taxonomy_hash', 'our_taxonomy_hash', 'mappings', 'created_at']
        if all(key in cache for key in required_keys):
            return cache
        else:
            logging.warning(f"Invalid cache structure in {MAPPING_CACHE_FILE}")
            return None

    except Exception as e:
        logging.warning(f"Failed to load mapping cache: {e}")
        return None


def save_mapping_cache(cache: Dict):
    """
    Save taxonomy mapping cache to disk.

    Args:
        cache: Mapping cache dictionary

    Raises:
        Exception: If cache save fails for any reason
    """
    try:
        # Ensure cache directory exists
        cache_dir = os.path.dirname(MAPPING_CACHE_FILE)
        os.makedirs(cache_dir, exist_ok=True)
        logging.debug(f"Cache directory exists: {cache_dir}")

        # Write cache to file
        logging.debug(f"Writing cache with {len(cache.get('mappings', {}))} mappings to {MAPPING_CACHE_FILE}")
        with open(MAPPING_CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)

        # Validate file was created and has content
        if not os.path.exists(MAPPING_CACHE_FILE):
            raise IOError(f"Cache file was not created at {MAPPING_CACHE_FILE}")

        file_size = os.path.getsize(MAPPING_CACHE_FILE)
        if file_size == 0:
            raise IOError(f"Cache file is empty: {MAPPING_CACHE_FILE}")

        logging.info(f"✅ Saved taxonomy mapping cache to {MAPPING_CACHE_FILE} ({file_size} bytes)")

    except Exception as e:
        logging.error(f"❌ Failed to save mapping cache: {e}")
        # Re-raise to ensure caller knows about the failure
        raise


def needs_remapping(
    our_taxonomy_hash: str,
    shopify_taxonomy_hash: str,
    cache: Optional[Dict]
) -> bool:
    """
    Determine if taxonomy mapping needs to be regenerated.

    Args:
        our_taxonomy_hash: Hash of our internal taxonomy
        shopify_taxonomy_hash: Hash of Shopify taxonomy
        cache: Existing cache or None

    Returns:
        True if remapping is needed, False if cache is valid
    """
    if cache is None:
        logging.info("No cache found - mapping needed")
        return True

    cached_our_hash = cache.get('our_taxonomy_hash', '')
    cached_shopify_hash = cache.get('shopify_taxonomy_hash', '')

    if cached_our_hash != our_taxonomy_hash:
        logging.info("Our taxonomy changed - remapping needed")
        return True

    if cached_shopify_hash != shopify_taxonomy_hash:
        logging.info("Shopify taxonomy changed - remapping needed")
        return True

    logging.info("Cache is valid - using existing mappings")
    return False


def create_ai_mapping_prompt(
    our_categories: List[str],
    shopify_categories: List[Dict]
) -> str:
    """
    Create prompt for AI to map our taxonomy to Shopify's taxonomy.

    Args:
        our_categories: List of our category paths
        shopify_categories: List of Shopify category dicts

    Returns:
        Prompt string for AI
    """
    # Group Shopify categories by top-level for easier navigation
    shopify_by_top = {}
    for cat in shopify_categories:
        full_name = cat.get('fullName', '')
        top_level = full_name.split(' > ')[0] if ' > ' in full_name else full_name

        if top_level not in shopify_by_top:
            shopify_by_top[top_level] = []

        shopify_by_top[top_level].append({
            'id': cat.get('id'),
            'fullName': full_name
        })

    # Build Shopify taxonomy text (grouped and truncated for token efficiency)
    shopify_text = "SHOPIFY STANDARD PRODUCT TAXONOMY:\n\n"
    for top_level in sorted(shopify_by_top.keys())[:50]:  # Limit to 50 top-level categories
        shopify_text += f"{top_level}:\n"
        for cat in shopify_by_top[top_level][:100]:  # Limit subcategories per top-level
            shopify_text += f"  - {cat['fullName']} [ID: {cat['id']}]\n"

        if len(shopify_by_top[top_level]) > 100:
            shopify_text += f"  ... and {len(shopify_by_top[top_level]) - 100} more\n"
        shopify_text += "\n"

    # Build our categories text
    our_text = "OUR INTERNAL TAXONOMY (to be mapped):\n\n"
    for cat_path in our_categories:
        our_text += f"- {cat_path}\n"

    prompt = f"""You are a product taxonomy mapping expert. Your task is to map our internal product taxonomy to Shopify's Standard Product Taxonomy.

{our_text}

{shopify_text}

INSTRUCTIONS:

For each of our internal taxonomy paths, find the BEST matching Shopify category using a BOTTOM-UP search strategy.

MAPPING STRATEGY (CRITICAL):
1. **START WITH THE RIGHTMOST/MOST SPECIFIC TERM** (the leaf category)
   Example: For "Landscape and Construction > Aggregates > Sand"
   - Extract the specific term: "Sand"
   - Search Shopify taxonomy for exact or semantic matches to "Sand"
   - Found: "Home & Garden > Lawn & Garden > Gardening > Sands & Soils > Sand" ✅

2. **Validate the match makes semantic sense**
   - Does the Shopify category path align with the product type?
   - Is this the most specific level available?

3. **Only use broader categories if no specific match exists**
   - If "Sand" had no specific match, then consider "Aggregates" or "Landscape and Construction"

4. **Assign confidence level:**
   - "high": Exact term match at deepest level (e.g., "Sand" → "...> Sand")
   - "medium": Semantic match but not exact term
   - "low": Had to use broader/generic category

EXAMPLES:
- "Landscape and Construction > Aggregates > Sand" → Search for "Sand" → "Home & Garden > Lawn & Garden > Gardening > Sands & Soils > Sand" (high)
- "Landscape and Construction > Aggregates > Soil" → Search for "Soil" → "Home & Garden > Lawn & Garden > Gardening > Sands & Soils > Soil" (high)
- "Pet Supplies > Dogs > Collars" → Search for "Collars" → "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Collars & Leashes > Dog Collars" (high)

OUTPUT FORMAT (valid JSON only, no markdown):

{{
  "Our Category > Path > Here": {{
    "shopify_category": "Shopify > Category > Path",
    "shopify_id": "gid://shopify/TaxonomyCategory/...",
    "confidence": "high|medium|low",
    "reasoning": "Brief explanation of match"
  }},
  ...
}}

CRITICAL REQUIREMENTS:
- Return ONLY valid JSON (no markdown, no code blocks, no extra text)
- Map ALL {len(our_categories)} of our categories
- ⚠️  ONLY use Shopify category IDs that appear in the list above
- ⚠️  DO NOT fabricate or guess category IDs - they must exist in the provided list
- ⚠️  DO NOT create IDs by pattern matching (e.g., hg-5-4-9) - validate they exist!
- Be specific - prefer deeper category levels when available
- If uncertain about an ID, verify it exists in the Shopify list before using it

VALIDATION:
Your response will be validated against the Shopify taxonomy. Any hallucinated IDs that don't exist will cause mapping failures.

Begin mapping:"""

    return prompt


def generate_taxonomy_mapping_with_ai(
    our_categories: List[str],
    shopify_categories: List[Dict],
    api_key: str,
    provider: str = "claude",
    model: str = None,
    status_fn=None
) -> Dict:
    """
    Use AI to create intelligent mapping from our taxonomy to Shopify's taxonomy.

    Args:
        our_categories: List of our category path strings
        shopify_categories: List of Shopify category dicts
        api_key: AI provider API key
        provider: "claude" or "openai"
        model: Model to use (optional, uses defaults)
        status_fn: Optional status update function

    Returns:
        Mapping dictionary: {our_category_path: {shopify_category, shopify_id, confidence, reasoning}}

    Raises:
        Exception: If API call fails
    """
    if status_fn:
        log_and_status(status_fn, f"🤖 Using AI to map {len(our_categories)} categories to Shopify taxonomy...")
    else:
        logging.info(f"🤖 Using AI to map {len(our_categories)} categories to Shopify taxonomy...")

    prompt = create_ai_mapping_prompt(our_categories, shopify_categories)

    try:
        if provider == "claude":
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError("anthropic package not installed")

            client = Anthropic(api_key=api_key)
            model = model or "claude-sonnet-4-5-20250929"

            logging.info(f"Calling Claude API ({model}) for taxonomy mapping...")

            response = client.messages.create(
                model=model,
                max_tokens=16000,  # Large output needed for many mappings
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text.strip()

            # Calculate cost
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cost = (input_tokens * 0.003 / 1000) + (output_tokens * 0.015 / 1000)

            logging.info(f"✅ Claude API call successful")
            logging.info(f"Token usage - Input: {input_tokens}, Output: {output_tokens}")
            logging.info(f"Cost: ${cost:.4f}")

        elif provider == "openai":
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError("openai package not installed")

            client = OpenAI(api_key=api_key)
            model = model or "gpt-4o"

            logging.info(f"Calling OpenAI API ({model}) for taxonomy mapping...")

            # GPT-5 models have different parameter requirements
            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }

            if model.startswith("gpt-5"):
                # GPT-5: uses max_completion_tokens, temperature must be 1 (default)
                # Use higher limit for taxonomy mapping (114 categories with reasoning = ~30K tokens)
                api_params["max_completion_tokens"] = 64000
                # Note: GPT-5 only supports temperature=1 (default), so we omit it
                # GPT-5 supports up to 128K output tokens, but we use 64K to be conservative
            else:
                # GPT-4 and earlier: use max_tokens and temperature=0 for deterministic output
                api_params["max_tokens"] = 16000
                api_params["temperature"] = 0

            response = client.chat.completions.create(**api_params)

            # Extract response content with detailed error handling
            choice = response.choices[0]
            message = choice.message

            # Log response details for debugging
            logging.debug(f"Response choice: {choice}")
            logging.debug(f"Finish reason: {choice.finish_reason}")
            logging.debug(f"Message content type: {type(message.content)}")
            logging.debug(f"Message content is None: {message.content is None}")

            result_text = message.content.strip() if message.content else ""

            # Calculate cost (approximate)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            # Check for empty response
            if not result_text:
                logging.error(f"❌ OpenAI returned empty response!")
                logging.error(f"Finish reason: {choice.finish_reason}")
                logging.error(f"Response ID: {response.id}")
                logging.error(f"Output tokens: {output_tokens}")
                if hasattr(message, 'refusal') and message.refusal:
                    logging.error(f"Refusal: {message.refusal}")
                raise ValueError(f"OpenAI returned empty response (finish_reason: {choice.finish_reason})")

            # Check if response was truncated due to token limit
            if choice.finish_reason == "length":
                logging.warning(f"⚠️  Response may be truncated (finish_reason=length)")
                logging.warning(f"Output tokens: {output_tokens}, likely hit max_completion_tokens limit")
                logging.warning(f"Consider increasing max_completion_tokens for complete response")
            cost = (input_tokens * 0.0025 / 1000) + (output_tokens * 0.01 / 1000)  # GPT-4o pricing

            logging.info(f"✅ OpenAI API call successful")
            logging.info(f"Token usage - Input: {input_tokens}, Output: {output_tokens}")
            logging.info(f"Cost: ${cost:.4f}")
            logging.info(f"Finish reason: {choice.finish_reason}")
            logging.info(f"Response length: {len(result_text)} characters")

        else:
            raise ValueError(f"Unknown AI provider: {provider}")

        # Log raw response for debugging (first 500 chars)
        logging.debug(f"Raw AI response (first 500 chars): {result_text[:500]}")
        logging.debug(f"Response length: {len(result_text)} characters")

        # Parse JSON response
        try:
            # Remove markdown code blocks if present
            cleaned_text = result_text
            if result_text.startswith("```"):
                logging.debug("Removing markdown code blocks from response")
                lines = result_text.split('\n')
                cleaned_text = '\n'.join(lines[1:-1])

            # Attempt JSON parse
            logging.debug("Parsing JSON response...")
            mappings = json.loads(cleaned_text)

            if not isinstance(mappings, dict):
                raise ValueError(f"Expected dict, got {type(mappings).__name__}")

            logging.info(f"✅ Successfully parsed {len(mappings)} mappings from AI response")

        except json.JSONDecodeError as e:
            logging.error(f"❌ Failed to parse AI response as JSON: {e}")
            logging.error(f"Response text (first 1000 chars): {result_text[:1000]}")
            logging.error(f"Response text (last 500 chars): {result_text[-500:]}")
            raise ValueError(f"AI returned invalid JSON: {e}") from e

        # Validate mappings structure
        logging.debug("Validating mapping structure and Shopify IDs...")

        # Create set of valid Shopify taxonomy IDs for quick lookup
        valid_shopify_ids = {cat.get('id') for cat in shopify_categories if cat.get('id')}
        logging.debug(f"Loaded {len(valid_shopify_ids)} valid Shopify category IDs for validation")

        valid_mappings = {}
        invalid_count = 0
        hallucinated_ids = 0

        for category, mapping in mappings.items():
            required_keys = ['shopify_category', 'shopify_id', 'confidence']

            if not isinstance(mapping, dict):
                logging.warning(f"❌ Invalid mapping for '{category}': not a dict (got {type(mapping).__name__})")
                invalid_count += 1
                continue

            missing_keys = [key for key in required_keys if key not in mapping]
            if missing_keys:
                logging.warning(f"❌ Invalid mapping for '{category}': missing keys {missing_keys}")
                invalid_count += 1
                continue

            # Validate that the Shopify ID actually exists in the taxonomy
            shopify_id = mapping.get('shopify_id')
            if shopify_id and shopify_id != "None" and shopify_id not in valid_shopify_ids:
                logging.warning(f"❌ Hallucinated ID for '{category}': {mapping.get('shopify_category')} ({shopify_id}) DOES NOT EXIST in Shopify taxonomy!")
                invalid_count += 1
                hallucinated_ids += 1
                continue

            # Valid mapping
            valid_mappings[category] = mapping
            logging.debug(f"✅ Valid mapping: {category} -> {mapping.get('shopify_category')} (confidence: {mapping.get('confidence')})")

        # Report validation results
        if invalid_count > 0:
            logging.warning(f"⚠️  {invalid_count} mappings failed validation")
            if hallucinated_ids > 0:
                logging.error(f"🚨 {hallucinated_ids} HALLUCINATED IDs detected - these categories DO NOT EXIST in Shopify!")

        if len(valid_mappings) == 0:
            raise ValueError("No valid mappings found in AI response - all mappings failed validation")

        if status_fn:
            log_and_status(status_fn, f"✅ AI mapped {len(valid_mappings)}/{len(our_categories)} categories")
        else:
            logging.info(f"✅ AI mapped {len(valid_mappings)}/{len(our_categories)} categories")

        # Log summary by confidence
        confidence_counts = {"high": 0, "medium": 0, "low": 0, "null": 0}
        for mapping in valid_mappings.values():
            conf = mapping.get('confidence', 'low')
            if mapping.get('shopify_id') is None:
                confidence_counts['null'] += 1
            else:
                confidence_counts[conf] += 1

        logging.info(f"Mapping confidence breakdown: {confidence_counts}")

        return valid_mappings

    except Exception as e:
        logging.error(f"❌ AI taxonomy mapping failed: {e}")
        logging.exception("Full traceback:")
        raise


def get_or_create_taxonomy_mapping(
    our_taxonomy_path: str,
    shopify_categories: List[Dict],
    api_key: str,
    provider: str = "claude",
    model: str = None,
    status_fn=None,
    force_remap: bool = False
) -> Dict:
    """
    Get cached taxonomy mapping or create new one if needed.

    This is the main entry point for taxonomy mapping. It:
    1. Computes hashes of both taxonomies
    2. Checks if cache is valid
    3. Returns cached mappings if valid, or generates new ones if needed

    Args:
        our_taxonomy_path: Path to PRODUCT_TAXONOMY.md
        shopify_categories: List of Shopify category dicts from GitHub
        api_key: AI provider API key
        provider: "claude" or "openai"
        model: AI model to use (optional)
        status_fn: Optional status update function
        force_remap: Force remapping even if cache is valid

    Returns:
        Dictionary mapping our categories to Shopify categories

    Raises:
        Exception: If mapping generation fails
    """
    # Compute hashes
    our_taxonomy_hash = compute_file_hash(our_taxonomy_path)
    shopify_taxonomy_hash = compute_taxonomy_hash(shopify_categories)

    logging.info(f"Our taxonomy hash: {our_taxonomy_hash[:12]}...")
    logging.info(f"Shopify taxonomy hash: {shopify_taxonomy_hash[:12]}...")

    # Load existing cache
    cache = load_mapping_cache()

    # Check if remapping is needed
    if force_remap:
        logging.info("Force remap requested")
        needs_remap = True
    else:
        needs_remap = needs_remapping(our_taxonomy_hash, shopify_taxonomy_hash, cache)

    if not needs_remap and cache:
        if status_fn:
            log_and_status(status_fn, f"✅ Using cached taxonomy mappings ({len(cache['mappings'])} categories)")
        logging.info(f"Using cached taxonomy mappings from {cache.get('created_at')}")
        return cache['mappings']

    # Need to generate new mappings
    if status_fn:
        log_and_status(status_fn, "🔄 Generating new taxonomy mappings with AI...")

    # Load our taxonomy
    our_categories = load_our_taxonomy(our_taxonomy_path)

    if not our_categories:
        raise ValueError(f"Failed to load categories from {our_taxonomy_path}")

    # Generate mappings with AI
    mappings = generate_taxonomy_mapping_with_ai(
        our_categories,
        shopify_categories,
        api_key,
        provider,
        model,
        status_fn
    )

    # Validate mappings were generated
    if not mappings:
        raise ValueError("AI mapping generation returned empty mappings")

    if len(mappings) == 0:
        raise ValueError("AI mapping generation returned zero mappings")

    logging.info(f"Generated {len(mappings)} taxonomy mappings")

    # Create new cache
    new_cache = {
        'version': '1.0',
        'shopify_taxonomy_hash': shopify_taxonomy_hash,
        'our_taxonomy_hash': our_taxonomy_hash,
        'provider': provider,
        'model': model or 'default',
        'created_at': datetime.now().isoformat(),
        'category_count': len(our_categories),
        'mapped_count': len(mappings),
        'mappings': mappings
    }

    # Save cache (will raise exception if save fails)
    save_mapping_cache(new_cache)

    # Verify cache file was created
    if not os.path.exists(MAPPING_CACHE_FILE):
        raise IOError(f"Cache file was not created after save: {MAPPING_CACHE_FILE}")

    # Verify we can load it back
    verification_cache = load_mapping_cache()
    if not verification_cache:
        raise IOError(f"Cache file was created but cannot be loaded: {MAPPING_CACHE_FILE}")

    if len(verification_cache.get('mappings', {})) != len(mappings):
        raise ValueError(
            f"Cache verification failed: expected {len(mappings)} mappings, "
            f"but loaded {len(verification_cache.get('mappings', {}))}"
        )

    logging.info(f"✅ Cache verified: {len(mappings)} mappings saved and loaded successfully")

    return mappings


def lookup_shopify_category(
    department: str,
    category: str,
    subcategory: str,
    mappings: Dict
) -> Optional[str]:
    """
    Look up Shopify category ID for our internal taxonomy path.

    Tries multiple lookup strategies:
    1. Full path: Department > Category > Subcategory
    2. Department > Category (if subcategory not found)
    3. Department (if category not found)

    Args:
        department: Department name
        category: Category name
        subcategory: Subcategory name (can be empty)
        mappings: Taxonomy mappings dictionary

    Returns:
        Shopify category GID or None if no mapping found
    """
    # Try full path first
    if subcategory:
        full_path = f"{department} > {category} > {subcategory}"
        if full_path in mappings:
            mapping = mappings[full_path]
            if mapping.get('shopify_id'):
                logging.debug(f"Found mapping for full path: {full_path} -> {mapping['shopify_category']}")
                return mapping['shopify_id']

    # Try department > category
    cat_path = f"{department} > {category}"
    if cat_path in mappings:
        mapping = mappings[cat_path]
        if mapping.get('shopify_id'):
            logging.debug(f"Found mapping for category path: {cat_path} -> {mapping['shopify_category']}")
            return mapping['shopify_id']

    # Try just department (fallback)
    if department in mappings:
        mapping = mappings[department]
        if mapping.get('shopify_id'):
            logging.debug(f"Found mapping for department: {department} -> {mapping['shopify_category']}")
            return mapping['shopify_id']

    logging.warning(f"No Shopify category mapping found for: {department} > {category} > {subcategory}")
    return None
