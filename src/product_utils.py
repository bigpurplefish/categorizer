"""
Product utility functions for formatting and validating product data.

These utilities ensure consistent product data structure across AI providers.
"""

import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "collectors" / "shared"))
from utils.rich_text_utils import html_to_shopify_rich_text, HTMLToShopifyRichTextParser  # noqa: E402


# Purchase option labels for metafield
PURCHASE_OPTION_LABELS = {
    1: "Delivery (standard shipping)",
    2: "Store Pickup",
    3: "Local Delivery (within service area)",
    4: "White Glove Delivery (premium items)",
    5: "Customer Pickup Only (bulk items)"
}


def convert_weight_to_grams(weight: float, weight_unit: str = None) -> int:
    """
    Convert a weight value to grams based on its unit.

    Args:
        weight: The numeric weight value
        weight_unit: Unit of measurement ('lb', 'lbs', 'kg', 'kgs', 'oz', 'g').
                     Defaults to 'lb' if None or empty.

    Returns:
        Weight in grams as an integer
    """
    unit = (weight_unit or 'lb').strip().lower()
    if unit in ('lb', 'lbs'):
        return int(weight * 453.592)
    elif unit in ('kg', 'kgs'):
        return int(weight * 1000)
    elif unit == 'oz':
        return int(weight * 28.3495)
    elif unit == 'g':
        return int(weight)
    else:
        # Unknown unit — fall back to lb conversion
        return int(weight * 453.592)


def format_purchase_options_metafield(purchase_options: List[int]) -> str:
    """
    Format purchase options as a JSON object mapping numbers to labels.

    Args:
        purchase_options: List of purchase option numbers (e.g., [1, 2, 3])

    Returns:
        JSON string mapping option numbers to labels
        Example: '{"1": "Delivery (standard shipping)", "2": "Store Pickup", "3": "Local Delivery"}'
    """
    options_dict = {str(opt): PURCHASE_OPTION_LABELS[opt] for opt in purchase_options if opt in PURCHASE_OPTION_LABELS}
    return json.dumps(options_dict)


def add_metafield_if_not_exists(product: Dict, namespace: str, key: str, value: Any, field_type: str) -> bool:
    """
    Add a metafield to product if it doesn't already exist.

    Args:
        product: Product dictionary
        namespace: Metafield namespace
        key: Metafield key
        value: Metafield value
        field_type: Metafield type (e.g., 'boolean', 'json', 'single_line_text_field')

    Returns:
        True if metafield was added, False if it already exists
    """
    if 'metafields' not in product:
        product['metafields'] = []

    # Check if metafield already exists
    for metafield in product['metafields']:
        if metafield.get('namespace') == namespace and metafield.get('key') == key:
            logging.debug(f"Metafield {namespace}.{key} already exists, skipping")
            return False

    # Add new metafield
    product['metafields'].append({
        'namespace': namespace,
        'key': key,
        'value': value,
        'type': field_type
    })

    return True


def reorder_product_fields(product: Dict) -> Dict:
    """
    Reorder product fields according to GraphQL output requirements.

    Field order:
    1. Single-value keys (title, descriptionHtml, vendor, status, product_type, shopify_category_id, shopify_category)
    2. Array keys in order: tags, options, metafields, variants, images, media

    Args:
        product: Product dictionary with unordered fields

    Returns:
        Product dictionary with fields in correct order
    """
    # Define field order
    single_value_fields = [
        'title',
        'descriptionHtml',
        'vendor',
        'status',
        'product_type',
        'shopify_category_id',
        'shopify_category'
    ]

    array_fields = [
        'tags',
        'options',
        'metafields',
        'variants',
        'images',
        'media'
    ]

    # Build ordered dict
    ordered_product = {}

    # Add single-value fields first
    for field in single_value_fields:
        if field in product:
            ordered_product[field] = product[field]

    # Add array fields in order
    for field in array_fields:
        if field in product:
            ordered_product[field] = product[field]

    # Add any remaining fields that weren't in our predefined lists
    for key, value in product.items():
        if key not in ordered_product:
            ordered_product[key] = value

    return ordered_product


def should_calculate_shipping_weight(purchase_options: List[int]) -> bool:
    """
    Determine if shipping weight should be calculated based on purchase options.

    Args:
        purchase_options: List of purchase option numbers

    Returns:
        True if product is shipped (option 1 present), False otherwise
    """
    return 1 in purchase_options


