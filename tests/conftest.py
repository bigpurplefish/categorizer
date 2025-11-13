"""
Pytest configuration and shared fixtures for Product Categorizer tests.
"""

import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime


# ============================================================================
# SAMPLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_products():
    """Sample product data for testing."""
    return [
        {
            "title": "Techo-Bloc Aberdeen Slab",
            "product_type": "Landscape and Construction",
            "tags": ["Pavers and Hardscaping", "Slabs"],
            "body_html": "<p>Premium concrete paver slab for patios and walkways</p>",
            "variants": [
                {
                    "sku": "50000",
                    "price": "12.99",
                    "weight": 0,
                    "grams": 0,
                    "option1": "Rock Garden Brown",
                    "metafields": [
                        {
                            "namespace": "custom",
                            "key": "size_info",
                            "value": "20 × 10 × 2 ¼ in (508 × 254 × 57 mm)",
                            "type": "single_line_text_field"
                        }
                    ]
                }
            ],
            "options": [
                {"name": "Color"}
            ]
        },
        {
            "title": "Premium Dog Food 50lb Bag",
            "product_type": "Pet Supplies",
            "tags": ["Dogs", "Food"],
            "body_html": "<p>High-quality 50 lb bag of dog food</p>",
            "variants": [
                {
                    "sku": "DOG-001",
                    "price": "49.99",
                    "weight": 50,
                    "grams": 22680,
                    "metafields": []
                }
            ],
            "options": []
        },
        {
            "title": "Concrete Sealer 5 Gallon",
            "product_type": "Paving & Construction Supplies",
            "tags": ["Paving & Construction Supplies", "Sealers"],
            "body_html": "<p>Professional grade concrete sealer, 5 gallon container</p>",
            "variants": [
                {
                    "sku": "SEAL-5GAL",
                    "price": "89.99",
                    "weight": 0,
                    "grams": 0,
                    "metafields": []
                }
            ],
            "options": []
        }
    ]


@pytest.fixture
def sample_product_no_weight():
    """Sample product without weight information."""
    return {
        "title": "Garden Gnome Statue",
        "product_type": "Home and Gift",
        "tags": ["Home Decor"],
        "body_html": "<p>Decorative garden gnome</p>",
        "variants": [
            {
                "sku": "GNOME-001",
                "price": "24.99",
                "weight": 0,
                "grams": 0,
                "metafields": []
            }
        ],
        "options": []
    }


@pytest.fixture
def sample_taxonomy():
    """Sample taxonomy structure for testing."""
    return {
        "Landscape And Construction": {
            "Aggregates": ["Stone", "Soil", "Mulch", "Sand"],
            "Pavers And Hardscaping": ["Slabs", "Pavers", "Retaining Walls"],
            "Paving Tools & Equipment": ["Hand Tools", "Compactors"],
            "Paving & Construction Supplies": ["Edging", "Adhesives", "Sealers"]
        },
        "Pet Supplies": {
            "Dogs": ["Food", "Toys", "Bedding"],
            "Cats": ["Food", "Toys", "Litter"]
        },
        "Home And Gift": {
            "Home Decor": ["Candles", "Wall Art", "Statues"]
        },
        "Lawn And Garden": {
            "Garden Tools": ["Shovels", "Pruners"],
            "Garden Supplies": ["Fertilizers", "Planters"]
        }
    }


@pytest.fixture
def sample_taxonomy_cache():
    """Sample Shopify taxonomy cache data."""
    return {
        "Pavers and Hardscaping": "gid://shopify/TaxonomyCategory/aa_321",
        "Slabs": "gid://shopify/TaxonomyCategory/aa_321_123",
        "Dogs > Food": "gid://shopify/TaxonomyCategory/pb_101",
        "Home Decor": "gid://shopify/TaxonomyCategory/hg_202"
    }


@pytest.fixture
def sample_ai_taxonomy_response():
    """Sample AI API response with taxonomy assignment."""
    return {
        "department": "Landscape and Construction",
        "category": "Pavers and Hardscaping",
        "subcategory": "Slabs",
        "reasoning": "Concrete paver slab for outdoor hardscaping"
    }


# ============================================================================
# TEMPORARY FILE FIXTURES
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir):
    """Create a temporary config.json file."""
    config_path = temp_dir / "config.json"
    config_data = {
        "AI_PROVIDER": "claude",
        "CLAUDE_API_KEY": "test_claude_key_12345",
        "CLAUDE_MODEL": "claude-sonnet-4-5-20250929",
        "OPENAI_API_KEY": "test_openai_key_67890",
        "OPENAI_MODEL": "gpt-5",
        "INPUT_FILE": str(temp_dir / "input.json"),
        "OUTPUT_FILE": str(temp_dir / "output.json"),
        "LOG_FILE": str(temp_dir / "test.log"),
        "TAXONOMY_DOC_PATH": str(temp_dir / "PRODUCT_TAXONOMY.md"),
        "VOICE_TONE_DOC_PATH": str(temp_dir / "VOICE_AND_TONE_GUIDELINES.md"),
        "WINDOW_GEOMETRY": "800x800"
    }
    with open(config_path, 'w') as f:
        json.dump(config_data, f, indent=4)
    return config_path


