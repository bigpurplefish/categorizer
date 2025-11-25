"""
Product utility functions for formatting and validating product data.

These utilities ensure consistent product data structure across AI providers.
"""

import json
import logging
from typing import Dict, List, Any


# Purchase option labels for metafield
PURCHASE_OPTION_LABELS = {
    1: "Delivery (standard shipping)",
    2: "Store Pickup",
    3: "Local Delivery (within service area)",
    4: "White Glove Delivery (premium items)",
    5: "Customer Pickup Only (bulk items)"
}


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
