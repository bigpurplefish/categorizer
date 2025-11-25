"""
Claude API integration for product taxonomy assignment and description rewriting.
"""

import os
import json
import logging
import hashlib
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional

try:
    import anthropic
except ImportError:
    anthropic = None
    logging.warning("anthropic package not installed. Claude AI features will be disabled.")

from .config import log_and_status
from .product_utils import (
    format_purchase_options_metafield,
    add_metafield_if_not_exists,
    reorder_product_fields,
    should_calculate_shipping_weight,
    is_non_shipped_category,
    remove_weight_data_from_variants
)


# Cache file location
CACHE_FILE = "claude_enhanced_cache.json"


def load_cache() -> Dict:
    """Load the Claude enhancement cache from disk."""
    if not os.path.exists(CACHE_FILE):
        return {"cache_version": "1.0", "products": {}}

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.warning(f"Failed to load Claude cache: {e}")
        return {"cache_version": "1.0", "products": {}}


def save_cache(cache: Dict):
    """Save the Claude enhancement cache to disk."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Failed to save Claude cache: {e}")


def compute_product_hash(product: Dict) -> str:
    """Compute a hash of the product's title and description to detect changes."""
    title = product.get('title', '')
    # Support both GraphQL (descriptionHtml) and REST (body_html) field names
    body_html = product.get('descriptionHtml') or product.get('body_html', '')
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


def build_taxonomy_prompt(title: str, body_html: str, taxonomy_doc: str, current_weight: float = 0, variant_data: dict = None) -> str:
    """
    Build the prompt for Claude to assign product taxonomy, calculate shipping weight, and determine purchase options.

    Args:
        title: Product title
        body_html: Product description (HTML)
        taxonomy_doc: Full taxonomy markdown document
        current_weight: Existing variant weight (if any)
        variant_data: Dict with variant information (dimensions, etc.)

    Returns:
        Formatted prompt string
    """
    # Load packaging weight reference
    packaging_doc = load_markdown_file("/Users/moosemarketer/Code/shared-docs/python/PACKAGING_WEIGHT_REFERENCE.md")

    # Build dimensions info if available
    dimensions_info = ""
    if variant_data and variant_data.get('size_info_metafield'):
        dimensions_info = f"\n- Dimensions/Size: {variant_data['size_info_metafield']}"

    # Build current weight info
    current_weight_info = ""
    if current_weight > 0:
        current_weight_info = f"\n- Current variant.weight: {current_weight} lbs"

    prompt = f"""You are a product categorization and shipping weight estimation expert. Your tasks:
1. Assign product to correct taxonomy category
2. Determine applicable purchase/fulfillment options based on category
3. Calculate accurate shipping weight (conservative estimate to avoid undercharging)

{taxonomy_doc}

{packaging_doc}

Product to analyze:
- Title: {title}
- Description: {body_html}{dimensions_info}{current_weight_info}

INSTRUCTIONS:

**STEP 1: TAXONOMY ASSIGNMENT**
Analyze the product and assign to Department, Category, and Subcategory from taxonomy above.

**STEP 2: PURCHASE OPTIONS**
Based on the assigned taxonomy category/subcategory, determine which purchase options apply (see taxonomy document for mappings).
Purchase options are CATEGORY-DRIVEN, not size or weight dependent.
- Option 1: Delivery (standard shipping)
- Option 2: Store Pickup
- Option 3: Local Delivery (within service area)
- Option 4: White Glove Delivery (premium items)
- Option 5: Customer Pickup Only (hay, bulk items)

**STEP 3: WEIGHT ESTIMATION**
Calculate weight based on whether the product is shipped:

**FIRST: Determine if product is shipped**
- Product IS SHIPPED if option 1 (Delivery) is in purchase_options
- Product is NOT SHIPPED if option 1 is NOT in purchase_options

**IF PRODUCT IS NOT SHIPPED:**

   **Case A: Has existing weight (current weight > 0)**
   - Use the existing variant weight as-is (no packaging added)
   - final_shipping_weight = current weight
   - confidence = "high"
   - source = "variant_weight_no_shipping"
   - reasoning = "Product not shipped, using existing weight without packaging"

   **Case B: No existing weight (current weight = 0)**
   - Calculate/estimate product weight using priorities below (B → C → D)
   - Add ONLY product packaging weight (NO shipping packaging)
   - weight = product_weight + product_packaging (NO shipping_packaging, NO 10% margin)
   - final_shipping_weight = weight
   - source = "extracted_from_text_no_shipping" or "calculated_from_dimensions_no_shipping" or "estimated_no_shipping"
   - reasoning = "Product not shipped, calculated weight includes product packaging only (no shipping packaging)"

**IF PRODUCT IS SHIPPED (option 1 in purchase_options):**

   Calculate conservative shipping weight using this EXACT PRIORITY ORDER:

   **PRIORITY A: Use existing variant.weight if available (HIGHEST PRIORITY)**
      - If current weight > 0:
        * product_weight = current weight
        * Apply packaging rules from table above
        * shipping_weight = product_weight + product_packaging + shipping_packaging
        * confidence = "high"
        * source = "variant_weight"

   **PRIORITY B: Extract from text (SECOND PRIORITY)**
      - If weight is mentioned in title/description:
        * Extract weight: "50 lb bag", "25 lbs", "3 oz can"
        * Handle liquid conversions:
          - "5 gallon sealer" → detect material type → convert to lbs
          - "32 fl oz fertilizer" → detect material type → convert to lbs
        * product_weight = extracted/converted weight
        * Apply packaging rules from table above
        * shipping_weight = product_weight + product_packaging + shipping_packaging
        * confidence = "high"
        * source = "extracted_from_text"

   **PRIORITY C: Calculate from dimensions (THIRD PRIORITY, for hardscape products only)**
      - If dimensions are provided (for concrete/hardscape products):
        * Calculate volume in cubic feet: (length_in × width_in × thickness_in) / 1728
        * Estimate product_weight:
          - Concrete/pavers: volume × 150 lbs/ft³
          - Natural stone: volume × 165 lbs/ft³
        * Apply packaging rules from table above
        * shipping_weight = product_weight + product_packaging + shipping_packaging
        * confidence = "high"
        * source = "calculated_from_dimensions"

   **PRIORITY D: Estimate based on context (LOWEST PRIORITY, last resort)**
      - If none of the above available:
        * Estimate based on product type, description, and category context
        * Use comparable products as reference
        * Be CONSERVATIVE (round up)
        * Apply packaging rules from table above
        * shipping_weight = estimated_product_weight + product_packaging + shipping_packaging
        * confidence = "medium" or "low" (use "low" if very uncertain)
        * source = "estimated"

   **CRITICAL WEIGHT RULES (for shipped products only):**
   - Always round UP to nearest 0.5 lb
   - Be conservative - underestimating costs us money
   - Apply 10% safety margin to final weight: final_shipping_weight = shipping_weight × 1.10

**STEP 4: NEEDS REVIEW FLAG**
Set needs_review = true if:
- Weight confidence is "low"
- Product is unusual or doesn't fit standard categories
- Insufficient information to make confident estimates

Return ONLY a valid JSON object in this exact format (no markdown, no code blocks, no explanation):
{{
  "department": "Exact department name from taxonomy",
  "category": "Exact category name from taxonomy",
  "subcategory": "Exact subcategory name from taxonomy (or empty string if none)",
  "reasoning": "Brief explanation of categorization choice",
  "weight_estimation": {{
    "original_weight": {current_weight},
    "product_weight": 39.0,
    "product_packaging_weight": 3.9,
    "shipping_packaging_weight": 5.0,
    "calculated_shipping_weight": 47.9,
    "final_shipping_weight": 52.7,
    "confidence": "high|medium|low",
    "source": "variant_weight|extracted_from_text|calculated_from_dimensions|estimated|variant_weight_no_shipping|extracted_from_text_no_shipping|calculated_from_dimensions_no_shipping|estimated_no_shipping",
    "reasoning": "Explain how you calculated/estimated the weight"
  }},
  "purchase_options": [1, 2, 3, 4, 5],
  "needs_review": false
}}

EXAMPLE 1 - Product that IS SHIPPED (option 1 in purchase_options):
{{
  "department": "Pet Supplies",
  "category": "Dogs",
  "subcategory": "Food",
  "reasoning": "Dog food product",
  "weight_estimation": {{
    "original_weight": 50.0,
    "product_weight": 50.0,
    "product_packaging_weight": 2.5,
    "shipping_packaging_weight": 3.0,
    "calculated_shipping_weight": 55.5,
    "final_shipping_weight": 61.0,
    "confidence": "high",
    "source": "variant_weight",
    "reasoning": "Product is shipped (option 1). Used existing variant.weight of 50 lbs. Added 5% for bag weight (2.5 lbs) + 3 lbs shipping box. Applied 10% safety margin."
  }},
  "purchase_options": [1, 2, 3],
  "needs_review": false
}}

EXAMPLE 2 - Product that is NOT SHIPPED with existing weight (option 1 NOT in purchase_options):
{{
  "department": "Livestock and Farm",
  "category": "Horses",
  "subcategory": "Feed",
  "reasoning": "Hay bale - pickup only",
  "weight_estimation": {{
    "original_weight": 45.0,
    "product_weight": 45.0,
    "product_packaging_weight": 0,
    "shipping_packaging_weight": 0,
    "calculated_shipping_weight": 45.0,
    "final_shipping_weight": 45.0,
    "confidence": "high",
    "source": "variant_weight_no_shipping",
    "reasoning": "Product not shipped (pickup only). Using existing weight without packaging."
  }},
  "purchase_options": [5],
  "needs_review": false
}}

EXAMPLE 3 - Product that is NOT SHIPPED with NO existing weight (option 1 NOT in purchase_options):
{{
  "department": "Landscape and Construction",
  "category": "Aggregates",
  "subcategory": "Mulch",
  "reasoning": "Bulk mulch - pickup only",
  "weight_estimation": {{
    "original_weight": 0,
    "product_weight": 40.0,
    "product_packaging_weight": 0,
    "shipping_packaging_weight": 0,
    "calculated_shipping_weight": 40.0,
    "final_shipping_weight": 40.0,
    "confidence": "medium",
    "source": "estimated_no_shipping",
    "reasoning": "Product not shipped (pickup only). Estimated 1 cubic yard of mulch at ~40 lbs. No packaging added (sold loose/bulk)."
  }},
  "purchase_options": [2, 5],
  "needs_review": false
}}"""

    return prompt


