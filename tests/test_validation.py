"""Tests for path and host validation."""

import pytest

from scout_mcp.utils.validation import (
    PathTraversalError,
    validate_host,
    validate_path,
)


class TestValidatePath:
    """Test path validation."""

    def test_simple_absolute_path(self):
        """Test validating a simple absolute path."""
        assert validate_path("/var/log") == "/var/log"

    def test_simple_relative_path(self):
        """Test validating a simple relative path."""
        assert validate_path("logs/app.log") == "logs/app.log"

    def test_home_directory(self):
        """Test that home directory paths are preserved."""
        assert validate_path("~/code") == "~/code"
        assert validate_path("~/.ssh/config") == "~/.ssh/config"

    def test_home_directory_expansion(self):
        """Test that ~username paths are preserved."""
        assert validate_path("~user/code") == "~user/code"

    def test_traversal_dot_dot_slash(self):
        """Test that ../ is rejected."""
        with pytest.raises(PathTraversalError, match="Path traversal not allowed"):
            validate_path("../etc/passwd")

    def test_traversal_embedded(self):
        """Test that embedded ../ is rejected."""
        with pytest.raises(PathTraversalError, match="Path traversal not allowed"):
            validate_path("/var/log/../../../etc/passwd")

    def test_traversal_normalized(self):
        """Test that paths escaping root after normalization are rejected."""
        with pytest.raises(PathTraversalError, match="Path traversal not allowed"):
            validate_path("/var/log/../../..")

    def test_traversal_just_double_dots(self):
        """Test that just '..' is rejected."""
        with pytest.raises(PathTraversalError, match="Path traversal not allowed"):
            validate_path("..")

    def test_traversal_slash_dot_dot(self):
        """Test that /.. is rejected."""
        with pytest.raises(PathTraversalError, match="Path traversal not allowed"):
            validate_path("/var/log/..")

    def test_null_byte(self):
        """Test that null bytes are rejected."""
        with pytest.raises(PathTraversalError, match="null byte"):
            validate_path("/var/log/app.log\x00.txt")

    def test_null_byte_embedded(self):
        """Test that embedded null bytes are rejected."""
        with pytest.raises(PathTraversalError, match="null byte"):
            validate_path("/var/\x00log/app.log")

    def test_empty_path(self):
        """Test that empty paths are rejected."""
        with pytest.raises(ValueError, match="Path cannot be empty"):
            validate_path("")

    def test_absolute_not_allowed(self):
        """Test that absolute paths can be rejected when configured."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            validate_path("/etc/passwd", allow_absolute=False)

    def test_relative_allowed_when_absolute_disabled(self):
        """Test that relative paths work when absolute paths are disabled."""
        assert validate_path("etc/passwd", allow_absolute=False) == "etc/passwd"

    def test_path_with_spaces(self):
        """Test that paths with spaces are allowed."""
        assert validate_path("/var/log/my file.log") == "/var/log/my file.log"

    def test_path_with_special_chars(self):
        """Test that paths with safe special characters are allowed."""
        assert validate_path("/var/log/app-2024.log") == "/var/log/app-2024.log"
        assert validate_path("/var/log/app_file.log") == "/var/log/app_file.log"
        assert validate_path("/var/log/file[1].log") == "/var/log/file[1].log"

    def test_normalization_removes_redundant_slashes(self):
        """Test that path normalization works."""
        # os.path.normpath removes redundant slashes
        assert validate_path("/var//log///app.log") == "/var/log/app.log"

    def test_normalization_removes_current_dir(self):
        """Test that current directory markers are normalized."""
        # os.path.normpath removes . components
        assert validate_path("/var/./log/./app.log") == "/var/log/app.log"


class TestValidateHost:
    """Test host validation."""

    def test_simple_host(self):
        """Test validating a simple hostname."""
        assert validate_host("myserver") == "myserver"

    def test_host_with_domain(self):
        """Test validating a fully qualified domain name."""
        assert validate_host("server.example.com") == "server.example.com"

    def test_host_with_subdomain(self):
        """Test validating hosts with multiple subdomains."""
        assert validate_host("web.prod.example.com") == "web.prod.example.com"

    def test_host_with_hyphen(self):
        """Test that hyphens in hostnames are allowed."""
        assert validate_host("web-server-01") == "web-server-01"

    def test_host_with_numbers(self):
        """Test that numbers in hostnames are allowed."""
        assert validate_host("server123") == "server123"

    def test_ip_address(self):
        """Test that IP addresses are valid hosts."""
        assert validate_host("192.168.1.100") == "192.168.1.100"

    def test_ipv6_address(self):
        """Test that IPv6 addresses are valid hosts."""
        # Note: colons are NOT in suspicious_chars for host validation
        # because they're needed for IPv6 and port specs handled elsewhere
        assert validate_host("2001:db8::1") == "2001:db8::1"

    def test_empty_host(self):
        """Test that empty hosts are rejected."""
        with pytest.raises(ValueError, match="Host cannot be empty"):
            validate_host("")

    def test_host_too_long(self):
        """Test that excessively long hostnames are rejected."""
        long_host = "a" * 254
        with pytest.raises(ValueError, match="Host name too long"):
            validate_host(long_host)

    def test_host_max_length(self):
        """Test that 253 character hostnames are allowed."""
        max_host = "a" * 253
        assert validate_host(max_host) == max_host

    def test_host_with_slash(self):
        """Test that slashes are rejected (path injection)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server/path")

    def test_host_with_semicolon(self):
        """Test that semicolons are rejected (command injection)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server;rm -rf /")

    def test_host_with_pipe(self):
        """Test that pipes are rejected (command injection)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server|cat /etc/passwd")

    def test_host_with_ampersand(self):
        """Test that ampersands are rejected (command injection)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server&background")

    def test_host_with_dollar(self):
        """Test that dollar signs are rejected (variable expansion)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server$VAR")

    def test_host_with_backtick(self):
        """Test that backticks are rejected (command substitution)."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server`whoami`")

    def test_host_with_newline(self):
        """Test that newlines are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server\nmalicious")

    def test_host_with_carriage_return(self):
        """Test that carriage returns are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server\rmalicious")

    def test_host_with_null_byte(self):
        """Test that null bytes are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server\x00malicious")

    def test_host_with_backslash(self):
        """Test that backslashes are rejected."""
        with pytest.raises(ValueError, match="invalid characters"):
            validate_host("server\\path")


