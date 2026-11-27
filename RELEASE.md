# Cutting an ELI Creation Station release

Maintainer: **ShadowESC95/ELI_Creation_Station** on GitHub. The process is ELI Legal's
(docs/PACKAGING.md).

1. **Bump the version** in `src/eli_creation/__init__.py` (pyproject reads it). Write what changed
   in `packaging/release_notes.md`.
2. **Bring the reused code up to date**: `python3 scripts/sync_reused.py`, then
   `python3 scripts/sync_reused.py --check` (merge any adapted file whose original changed), and
   `python3 scripts/build_licence.py` if ELI v3's EULA changed.
3. **Check it locally**:

   ```bash
   .venv/bin/python -m pytest
   .venv/bin/ruff check src tests
   .venv/bin/mypy
   .venv/bin/eli-creation selftest
   python3 scripts/check_release.py --check
   ```

4. **Dry run**: Actions → **release** → **Run workflow** builds and tests every installer and
   publishes nothing.
5. **Tag**: `git tag -a v0.1.0 -m "ELI Creation Station 0.1.0" && git push origin v0.1.0`. The
   workflow attaches every installer, the SBOM and `SHA256SUMS` to a **draft** release for a person
   to publish.

The builds are not signed until the publisher's certificates are set (`packaging/windows/build.ps1`,
`packaging/macos/build.sh`).
