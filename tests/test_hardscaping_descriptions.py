"""
Tests for hardscaping dual description functionality.

Tests that hardscaping products (Pavers and Hardscaping category) generate
two descriptions: one for homeowners and one for professionals.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock


class TestIsHardscapingProduct:
    """Test is_hardscaping_product helper function."""

    def test_pavers_and_hardscaping_is_hardscaping(self):
        """Test that Pavers and Hardscaping category returns True."""
        from src.claude_api import is_hardscaping_product as claude_is_hardscaping
        from src.openai_api import is_hardscaping_product as openai_is_hardscaping

        assert claude_is_hardscaping("Pavers and Hardscaping") is True
        assert openai_is_hardscaping("Pavers and Hardscaping") is True

    def test_other_categories_not_hardscaping(self):
        """Test that other categories return False."""
        from src.claude_api import is_hardscaping_product as claude_is_hardscaping
        from src.openai_api import is_hardscaping_product as openai_is_hardscaping

        non_hardscaping_categories = [
            "Dogs",
            "Cats",
            "Aggregates",
            "Garden Tools",
            "Home Decor",
            "Horses",
            "Deer",
            "Paving Tools & Equipment",
            "Paving & Construction Supplies",
        ]

        for category in non_hardscaping_categories:
            assert claude_is_hardscaping(category) is False, f"Claude: {category} should not be hardscaping"
            assert openai_is_hardscaping(category) is False, f"OpenAI: {category} should not be hardscaping"

    def test_empty_category_not_hardscaping(self):
        """Test that empty category returns False."""
        from src.claude_api import is_hardscaping_product as claude_is_hardscaping
        from src.openai_api import is_hardscaping_product as openai_is_hardscaping

        assert claude_is_hardscaping("") is False
        assert openai_is_hardscaping("") is False

    def test_case_sensitive(self):
        """Test that category matching is case-sensitive."""
        from src.claude_api import is_hardscaping_product as claude_is_hardscaping
        from src.openai_api import is_hardscaping_product as openai_is_hardscaping

        # Exact match should work
        assert claude_is_hardscaping("Pavers and Hardscaping") is True

        # Different case should not match
        assert claude_is_hardscaping("pavers and hardscaping") is False
        assert claude_is_hardscaping("PAVERS AND HARDSCAPING") is False
        assert openai_is_hardscaping("Pavers And Hardscaping") is False


class TestClaudeHardscapingDescriptions:
    """Test hardscaping dual description generation with Claude API."""

    @patch('src.claude_api.anthropic')
    def test_hardscaping_generates_two_descriptions(self, mock_anthropic):
        """Test that hardscaping products generate homeowner and professional descriptions."""
        from src.claude_api import enhance_product_with_claude

        # Mock the Anthropic client
        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        # Mock taxonomy response (returns hardscaping category)
        taxonomy_response = MagicMock()
        taxonomy_response.content = [MagicMock(text=json.dumps({
            "department": "Landscape and Construction",
            "category": "Pavers and Hardscaping",
            "subcategory": "Slabs",
            "reasoning": "This is a patio slab",
            "weight_estimation": {
                "original_weight": 0,
                "product_weight": 50,
                "product_packaging_weight": 5,
                "shipping_packaging_weight": 5,
                "calculated_shipping_weight": 60,
                "final_shipping_weight": 66,
                "confidence": "high",
                "source": "calculated_from_dimensions",
                "reasoning": "Calculated from dimensions"
            },
            "purchase_options": [2, 3],
            "needs_review": False
        }))]
        taxonomy_response.id = "test-id"
        taxonomy_response.model = "claude-sonnet-4-5-20250929"
        taxonomy_response.stop_reason = "end_turn"
        taxonomy_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        # Mock homeowner description response
        homeowner_response = MagicMock()
        homeowner_response.content = [MagicMock(text="<p>Perfect for your backyard patio project.</p>")]
        homeowner_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        # Mock professional description response
        professional_response = MagicMock()
        professional_response.content = [MagicMock(text="<p>Efficient installation for commercial projects.</p>")]
        professional_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        # Set up mock to return different responses for each call
        mock_client.messages.create.side_effect = [
            taxonomy_response,
            homeowner_response,
            professional_response
        ]

        product = {
            "title": "Cambridge Sherwood Slab",
            "descriptionHtml": "<p>Original description</p>",
            "variants": [{"weight": 0}]
        }

        result = enhance_product_with_claude(
            product=product,
            taxonomy_doc="# Taxonomy",
            voice_tone_doc="# Voice",
            api_key="test-key",
            model="claude-sonnet-4-5-20250929"
        )

        # Verify 3 API calls were made (taxonomy + 2 descriptions)
        assert mock_client.messages.create.call_count == 3

        # Verify homeowner description is in descriptionHtml
        assert result["descriptionHtml"] == "<p>Perfect for your backyard patio project.</p>"

        # Verify professional description is in metafield
        professional_metafield = None
        for mf in result.get("metafields", []):
            if mf.get("key") == "professional_description":
                professional_metafield = mf
                break

        assert professional_metafield is not None, "professional_description metafield not found"
        assert professional_metafield["namespace"] == "custom"
        assert professional_metafield["type"] == "rich_text_field"
        # Value should be Shopify rich text JSON format
        value_json = json.loads(professional_metafield["value"])
        assert value_json["type"] == "root"
        assert len(value_json["children"]) > 0
        # First child should be a paragraph with the text
        assert value_json["children"][0]["type"] == "paragraph"
        assert value_json["children"][0]["children"][0]["value"] == "Efficient installation for commercial projects."

    @patch('src.claude_api.anthropic')
    def test_non_hardscaping_generates_single_description(self, mock_anthropic):
        """Test that non-hardscaping products generate only one description."""
        from src.claude_api import enhance_product_with_claude

        mock_client = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client

        # Mock taxonomy response (returns non-hardscaping category)
        taxonomy_response = MagicMock()
        taxonomy_response.content = [MagicMock(text=json.dumps({
            "department": "Pet Supplies",
            "category": "Dogs",
            "subcategory": "Food",
            "reasoning": "Dog food product",
            "weight_estimation": {
                "original_weight": 25,
                "product_weight": 25,
                "product_packaging_weight": 1.25,
                "shipping_packaging_weight": 3,
                "calculated_shipping_weight": 29.25,
                "final_shipping_weight": 32.2,
                "confidence": "high",
                "source": "variant_weight",
                "reasoning": "Used existing weight"
            },
            "purchase_options": [1, 2, 3],
            "needs_review": False
        }))]
        taxonomy_response.id = "test-id"
        taxonomy_response.model = "claude-sonnet-4-5-20250929"
        taxonomy_response.stop_reason = "end_turn"
        taxonomy_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        # Mock single description response
        description_response = MagicMock()
        description_response.content = [MagicMock(text="<p>Quality dog food for your pet.</p>")]
        description_response.id = "test-id"
        description_response.model = "claude-sonnet-4-5-20250929"
        description_response.stop_reason = "end_turn"
        description_response.usage = MagicMock(input_tokens=100, output_tokens=50)

        mock_client.messages.create.side_effect = [taxonomy_response, description_response]

        product = {
            "title": "Premium Dog Food 25lb",
            "descriptionHtml": "<p>Original description</p>",
            "variants": [{"weight": 25}]
        }

        result = enhance_product_with_claude(
            product=product,
            taxonomy_doc="# Taxonomy",
            voice_tone_doc="# Voice",
            api_key="test-key",
            model="claude-sonnet-4-5-20250929"
        )

        # Verify only 2 API calls (taxonomy + 1 description)
        assert mock_client.messages.create.call_count == 2

        # Verify description is in descriptionHtml
        assert result["descriptionHtml"] == "<p>Quality dog food for your pet.</p>"

        # Verify NO professional_description metafield
        professional_metafield = None
        for mf in result.get("metafields", []):
            if mf.get("key") == "professional_description":
                professional_metafield = mf
                break

        assert professional_metafield is None, "professional_description should not exist for non-hardscaping"


class TestOpenAIHardscapingDescriptions:
    """Test hardscaping dual description generation with OpenAI API."""

    @patch('src.openai_api.OpenAI')
    def test_hardscaping_generates_two_descriptions(self, mock_openai_class):
        """Test that hardscaping products generate homeowner and professional descriptions."""
        from src.openai_api import enhance_product_with_openai

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Mock taxonomy response
        taxonomy_response = MagicMock()
        taxonomy_response.id = "test-id"
        taxonomy_response.model = "gpt-5"
        taxonomy_response.choices = [MagicMock(
            message=MagicMock(content=json.dumps({
                "department": "Landscape and Construction",
                "category": "Pavers and Hardscaping",
                "subcategory": "Pavers",
                "reasoning": "Paver product",
                "weight_estimation": {
                    "original_weight": 0,
                    "product_weight": 8,
                    "product_packaging_weight": 0.8,
                    "shipping_packaging_weight": 2,
                    "calculated_shipping_weight": 10.8,
                    "final_shipping_weight": 11.9,
                    "confidence": "high",
                    "source": "estimated",
                    "reasoning": "Estimated"
                },
                "purchase_options": [2, 3],
                "needs_review": False
            })),
            finish_reason="stop"
        )]
        taxonomy_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        # Mock homeowner description
        homeowner_response = MagicMock()
        homeowner_response.id = "test-id"
        homeowner_response.model = "gpt-5"
        homeowner_response.choices = [MagicMock(
            message=MagicMock(content="<p>Create your dream patio with these beautiful pavers.</p>"),
            finish_reason="stop"
        )]
        homeowner_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        # Mock professional description
        professional_response = MagicMock()
        professional_response.id = "test-id"
        professional_response.model = "gpt-5"
        professional_response.choices = [MagicMock(
            message=MagicMock(content="<p>High-efficiency pavers for commercial installations.</p>"),
            finish_reason="stop"
        )]
        professional_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)

        mock_client.chat.completions.create.side_effect = [
            taxonomy_response,
            homeowner_response,
            professional_response
        ]

        product = {
            "title": "Nicolock Colonial Paver",
            "descriptionHtml": "<p>Original</p>",
            "variants": [{"weight": 0}]
        }

        result = enhance_product_with_openai(
            product=product,
            taxonomy_doc="# Taxonomy",
            voice_tone_doc="# Voice",
            shopify_categories=[],
            api_key="test-key",
            model="gpt-5"
        )

        # Verify 3 API calls
        assert mock_client.chat.completions.create.call_count == 3

        # Verify homeowner description
        assert result["descriptionHtml"] == "<p>Create your dream patio with these beautiful pavers.</p>"

        # Verify professional description metafield
        professional_metafield = None
        for mf in result.get("metafields", []):
            if mf.get("key") == "professional_description":
                professional_metafield = mf
                break

        assert professional_metafield is not None
        assert professional_metafield["type"] == "rich_text_field"
        # Value should be Shopify rich text JSON format
        value_json = json.loads(professional_metafield["value"])
        assert value_json["type"] == "root"
        assert len(value_json["children"]) > 0
        assert value_json["children"][0]["type"] == "paragraph"
        assert value_json["children"][0]["children"][0]["value"] == "High-efficiency pavers for commercial installations."


class TestHardscapingDescriptionPrompts:
    """Test that hardscaping description prompts include correct audience targeting."""

    def test_homeowner_prompt_includes_audience(self):
        """Test homeowner description prompt includes DIY/residential context."""
        from src.claude_api import build_description_prompt

        prompt = build_description_prompt(
            title="Test Paver",
            body_html="<p>Description</p>",
            department="Landscape and Construction",
            voice_tone_doc="# Guidelines",
            audience_name="Homeowners (DIY enthusiasts and property owners doing residential projects like patios, walkways, and backyard improvements)"
        )

        assert "Homeowners" in prompt
        assert "DIY" in prompt
        assert "residential projects" in prompt
        assert "patios" in prompt

    def test_professional_prompt_includes_audience(self):
        """Test professional description prompt includes contractor context."""
        from src.claude_api import build_description_prompt

        prompt = build_description_prompt(
            title="Test Paver",
            body_html="<p>Description</p>",
            department="Landscape and Construction",
            voice_tone_doc="# Guidelines",
            audience_name="Professional contractors and landscapers (commercial installers focused on efficiency, durability, specifications, and job site requirements)"
        )

        assert "Professional contractors" in prompt
        assert "landscapers" in prompt
        assert "efficiency" in prompt
        assert "durability" in prompt
        assert "specifications" in prompt

    def test_openai_homeowner_prompt_includes_audience(self):
        """Test OpenAI homeowner description prompt includes DIY/residential context."""
        from src.openai_api import _build_description_prompt

        prompt = _build_description_prompt(
            title="Test Paver",
            body_html="<p>Description</p>",
            department="Landscape and Construction",
            voice_tone_doc="# Guidelines",
            audience_name="Homeowners (DIY enthusiasts and property owners doing residential projects like patios, walkways, and backyard improvements)"
        )

        assert "Homeowners" in prompt
        assert "DIY" in prompt

    def test_openai_professional_prompt_includes_audience(self):
        """Test OpenAI professional description prompt includes contractor context."""
        from src.openai_api import _build_description_prompt

        prompt = _build_description_prompt(
            title="Test Paver",
            body_html="<p>Description</p>",
            department="Landscape and Construction",
            voice_tone_doc="# Guidelines",
            audience_name="Professional contractors and landscapers (commercial installers focused on efficiency, durability, specifications, and job site requirements)"
        )

        assert "Professional contractors" in prompt
        assert "landscapers" in prompt


class TestHardscapingMetafieldStructure:
    """Test professional_description metafield structure."""

    def test_metafield_uses_correct_namespace(self):
        """Test that professional_description uses 'custom' namespace."""
        from src.product_utils import add_metafield_if_not_exists

        product = {"metafields": []}

        result = add_metafield_if_not_exists(
            product, "custom", "professional_description",
            "<p>Test</p>", "multi_line_text_field"
        )

        assert result is True
        assert product["metafields"][0]["namespace"] == "custom"

    def test_metafield_uses_correct_type(self):
        """Test that professional_description uses rich_text_field type."""
        from src.product_utils import add_metafield_if_not_exists

        product = {"metafields": []}

        add_metafield_if_not_exists(
            product, "custom", "professional_description",
            "<p>Test</p>", "rich_text_field"
        )

        assert product["metafields"][0]["type"] == "rich_text_field"

    def test_metafield_not_duplicated(self):
        """Test that professional_description is not added if it exists."""
        from src.product_utils import add_metafield_if_not_exists

        product = {
            "metafields": [{
                "namespace": "custom",
                "key": "professional_description",
                "value": "<p>Existing</p>",
                "type": "rich_text_field"
            }]
        }

        result = add_metafield_if_not_exists(
            product, "custom", "professional_description",
            "<p>New</p>", "rich_text_field"
        )

        assert result is False
        assert len(product["metafields"]) == 1
        assert product["metafields"][0]["value"] == "<p>Existing</p>"


class TestHTMLToShopifyRichText:
    """Test HTML to Shopify rich text JSON conversion."""

    def test_simple_paragraph(self):
        """Test converting a simple paragraph."""
        from src.product_utils import html_to_shopify_rich_text

        html = "<p>Simple text content.</p>"
        result = json.loads(html_to_shopify_rich_text(html))

        assert result["type"] == "root"
        assert len(result["children"]) == 1
        assert result["children"][0]["type"] == "paragraph"
        assert result["children"][0]["children"][0]["value"] == "Simple text content."

    def test_heading_levels(self):
        """Test converting headings h1-h6."""
        from src.product_utils import html_to_shopify_rich_text

        for level in range(1, 7):
            html = f"<h{level}>Heading {level}</h{level}>"
            result = json.loads(html_to_shopify_rich_text(html))

            assert result["children"][0]["type"] == "heading"
            assert result["children"][0]["level"] == level
            assert result["children"][0]["children"][0]["value"] == f"Heading {level}"

    def test_bold_text(self):
        """Test converting bold text."""
        from src.product_utils import html_to_shopify_rich_text

        html = "<p><strong>Bold text</strong> and normal.</p>"
        result = json.loads(html_to_shopify_rich_text(html))

        paragraph = result["children"][0]
        assert paragraph["children"][0]["value"] == "Bold text"
        assert paragraph["children"][0].get("bold") is True
        assert paragraph["children"][1]["value"] == "and normal."
        assert paragraph["children"][1].get("bold") is None

    def test_italic_text(self):
        """Test converting italic text."""
        from src.product_utils import html_to_shopify_rich_text

        html = "<p><em>Italic text</em> and normal.</p>"
        result = json.loads(html_to_shopify_rich_text(html))

        paragraph = result["children"][0]
        assert paragraph["children"][0]["value"] == "Italic text"
        assert paragraph["children"][0].get("italic") is True

    def test_unordered_list(self):
        """Test converting unordered list."""
        from src.product_utils import html_to_shopify_rich_text

        html = "<ul><li>Item one</li><li>Item two</li></ul>"
        result = json.loads(html_to_shopify_rich_text(html))

        list_node = result["children"][0]
        assert list_node["type"] == "list"
        assert list_node["listType"] == "unordered"
        assert len(list_node["children"]) == 2
        assert list_node["children"][0]["type"] == "list-item"
        assert list_node["children"][0]["children"][0]["value"] == "Item one"

    def test_ordered_list(self):
        """Test converting ordered list."""
        from src.product_utils import html_to_shopify_rich_text

        html = "<ol><li>First</li><li>Second</li></ol>"
        result = json.loads(html_to_shopify_rich_text(html))

        list_node = result["children"][0]
        assert list_node["type"] == "list"
        assert list_node["listType"] == "ordered"

    def test_link(self):
        """Test converting links."""
        from src.product_utils import html_to_shopify_rich_text

        html = '<p><a href="https://example.com">Click here</a></p>'
        result = json.loads(html_to_shopify_rich_text(html))

        paragraph = result["children"][0]
        link = paragraph["children"][0]
        assert link["type"] == "link"
        assert link["url"] == "https://example.com"
        assert link["children"][0]["value"] == "Click here"

    def test_empty_html(self):
        """Test empty HTML returns empty root."""
        from src.product_utils import html_to_shopify_rich_text

        result = json.loads(html_to_shopify_rich_text(""))
        assert result["type"] == "root"
        assert result["children"] == []

    def test_complex_structure(self):
        """Test converting complex HTML with multiple elements."""
        from src.product_utils import html_to_shopify_rich_text

        html = """<p>Intro paragraph.</p>
        <h3>Features</h3>
        <ul>
            <li><strong>Feature one:</strong> Description.</li>
            <li><strong>Feature two:</strong> More info.</li>
        </ul>"""
        result = json.loads(html_to_shopify_rich_text(html))

        assert result["type"] == "root"
        assert len(result["children"]) == 3
        assert result["children"][0]["type"] == "paragraph"
        assert result["children"][1]["type"] == "heading"
        assert result["children"][1]["level"] == 3
        assert result["children"][2]["type"] == "list"
