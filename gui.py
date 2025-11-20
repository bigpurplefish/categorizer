#!/usr/bin/env python3
"""
Product Categorizer - GUI Entry Point

Version 1.0.0
Graphical user interface for AI-powered product categorization, weight estimation,
and description enhancement.

This application takes product data from collectors (enhanced with images and data)
and outputs categorized, AI-enhanced products ready for upload to Shopify.
"""

import os
import sys
import json
import logging
import threading
import queue
from tkinter import filedialog, messagebox
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from ttkbootstrap.tooltip import ToolTip

# Import src modules
try:
    from src.config import (
        load_config,
        save_config,
        setup_logging,
        log_and_status,
        SCRIPT_VERSION
    )
    from src.ai_provider import batch_enhance_products
except ImportError as e:
    print(f"Error importing src: {e}")
    print("Make sure the src package is in the same directory as this script.")
    sys.exit(1)


# AI Provider options
AI_PROVIDERS = [
    ("Claude (Anthropic)", "claude"),
    ("ChatGPT (OpenAI)", "openai")
]

# Claude model options
CLAUDE_MODELS = [
    ("Claude Sonnet 4.5 (Recommended)", "claude-sonnet-4-5-20250929"),
    ("Claude Opus 3.5", "claude-opus-3-5-20241022"),
    ("Claude Sonnet 3.5", "claude-3-5-sonnet-20241022"),
    ("Claude Haiku 3.5", "claude-3-5-haiku-20241022")
]

# OpenAI model options
OPENAI_MODELS = [
    ("GPT-5 (Latest, Recommended)", "gpt-5"),
    ("GPT-5 Mini", "gpt-5-mini"),
    ("GPT-5 Nano", "gpt-5-nano"),
    ("GPT-4o", "gpt-4o"),
    ("GPT-4o Mini", "gpt-4o-mini"),
    ("GPT-4 Turbo", "gpt-4-turbo"),
    ("GPT-4", "gpt-4")
]


def get_provider_display_from_id(provider_id):
    """Convert provider ID to display name."""
    for display, pid in AI_PROVIDERS:
        if pid == provider_id:
            return display
    return "Claude (Anthropic)"  # fallback to default


def get_provider_id_from_display(display_name):
    """Convert display name to provider ID."""
    for display, provider_id in AI_PROVIDERS:
        if display == display_name:
            return provider_id
    return "claude"  # fallback to default


def get_model_id_from_display(display_name, provider="claude"):
    """Convert display name to model ID."""
    models = CLAUDE_MODELS if provider == "claude" else OPENAI_MODELS
    for display, model_id in models:
        if display == display_name:
            return model_id
    # Return default based on provider
    return "claude-sonnet-4-5-20250929" if provider == "claude" else "gpt-5"


def get_display_from_model_id(model_id, provider="claude"):
    """Convert model ID to display name."""
    models = CLAUDE_MODELS if provider == "claude" else OPENAI_MODELS
    for display, mid in models:
        if mid == model_id:
            return display
    # Return default based on provider
    return "Claude Sonnet 4.5 (Recommended)" if provider == "claude" else "GPT-5 (Latest, Recommended)"


