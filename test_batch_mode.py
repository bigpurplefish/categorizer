#!/usr/bin/env python3
"""
Test script for Batch Mode API functionality.

This script demonstrates and tests the batch processing capabilities
for both OpenAI and Claude APIs.

IMPORTANT: This script will use API credits if run with real API keys.
For testing without costs, use mock data or test with a small sample.

Usage:
    # Test with OpenAI (GPT-5) in batch mode
    python test_batch_mode.py --provider openai --batch-mode

    # Test with Claude (Sonnet 4.5) in batch mode
    python test_batch_mode.py --provider claude --batch-mode

    # Test standard mode (for comparison)
    python test_batch_mode.py --provider openai
"""

import sys
import os
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from src.config import load_config, setup_logging
from src.ai_provider import batch_enhance_products


# Sample test products (minimal data for testing)
TEST_PRODUCTS = [
    {
        "title": "Premium Dog Food - Chicken & Rice 50lb",
        "body_html": "High quality dog food made with real chicken and rice. Perfect for adult dogs.",
        "variants": [
            {
                "title": "50 LB",
                "weight": 50.0,
                "sku": "DOG-FOOD-50"
            }
        ]
    },
    {
        "title": "Garden Stone Paver 12x12 inch",
        "body_html": "Decorative concrete paver for patios and walkways. Durable and weather-resistant.",
        "variants": [
            {
                "title": "12x12",
                "weight": 15.0,
                "sku": "PAVER-12X12"
            }
        ]
    }
]


def print_status(msg):
    """Print status message."""
    print(f"[TEST] {msg}")


def main():
    """Test batch mode functionality."""
    import argparse

    parser = argparse.ArgumentParser(description="Test batch mode API")
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        default="openai",
        help="AI provider to test"
    )
    parser.add_argument(
        "--batch-mode",
        action="store_true",
        help="Enable batch mode (50%% cost savings)"
    )
    parser.add_argument(
        "--products",
        type=int,
        default=2,
        help="Number of test products to process (default: 2)"
    )

    args = parser.parse_args()

    # Load config
    try:
        config = load_config()
    except Exception:
        print("ERROR: Could not load config.json")
        print("Please run the GUI first to create the configuration file.")
        return 1

    # Override with test settings
    config["AI_PROVIDER"] = args.provider
    config["USE_BATCH_MODE"] = args.batch_mode

    # Validate API key
    provider_name = "OpenAI" if args.provider == "openai" else "Claude"
    api_key_field = "OPENAI_API_KEY" if args.provider == "openai" else "CLAUDE_API_KEY"

    if not config.get(api_key_field):
        api_key = os.getenv(api_key_field)
        if not api_key:
            print(f"ERROR: {provider_name} API key not found.")
            print(f"Set it in config.json or via {api_key_field} environment variable.")
            return 1
        config[api_key_field] = api_key

    # Setup logging
    log_file = "test_batch_mode.log"
    setup_logging(log_file)

    # Prepare test products
    test_products = TEST_PRODUCTS[:args.products]

    print("\n" + "=" * 80)
    print("BATCH MODE TEST")
    print("=" * 80)
    print(f"Provider: {provider_name}")
    print(f"Model: {config.get('OPENAI_MODEL' if args.provider == 'openai' else 'CLAUDE_MODEL')}")
    print(f"Batch Mode: {'ENABLED (50% savings)' if args.batch_mode else 'DISABLED (standard)'}")
    print(f"Test Products: {len(test_products)}")
    print(f"Log File: {log_file}")
    print("=" * 80 + "\n")

    if args.batch_mode:
        print("⚠️  WARNING: Batch mode will submit jobs to the API and poll for completion.")
        print("   This may take several minutes to hours depending on queue.")
        print("   API costs will be 50% of standard pricing.\n")

        response = input("Continue with batch mode test? (yes/no): ")
        if response.lower() != "yes":
            print("Test cancelled.")
            return 0

    print("\nStarting enhancement process...\n")

    try:
        enhanced_products = batch_enhance_products(
            test_products,
            config,
            status_fn=print_status
        )

        print("\n" + "=" * 80)
        print("TEST RESULTS")
        print("=" * 80)
        print(f"Products processed: {len(enhanced_products)}")

        for i, product in enumerate(enhanced_products, 1):
            print(f"\nProduct {i}: {product.get('title')}")
            print(f"  Department: {product.get('product_type')}")
            print(f"  Tags: {product.get('tags')}")
            print(f"  Description length: {len(product.get('body_html', ''))} chars")

            if 'variants' in product and product['variants']:
                weight = product['variants'][0].get('weight', 0)
                print(f"  Shipping weight: {weight} lbs")

        print("\n✅ Test completed successfully!")
        print(f"📄 Check {log_file} for detailed logs")

        # Save results
        output_file = f"test_batch_results_{args.provider}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({"products": enhanced_products}, f, indent=2, ensure_ascii=False)
        print(f"💾 Results saved to: {output_file}")

        return 0

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print(f"📄 Check {log_file} for detailed error information")
        return 1


if __name__ == "__main__":
    sys.exit(main())
