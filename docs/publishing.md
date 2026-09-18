# Publishing

The package is not on PyPI yet, which is why the README installs from the repository. This is
what publishing takes, and it is deliberately set up so that no API token is ever stored in the
repository or pasted into a chat.

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

- `pip install jev-browser-pilot` starts working, so the README's install section should be
  shortened back to the plain form. The plain form is deliberately not there yet: instructions
  that do not resolve are worse than longer ones that do.
- The `pypi` environment URL in the workflow gives the release a link on the Actions tab.
- Later releases only need a new tag and a published GitHub release. The PyPI publisher entry
  already trusts this repository and workflow.

## Versioning

`pyproject.toml` holds the version, and the git tag matches it (`v0.1.0`, `v0.1.1`, ...). PyPI
refuses a second upload of a version that already exists, so a version bump is part of every
release that changes the package.
