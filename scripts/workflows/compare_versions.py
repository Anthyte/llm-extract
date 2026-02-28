#!/usr/bin/env python3
"""
Compare two versions to check if the new version is greater than the old one
Usage: compare_versions.py <new_version> <old_version>
"""

import sys
from packaging.version import Version


def main():
    if len(sys.argv) != 3:
        print("Usage: compare_versions.py <new_version> <old_version>", file=sys.stderr)
        sys.exit(1)
    
    new_version_str = sys.argv[1]
    old_version_str = sys.argv[2]
    
    try:
        new_version = Version(new_version_str)
        old_version = Version(old_version_str)
        
        if new_version > old_version:
            print("true")
        else:
            print("false")
    except Exception as e:
        print(f"ERROR: Failed to compare versions: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()