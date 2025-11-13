#!/usr/bin/env python3
"""
Product Categorizer - CLI Entry Point

Command-line interface for AI-powered product categorization.
Processes products from JSON input files and enhances them with taxonomy,
weight estimation, and rewritten descriptions.
"""

import argparse
import sys
import os
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from src.config import (
    load_config,
    setup_logging,
    log_and_status,
    SCRIPT_VERSION
)
from src.ai_provider import batch_enhance_products


def print_status(message):
    """Print status message to stdout."""
    print(f"[STATUS] {message}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Product Categorizer - AI-powered product enhancement",
        epilog=f"Version {SCRIPT_VERSION}"
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input JSON file containing products"
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path to output JSON file for enhanced products"
    )
    parser.add_argument(
        "--provider",
        choices=["claude", "openai"],
        default="claude",
        help="AI provider to use (default: claude)"
    )
    parser.add_argument(
        "--claude-model",
        default="claude-sonnet-4-5-20250929",
        help="Claude model ID (default: claude-sonnet-4-5-20250929)"
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-5",
        help="OpenAI model ID (default: gpt-5)"
    )
    parser.add_argument(
        "--claude-api-key",
        help="Claude API key (or set CLAUDE_API_KEY env var)"
    )
    parser.add_argument(
        "--openai-api-key",
        help="OpenAI API key (or set OPENAI_API_KEY env var)"
    )
    parser.add_argument(
        "--taxonomy-doc",
        help="Path to taxonomy markdown document"
    )
    parser.add_argument(
        "--voice-tone-doc",
        help="Path to voice and tone guidelines document"
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output"
    )

    args = parser.parse_args()

    # Validate input file exists
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        return 1

    # Load config (use default if not exists, then override with CLI args)
    try:
        config = load_config()
    except Exception:
        # No config file, use defaults
        config = {}

    # Override config with CLI arguments
    if args.provider:
        config["AI_PROVIDER"] = args.provider
    if args.claude_model:
        config["CLAUDE_MODEL"] = args.claude_model
    if args.openai_model:
        config["OPENAI_MODEL"] = args.openai_model
    if args.claude_api_key:
        config["CLAUDE_API_KEY"] = args.claude_api_key
    if args.openai_api_key:
        config["OPENAI_API_KEY"] = args.openai_api_key
    if args.taxonomy_doc:
        config["TAXONOMY_DOC_PATH"] = args.taxonomy_doc
    if args.voice_tone_doc:
        config["VOICE_TONE_DOC_PATH"] = args.voice_tone_doc

    # Check for API keys
    if config.get("AI_PROVIDER") == "claude":
        api_key = config.get("CLAUDE_API_KEY") or os.getenv("CLAUDE_API_KEY")
        if not api_key:
            print("ERROR: Claude API key required. Provide via --claude-api-key or CLAUDE_API_KEY environment variable.")
            return 1
        config["CLAUDE_API_KEY"] = api_key
    elif config.get("AI_PROVIDER") == "openai":
        api_key = config.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("ERROR: OpenAI API key required. Provide via --openai-api-key or OPENAI_API_KEY environment variable.")
            return 1
        config["OPENAI_API_KEY"] = api_key

    # Setup logging
    log_file = args.log_file or config.get("LOG_FILE", "categorizer_cli.log")
    setup_logging(log_file)

    # Load input products
    print_status(f"Loading products from {input_path}")
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Handle both {"products": [...]} and [...] formats
        if isinstance(data, dict) and "products" in data:
            products = data["products"]
        elif isinstance(data, list):
            products = data
        else:
            print("ERROR: Input JSON must be array of products or {\"products\": [...]}")
            return 1

        print_status(f"Loaded {len(products)} products")
    except Exception as e:
        print(f"ERROR: Failed to load input file: {e}")
        return 1

    # Process products
    print_status("Starting AI enhancement...")
    try:
        enhanced_products = batch_enhance_products(
            products,
            config,
            status_fn=print_status
        )
        print_status(f"Enhanced {len(enhanced_products)} products")
    except Exception as e:
        print(f"ERROR: Failed to enhance products: {e}")
        return 1

    # Save output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print_status(f"Saving enhanced products to {output_path}")
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({"products": enhanced_products}, f, indent=2, ensure_ascii=False)
        print_status("✓ Complete!")
    except Exception as e:
        print(f"ERROR: Failed to save output file: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
