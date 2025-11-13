"""
Tests for categorizer_modules/config.py

Tests configuration loading, saving, and logging setup.
"""

import pytest
import json
import sys
import logging
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from categorizer_modules import config


# ============================================================================
# LOAD CONFIG TESTS
# ============================================================================

class TestLoadConfig:
    """Tests for load_config() function."""

    def test_load_nonexistent_creates_default(self, temp_dir, monkeypatch):
        """Test loading config when file doesn't exist creates default."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        result = config.load_config()

        assert result is not None
        assert "AI_PROVIDER" in result
        assert "CLAUDE_API_KEY" in result
        assert "OPENAI_API_KEY" in result
        assert result["AI_PROVIDER"] == "claude"
        assert config_path.exists()

    def test_load_existing_config(self, temp_config_file, monkeypatch):
        """Test loading existing config file."""
        monkeypatch.setattr(config, 'CONFIG_FILE', str(temp_config_file))

        result = config.load_config()

        assert result["AI_PROVIDER"] == "claude"
        assert result["CLAUDE_API_KEY"] == "test_claude_key_12345"
        assert result["CLAUDE_MODEL"] == "claude-sonnet-4-5-20250929"

    def test_load_config_with_missing_fields(self, temp_dir, monkeypatch):
        """Test loading config with missing fields adds defaults."""
        config_path = temp_dir / "config.json"
        incomplete_config = {
            "AI_PROVIDER": "openai"
            # Missing other required fields
        }
        with open(config_path, 'w') as f:
            json.dump(incomplete_config, f)

        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        result = config.load_config()

        # Should have added missing fields
        assert "CLAUDE_API_KEY" in result
        assert "OPENAI_API_KEY" in result
        assert "INPUT_FILE" in result
        # Should preserve existing value
        assert result["AI_PROVIDER"] == "openai"

    def test_load_corrupted_json(self, temp_dir, monkeypatch, caplog):
        """Test loading corrupted JSON returns defaults."""
        config_path = temp_dir / "corrupted.json"
        config_path.write_text("{ invalid json }")

        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        with caplog.at_level(logging.ERROR):
            result = config.load_config()

        assert result is not None  # Should return defaults
        assert "Failed to parse config.json" in caplog.text

    def test_load_config_io_error(self, temp_dir, monkeypatch, caplog):
        """Test handling of IO errors when loading config."""
        config_path = temp_dir / "config.json"
        # Create an existing config file first
        config_path.write_text('{"test": "value"}')
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        def mock_open_error(*args, **kwargs):
            raise IOError("Read error")

        with caplog.at_level(logging.ERROR):
            with patch("builtins.open", side_effect=mock_open_error):
                result = config.load_config()

        assert result is not None  # Should return defaults
        assert ("Failed to read/write config.json" in caplog.text or
                "Unexpected error loading config" in caplog.text)

    def test_load_config_unexpected_error(self, temp_dir, monkeypatch, caplog):
        """Test handling of unexpected errors when loading config."""
        config_path = temp_dir / "config.json"
        config_path.write_text('{"test": "value"}')
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        def mock_json_load_error(*args, **kwargs):
            raise ValueError("Unexpected error")

        with caplog.at_level(logging.ERROR):
            with patch("json.load", side_effect=mock_json_load_error):
                result = config.load_config()

        assert result is not None  # Should return defaults
        assert "Unexpected error loading config" in caplog.text

    def test_default_config_structure(self, temp_dir, monkeypatch):
        """Test that default config has expected structure."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        result = config.load_config()

        # Check all required fields exist
        assert "AI_PROVIDER" in result
        assert "CLAUDE_API_KEY" in result
        assert "CLAUDE_MODEL" in result
        assert "OPENAI_API_KEY" in result
        assert "OPENAI_MODEL" in result
        assert "INPUT_FILE" in result
        assert "OUTPUT_FILE" in result
        assert "LOG_FILE" in result
        assert "TAXONOMY_DOC_PATH" in result
        assert "VOICE_TONE_DOC_PATH" in result
        assert "WINDOW_GEOMETRY" in result

    def test_default_values(self, temp_dir, monkeypatch):
        """Test that default config has correct default values."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        result = config.load_config()

        assert result["AI_PROVIDER"] == "claude"
        assert result["CLAUDE_MODEL"] == "claude-sonnet-4-5-20250929"
        assert result["OPENAI_MODEL"] == "gpt-5"
        assert result["WINDOW_GEOMETRY"] == "800x800"


# ============================================================================
# SAVE CONFIG TESTS
# ============================================================================

class TestSaveConfig:
    """Tests for save_config() function."""

    def test_save_config_creates_file(self, temp_dir, monkeypatch):
        """Test saving config creates a new file."""
        config_path = temp_dir / "new_config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        test_config = {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": "test_key"
        }

        config.save_config(test_config)

        assert config_path.exists()
        with open(config_path, 'r') as f:
            loaded = json.load(f)
        assert loaded == test_config

    def test_save_config_overwrites_existing(self, temp_config_file, monkeypatch):
        """Test saving config overwrites existing file."""
        monkeypatch.setattr(config, 'CONFIG_FILE', str(temp_config_file))

        new_config = {
            "AI_PROVIDER": "openai",
            "OPENAI_MODEL": "gpt-4o"
        }

        config.save_config(new_config)

        with open(temp_config_file, 'r') as f:
            loaded = json.load(f)
        assert loaded["AI_PROVIDER"] == "openai"
        assert loaded["OPENAI_MODEL"] == "gpt-4o"

    def test_save_config_preserves_formatting(self, temp_dir, monkeypatch):
        """Test that saved config has proper JSON formatting."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        test_config = {
            "key1": "value1",
            "key2": {"nested": "value"}
        }

        config.save_config(test_config)

        with open(config_path, 'r') as f:
            content = f.read()

        # Should have indentation (not minified)
        assert '\n' in content
        assert '    ' in content or '\t' in content

    def test_save_config_io_error(self, temp_dir, monkeypatch, caplog):
        """Test handling of IO errors when saving config."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        def mock_open_error(*args, **kwargs):
            raise IOError("Write error")

        with caplog.at_level(logging.ERROR):
            with patch("builtins.open", side_effect=mock_open_error):
                config.save_config({"test": "value"})

        assert "Failed to write config.json" in caplog.text

    def test_save_config_unexpected_error(self, temp_dir, monkeypatch, caplog):
        """Test handling of unexpected errors when saving config."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        def mock_json_dump_error(*args, **kwargs):
            raise ValueError("Unexpected error")

        with caplog.at_level(logging.ERROR):
            with patch("json.dump", side_effect=mock_json_dump_error):
                config.save_config({"test": "value"})

        assert "Unexpected error saving config" in caplog.text


