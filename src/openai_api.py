"""
OpenAI API integration for product taxonomy assignment and description rewriting.
"""

import json
import logging
from typing import Dict, List

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logging.warning("openai package not installed. OpenAI features will be disabled.")

from .config import log_and_status


def is_reasoning_model(model: str) -> bool:
    """
    Determine if a model is a reasoning model (GPT-5, o-series).

    Reasoning models have restricted parameter support:
    - Use 'max_completion_tokens' instead of 'max_tokens'
    - Don't support custom temperature (only default value 1)
    - Don't support: top_p, presence_penalty, frequency_penalty, logprobs, logit_bias

    Args:
        model: Model identifier (e.g., "gpt-5", "gpt-4o", "o1-preview")

    Returns:
        True if model is a reasoning model, False otherwise
    """
    model_lower = model.lower()

    # GPT-5 series are reasoning models
    if model_lower.startswith("gpt-5"):
        return True

    # o-series are reasoning models (o1, o3, o4)
    if model_lower.startswith("o1") or model_lower.startswith("o3") or model_lower.startswith("o4"):
        return True

    # All other models (GPT-4o, GPT-4, GPT-3.5, etc.) are NOT reasoning models
    return False


def uses_max_completion_tokens(model: str) -> bool:
    """
    Determine if a model uses 'max_completion_tokens' instead of 'max_tokens'.

    This is a convenience wrapper around is_reasoning_model().

    Args:
        model: Model identifier

    Returns:
        True if model uses max_completion_tokens, False if it uses max_tokens
    """
    return is_reasoning_model(model)


def get_openai_model_pricing(model: str) -> tuple:
    """
    Get pricing for OpenAI models (input cost per 1M tokens, output cost per 1M tokens).

    Returns:
        Tuple of (input_cost, output_cost) per million tokens
    """
    # GPT-5 models (released August 2025)
    if model.startswith("gpt-5"):
        return (1.25, 10.00)  # GPT-5, GPT-5-mini, GPT-5-nano all same pricing

    # GPT-4o models
    elif model.startswith("gpt-4o"):
        return (2.50, 10.00)

    # GPT-4 Turbo
    elif "gpt-4-turbo" in model or "gpt-4-1106" in model or "gpt-4-0125" in model:
        return (10.00, 30.00)

    # GPT-4
    elif model.startswith("gpt-4"):
        return (30.00, 60.00)

    # Default to GPT-5 pricing (most common)
    else:
        return (1.25, 10.00)


def match_shopify_category_with_openai(
    product_title: str,
    product_description: str,
    shopify_categories: List[Dict],
    api_key: str,
    model: str,
    status_fn=None
) -> str:
    """
    Use OpenAI to match a product to the best Shopify taxonomy category.

    Args:
        product_title: Product title
        product_description: Product description
        shopify_categories: List of dicts with 'id' and 'fullName' from Shopify
        api_key: OpenAI API key
        model: OpenAI model ID
        status_fn: Optional status update function

    Returns:
        Shopify category ID (GID format) or None if no good match

    Raises:
        Exception: If API call fails
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot match Shopify categories."
        logging.error(error_msg)
        raise ImportError(error_msg)

    try:
        client = OpenAI(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  🔍 Matching to Shopify category...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL: SHOPIFY CATEGORY MATCHING")
        logging.info(f"Product: {product_title}")
        logging.info(f"Available categories: {len(shopify_categories)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        # Build category list for prompt - include ALL categories in compact format
        # Group by top-level category to make it easier for AI to navigate
        categories_by_top = {}
        for cat in shopify_categories:
            full_name = cat['fullName']
            top_level = full_name.split(' > ')[0] if ' > ' in full_name else full_name
            if top_level not in categories_by_top:
                categories_by_top[top_level] = []
            categories_by_top[top_level].append(full_name)

        # Build compact category text
        categories_text = ""
        for top_level in sorted(categories_by_top.keys()):
            categories_text += f"\n{top_level}:\n"
            for cat_name in categories_by_top[top_level][:200]:  # Limit per top-level to manage size
                categories_text += f"  - {cat_name}\n"
            if len(categories_by_top[top_level]) > 200:
                categories_text += f"  ... and {len(categories_by_top[top_level]) - 200} more\n"

        prompt = f"""You are a product categorization expert. Match this product to the BEST category from Shopify's Standard Product Taxonomy.

Product Information:
- Title: {product_title}
- Description: {product_description[:1000]}

Available Shopify Categories (hierarchical paths):
{categories_text}

CRITICAL INSTRUCTIONS:
1. Analyze the product title and description carefully
2. Find the MOST SPECIFIC category - NOT a top-level category!
   - ❌ WRONG: "Home & Garden" (too generic)
   - ✅ CORRECT: "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones" (specific)
3. Choose the DEEPEST, most detailed category path that accurately describes this product
4. For patio/outdoor hardscape products, look for categories containing "Pavers", "Stepping Stones", "Outdoor Living", "Hardscape", "Landscaping"
5. Return the COMPLETE hierarchical path (e.g., "Parent > Child > Grandchild")

Return ONLY a valid JSON object in this exact format (no markdown, no code blocks, no explanation):
{{
  "category_fullName": "Complete hierarchical category path from the list above (must include all levels separated by ' > ')",
  "reasoning": "Brief 1-sentence explanation of why you chose this specific category"
}}

EXAMPLE GOOD RESPONSES:
- {{"category_fullName": "Home & Garden > Lawn & Garden > Outdoor Living > Pavers & Stepping Stones", "reasoning": "Product is patio slabs for outdoor hardscaping"}}
- {{"category_fullName": "Animals & Pet Supplies > Pet Supplies > Dog Supplies > Dog Beds", "reasoning": "Product is a bed specifically for dogs"}}

EXAMPLE BAD RESPONSES (too generic):
- {{"category_fullName": "Home & Garden", "reasoning": "..."}} ❌ TOO GENERIC
- {{"category_fullName": "Animals & Pet Supplies", "reasoning": "..."}} ❌ TOO GENERIC

