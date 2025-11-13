"""
Utility functions for the categorizer application.
"""

import logging
import re
from typing import Dict, List


def count_images_per_variant(product: Dict) -> Dict[str, int]:
    """
    Count images for each product variant by parsing alt text tags.

    Images are grouped by variant using the alt text format:
    "{Product Title} #{Variant_Identifier}"

    Example: "Purina® Amplify® High-Fat Horse Supplement #50_LB"
    The variant identifier is extracted from the part after the '#' symbol.

    Args:
        product: Product dictionary containing 'images' array and 'variants' array

    Returns:
        Dictionary mapping variant identifiers to image counts
        Example: {"50_LB": 6, "25_LB": 3}

    Example:
        >>> product = {
        ...     "images": [
        ...         {"alt": "Product Name #50_LB"},
        ...         {"alt": "Product Name #50_LB"},
        ...         {"alt": "Product Name #25_LB"}
        ...     ]
        ... }
        >>> count_images_per_variant(product)
        {'50_LB': 2, '25_LB': 1}
    """
    images = product.get('images', [])
    variant_image_counts = {}

    if not images:
        logging.debug("Product has no images")
        return variant_image_counts

    # Group images by variant identifier from alt text
    for image in images:
        alt_text = image.get('alt', '')

        if not alt_text:
            logging.debug(f"Image has no alt text, skipping: {image.get('src', 'unknown')}")
            continue

        # Extract variant identifier from alt text
        # Format: "{Product Title} #{Variant_Identifier}"
        # Example: "Purina® Amplify® High-Fat Horse Supplement #50_LB"
        match = re.search(r'#(.+)$', alt_text)

        if match:
            variant_id = match.group(1).strip()

            if variant_id in variant_image_counts:
                variant_image_counts[variant_id] += 1
            else:
                variant_image_counts[variant_id] = 1

            logging.debug(f"Image for variant '{variant_id}': {alt_text}")
        else:
            logging.warning(f"Alt text does not match expected format (no '#' found): {alt_text}")

    logging.info(f"Image count per variant: {variant_image_counts}")
    return variant_image_counts


def get_variants_needing_images(product: Dict, target_image_count: int = 5) -> Dict[str, Dict]:
    """
    Identify variants that need additional lifestyle images.

    Args:
        product: Product dictionary
        target_image_count: Target number of images per variant (default: 5)

    Returns:
        Dictionary mapping variant identifiers to info about images needed
        Example: {
            "50_LB": {
                "existing_count": 2,
                "images_needed": 3,
                "variant_data": {...}  # Full variant object
            }
        }
    """
    image_counts = count_images_per_variant(product)
    variants = product.get('variants', [])
    variants_needing_images = {}

    if not variants:
        logging.debug("Product has no variants")
        return variants_needing_images

    # For each variant, check if it needs more images
    for variant in variants:
        # Extract variant identifier from option1 (primary size/option)
        variant_id = variant.get('option1', '')

        # Normalize the variant ID to match the format in alt text
        # Replace spaces with underscores and convert to the same format
        variant_id_normalized = variant_id.replace(' ', '_')

        # Get existing image count for this variant
        existing_count = image_counts.get(variant_id_normalized, 0)

        if existing_count < target_image_count:
            images_needed = target_image_count - existing_count
            variants_needing_images[variant_id_normalized] = {
                "existing_count": existing_count,
                "images_needed": images_needed,
                "variant_data": variant,
                "variant_option_value": variant_id  # Original format (e.g., "50 LB")
            }

            logging.info(f"Variant '{variant_id}' needs {images_needed} more images (has {existing_count}/{target_image_count})")
        else:
            logging.debug(f"Variant '{variant_id}' has enough images ({existing_count}/{target_image_count})")

    return variants_needing_images


def build_gemini_lifestyle_prompt_for_variant(
    product_title: str,
    product_description: str,
    variant_option_value: str,
    images_needed: int,
    department: str,
    category: str,
    subcategory: str
) -> str:
    """
    Build a prompt for Gemini Flash 2.5 to generate photorealistic lifestyle product images.

    The prompt instructs Gemini to create lifestyle images that:
    - Are photorealistic
    - Feature people/animals when appropriate based on product taxonomy
    - Show subjects using the product in an appropriate setting
    - Feature smiling people reflective of the Newfield, NJ 08009 demographics
    - Tell a story of happy customers
    - Are unique for each product
    - Have square 2048x2048px aspect ratio

    Args:
        product_title: Product title
        product_description: Product description HTML
        variant_option_value: Variant option (e.g., "50 LB")
        images_needed: Number of images to generate
        department: Product department
        category: Product category
        subcategory: Product subcategory

    Returns:
        Complete Gemini prompt string ready to use
    """
    # Build the taxonomy context
    taxonomy_context = f"{department}"
    if category:
        taxonomy_context += f" > {category}"
    if subcategory:
        taxonomy_context += f" > {subcategory}"

    prompt = f"""Generate {images_needed} unique, photorealistic lifestyle product images for the following product:

**Product Details:**
- Product: {product_title} ({variant_option_value})
- Taxonomy: {taxonomy_context}
- Description: {product_description}

**Image Requirements:**

1. **Photorealism:**
   - Images must be photorealistic, not illustrated or cartoon-style
   - High quality, professional product photography aesthetic
   - Natural lighting and realistic shadows
   - Sharp focus on the product

2. **Lifestyle Context:**
   - Show the product being used in an appropriate, realistic setting based on its category
   - Include people and/or animals when appropriate for the product type and taxonomy category
   - People should be actively using or interacting with the product
   - Settings should match the product's intended use case (e.g., farm/ranch for livestock feed, home garden for garden supplies, pet home environment for pet products)

3. **Subject Demographics (when people are included):**
   - Analyze the product and its taxonomy to determine the most likely customer demographic
   - Consider that this store is located in Newfield, NJ 08009 - a rural South Jersey community
   - For farm/livestock/agricultural products: Show working professionals in appropriate work attire
   - For pet products: Show families or individuals of diverse ages who would own pets
   - For garden/landscape products: Show homeowners and DIY enthusiasts
   - For hunting/fishing: Show outdoor enthusiasts in appropriate gear
   - All people should be smiling and appear genuinely happy while using the product
   - Reflect diversity appropriate to rural South Jersey demographics

4. **Uniqueness and Storytelling:**
   - Each of the {images_needed} images should tell a different story or show a different use case
   - Vary the settings, angles, and scenarios across the image set
   - Show different benefits or features of the product through the images
   - Create a cohesive visual story of satisfied customers enjoying the product

5. **Technical Specifications:**
   - Aspect ratio: Square (1:1)
   - Resolution: 2048x2048 pixels
   - File format: JPEG or PNG
   - Suitable for Shopify product gallery display

**Important Guidelines:**
- The product should be clearly visible and identifiable in each image
- Avoid cluttered backgrounds that distract from the product
- Ensure people (when included) look natural and authentic, not overly posed
- Match the tone and style to the product category (professional for construction, warm for pets, etc.)
- Do NOT include any text, logos, or branding overlays on the images
- Images should be suitable for e-commerce use

Please generate {images_needed} distinct lifestyle images following these specifications."""

    return prompt