def build_description_prompt(title: str, body_html: str, department: str, voice_tone_doc: str, audience_name: str = None) -> str:
    """
    Build the prompt for Claude to rewrite product description.

    Args:
        title: Product title
        body_html: Current product description (HTML)
        department: Assigned department (for tone selection)
        voice_tone_doc: Full voice and tone guidelines document
        audience_name: Optional target audience name for tailored descriptions

    Returns:
        Formatted prompt string
    """
    audience_context = f"\nTarget Audience: {audience_name}" if audience_name else ""
    audience_instruction = f"AUDIENCE: Tailor this description specifically for {audience_name}. Use language, benefits, and examples that resonate with this audience.\n\n" if audience_name else ""

    prompt = f"""You are a professional product copywriter. Rewrite this product description following our voice and tone guidelines.

{voice_tone_doc}

Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}{audience_context}

{audience_instruction}

Your task:
1. Read the current description to understand the product's features and benefits
2. Apply the tone guidelines for the "{department}" department
3. Rewrite the description following ALL the core requirements:
   - Use second-person voice (addressing the customer directly)
   - Prefer imperative-first phrasing (e.g., "Support...", "Keep...", "Help...")
   - Avoid generic phrases like "premium", "must-have", "high-quality"
   - Focus on benefits and use cases, not just features
   - Ensure proper punctuation (no encoded characters like \u2019)
   - Make it unique and natural (vary your phrasing)

4. SEO Optimization requirements:
   - Include relevant keywords naturally in the first paragraph
   - Use specific, descriptive terms that customers would search for
   - Mention key product attributes (size, material, color, use case) early
   - Focus on search intent (what problem does this solve?)
   - Avoid keyword stuffing - maintain natural, readable language
   - Include semantic variations of key terms

Return ONLY the rewritten description in HTML format. Do not include any explanations, notes, or markdown formatting. Just the HTML content that will go directly into the body_html field."""

    return prompt


