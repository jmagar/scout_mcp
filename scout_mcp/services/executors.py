"""SSH command executors for file operations."""

import shlex
from typing import TYPE_CHECKING

from scout_mcp.models import CommandResult

if TYPE_CHECKING:
    import asyncssh


async def stat_path(conn: "asyncssh.SSHClientConnection", path: str) -> str | None:
    """Determine if path is a file, directory, or doesn't exist.

    Returns:
        'file', 'directory', or None if path doesn't exist.
    """
    result = await conn.run(f'stat -c "%F" {shlex.quote(path)} 2>/dev/null', check=False)

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
            containers.append({
                "name": parts[0],
                "status": parts[1],
                "image": parts[2],
            })

    return containers


async def docker_inspect(
    conn: "asyncssh.SSHClientConnection",
    container: str,
) -> bool:
    """Check if Docker container exists.

    Returns:
        True if container exists, False otherwise.
    """
    cmd = f"docker inspect --format '{{{{.Name}}}}' {shlex.quote(container)} 2>/dev/null"

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
            pools.append({
                "name": parts[0],
                "size": parts[1],
                "alloc": parts[2],
                "free": parts[3],
                "cap": parts[4],
                "health": parts[5],
            })
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
        cmd = f"zfs list -H -r -o name,used,avail,refer,mountpoint {shlex.quote(pool)} 2>/dev/null"
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
            datasets.append({
                "name": parts[0],
                "used": parts[1],
                "avail": parts[2],
                "refer": parts[3],
                "mountpoint": parts[4],
            })
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
            f"zfs list -H -t snapshot -o name,used,creation "
            f"2>/dev/null | tail -{limit}"
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
            snapshots.append({
                "name": parts[0],
                "used": parts[1],
                "creation": parts[2],
            })
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