class TestPathTraversalError:
    """Test the PathTraversalError exception."""

    def test_is_value_error(self):
        """Test that PathTraversalError is a ValueError."""
        assert issubclass(PathTraversalError, ValueError)

    def test_can_catch_as_value_error(self):
        """Test that PathTraversalError can be caught as ValueError."""
        with pytest.raises(ValueError):
            raise PathTraversalError("test")

    def test_error_message(self):
        """Test that error messages are preserved."""
        with pytest.raises(PathTraversalError, match="custom message"):
            raise PathTraversalError("custom message")


class TestIntegrationWithParser:
    """Test validation integration with parser."""

    def test_parser_rejects_traversal(self):
        """Test that parse_target rejects path traversal."""
        from scout_mcp.utils.parser import parse_target

        with pytest.raises(PathTraversalError):
            parse_target("myhost:../etc/passwd")

    def test_parser_rejects_malicious_host(self):
        """Test that parse_target rejects malicious hosts."""
        from scout_mcp.utils.parser import parse_target

        with pytest.raises(ValueError, match="invalid characters"):
            parse_target("host;rm -rf /:/var/log")

    def test_parser_accepts_valid_target(self):
        """Test that parse_target accepts valid targets."""
        from scout_mcp.utils.parser import parse_target

        target = parse_target("myhost:/var/log/app.log")
        assert target.host == "myhost"
        assert target.path == "/var/log/app.log"

    def test_parser_accepts_home_directory(self):
        """Test that parse_target accepts home directory paths."""
        from scout_mcp.utils.parser import parse_target

        target = parse_target("myhost:~/.ssh/config")
        assert target.host == "myhost"
        assert target.path == "~/.ssh/config"
