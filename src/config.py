"""
Configuration and logging management for Garoppos Product Categorizer.
"""

import os
import sys
import json
import logging

# Version
SCRIPT_VERSION = "1.0.0 - Garoppos Product Categorizer"

# File paths
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(APP_DIR, "config.json")
# Garoppos shared-docs directory (one level up from categorizer)
GAROPPOS_DIR = os.path.dirname(APP_DIR)
SHARED_DOCS_DIR = os.path.join(GAROPPOS_DIR, "shared-docs")


def load_config():
    """Load configuration from config.json or create with defaults."""
    default = {
        "_AI_SETTINGS": "AI settings for taxonomy and description enhancement.",
        "AI_PROVIDER": "claude",
        "_CLAUDE_AI_SETTINGS": "Claude AI specific settings.",
        "CLAUDE_API_KEY": "",
        "CLAUDE_MODEL": "claude-sonnet-4-5-20250929",
        "_OPENAI_SETTINGS": "OpenAI/ChatGPT specific settings.",
        "OPENAI_API_KEY": "",
        "OPENAI_MODEL": "gpt-5",
        "_BATCH_MODE_SETTINGS": "Batch API settings for cost savings (50% off standard pricing).",
        "USE_BATCH_MODE": False,
        "BATCH_COMPLETION_WINDOW": "24h",
        "BATCH_POLL_INTERVAL": 60,
        "_USER SETTINGS": "These are user settings specified in the main UI.",
        "INPUT_FILE": "",
        "OUTPUT_FILE": "",
        "LOG_FILE": "",
        "TAXONOMY_DOC_PATH": os.path.join(SHARED_DOCS_DIR, "PRODUCT_TAXONOMY.md"),
        "VOICE_TONE_DOC_PATH": os.path.join(SHARED_DOCS_DIR, "VOICE_AND_TONE_GUIDELINES.md"),
        "VERBOSE": False,
        "PROCESSING_MODE": "skip",
        "START_RECORD": "",
        "END_RECORD": "",
        "FORCE_REFRESH_AI_CACHE": False,
        "FORCE_REFRESH_TAXONOMY": False,
        "WINDOW_GEOMETRY": "800x800"
    }

    try:
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=4)
            return default
        else:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded_config = json.load(f)

                # Ensure all required fields exist
                for key in default:
                    if key not in loaded_config:
                        loaded_config[key] = default[key]

                return loaded_config
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse config.json: {e}. Using defaults.")
        return default
    except IOError as e:
        logging.error(f"Failed to read/write config.json: {e}. Using defaults.")
        return default
    except Exception as e:
        logging.error(f"Unexpected error loading config: {e}. Using defaults.")
        return default


def save_config(config):
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        logging.error(f"Failed to write config.json: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving config: {e}")


def setup_logging(log_path: str, level: int = logging.INFO):
    """
    Configure logging to file and console.

    Args:
        log_path: Path to log file
        level: Default logging level (typically INFO)
    """
    try:
        for h in logging.root.handlers[:]:
            logging.root.removeHandler(h)

        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
        )

        logging.root.setLevel(logging.DEBUG)
        logging.root.addHandler(file_handler)
        logging.root.addHandler(console_handler)

        install_global_exception_logging()
    except Exception as e:
        print(f"Failed to setup logging: {e}", file=sys.stderr)
        raise


def install_global_exception_logging():
    """Log all unhandled exceptions to the log file."""
    def _log_excepthook(exctype, value, tb):
        logging.critical(
            "Unhandled exception",
            exc_info=(exctype, value, tb)
        )
        sys.__excepthook__(exctype, value, tb)

    sys.excepthook = _log_excepthook


def log_and_status(status_fn, msg: str, level: str = "info", ui_msg: str = None):
    """
    Log a message to log file, console, AND UI status field.

    Args:
        status_fn: Function to update UI status field
        msg: Detailed message for log file and console
        level: Log level - "info", "warning", or "error"
        ui_msg: Optional user-friendly message for UI
    """
    if ui_msg is None:
        ui_msg = msg

    # Always log to file/console first
    if level == "error":
        logging.error(msg)
    elif level == "warning":
        logging.warning(msg)
    else:
        logging.info(msg)

    # Then try to update UI
    if status_fn is not None:
        try:
            status_fn(ui_msg)
        except Exception as e:
            logging.warning(f"status_fn raised while logging message: {e}", exc_info=True)
            # Print to console as fallback
            print(f"[STATUS] {ui_msg}")
