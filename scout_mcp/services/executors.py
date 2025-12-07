"""SSH command executors for file operations."""

import asyncio
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from scout_mcp.models import BroadcastResult, CommandResult

if TYPE_CHECKING:
    import asyncssh

    from scout_mcp.config import Config
    from scout_mcp.services.pool import ConnectionPool


@dataclass
class TransferResult:
    """Result of a file transfer operation."""

    success: bool
    message: str
    bytes_transferred: int = 0


async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    """Determine if path is a file, directory, or doesn't exist.

    Returns:
        'file', 'directory', or None if path doesn't exist.
    """
    cmd = f'stat -c "%F" {shlex.quote(path)} 2>/dev/null'
    result = await conn.run(cmd, check=False)

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
) -> tuple[str, bool]:
    """Read file contents, limited to max_size bytes.

    Returns:
        Tuple of (file contents as string, was_truncated boolean).

    Raises:
        RuntimeError: If file cannot be read.
    """
    result = await conn.run(f"head -c {max_size} {shlex.quote(path)}", check=False)

    if result.returncode != 0:
        stderr = result.stderr
        if isinstance(stderr, bytes):
            error_msg = stderr.decode("utf-8", errors="replace")
        else:
            error_msg = stderr or ""
        raise RuntimeError(f"Failed to read {path}: {error_msg}")

    stdout = result.stdout
    if stdout is None:
        return ("", False)

    if isinstance(stdout, bytes):
        content = stdout.decode("utf-8", errors="replace")
    else:
        content = stdout

    # Check if file was truncated by comparing output length to max_size
    was_truncated = len(content.encode("utf-8")) >= max_size

    return (content, was_truncated)


async def ls_dir(conn: "asyncssh.SSHClientConnection", path: str) -> str:
    """List directory contents with details.

    Returns:
        Directory listing as formatted string.

    Raises:
        RuntimeError: If directory cannot be listed.
    """
    result = await conn.run(f"ls -la {shlex.quote(path)}", check=False)

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


async def tree_dir(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    max_depth: int = 3,
) -> str:
    """Show directory tree structure.

    Tries 'tree' command first, falls back to 'find' if unavailable.

    Args:
        conn: SSH connection to execute command on.
        path: Directory path to show tree for.
        max_depth: Maximum depth to traverse (default: 3).

    Returns:
        Directory tree as formatted string.
    """
    # Try tree command first
    result = await conn.run(
        f"tree -L {max_depth} --noreport {shlex.quote(path)} 2>/dev/null", check=False
    )

    if result.returncode == 0:
        stdout = result.stdout
        if stdout is None:
            return ""
        if isinstance(stdout, bytes):
            return stdout.decode("utf-8", errors="replace")
        return stdout

    # Fall back to find
    find_cmd = (
        f"find {shlex.quote(path)} -maxdepth {max_depth} -type f -o -type d "
        f"2>/dev/null | head -100"
    )
    result = await conn.run(find_cmd, check=False)

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
    full_command = f"cd {shlex.quote(working_dir)} && timeout {timeout} {command}"

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


