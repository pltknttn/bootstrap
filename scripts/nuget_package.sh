#!/bin/bash

# Build NuGet packages from nuspec templates in ./nuget/
#
# Optional environment variables:
#   PACKAGE_VERSION     - Package version (default: 0.0.1)
#   PACKAGE_ID          - Overrides <id> in nuspec if set
#   PACKAGE_DESCRIPTION - Overrides <description> in nuspec if set
#   PACKAGE_AUTHOR      - Overrides <authors> in nuspec if set
#   PACKAGE_ICON        - Icon link (URL) or path (overrides <icon> if set)
#
# Output: {PACKAGE_ID|nuspec_id}.{PACKAGE_VERSION}.nupkg in project root

set -e

# Resolve paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The Python script handles the full build logic.
# We pass all overrides as CLI flags so the script is reusable standalone.
PY_SCRIPT="$SCRIPT_DIR/nuget_package.py"

echo "Building all NuGet packages from nuspec templates..."

python3 "$PY_SCRIPT" "$SCRIPT_DIR/../nuget" \
    --version      "${PACKAGE_VERSION:-0.0.1}" \
    --package-id   "${PACKAGE_ID:-}" \
    --description  "${PACKAGE_DESCRIPTION:-}" \
    --author       "${PACKAGE_AUTHOR:-}" \
    --icon-link    "${PACKAGE_ICON:-}"
