"""SSH command executors for file operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncssh


@dataclass
class CommandResult:
    """Result of a remote command execution."""

    output: str
    error: str
    returncode: int


async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    """Determine if path is a file, directory, or doesn't exist.

    Returns:
        'file', 'directory', or None if path doesn't exist.
    """
    result = await conn.run(
        f'stat -c "%F" {path!r} 2>/dev/null',
        check=False
    )

    if result.returncode != 0:
        return None

    stdout = result.stdout
    if stdout is None:
        return None

    # Handle bytes or str
    if isinstance(stdout, bytes):
        file_type = stdout.decode("utf-8", errors="replace").strip().lower()
    else:
        file_type = stdout.strip().lower()

    if "directory" in file_type:
        return "directory"
    elif "regular" in file_type or "file" in file_type:
        return "file"
    else:
        return "file"  # Treat other types as files


async def cat_file(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_size: int,
) -> str:
    """Read file contents, limited to max_size bytes.

    Returns:
        File contents as string.

    Raises:
        RuntimeError: If file cannot be read.
    """
    result = await conn.run(
        f'head -c {max_size} {path!r}',
        check=False
    )

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to read {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return stdout


async def ls_dir(conn: "asyncssh.SSHClientConnection", path: str) -> str:
    """List directory contents with details.

    Returns:
        Directory listing as formatted string.

    Raises:
        RuntimeError: If directory cannot be listed.
    """
    result = await conn.run(
        f'ls -la {path!r}',
        check=False
    )

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to list {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace")
    return stdout


async def run_command(
    conn: "asyncssh.SSHClientConnection",
    working_dir: str,
    command: str,
    timeout: int,
) -> CommandResult:
    """Execute arbitrary command in working directory.

    Returns:
        CommandResult with stdout, stderr, and return code.
    """
    full_command = f'cd {working_dir!r} && timeout {timeout} {command}'

    result = await conn.run(full_command, check=False)

    # Handle stdout
    stdout = result.stdout
    if stdout is None:
        output = ""
    elif isinstance(stdout, bytes):
        output = stdout.decode("utf-8", errors="replace")
    else:
        output = stdout

    # Handle stderr
    stderr = result.stderr
    if stderr is None:
        error = ""
    elif isinstance(stderr, bytes):
        error = stderr.decode("utf-8", errors="replace")
    else:
        error = stderr

    # Handle returncode
    returncode = result.returncode if result.returncode is not None else 0

    return CommandResult(
        output=output,
        error=error,
        returncode=returncode,
    )
