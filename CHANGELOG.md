# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.1] - 2026-07-20
### Added
- pytest test suite for the release script, covering version parsing, README and changelog updates, git state checks, and the end-to-end release flow. The tests live in `release.py` and run with `uv run --with-requirements release.py pytest release.py`.
- Type annotations on the release script and its tests, with [ruff](https://docs.astral.sh/ruff/) formatting/linting and [ty](https://docs.astral.sh/ty/) type checking enforced in CI.