def build_collection_description_prompt(collection_title: str, department: str, product_samples: List[str], voice_tone_doc: str) -> str:
    """
    Build the prompt for Claude to generate collection description.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions (body_html) from this collection
        voice_tone_doc: Full voice and tone guidelines document

    Returns:
        Formatted prompt string
    """
    # Limit to 5 product samples to keep prompt size reasonable
    samples_text = "\n\n".join([f"Product {i+1}:\n{sample[:500]}..." for i, sample in enumerate(product_samples[:5])])

    prompt = f"""You are a professional collection copywriter. Write a compelling 100-word description for this product collection.

{voice_tone_doc}

Collection information:
- Collection Name: {collection_title}
- Department: {department}
- Sample products in this collection:

{samples_text}

Your task:
1. Analyze the product samples to understand what this collection offers
2. Apply the tone guidelines for the "{department}" department
3. Write a 100-word collection description following these requirements:
   - Use second-person voice (addressing the customer directly)
   - Prefer imperative-first phrasing when appropriate
   - Avoid generic phrases like "premium", "must-have", "high-quality"
   - Focus on what the collection offers and who it's for
   - Ensure proper punctuation (no encoded characters like \u2019)
   - Make it compelling and natural

4. SEO Optimization requirements:
   - Include the collection name naturally in the first sentence
   - Use specific, descriptive terms that customers would search for
   - Mention key product types and use cases in this collection
   - Focus on search intent (why would someone browse this collection?)
   - Avoid keyword stuffing - maintain natural, readable language
   - Include semantic variations (e.g., "patio slabs" and "outdoor pavers")

5. Length constraint:
   - Must be approximately 100 words (90-110 words is acceptable)
   - Be concise and impactful

Return ONLY the collection description in plain text format. Do not include any explanations, notes, HTML tags, or markdown formatting. Just the plain text description."""

    return prompt


