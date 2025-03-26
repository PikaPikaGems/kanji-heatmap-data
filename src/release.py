#!/usr/bin/env python3

import os
import tarfile
import argparse
import sys
import subprocess
import constants as const

def create_archive() -> bool:
    
    archive_path = os.path.join(const.dir_releases, const.archive_file)

    for output_file in const.output_files:
        file_path = os.path.join(const.dir_out, output_file)
        if not os.path.isfile(file_path):
            print(f"Error: Required output file not found: {file_path}")
            return False

    with tarfile.open(archive_path, mode="w:gz") as tar:
        for output_file in const.output_files:
            file_path = os.path.join(const.dir_out, output_file)
            tar.add(file_path, arcname=output_file)

    print(f"Successfully created archive: {archive_path}")
    return True

def create_git_tag(version: str) -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, capture_output=True)

        tag_message = f"Release {version}"
        subprocess.run(
            ["git", "tag", "-a", version, "-m", tag_message],
            check=True,
            capture_output=True,
            text=True
        )

        subprocess.run(
            ["git", "push", "origin", version],
            check=True,
            capture_output=True,
            text=True,
        )

        print(f"Successfully created and pushed tag: {version}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to create or push tag - {e}")
        print(f"Git output: {e.output}")
        return False
    except FileNotFoundError:
        print("Error: Git is not installed or not found in PATH")
        return False


def validate_version(version: str):
    if not version.startswith("v"):
        version = "v" + version

    return version

def main():
    parser = argparse.ArgumentParser(description="Prepare release (archive output files, create/push tag)")
    parser.add_argument(
        "version", type=validate_version, help="Version number (e.g. v0.9, 1.0.1)"
    )

    args = parser.parse_args()

    archive_success = create_archive()
    if not archive_success:
        sys.exit(1)

    tag_success = create_git_tag(args.version)

    sys.exit(0 if tag_success else 1)

if __name__ == "__main__":
    main()