If no good match exists, return: {{"category_fullName": null, "reasoning": "No suitable category found"}}"""

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": prompt
            }]
        }

        # Add temperature only for non-reasoning models
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.3
            logging.debug(f"Using temperature=0.3 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 512
            logging.debug(f"Using max_completion_tokens=512 for model {model}")
        else:
            api_params["max_tokens"] = 512
            logging.debug(f"Using max_tokens=512 for model {model}")

        response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Shopify category matching API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}")

        # Extract response
        response_text = response.choices[0].message.content.strip()
        logging.debug(f"Raw response: {response_text}")

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            lines = response_text.split('\n')
            response_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        # Parse JSON
        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse Shopify category JSON: {e}")
            logging.error(f"Response: {response_text}")
            return None

        category_fullName = result.get('category_fullName')
        reasoning = result.get('reasoning', '')

        if not category_fullName:
            logging.warning(f"⚠️  AI could not find suitable Shopify category: {reasoning}")
            if status_fn:
                log_and_status(status_fn, f"    ⚠️  No suitable Shopify category found")
            return None

        # Find the category ID by matching fullName
        category_id = None
        for cat in shopify_categories:
            if cat['fullName'] == category_fullName:
                category_id = cat['id']
                break

        if category_id:
            logging.info(f"✅ Matched Shopify category: {category_fullName}")
            logging.info(f"📝 Reasoning: {reasoning}")
            logging.info(f"🆔 Category ID: {category_id}")
            if status_fn:
                log_and_status(status_fn, f"    ✅ Matched: {category_fullName}")
        else:
            logging.warning(f"⚠️  AI selected category not found in list: {category_fullName}")
            if status_fn:
                log_and_status(status_fn, f"    ⚠️  Category not found: {category_fullName}")

        return category_id

    except Exception as e:
        logging.error(f"Error matching Shopify category: {e}")
        logging.exception("Full traceback:")
        return None


def enhance_product_with_openai(
    product: Dict,
    taxonomy_doc: str,
    voice_tone_doc: str,
    shopify_categories: List[Dict],
    api_key: str,
    model: str,
    status_fn=None,
    audience_config: Dict = None
) -> Dict:
    """
    Enhance a single product using OpenAI API.

    Args:
        product: Product dictionary
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: OpenAI API key
        model: OpenAI model ID (e.g., "gpt-4o")
        status_fn: Optional status update function
        audience_config: Optional audience configuration dict with keys:
            - count: 1 or 2
            - audience_1_name: str
            - audience_2_name: str (if count=2)
            - tab_1_label: str (if count=2)
            - tab_2_label: str (if count=2)

    Returns:
        Enhanced product dictionary (includes metafields for multiple audiences)

    Raises:
        Exception: If API call fails or response is invalid
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot enhance products. Install with: pip install openai"
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
        client = OpenAI(api_key=api_key)

        # ========== STEP 1: TAXONOMY ASSIGNMENT + WEIGHT ESTIMATION + PURCHASE OPTIONS ==========
        if status_fn:
            log_and_status(status_fn, f"  🤖 Assigning taxonomy and calculating shipping weight for: {title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL #1: ENHANCED TAXONOMY (TAXONOMY + WEIGHT + PURCHASE OPTIONS)")
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

        taxonomy_prompt = _build_taxonomy_prompt(title, body_html, taxonomy_doc, current_weight, variant_data)

        # Log prompt preview (first 500 chars)
        logging.debug(f"Enhanced taxonomy prompt (first 500 chars):\n{taxonomy_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(taxonomy_prompt)} characters")

        # Make API call with correct parameters based on model
        logging.info("Sending taxonomy assignment request to OpenAI API...")

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": taxonomy_prompt
            }]
        }

        # Add temperature only for non-reasoning models
        # Reasoning models (GPT-5, o-series) only support temperature=1 (default)
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.3
            logging.debug(f"Using temperature=0.3 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter based on model
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 16000
            logging.debug(f"Using max_completion_tokens=16000 for model {model}")
        else:
            api_params["max_tokens"] = 16000
            logging.debug(f"Using max_tokens=16000 for model {model}")

        taxonomy_response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Taxonomy API call successful")
        logging.info(f"Response ID: {taxonomy_response.id}")
        logging.info(f"Model used: {taxonomy_response.model}")
        logging.info(f"Finish reason: {taxonomy_response.choices[0].finish_reason}")
        logging.info(f"Token usage - Prompt: {taxonomy_response.usage.prompt_tokens}, Completion: {taxonomy_response.usage.completion_tokens}, Total: {taxonomy_response.usage.total_tokens}")

        # Calculate cost based on model pricing
        input_cost, output_cost = get_openai_model_pricing(model)
        taxonomy_cost = (taxonomy_response.usage.prompt_tokens * input_cost / 1_000_000) + (taxonomy_response.usage.completion_tokens * output_cost / 1_000_000)
        logging.info(f"Cost: ${taxonomy_cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

        # Extract taxonomy from response
        taxonomy_text = taxonomy_response.choices[0].message.content.strip()
        logging.debug(f"Raw taxonomy response:\n{taxonomy_text}")

        # Remove markdown code blocks if present
        if taxonomy_text.startswith("```"):
            logging.debug("Removing markdown code block wrapper from taxonomy response")
            lines = taxonomy_text.split('\n')
            # Remove first line (```json or ```) and last line (```)
            taxonomy_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

        # Parse JSON response
        try:
            taxonomy_result = json.loads(taxonomy_text)
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse taxonomy JSON response: {e}"
            logging.error(error_msg)
            logging.error(f"Raw response text: {taxonomy_text}")
            raise ValueError(f"{error_msg}\nResponse: {taxonomy_text[:200]}...")

        # Validate required fields
        department = taxonomy_result.get('department', '')
        category = taxonomy_result.get('category', '')
        subcategory = taxonomy_result.get('subcategory', '')
        reasoning = taxonomy_result.get('reasoning', '')
        weight_estimation = taxonomy_result.get('weight_estimation', {})
        purchase_options = taxonomy_result.get('purchase_options', [])
        needs_review = taxonomy_result.get('needs_review', False)

        if not department or not category:
            error_msg = f"Taxonomy response missing required fields. Department: '{department}', Category: '{category}'"
            logging.error(error_msg)
            logging.error(f"Full taxonomy result: {taxonomy_result}")
            raise ValueError(error_msg)

        # ========== CRITICAL: VALIDATE TAXONOMY AGAINST DEFINED STRUCTURE ==========
        # TODO: Implement validate_taxonomy_assignment function
        # from .utils import validate_taxonomy_assignment

        # DISABLED: validate_taxonomy_assignment function not implemented
        # is_valid, error_msg, suggestions = validate_taxonomy_assignment(
        #     department,
        #     category,
        #     subcategory,
        #     taxonomy_path="/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md"
        # )

        if False:  # DISABLED validation block
            # Log detailed error information
            logging.error("=" * 80)
            logging.error("❌ TAXONOMY VALIDATION FAILED")
            logging.error("=" * 80)
            logging.error(f"Product: {title}")
            logging.error(f"AI assigned taxonomy:")
            logging.error(f"  - Department: {department}")
            logging.error(f"  - Category: {category}")
            logging.error(f"  - Subcategory: {subcategory}")
            logging.error(f"  - Reasoning: {reasoning}")
            logging.error("")
            logging.error(f"Error: {error_msg}")
            logging.error("")

            if "valid_departments" in suggestions:
                logging.error(f"Valid departments:")
                for dept in suggestions["valid_departments"]:
                    logging.error(f"  - {dept}")

            if "valid_categories" in suggestions:
                logging.error(f"Valid categories for '{department}':")
                for cat in suggestions["valid_categories"]:
                    logging.error(f"  - {cat}")

            if "valid_subcategories" in suggestions:
                logging.error(f"Valid subcategories for '{department}' > '{category}':")
                for subcat in suggestions["valid_subcategories"]:
                    logging.error(f"  - {subcat}")

            logging.error("")
            logging.error(f"How to fix:")
            logging.error(f"  {suggestions.get('suggestion', 'Update PRODUCT_TAXONOMY.md or correct product data')}")
            logging.error("")
            logging.error(f"Taxonomy file: /Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md")
            logging.error("=" * 80)

            # Display to user via status function
            if status_fn:
                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, "=" * 80, "error")
                log_and_status(status_fn, "❌ TAXONOMY VALIDATION FAILED - PROCESSING STOPPED", "error")
                log_and_status(status_fn, "=" * 80, "error")
                log_and_status(status_fn, f"Product: {title}", "error")
                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, f"AI tried to assign:", "error")
                log_and_status(status_fn, f"  Department: {department}", "error")
                log_and_status(status_fn, f"  Category: {category}", "error")
                if subcategory:
                    log_and_status(status_fn, f"  Subcategory: {subcategory}", "error")
                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, f"❌ {error_msg}", "error")
                log_and_status(status_fn, "", "error")

                if "valid_departments" in suggestions:
                    log_and_status(status_fn, f"Valid departments in taxonomy:", "error")
                    for dept in suggestions["valid_departments"]:
                        log_and_status(status_fn, f"  • {dept}", "error")

                if "valid_categories" in suggestions:
                    log_and_status(status_fn, f"Valid categories for '{department}':", "error")
                    for cat in suggestions["valid_categories"]:
                        log_and_status(status_fn, f"  • {cat}", "error")

                if "valid_subcategories" in suggestions:
                    log_and_status(status_fn, f"Valid subcategories for '{department}' > '{category}':", "error")
                    for subcat in suggestions["valid_subcategories"]:
                        log_and_status(status_fn, f"  • {subcat}", "error")

                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, f"💡 How to fix:", "error")
                log_and_status(status_fn, f"  {suggestions.get('suggestion', 'Update PRODUCT_TAXONOMY.md or correct product data')}", "error")
                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, f"📁 Taxonomy file:", "error")
                log_and_status(status_fn, f"  /Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md", "error")
                log_and_status(status_fn, "", "error")
                log_and_status(status_fn, "Processing stopped. Fix the taxonomy and try again.", "error")
                log_and_status(status_fn, "=" * 80, "error")

            # Raise exception to stop processing
            raise ValueError(f"Taxonomy validation failed: {error_msg}. Product cannot be categorized with current taxonomy structure.")

        if not weight_estimation or not isinstance(weight_estimation, dict):
            error_msg = f"Taxonomy response missing or invalid weight_estimation field"
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
        if needs_review:
            logging.warning(f"⚠️  NEEDS REVIEW: This product requires manual verification")

        if status_fn:
            log_and_status(status_fn, f"    ✅ Department: {department}")
            log_and_status(status_fn, f"    ✅ Category: {category}")
            if subcategory:
                log_and_status(status_fn, f"    ✅ Subcategory: {subcategory}")
            log_and_status(status_fn, f"    📝 Reasoning: {reasoning}")
            log_and_status(status_fn, f"    ⚖️  Shipping Weight: {weight_estimation.get('final_shipping_weight', 0)} lbs (confidence: {weight_estimation.get('confidence', 'unknown')})")
            if needs_review:
                log_and_status(status_fn, f"    ⚠️  NEEDS REVIEW")

        # ========== STEP 2: DESCRIPTION REWRITING ==========
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
            logging.info(f"OPENAI API CALL #2A: DESCRIPTION FOR AUDIENCE 1 ({audience_1_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_1 = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name)

            logging.debug(f"Description prompt for Audience 1 (first 500 chars):\n{description_prompt_1[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_1)} characters")
            logging.info(f"Sending description rewriting request for {audience_1_name}...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt_1}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response_1 = client.chat.completions.create(**api_params)

            logging.info(f"✅ Audience 1 description API call successful")
            logging.info(f"Token usage - Prompt: {description_response_1.usage.prompt_tokens}, Completion: {description_response_1.usage.completion_tokens}, Total: {description_response_1.usage.total_tokens}")

            input_cost, output_cost = get_openai_model_pricing(model)
            description_1_cost = (description_response_1.usage.prompt_tokens * input_cost / 1_000_000) + (description_response_1.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${description_1_cost:.6f}")
            total_description_cost += description_1_cost

            description_audience_1 = description_response_1.choices[0].message.content.strip()
            if description_audience_1.startswith("```"):
                lines = description_audience_1.split('\n')
                description_audience_1 = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

            if not description_audience_1 or len(description_audience_1.strip()) == 0:
                logging.warning(f"⚠️  OpenAI returned empty description for {audience_1_name}! Using original body_html")
                description_audience_1 = body_html

            logging.info(f"✅ Description for {audience_1_name} complete ({len(description_audience_1)} characters)")

            # Description for Audience 2
            if status_fn:
                log_and_status(status_fn, f"  ✍️  Generating description for {audience_2_name}...")

            logging.info("=" * 80)
            logging.info(f"OPENAI API CALL #2B: DESCRIPTION FOR AUDIENCE 2 ({audience_2_name})")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt_2 = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_2_name)

            logging.debug(f"Description prompt for Audience 2 (first 500 chars):\n{description_prompt_2[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt_2)} characters")
            logging.info(f"Sending description rewriting request for {audience_2_name}...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt_2}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response_2 = client.chat.completions.create(**api_params)

            logging.info(f"✅ Audience 2 description API call successful")
            logging.info(f"Token usage - Prompt: {description_response_2.usage.prompt_tokens}, Completion: {description_response_2.usage.completion_tokens}, Total: {description_response_2.usage.total_tokens}")

            description_2_cost = (description_response_2.usage.prompt_tokens * input_cost / 1_000_000) + (description_response_2.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${description_2_cost:.6f}")
            total_description_cost += description_2_cost

            description_audience_2 = description_response_2.choices[0].message.content.strip()
            if description_audience_2.startswith("```"):
                lines = description_audience_2.split('\n')
                description_audience_2 = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

            if not description_audience_2 or len(description_audience_2.strip()) == 0:
                logging.warning(f"⚠️  OpenAI returned empty description for {audience_2_name}! Using original body_html")
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
            logging.info(f"OPENAI API CALL #2: DESCRIPTION REWRITING")
            logging.info(f"Product: {title}")
            logging.info(f"Department: {department}")
            if audience_1_name:
                logging.info(f"Audience: {audience_1_name}")
            logging.info(f"Model: {model}")
            logging.info("=" * 80)

            description_prompt = _build_description_prompt(title, body_html, department, voice_tone_doc, audience_1_name if audience_1_name else None)

            logging.debug(f"Description prompt (first 500 chars):\n{description_prompt[:500]}...")
            logging.debug(f"Full prompt length: {len(description_prompt)} characters")
            logging.info("Sending description rewriting request to OpenAI API...")

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt}]
            }
            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7
            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_response = client.chat.completions.create(**api_params)

            logging.info(f"✅ Description API call successful")
            logging.info(f"Response ID: {description_response.id}")
            logging.info(f"Model used: {description_response.model}")
            logging.info(f"Finish reason: {description_response.choices[0].finish_reason}")
            logging.info(f"Token usage - Prompt: {description_response.usage.prompt_tokens}, Completion: {description_response.usage.completion_tokens}, Total: {description_response.usage.total_tokens}")

            input_cost, output_cost = get_openai_model_pricing(model)
            total_description_cost = (description_response.usage.prompt_tokens * input_cost / 1_000_000) + (description_response.usage.completion_tokens * output_cost / 1_000_000)
            logging.info(f"Cost: ${total_description_cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

            enhanced_description = description_response.choices[0].message.content.strip()

            logging.debug(f"Raw description response length: {len(enhanced_description)} characters")
            logging.debug(f"Raw description response (first 1000 chars):\n{enhanced_description[:1000]}...")

            if enhanced_description.startswith("```"):
                logging.debug("Removing markdown code block wrapper from description response")
                lines = enhanced_description.split('\n')
                enhanced_description = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])
                logging.debug(f"After removing wrapper: {len(enhanced_description)} characters")

            if not enhanced_description or len(enhanced_description.strip()) == 0:
                logging.warning("⚠️  OpenAI returned empty description! Using original body_html")
                logging.warning(f"Original body_html length: {len(body_html)} characters")
                enhanced_description = body_html

            logging.info(f"✅ Description rewritten ({len(enhanced_description)} characters)")

            if status_fn:
                log_and_status(status_fn, f"    ✅ Description rewritten ({len(enhanced_description)} characters)")

        # Calculate total cost
        total_cost = taxonomy_cost + total_description_cost
        logging.info(f"Total cost for this product: ${total_cost:.6f}")

        # Create enhanced product with new taxonomy, description, weight, and purchase options
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

        # Update ALL variants with shipping weight and weight_data
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

        # Add REQUIRED hide_online_price metafield (MUST be present for ALL products per GraphQL requirements)
        enhanced_product['metafields'].append({
            'namespace': 'custom',
            'key': 'hide_online_price',
            'value': 'true',
            'type': 'boolean'
        })

        # Add purchase_options as product-level metafield
        enhanced_product['metafields'].append({
            'namespace': 'custom',
            'key': 'purchase_options',
            'value': json.dumps(purchase_options),
            'type': 'json'
        })

        logging.info(f"✅ Added required metafields: hide_online_price=true, purchase_options={purchase_options}")

        # Add audience descriptions as metafields if multiple audiences
        if audience_count == 2 and description_audience_1 and description_audience_2:
            # Initialize metafields array if it doesn't exist
            if 'metafields' not in enhanced_product:
                enhanced_product['metafields'] = []

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

        # ========== STEP 3: SHOPIFY CATEGORY MATCHING ==========
        # Use AI to match product to Shopify's standard taxonomy
        shopify_category_id = None
        if shopify_categories and len(shopify_categories) > 0:
            try:
                shopify_category_id = match_shopify_category_with_openai(
                    title,
                    enhanced_description,
                    shopify_categories,
                    api_key,
                    model,
                    status_fn
                )
            except Exception as e:
                logging.warning(f"Failed to match Shopify category: {e}")
                shopify_category_id = None

        # Store Shopify category ID in product
        if shopify_category_id:
            enhanced_product['shopify_category_id'] = shopify_category_id
            logging.info(f"Stored Shopify category ID: {shopify_category_id}")
        else:
            enhanced_product['shopify_category_id'] = None
            logging.warning("No Shopify category ID assigned")

        logging.info("=" * 80)
        logging.info(f"✅ PRODUCT ENHANCEMENT COMPLETE: {title}")
        logging.info(f"Custom taxonomy: {department} > {category} > {subcategory}")
        logging.info(f"Shopify category ID: {enhanced_product.get('shopify_category_id', 'None')}")
        logging.info(f"Description length: {len(enhanced_description)} characters")
        logging.info("=" * 80)

        return enhanced_product

    except Exception as e:
        # Log detailed error information
        error_msg = f"Error enhancing product '{title}' with OpenAI API"
        logging.error("=" * 80)
        logging.error(f"❌ {error_msg}")
        logging.error(f"Error Type: {type(e).__name__}")
        logging.error(f"Error Details: {str(e)}")

        # Check if it's an OpenAI API error
        if OpenAI and hasattr(e, 'status_code'):
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
    Generate a collection description using OpenAI API.

    Args:
        collection_title: Collection name
        department: Department for tone selection
        product_samples: List of product descriptions from this collection
        voice_tone_doc: Voice and tone guidelines markdown content
        api_key: OpenAI API key
        model: OpenAI model ID
        status_fn: Optional status update function

    Returns:
        Generated collection description (plain text)

    Raises:
        Exception: If API call fails
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot generate collection descriptions."
        logging.error(error_msg)
        raise ImportError(error_msg)

    if not collection_title:
        error_msg = f"Collection has no title, cannot generate description"
        logging.error(error_msg)
        raise ValueError(error_msg)

    try:
        client = OpenAI(api_key=api_key)

        if status_fn:
            log_and_status(status_fn, f"  📝 Generating description for: {collection_title[:50]}...")

        logging.info("=" * 80)
        logging.info(f"OPENAI API CALL: COLLECTION DESCRIPTION")
        logging.info(f"Collection: {collection_title}")
        logging.info(f"Department: {department}")
        logging.info(f"Product samples: {len(product_samples)}")
        logging.info(f"Model: {model}")
        logging.info("=" * 80)

        collection_prompt = _build_collection_description_prompt(
            collection_title,
            department,
            product_samples,
            voice_tone_doc
        )

        # Log prompt preview
        logging.debug(f"Collection prompt (first 500 chars):\n{collection_prompt[:500]}...")
        logging.debug(f"Full prompt length: {len(collection_prompt)} characters")

        # Make API call with correct parameters based on model
        logging.info("Sending collection description request to OpenAI API...")

        # Build API call parameters
        api_params = {
            "model": model,
            "messages": [{
                "role": "user",
                "content": collection_prompt
            }]
        }

        # Add temperature only for non-reasoning models
        # Reasoning models (GPT-5, o-series) only support temperature=1 (default)
        if not is_reasoning_model(model):
            api_params["temperature"] = 0.7
            logging.debug(f"Using temperature=0.7 for model {model}")
        else:
            logging.debug(f"Omitting temperature for reasoning model {model} (only default value 1 supported)")

        # Use correct token limit parameter based on model
        # 100 words ~ 150 tokens, give buffer
        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 512
            logging.debug(f"Using max_completion_tokens=512 for model {model}")
        else:
            api_params["max_tokens"] = 512
            logging.debug(f"Using max_tokens=512 for model {model}")

        response = client.chat.completions.create(**api_params)

        # Log response details
        logging.info(f"✅ Collection description API call successful")
        logging.info(f"Response ID: {response.id}")
        logging.info(f"Model used: {response.model}")
        logging.info(f"Finish reason: {response.choices[0].finish_reason}")
        logging.info(f"Token usage - Prompt: {response.usage.prompt_tokens}, Completion: {response.usage.completion_tokens}, Total: {response.usage.total_tokens}")

        input_cost, output_cost = get_openai_model_pricing(model)
        cost = (response.usage.prompt_tokens * input_cost / 1_000_000) + (response.usage.completion_tokens * output_cost / 1_000_000)
        logging.info(f"Cost: ${cost:.6f} (Model: {model}, Pricing: ${input_cost}/${output_cost} per 1M tokens)")

        # Extract description
        description = response.choices[0].message.content.strip()
        logging.debug(f"Generated description ({len(description.split())} words):\n{description}")

        # Remove markdown code blocks if present
        if description.startswith("```"):
            logging.debug("Removing markdown code block wrapper from description")
            lines = description.split('\n')
            description = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

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

        # Check if it's an OpenAI API error
        if OpenAI and hasattr(e, 'status_code'):
            logging.error(f"HTTP Status Code: {e.status_code}")
        if hasattr(e, 'response'):
            logging.error(f"API Response: {e.response}")

        # Log full stack trace
        logging.exception("Full traceback:")
        logging.error("=" * 80)

        # Re-raise with clear message
        raise Exception(f"{error_msg}: {str(e)}") from e


