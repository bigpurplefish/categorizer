# Garoppos Product Categorizer

AI-powered product categorization, weight estimation, and description enhancement tool.

## Overview

The Product Categorizer takes JSON product data from collector scripts (enhanced with images and metadata) and uses AI to:

1. **Assign Taxonomy**: Automatically categorize products into Department > Category > Subcategory
2. **Estimate Shipping Weight**: Calculate accurate shipping weights based on product data
3. **Rewrite Descriptions**: Generate professional, SEO-optimized product descriptions
4. **Identify Purchase Options**: Determine applicable fulfillment methods (delivery, pickup, etc.)

## Quick Start

### Installation

```bash
# Install core dependencies + GUI
pip install -r requirements-gui.txt

# Or just core dependencies (CLI only)
pip install -r requirements.txt

# For development (includes testing tools)
pip install -r requirements-dev.txt
```

### Running the Application

**GUI Mode (Recommended for interactive use):**
```bash
python3 gui.py
```

**CLI Mode (For automation and scripting):**
```bash
python3 main.py --input input/products.json --output output/enhanced.json --provider claude
```

## Configuration

### API Settings

The application supports two AI providers:

- **Claude (Anthropic)**: Recommended, high-quality results
  - Get API key at: https://console.anthropic.com
  - Models: Sonnet 4.5, Opus 3.5, Sonnet 3.5, Haiku 3.5

- **OpenAI (ChatGPT)**: Cost-effective alternative
  - Get API key at: https://platform.openai.com
  - Models: GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-4o, GPT-4

Configure API keys via the **API Settings** button in the toolbar.

### File Paths

1. **Input File**: JSON file from collector scripts (e.g., `techo_bloc_products.json`)
2. **Output File**: Enhanced JSON file ready for uploader (e.g., `categorized_products.json`)
3. **Log File**: Detailed processing logs (e.g., `categorizer_log.txt`)

### Document Paths

The application uses shared documentation:

- **Taxonomy Document**: `/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md`
- **Voice/Tone Guidelines**: `/Users/moosemarketer/Code/shared-docs/python/VOICE_AND_TONE_GUIDELINES.md`

These paths are configured in `config.json` and can be modified if needed.

## Workflow

```
Collector Output (JSON)
         ↓
Product Categorizer (AI Enhancement)
         ↓
Enhanced Products (JSON)
         ↓
Shopify Uploader
```

## Features

### 1. Taxonomy Assignment

AI analyzes product title and description to assign:
- **Department**: Top-level category (e.g., "Landscape and Construction")
- **Category**: Mid-level category (e.g., "Pavers and Hardscaping")
- **Subcategory**: Specific category (e.g., "Patio Slabs")

### 2. Shipping Weight Estimation

Calculates accurate shipping weights using:
- Existing variant weights (if available)
- Extracted weights from text (e.g., "50 lb bag")
- Liquid conversions (gallons/fl oz to pounds)
- Dimensional calculations (for hardscape products)
- Conservative estimates with 10% safety margin

Includes packaging weights based on product category.

### 3. Description Rewriting

Generates mobile-optimized, SEO-friendly descriptions:
- Second-person voice ("you", "your")
- Imperative-first phrasing
- Department-specific tone (professional, empathetic, etc.)
- 150-350 words (mobile-optimized)
- Clear structure with subheadings and bullet points

### 4. Purchase Options

Identifies applicable fulfillment methods:
- Option 1: Delivery (standard shipping)
- Option 2: Store Pickup
- Option 3: Local Delivery (within service area)
- Option 4: White Glove Delivery (premium items)
- Option 5: Customer Pickup Only (hay, bulk items)

## Output Format

Enhanced products include:

```json
{
  "title": "Product Title",
  "body_html": "<p>Enhanced description...</p>",
  "product_type": "Department Name",
  "tags": ["Category", "Subcategory"],
  "variants": [
    {
      "weight": 52.7,
      "grams": 23904,
      "weight_data": {
        "original_weight": 50.0,
        "final_shipping_weight": 52.7,
        "confidence": "high",
        "source": "variant_weight",
        "reasoning": "..."
      }
    }
  ],
  "metafields": [
    {
      "namespace": "custom",
      "key": "purchase_options",
      "value": "[1, 3, 5]",
      "type": "json"
    }
  ],
  "shopify_category_id": "gid://shopify/TaxonomyCategory/..."
}
```

## Processing Cache

The application caches enhanced products to avoid redundant AI API calls:

- Cache file: `claude_enhanced_cache.json`
- Products are re-enhanced only if title or description changes
- Cache survives application restarts
- Reduces costs and processing time

## Error Handling

- **Taxonomy Validation**: Ensures AI-assigned taxonomy matches defined structure
- **Weight Review Flags**: Marks products needing manual weight verification
- **Detailed Logging**: All AI interactions logged for debugging
- **Graceful Failures**: Processing stops on errors to prevent data corruption

## Cost Estimation

Approximate costs per product (2 API calls):

- **OpenAI GPT-5 Nano**: ~$0.002 (cheapest)
- **OpenAI GPT-5 Mini**: ~$0.003
- **OpenAI GPT-5**: ~$0.008 (recommended)
- **OpenAI GPT-4o**: ~$0.015
- **Claude Sonnet 4.5**: ~$0.022
- **Claude Opus 3.5**: ~$0.040 (highest quality)

For 100 products:
- GPT-5 Nano: ~$0.20
- GPT-5: ~$0.80
- Claude Sonnet 4.5: ~$2.20

## Requirements

**Core Dependencies:**
- Python 3.12+
- anthropic (Claude AI)
- openai (OpenAI API)
- requests

**GUI Dependencies:**
- ttkbootstrap (GUI framework)

**Development Dependencies:**
- pytest (testing)
- pytest-cov (coverage)
- black, flake8 (code quality)

## Architecture

```
categorizer/
├── main.py                     # CLI entry point
├── gui.py                      # GUI entry point
├── src/                        # Application source code
│   ├── __init__.py             # Package initialization
│   ├── config.py               # Configuration and logging
│   ├── ai_provider.py          # AI provider abstraction
│   ├── claude_api.py           # Claude API implementation
│   ├── openai_api.py           # OpenAI API implementation
│   ├── taxonomy_search.py      # Shopify taxonomy matching
│   └── utils.py                # Utility functions (image counting, prompts)
├── tests/                      # Comprehensive test suite
├── docs/                       # Documentation
├── input/                      # Input JSON files
└── output/                     # Enhanced output JSON files
```

## Support

For issues or questions:
1. Check the log file for detailed error information
2. Review the taxonomy and voice/tone documents
3. Verify API keys are configured correctly
4. Ensure input JSON format matches expected structure

## Version

Current Version: **1.0.0**
