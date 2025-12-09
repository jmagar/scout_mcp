"""Shell command safety utilities."""

import shlex


def quote_path(path: str) -> str:
    """Safely quote a path for shell commands.

    Args:
        path: File system path to quote

    Returns:
        Shell-safe quoted path
    """
    return shlex.quote(path)


def quote_arg(arg: str) -> str:
    """Safely quote a shell argument.

    Args:
        arg: Argument to quote

    Returns:
        Shell-safe quoted argument
    """
    return shlex.quote(arg)
