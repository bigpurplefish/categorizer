# Categorizer Project - Extraction Summary

**Date**: November 13, 2025
**Source**: Garoppos Uploader v2.6.0
**Target**: Garoppos Categorizer v1.0.0

## Overview

This document summarizes the extraction of AI-powered product categorization functionality from the Shopify Product Uploader into a new standalone Categorizer project.

## Motivation

The original uploader combined two distinct responsibilities:
1. **Content Enhancement** - AI-powered taxonomy assignment, description rewriting, weight estimation
2. **Shopify Upload** - Product/collection creation, variant management, media upload

This violates the Single Responsibility Principle and created unnecessary coupling. The refactoring separates these concerns into two focused, maintainable applications.

## Project Relationships

```
Collectors (scrapers) → Categorizer (AI enhancement) → Uploader (Shopify upload)
```

### Data Flow

1. **Collectors** → Output raw product data (JSON)
2. **Categorizer** → Enhance with taxonomy, descriptions, weights (JSON)
3. **Uploader** → Upload enhanced products to Shopify

Each project can be run independently and has clear input/output contracts.

## What Was Moved

### Files Moved to Categorizer

**Core Modules:**
- `uploader_modules/openai_api.py` → `categorizer_modules/openai_api.py`
- `uploader_modules/claude_api.py` → `categorizer_modules/claude_api.py`
- `uploader_modules/ai_provider.py` → `categorizer_modules/ai_provider.py`

**New Module Created:**
- `categorizer_modules/taxonomy_search.py` - Extracted taxonomy functions from `shopify_api.py`:
  - `search_shopify_taxonomy()`
  - `fetch_shopify_taxonomy_from_github()`
  - `fetch_all_shopify_categories()`
  - `get_taxonomy_id()`
  - `load_taxonomy_cache()` / `save_taxonomy_cache()`

**Configuration:**
- `categorizer_modules/config.py` - Config management for categorizer

**Documentation:**
- `docs/PRODUCT_TAXONOMY.md` - Product taxonomy structure
- `docs/VOICE_AND_TONE_GUIDELINES.md` - Content writing standards

**Cache Files:**
- `product_taxonomy.json` - Taxonomy ID cache
- `shopify_taxonomy_cache.json` - Full taxonomy cache

### Files Created

**Main Application:**
- `categorizer.py` - GUI application (800+ lines)

**Tests:**
- `tests/conftest.py` - Shared test fixtures
- `tests/test_taxonomy_search.py` - 37 tests for taxonomy functionality
- `tests/test_config.py` - 30 tests for configuration management

**Documentation:**
- `CLAUDE.md` - Project-specific development guide
- `README.md` - User documentation
- `requirements.txt` - Python dependencies
- `PROJECT_EXTRACTION_SUMMARY.md` - This document

## What Was Removed from Uploader

### Code Removed

**Modules:**
- `uploader_modules/openai_api.py` (deleted)
- `uploader_modules/claude_api.py` (deleted)
- `uploader_modules/ai_provider.py` (deleted)

**Functions from `shopify_api.py`:**
- `search_shopify_taxonomy()` (291 lines)
- `get_taxonomy_id()` (with fallback strategies)
- Related imports and dependencies

**GUI Elements from `gui.py`:**
- AI Provider dropdown
- AI Model selection
- "Use AI for taxonomy and descriptions" checkbox
- Claude/OpenAI API Key fields
- Audience configuration fields
- All AI-related callbacks and state management

**Processing Logic from `product_processing.py`:**
- AI enhancement calls (batch_enhance_products)
- Collection description generation
- All taxonomy assignment via AI
- Description rewriting via AI

**Configuration from `config.py`:**
- `AI_PROVIDER`, `USE_AI_ENHANCEMENT`
- `CLAUDE_API_KEY`, `CLAUDE_MODEL`
- `OPENAI_API_KEY`, `OPENAI_MODEL`
- `AUDIENCE_COUNT`, audience names and tab labels

**Dependencies from `requirements.txt`:**
- `anthropic>=0.18.0`
- `openai>=1.0.0`

