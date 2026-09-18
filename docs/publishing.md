# Publishing

The project is on PyPI: `pip install jev-browser-pilot` resolves, and `0.1.1` was the first version
uploaded. This is how the lane works, and what it takes to set it up again from scratch.

## One-time setup on PyPI (about two minutes, needs the account)

1. Sign in to <https://pypi.org> and open **Account settings → Publishing**.
2. Under *Add a new pending publisher*, choose **GitHub** and fill in:

   | field | value |
   |---|---|
   | PyPI project name | `jev-browser-pilot` |
   | owner | `aidil2105` |
   | repository name | `jev-browser-pilot` |
   | workflow name | `publish.yml` |
   | environment name | `pypi` |

3. Save. That is the whole setup: it authorises the `publish` job in
   `.github/workflows/publish.yml` to upload as this project, and it is the only step that
   cannot be done from the repository.

## Publishing

The workflow runs when a release is published, or by hand from the Actions tab
(*publish → Run workflow*). It builds the wheel and the sdist, installs each into a clean
environment and runs `jev-pilot selftest` against them, and only then uploads. A build that does
not install does not publish.

By hand from a checkout, with a token, if that is ever preferable:

```
uv build
UV_PUBLISH_TOKEN=pypi-... uv publish
```

The token goes in the shell environment for that one command, not into a file in this repository.

## After the first publish

Done on 2026-09-18: `0.1.1` was uploaded by this workflow through the pending publisher above. Two
things that are easy to get wrong later:

- **The description on PyPI is the README inside the uploaded artifact.** A documentation change
  does not reach the project page until a new version is uploaded. `0.1.1` was published with an
  install section that said the package was not on PyPI, and `0.2.1` exists only because a citation
  fix landed after `0.2.0` was tagged, which is why `0.1.2` exists as well.
- **Check it rather than assume it.** `python scripts/verify-pypi-description.py <version>` fetches
  the published description and diffs it against the README in that version's own commit, line
  endings aside. CI also carries a warning job (`description-sync`) that fires when README.md changes
  without a version bump, so the divergence is labelled instead of discovered later.
- **Later releases need nothing new on PyPI.** A new tag, a version bump in `pyproject.toml` and a
  published GitHub release are enough; the trusted publisher entry already covers them. PyPI
  refuses a version that already exists, so bump every time.
- **A resolver may still offer the previous version right after an upload.** uv, for instance,
  caches index pages: `uv pip install jev-browser-pilot` returned the older release for a couple of
  minutes while `python -m pip` resolved the new one, and `uv pip install --refresh` agreed with
  pip. Check with a cache busting request (`curl` with a random query string) before believing a
  release failed to land.

## Versioning

`pyproject.toml` holds the version, and the git tag matches it (`v0.1.0`, `v0.1.1`, ...). PyPI
refuses a second upload of a version that already exists, so a version bump is part of every
release that changes the package.
