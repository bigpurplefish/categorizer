# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python GUI application for enriching product data with AI-powered taxonomy assignment, description rewriting, and metadata generation. It processes JSON output from collector projects and enhances it with:

- **Taxonomy Assignment**: Automatically assigns products to Department, Category, and Subcategory
- **Shipping Weight Estimation**: Calculates estimated shipping weights with confidence levels
- **Description Rewriting**: Rewrites product descriptions according to brand voice and tone guidelines
- **Collection Descriptions**: Generates SEO-optimized descriptions for product collections
- **Purchase Options Analysis**: Identifies primary purchase considerations (price, quality, features, etc.)

**Main Script:** `categorizer.py`
**Current Version:** 1.0.0

## Shared Requirements

**IMPORTANT**: This project MUST explicitly follow the requirements documentation located in `/Users/moosemarketer/Code/shared-docs/python`.

**Always reference shared docs - NEVER duplicate them locally.**

### Shared Documentation Reference

The following requirements are defined in shared-docs and should always be referenced (not duplicated):

- **[PRODUCT_TAXONOMY.md](../../../shared-docs/python/PRODUCT_TAXONOMY.md)** - Product categorization hierarchy and purchase options
- **[PACKAGING_WEIGHT_REFERENCE.md](../../../shared-docs/python/PACKAGING_WEIGHT_REFERENCE.md)** - Shipping weight calculation guidelines
- **[PROJECT_STRUCTURE_REQUIREMENTS.md](../../../shared-docs/python/PROJECT_STRUCTURE_REQUIREMENTS.md)** - Python project structure conventions
- **[GIT_WORKFLOW.md](../../../shared-docs/python/GIT_WORKFLOW.md)** - Git commit and workflow standards
- **[LOGGING_REQUIREMENTS.md](../../../shared-docs/python/LOGGING_REQUIREMENTS.md)** - Logging patterns and requirements
- **[GUI_DESIGN_REQUIREMENTS.md](../../../shared-docs/python/GUI_DESIGN_REQUIREMENTS.md)** - GUI design standards
- **[GRAPHQL_OUTPUT_REQUIREMENTS.md](../../../shared-docs/python/GRAPHQL_OUTPUT_REQUIREMENTS.md)** - GraphQL output format requirements
- **[COMPLIANCE_CHECKLIST.md](../../../shared-docs/python/COMPLIANCE_CHECKLIST.md)** - Project compliance verification

### Project-Specific Documentation

The following docs are specific to this project (kept in local `docs/`):

- **`docs/VOICE_AND_TONE_GUIDELINES.md`** - Brand voice and tone for product descriptions

### Using Context7 for Documentation

When generating or updating code, planning features, or researching solutions, **ALWAYS use Context7** to fetch up-to-date documentation for:

- Python language features
- Library APIs (anthropic, openai, requests, ttkbootstrap, etc.)
- Best practices and design patterns

Use the Context7 MCP tools:
1. `mcp__context7__resolve-library-id` - Find the library ID
2. `mcp__context7__get-library-docs` - Fetch documentation

Example workflow:
```
1. Resolve library: "anthropic" → /anthropic/anthropic-sdk-python
2. Fetch docs for specific topic: "streaming responses"
3. Apply latest API patterns from documentation
```

## Development Commands

### Running the Application
```bash
python3 categorizer.py
```

### Installing Dependencies
```bash
pip install -r requirements.txt
```

Required packages:
- `ttkbootstrap>=1.10.0` - Modern themed tkinter GUI
- `requests>=2.28.0` - HTTP library for API calls
- `anthropic>=0.18.0` - Claude AI API client
- `openai>=1.0.0` - OpenAI API client

## Input/Output

### Input Format
Accepts JSON files output by collector projects. Expected structure:
- Array of product objects
- Each product has: `item_#`, `description_1`, `size`, `upc_updated`, `manufacturer_found`, etc.
- Support for parent/child variant relationships via `parent` field
- See `/Users/moosemarketer/Code/garoppos/collectors/shared-docs/INPUT_FILE_STRUCTURE.md`

### Output Format
Enhanced JSON with additional fields:
- `product_type`: Department (e.g., "Pet Supplies", "Landscape And Construction")
- `tags`: [Category, Subcategory] array
- `body_html`: Rewritten product description
- `weight`: Estimated shipping weight (in pounds)
- `weight_unit`: "lb"
- `metafields`: Additional metadata including weight estimation details and purchase options

## Architecture

### Core Modules