async def docker_logs(
    conn: "asyncssh.SSHClientConnection",
    container: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker container logs.

    Args:
        conn: SSH connection to execute command on.
        container: Container name or ID.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps in output (default: True).

    Returns:
        Tuple of (logs content, container_exists boolean).

    Raises:
        RuntimeError: If Docker command fails unexpectedly.
    """
    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker logs --tail {tail} {ts_flag} {shlex.quote(container)} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for "No such container" error
    if result.returncode != 0:
        if "No such container" in stdout or "no such container" in stdout.lower():
            return ("", False)
        # Docker daemon not running or other error
        raise RuntimeError(f"Docker error: {stdout}")

    return (stdout, True)


async def docker_ps(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List Docker containers on remote host.

    Returns:
        List of dicts with 'name', 'status', 'image' keys.
        Empty list if Docker not available.
    """
    cmd = "docker ps -a --format '{{.Names}}\\t{{.Status}}\\t{{.Image}}' 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for Docker errors
    if result.returncode != 0:
        return []  # Docker not available

    containers = []
    for line in stdout.strip().split("\n"):
        if not line or "\t" not in line:
            continue
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            containers.append(
                {
                    "name": parts[0],
                    "status": parts[1],
                    "image": parts[2],
                }
            )

    return containers


async def docker_inspect(
    conn: "asyncssh.SSHClientConnection",
    container: str,
) -> bool:
    """Check if Docker container exists.

    Returns:
        True if container exists, False otherwise.
    """
    quoted = shlex.quote(container)
    cmd = f"docker inspect --format '{{{{.Name}}}}' {quoted} 2>/dev/null"

    result = await conn.run(cmd, check=False)
    return result.returncode == 0


async def compose_ls(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List Docker Compose projects on remote host.

    Returns:
        List of dicts with 'name', 'status', 'config_file' keys.
        Empty list if Docker Compose not available.
    """
    import json

    cmd = "docker compose ls --format json 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for errors
    if result.returncode != 0:
        return []

    # Parse JSON output
    try:
        projects = json.loads(stdout)
        return [
            {
                "name": p.get("Name", ""),
                "status": p.get("Status", ""),
                "config_file": p.get("ConfigFiles", ""),
            }
            for p in projects
        ]
    except json.JSONDecodeError:
        return []


async def compose_config(
    conn: "asyncssh.SSHClientConnection",
    project: str,
) -> tuple[str, str | None]:
    """Read Docker Compose config file for a project.

    Args:
        conn: SSH connection.
        project: Compose project name.

    Returns:
        Tuple of (config_content, config_path) or ("", None) if not found.
    """
    import json

    # First get the config file path
    cmd = "docker compose ls --format json 2>&1"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return ("", None)
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return ("", None)

    # Find the project
    try:
        projects = json.loads(stdout)
        config_file = None
        for p in projects:
            if p.get("Name") == project:
                config_file = p.get("ConfigFiles")
                break

        if not config_file:
            return ("", None)

        # Read the config file
        read_result = await conn.run(f"cat {shlex.quote(config_file)}", check=False)

        if read_result.returncode != 0:
            return ("", config_file)

        content = read_result.stdout
        if content is None:
            return ("", config_file)
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")

        return (content, config_file)

    except json.JSONDecodeError:
        return ("", None)


async def compose_logs(
    conn: "asyncssh.SSHClientConnection",
    project: str,
    tail: int = 100,
    timestamps: bool = True,
) -> tuple[str, bool]:
    """Fetch Docker Compose stack logs.

    Args:
        conn: SSH connection.
        project: Compose project name.
        tail: Number of lines from end (default: 100).
        timestamps: Include timestamps (default: True).

    Returns:
        Tuple of (logs content, project_exists boolean).
    """
    ts_flag = "--timestamps" if timestamps else ""
    cmd = f"docker compose -p {shlex.quote(project)} logs --tail {tail} {ts_flag} 2>&1"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    # Check for project not found
    if result.returncode != 0:
        if "no configuration file provided" in stdout.lower():
            return ("", False)
        # Other error - still return output
        return (stdout, True)

    return (stdout, True)


async def zfs_check(
    conn: "asyncssh.SSHClientConnection",
) -> bool:
    """Check if ZFS is available on remote host.

    Returns:
        True if ZFS is available, False otherwise.
    """
    cmd = "command -v zpool >/dev/null 2>&1 && zpool status >/dev/null 2>&1"
    result = await conn.run(cmd, check=False)
    return result.returncode == 0


async def zfs_pools(
    conn: "asyncssh.SSHClientConnection",
) -> list[dict[str, str]]:
    """List ZFS pools on remote host.

    Returns:
        List of dicts with 'name', 'size', 'alloc', 'free', 'cap', 'health' keys.
        Empty list if ZFS not available.
    """
    cmd = "zpool list -H -o name,size,alloc,free,cap,health 2>/dev/null"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    pools = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 6:
            pools.append(
                {
                    "name": parts[0],
                    "size": parts[1],
                    "alloc": parts[2],
                    "free": parts[3],
                    "cap": parts[4],
                    "health": parts[5],
                }
            )
    return pools


async def zfs_pool_status(
    conn: "asyncssh.SSHClientConnection",
    pool: str,
) -> tuple[str, bool]:
    """Get detailed status of a ZFS pool.

    Args:
        conn: SSH connection.
        pool: Pool name.

    Returns:
        Tuple of (status_output, pool_exists).
    """
    cmd = f"zpool status {shlex.quote(pool)} 2>&1"
    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        stdout = ""
    elif isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        if "no such pool" in stdout.lower():
            return ("", False)
        return (stdout, True)

    return (stdout, True)


async def zfs_datasets(
    conn: "asyncssh.SSHClientConnection",
    pool: str | None = None,
) -> list[dict[str, str]]:
    """List ZFS datasets on remote host.

    Args:
        conn: SSH connection.
        pool: Optional pool name to filter by.

    Returns:
        List of dicts with 'name', 'used', 'avail', 'refer', 'mountpoint' keys.
    """
    if pool:
        quoted_pool = shlex.quote(pool)
        cmd = (
            f"zfs list -H -r -o name,used,avail,refer,mountpoint "
            f"{quoted_pool} 2>/dev/null"
        )
    else:
        cmd = "zfs list -H -o name,used,avail,refer,mountpoint 2>/dev/null"

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    datasets = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 5:
            datasets.append(
                {
                    "name": parts[0],
                    "used": parts[1],
                    "avail": parts[2],
                    "refer": parts[3],
                    "mountpoint": parts[4],
                }
            )
    return datasets


async def zfs_snapshots(
    conn: "asyncssh.SSHClientConnection",
    dataset: str | None = None,
    limit: int = 50,
) -> list[dict[str, str]]:
    """List ZFS snapshots on remote host.

    Args:
        conn: SSH connection.
        dataset: Optional dataset name to filter by.
        limit: Maximum number of snapshots to return.

    Returns:
        List of dicts with 'name', 'used', 'creation' keys.
    """
    if dataset:
        cmd = (
            f"zfs list -H -t snapshot -r -o name,used,creation "
            f"{shlex.quote(dataset)} 2>/dev/null | tail -{limit}"
        )
    else:
        cmd = (
            f"zfs list -H -t snapshot -o name,used,creation 2>/dev/null | tail -{limit}"
        )

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return []
    if isinstance(stdout, bytes):
        stdout = stdout.decode("utf-8", errors="replace")

    if result.returncode != 0:
        return []

    snapshots = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 2)
        if len(parts) >= 3:
            snapshots.append(
                {
                    "name": parts[0],
                    "used": parts[1],
                    "creation": parts[2],
                }
            )
    return snapshots


async def syslog_read(
    conn: "asyncssh.SSHClientConnection",
    lines: int = 100,
) -> tuple[str, str]:
    """Read system logs from remote host.

    Tries journalctl first (systemd), falls back to /var/log/syslog.

    Args:
        conn: SSH connection
        lines: Number of log lines to retrieve (default 100)

    Returns:
        Tuple of (log content, source).
        Source is 'journalctl', 'syslog', or 'none'.
    """
    # Try journalctl first (systemd systems)
    check_journalctl = await conn.run("command -v journalctl", check=False)
    if check_journalctl.returncode == 0:
        result = await conn.run(
            f"journalctl --no-pager -n {lines} 2>/dev/null",
            check=False,
        )
        if result.returncode == 0:
            stdout = result.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            return (stdout, "journalctl")

    # Fall back to /var/log/syslog
    check_syslog = await conn.run("test -r /var/log/syslog", check=False)
    if check_syslog.returncode == 0:
        result = await conn.run(
            f"tail -n {lines} /var/log/syslog 2>/dev/null",
            check=False,
        )
        if result.returncode == 0:
            stdout = result.stdout or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            return (stdout, "syslog")

    return ("", "none")


async def find_files(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    pattern: str,
    max_depth: int = 5,
    file_type: str | None = None,
    max_results: int = 100,
) -> str:
    """Find files matching pattern under path.

    Args:
        conn: SSH connection
        path: Starting directory path
        pattern: Glob pattern (e.g., "*.py", "config*")
        max_depth: Maximum depth to search (default: 5)
        file_type: Optional type filter ('f' for files, 'd' for dirs)
        max_results: Maximum results to return (default: 100)

    Returns:
        Newline-separated list of matching paths, or error message.
    """
    # Build find command
    type_flag = f"-type {shlex.quote(file_type)}" if file_type else ""
    cmd = (
        f"find {shlex.quote(path)} -maxdepth {max_depth} -name {shlex.quote(pattern)} "
        f"{type_flag} 2>/dev/null | head -{max_results}"
    )

    result = await conn.run(cmd, check=False)

    stdout = result.stdout
    if stdout is None:
        return ""
    if isinstance(stdout, bytes):
        return stdout.decode("utf-8", errors="replace").strip()
    return stdout.strip()


async def diff_files(
    conn1: "asyncssh.SSHClientConnection",
    path1: str,
    conn2: "asyncssh.SSHClientConnection",
    path2: str,
    max_file_size: int = 1048576,
    context_lines: int = 3,
) -> tuple[str, bool]:
    """Compare two files from potentially different hosts.

    Args:
        conn1: SSH connection for first file
        path1: Path to first file
        conn2: SSH connection for second file
        path2: Path to second file
        max_file_size: Maximum file size to read (default: 1MB)
        context_lines: Number of context lines in diff output (default: 3)

    Returns:
        Tuple of (diff output, files_are_identical).
        Empty diff output means files are identical.
    """
    import difflib

    # Read both files
    content1, _ = await cat_file(conn1, path1, max_file_size)
    content2, _ = await cat_file(conn2, path2, max_file_size)

    # Check if identical
    if content1 == content2:
        return ("", True)

    # Generate unified diff
    diff = difflib.unified_diff(
        content1.splitlines(keepends=True),
        content2.splitlines(keepends=True),
        fromfile=path1,
        tofile=path2,
        n=context_lines,
    )
    diff_output = "".join(diff)

    return (diff_output, False)


async def diff_with_content(
    conn: "asyncssh.SSHClientConnection",
    path: str,
    expected_content: str,
    max_file_size: int = 1048576,
    context_lines: int = 3,
) -> tuple[str, bool]:
    """Compare remote file with expected content.

    Args:
        conn: SSH connection
        path: Remote file path
        expected_content: Content to compare against
        max_file_size: Maximum file size to read (default: 1MB)
        context_lines: Number of context lines in diff output (default: 3)

    Returns:
        Tuple of (diff output, files_are_identical).
    """
    import difflib

    # Read remote file
    actual_content, _ = await cat_file(conn, path, max_file_size)

    # Check if identical
    if actual_content == expected_content:
        return ("", True)

    # Generate unified diff
    diff = difflib.unified_diff(
        expected_content.splitlines(keepends=True),
        actual_content.splitlines(keepends=True),
        fromfile="expected",
        tofile=path,
        n=context_lines,
    )
    diff_output = "".join(diff)

    return (diff_output, False)


async def broadcast_read(
    pool: "ConnectionPool",
    config: "Config",
    targets: list[tuple[str, str]],
    max_file_size: int,
) -> list[BroadcastResult]:
    """Read files/directories from multiple hosts concurrently.

    Args:
        pool: Connection pool
        config: Scout config for host lookup
        targets: List of (host_name, path) tuples
        max_file_size: Maximum file size to read

    Returns:
        List of BroadcastResult, one per target.
    """

    async def read_single(host_name: str, path: str) -> BroadcastResult:
        """Read from a single host."""
        try:
            ssh_host = config.get_host(host_name)
            if ssh_host is None:
                return BroadcastResult(
                    host=host_name,
                    path=path,
                    output="",
                    success=False,
                    error=f"Unknown host: {host_name}",
                )

            conn = await pool.get_connection(ssh_host)
            path_type = await stat_path(conn, path)

            if path_type == "file":
                content, _ = await cat_file(conn, path, max_file_size)
                return BroadcastResult(
                    host=host_name, path=path, output=content, success=True
                )
            elif path_type == "directory":
                listing = await ls_dir(conn, path)
                return BroadcastResult(
                    host=host_name, path=path, output=listing, success=True
                )
            else:
                return BroadcastResult(
                    host=host_name,
                    path=path,
                    output="",
                    success=False,
                    error=f"Path not found: {path}",
                )
        except Exception as e:
            return BroadcastResult(
                host=host_name, path=path, output="", success=False, error=str(e)
            )

    tasks = [read_single(h, p) for h, p in targets]
    results = await asyncio.gather(*tasks)
    return list(results)


async def broadcast_command(
    pool: "ConnectionPool",
    config: "Config",
    targets: list[tuple[str, str]],
    command: str,
    timeout: int,
) -> list[BroadcastResult]:
    """Execute command on multiple hosts concurrently.

    Args:
        pool: Connection pool
        config: Scout config for host lookup
        targets: List of (host_name, path) tuples
        command: Shell command to execute
        timeout: Command timeout in seconds

    Returns:
        List of BroadcastResult, one per target.
    """

    async def execute_single(host_name: str, path: str) -> BroadcastResult:
        """Execute command on a single host."""
        try:
            ssh_host = config.get_host(host_name)
            if ssh_host is None:
                return BroadcastResult(
                    host=host_name,
                    path=path,
                    output="",
                    success=False,
                    error=f"Unknown host: {host_name}",
                )

            conn = await pool.get_connection(ssh_host)
            result = await run_command(conn, path, command, timeout)

            # Format output
            output_parts = [result.output]
            if result.error:
                output_parts.append("\n---\nErrors:\n" + result.error)
            if result.returncode != 0:
                output_parts.append(f"\nExit code: {result.returncode}")

            output = "".join(output_parts)
            success = result.returncode == 0

            error_msg = (
                None if success else f"Command exited with code {result.returncode}"
            )
            return BroadcastResult(
                host=host_name,
                path=path,
                output=output,
                success=success,
                error=error_msg,
            )
        except Exception as e:
            return BroadcastResult(
                host=host_name, path=path, output="", success=False, error=str(e)
            )

    tasks = [execute_single(h, p) for h, p in targets]
    results = await asyncio.gather(*tasks)
    return list(results)


async def beam_transfer(
    conn: "asyncssh.SSHClientConnection",
    source: str,
    destination: str,
    direction: str,
) -> TransferResult:
    """Transfer file using SFTP (beam action).

    Args:
        conn: SSH connection to remote host
        source: Source path (local or remote depending on direction)
        destination: Destination path (local or remote depending on direction)
        direction: Either "upload" (local→remote) or "download" (remote→local)

    Returns:
        TransferResult with success status and message

    Raises:
        ValueError: If direction is invalid
        RuntimeError: If transfer fails
    """
    if direction not in ("upload", "download"):
        raise ValueError(f"direction must be 'upload' or 'download', got '{direction}'")

    try:
        async with conn.start_sftp_client() as sftp:
            if direction == "upload":
                # Local → Remote
                source_path = Path(source)
                if not source_path.exists():
                    raise RuntimeError(f"Source file not found: {source}")

                file_size = source_path.stat().st_size
                await sftp.put(source, destination)

                return TransferResult(
                    success=True,
                    message=f"Uploaded {source} → {destination}",
                    bytes_transferred=file_size,
                )
            else:
                # Remote → Local
                await sftp.get(source, destination)

                # Get transferred file size
                dest_path = Path(destination)
                file_size = dest_path.stat().st_size if dest_path.exists() else 0

                return TransferResult(
                    success=True,
                    message=f"Downloaded {source} → {destination}",
                    bytes_transferred=file_size,
                )
    except Exception as e:
        return TransferResult(
            success=False,
            message=f"Transfer failed: {e}",
            bytes_transferred=0,
        )


async def beam_transfer_remote_to_remote(
    source_conn: "asyncssh.SSHClientConnection",
    target_conn: "asyncssh.SSHClientConnection",
    source_path: str,
    target_path: str,
) -> TransferResult:
    """Transfer file from one remote host to another via local relay.

    Downloads file from source to local temp directory, then uploads to target.
    Cleans up temp file after transfer completes or fails.

    Args:
        source_conn: SSH connection to source host
        target_conn: SSH connection to target host
        source_path: Path to file on source host
        target_path: Path to destination on target host

    Returns:
        TransferResult with success status, message, and bytes transferred.

    Raises:
        RuntimeError: If download or upload fails.
    """
    import tempfile

    # Create temp file for relay
    temp_file = None

    try:
        # Download from source to temp
        with tempfile.NamedTemporaryFile(delete=False, prefix="scout_beam_") as tf:
            temp_file = Path(tf.name)

        try:
            async with source_conn.start_sftp_client() as source_sftp:
                await source_sftp.get(source_path, str(temp_file))
        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Download from source failed: {e}",
                bytes_transferred=0,
            )

        # Verify download succeeded
        if not temp_file.exists():
            return TransferResult(
                success=False,
                message="Download completed but temp file not found",
                bytes_transferred=0,
            )

        file_size = temp_file.stat().st_size

        # Upload from temp to target
        try:
            async with target_conn.start_sftp_client() as target_sftp:
                await target_sftp.put(str(temp_file), target_path)
        except Exception as e:
            return TransferResult(
                success=False,
                message=f"Upload to target failed: {e}",
                bytes_transferred=0,
            )

        return TransferResult(
            success=True,
            message=f"Transferred {source_path} → {target_path} (via relay)",
            bytes_transferred=file_size,
        )

    finally:
        # Clean up temp file
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except Exception:
                pass  # Best effort cleanup