# ============================================================================
# SETUP LOGGING TESTS
# ============================================================================

class TestSetupLogging:
    """Tests for setup_logging() function."""

    def test_setup_logging_creates_handlers(self, temp_dir):
        """Test that setup_logging creates file and console handlers."""
        log_path = temp_dir / "test.log"

        config.setup_logging(str(log_path))

        # Check that handlers were created
        root_logger = logging.getLogger()
        assert len(root_logger.handlers) >= 2

        # Check that file handler exists
        file_handlers = [h for h in root_logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) > 0

        # Check that console handler exists
        console_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(console_handlers) > 0

    def test_setup_logging_creates_log_file(self, temp_dir):
        """Test that setup_logging creates log file."""
        log_path = temp_dir / "test.log"

        config.setup_logging(str(log_path))
        logging.info("Test log message")

        assert log_path.exists()
        with open(log_path, 'r') as f:
            content = f.read()
        assert "Test log message" in content

    def test_setup_logging_with_level(self, temp_dir):
        """Test setup_logging with custom logging level."""
        log_path = temp_dir / "test.log"

        config.setup_logging(str(log_path), level=logging.WARNING)

        # Info should not be logged
        logging.info("Info message")
        # Warning should be logged
        logging.warning("Warning message")

        with open(log_path, 'r') as f:
            content = f.read()
        assert "Warning message" in content
        # Info messages might be in file handler (DEBUG level), but not console

    def test_setup_logging_removes_old_handlers(self, temp_dir):
        """Test that setup_logging removes old handlers."""
        log_path = temp_dir / "test.log"

        # Setup logging twice
        config.setup_logging(str(log_path))
        initial_handler_count = len(logging.getLogger().handlers)

        config.setup_logging(str(log_path))
        final_handler_count = len(logging.getLogger().handlers)

        # Handler count should be the same (old handlers removed)
        assert final_handler_count == initial_handler_count

    def test_setup_logging_installs_exception_hook(self, temp_dir):
        """Test that setup_logging installs global exception handler."""
        log_path = temp_dir / "test.log"

        config.setup_logging(str(log_path))

        # Check that excepthook was modified
        assert sys.excepthook != sys.__excepthook__

    def test_setup_logging_formats_correctly(self, temp_dir):
        """Test that log messages have correct format."""
        log_path = temp_dir / "test.log"

        config.setup_logging(str(log_path))
        logging.info("Test message")

        with open(log_path, 'r') as f:
            content = f.read()

        # Should contain timestamp, level, and message
        assert "INFO" in content
        assert "Test message" in content
        assert "|" in content  # Format uses pipe separators

    def test_setup_logging_error_handling(self, temp_dir):
        """Test that setup_logging raises on critical errors."""
        # Try to create log in non-existent directory
        log_path = temp_dir / "nonexistent" / "subdir" / "test.log"

        with pytest.raises(Exception):
            config.setup_logging(str(log_path))


