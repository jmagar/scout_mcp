"""Protocol interfaces for dependency inversion.

Defines abstract interfaces that components depend on,
enabling easier testing and future refactoring.

Usage Example:

    from scout_mcp.protocols import SSHConnectionPool

    async def my_function(pool: SSHConnectionPool):
        '''Function depends on protocol, not concrete implementation.'''
        conn = await pool.get_connection(host)
        # ... use connection

    # Can pass any implementation
    from scout_mcp.services.pool import ConnectionPool
    await my_function(ConnectionPool())  # Works

    # Or mock for testing
    class MockPool:
        async def get_connection(self, host):
            return mock_connection

    await my_function(MockPool())  # Also works

Protocol Benefits:
    - Dependency inversion: Depend on abstractions, not concrete classes
    - Easier testing: Mock implementations for unit tests
    - Better architecture: Clear contracts between components
    - Runtime checking: @runtime_checkable enables isinstance() checks
"""

from typing import Any, Protocol, runtime_checkable

from scout_mcp.models import CommandResult, SSHHost


@runtime_checkable
class SSHConnectionPool(Protocol):
    """Protocol for SSH connection pooling.

    Implementations must provide connection management with
    retry and cleanup capabilities.

    Example implementation:
        class MyPool:
            async def get_connection(
                self, host: SSHHost
            ) -> asyncssh.SSHClientConnection:
                # Create or reuse connection
                return connection

            async def remove_connection(self, host_name: str) -> None:
                # Remove from pool
                pass

            async def close_all(self) -> None:
                # Close all connections
                pass
    """

    async def get_connection(self, host: SSHHost) -> Any:
        """Get or create connection for host.

        Args:
            host: SSH host configuration

        Returns:
            SSH connection object

        Raises:
            ConnectionError: If unable to connect
        """
        ...

    async def remove_connection(self, host_name: str) -> None:
        """Remove connection from pool.

        Args:
            host_name: Name of host to remove

        Note:
            Safe to call even if connection doesn't exist.
        """
        ...

    async def close_all(self) -> None:
        """Close all connections in pool.

        Should gracefully handle cleanup failures and
        ensure all resources are released.
        """
        ...


@runtime_checkable
class FileOperations(Protocol):
    """Protocol for file operations.

    Implementations must provide basic file/directory operations
    on remote systems via SSH.

    Example implementation:
        class RemoteFileOps:
            async def read_file(self, conn, path: str, max_size: int) -> str:
                # Read file via SSH
                return content

            async def list_directory(self, conn, path: str) -> str:
                # List directory via SSH
                return listing

            async def execute_command(
                self, conn, command: str, timeout: int
            ) -> CommandResult:
                # Execute command via SSH
                return CommandResult(...)
    """

    async def read_file(
        self,
        conn: Any,
        path: str,
        max_size: int,
    ) -> str:
        """Read file content.

        Args:
            conn: SSH connection
            path: File path
            max_size: Maximum file size in bytes

        Returns:
            File content as string

        Raises:
            FileNotFoundError: If file doesn't exist
            PermissionError: If no read permission
            ValueError: If file exceeds max_size
        """
        ...

    async def list_directory(
        self,
        conn: Any,
        path: str,
    ) -> str:
        """List directory contents.

        Args:
            conn: SSH connection
            path: Directory path

        Returns:
            Directory listing (format implementation-specific)

        Raises:
            FileNotFoundError: If directory doesn't exist
            PermissionError: If no read permission
            NotADirectoryError: If path is not a directory
        """
        ...

    async def execute_command(
        self,
        conn: Any,
        command: str,
        timeout: int,
    ) -> CommandResult:
        """Execute shell command.

        Args:
            conn: SSH connection
            command: Command to execute
            timeout: Command timeout in seconds

        Returns:
            Command result with stdout/stderr/exit_code

        Raises:
            TimeoutError: If command exceeds timeout
            PermissionError: If no execute permission
        """
        ...


@runtime_checkable
class CommandExecutor(Protocol):
    """Protocol for command execution.

    Simpler interface focused on command execution only.

    Example implementation:
        class RemoteExecutor:
            async def execute(
                self, conn, command: str, timeout: int
            ) -> CommandResult:
                # Run command remotely
                return CommandResult(...)
    """

    async def execute(
        self,
        conn: Any,
        command: str,
        timeout: int,
    ) -> CommandResult:
        """Execute command on remote host.

        Args:
            conn: SSH connection
            command: Command to execute
            timeout: Timeout in seconds

        Returns:
            Command result with output and exit code

        Raises:
            TimeoutError: If execution exceeds timeout
        """
        ...


@runtime_checkable
class FileReader(Protocol):
    """Protocol for file reading.

    Focused interface for reading file contents only.

    Example implementation:
        class RemoteFileReader:
            async def read(self, conn, path: str, max_size: int) -> str:
                # Read file from remote host
                return content
    """

    async def read(
        self,
        conn: Any,
        path: str,
        max_size: int,
    ) -> str:
        """Read file from remote host.

        Args:
            conn: SSH connection
            path: Path to file
            max_size: Maximum size to read

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file too large
        """
        ...


# Export all protocols
__all__ = [
    "SSHConnectionPool",
    "FileOperations",
    "CommandExecutor",
    "FileReader",
]
