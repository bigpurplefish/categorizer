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
    settings_window.geometry("700x350")
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

    # Info label about AI
    info_frame = tb.Frame(main_frame)
    info_frame.grid(row=5, column=0, columnspan=2, sticky="ew", pady=10)

    info_label = tb.Label(
        info_frame,
        text="Configure AI provider and model selection in the main window.\n"
             "API keys are required for AI enhancement features.",
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

        save_config(cfg)
        messagebox.showinfo("Settings Saved", "API settings have been saved successfully.")
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


def process_products_worker(cfg, status_fn, progress_var, app):
    """
    Worker thread function to process products with AI enhancement.

    Args:
        cfg: Configuration dictionary
        status_fn: Status update function
        progress_var: Progress bar variable
        app: Main application window
    """
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

        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, "GAROPPOS PRODUCT CATEGORIZER")
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, f"Version: {SCRIPT_VERSION}")
        log_and_status(status_fn, "")

        # Load input products
        log_and_status(status_fn, f"Loading products from: {input_file}")
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                products = json.load(f)

            if not isinstance(products, list):
                raise ValueError("Input file must contain a JSON array of products")

            if len(products) == 0:
                raise ValueError("Input file contains no products")

            log_and_status(status_fn, f"Loaded {len(products)} products")
            log_and_status(status_fn, "")

        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON from input file: {e}"
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("JSON Error", error_msg))
            return
        except Exception as e:
            error_msg = f"Failed to load input file: {e}"
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Load Error", error_msg))
            return

        # Get taxonomy and voice/tone document paths
        taxonomy_path = cfg.get("TAXONOMY_DOC_PATH", "").strip()
        voice_tone_path = cfg.get("VOICE_TONE_DOC_PATH", "").strip()

        if not taxonomy_path or not os.path.exists(taxonomy_path):
            error_msg = f"Taxonomy document not found: {taxonomy_path}"
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Config Error", error_msg))
            return

        if not voice_tone_path or not os.path.exists(voice_tone_path):
            error_msg = f"Voice/tone guidelines document not found: {voice_tone_path}"
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Config Error", error_msg))
            return

        # Process products with AI enhancement
        log_and_status(status_fn, "Starting AI enhancement...")
        log_and_status(status_fn, "")

        try:
            enhanced_products = batch_enhance_products(
                products,
                cfg,
                status_fn,
                taxonomy_path,
                voice_tone_path
            )

            log_and_status(status_fn, "")
            log_and_status(status_fn, f"Enhanced {len(enhanced_products)} products")

        except Exception as e:
            error_msg = f"AI enhancement failed: {e}"
            log_and_status(status_fn, "", "error")
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Enhancement Error", error_msg))
            return

        # Save enhanced products to output file
        log_and_status(status_fn, "")
        log_and_status(status_fn, f"Saving enhanced products to: {output_file}")

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_products, f, indent=2, ensure_ascii=False)

            log_and_status(status_fn, f"Successfully saved {len(enhanced_products)} products")

        except Exception as e:
            error_msg = f"Failed to save output file: {e}"
            log_and_status(status_fn, error_msg, "error")
            app.after(0, lambda: messagebox.showerror("Save Error", error_msg))
            return

        # Success!
        log_and_status(status_fn, "")
        log_and_status(status_fn, "=" * 80)
        log_and_status(status_fn, "CATEGORIZATION COMPLETE")
        log_and_status(status_fn, "=" * 80)

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

    # Add settings button
    settings_btn = tb.Button(
        toolbar,
        text="API Settings",
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

    # Status text area
    status_frame = tb.Frame(container)
    status_frame.grid(row=row, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)
    container.rowconfigure(row, weight=1)

    status_text = tb.Text(status_frame, height=15, wrap="word", state="disabled")
    status_text.pack(side="left", fill="both", expand=True)

    scrollbar = tb.Scrollbar(status_frame, command=status_text.yview)
    scrollbar.pack(side="right", fill="y")
    status_text.config(yscrollcommand=scrollbar.set)

    def update_status(message):
        """Update status text area."""
        status_text.config(state="normal")
        status_text.insert("end", message + "\n")
        status_text.see("end")
        status_text.config(state="disabled")
        app.update_idletasks()

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

        # Start progress bar animation
        progress_bar.start()

        # Clear previous status
        clear_status()

        # Create and start worker thread
        processing_thread = threading.Thread(
            target=process_products_worker,
            args=(cfg, update_status, progress_var, app),
            daemon=True
        )
        processing_thread.start()

        # Monitor thread completion
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
