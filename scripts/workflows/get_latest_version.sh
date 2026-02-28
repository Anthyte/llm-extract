#!/bin/bash
# Get the latest release version from git tags

set -euo pipefail

LATEST_TAG=$(git tag --sort=-v:refname | head -n 1)

if [ -z "$LATEST_TAG" ]; then
    echo "0.0.0"
    echo "No previous releases found" >&2
else
    # Remove 'v' prefix if present
    LATEST_VERSION=${LATEST_TAG#v}
    echo "$LATEST_VERSION"
fi