def open_api_settings(cfg, parent):
    """Open the API settings dialog."""
    settings_window = tb.Toplevel(parent)
    settings_window.title("API Settings")
    settings_window.geometry("700x450")
    settings_window.transient(parent)
    settings_window.grab_set()

    # Main frame with padding
    main_frame = tb.Frame(settings_window, padding=20)
    main_frame.pack(fill="both", expand=True)

    # Title
    tb.Label(
        main_frame,
        text="API Settings",
        font=("Arial", 14, "bold")
    ).grid(row=0, column=0, columnspan=2, pady=(0, 20))

    # AI Settings Section
    tb.Label(
        main_frame,
        text="AI API Keys",
        font=("Arial", 11, "bold")
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 5))

    tb.Separator(main_frame, orient="horizontal").grid(
        row=2, column=0, columnspan=2, sticky="ew", pady=(0, 10)
    )

    # Claude API Key
    tb.Label(main_frame, text="Claude API Key:").grid(
        row=3, column=0, sticky="w", padx=5, pady=5
    )
    claude_api_key_var = tb.StringVar(value=cfg.get("CLAUDE_API_KEY", ""))
    claude_api_key_entry = tb.Entry(main_frame, textvariable=claude_api_key_var, width=50, show="*")
    claude_api_key_entry.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(
        claude_api_key_entry,
        text="Your Anthropic Claude API key\n(Get one at: console.anthropic.com)"
    )

    # OpenAI API Key
    tb.Label(main_frame, text="OpenAI API Key:").grid(
        row=4, column=0, sticky="w", padx=5, pady=5
    )
    openai_api_key_var = tb.StringVar(value=cfg.get("OPENAI_API_KEY", ""))
    openai_api_key_entry = tb.Entry(main_frame, textvariable=openai_api_key_var, width=50, show="*")
    openai_api_key_entry.grid(row=4, column=1, sticky="ew", padx=5, pady=5)
    ToolTip(
        openai_api_key_entry,
        text="Your OpenAI API key\n(Get one at: platform.openai.com)"
    )

    # Batch Mode Settings Section
    tb.Label(
        main_frame,
        text="Batch Processing (50% Cost Savings)",
        font=("Arial", 11, "bold")
    ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(20, 5))

    tb.Separator(main_frame, orient="horizontal").grid(
        row=6, column=0, columnspan=2, sticky="ew", pady=(0, 10)
    )

    # Enable Batch Mode checkbox
    batch_mode_var = tb.BooleanVar(value=cfg.get("USE_BATCH_MODE", False))
    batch_mode_check = tb.Checkbutton(
        main_frame,
        text="Enable Batch Mode",
        variable=batch_mode_var,
        bootstyle="success-round-toggle"
    )
    batch_mode_check.grid(row=7, column=0, columnspan=2, sticky="w", padx=5, pady=5)
    ToolTip(
        batch_mode_check,
        text="Enable batch processing for 50% cost savings\n"
             "• 50% cheaper than standard API\n"
             "• Same model quality and accuracy\n"
             "• Best for large batches (10+ products)\n"
             "\n"
             "⚠️ Processing happens on API provider's schedule\n"
             "• Jobs submitted immediately, processed asynchronously\n"
             "• Completes within 24 hours (often faster)\n"
             "• Not suitable for urgent/immediate results"
    )

    # Info label about AI
    info_frame = tb.Frame(main_frame)
    info_frame.grid(row=8, column=0, columnspan=2, sticky="ew", pady=10)

    info_label = tb.Label(
        info_frame,
        text="Configure AI provider and model selection in the main window.\n"
             "API keys are required for AI enhancement features.\n"
             "Batch mode saves 50% on API costs but processes asynchronously.",
        font=("Arial", 9),
        foreground="#5BC0DE",
        justify="left"
    )
    info_label.pack(anchor="w", padx=5)

    # Configure column weights
    main_frame.columnconfigure(1, weight=1)

    # Button frame
    button_frame = tb.Frame(settings_window)
    button_frame.pack(side="bottom", fill="x", padx=20, pady=20)

    def save_settings():
        """Save settings and close dialog."""
        cfg["CLAUDE_API_KEY"] = claude_api_key_var.get().strip()
        cfg["OPENAI_API_KEY"] = openai_api_key_var.get().strip()
        cfg["USE_BATCH_MODE"] = batch_mode_var.get()

        save_config(cfg)

        batch_status = "enabled (50% cost savings)" if cfg["USE_BATCH_MODE"] else "disabled"
        messagebox.showinfo(
            "Settings Saved",
            f"API settings have been saved successfully.\n\nBatch mode: {batch_status}"
        )
        settings_window.destroy()

    def cancel_settings():
        """Close dialog without saving."""
        settings_window.destroy()

    # Save and Cancel buttons
    tb.Button(
        button_frame,
        text="Save",
        command=save_settings,
        bootstyle="success",
        width=15
    ).pack(side="right", padx=5)

    tb.Button(
        button_frame,
        text="Cancel",
        command=cancel_settings,
        bootstyle="secondary",
        width=15
    ).pack(side="right")


