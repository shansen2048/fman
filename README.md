# fman

Cross-platform, dual-pane file manager implemented in Python and PyQt5 with a
plugin-first architecture and an fbs-based build/release pipeline.

## Highlights

- Dual-pane UI with a Qt-based frontend and a model/view backend.
- Plugin system with built-in and user/third-party plugins.
- Themed UI and configurable key bindings.
- Cross-platform packaging for macOS, Windows, and multiple Linux distros.

## Architecture at a Glance

Runtime entrypoint:
- `src/main/python/fman/main.py` boots the `ApplicationContext` and starts the Qt event loop.

Application context and orchestration:
- `src/main/python/fman/impl/application_context.py` wires together the main
  window, controllers, metrics, plugins, and platform-specific integrations.

Core services and abstractions:
- Model and file system abstractions live under `src/main/python/fman/impl/model`
  and `src/main/python/fman/impl/plugins/mother_fs.py`.
- UI and view logic is in `src/main/python/fman/impl/view` and
  `src/main/python/fman/impl/widgets.py`.

Plugins and resources:
- Built-in plugins and resources ship in `src/main/resources/base/Plugins/Core`.
- Plugin discovery loads built-ins, third-party plugins, and user plugins from
  the data directory (see `find_plugin_dirs` in
  `src/main/python/fman/impl/plugins/discover.py`).

Build and packaging:
- `build.py` is the CLI entrypoint for the fbs build system and delegates to
  `src/build/python/build_impl/*` for platform-specific steps.

## Repository Layout

- `src/main/python/`: Application source (runtime, UI, plugins, utilities).
- `src/main/resources/`: Bundled resources (themes, key bindings, core plugin).
- `src/build/`: Build settings and platform-specific packaging logic.
- `src/unittest/python/`: Unit tests (Python `unittest`).
- `src/integrationtest/python/`: Integration tests.
- `requirements/`: Per-OS Python dependency sets.
- `conf/` and `src/sign/`: Signing keys and certificates for releases.

## Development Setup

Prerequisites:
- Python 3.9.

Install dependencies for your OS (examples):

```bash
pip install -Ur requirements/ubuntu.txt
```

Run in development mode:

```bash
python build.py run
```

List available build commands:

```bash
python build.py
```

## Tests

Tests use the standard library `unittest` framework. Because sources are not
installed as a package in development, set `PYTHONPATH` to include the source
trees.

Unit tests:

```bash
PYTHONPATH=src/main/python:src/unittest/python \
  python -m unittest discover -s src/unittest/python
```

Integration tests:

```bash
PYTHONPATH=src/main/python:src/unittest/python:src/integrationtest/python \
  python -m unittest discover -s src/integrationtest/python
```

## Release and Packaging

Releases are orchestrated through `build.py` and the fbs build system. The
platform-specific packaging/signing steps are implemented in
`src/build/python/build_impl`.

For platform-specific signing and packaging prerequisites, see `install.txt`.

## Notes on Signing Material

This repository contains certificates and keys used for packaging/signing
(`conf/`, `src/sign/`). Treat these as sensitive assets and restrict access to
authorized release engineers.
