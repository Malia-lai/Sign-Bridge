# Release checklist

Use this checklist for each agent service release. A release is not complete until its
version, changelog entry, and Git tag agree.

## Prepare

- [ ] Confirm the intended changes are merged into `main` and the working tree is clean.
- [ ] Run the CI checks in `.github/workflows/ci.yml` and review their results.
- [ ] Choose the next [Semantic Versioning](https://semver.org/) version.
- [ ] Update `app/main.py`'s FastAPI version and the version heading in `CHANGELOG.md`.
- [ ] Add a dated changelog summary covering user-visible changes and migration notes.
- [ ] Review `README.md`, `.env.example`, API docs, and Docker instructions for accuracy.

## Publish

- [ ] Commit the version and changelog updates.
- [ ] Create an annotated tag from the release commit: `git tag -a v<VERSION> -m "Sign-Bridge Agent v<VERSION>"`.
- [ ] Push the commit and tag: `git push origin main && git push origin v<VERSION>`.
- [ ] Confirm the tag points to the intended commit and the CI workflow succeeds for it.
- [ ] Record deployment details and any follow-up work in the release notes.

## Rollback

- [ ] If the release must be withdrawn, document the reason and publish a corrective version.
- [ ] Do not move or reuse a published version tag.