## Categorizer Features

### Core Functionality

1. **Taxonomy Assignment**
   - Analyzes product title, description, dimensions
   - Assigns Department, Category, Subcategory
   - Validates against internal taxonomy structure
   - Uses multi-strategy matching (exact, contains, keyword)

2. **Shipping Weight Estimation**
   - Calculates weight based on product dimensions and type
   - Provides confidence levels (low/medium/high)
   - Includes packaging estimates
   - Adds 10% safety margin
   - Detailed reasoning for estimates

3. **Description Rewriting**
   - Rewrites per voice/tone guidelines
   - Department-specific tone (empathetic for pets, professional for construction)
   - Ensures uniqueness (no 7+ word repetitions)
   - Second-person voice, imperative-first phrasing
   - Maintains factual accuracy

4. **Collection Description Generation**
   - Samples products from collection (up to 5)
   - Generates SEO-optimized 100-word descriptions
   - Applies appropriate department tone

5. **Purchase Options Analysis**
   - Identifies primary purchase consideration
   - Options: price, quality, features, brand, reviews
   - Stored as product metafield

### AI Provider Support

**Claude (Anthropic):**
- Models: Sonnet 4.5, Opus 3.5, Sonnet 3.5, Haiku 3.5
- Best for complex reasoning and detailed analysis
- Higher cost, higher quality

**OpenAI (ChatGPT):**
- Models: GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-4o, GPT-4o Mini
- Good balance of speed and accuracy
- More cost-effective for large batches

### Technical Stack

- **GUI**: ttkbootstrap with 'darkly' theme
- **AI Integration**: anthropic SDK, openai SDK
- **Taxonomy**: Shopify GraphQL API 2025-10
- **Caching**: JSON file-based caching (30-day duration)
- **Testing**: pytest with 67 tests, comprehensive mocking

## Uploader Changes

### New Scope

The uploader is now a **pure Shopify upload tool** that:
- Accepts pre-enhanced product data
- Creates collections (department, category, subcategory)
- Uploads products with all fields
- Manages variants, images, 3D models, metafields
- Publishes to sales channels
- Handles state management for crash recovery

### Expected Input Format

Products must come from categorizer with:
- `product_type` - Department (e.g., "Pet Supplies")
- `tags` - [Category, Subcategory] (e.g., ["Dogs", "Dog Food"])
- `body_html` - Rewritten description
- `weight` - Estimated shipping weight in pounds
- `weight_unit` - "lb"
- `metafields` - Including weight_data, purchase_options

### Retained Functionality

- Product creation (productCreate mutation)
- Variant bulk creation (productVariantsBulkCreate)
- Collection management (smart collections with rules)
- 3D model upload (staged upload process)
- Metafield definitions
- Sales channel publishing
- Resume/overwrite modes
- State management

## Directory Structure

### Categorizer Project

```
/Users/moosemarketer/Code/garoppos/categorizer/
├── CLAUDE.md                          # Development guide
├── README.md                          # User documentation
├── PROJECT_EXTRACTION_SUMMARY.md      # This file
├── requirements.txt                   # Dependencies
├── categorizer.py                     # Main GUI application
├── config.json                        # User configuration (gitignored)
├── product_taxonomy.json              # Taxonomy cache (gitignored)
├── shopify_taxonomy_cache.json        # Full taxonomy cache (gitignored)
├── categorizer_modules/
│   ├── __init__.py
│   ├── ai_provider.py                 # Abstract AI interface
│   ├── claude_api.py                  # Claude implementation
│   ├── openai_api.py                  # OpenAI implementation
│   ├── taxonomy_search.py             # Shopify taxonomy search
│   └── config.py                      # Configuration management
├── docs/
│   ├── PRODUCT_TAXONOMY.md            # Taxonomy structure
│   └── VOICE_AND_TONE_GUIDELINES.md   # Writing standards
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Shared fixtures
│   ├── test_config.py                 # 30 tests
│   └── test_taxonomy_search.py        # 37 tests
├── input/                             # Input JSON files
└── output/                            # Output JSON files
```

