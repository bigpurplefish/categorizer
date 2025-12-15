"""
Product utility functions for formatting and validating product data.

These utilities ensure consistent product data structure across AI providers.
"""

import json
import logging
import re
from typing import Dict, List, Any
from html.parser import HTMLParser


class HTMLToShopifyRichTextParser(HTMLParser):
    """
    Parser to convert HTML to Shopify rich text JSON format.

    Supports: paragraphs, headings (h1-h6), bold, italic, links, ordered/unordered lists.
    """

    def __init__(self):
        super().__init__()
        self.children = []
        self.stack = []
        self.current_text_attrs = {}

    def _current_parent(self):
        if self.stack:
            return self.stack[-1].get('children', [])
        return self.children

    def _flush_text(self, text: str):
        if not text:
            return
        text_node = {"type": "text", "value": text}
        if self.current_text_attrs.get('bold'):
            text_node['bold'] = True
        if self.current_text_attrs.get('italic'):
            text_node['italic'] = True
        self._current_parent().append(text_node)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)

        if tag == 'p':
            node = {"type": "paragraph", "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level = int(tag[1])
            node = {"type": "heading", "level": level, "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag == 'ul':
            node = {"type": "list", "listType": "unordered", "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag == 'ol':
            node = {"type": "list", "listType": "ordered", "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag == 'li':
            node = {"type": "list-item", "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag in ('strong', 'b'):
            self.current_text_attrs['bold'] = True
        elif tag in ('em', 'i'):
            self.current_text_attrs['italic'] = True
        elif tag == 'a':
            href = attrs_dict.get('href', '')
            node = {"type": "link", "url": href, "children": []}
            self._current_parent().append(node)
            self.stack.append(node)
        elif tag == 'br':
            self._flush_text("\n")

    def handle_endtag(self, tag):
        if tag in ('p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'a'):
            if self.stack:
                self.stack.pop()
        elif tag in ('strong', 'b'):
            self.current_text_attrs['bold'] = False
        elif tag in ('em', 'i'):
            self.current_text_attrs['italic'] = False

    def handle_data(self, data):
        text = data.strip()
        if text:
            self._flush_text(text)

    def get_result(self) -> dict:
        return {"type": "root", "children": self.children}


def html_to_shopify_rich_text(html: str) -> str:
    """
    Convert HTML to Shopify rich_text_field JSON format.

    Args:
        html: HTML string to convert

    Returns:
        JSON string in Shopify rich text format
    """
    if not html or not html.strip():
        return json.dumps({"type": "root", "children": []})

    html = re.sub(r'>\s+<', '><', html)

    parser = HTMLToShopifyRichTextParser()
    parser.feed(html)
    result = parser.get_result()

    if not result['children']:
        plain_text = re.sub(r'<[^>]+>', '', html).strip()
        if plain_text:
            result['children'] = [{
                "type": "paragraph",
                "children": [{"type": "text", "value": plain_text}]
            }]

    return json.dumps(result)


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