def is_non_shipped_category(department: str, category: str) -> bool:
    """
    Check if a product category should never be shipped.

    Non-shipped categories:
    - Landscape and Construction > Aggregates (all subcategories)
    - Landscape and Construction > Pavers and Hardscaping (all subcategories)

    Args:
        department: Product department
        category: Product category

    Returns:
        True if category is never shipped, False otherwise
    """
    if department == "Landscape and Construction":
        if category in ["Aggregates", "Pavers and Hardscaping"]:
            return True

    return False


def remove_weight_data_from_variants(product: Dict) -> Dict:
    """
    Remove weight_data from all product variants.

    Used for non-shipped products where weight calculation is not needed.

    Args:
        product: Product dictionary

    Returns:
        Product dictionary with weight_data removed from variants
    """
    if 'variants' in product:
        for variant in product['variants']:
            if 'weight_data' in variant:
                del variant['weight_data']
                logging.debug(f"Removed weight_data from variant {variant.get('sku', 'unknown')}")

    return product


# Common short words that should be lowercase in title case (articles, prepositions, conjunctions)
_TITLE_CASE_LOWERCASE = {
    'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'for', 'yet', 'so',
    'in', 'on', 'at', 'to', 'by', 'of', 'up', 'as', 'is', 'it',
    'if', 'no', 'not', 'with', 'from', 'into', 'per', 'via',
}

# Words that should stay ALL-CAPS: units and known brand acronyms.
# Only words in this set will be forced uppercase; everything else gets title-cased.
_FORCE_UPPERCASE = {
    # Measurement units
    'LB', 'LBS', 'OZ', 'ML', 'KG', 'GM', 'FT', 'IN', 'YD', 'QT',
    'PT', 'GAL', 'MM', 'CM', 'CC', 'HP', 'PSI', 'RPM', 'LED', 'UV',
    'HD', 'XL', 'XXL', 'ID', 'OD',
    # Known brand acronyms
    'SOG', 'OX', 'PVC', 'USA', 'AKC', 'K9', 'GPS', 'LCD',
}


def normalize_title_case(title: str) -> str:
    """
    Normalize ALL-CAPS titles to title case.

    Detects if a title is ALL-CAPS (>=80% uppercase letters) and converts
    to title case. Fixes common .title() artifacts and preserves known
    acronyms and measurement units. Also fixes double-escaped quotes.

    Args:
        title: Product title string, or None.

    Returns:
        Normalized title string, or None if input was None.
    """
    if title is None:
        return None
    if not title:
        return title

    # Fix double-escaped quotes regardless of casing
    title = title.replace('""', '"')

    # Count uppercase vs lowercase letters to determine if ALL-CAPS
    upper_count = sum(1 for c in title if c.isupper())
    lower_count = sum(1 for c in title if c.islower())
    total_letters = upper_count + lower_count

    if total_letters == 0:
        return title

    # Only convert if >=80% of letters are uppercase
    if upper_count / total_letters < 0.80:
        return title

    # Apply .title() then fix artifacts
    result = title.title()

    # Fix apostrophe artifacts: 'S, 'T, 'Re, 'Ll, 'Ve, 'D, 'M
    result = re.sub(r"'S\b", "'s", result)
    result = re.sub(r"'T\b", "'t", result)
    result = re.sub(r"'Re\b", "'re", result)
    result = re.sub(r"'Ll\b", "'ll", result)
    result = re.sub(r"'Ve\b", "'ve", result)
    result = re.sub(r"'D\b", "'d", result)
    result = re.sub(r"'M\b", "'m", result)

    # Process each word for forced-uppercase tokens and lowercase articles
    words = result.split(' ')
    processed = []
    for i, word in enumerate(words):
        # Strip punctuation to get the core alphabetic word
        core = re.sub(r'[^A-Za-z]', '', word)
        core_upper = core.upper()

        if not core:
            # Non-alphabetic token (numbers, punctuation)
            processed.append(word)
            continue

        # Check if the word should be forced uppercase (units, brand acronyms)
        if core_upper in _FORCE_UPPERCASE:
            processed.append(_restore_upper(word))
            continue

        # Common short words should be lowercase (except first/last word)
        if core.lower() in _TITLE_CASE_LOWERCASE and i != 0 and i != len(words) - 1:
            processed.append(word.lower())
            continue

        processed.append(word)

    return ' '.join(processed)


def _restore_upper(word: str) -> str:
    """Restore all alphabetic characters in a word to uppercase."""
    return ''.join(c.upper() if c.isalpha() else c for c in word)