### Uploader Project (Updated)

```
/Users/moosemarketer/Code/garoppos/uploader/
├── CLAUDE.md                          # Updated - no AI references
├── uploader.py                        # Main entry point (unchanged)
├── requirements.txt                   # Updated - removed AI dependencies
├── uploader_modules/
│   ├── shopify_api.py                 # Reduced from 1208 to 917 lines
│   ├── gui.py                         # Removed AI GUI elements
│   ├── product_processing.py          # Removed AI enhancement calls
│   ├── config.py                      # Removed AI config fields
│   └── ... (other modules unchanged)
└── tests/                             # Existing tests (kept for reference)
```

## Workflow Examples

### Complete Workflow

```bash
# Step 1: Run collector to scrape manufacturer website
cd /Users/moosemarketer/Code/garoppos/collectors/purinamills
python3 main.py
# Output: purinamills/output/purinamills-enriched.json

# Step 2: Run categorizer to enhance products
cd /Users/moosemarketer/Code/garoppos/categorizer
python3 categorizer.py
# Input: Select purinamills-enriched.json
# Output: categorizer/output/purinamills-categorized.json

# Step 3: Run uploader to push to Shopify
cd /Users/moosemarketer/Code/garoppos/uploader
python3 uploader.py
# Input: Select purinamills-categorized.json
# Output: Products live on Shopify store
```

### Independent Testing

Each project can be tested independently:

```bash
# Test categorizer
cd /Users/moosemarketer/Code/garoppos/categorizer
python -m pytest tests/ -v --cov=categorizer_modules

# Test uploader
cd /Users/moosemarketer/Code/garoppos/uploader
python -m pytest tests/ -v --cov=uploader_modules
```

## Benefits of Separation

1. **Single Responsibility** - Each project has one clear purpose
2. **Independent Deployment** - Can update/deploy separately
3. **Easier Testing** - Smaller scope, focused tests
4. **Better Maintainability** - Changes isolated to relevant project
5. **Reusability** - Categorizer can enhance data for uses beyond Shopify
6. **Cost Control** - Can run categorizer offline/batched, uploader separately
7. **Failure Isolation** - AI issues don't block Shopify uploads
8. **Team Organization** - Different teams can own different projects

## Migration Notes

### For Existing Users

If you were using the uploader with AI enhancement enabled:

1. **Update your workflow** - Run categorizer first, then uploader
2. **Install categorizer** - New project with its own dependencies
3. **Configuration split** - AI keys move to categorizer config.json
4. **Cache files moved** - Taxonomy caches now in categorizer directory

### Backwards Compatibility

The uploader can still work with old JSON formats that lack enhanced fields:
- Products without `product_type` get default department
- Products without `weight` use variant weight field (if present)
- Products without rewritten descriptions use original `description_1`

### Breaking Changes

- Uploader no longer performs AI enhancement (intentional)
- Uploader no longer validates taxonomy (done by categorizer)
- Uploader config.json format changed (AI fields removed)

## Testing Status

### Categorizer

✅ **67 tests, all passing**
- 30 config tests
- 37 taxonomy tests
- Full mock coverage (no actual API calls)
- Comprehensive error handling

### Uploader

✅ **169 tests, all passing**
- Previous test suite maintained
- Tests adapted for new scope
- AI-related tests archived

## Next Steps

### Categorizer

- [ ] Create .gitignore for cache files and config.json
- [ ] Set up git repository
- [ ] Add more AI provider tests
- [ ] Performance optimization for batch processing

### Uploader

- [ ] Update test suite to remove AI test references
- [ ] Performance testing with categorizer output
- [ ] Update user documentation

## Conclusion

The categorizer project successfully extracts AI enhancement functionality from the uploader, creating two focused, maintainable applications. The separation improves code quality, testability, and deployment flexibility while maintaining a clear data pipeline from collectors → categorizer → uploader → Shopify.

Both projects follow shared Python standards and use Context7 for up-to-date library documentation, ensuring consistency and maintainability across the Garoppos product data pipeline.