def enhance_product_with_claude(
    product: Dict,
    taxonomy_doc: str,
    voice_tone_doc: str,
    api_key: str,
    model: str,
    status_fn=None,
    audience_config: Dict = None,
    taxonomy_mappings: Dict = None
) -> Dict:
    """
    Enhance a single product using Claude API.

    Args:
        product: Product dictionary
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: Claude API key
        model: Claude model ID
        status_fn: Optional status update function

    Returns:
        Enhanced product dictionary

    Raises:
        Exception: If API call fails or response is invalid
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Cannot enhance products. Install with: pip install anthropic"
        logging.error(error_msg)
        raise ImportError(error_msg)

    title = product.get('title', '')
    # Support both GraphQL (descriptionHtml) and REST (body_html) field names
    body_html = product.get('descriptionHtml') or product.get('body_html', '')

    if not title:
        error_msg = f"Product has no title, cannot enhance: {product}"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        # ========== CHECK FOR VARIANTS NEEDING IMAGES ==========
        # Removed: lifestyle image prompt generation moved to upscaler project
        # No image prompt generation in this module

        # ========== STEP 1: TAXONOMY ASSIGNMENT + WEIGHT ESTIMATION + PURCHASE OPTIONS ==========
        if status_fn:
            log_and_status(status_fn, f"  🤖 Analyzing product and assigning taxonomy for: {title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"CLAUDE API CALL #1: ENHANCED TAXONOMY (TAXONOMY + WEIGHT + PURCHASE OPTIONS)")
        logging.info(f"Product: {title}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        # Get first variant's weight for reference (if product has variants)
        current_weight = 0
        variant_data = None
        if product.get('variants') and len(product['variants']) > 0:
            first_variant = product['variants'][0]
            current_weight = first_variant.get('weight', 0)

            # Extract size_info metafield if exists
            metafields = first_variant.get('metafields', [])
            for mf in metafields:
                if mf.get('key') == 'size_info':
                    variant_data = {'size_info_metafield': mf.get('value', '')}
                    break

        taxonomy_prompt = build_taxonomy_prompt(title, body_html, taxonomy_doc, current_weight, variant_data)

        # Log prompt preview (first 500 chars)
        logging.debug(f"Taxonomy prompt (first 500 chars):\n{taxonomy_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(taxonomy_prompt)} characters")

        # Make API call
        logging.info("Sending taxonomy assignment request to Claude API...")
        taxonomy_response = client.messages.create(
            model=model,
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": taxonomy_prompt
            }]
        )

        # Log response details
        logging.info(f"✅ Taxonomy API call successful")
        logging.info(f"Response ID: {taxonomy_response.id}")
        logging.info(f"Model used: {taxonomy_response.model}")
        logging.info(f"Stop reason: {taxonomy_response.stop_reason}")
        logging.info(f"Token usage - Input: {taxonomy_response.usage.input_tokens}, Output: {taxonomy_response.usage.output_tokens}")

        taxonomy_cost = (taxonomy_response.usage.input_tokens * 0.003 / 1000) + (taxonomy_response.usage.output_tokens * 0.015 / 1000)
        logging.info(f"Cost: ${taxonomy_cost:.6f}")

        # Extract taxonomy from response
        taxonomy_text = taxonomy_response.content[0].text.strip()
        logging.debug(f"Raw taxonomy response:\n{taxonomy_text}")

        # Remove markdown code blocks if present
        if taxonomy_text.startswith("```"):
            logging.debug("Removing markdown code block wrapper from taxonomy response")
            lines = taxonomy_text.split('\n')
            taxonomy_text = '\n'.join(lines[1:-1])

        # Parse JSON response
        try:
            taxonomy_result = json.loads(taxonomy_text)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse taxonomy JSON response: {e}"
            logging.error(error_msg)
            logging.error(f"Raw response text: {taxonomy_text}")
            raise ValueError(f"{error_msg}\nResponse: {taxonomy_text[:200]}...")

        # Validate and extract fields
        department = taxonomy_result.get('department', '')
        category = taxonomy_result.get('category', '')
        subcategory = taxonomy_result.get('subcategory', '')
        reasoning = taxonomy_result.get('reasoning', '')
        weight_estimation = taxonomy_result.get('weight_estimation', {})
        purchase_options = taxonomy_result.get('purchase_options', [])
        needs_review = taxonomy_result.get('needs_review', False)
        # Removed: lifestyle_images_prompt - moved to upscaler project

        if not department or not category:
            error_msg = f"Taxonomy response missing required fields. Department: '{department}', Category: '{category}'"
            logging.error(error_msg)
            logging.error(f"Full taxonomy result: {taxonomy_result}")
            raise ValueError(error_msg)

        logging.info(f"✅ Taxonomy assigned: {department} > {category} > {subcategory}")
        logging.info(f"📝 Reasoning: {reasoning}")
        logging.info(f"⚖️  Weight Estimation:")
        logging.info(f"   - Original weight: {weight_estimation.get('original_weight', 0)} lbs")
        logging.info(f"   - Final shipping weight: {weight_estimation.get('final_shipping_weight', 0)} lbs")
        logging.info(f"   - Confidence: {weight_estimation.get('confidence', 'unknown')}")
        logging.info(f"   - Source: {weight_estimation.get('source', 'unknown')}")
        logging.info(f"   - Reasoning: {weight_estimation.get('reasoning', '')}")
        logging.info(f"🛒 Purchase Options: {purchase_options}")
        logging.info(f"⚠️  Needs Review: {needs_review}")

        # Removed: lifestyle_images_prompt handling
        if status_fn:
            log_and_status(status_fn, f"    ✅ Department: {department}")
            log_and_status(status_fn, f"    ✅ Category: {category}")
            if subcategory:
                log_and_status(status_fn, f"    ✅ Subcategory: {subcategory}")
            log_and_status(status_fn, f"    📝 Reasoning: {reasoning}")
            log_and_status(status_fn, f"    ⚖️  Shipping Weight: {weight_estimation.get('final_shipping_weight', 0)} lbs (confidence: {weight_estimation.get('confidence', 'unknown')})")
            log_and_status(status_fn, f"    🛒 Purchase Options: {purchase_options}")
            # Removed: lifestyle_images_prompt handling
        time.sleep(0.5)  # Brief delay between API calls

        # Determine number of audiences from config
        audience_count = 1
        audience_1_name = None
        audience_2_name = None
        if audience_config:
            audience_count = audience_config.get("count", 1)
            audience_1_name = audience_config.get("audience_1_name", "").strip()
            audience_2_name = audience_config.get("audience_2_name", "").strip()

        # Generate description(s) based on audience count
        enhanced_description = None  # Primary description (goes in body_html)
        description_audience_1 = None  # Audience 1 metafield
        description_audience_2 = None  # Audience 2 metafield
        total_description_cost = 0

        # Only generate multiple descriptions if both audience names are provided
        if audience_count == 2 and audience_1_name and audience_2_name:
            # Generate TWO descriptions for different audiences

            # Description for Audience 1
            if status_fn:
                log_and_status(status_fn, f"  ✍️  Generating description for {audience_1_name}...")

            logging.info("=" * 80)
            logging.info(f"CLAUDE API CALL #2A: DESCRIPTION FOR AUDIENCE 1 ({audience_1_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_1 = build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name)

            logging.debug(f"Description prompt for Audience 1 (first 500 chars):\n{description_prompt_1[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_1)} characters")
            logging.info(f"Sending description rewriting request for {audience_1_name}...")

            description_response_1 = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": description_prompt_1}]
            )

            logging.info(f"✅ Audience 1 description API call successful")
            logging.info(f"Token usage - Input: {description_response_1.usage.input_tokens}, Output: {description_response_1.usage.output_tokens}")

            description_1_cost = (description_response_1.usage.input_tokens * 0.003 / 1000) + (description_response_1.usage.output_tokens * 0.015 / 1000)
            logging.info(f"Cost: ${description_1_cost:.6f}")
            total_description_cost += description_1_cost

            description_audience_1 = description_response_1.content[0].text.strip()
            if description_audience_1.startswith("```"):
                lines = description_audience_1.split('\n')
                description_audience_1 = '\n'.join(lines[1:-1])

            if not description_audience_1 or len(description_audience_1.strip()) == 0:
                logging.warning(f"⚠️  Claude returned empty description for {audience_1_name}! Using original body_html")
                description_audience_1 = body_html

            logging.info(f"✅ Description for {audience_1_name} complete ({len(description_audience_1)} characters)")

            # Description for Audience 2
            time.sleep(0.5)  # Brief delay between API calls

            if status_fn:
                log_and_status(status_fn, f"  ✍️  Generating description for {audience_2_name}...")

            logging.info("=" * 80)
            logging.info(f"CLAUDE API CALL #2B: DESCRIPTION FOR AUDIENCE 2 ({audience_2_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_2 = build_description_prompt(title, body_html, department, voice_tone_doc, audience_2_name)

            logging.debug(f"Description prompt for Audience 2 (first 500 chars):\n{description_prompt_2[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_2)} characters")
            logging.info(f"Sending description rewriting request for {audience_2_name}...")

            description_response_2 = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": description_prompt_2}]
            )

            logging.info(f"✅ Audience 2 description API call successful")
            logging.info(f"Token usage - Input: {description_response_2.usage.input_tokens}, Output: {description_response_2.usage.output_tokens}")

            description_2_cost = (description_response_2.usage.input_tokens * 0.003 / 1000) + (description_response_2.usage.output_tokens * 0.015 / 1000)
            logging.info(f"Cost: ${description_2_cost:.6f}")
            total_description_cost += description_2_cost

            description_audience_2 = description_response_2.content[0].text.strip()
            if description_audience_2.startswith("```"):
                lines = description_audience_2.split('\n')
                description_audience_2 = '\n'.join(lines[1:-1])

            if not description_audience_2 or len(description_audience_2.strip()) == 0:
                logging.warning(f"⚠️  Claude returned empty description for {audience_2_name}! Using original body_html")
                description_audience_2 = body_html

            logging.info(f"✅ Description for {audience_2_name} complete ({len(description_audience_2)} characters)")

            # Use Audience 1 description as primary body_html
            enhanced_description = description_audience_1

            if status_fn:
                log_and_status(status_fn, f"    ✅ Generated 2 audience descriptions ({len(description_audience_1)} + {len(description_audience_2)} chars)")

        else:
            # Single audience mode (default behavior)
            if status_fn:
                audience_label = f" for {audience_1_name}" if audience_1_name else ""
                log_and_status(status_fn, f"  ✍️  Rewriting description{audience_label}...")

            logging.info("=" * 80)
            logging.info(f"CLAUDE API CALL #2: DESCRIPTION REWRITING")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            if audience_1_name:
                logging.info(f"Audience: {audience_1_name}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt = build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name if audience_1_name else None)

            logging.debug(f"Description prompt (first 500 chars):\n{description_prompt[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt)} characters")
            logging.info("Sending description rewriting request to Claude API...")

            description_response = client.messages.create(
                model=model,
                max_tokens=2048,
                messages=[{"role": "user", "content": description_prompt}]
            )

            logging.info(f"✅ Description API call successful")
            logging.info(f"Response ID: {description_response.id}")
            logging.info(f"Model used: {description_response.model}")
            logging.info(f"Stop reason: {description_response.stop_reason}")
            logging.info(f"Token usage - Input: {description_response.usage.input_tokens}, Output: {description_response.usage.output_tokens}")

            total_description_cost = (description_response.usage.input_tokens * 0.003 / 1000) + (description_response.usage.output_tokens * 0.015 / 1000)
            logging.info(f"Cost: ${total_description_cost:.6f}")

            enhanced_description = description_response.content[0].text.strip()
            logging.debug(f"Enhanced description (first 500 chars):\n{enhanced_description[:500]}...")

            if enhanced_description.startswith("```"):
                logging.debug("Removing markdown code block wrapper from description response")
                lines = enhanced_description.split('\n')
                enhanced_description = '\n'.join(lines[1:-1])

            if not enhanced_description or len(enhanced_description.strip()) == 0:
                logging.warning("⚠️  Claude returned empty description! Using original body_html")
                logging.warning(f"Original body_html length: {len(body_html)} characters")
                enhanced_description = body_html

            logging.info(f"✅ Description rewritten ({len(enhanced_description)} characters)")

            if status_fn:
                log_and_status(status_fn, f"    ✅ Description rewritten ({len(enhanced_description)} characters)")

        # Calculate total cost
        total_cost = taxonomy_cost + total_description_cost
        logging.info(f"Total cost for this product: ${total_cost:.6f}")

        # Create enhanced product with new taxonomy and description
        enhanced_product = product.copy()
        enhanced_product['product_type'] = department

        # Build tags array: category + subcategory (if exists)
        tags = [category]
        if subcategory:
            tags.append(subcategory)

        # Preserve any existing tags that aren't taxonomy-related
        existing_tags = product.get('tags', [])
        if isinstance(existing_tags, str):
            existing_tags = [t.strip() for t in existing_tags.split(',') if t.strip()]

        # Add existing tags that aren't department/category names
        for tag in existing_tags:
            if tag and tag not in tags and tag != department:
                tags.append(tag)

        enhanced_product['tags'] = tags
        # GraphQL format only (no REST API backward compatibility)
        enhanced_product['descriptionHtml'] = enhanced_description

        # Preserve status field if present in input (GraphQL), or set to ACTIVE by default
        if 'status' in product:
            enhanced_product['status'] = product['status']
        else:
            enhanced_product['status'] = 'ACTIVE'  # Default for GraphQL compatibility

        # Add lifestyle image prompts if any variants need images
        # Removed: lifestyle_images_prompt handling
        final_shipping_weight = weight_estimation.get('final_shipping_weight', 0)
        final_shipping_weight_grams = int(final_shipping_weight * 453.592)  # Convert lbs to grams

        if 'variants' in enhanced_product and enhanced_product['variants']:
            for variant in enhanced_product['variants']:
                # Store weight data for output file (NOT sent to Shopify)
                variant['weight_data'] = {
                    'original_weight': weight_estimation.get('original_weight', 0),
                    'product_weight': weight_estimation.get('product_weight', 0),
                    'product_packaging_weight': weight_estimation.get('product_packaging_weight', 0),
                    'shipping_packaging_weight': weight_estimation.get('shipping_packaging_weight', 0),
                    'calculated_shipping_weight': weight_estimation.get('calculated_shipping_weight', 0),
                    'final_shipping_weight': final_shipping_weight,
                    'confidence': weight_estimation.get('confidence', 'unknown'),
                    'source': weight_estimation.get('source', 'unknown'),
                    'reasoning': weight_estimation.get('reasoning', ''),
                    'needs_review': needs_review
                }

                # Update Shopify weight fields
                variant['weight'] = final_shipping_weight
                variant['grams'] = final_shipping_weight_grams

        logging.info(f"✅ Updated {len(enhanced_product.get('variants', []))} variants with shipping weight: {final_shipping_weight} lbs")

        # Initialize metafields array if not present
        if 'metafields' not in enhanced_product:
            enhanced_product['metafields'] = []

        # Add REQUIRED hide_online_price metafield (check for duplicates)
        if add_metafield_if_not_exists(enhanced_product, 'custom', 'hide_online_price', 'true', 'boolean'):
            logging.info(f"✅ Added hide_online_price metafield")
        else:
            logging.info(f"ℹ️  hide_online_price metafield already exists")

        # Add purchase_options as product-level metafield (formatted as object mapping)
        purchase_options_value = format_purchase_options_metafield(purchase_options)
        if add_metafield_if_not_exists(enhanced_product, 'custom', 'purchase_options', purchase_options_value, 'json'):
            logging.info(f"✅ Added purchase_options metafield: {purchase_options}")
        else:
            logging.info(f"ℹ️  purchase_options metafield already exists")

        # Add audience descriptions as metafields if multiple audiences
        if audience_count == 2 and description_audience_1 and description_audience_2:
            # Metafields array already initialized above
            pass

            # Add audience configuration metafield (for Liquid template)
            audience_metadata = {
                "count": 2,
                "audience_1_name": audience_1_name,
                "audience_2_name": audience_2_name,
                "tab_1_label": audience_config.get("tab_1_label", audience_1_name),
                "tab_2_label": audience_config.get("tab_2_label", audience_2_name)
            }

            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "audience_config",
                "value": json.dumps(audience_metadata),
                "type": "json"
            })

            # Add audience 1 description metafield
            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "description_audience_1",
                "value": description_audience_1,
                "type": "multi_line_text_field"
            })

            # Add audience 2 description metafield
            enhanced_product['metafields'].append({
                "namespace": "custom",
                "key": "description_audience_2",
                "value": description_audience_2,
                "type": "multi_line_text_field"
            })

            logging.info(f"Added audience metafields to product:")
            logging.info(f"  - audience_config: {audience_metadata}")
            logging.info(f"  - description_audience_1: {len(description_audience_1)} chars")
            logging.info(f"  - description_audience_2: {len(description_audience_2)} chars")

        # ========== SHOPIFY CATEGORY MATCHING ==========
        # Use intelligent pre-computed mapping (one-time AI mapping, cached)
        shopify_category_id = None
        if taxonomy_mappings:
            try:
                from .taxonomy_mapper import lookup_shopify_category

                shopify_mapping = lookup_shopify_category(
                    department,
                    category,
                    subcategory,
                    taxonomy_mappings
                )

                if shopify_mapping:
                    logging.info(f"✅ Matched to Shopify category via intelligent mapping")
                    enhanced_product['shopify_category_id'] = shopify_mapping.get('shopify_id')
                    enhanced_product['shopify_category'] = shopify_mapping.get('shopify_category')
                    logging.info(f"Stored Shopify category: {shopify_mapping.get('shopify_category')}")
                    logging.info(f"Stored Shopify category ID: {shopify_mapping.get('shopify_id')}")
                else:
                    logging.warning(f"⚠️  No Shopify category mapping found for: {department} > {category} > {subcategory}")
                    enhanced_product['shopify_category_id'] = None
                    enhanced_product['shopify_category'] = None
            except Exception as e:
                logging.warning(f"Failed to lookup Shopify category: {e}")
                enhanced_product['shopify_category_id'] = None
                enhanced_product['shopify_category'] = None
        else:
            logging.info("ℹ️  Taxonomy mappings not available - skipping Shopify category matching")
            enhanced_product['shopify_category_id'] = None
            enhanced_product['shopify_category'] = None

        logging.info("=" * 80)
        logging.info(f"✅ PRODUCT ENHANCEMENT COMPLETE: {title}")
        logging.info(f"Custom taxonomy: {department} > {category} > {subcategory}")
        shopify_cat = enhanced_product.get('shopify_category', 'None')
        shopify_id = enhanced_product.get('shopify_category_id', 'None')
        logging.info(f"Shopify category: {shopify_cat}")
        logging.info(f"Shopify category ID: {shopify_id}")
        logging.info(f"Description length: {len(enhanced_product.get('body_html', ''))} characters")
        logging.info("=" * 80)

        # Remove weight_data from non-shipped products
        if not should_calculate_shipping_weight(purchase_options):
            enhanced_product = remove_weight_data_from_variants(enhanced_product)
            logging.info(f"ℹ️  Removed weight_data from non-shipped product (purchase_options: {purchase_options})")

        # Reorder fields according to GraphQL output requirements
        enhanced_product = reorder_product_fields(enhanced_product)

        return enhanced_product

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error enhancing product '{title}' with Claude API"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's a rate limit error and provide user-friendly message
        if anthropic and isinstance(e, anthropic.RateLimitError):
            logging.error("=" * 80)
            logging.error("⏱️  RATE LIMIT EXCEEDED")
            logging.error("=" * 80)
            logging.error("")
            logging.error("You've exceeded Claude's API rate limits.")
            logging.error("")
            logging.error("💡 SOLUTIONS:")
            logging.error("")
            logging.error("1. ⏰ WAIT 60 SECONDS and try again")
            logging.error("   Rate limits reset after 1 minute")
            logging.error("")
            logging.error("2. ♻️  DISABLE 'Force Refresh Taxonomy'")
            logging.error("   You just generated the taxonomy mapping - use the cached version!")
            logging.error("   Uncheck 'Force Refresh Taxonomy' in the GUI and run again")
            logging.error("")
            logging.error("3. 🔄 SWITCH TO GPT-5")
            logging.error("   OpenAI has different rate limits")
            logging.error("")
            logging.error("4. 📈 UPGRADE YOUR CLAUDE API TIER")
            logging.error("   Contact Anthropic sales: https://www.anthropic.com/contact-sales")
            logging.error("")
            logging.error("=" * 80)

            # Provide user-friendly message via status function
            if status_fn:
                log_and_status(status_fn, "")
                log_and_status(status_fn, "⏱️  Rate Limit Exceeded - Claude API")
                log_and_status(status_fn, "")
                log_and_status(status_fn, "💡 Quick Fix: Wait 60 seconds OR disable 'Force Refresh Taxonomy'")
                log_and_status(status_fn, "   (You already have a cached taxonomy mapping)")
                log_and_status(status_fn, "")

            # Raise with user-friendly message
            raise Exception(
                "Claude API rate limit exceeded. "
                "Wait 60 seconds or disable 'Force Refresh Taxonomy' to use cached mapping. "
                "See logs for details."
            ) from e

        # Check if it's an Anthropic API error
        if anthropic and isinstance(e, anthropic.APIError):
            logging.error("This is an Anthropic API error")
            if hasattr(e, 'status_code'):
                logging.error(f"HTTP Status Code: {e.status_code}")
            if hasattr(e, 'response'):
                logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


def generate_collection_description(
    collection_title: str,
    department: str,
    product_samples: List[str],
    voice_tone_doc: str,
    api_key: str,
    model: str,
    status_fn=None
) -> str:
    """
    Generate a collection description using Claude API.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions from this collection
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: Claude API key
        model: Claude model ID
        status_fn: Optional status update function

    Returns:
        Generated collection description (plain text)

    Raises:
        Exception: If API call fails
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Cannot generate collection descriptions."
        logging.error(error_msg)
        raise ImportError(error_msg)

    if not collection_title:
        error_msg = f"Collection has no title, cannot generate description"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  📝 Generating description for: {collection_title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"CLAUDE API CALL: COLLECTION DESCRIPTION")
        logging.info(f"Collection: {collection_title}")
        logging.info(f"Department: {department}")
        logging.info(f"Product samples: {len(product_samples)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        collection_prompt = build_collection_description_prompt(
            collection_title,
            department,
            product_samples,
            voice_tone_doc
        )

        # Log prompt preview
        logging.debug(f"Collection prompt (first 500 chars):\n{collection_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(collection_prompt)} characters")

        # Make API call
        logging.info("Sending collection description request to Claude API...")
        response = client.messages.create(
            model=model,
            max_tokens=512,  # 100 words ~ 150 tokens, give buffer
            messages=[{
                "role": "user",
                "content": collection_prompt
            }]
        )

        # Log response details
        logging.info(f"✅ Collection description API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Model used: {response.model}")
        logging.info(f"Stop reason: {response.stop_reason}")
        logging.info(f"Token usage - Input: {response.usage.input_tokens}, Output: {response.usage.output_tokens}")

        cost = (response.usage.input_tokens * 0.003 / 1000) + (response.usage.output_tokens * 0.015 / 1000)
        logging.info(f"Cost: ${cost:.6f}")

        # Extract description
        description = response.content[0].text.strip()
        logging.debug(f"Generated description ({len(description.split())} words):\n{description}")

        # Remove markdown code blocks if present
        if description.startswith("```"):
            logging.debug("Removing markdown code block wrapper from description")
            lines = description.split('\n')
            description = '\n'.join(lines[1:-1])

        word_count = len(description.split())
        logging.info(f"✅ Collection description generated ({word_count} words)")

        if status_fn:
            log_and_status(status_fn, f"    ✅ Description generated ({word_count} words)")

        logging.info("=" * 80)
        logging.info(f"✅ COLLECTION DESCRIPTION COMPLETE: {collection_title}")
        logging.info("=" * 80)

        return description

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error generating description for collection '{collection_title}'"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's an Anthropic API error
        if anthropic and isinstance(e, anthropic.APIError):
            logging.error("This is an Anthropic API error")
            if hasattr(e, 'status_code'):
                logging.error(f"HTTP Status Code: {e.status_code}")
            if hasattr(e, 'response'):
                logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


