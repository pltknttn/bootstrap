#!/usr/bin/env python3
"""Build NuGet packages from nuspec templates.

Callable directly from the console or via ``nuget_package.sh``.

Examples
--------
    python3 nuget_package.py nuget/bootstrap.nuspec
    python3 nuget_package.py nuget/ --version 6.0.0-alpha.1
    python3 nuget_package.py nuget/bootstrap.nuspec --package-id my.bootstrap --version 1.0.0
"""

import argparse
import re
import shutil
import zipfile
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def replace_tag(text, tag, value):
    """Replace the first ``<tag>…</tag>`` occurrence with ``<tag>value</tag>``."""
    pattern = rf"<{tag}>[\s\S]*?</{tag}>"
    return re.sub(pattern, f"<{tag}>{value}</{tag}>", text, count=1)


def resolve_project_root(explicit_root):
    """Return the project-root :class:`~pathlib.Path`.

    When *explicit_root* is given it is used as-is; otherwise the
    grandparent of this script's own directory (i.e. the repo root)
    is returned.
    """
    if explicit_root:
        return Path(explicit_root).resolve()
    return Path(__file__).resolve().parent.parent


def handle_icon(icon_link, project_root):
    """Download or copy an icon and return ``(icon_name, nuspec_content)``.

    *icon_link* may be an ``http(s)://`` URL (downloaded to the project
    root) or a local file path (copied to the project root).

    Returns ``(None, content)`` when *icon_link* is empty or the icon
    could not be resolved.
    """
    if not icon_link:
        return None, None

    if icon_link.startswith(("http://", "https://")):
        icon_name = icon_link.rstrip("/").split("/")[-1]
        icon_dest = project_root / icon_name
        try:
            urllib.request.urlretrieve(icon_link, str(icon_dest))
        except Exception as exc:
            print(f"Warning: failed to download icon from {icon_link}: {exc}")
            return None, None
    else:
        icon_src = Path(icon_link)
        if icon_src.is_file():
            icon_name = icon_src.name
            shutil.copy(str(icon_src), str(project_root / icon_name))
        else:
            print(f"Warning: icon file not found at {icon_link}")
            return None, None

    print(f"Icon '{icon_name}' placed at project root.")
    return icon_name, icon_name


def collect_file_entries(content, project_root):
    """Return ``[(arcname, src_path)]`` for every ``<file>`` entry.

    Glob patterns (``*``) are expanded via :meth:`pathlib.Path.glob`;
    explicit (non-glob) paths are resolved directly.  The returned list
    is de-duplicated so that the same *arcname* is never produced twice.
    """
    file_pattern = r'<file\s+src="([^"]+)"\s+target="([^"]*)"\s*/>'
    entries = []
    seen = set()

    for match in re.finditer(file_pattern, content):
        src_pattern = match.group(1).replace("\\", "/")
        target = match.group(2).replace("\\", "/")

        if "*" in src_pattern:
            for src_file in project_root.glob(src_pattern):
                if src_file.is_file():
                    arcname = f"{target}/{src_file.relative_to(project_root)}"
                    if arcname not in seen:
                        entries.append((arcname, src_file))
                        seen.add(arcname)
        else:
            src_file = project_root / src_pattern
            if src_file.is_file():
                arcname = f"{target}/{src_file.name}" if target else src_file.name
                if arcname not in seen:
                    entries.append((arcname, src_file))
                    seen.add(arcname)

    return entries


# ---------------------------------------------------------------------------
# Core build logic
# ---------------------------------------------------------------------------

def build_package(nuspec_path, args):
    """Build one ``.nupkg`` from *nuspec_path* using parsed CLI *args*."""
    project_root = resolve_project_root(args.project_root)
    nuspec_file = Path(nuspec_path)

    print(f"Building package from {nuspec_file.name}...")

    version = args.version
    package_id = args.package_id or ""
    description = args.description or ""
    author = args.author or ""
    icon_link = args.icon_link or ""

    # Read nuspec template
    content = nuspec_file.read_text()

    # Determine effective package id (override or from nuspec)
    id_match = re.search(r"<id>([\s\S]*?)</id>", content)
    default_id = id_match.group(1).strip() if id_match else "package"
    effective_id = package_id if package_id else default_id

    # Apply parameter overrides
    content = replace_tag(content, "version", version)
    if package_id:
        content = replace_tag(content, "id", package_id)
    if description:
        content = replace_tag(content, "description", description)
    if author:
        content = replace_tag(content, "authors", author)

    # Handle icon if specified (URL or local path)
    icon_name, _ = handle_icon(icon_link, project_root)
    if icon_name:
        content = replace_tag(content, "icon", icon_name)

    # Output path
    output_file = project_root / f"{effective_id}.{version}.nupkg"

    # Build the .nupkg (ZIP archive)
    with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add icon-link icon at root first (takes precedence over nuspec <file> entries)
        if icon_name:
            icon_file = project_root / icon_name
            if icon_file.exists():
                zf.write(str(icon_file), icon_name)

        # Add the nuspec as package metadata
        zf.writestr(f"{effective_id}.nuspec", content)

        # Collect and write <file> entries (skip icon if already added via --icon-link)
        entries = collect_file_entries(content, project_root)
        added = {icon_name} if icon_name else set()

        for arcname, src_file in entries:
            if arcname not in added:
                zf.write(str(src_file), arcname)
                added.add(arcname)

    print(f"Created {output_file}")
    return output_file


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Build NuGet packages from nuspec templates.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "nuspec",
        help="Path to a .nuspec file, or a directory containing .nuspec files",
    )
    parser.add_argument(
        "--version", default="0.0.1",
        help="Package version (default: 0.0.1)",
    )
    parser.add_argument(
        "--package-id", default="",
        help="Override <id> in the nuspec",
    )
    parser.add_argument(
        "--description", default="",
        help="Override <description> in the nuspec",
    )
    parser.add_argument(
        "--author", default="",
        help="Override <authors> in the nuspec",
    )
    parser.add_argument(
        "--icon-link", default="",
        help="Icon link: URL to download, or local file path",
    )
    parser.add_argument(
        "--project-root", default=None,
        help="Project root directory (default: parent of script dir)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    nuspec_path = Path(args.nuspec)

    if nuspec_path.is_dir():
        nuspec_files = sorted(nuspec_path.glob("*.nuspec"))
    elif nuspec_path.is_file():
        nuspec_files = [nuspec_path]
    else:
        raise FileNotFoundError(f"Path not found: {nuspec_path}")

    if not nuspec_files:
        print(f"No .nuspec files found in {nuspec_path}")
        return

    for nuspec in nuspec_files:
        build_package(nuspec, args)

    print("Done!")


if __name__ == "__main__":
    main()
