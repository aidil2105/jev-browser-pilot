#!/usr/bin/env bash
# Warn when the README has changed since the newest release without a version bump.
#
# The description PyPI shows for a release is the README inside the uploaded artifact, so a README
# edit that is never released leaves the project page quietly stating something else. This does not
# fail a build: it labels the divergence, and prints the command that checks the published text.
#
# Usage: scripts/check-description-sync.sh [repo-dir]
set -euo pipefail

cd "${1:-.}"

tag=$(git tag --list 'v*' --sort=-v:refname | head -1 || true)
if [ -z "$tag" ]; then
  echo "no release tag yet; nothing to compare against"
  exit 0
fi

released=$(git show "$tag:pyproject.toml" | sed -n 's/^version = "\(.*\)"/\1/p' | head -1)
current=$(sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml | head -1)

if git diff --quiet "$tag" -- README.md; then
  echo "README.md is unchanged since $tag; the published description still matches"
  exit 0
fi

if [ "$released" != "$current" ]; then
  echo "README.md changed since $tag, and the version moved from $released to $current"
  echo "the next release publishes the new description; nothing to do"
  exit 0
fi

echo "::warning::README.md changed since $tag but pyproject.toml still says $current."
echo "::warning::The PyPI page for $current keeps the old description until a new version is released."
echo "::warning::Bump the version, or ignore this while a release is in progress."
echo "Check the published text with: python scripts/verify-pypi-description.py $current"
exit 0