@pytest.fixture
def temp_taxonomy_cache_file(temp_dir):
    """Create a temporary product_taxonomy.json file."""
    cache_path = temp_dir / "product_taxonomy.json"
    cache_data = {
        "Pavers and Hardscaping": "gid://shopify/TaxonomyCategory/aa_321",
        "Slabs": "gid://shopify/TaxonomyCategory/aa_321_123"
    }
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f, indent=4)
    return cache_path


@pytest.fixture
def temp_taxonomy_file(temp_dir, sample_taxonomy):
    """Create a temporary PRODUCT_TAXONOMY.md file."""
    taxonomy_path = temp_dir / "PRODUCT_TAXONOMY.md"

    # Generate markdown content from sample taxonomy
    content = "# Product Taxonomy\n\n"
    for idx, (dept, categories) in enumerate(sample_taxonomy.items(), 1):
        content += f"### {idx}. {dept.upper()}\n\n"
        for category, subcategories in categories.items():
            content += f"#### {category}\n\n"
            for sub_idx, subcat in enumerate(subcategories, 1):
                content += f"  {sub_idx}. **{subcat}** - Options: 1, 3, 5\n"
            content += "\n"

    with open(taxonomy_path, 'w') as f:
        f.write(content)

    return taxonomy_path


@pytest.fixture
def temp_products_json(temp_dir, sample_products):
    """Create temporary products.json file."""
    products_path = temp_dir / "products.json"
    with open(products_path, 'w') as f:
        json.dump(sample_products, f, indent=4)
    return products_path


# ============================================================================
# MOCK API FIXTURES
# ============================================================================

@pytest.fixture
def mock_shopify_taxonomy_response():
    """Mock Shopify taxonomy search response."""
    return {
        "data": {
            "taxonomy": {
                "categories": {
                    "edges": [
                        {
                            "node": {
                                "id": "gid://shopify/TaxonomyCategory/aa_321",
                                "fullName": "Home & Garden > Lawn & Garden > Pavers and Hardscaping",
                                "name": "Pavers and Hardscaping"
                            }
                        },
                        {
                            "node": {
                                "id": "gid://shopify/TaxonomyCategory/aa_321_123",
                                "fullName": "Home & Garden > Lawn & Garden > Pavers and Hardscaping > Slabs",
                                "name": "Slabs"
                            }
                        }
                    ],
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": None
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_shopify_taxonomy_empty_response():
    """Mock empty Shopify taxonomy response."""
    return {
        "data": {
            "taxonomy": {
                "categories": {
                    "edges": [],
                    "pageInfo": {
                        "hasNextPage": False,
                        "endCursor": None
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_shopify_taxonomy_error_response():
    """Mock Shopify taxonomy error response."""
    return {
        "errors": [
            {"message": "GraphQL query error"}
        ]
    }


@pytest.fixture
def mock_claude_response(sample_ai_taxonomy_response):
    """Mock Claude API response."""
    class MockResponse:
        def __init__(self):
            self.id = "msg_test123"
            self.model = "claude-sonnet-4-5-20250929"
            self.content = [
                type('obj', (object,), {
                    'text': json.dumps(sample_ai_taxonomy_response)
                })
            ]
            self.usage = type('obj', (object,), {
                'input_tokens': 500,
                'output_tokens': 200
            })
            self.stop_reason = 'end_turn'

    return MockResponse()


@pytest.fixture
def mock_openai_response(sample_ai_taxonomy_response):
    """Mock OpenAI API response."""
    class MockResponse:
        def __init__(self):
            self.id = "chatcmpl-test123"
            self.model = "gpt-5"
            self.choices = [
                type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'content': json.dumps(sample_ai_taxonomy_response)
                    }),
                    'finish_reason': 'stop'
                })
            ]
            self.usage = type('obj', (object,), {
                'prompt_tokens': 500,
                'completion_tokens': 200,
                'total_tokens': 700
            })

    return MockResponse()


# ============================================================================
# PATH FIXTURES
# ============================================================================

@pytest.fixture
def project_root():
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def categorizer_modules_path(project_root):
    """Get categorizer_modules directory path."""
    return project_root / "categorizer_modules"


# ============================================================================
# UTILITY FIXTURES
# ============================================================================

@pytest.fixture
def capture_logs(caplog):
    """Capture log output for testing."""
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.fixture
def mock_status_fn():
    """Mock status function that collects status messages."""
    messages = []

    def status_fn(msg):
        messages.append(msg)

    status_fn.messages = messages
    return status_fn
