"""
Categorizer Modules Package

This package contains the core functionality for the Garoppos Product Categorizer.

Modules:
- ai_provider: Abstract interface for AI providers
- claude_api: Claude (Anthropic) AI implementation
- openai_api: OpenAI AI implementation
- taxonomy_search: Shopify taxonomy search and matching logic
"""

__version__ = "1.0.0"

__all__ = [
    "ai_provider",
    "claude_api",
    "openai_api",
    "taxonomy_search",
]