def process_products_worker(cfg, status_queue, button_control_queue, app):
    """
    Worker thread function to process products with AI enhancement.
    Uses queue-based communication for thread-safe GUI updates.

    Args:
        cfg: Configuration dictionary
        status_queue: Queue for status messages
        button_control_queue: Queue for button state control
        app: Main application window
    """
    def status(msg):
        """Thread-safe status update via queue."""
        try:
            status_queue.put(msg)
        except Exception as e:
            logging.error(f"Failed to queue status message: {e}")

    try:
        # Get file paths
        input_file = cfg.get("INPUT_FILE", "").strip()
        output_file = cfg.get("OUTPUT_FILE", "").strip()
        log_file = cfg.get("LOG_FILE", "").strip()

        # Validate inputs
        if not input_file or not os.path.exists(input_file):
            app.after(0, lambda: messagebox.showerror(
                "Input Error",
                f"Input file not found:\n{input_file}"
            ))
            return

        if not output_file:
            app.after(0, lambda: messagebox.showerror(
                "Output Error",
                "Output file path not specified."
            ))
            return

        if not log_file:
            app.after(0, lambda: messagebox.showerror(
                "Log Error",
                "Log file path not specified."
            ))
            return

        # Setup logging
        setup_logging(log_file)
        logging.info("=" * 80)
        logging.info(f"STARTING PRODUCT CATEGORIZATION")
        logging.info(f"Version: {SCRIPT_VERSION}")
        logging.info(f"Input file: {input_file}")
        logging.info(f"Output file: {output_file}")
        logging.info("=" * 80)

        log_and_status(status, "=" * 80)
        log_and_status(status, "GAROPPOS PRODUCT CATEGORIZER")
        log_and_status(status, "=" * 80)
        log_and_status(status, f"Version: {SCRIPT_VERSION}")
        log_and_status(status, "")

        # Load input products
        log_and_status(status, f"Loading products from: {input_file}")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Handle both formats:
            # 1. Direct array: [{product1}, {product2}, ...]
            # 2. Object with products key: {"products": [{product1}, {product2}, ...]}
            if isinstance(data, list):
                all_products = data
            elif isinstance(data, dict) and "products" in data:
                all_products = data["products"]
                if not isinstance(all_products, list):
                    raise ValueError("'products' field must be an array")
            else:
                raise ValueError(
                    "Input file must contain either:\n"
                    "1. A JSON array of products: [{...}, {...}]\n"
                    "2. A JSON object with 'products' key: {\"products\": [{...}, {...}]}"
                )

            if len(all_products) == 0:
                raise ValueError("Input file contains no products")

            log_and_status(status, f"Loaded {len(all_products)} products from input file")
            log_and_status(status, "")

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from input file: {e}"
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("JSON Error", error_msg))
            return
        except Exception as e:
            error_msg = f"Failed to load input file: {e}"
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Load Error", error_msg))
            return

        # Get processing parameters
        processing_mode = cfg.get("PROCESSING_MODE", "skip")
        start_record_str = cfg.get("START_RECORD", "").strip()
        end_record_str = cfg.get("END_RECORD", "").strip()

        # Parse start/end record numbers
        try:
            start_record = int(start_record_str) if start_record_str else 0
        except ValueError:
            start_record = 0

        try:
            end_record = int(end_record_str) if end_record_str else 0
        except ValueError:
            end_record = 0

        # Convert to 0-based indices
        start_idx = 0
        end_idx = None

        if start_record > 0:
            start_idx = start_record - 1  # Convert to 0-based index

        if end_record > 0:
            end_idx = end_record  # Keep as-is for slicing

        # Slice products by record range
        products_to_process = all_products[start_idx:end_idx]

        log_and_status(status, f"Processing mode: {processing_mode.upper()}")
        if start_record > 0 or end_record > 0:
            log_and_status(status, f"Record range: {start_record or 1} to {end_record or len(all_products)}")
        log_and_status(status, f"Products to process: {len(products_to_process)}")
        log_and_status(status, "")

        # Handle skip mode - load existing output
        existing_products = {}
        if processing_mode == "skip" and os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                    if isinstance(existing_data, list):
                        # Index by title for fast lookup
                        for product in existing_data:
                            title = product.get("title", "")
                            if title:
                                existing_products[title] = product
                        log_and_status(status, f"Found {len(existing_products)} existing products in output file")
                        log_and_status(status, "")
            except Exception as e:
                log_and_status(status, f"Warning: Could not load existing output file: {e}", "warning")
                log_and_status(status, "")

        # Filter products for processing
        products = []
        skipped_count = 0

        for i, product in enumerate(products_to_process):
            actual_record_num = start_idx + i + 1
            title = product.get("title", "")

            # Check if already processed (skip mode)
            if processing_mode == "skip" and title in existing_products:
                existing = existing_products[title]
                # Check if product has been enhanced (has taxonomy)
                if existing.get("product_type"):
                    log_and_status(status, f"⏭ Skipping record #{actual_record_num}: {title} (already processed)")
                    skipped_count += 1
                    continue

            products.append(product)

        if skipped_count > 0:
            log_and_status(status, "")
            log_and_status(status, f"Skipped {skipped_count} already-processed products")
            log_and_status(status, "")

        if len(products) == 0:
            log_and_status(status, "No products to process!")
            log_and_status(status, "All products in range have already been processed.")
            return

        log_and_status(status, f"Processing {len(products)} products...")
        log_and_status(status, "")

        # Get taxonomy and voice/tone document paths
        taxonomy_path = cfg.get("TAXONOMY_DOC_PATH", "").strip()
        voice_tone_path = cfg.get("VOICE_TONE_DOC_PATH", "").strip()

        if not taxonomy_path or not os.path.exists(taxonomy_path):
            error_msg = f"Taxonomy document not found: {taxonomy_path}"
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Config Error", error_msg))
            return

        if not voice_tone_path or not os.path.exists(voice_tone_path):
            error_msg = f"Voice/tone guidelines document not found: {voice_tone_path}"
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Config Error", error_msg))
            return

        # Process products with AI enhancement
        log_and_status(status, "Starting AI enhancement...")
        log_and_status(status, "")

        try:
            enhanced_products = batch_enhance_products(
                products,
                cfg,
                status,
                taxonomy_path,
                voice_tone_path
            )

            log_and_status(status, "")
            log_and_status(status, f"Enhanced {len(enhanced_products)} products")

        except Exception as e:
            error_msg = f"AI enhancement failed: {e}"
            log_and_status(status, "", "error")
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Enhancement Error", error_msg))
            return

        # Merge with existing products if in skip mode
        if processing_mode == "skip" and existing_products:
            log_and_status(status, "")
            log_and_status(status, "Merging with existing products...")

            # Update existing products with newly enhanced ones
            for product in enhanced_products:
                title = product.get("title", "")
                if title:
                    existing_products[title] = product

            # Convert back to list
            all_enhanced = list(existing_products.values())
            log_and_status(status, f"Total products in output: {len(all_enhanced)}")
        else:
            all_enhanced = enhanced_products

        # Save enhanced products to output file
        log_and_status(status, "")
        log_and_status(status, f"Saving enhanced products to: {output_file}")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(all_enhanced, f, indent=2, ensure_ascii=False)

            log_and_status(status, f"Successfully saved {len(all_enhanced)} products")

        except Exception as e:
            error_msg = f"Failed to save output file: {e}"
            log_and_status(status, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Save Error", error_msg))
            return

        # Success!
        log_and_status(status, "")
        log_and_status(status, "=" * 80)
        log_and_status(status, "CATEGORIZATION COMPLETE")
        log_and_status(status, "=" * 80)
        log_and_status(status, f"✅ Enhanced: {len(enhanced_products)} products")
        if skipped_count > 0:
            log_and_status(status, f"⏭ Skipped: {skipped_count} already-processed products")
        log_and_status(status, f"📁 Total in output file: {len(all_enhanced)} products")
        log_and_status(status, "=" * 80)

        logging.info("=" * 80)
        logging.info("CATEGORIZATION COMPLETE")
        logging.info(f"Enhanced products saved to: {output_file}")
        logging.info("=" * 80)

        app.after(0, lambda: messagebox.showinfo(
            "Success",
            f"Successfully categorized and enhanced {len(enhanced_products)} products!\n\n"
            f"Output saved to:\n{output_file}"
        ))

    except Exception as e:
        error_msg = f"Unexpected error during processing: {e}"
        logging.exception(error_msg)
        app.after(0, lambda: messagebox.showerror("Error", error_msg))
    finally:
        # Always re-enable buttons
        button_control_queue.put("enable_buttons")


def build_gui():
    """Build the main GUI application."""
    global cfg
    cfg = load_config()

    app = tb.Window(themename="darkly")
    app.title("Garoppos Product Categorizer")
    app.geometry(cfg.get("WINDOW_GEOMETRY", "800x800"))

    # Create menu bar
    menu_bar = tb.Menu(app)
    app.config(menu=menu_bar)

    # Add Settings menu
    settings_menu = tb.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="Settings", menu=settings_menu)
    settings_menu.add_command(label="API Settings", command=lambda: open_api_settings(cfg, app))

    # Create toolbar
    toolbar = tb.Frame(app)
    toolbar.pack(side="top", fill="x", padx=5, pady=5)

    # Add settings button with gear icon
    settings_btn = tb.Button(
        toolbar,
        text="⚙️ Settings",
        command=lambda: open_api_settings(cfg, app),
        bootstyle="secondary-outline"
    )
    settings_btn.pack(side="left", padx=5)

    # Main container
    container = tb.Frame(app)
    container.pack(fill="both", expand=True, padx=10, pady=10)
    container.columnconfigure(1, weight=1)

    # Title
    tb.Label(container, text="Garoppos Product Categorizer", font=("Arial", 14, "bold")).grid(
        row=0, column=0, columnspan=3, pady=10
    )

    # Current row tracker
    row = 1

    # AI Provider Selection
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="AI Provider", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Select the AI provider to use for categorization and enhancement.\n\n"
                           "Claude: Anthropic's Claude models\n"
                           "ChatGPT: OpenAI's GPT models", bootstyle="info")

    provider_var = tb.StringVar(value=get_provider_display_from_id(cfg.get("AI_PROVIDER", "claude")))
    provider_combo = tb.Combobox(
        container,
        textvariable=provider_var,
        values=[display for display, _ in AI_PROVIDERS],
        state="readonly",
        width=48
    )
    provider_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)

    def on_provider_change(*args):
        """Update model dropdown when provider changes."""
        provider_id = get_provider_id_from_display(provider_var.get())
        cfg["AI_PROVIDER"] = provider_id
        save_config(cfg)

        # Update model dropdown options
        if provider_id == "claude":
            model_combo['values'] = [display for display, _ in CLAUDE_MODELS]
            saved_model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
            model_var.set(get_display_from_model_id(saved_model, "claude"))
        else:
            model_combo['values'] = [display for display, _ in OPENAI_MODELS]
            saved_model = cfg.get("OPENAI_MODEL", "gpt-5")
            model_var.set(get_display_from_model_id(saved_model, "openai"))

    provider_var.trace_add("write", on_provider_change)

    row += 1

    # AI Model Selection
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="AI Model", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Select the AI model to use.\n\n"
                           "Newer models are generally more accurate.\n"
                           "Recommended options are marked.", bootstyle="info")

    current_provider = get_provider_id_from_display(provider_var.get())
    if current_provider == "claude":
        saved_model = cfg.get("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
        model_values = [display for display, _ in CLAUDE_MODELS]
        model_display = get_display_from_model_id(saved_model, "claude")
    else:
        saved_model = cfg.get("OPENAI_MODEL", "gpt-5")
        model_values = [display for display, _ in OPENAI_MODELS]
        model_display = get_display_from_model_id(saved_model, "openai")

    model_var = tb.StringVar(value=model_display)
    model_combo = tb.Combobox(
        container,
        textvariable=model_var,
        values=model_values,
        state="readonly",
        width=48
    )
    model_combo.grid(row=row, column=1, sticky="ew", padx=5, pady=5)

    def on_model_change(*args):
        """Save model selection to config."""
        provider_id = get_provider_id_from_display(provider_var.get())
        model_id = get_model_id_from_display(model_var.get(), provider_id)

        if provider_id == "claude":
            cfg["CLAUDE_MODEL"] = model_id
        else:
            cfg["OPENAI_MODEL"] = model_id

        save_config(cfg)

    model_var.trace_add("write", on_model_change)

    row += 1

    # Input File field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Input File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Select the JSON file containing product data from collectors.\n\n"
                           "This should be the output from the collector scripts with "
                           "enhanced images and metadata.", bootstyle="info")

    input_var = tb.StringVar(value=cfg.get("INPUT_FILE", ""))
    tb.Entry(container, textvariable=input_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    def browse_input():
        filename = filedialog.askopenfilename(
            title="Select Input File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            input_var.set(filename)

    tb.Button(container, text="Browse", command=browse_input, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )

    def on_input_change(*args):
        cfg["INPUT_FILE"] = input_var.get()
        save_config(cfg)

    input_var.trace_add("write", on_input_change)

    row += 1

    # Output File field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Output File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Choose where to save the enhanced product data.\n\n"
                           "This file will contain products with AI-assigned taxonomy, "
                           "weight estimates, and rewritten descriptions.", bootstyle="info")

    output_var = tb.StringVar(value=cfg.get("OUTPUT_FILE", ""))
    tb.Entry(container, textvariable=output_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    def browse_output():
        filename = filedialog.asksaveasfilename(
            title="Select Output File",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filename:
            output_var.set(filename)

    tb.Button(container, text="Browse", command=browse_output, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )

    def on_output_change(*args):
        cfg["OUTPUT_FILE"] = output_var.get()
        save_config(cfg)

    output_var.trace_add("write", on_output_change)

    row += 1

    # Log File field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Log File", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Choose where to save detailed processing logs.\n\n"
                           "Logs help track what happened during processing and "
                           "troubleshoot issues.", bootstyle="info")

    log_file_var = tb.StringVar(value=cfg.get("LOG_FILE", ""))
    tb.Entry(container, textvariable=log_file_var, width=50).grid(
        row=row, column=1, sticky="ew", padx=5, pady=5
    )

    def browse_log_file():
        filename = filedialog.asksaveasfilename(
            title="Select Log File",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            log_file_var.set(filename)

    tb.Button(container, text="Browse", command=browse_log_file, bootstyle="info-outline").grid(
        row=row, column=2, padx=5, pady=5
    )

    def on_log_change(*args):
        cfg["LOG_FILE"] = log_file_var.get()
        save_config(cfg)

    log_file_var.trace_add("write", on_log_change)

    row += 1

    # Processing Mode field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Processing Mode", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Choose how to handle records that have already been processed.\n\n"
                           "Skip: Skip records that already have processed data.\n"
                           "Overwrite: Re-process all records, overwriting existing data.\n\n"
                           "Tip: Use 'Skip' to resume interrupted processing.", bootstyle="info")

    # Radio buttons for processing mode
    mode_frame = tb.Frame(container)
    mode_frame.grid(row=row, column=1, columnspan=2, sticky="w", padx=5, pady=5)

    processing_mode_var = tb.StringVar(value=cfg.get("PROCESSING_MODE", "skip"))

    skip_radio = tb.Radiobutton(
        mode_frame,
        text="Skip Processed Records",
        variable=processing_mode_var,
        value="skip",
        bootstyle="primary"
    )
    skip_radio.pack(side="left", padx=(0, 20))

    overwrite_radio = tb.Radiobutton(
        mode_frame,
        text="Overwrite All Records",
        variable=processing_mode_var,
        value="overwrite",
        bootstyle="warning"
    )
    overwrite_radio.pack(side="left")

    def on_mode_change(*args):
        cfg["PROCESSING_MODE"] = processing_mode_var.get()
        save_config(cfg)

    processing_mode_var.trace_add("write", on_mode_change)

    row += 1

    # Start Record field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="Start Record", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Specify the first record to process (1-based index).\n\n"
                           "Leave blank to start from the beginning.\n"
                           "Example: Enter '10' to start from the 10th record.\n\n"
                           "Tip: Blank = process from start.", bootstyle="info")

    start_record_var = tb.StringVar(value=cfg.get("START_RECORD", ""))
    start_spinbox = tb.Spinbox(
        container,
        textvariable=start_record_var,
        from_=0,
        to=999999,
        increment=1,
        width=10
    )
    start_spinbox.grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def on_start_change(*args):
        try:
            val = start_record_var.get().strip()
            if val:
                int(val)  # Validate it's a valid integer
            cfg["START_RECORD"] = val
            save_config(cfg)
        except (ValueError, Exception):
            cfg["START_RECORD"] = ""
            save_config(cfg)

    start_record_var.trace_add("write", on_start_change)

    row += 1

    # End Record field
    label_frame = tb.Frame(container)
    label_frame.grid(row=row, column=0, sticky="w", padx=5, pady=5)

    tb.Label(label_frame, text="End Record", anchor="w").pack(side="left")
    help_icon = tb.Label(label_frame, text=" ⓘ ", font=("Arial", 9),
                         foreground="#5BC0DE", cursor="hand2")
    help_icon.pack(side="left")
    tb.Label(label_frame, text=":", anchor="w").pack(side="left")

    ToolTip(help_icon, text="Specify the last record to process (1-based index).\n\n"
                           "Leave blank to process until the end.\n"
                           "Example: Enter '50' to stop processing after the 50th record.\n\n"
                           "Tip: Blank = process to end.", bootstyle="info")

    end_record_var = tb.StringVar(value=cfg.get("END_RECORD", ""))
    end_spinbox = tb.Spinbox(
        container,
        textvariable=end_record_var,
        from_=0,
        to=999999,
        increment=1,
        width=10
    )
    end_spinbox.grid(row=row, column=1, sticky="w", padx=5, pady=5)

    def on_end_change(*args):
        try:
            val = end_record_var.get().strip()
            if val:
                int(val)  # Validate it's a valid integer
            cfg["END_RECORD"] = val
            save_config(cfg)
        except (ValueError, Exception):
            cfg["END_RECORD"] = ""
            save_config(cfg)

    end_record_var.trace_add("write", on_end_change)

    row += 1

    # Separator
    tb.Separator(container, orient="horizontal").grid(
        row=row, column=0, columnspan=3, sticky="ew", pady=15
    )

    row += 1

    # Progress bar
    progress_var = tb.IntVar(value=0)
    progress_bar = tb.Progressbar(
        container,
        variable=progress_var,
        mode="indeterminate",
        bootstyle="success-striped"
    )
    progress_bar.grid(row=row, column=0, columnspan=3, sticky="ew", padx=5, pady=10)

    row += 1

    # Status Log label (REQUIRED)
    tb.Label(container, text="Status Log:", anchor="w", font=("Arial", 10, "bold")).grid(
        row=row, column=0, columnspan=3, sticky="w", padx=5, pady=(10, 5)
    )

    row += 1

    # Status text area with queue-based threading
    status_frame = tb.Frame(container)
    status_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
    container.rowconfigure(row, weight=1)

    status_text = tb.Text(status_frame, height=15, wrap="word", state="normal")
    status_text.pack(side="left", fill="both", expand=True)

    scrollbar = tb.Scrollbar(status_frame, command=status_text.yview)
    scrollbar.pack(side="right", fill="y")
    status_text.config(yscrollcommand=scrollbar.set)

    # Create queues for thread-safe GUI updates
    status_queue = queue.Queue()
    button_control_queue = queue.Queue()

    def process_queues():
        """Process all pending messages from queues. Runs in main thread."""
        try:
            # Process status messages
            messages = []
            while True:
                try:
                    msg = status_queue.get_nowait()
                    messages.append(msg)
                except queue.Empty:
                    break

            if messages:
                status_text.config(state="normal")
                for msg in messages:
                    status_text.insert("end", msg + "\n")
                status_text.see("end")
                status_text.config(state="disabled")
                status_text.update_idletasks()

            # Process button control signals
            while True:
                try:
                    signal = button_control_queue.get_nowait()
                    if signal == "enable_buttons":
                        start_btn.config(state="normal")
                        clear_btn.config(state="normal")
                except queue.Empty:
                    break

        except Exception as e:
            logging.error(f"Error processing queues: {e}", exc_info=True)

        # Schedule next check (50ms = 20 times per second)
        app.after(50, process_queues)

    def clear_status():
        """Clear status text area."""
        status_text.config(state="normal")
        status_text.delete("1.0", "end")
        status_text.config(state="disabled")

    row += 1

    # Control buttons
    button_frame = tb.Frame(container)
    button_frame.grid(row=row, column=0, columnspan=3, pady=10)

    processing_thread = None

    def start_processing():
        """Start processing products."""
        nonlocal processing_thread

        if processing_thread and processing_thread.is_alive():
            messagebox.showwarning("Already Running", "Processing is already in progress.")
            return

        # Disable buttons during processing
        start_btn.config(state="disabled")
        clear_btn.config(state="disabled")

        # Start progress bar animation
        progress_bar.start()

        # Clear previous status
        clear_status()

        # Create and start worker thread with queues
        processing_thread = threading.Thread(
            target=process_products_worker,
            args=(cfg, status_queue, button_control_queue, app),
            daemon=True
        )
        processing_thread.start()

        # Monitor thread completion (for progress bar)
        def check_thread():
            if processing_thread.is_alive():
                app.after(100, check_thread)
            else:
                progress_bar.stop()

        app.after(100, check_thread)

    def stop_processing():
        """Stop processing (graceful shutdown not implemented - would require interrupt mechanism)."""
        messagebox.showinfo(
            "Stop Processing",
            "To stop processing, please close the application.\n\n"
            "Note: The current product will complete before stopping."
        )

    start_btn = tb.Button(
        button_frame,
        text="Start Processing",
        command=start_processing,
        bootstyle="success",
        width=20
    )
    start_btn.pack(side="left", padx=5)

    stop_btn = tb.Button(
        button_frame,
        text="Stop",
        command=stop_processing,
        bootstyle="danger",
        width=15
    )
    stop_btn.pack(side="left", padx=5)

    clear_btn = tb.Button(
        button_frame,
        text="Clear Log",
        command=clear_status,
        bootstyle="secondary",
        width=15
    )
    clear_btn.pack(side="left", padx=5)

    # Save window geometry on close
    def on_close():
        cfg["WINDOW_GEOMETRY"] = app.geometry()
        save_config(cfg)
        app.destroy()

    app.protocol("WM_DELETE_WINDOW", on_close)

    # Start queue processor (REQUIRED for thread-safe GUI updates)
    app.after(50, process_queues)

    # Add initial welcome messages
    def status(msg):
        """Queue-based status function for initialization."""
        status_queue.put(msg)

    status("=" * 80)
    status(f"Garoppos Product Categorizer {SCRIPT_VERSION}")
    status("GUI loaded successfully")
    status("=" * 80)
    status("")
    status("Configure your settings above and click 'Start Processing' to begin.")
    status("")

    # Start the GUI
    app.mainloop()


def main():
    """Main entry point for the application."""
    try:
        print(f"Starting {SCRIPT_VERSION}")
        build_gui()
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        logging.exception("Fatal error in main:")
        sys.exit(1)


if __name__ == "__main__":
    main()
