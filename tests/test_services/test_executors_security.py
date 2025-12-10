"""Security tests for command execution."""

import pytest
from scout_mcp.services.executors import validate_command, run_command
from scout_mcp.models import CommandResult


class TestCommandValidation:
    """Test command validation prevents injection."""

    def test_validate_command_allows_safe_commands(self):
        """Safe commands in allowlist should pass validation."""
        cmd, args = validate_command("grep pattern file.txt")
        assert cmd == "grep"
        assert args == ["pattern", "file.txt"]

    def test_validate_command_rejects_dangerous_commands(self):
        """Commands not in allowlist should be rejected."""
        with pytest.raises(ValueError, match="Command 'rm' not allowed"):
            validate_command("rm -rf /")

    def test_validate_command_rejects_shell_metacharacters(self):
        """Shell metacharacters in command should be rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_command("ls; whoami")

    def test_validate_command_rejects_command_substitution(self):
        """Command substitution attempts should be rejected."""
        with pytest.raises(ValueError, match="not allowed"):
            validate_command("echo $(whoami)")

    def test_validate_command_handles_empty_command(self):
        """Empty command should raise ValueError."""
        with pytest.raises(ValueError, match="Empty command"):
            validate_command("")

    def test_validate_command_with_flags(self):
        """Commands with flags should be parsed correctly."""
        cmd, args = validate_command("grep -r pattern dir/")
        assert cmd == "grep"
        assert "-r" in args
        assert "pattern" in args
