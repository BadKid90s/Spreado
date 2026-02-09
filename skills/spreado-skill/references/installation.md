# Spreado Installation Guide

Spreado can be installed using several methods depending on your environment and preference.

## 1. Direct Download (Easiest)
Download pre-compiled binaries for your OS. No Python environment required.

| OS | Download Links |
| :--- | :--- |
| **Windows** | [x64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-x64.exe) \| [ARM64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-windows-arm64.exe) |
| **macOS** | [Apple Silicon](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-arm64) \| [Intel](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-macos-x64) |
| **Linux** | [x64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-x64) \| [ARM64](https://github.com/BadKid90s/Spreado/releases/latest/download/spreado-linux-arm64) |

## 2. Using uv (Recommended for Python users)
Fastest way to install if you have [uv](https://github.com/astral-sh/uv) installed.
```bash
# Global install as a tool
uv tool install spreado

# Or add to current project
uv add spreado
```

## 3. Via pip
Standard Python installation.
```bash
pip install spreado
```

## 4. From Source (Development)
```bash
git clone https://github.com/BadKid90s/spreado.git
cd spreado
uv sync  # or pip install .
```
