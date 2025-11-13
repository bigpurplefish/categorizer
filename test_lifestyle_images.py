#!/usr/bin/env python3
"""
Test script for lifestyle image prompt generation feature.

Tests the image counting and prompt generation logic with sample products.
"""

import json
import sys
import os

# Add categorizer_modules to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'categorizer_modules'))

from utils import count_images_per_variant, get_variants_needing_images, build_gemini_lifestyle_prompt_for_variant


def test_image_counting():
    """Test image counting per variant."""
    print("=" * 80)
    print("TEST 1: Image Counting Per Variant")
    print("=" * 80)

    # Test product with multiple images for one variant
    product1 = {
        "title": "Purina® Amplify® High-Fat Horse Supplement",
        "images": [
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"}
        ]
    }

    counts1 = count_images_per_variant(product1)
    print(f"\nProduct: {product1['title']}")
    print(f"Image counts: {counts1}")
    print(f"✅ Expected: {{'50_LB': 6}}, Got: {counts1}")
    assert counts1 == {'50_LB': 6}, f"Expected {{'50_LB': 6}}, got {counts1}"

    # Test product with one image
    product2 = {
        "title": "PURINA® COUNTRY ACRES CAT",
        "images": [
            {"alt": "PURINA® COUNTRY ACRES CAT #40_LB"}
        ]
    }

    counts2 = count_images_per_variant(product2)
    print(f"\nProduct: {product2['title']}")
    print(f"Image counts: {counts2}")
    print(f"✅ Expected: {{'40_LB': 1}}, Got: {counts2}")
    assert counts2 == {'40_LB': 1}, f"Expected {{'40_LB': 1}}, got {counts2}"

    # Test product with no images
    product3 = {
        "title": "Test Product",
        "images": []
    }

    counts3 = count_images_per_variant(product3)
    print(f"\nProduct: {product3['title']}")
    print(f"Image counts: {counts3}")
    print(f"✅ Expected: {{}}, Got: {counts3}")
    assert counts3 == {}, f"Expected {{}}, got {counts3}"

    print("\n✅ All image counting tests passed!")


def test_variants_needing_images():
    """Test identification of variants needing additional images."""
    print("\n" + "=" * 80)
    print("TEST 2: Identifying Variants Needing Images")
    print("=" * 80)

    # Product with 1 image, needs 4 more
    product1 = {
        "title": "PURINA® COUNTRY ACRES CAT",
        "images": [
            {"alt": "PURINA® COUNTRY ACRES CAT #40_LB"}
        ],
        "variants": [
            {"option1": "40 LB", "sku": "313"}
        ]
    }

    needs_images1 = get_variants_needing_images(product1, target_image_count=5)
    print(f"\nProduct: {product1['title']}")
    print(f"Variants needing images: {list(needs_images1.keys())}")

    if '40_LB' in needs_images1:
        print(f"  - 40_LB: needs {needs_images1['40_LB']['images_needed']} images (has {needs_images1['40_LB']['existing_count']}/5)")
        assert needs_images1['40_LB']['images_needed'] == 4, "Should need 4 images"
        assert needs_images1['40_LB']['existing_count'] == 1, "Should have 1 existing image"
        print("  ✅ Correct!")
    else:
        raise AssertionError("40_LB variant not found in needs_images1")

    # Product with 6 images, needs 0 more (already has enough)
    product2 = {
        "title": "Purina® Amplify® High-Fat Horse Supplement",
        "images": [
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"},
            {"alt": "Purina® Amplify® High-Fat Horse Supplement #50_LB"}
        ],
        "variants": [
            {"option1": "50 LB", "sku": "7676"}
        ]
    }

    needs_images2 = get_variants_needing_images(product2, target_image_count=5)
    print(f"\nProduct: {product2['title']}")
    print(f"Variants needing images: {list(needs_images2.keys())}")

    if len(needs_images2) == 0:
        print("  ✅ Correct! Product has enough images (6/5)")
    else:
        raise AssertionError(f"Expected 0 variants needing images, got {len(needs_images2)}")

    print("\n✅ All variant identification tests passed!")


def test_gemini_prompt_generation():
    """Test Gemini prompt generation."""
    print("\n" + "=" * 80)
    print("TEST 3: Gemini Prompt Generation")
    print("=" * 80)

    prompt = build_gemini_lifestyle_prompt_for_variant(
        product_title="PURINA® COUNTRY ACRES CAT",
        product_description="<p>Purina Animal Nutrition Country Acres Farm Cat 40LB</p>",
        variant_option_value="40 LB",
        images_needed=4,
        department="Pet Supplies",
        category="Cats",
        subcategory="Cat Food"
    )

    print(f"\nGenerated Gemini prompt (first 500 chars):")
    print("-" * 80)
    print(prompt[:500])
    print("...")
    print("-" * 80)
    print(f"\nFull prompt length: {len(prompt)} characters")

    # Verify key elements are in the prompt
    assert "PURINA® COUNTRY ACRES CAT" in prompt, "Product title missing"
    assert "40 LB" in prompt, "Variant option missing"
    assert "4 unique, photorealistic lifestyle product images" in prompt, "Image count missing"
    assert "Pet Supplies > Cats > Cat Food" in prompt, "Taxonomy missing"
    assert "Newfield, NJ 08009" in prompt, "Location missing"
    assert "2048x2048 pixels" in prompt, "Resolution specification missing"
    assert "Square (1:1)" in prompt, "Aspect ratio missing"

    print("\n✅ All required elements present in prompt!")
    print("✅ Gemini prompt generation test passed!")


def test_with_real_product_data():
    """Test with real product data from purinamills.json."""
    print("\n" + "=" * 80)
    print("TEST 4: Real Product Data from purinamills.json")
    print("=" * 80)

    json_path = "/Users/moosemarketer/Code/garoppos/collectors/purinamills/output/purinamills.json"

    if not os.path.exists(json_path):
        print(f"⚠️  Warning: {json_path} not found, skipping real data test")
        return

    with open(json_path, 'r') as f:
        data = json.load(f)

    products = data.get('products', [])
    print(f"\nLoaded {len(products)} products from purinamills.json")

    # Test first 5 products
    for i, product in enumerate(products[:5], 1):
        title = product.get('title', 'Untitled')
        print(f"\n{i}. {title}")

        # Count images
        image_counts = count_images_per_variant(product)
        print(f"   Image counts: {image_counts}")

        # Check which variants need images
        needs_images = get_variants_needing_images(product, target_image_count=5)

        if needs_images:
            print(f"   ⚠️  Needs images for {len(needs_images)} variant(s):")
            for variant_id, info in needs_images.items():
                print(f"      - {variant_id}: needs {info['images_needed']} more images (has {info['existing_count']}/5)")
        else:
            print(f"   ✅ All variants have sufficient images")

    print("\n✅ Real product data test completed!")


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("LIFESTYLE IMAGE PROMPT GENERATION - TEST SUITE")
    print("=" * 80)

    try:
        test_image_counting()
        test_variants_needing_images()
        test_gemini_prompt_generation()
        test_with_real_product_data()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)

    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