# ========== BATCH API FUNCTIONS (50% COST SAVINGS) ==========

def enhance_products_with_claude_batch(
    products: List[Dict],
    taxonomy_doc: str,
    voice_tone_doc: str,
    api_key: str,
    model: str,
    poll_interval: int = 60,
    status_fn=None,
    audience_config: Dict = None
) -> List[Dict]:
    """
    Enhance multiple products using Anthropic Message Batches API for 50% cost savings.

    Message Batches API provides:
    - 50% lower costs compared to standard API
    - Asynchronous processing with 24-hour completion window
    - Same model quality and capabilities

    Args:
        products: List of product dictionaries
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown
        api_key: Claude API key
        model: Claude model ID
        poll_interval: Seconds between status polls (default: 60)
        status_fn: Optional status update function
        audience_config: Optional audience configuration dict

    Returns:
        List of enhanced product dictionaries

    Raises:
        Exception: If batch creation or processing fails
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Cannot use batch processing."
        logging.error(error_msg)
        raise ImportError(error_msg)

    import time

    client = anthropic.Anthropic(api_key=api_key)

    if status_fn:
        log_and_status(status_fn, f"🔄 Preparing batch processing for {len(products)} products...")
        log_and_status(status_fn, f"💰 Batch mode enabled: 50% cost savings")

    logging.info("=" * 80)
    logging.info(f"ANTHROPIC MESSAGE BATCHES API PROCESSING - 50% COST SAVINGS")
    logging.info(f"Total products: {len(products)}")
    logging.info(f"Model: {model}")
    logging.info("=" * 80)

    # Step 1: Create batch requests for taxonomy
    if status_fn:
        log_and_status(status_fn, f"📝 Creating batch requests...")

    taxonomy_batch_requests = []
    for i, product in enumerate(products):
        title = product.get('title', '')
        # Support both GraphQL (descriptionHtml) and REST (body_html) field names
        body_html = product.get('descriptionHtml') or product.get('body_html', '')

        # Get first variant's weight for reference (if product has variants)
        current_weight = 0
        variant_data = None
        if product.get('variants') and len(product['variants']) > 0:
            first_variant = product['variants'][0]
            current_weight = first_variant.get('weight', 0)

            # Extract size_info metafield if exists
            metafields = first_variant.get('metafields', [])
            for mf in metafields:
                if mf.get('key') == 'size_info':
                    variant_data = {'size_info_metafield': mf.get('value', '')}
                    break

        # Removed: lifestyle image prompt generation moved to upscaler project
        taxonomy_prompt = build_taxonomy_prompt(title, body_html, taxonomy_doc, current_weight, variant_data)

        taxonomy_batch_requests.append({
            "custom_id": f"taxonomy-{i}",
            "params": {
                "model": model,
                "max_tokens": 16000,
                "messages": [{"role": "user", "content": taxonomy_prompt}]
            }
        })

    logging.info(f"Created {len(taxonomy_batch_requests)} taxonomy requests")

    # Step 2: Create taxonomy batch
    if status_fn:
        log_and_status(status_fn, f"🚀 Starting taxonomy batch processing...")

    try:
        taxonomy_batch = client.beta.messages.batches.create(
            requests=taxonomy_batch_requests
        )

        logging.info(f"✅ Created taxonomy batch: {taxonomy_batch.id}")
        logging.info(f"Status: {taxonomy_batch.processing_status}")

        if status_fn:
            log_and_status(status_fn, f"⏳ Batch job created: {taxonomy_batch.id}")
            log_and_status(status_fn, f"Status: {taxonomy_batch.processing_status}")

        # Step 3: Poll for completion
        if status_fn:
            log_and_status(status_fn, f"⏰ Waiting for batch to complete (polling every {poll_interval}s)...")

        while taxonomy_batch.processing_status in ["in_progress"]:
            time.sleep(poll_interval)
            taxonomy_batch = client.beta.messages.batches.retrieve(taxonomy_batch.id)

            progress_msg = f"Status: {taxonomy_batch.processing_status}"
            if taxonomy_batch.request_counts:
                progress_msg += f" | Completed: {taxonomy_batch.request_counts.succeeded}/{len(taxonomy_batch_requests)}"
                if taxonomy_batch.request_counts.errored > 0:
                    progress_msg += f" | Errors: {taxonomy_batch.request_counts.errored}"

            logging.info(progress_msg)
            if status_fn:
                log_and_status(status_fn, f"⏳ {progress_msg}")

        # Check final status
        if taxonomy_batch.processing_status not in ["ended"]:
            error_msg = f"Batch job failed with status: {taxonomy_batch.processing_status}"
            logging.error(error_msg)
            raise Exception(error_msg)

        logging.info(f"✅ Taxonomy batch completed!")
        if status_fn:
            log_and_status(status_fn, f"✅ Taxonomy batch complete!")

        # Step 4: Retrieve results
        if status_fn:
            log_and_status(status_fn, f"📥 Downloading batch results...")

        taxonomy_results = {}
        for result in client.beta.messages.batches.results(taxonomy_batch.id):
            taxonomy_results[result.custom_id] = result

        logging.info(f"✅ Downloaded {len(taxonomy_results)} results")

        # Step 5: Process taxonomy results and create description batch
        enhanced_products = []
        description_batch_requests = []

        for i, product in enumerate(products):
            taxonomy_result_key = f"taxonomy-{i}"

            if taxonomy_result_key not in taxonomy_results:
                logging.error(f"Missing result for product {i}: {product.get('title', '')}")
                continue

            result_wrapper = taxonomy_results[taxonomy_result_key]

            if result_wrapper.result.type != "succeeded":
                logging.error(f"Taxonomy request failed for product {i}: {result_wrapper.result.type}")
                continue

            # Parse taxonomy response
            taxonomy_message = result_wrapper.result.message
            taxonomy_text = taxonomy_message.content[0].text.strip()

            # Remove markdown if present
            if taxonomy_text.startswith("```"):
                lines = taxonomy_text.split('\n')
                taxonomy_text = '\n'.join(lines[1:-1])

            try:
                taxonomy_result = json.loads(taxonomy_text)
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse taxonomy JSON for product {i}: {e}")
                continue

            # Extract taxonomy data
            department = taxonomy_result.get('department', '')
            category = taxonomy_result.get('category', '')
            subcategory = taxonomy_result.get('subcategory', '')
            weight_estimation = taxonomy_result.get('weight_estimation', {})
            purchase_options = taxonomy_result.get('purchase_options', [])
            needs_review = taxonomy_result.get('needs_review', False)
            # Removed: lifestyle_images_prompt - moved to upscaler project

            # Create enhanced product with taxonomy
            enhanced_product = product.copy()
            enhanced_product['product_type'] = department

            tags = [category]
            if subcategory:
                tags.append(subcategory)
            enhanced_product['tags'] = tags

            # Preserve status field if present in input (GraphQL), or set to ACTIVE by default
            if 'status' in product:
                enhanced_product['status'] = product['status']
            else:
                enhanced_product['status'] = 'ACTIVE'  # Default for GraphQL compatibility

            # Add lifestyle image prompts
            # Removed: lifestyle_images_prompt handling
        if status_fn:
            log_and_status(status_fn, f"📝 Creating description batch...")

        description_batch = client.beta.messages.batches.create(
            requests=description_batch_requests
        )

        logging.info(f"✅ Created description batch: {description_batch.id}")

        if status_fn:
            log_and_status(status_fn, f"⏳ Processing descriptions...")

        # Poll for description batch completion
        while description_batch.processing_status in ["in_progress"]:
            time.sleep(poll_interval)
            description_batch = client.beta.messages.batches.retrieve(description_batch.id)

            progress_msg = f"Descriptions: {description_batch.processing_status}"
            if description_batch.request_counts:
                progress_msg += f" | {description_batch.request_counts.succeeded}/{len(description_batch_requests)}"

            logging.info(progress_msg)
            if status_fn:
                log_and_status(status_fn, f"⏳ {progress_msg}")

        if description_batch.processing_status not in ["ended"]:
            error_msg = f"Description batch failed: {description_batch.processing_status}"
            logging.error(error_msg)
            raise Exception(error_msg)

        # Retrieve description results
        description_results = {}
        for result in client.beta.messages.batches.results(description_batch.id):
            description_results[result.custom_id] = result

        # Apply descriptions to products
        for i, enhanced_product in enumerate(enhanced_products):
            desc_key = f"description-{i}"
            if desc_key in description_results:
                desc_result = description_results[desc_key]
                if desc_result.result.type == "succeeded":
                    description = desc_result.result.message.content[0].text.strip()

                    if description.startswith("```"):
                        lines = description.split('\n')
                        description = '\n'.join(lines[1:-1])

                    # GraphQL format only (no REST API backward compatibility)
                    enhanced_product['descriptionHtml'] = description

        logging.info(f"✅ Batch processing complete: {len(enhanced_products)} products enhanced")
        if status_fn:
            log_and_status(status_fn, f"✅ Successfully enhanced {len(enhanced_products)} products using batch API")
            log_and_status(status_fn, f"💰 Cost savings: 50% compared to standard API")

        return enhanced_products

    except Exception as e:
        error_msg = f"Batch processing failed"
        logging.error(f"❌ {error_msg}: {str(e)}")
        logging.exception("Full traceback:")
        raise Exception(f"{error_msg}: {str(e)}") from e


def batch_enhance_products(
    products: List[Dict],
    cfg: Dict,
    status_fn,
    taxonomy_path: str = "/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md",
    voice_tone_path: str = "docs/VOICE_AND_TONE_GUIDELINES.md"
) -> List[Dict]:
    """
    Enhance multiple products with Claude API using caching.

    Args:
        products: List of product dictionaries
        cfg: Configuration dictionary
        status_fn: Status update function
        taxonomy_path: Path to taxonomy markdown file
        voice_tone_path: Path to voice and tone guidelines markdown file

    Returns:
        List of enhanced product dictionaries

    Raises:
        Exception: Stops immediately on API failure
    """
    if anthropic is None:
        error_msg = "anthropic package not installed. Install with: pip install anthropic"
        log_and_status(status_fn, f"❌ {error_msg}", "error")
        raise ImportError(error_msg)

    api_key = cfg.get("CLAUDE_API_KEY", "").strip()
    model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")

    if not api_key:
        error_msg = "Claude API key not configured. Add your API key in Settings dialog."
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
    log_and_status(status_fn, f"🤖 Using Claude model: {model}\n")

    # Load cache
    cache = load_cache()
    cached_products = cache.get("products", {})

    enhanced_products = []
    enhanced_count = 0
    cached_count = 0

    total = len(products)

    logging.info("=" * 80)
    logging.info(f"STARTING BATCH CLAUDE AI ENHANCEMENT")
    logging.info(f"Total products to process: {total}")
    logging.info(f"Model: {model}")
    logging.info("=" * 80)

    for i, product in enumerate(products, 1):
        title = product.get('title', f'Product {i}')
        log_and_status(
            status_fn,
            f"Processing product {i}/{total}: {title[:60]}...",
            ui_msg=f"Enhancing with Claude AI: {i}/{total}"
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

                enhanced_products.append(enhanced_product)
                cached_count += 1
                continue

        # Not in cache or changed - enhance with Claude
        try:
            enhanced_product = enhance_product_with_claude(
                product,
                taxonomy_doc,
                voice_tone_doc,
                api_key,
                model,
                status_fn
            )

            # Save to cache
            cached_products[cache_key] = {
                "enhanced_at": datetime.now().isoformat(),
                "input_hash": product_hash,
                "department": enhanced_product.get('product_type', ''),
                "category": enhanced_product.get('tags', [])[0] if enhanced_product.get('tags') else '',
                "subcategory": enhanced_product.get('tags', [])[1] if len(enhanced_product.get('tags', [])) > 1 else '',
                "enhanced_description": enhanced_product.get('body_html', '')
            }
            enhanced_count += 1

            enhanced_products.append(enhanced_product)

        except Exception as e:
            # Claude API failed - stop processing immediately
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, "=" * 80, "error")
            log_and_status(status_fn, "❌ CLAUDE API ENHANCEMENT FAILED", "error")
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

        # Rate limiting: ~10 requests per minute (5 products = 10 requests)
        if i % 5 == 0 and i < total:
            log_and_status(status_fn, f"  ⏸️  Rate limit pause (5 products processed)...")
            time.sleep(6)  # 6 second pause every 5 products

        log_and_status(status_fn, "")  # Empty line between products

    # Save cache
    cache["products"] = cached_products
    save_cache(cache)

    # Summary
    logging.info("=" * 80)
    logging.info(f"BATCH CLAUDE AI ENHANCEMENT COMPLETE")
    logging.info(f"Newly enhanced: {enhanced_count}")
    logging.info(f"Used cache: {cached_count}")
    logging.info(f"Total processed: {total}")
    logging.info("=" * 80)

    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, "CLAUDE AI ENHANCEMENT SUMMARY")
    log_and_status(status_fn, "=" * 80)
    log_and_status(status_fn, f"✅ Newly enhanced: {enhanced_count}")
    log_and_status(status_fn, f"♻️  Used cache: {cached_count}")
    log_and_status(status_fn, f"📊 Total processed: {total}")

    return enhanced_products