# ========== PROMPT BUILDERS (MATCHING CLAUDE API PROMPTS) ==========

def _build_taxonomy_prompt(title: str, body_html: str, taxonomy_doc: str, current_weight: float = 0, variant_data: dict = None) -> str:
    """
    Build enhanced prompt for taxonomy assignment + weight estimation + purchase options.

    Args:
        title: Product title
        body_html: Product description
        taxonomy_doc: Full taxonomy document with purchase options
        current_weight: Existing weight from variant.weight field (0 if none)
        variant_data: Optional dict with variant info (dimensions, size_info metafield, etc.)

    Returns:
        Complete prompt string
    """

    # Extract dimensions from variant data if available
    dimensions_info = ""
    if variant_data:
        size_info = variant_data.get('size_info_metafield', '')
        if size_info:
            dimensions_info = f"\n- Size/Dimensions: {size_info}"

    # Build current weight info string
    if current_weight > 0:
        current_weight_info = f"\n- Current Weight (variant.weight): {current_weight} lb"
    else:
        current_weight_info = "\n- Current Weight (variant.weight): Not specified"

    # Load packaging reference document
    packaging_doc = """
PACKAGING WEIGHT REFERENCE TABLE:
Use these rules when calculating shipping weights:

| Department | Category | Subcategory | Product Packaging | Shipping Packaging | Notes |
|------------|----------|-------------|-------------------|-------------------|-------|
| **Landscape and Construction** |
| | Aggregates | Stone, Soil, Sand | Weight included in product | 2 lbs (pallet stabilization) | Sold in pre-weighted bags |
| | Aggregates | Mulch | Weight included in product | 2 lbs | Usually bagged |
| | Pavers and Hardscaping | All | 10% of product weight | 5 lbs (pallet wrap + protection) | Heavy concrete items |
| | Paving Tools & Equipment | Hand Tools | 0.5 lbs | 2 lbs (box) | Metal tools |
| | Paving Tools & Equipment | Compactors | 2 lbs | 5 lbs (crate) | Heavy machinery |
| | Paving & Construction Supplies | All | 5% of product weight | 1.5 lbs | Bagged/bottled products |
| **Lawn and Garden** |
| | Garden Tools | All | 0.5 lbs | 2 lbs (box) | Standard tools |
| | Garden Supplies | Fertilizers, Soil | Weight included | 2 lbs | Pre-bagged |
| | Garden Supplies | Planters | 10% of product weight | 3 lbs (box + bubble wrap) | Fragile |
| | Garden Decor | All | 0.3 lbs | 1.5 lbs (padded box) | Small decorative items |
| **Home and Gift** |
| | All | All | 0.3 lbs | 1.5 lbs (padded box) | Small items, fragile |
| **Pet Supplies** |
| | Dogs, Cats | Food | 5% of product weight (bag) | 3 lbs (box + padding) | Pre-weighted bags |
| | Dogs, Cats | Toys, Accessories | 0.2 lbs | 1 lb (envelope/small box) | Small items |
| | Dogs, Cats | Bedding, Crates, Carriers | 1 lb | 3 lbs (box) | Bulky items |
| | Birds, Small Pets | All | 0.3 lbs | 1.5 lbs | Smaller items |
| **Livestock and Farm** |
| | All | Hay | Weight included | 0 lbs | Customer pickup only |
| | All | Feed (not hay) | 2% of product weight | 4 lbs (box) | Large bags |
| | All | Health, Accessories | 0.5 lbs | 2 lbs | Standard items |
| **Hunting and Fishing** |
| | Deer | Blinds | 5% of product weight | 8 lbs (crate + padding) | Large bulky items |
| | Deer | All others | 0.5 lbs | 2 lbs | Standard hunting supplies |

LIQUID TO WEIGHT CONVERSION TABLE:
Use these conversions when extracting weight from liquid measures:

| Material Type | Gallons to Pounds | Fluid Ounces to Pounds |
|---------------|-------------------|------------------------|
| Water, General Liquids | 8.34 lbs/gal | 0.0652 lbs/fl oz |
| Fertilizer (liquid) | 10.5 lbs/gal | 0.0820 lbs/fl oz |
| Sealers, Adhesives | 9.0 lbs/gal | 0.0703 lbs/fl oz |
| Paint, Coatings | 11.0 lbs/gal | 0.0859 lbs/fl oz |
| Oils, Petroleum Products | 7.5 lbs/gal | 0.0586 lbs/fl oz |

When detecting material type:
- Check product title and description for keywords
- Fertilizer: "fertilizer", "plant food", "nutrient"
- Sealer: "sealer", "adhesive", "glue", "bonder"
- Paint: "paint", "stain", "coating", "finish"
- Oil: "oil", "lubricant", "petroleum"
- Default to "Water, General Liquids" if uncertain"""

    prompt = f"""You are a product categorization and logistics expert. Given the product information below, you must:
1. Assign it to the appropriate category in our taxonomy
2. Estimate shipping weight (conservative estimate to avoid undercharging)
3. Determine applicable purchase/fulfillment options based on category

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


def _build_description_prompt(title: str, body_html: str, department: str, voice_tone_doc: str, audience_name: str = None) -> str:
    """Build the prompt for description rewriting - mobile-optimized for maximum conversion."""
    audience_context = f"\nTarget Audience: {audience_name}" if audience_name else ""

    prompt = f"""You are a professional e-commerce copywriter specializing in mobile-optimized product descriptions that drive conversions.

