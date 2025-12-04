"""Security tests for command injection prevention."""

import shlex

from scout_mcp.utils.shell import quote_arg, quote_path


class TestShellQuoting:
    """Test shell quoting utilities."""

    def test_quote_path_simple(self):
        """Test quoting a simple path."""
        # shlex.quote only adds quotes when necessary
        quoted = quote_path("/var/log")
        # Simple paths may not need quotes, but result is still shell-safe
        assert quoted == "/var/log" or quoted == "'/var/log'"
        # Verify it's safe to use
        parts = shlex.split(f"cat {quoted}")
        assert len(parts) == 2
        assert parts[1] == "/var/log"

    def test_quote_path_with_spaces(self):
        """Test quoting a path with spaces."""
        assert quote_path("/var/log/my file.txt") == "'/var/log/my file.txt'"

    def test_quote_path_injection_attempt(self):
        """Test that injection attempts are safely quoted."""
        malicious = "/tmp'; rm -rf / #"
        quoted = quote_path(malicious)
        # Should be safely quoted - cannot break out
        # When we split the full command, the malicious parts should be contained
        full_cmd = f"cat {quoted}"
        parts = shlex.split(full_cmd)
        # The path should be a single argument to cat
        assert len(parts) == 2
        assert parts[0] == "cat"
        # rm -rf should not appear as separate commands
        assert "rm" not in parts
        assert "-rf" not in parts

    def test_quote_path_backticks(self):
        """Test that backticks are safely quoted."""
        malicious = "/tmp/`whoami`.txt"
        quoted = quote_path(malicious)
        assert quoted == "'/tmp/`whoami`.txt'"
        # Backticks should be escaped and not executed
        assert "`" in quoted

    def test_quote_path_dollar_expansion(self):
        """Test that dollar expansions are safely quoted."""
        malicious = "/tmp/$HOME/file"
        quoted = quote_path(malicious)
        assert quoted == "'/tmp/$HOME/file'"
        # Dollar signs should be preserved as literals
        assert "$" in quoted

    def test_quote_arg_semicolon(self):
        """Test that semicolons cannot inject commands."""
        malicious = "arg; rm -rf /"
        quoted = quote_arg(malicious)
        # The semicolon should be part of the quoted string
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert ";" in parts[0]
        # rm should not be a separate command
        assert "rm" not in shlex.split(f"echo {quoted}")[1:]

    def test_quote_arg_pipe(self):
        """Test that pipes cannot be used for command injection."""
        malicious = "arg | cat /etc/passwd"
        quoted = quote_arg(malicious)
        # The pipe should be part of the quoted string
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert "|" in parts[0]

    def test_quote_arg_ampersand(self):
        """Test that ampersands cannot background malicious commands."""
        malicious = "arg & evil-command"
        quoted = quote_arg(malicious)
        # The ampersand should be part of the quoted string
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert "&" in parts[0]

    def test_quote_path_newline(self):
        """Test that newlines are safely quoted."""
        malicious = "/tmp/file\nrm -rf /"
        quoted = quote_path(malicious)
        # Newline should be preserved as part of the path
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert "\n" in parts[0]

    def test_quote_empty_string(self):
        """Test quoting an empty string."""
        quoted = quote_path("")
        assert quoted == "''"

    def test_quote_path_with_quotes(self):
        """Test that quotes are properly escaped."""
        malicious = "/tmp/file'with'quotes"
        quoted = quote_path(malicious)
        # Should be safely quoted
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert "'" in parts[0]

    def test_quote_arg_double_quotes(self):
        """Test that double quotes are properly escaped."""
        malicious = 'arg"with"quotes'
        quoted = quote_arg(malicious)
        # Should be safely quoted
        parts = shlex.split(quoted)
        assert len(parts) == 1
        assert '"' in parts[0]

    def test_integration_with_command(self):
        """Test that quoted paths work correctly in full commands."""
        # Simulate what executors.py does
        path = "/tmp/file with spaces; rm -rf /"
        quoted = quote_path(path)
        cmd = f"cat {quoted}"

        # Parse the command as the shell would
        parts = shlex.split(cmd)

        # Should be exactly 2 parts: command and argument
        assert len(parts) == 2
        assert parts[0] == "cat"
        # The path should be preserved exactly
        assert parts[1] == path

    def test_comparison_with_repr(self):
        """Test that shlex.quote is more secure than repr."""
        # Example of a path that could be problematic with repr
        malicious = "/tmp/'; rm -rf / #"

        # With repr (INSECURE - old behavior)
        repr_quoted = repr(malicious)
        # repr just wraps in quotes but may use single or double quotes
        # and doesn't properly escape for shell
        assert "rm -rf" in repr_quoted

        # With shlex.quote (SECURE - new behavior)
        shell_quoted = quote_path(malicious)
        # shlex.quote properly escapes for shell with proper quoting
        # The exact format may vary but it must be shell-safe

        # When parsed, shlex.quote version is safe
        safe_parts = shlex.split(f"cat {shell_quoted}")
        assert len(safe_parts) == 2
        # The key test: the malicious string is treated as a single argument
        assert safe_parts[1] == malicious
        # And no command injection is possible
        assert "rm" not in [safe_parts[0]]
