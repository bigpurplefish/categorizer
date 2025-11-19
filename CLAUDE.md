# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Python GUI application for enriching product data with AI-powered taxonomy assignment, description rewriting, and metadata generation. It processes JSON output from collector projects and enhances it with:

- **Taxonomy Assignment**: Automatically assigns products to Department, Category, and Subcategory
- **Shipping Weight Estimation**: Calculates estimated shipping weights with confidence levels
- **Description Rewriting**: Rewrites product descriptions according to brand voice and tone guidelines
- **Collection Descriptions**: Generates SEO-optimized descriptions for product collections
- **Purchase Options Analysis**: Identifies primary purchase considerations (price, quality, features, etc.)

**Entry Points:**
- `gui.py` - Graphical user interface (recommended for interactive use)
- `main.py` - Command-line interface (recommended for automation)

**Current Version:** 1.0.0

## Shared Requirements

**IMPORTANT**: This project MUST explicitly follow the requirements documentation located in `/Users/moosemarketer/Code/shared-docs/python`.

**Always reference shared docs - NEVER duplicate them locally.**

### Global Python Standards (Code/shared-docs)

The following requirements apply to all Python projects and should always be referenced:

- **[PROJECT_STRUCTURE_REQUIREMENTS.md](../../../shared-docs/python/PROJECT_STRUCTURE_REQUIREMENTS.md)** - Python project structure conventions
- **[GIT_WORKFLOW.md](../../../shared-docs/python/GIT_WORKFLOW.md)** - Git commit and workflow standards
- **[LOGGING_REQUIREMENTS.md](../../../shared-docs/python/LOGGING_REQUIREMENTS.md)** - Logging patterns and requirements
- **[GUI_DESIGN_REQUIREMENTS.md](../../../shared-docs/python/GUI_DESIGN_REQUIREMENTS.md)** - GUI design standards
- **[GRAPHQL_OUTPUT_REQUIREMENTS.md](../../../shared-docs/python/GRAPHQL_OUTPUT_REQUIREMENTS.md)** - GraphQL output format requirements
- **[COMPLIANCE_CHECKLIST.md](../../../shared-docs/python/COMPLIANCE_CHECKLIST.md)** - Project compliance verification
- **[PACKAGING_WEIGHT_REFERENCE.md](../../../shared-docs/python/PACKAGING_WEIGHT_REFERENCE.md)** - Shipping weight calculation guidelines

### Garoppos Project Documentation (garoppos/shared-docs)

The following docs are shared across all Garoppos projects (categorizer, uploader, etc.):

- **[PRODUCT_TAXONOMY.md](../shared-docs/PRODUCT_TAXONOMY.md)** - Product categorization hierarchy and purchase options
- **[VOICE_AND_TONE_GUIDELINES.md](../shared-docs/VOICE_AND_TONE_GUIDELINES.md)** - Brand voice and tone for product descriptions

These are used by the AI to categorize products and write descriptions.

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

**GUI Mode (Interactive):**
```bash
python3 gui.py
```

**CLI Mode (Automation/Scripting):**
```bash
python3 main.py --input input/products.json --output output/enhanced.json --provider claude
```

### Installing Dependencies

**Production (Core functionality):**
```bash
pip install -r requirements.txt
```

**Production + GUI:**
```bash
pip install -r requirements-gui.txt
```

**Development (All dependencies + testing tools):**
```bash
pip install -r requirements-dev.txt
```

**Required Packages:**
- `requests>=2.28.0` - HTTP library for API calls
- `anthropic>=0.18.0` - Claude AI API client
- `openai>=1.0.0` - OpenAI API client
- `ttkbootstrap>=1.10.0` - GUI framework (requirements-gui.txt only)
- `pytest>=7.4.0` - Testing framework (requirements-dev.txt only)
- `pytest-cov>=4.1.0` - Coverage reporting (requirements-dev.txt only)

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

### Project Structure

```
categorizer/
├── main.py                 # CLI entry point
├── gui.py                  # GUI entry point
├── src/                    # Application source code
│   ├── ai_provider.py      # Abstract AI provider interface
│   ├── claude_api.py       # Claude (Anthropic) implementation
│   ├── openai_api.py       # OpenAI implementation
│   ├── taxonomy_search.py  # Shopify taxonomy search and matching
│   ├── utils.py            # Utility functions (image counting, prompt generation)
│   └── config.py           # Configuration management
├── tests/                  # Comprehensive test suite
├── docs/                   # Project-specific documentation
├── input/                  # Input JSON files
└── output/                 # Enhanced output JSON files
```

### Core Modules

- **`src/ai_provider.py`**: Abstract AI provider interface
- **`src/claude_api.py`**: Claude (Anthropic) implementation
- **`src/openai_api.py`**: OpenAI implementation
- **`src/taxonomy_search.py`**: Shopify taxonomy search and matching
- **`src/utils.py`**: Utility functions (image counting, lifestyle prompts)
- **`src/config.py`**: Configuration management and logging

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
- **Processing options**: `PROCESSING_MODE`, `START_RECORD`, `END_RECORD`
- Window geometry for UI persistence

### Processing Options