{voice_tone_doc}

Product information:
- Title: {title}
- Department: {department}
- Current Description: {body_html}{audience_context}

CRITICAL: Write for MOBILE-FIRST experience. Most customers will read this on phones where text appears longer and attention spans are shorter.
{f"AUDIENCE: Tailor this description specifically for {audience_name}. Use language, benefits, and examples that resonate with this audience." if audience_name else ""}

STRUCTURE & LENGTH:
- Target: 150-350 words (adjust based on product complexity)
- Simple products: 150-250 words
- Moderately complex: 250-350 words
- Complex/technical: 300-400 words maximum

OPENING SECTION (First 50-100 words - MOST CRITICAL):
- Lead with PRIMARY BENEFIT and key product attributes
- Include primary keyword in opening sentence
- Focus on how product solves customer problems
- This section appears above fold on mobile - make it count!
- Answer: "Why should I care about this product?"

CONTENT PRIORITY (in order):
1. Benefits first, then features
2. Combine features WITH their benefits (never list features alone)
3. Key specifications (dimensions, material, finish, color)
4. Address common customer questions/concerns
5. Installation, usage, or maintenance guidance (if relevant)

MOBILE FORMATTING RULES:
- Short sentences (10-15 words ideal) - mobile screens make text appear longer
- Short paragraphs (3-4 sentences maximum)
- Break content into scannable chunks with clear subheadings (use <h3> tags)
- Use <strong> tags to bold key features and specs for quick scanning
- Use bullet points for technical specs (<ul><li>...</li></ul>)
- Keep bullets concise (~20 words max per bullet)
- Ensure adequate white space between sections