# ============================================================================
# LOG AND STATUS TESTS
# ============================================================================

class TestLogAndStatus:
    """Tests for log_and_status() function."""

    def test_log_and_status_info(self, mock_status_fn, caplog):
        """Test logging info message with status update."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(mock_status_fn, "Test info message")

        assert "Test info message" in caplog.text
        assert len(mock_status_fn.messages) == 1
        assert mock_status_fn.messages[0] == "Test info message"

    def test_log_and_status_warning(self, mock_status_fn, caplog):
        """Test logging warning message."""
        with caplog.at_level(logging.WARNING):
            config.log_and_status(mock_status_fn, "Test warning", level="warning")

        assert "Test warning" in caplog.text
        assert caplog.records[0].levelname == "WARNING"

    def test_log_and_status_error(self, mock_status_fn, caplog):
        """Test logging error message."""
        with caplog.at_level(logging.ERROR):
            config.log_and_status(mock_status_fn, "Test error", level="error")

        assert "Test error" in caplog.text
        assert caplog.records[0].levelname == "ERROR"

    def test_log_and_status_with_ui_msg(self, mock_status_fn, caplog):
        """Test logging with separate UI message."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(
                mock_status_fn,
                "Detailed log message",
                ui_msg="Simple UI message"
            )

        assert "Detailed log message" in caplog.text
        assert mock_status_fn.messages[0] == "Simple UI message"

    def test_log_and_status_none_status_fn(self, caplog):
        """Test logging with None status function."""
        with caplog.at_level(logging.INFO):
            config.log_and_status(None, "Test message")

        assert "Test message" in caplog.text
        # Should not raise error

    def test_log_and_status_exception_in_status_fn(self, caplog):
        """Test handling exception in status function."""
        def failing_status_fn(msg):
            raise ValueError("Status function failed")

        with caplog.at_level(logging.INFO):
            config.log_and_status(failing_status_fn, "Test message")

        # The original message should be logged at INFO level
        # The exception warning should be at WARNING level
        assert "status_fn raised while logging message" in caplog.text


# ============================================================================
# GLOBAL EXCEPTION LOGGING TESTS
# ============================================================================

class TestGlobalExceptionLogging:
    """Tests for install_global_exception_logging() function."""

    def test_exception_hook_installed(self, temp_dir):
        """Test that exception hook is installed."""
        log_path = temp_dir / "test.log"
        config.setup_logging(str(log_path))

        # Check that sys.excepthook was modified
        assert sys.excepthook != sys.__excepthook__

    def test_exception_logged_to_file(self, temp_dir):
        """Test that unhandled exceptions are logged to file."""
        log_path = temp_dir / "test.log"
        config.setup_logging(str(log_path))

        # Manually trigger the exception hook
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()
            sys.excepthook(*exc_info)

        # Check log file
        with open(log_path, 'r') as f:
            content = f.read()
        assert "Unhandled exception" in content or "Test exception" in content


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestConfigIntegration:
    """Integration tests for config module."""

    def test_load_save_load_cycle(self, temp_dir, monkeypatch):
        """Test that config can be loaded, modified, saved, and reloaded."""
        config_path = temp_dir / "config.json"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Load (creates default)
        cfg1 = config.load_config()
        original_provider = cfg1["AI_PROVIDER"]

        # Modify
        cfg1["AI_PROVIDER"] = "openai"
        cfg1["OPENAI_MODEL"] = "gpt-4o"

        # Save
        config.save_config(cfg1)

        # Reload
        cfg2 = config.load_config()

        assert cfg2["AI_PROVIDER"] == "openai"
        assert cfg2["OPENAI_MODEL"] == "gpt-4o"
        assert cfg2["AI_PROVIDER"] != original_provider

    def test_config_and_logging_together(self, temp_dir, monkeypatch):
        """Test using config and logging together."""
        config_path = temp_dir / "config.json"
        log_path = temp_dir / "test.log"
        monkeypatch.setattr(config, 'CONFIG_FILE', str(config_path))

        # Load config
        cfg = config.load_config()
        cfg["LOG_FILE"] = str(log_path)
        config.save_config(cfg)

        # Setup logging
        config.setup_logging(cfg["LOG_FILE"])

        # Log a message
        logging.info("Test integration message")

        # Verify log file exists and contains message
        assert Path(log_path).exists()
        with open(log_path, 'r') as f:
            content = f.read()
        assert "Test integration message" in content
