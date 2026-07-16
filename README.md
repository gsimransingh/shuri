# Shuri

Shuri is a modern workstation diagnostics toolkit for IT professionals. It is currently
in early development, with an initial command for collecting a concise local system
snapshot.

## Requirements

- Python 3.12 or newer

## Installation

Create and activate a virtual environment, then install the project in editable mode:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Usage

Show operating system, processor, memory, disk, uptime, and Python information:

```powershell
shuri system-info
```

During development, the same command can be run without relying on a globally installed
launcher:

```powershell
python -m shuri system-info
```

The command only reads local system information; it does not modify workstation settings.

## Development

Run the test suite and lint checks:

```powershell
pytest
ruff check .
```
