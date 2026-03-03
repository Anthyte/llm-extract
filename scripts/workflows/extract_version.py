#!/usr/bin/env python3
"""
Extract version from pyproject.toml
"""

import sys
import tomllib
from pathlib import Path


def main():
    pyproject_path = Path("pyproject.toml")
    
    if not pyproject_path.exists():
        print("ERROR: pyproject.toml not found", file=sys.stderr)
        sys.exit(1)
    
    try:
        with open(pyproject_path, "rb") as f:
            pyproject_data = tomllib.load(f)
        
        version = pyproject_data["project"]["version"]
        print(version)
        return version
    except Exception as e:
        print(f"ERROR: Failed to extract version: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()