HTML STRUCTURE EXAMPLE:
<p>[Hook opening with primary benefit + primary keyword. 2-3 sentences max.]</p>

<h3>Key Features</h3>
<ul>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
  <li><strong>Feature:</strong> Brief benefit explanation</li>
</ul>

<h3>Applications</h3>
<p>[2-3 sentences about use cases and where/how product is used]</p>

<h3>Specifications</h3>
<ul>
  <li><strong>Material:</strong> [material]</li>
  <li><strong>Dimensions:</strong> [sizes]</li>
  <li><strong>Finish:</strong> [texture/surface]</li>
  <li><strong>Colors:</strong> [available colors]</li>
</ul>

<p>[Optional closing: maintenance, installation tip, or warranty info. 1-2 sentences.]</p>

VOICE & TONE:
- Conversational and informative (not salesy or pushy)
- Honest and specific (avoid exaggerated claims like "revolutionary" or "world-class")
- Second-person voice ("you", "your")
- Professional but accessible
- Avoid clichés and marketing jargon

SEO REQUIREMENTS:
- Include primary keyword in first 100 words
- Naturally incorporate related keywords throughout
- Minimum 150 words for SEO value
- Write for humans first, search engines second
- Use specific, descriptive terms customers search for

FOR HARDSCAPING/CONSTRUCTION PRODUCTS (pavers, slabs, stones):
Always include:
- Material composition (wet cast, concrete, natural stone, etc.)
- Finish/texture description
- Recommended applications (patios, walkways, driveways, pool decks)
- Dimensions/sizes available
- Installation considerations (if relevant)
- Durability features (stain resistance, weather resistance)
- Maintenance requirements
- Color options

