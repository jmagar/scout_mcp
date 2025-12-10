"""Security tests for command execution."""

import pytest

from scout_mcp.services.executors import (
    validate_command,
    validate_container_name,
    validate_depth,
    validate_project_name,
)


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


class TestDockerValidation:
    """Test Docker/Compose input validation."""

    def test_validate_container_name_allows_valid(self):
        """Valid container names should pass."""
        assert validate_container_name("my-container") == "my-container"
        assert validate_container_name("app_1") == "app_1"
        assert validate_container_name("web.service") == "web.service"

    def test_validate_container_name_rejects_injection(self):
        """Container names with injection attempts should fail."""
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("container;id")
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("app`whoami`")
        with pytest.raises(ValueError, match="Invalid container name"):
            validate_container_name("test$(ls)")

    def test_validate_project_name_allows_valid(self):
        """Valid project names should pass."""
        assert validate_project_name("my-project") == "my-project"
        assert validate_project_name("stack_prod") == "stack_prod"

    def test_validate_project_name_rejects_injection(self):
        """Project names with injection attempts should fail."""
        with pytest.raises(ValueError, match="Invalid project name"):
            validate_project_name("project|whoami")

    def test_validate_depth_allows_valid_range(self):
        """Depth 1-10 should be allowed."""
        assert validate_depth(1) == 1
        assert validate_depth(5) == 5
        assert validate_depth(10) == 10

    def test_validate_depth_rejects_out_of_range(self):
        """Depth outside 1-10 should be rejected."""
        with pytest.raises(ValueError, match="depth must be 1-10"):
            validate_depth(0)
        with pytest.raises(ValueError, match="depth must be 1-10"):
            validate_depth(99999)