The GUI provides flexible processing controls for batch operations:

**Processing Mode:**
- **Skip Processed Records** (default): Resumes interrupted processing by skipping products that already have enhanced data (taxonomy assigned). Ideal for resuming after interruptions or errors.
- **Overwrite All Records**: Re-processes all products in the range, overwriting any existing enhanced data. Use for re-running after configuration changes.

**Record Range:**
- **Start Record** (optional, 1-based): Begin processing from specific record number. Leave blank to start from beginning.
- **End Record** (optional, 1-based): Stop processing at specific record number. Leave blank to process until end.
- Example: Start=10, End=50 processes only records 10 through 50.

**Use Cases:**
1. **Resume interrupted processing**: Set mode to "Skip", leave range blank
2. **Test on sample batch**: Set Start=1, End=10, mode to "Overwrite"
3. **Process specific range**: Set Start and End to target specific products
4. **Re-process everything**: Set mode to "Overwrite", leave range blank

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

### Batch Mode (50% Cost Savings)

Both providers support **Batch API** processing for significant cost savings:

**Benefits:**
- **50% lower costs** compared to standard API pricing
- Same model quality and accuracy
- Ideal for processing large product catalogs (10+ products)
- Asynchronous processing with 24-hour completion window

**How It Works:**
1. All products are submitted as a single batch job
2. API processes requests asynchronously in the background
3. Application polls for completion status (default: every 60 seconds)
4. Results are downloaded and applied when batch completes

**Enabling Batch Mode:**

*GUI Mode:*
1. Open Settings → API Settings
2. Enable "Batch Processing (50% Cost Savings)" checkbox
3. Save settings
4. Process products normally - batch mode happens automatically

*CLI Mode:*
```bash
python3 main.py --input products.json --output enhanced.json --provider openai --batch-mode
```

**Configuration Options:**

In `config.json`:
```json
{
  "USE_BATCH_MODE": true,              // Enable batch processing
  "BATCH_COMPLETION_WINDOW": "24h",    // Max time for batch completion
  "BATCH_POLL_INTERVAL": 60            // Seconds between status checks
}
```

**When to Use Batch Mode:**
- ✅ Processing 10+ products at once
- ✅ Non-urgent processing (can wait up to 24 hours)
- ✅ Want to minimize API costs
- ❌ Need immediate results
- ❌ Processing only 1-5 products (overhead not worth it)

**Cost Comparison:**

| Provider | Standard API | Batch API | Savings |
|----------|-------------|-----------|---------|
| GPT-5 | $1.25/$10 per 1M tokens | $0.625/$5 per 1M tokens | 50% |
| Claude Sonnet 4.5 | $3/$15 per 1M tokens | $1.50/$7.50 per 1M tokens | 50% |

*Example: Processing 100 products with GPT-5*
- Standard: ~$2.50
- Batch: ~$1.25
- **You save: $1.25**

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

**Location**: `../shared-docs/PRODUCT_TAXONOMY.md` (Garoppos shared documentation)

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

**Location**: `../shared-docs/VOICE_AND_TONE_GUIDELINES.md` (Garoppos shared documentation)

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

**Repository:** https://github.com/bigpurplefish/categorizer

## Testing

### Running Tests
```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/test_ai_provider.py -v

# View coverage report
open htmlcov/index.html
```

### Test Coverage Status
- `src/utils.py` - 100% coverage
- `src/ai_provider.py` - 100% coverage
- `src/config.py` - 100% coverage
- `src/taxonomy_search.py` - ~89% coverage
- Overall: ~39% (integration modules like claude_api.py and openai_api.py require extensive mocking)

### Test Structure
- `tests/test_ai_provider.py` - AI provider abstraction (39 tests)
- `tests/test_taxonomy_search.py` - Taxonomy search and matching
- `tests/test_utils.py` - Utility functions (27 tests)
- `tests/test_config.py` - Configuration management
- `tests/conftest.py` - Shared pytest fixtures

### Testing Batch Mode

A dedicated test script is provided for batch mode API testing:

```bash
# Test OpenAI batch mode (GPT-5)
python3 test_batch_mode.py --provider openai --batch-mode

# Test Claude batch mode (Sonnet 4.5)
python3 test_batch_mode.py --provider claude --batch-mode

# Test standard mode for comparison
python3 test_batch_mode.py --provider openai

# Custom number of test products
python3 test_batch_mode.py --provider openai --batch-mode --products 5
```

**What the test does:**
1. Loads sample test products (2 products by default)
2. Submits them for enhancement using configured provider
3. Polls for completion (batch mode only)
4. Displays results and saves to `test_batch_results_[provider].json`
5. Logs detailed information to `test_batch_mode.log`

**Important Notes:**
- ⚠️ Test will consume API credits (50% savings in batch mode)
- Script prompts for confirmation before submitting batch jobs
- Batch mode tests may take several minutes to complete
- Ensure API keys are configured in `config.json` or environment variables

## Entry Points

- **GUI Mode**: `gui.py` - Tkinter GUI with ttkbootstrap theme, thread-safe processing
- **CLI Mode**: `main.py` - Command-line interface with argparse, suitable for automation