CRITICAL RULES:
- Put most important information in first 75-100 words
- No lengthy paragraphs - break them up
- Make content scannable without excessive scrolling
- Every sentence must add value - cut all fluff
- Combine features with benefits - never list features without context
- Use subheadings to help mobile users scan quickly

Return ONLY the HTML description. No explanations, notes, or markdown code blocks. Just clean, mobile-optimized HTML that will go directly into body_html."""

    return prompt


def _build_collection_description_prompt(collection_title: str, department: str, product_samples: List[str], voice_tone_doc: str) -> str:
    """Build the prompt for collection description (matches claude_api.py)."""
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


# ========== BATCH API FUNCTIONS (50% COST SAVINGS) ==========

def enhance_products_with_openai_batch(
    products: List[Dict],
    taxonomy_doc: str,
    voice_tone_doc: str,
    shopify_categories: List[Dict],
    api_key: str,
    model: str,
    completion_window: str = "24h",
    poll_interval: int = 60,
    status_fn=None,
    audience_config: Dict = None
) -> List[Dict]:
    """
    Enhance multiple products using OpenAI Batch API for 50% cost savings.

    Batch API provides:
    - 50% lower costs compared to standard API
    - Asynchronous processing with 24-hour completion window
    - Same model quality and capabilities

    Args:
        products: List of product dictionaries
        taxonomy_doc: Taxonomy markdown content
        voice_tone_doc: Voice and tone guidelines markdown
        shopify_categories: List of Shopify category dicts
        api_key: OpenAI API key
        model: OpenAI model ID
        completion_window: Time window for completion (default: "24h")
        poll_interval: Seconds between status polls (default: 60)
        status_fn: Optional status update function
        audience_config: Optional audience configuration dict

    Returns:
        List of enhanced product dictionaries

    Raises:
        Exception: If batch creation or processing fails
    """
    if OpenAI is None:
        error_msg = "openai package not installed. Cannot use batch processing."
        logging.error(error_msg)
        raise ImportError(error_msg)

    import time
    import tempfile
    from pathlib import Path

    client = OpenAI(api_key=api_key)

    if status_fn:
        log_and_status(status_fn, f"🔄 Preparing batch processing for {len(products)} products...")
        log_and_status(status_fn, f"💰 Batch mode enabled: 50% cost savings")

    logging.info("=" * 80)
    logging.info(f"OPENAI BATCH API PROCESSING - 50% COST SAVINGS")
    logging.info(f"Total products: {len(products)}")
    logging.info(f"Model: {model}")
    logging.info(f"Completion window: {completion_window}")
    logging.info("=" * 80)

    # Step 1: Create batch requests for taxonomy + weight + purchase options
    if status_fn:
        log_and_status(status_fn, f"📝 Creating batch requests...")

    taxonomy_requests = []
    for i, product in enumerate(products):
        title = product.get('title', '')
        # Support both GraphQL (descriptionHtml) and REST (body_html) field names
        body_html = product.get('descriptionHtml') or product.get('body_html', '')

        # Get current weight and variant data
        current_weight = 0
        variant_data = None
        if product.get('variants') and len(product['variants']) > 0:
            first_variant = product['variants'][0]
            current_weight = first_variant.get('weight', 0)
            metafields = first_variant.get('metafields', [])
            for mf in metafields:
                if mf.get('key') == 'size_info':
                    variant_data = {'size_info_metafield': mf.get('value', '')}
                    break

        taxonomy_prompt = _build_taxonomy_prompt(title, body_html, taxonomy_doc, current_weight, variant_data)

        api_params = {
            "model": model,
            "messages": [{"role": "user", "content": taxonomy_prompt}]
        }

        if not is_reasoning_model(model):
            api_params["temperature"] = 0.3

        if uses_max_completion_tokens(model):
            api_params["max_completion_tokens"] = 16000
        else:
            api_params["max_tokens"] = 16000

        taxonomy_requests.append({
            "custom_id": f"taxonomy-{i}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": api_params
        })

    # Step 2: Write batch requests to JSONL file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
        taxonomy_batch_file = f.name
        for req in taxonomy_requests:
            f.write(json.dumps(req) + '\n')

    logging.info(f"Created batch input file: {taxonomy_batch_file}")
    logging.info(f"Total requests: {len(taxonomy_requests)}")

    # Step 3: Upload batch file
    if status_fn:
        log_and_status(status_fn, f"☁️  Uploading batch file to OpenAI...")

    try:
        with open(taxonomy_batch_file, 'rb') as f:
            batch_input_file = client.files.create(
                file=Path(taxonomy_batch_file),
                purpose="batch"
            )

        logging.info(f"✅ Uploaded batch file: {batch_input_file.id}")

        # Step 4: Create batch job
        if status_fn:
            log_and_status(status_fn, f"🚀 Starting batch processing job...")

        batch = client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window=completion_window,
            metadata={"description": "Product taxonomy and weight estimation"}
        )

        logging.info(f"✅ Created batch job: {batch.id}")
        logging.info(f"Status: {batch.status}")
        logging.info(f"Completion window: {completion_window}")

        if status_fn:
            log_and_status(status_fn, f"⏳ Batch job created: {batch.id}")
            log_and_status(status_fn, f"Status: {batch.status}")
            log_and_status(status_fn, f"Processing will complete within {completion_window}")

        # Step 5: Poll for completion
        if status_fn:
            log_and_status(status_fn, f"⏰ Waiting for batch to complete (polling every {poll_interval}s)...")

        while batch.status in ["validating", "in_progress", "finalizing"]:
            time.sleep(poll_interval)
            batch = client.batches.retrieve(batch.id)

            progress_msg = f"Status: {batch.status}"
            if batch.request_counts:
                progress_msg += f" | Completed: {batch.request_counts.completed}/{batch.request_counts.total}"
                if batch.request_counts.failed > 0:
                    progress_msg += f" | Failed: {batch.request_counts.failed}"

            logging.info(progress_msg)
            if status_fn:
                log_and_status(status_fn, f"⏳ {progress_msg}")

        # Check final status
        if batch.status != "completed":
            error_msg = f"Batch job failed with status: {batch.status}"
            logging.error(error_msg)
            if batch.errors:
                for error in batch.errors.data:
                    logging.error(f"  - {error}")
            raise Exception(error_msg)

        logging.info(f"✅ Batch job completed successfully!")
        if status_fn:
            log_and_status(status_fn, f"✅ Batch processing complete!")

        # Step 6: Download and process results
        if status_fn:
            log_and_status(status_fn, f"📥 Downloading batch results...")

        # Get output file
        output_file_id = batch.output_file_id
        output_file_response = client.files.content(output_file_id)

        # Parse results
        results = {}
        for line in output_file_response.text.strip().split('\n'):
            result = json.loads(line)
            custom_id = result['custom_id']
            results[custom_id] = result

        logging.info(f"✅ Downloaded {len(results)} results")

        # Step 7: Process taxonomy results and create description requests
        enhanced_products = []
        description_requests = []

        for i, product in enumerate(products):
            taxonomy_result_key = f"taxonomy-{i}"

            if taxonomy_result_key not in results:
                logging.error(f"Missing result for product {i}: {product.get('title', '')}")
                continue

            taxonomy_response = results[taxonomy_result_key]

            if taxonomy_response['response']['status_code'] != 200:
                logging.error(f"Taxonomy request failed for product {i}: {taxonomy_response.get('error', 'Unknown error')}")
                continue

            # Parse taxonomy response
            taxonomy_text = taxonomy_response['response']['body']['choices'][0]['message']['content']

            # Remove markdown if present
            if taxonomy_text.startswith("```"):
                lines = taxonomy_text.split('\n')
                taxonomy_text = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

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

            # DISABLED: validate_taxonomy_assignment not implemented
            # from .utils import validate_taxonomy_assignment
            # is_valid, error_msg, suggestions = validate_taxonomy_assignment(
            #     department,
            #     category,
            #     subcategory,
            #     taxonomy_path="/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md"
            # )
            #
            # if not is_valid:
            #     logging.error(f"Taxonomy validation failed for product {i}: {error_msg}")
            #     continue

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

            # Add weight estimation
            final_shipping_weight = weight_estimation.get('final_shipping_weight', 0)
            final_shipping_weight_grams = int(final_shipping_weight * 453.592)

            if 'variants' in enhanced_product and enhanced_product['variants']:
                for variant in enhanced_product['variants']:
                    variant['weight_data'] = weight_estimation
                    variant['weight'] = final_shipping_weight
                    variant['grams'] = final_shipping_weight_grams

            # Initialize metafields array if not present
            if 'metafields' not in enhanced_product:
                enhanced_product['metafields'] = []

            # Add REQUIRED hide_online_price metafield (MUST be present for ALL products per GraphQL requirements)
            enhanced_product['metafields'].append({
                'namespace': 'custom',
                'key': 'hide_online_price',
                'value': 'true',
                'type': 'boolean'
            })

            # Add purchase options metafield
            enhanced_product['metafields'].append({
                'namespace': 'custom',
                'key': 'purchase_options',
                'value': json.dumps(purchase_options),
                'type': 'json'
            })

            enhanced_products.append(enhanced_product)

            # Create description request
            title = product.get('title', '')
            # Support both GraphQL (descriptionHtml) and REST (body_html) field names
            body_html = product.get('descriptionHtml') or product.get('body_html', '')

            description_prompt = _build_description_prompt(title, body_html, department, voice_tone_doc, None)

            api_params = {
                "model": model,
                "messages": [{"role": "user", "content": description_prompt}]
            }

            if not is_reasoning_model(model):
                api_params["temperature"] = 0.7

            if uses_max_completion_tokens(model):
                api_params["max_completion_tokens"] = 2048
            else:
                api_params["max_tokens"] = 2048

            description_requests.append({
                "custom_id": f"description-{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": api_params
            })

        # Step 8: Process descriptions in batch
        if status_fn:
            log_and_status(status_fn, f"📝 Creating description batch...")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            description_batch_file = f.name
            for req in description_requests:
                f.write(json.dumps(req) + '\n')

        with open(description_batch_file, 'rb') as f:
            desc_input_file = client.files.create(
                file=Path(description_batch_file),
                purpose="batch"
            )

        desc_batch = client.batches.create(
            input_file_id=desc_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window=completion_window,
            metadata={"description": "Product description rewriting"}
        )

        logging.info(f"✅ Created description batch: {desc_batch.id}")

        if status_fn:
            log_and_status(status_fn, f"⏳ Processing descriptions...")

        # Poll for description batch completion
        while desc_batch.status in ["validating", "in_progress", "finalizing"]:
            time.sleep(poll_interval)
            desc_batch = client.batches.retrieve(desc_batch.id)

            progress_msg = f"Descriptions: {desc_batch.status}"
            if desc_batch.request_counts:
                progress_msg += f" | {desc_batch.request_counts.completed}/{desc_batch.request_counts.total}"

            logging.info(progress_msg)
            if status_fn:
                log_and_status(status_fn, f"⏳ {progress_msg}")

        if desc_batch.status != "completed":
            error_msg = f"Description batch failed: {desc_batch.status}"
            logging.error(error_msg)
            raise Exception(error_msg)

        # Download description results
        desc_output = client.files.content(desc_batch.output_file_id)
        desc_results = {}
        for line in desc_output.text.strip().split('\n'):
            result = json.loads(line)
            desc_results[result['custom_id']] = result

        # Apply descriptions to products
        for i, enhanced_product in enumerate(enhanced_products):
            desc_key = f"description-{i}"
            if desc_key in desc_results:
                desc_response = desc_results[desc_key]
                if desc_response['response']['status_code'] == 200:
                    description = desc_response['response']['body']['choices'][0]['message']['content']

                    if description.startswith("```"):
                        lines = description.split('\n')
                        description = '\n'.join(lines[1:-1] if lines[-1] == '```' else lines[1:])

                    # GraphQL format only (no REST API backward compatibility)
                    enhanced_product['descriptionHtml'] = description

        logging.info(f"✅ Batch processing complete: {len(enhanced_products)} products enhanced")
        if status_fn:
            log_and_status(status_fn, f"✅ Successfully enhanced {len(enhanced_products)} products using batch API")
            log_and_status(status_fn, f"💰 Cost savings: 50% compared to standard API")

        return enhanced_products

    finally:
        # Cleanup temp files
        import os
        try:
            os.unlink(taxonomy_batch_file)
            if 'description_batch_file' in locals():
                os.unlink(description_batch_file)
        except:
            pass