- **`categorizer_modules/ai_provider.py`**: Abstract AI provider interface
- **`categorizer_modules/claude_api.py`**: Claude (Anthropic) implementation
- **`categorizer_modules/openai_api.py`**: OpenAI implementation
- **`categorizer_modules/taxonomy_search.py`**: Shopify taxonomy search and matching
- **`categorizer_modules/utils.py`**: Utility functions

### Data Flow

```
Collector JSON → Load Products → AI Enhancement → Output Enhanced JSON
                                      ↓
                      (Taxonomy + Weight + Description)
```

### Configuration

**`config.json`** structure:
- AI Provider settings: `AI_PROVIDER` ("claude" or "openai")
- Claude settings: `CLAUDE_API_KEY`, `CLAUDE_MODEL`
- OpenAI settings: `OPENAI_API_KEY`, `OPENAI_MODEL`
- File paths for input/output/logs
- Taxonomy and voice/tone document paths
- Window geometry for UI persistence

### Cache Files

**`product_taxonomy.json`**: Shopify taxonomy cache
- Maps category names to taxonomy GIDs
- Reduces redundant API calls
- Format: `{"category_name": "gid://shopify/TaxonomyCategory/..."}`

**`shopify_taxonomy_cache.json`**: Full taxonomy cache
- Cached taxonomy categories from Shopify GitHub
- 30-day cache duration
- Format: `{"cached_at": "ISO-8601", "categories": [...]}`

## AI Integration

### Supported Providers

**Claude (Anthropic)**:
- Models: Sonnet 4.5, Opus 3.5, Sonnet 3.5, Haiku 3.5
- Best for complex reasoning and detailed analysis
- Recommended for high-accuracy taxonomy assignment

**OpenAI (ChatGPT)**:
- Models: GPT-5, GPT-5 Mini, GPT-5 Nano, GPT-4o, GPT-4o Mini
- Good balance of speed and accuracy
- More cost-effective for large batches

### Processing Steps

1. **Taxonomy Assignment + Weight Estimation** (1 API call):
   - Analyzes product title, description, dimensions
   - Assigns Department, Category, Subcategory
   - Estimates shipping weight with confidence level
   - Identifies primary purchase consideration

2. **Description Rewriting** (1 API call):
   - Rewrites product description per voice/tone guidelines
   - Ensures uniqueness (no 7+ word repetitions)
   - Maintains factual accuracy
   - Applies department-specific tone

3. **Collection Description Generation** (as needed):
   - Samples products from collection
   - Generates 100-word SEO description
   - Applies appropriate department tone

## Taxonomy Structure

**Location**: `/Users/moosemarketer/Code/shared-docs/python/PRODUCT_TAXONOMY.md`

**Three-level hierarchy**:
1. **Department** (product_type): Top-level category
2. **Category** (first tag): Primary classification
3. **Subcategory** (second tag): Specific product type

The shared taxonomy document includes:
- Complete category and subcategory structure
- Purchase and fulfillment options per category
- Packaging and shipping guidelines
- Tags format for each subcategory

Example:
- Department: "Pet Supplies"
- Category: "Dogs"
- Subcategory: "Dog Food"

## Voice and Tone Guidelines

**Location**: `docs/VOICE_AND_TONE_GUIDELINES.md` (project-specific)

- Second-person voice ("you")
- Imperative-first phrasing
- Department-specific tone (empathetic for pets, professional for construction, etc.)
- Clear benefit-focused messaging

## Git Workflow Preference

**Commit Strategy:** Proactive (Option 2)

When making changes to this project:
1. ✅ Make the code changes and test them
2. ✅ After completing a significant feature or set of changes, **ASK THE USER**: "Would you like me to commit and push these changes to GitHub?"
3. ⏸️ Wait for user approval before committing
4. ✅ If approved, create a meaningful commit with descriptive message
5. ✅ Include "🤖 Generated with Claude Code" footer

**Repository:** https://github.com/bigpurplefish/garoppos-categorizer

## Testing

### Running Tests
```bash
python -m pytest tests/ -v
python -m pytest tests/ --cov=categorizer_modules --cov-report=term-missing
```

### Test Coverage Goals
- Overall coverage: 90%+
- Core modules: 95%+
- AI integration: 85%+

### Test Structure
- `tests/test_ai_provider.py` - AI provider abstraction
- `tests/test_claude_api.py` - Claude-specific tests
- `tests/test_openai_api.py` - OpenAI-specific tests
- `tests/test_taxonomy_search.py` - Taxonomy search and matching
- `tests/test_utils.py` - Utility functions
- `tests/test_gui.py` - GUI components (as applicable)

## Entry Point

Main execution starts in `categorizer.py`: `build_gui()` function creates the tkinter application and enters the event loop.
