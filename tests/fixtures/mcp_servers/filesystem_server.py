"""Deterministic local filesystem MCP fixture server.

The server is intentionally tiny and only operates inside the directory named
by MCP_FILESYSTEM_ROOT. It is safe to import without the optional MCP SDK; the
SDK is imported only when ``create_server`` or ``main`` is called.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT_ENV_VAR = "MCP_FILESYSTEM_ROOT"
ROOT_MARKER_FILE = ".mcp_fixture_root"
SERVER_NAME = "fixture-filesystem"
MAX_READ_BYTES = 64 * 1024


class FixtureFilesystemError(ValueError):
    """Raised when a fixture filesystem operation is not allowed."""


def fixture_root_from_env(
    env: Mapping[str, str] | None = None,
) -> Path:
    """Return the configured fixture root directory."""
    source = os.environ if env is None else env
    raw_root = source.get(ROOT_ENV_VAR)

    if not isinstance(raw_root, str) or not raw_root.strip():
        raise FixtureFilesystemError(f"{ROOT_ENV_VAR} must be set")

    return validate_fixture_root(raw_root)


def validate_fixture_root(root: str | Path) -> Path:
    """Return a fixture root only when it has the marker file."""
    try:
        root_path = Path(root).resolve(strict=True)
    except OSError as exc:
        raise FixtureFilesystemError(
            f"{ROOT_ENV_VAR} must point to an existing directory"
        ) from exc

    if not root_path.is_dir():
        raise FixtureFilesystemError(f"{ROOT_ENV_VAR} must point to a directory")

    marker_path = root_path / ROOT_MARKER_FILE
    if not marker_path.is_file() or is_link_or_reparse_point(marker_path):
        raise FixtureFilesystemError(
            f"{ROOT_ENV_VAR} must contain {ROOT_MARKER_FILE}"
        )

    return root_path


def validate_relative_path(path: str) -> Path:
    """Return a safe relative path supplied by a fixture tool caller."""
    if not isinstance(path, str) or not path.strip():
        raise FixtureFilesystemError("path must be a non-empty string")

    requested_path = Path(path)
    if requested_path.is_absolute() or requested_path.drive or requested_path.root:
        raise FixtureFilesystemError("path must be relative to the fixture root")

    if any(part == ".." for part in requested_path.parts):
        raise FixtureFilesystemError("path traversal is not allowed")

    if requested_path.parts == (ROOT_MARKER_FILE,):
        raise FixtureFilesystemError("fixture marker file is reserved")

    return requested_path


def is_link_or_reparse_point(path: Path) -> bool:
    """Return whether a path is a symlink or Windows reparse point."""
    if path.is_symlink():
        return True

    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True

    reparse_point = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if reparse_point:
        try:
            attributes = path.stat(follow_symlinks=False).st_file_attributes
        except (AttributeError, OSError):
            return False
        return bool(attributes & reparse_point)

    return False


def reject_symlinks(root: Path, relative_path: Path) -> None:
    """Reject any symlink or reparse point in the requested path."""
    current_path = root
    for part in relative_path.parts:
        current_path = current_path / part
        if is_link_or_reparse_point(current_path):
            raise FixtureFilesystemError(
                "symlinks and reparse points are not allowed"
            )


def normalized_relative_path(root: Path, target_path: Path) -> str:
    """Return a normalized POSIX relative path for trace output."""
    return target_path.relative_to(root).as_posix()


def resolve_fixture_path(root: str | Path, path: str) -> Path:
    """Resolve a user path under root, rejecting traversal and symlinks."""
    root_path = validate_fixture_root(root)
    requested_path = validate_relative_path(path)
    reject_symlinks(root_path, requested_path)

    target_path = (root_path / requested_path).resolve(strict=False)
    try:
        target_path.relative_to(root_path)
    except ValueError as exc:
        raise FixtureFilesystemError(
            "path must stay within the fixture root"
        ) from exc

    return target_path


def read_fixture_file(root: str | Path, path: str) -> dict[str, Any]:
    """Read a UTF-8 text file from the fixture root."""
    root_path = validate_fixture_root(root)
    target_path = resolve_fixture_path(root, path)
    if not target_path.is_file():
        raise FixtureFilesystemError("file does not exist")

    try:
        if target_path.stat().st_size > MAX_READ_BYTES:
            raise FixtureFilesystemError("file is too large to read")
        content = target_path.read_text(encoding="utf-8")
    except FixtureFilesystemError:
        raise
    except UnicodeDecodeError as exc:
        raise FixtureFilesystemError("file is not valid UTF-8 text") from exc
    except OSError as exc:
        raise FixtureFilesystemError("file could not be read") from exc

    return {
        "path": normalized_relative_path(root_path, target_path),
        "content": content,
    }


def delete_fixture_file(root: str | Path, path: str) -> dict[str, Any]:
    """Delete one regular file from the fixture root."""
    root_path = validate_fixture_root(root)
    target_path = resolve_fixture_path(root, path)
    if not target_path.is_file():
        raise FixtureFilesystemError("file does not exist")

    try:
        target_path.unlink()
    except OSError as exc:
        raise FixtureFilesystemError("file could not be deleted") from exc

    return {
        "path": normalized_relative_path(root_path, target_path),
        "deleted": True,
    }


def create_server(root: str | Path | None = None) -> Any:
    """Create the FastMCP fixture server."""
    fixture_root = (
        fixture_root_from_env()
        if root is None
        else validate_fixture_root(root)
    )

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP(SERVER_NAME)

    @mcp.tool()
    def read_file(path: str) -> dict[str, Any]:
        """Read a UTF-8 text file from the fixture root."""
        return read_fixture_file(fixture_root, path)

    @mcp.tool()
    def delete_file(path: str) -> dict[str, Any]:
        """Delete one regular file from the fixture root."""
        return delete_fixture_file(fixture_root, path)

    return mcp


def main() -> None:
    """Run the fixture server over stdio."""
    create_server().run()


if __name__ == "__main__":
    main()
