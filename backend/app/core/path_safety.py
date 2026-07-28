"""Path-containment helpers for artifact and upload access."""

from pathlib import Path
from typing import Union

PathLike = Union[str, Path]


def resolve_path_within(base_dir: PathLike, target_path: PathLike) -> Path:
    """Resolve a target path and require it to stay inside a resolved base directory."""
    resolved_base = Path(base_dir).resolve(strict=False)
    resolved_target = Path(target_path).resolve(strict=False)

    try:
        is_child = resolved_target.is_relative_to(resolved_base)
    except ValueError:
        is_child = False

    if not is_child:
        raise ValueError(f"Path '{resolved_target}' is outside '{resolved_base}'.")

    return resolved_target
