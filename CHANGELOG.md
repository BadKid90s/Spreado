# Changelog

## [1.1.0] - 2026-02-09

### 🚀 New Features
- **Agent Skill Support**: 🤖 Added a comprehensive "Spreado Skill" for AI Agents (Claude, Antigravity, Cursor, etc.). 
  - Automated installation guidance (Binary & Python).
  - Platform authentication and status verification workflows.
  - Video publishing assistance with metadata and scheduling.
- **Official Binary Downloads**: Added direct download links for pre-compiled binaries in `README.md` supporting:
  - **Windows**: x64, ARM64 (.exe)
  - **macOS**: Apple Silicon, Intel
  - **Linux**: x64, ARM64

### 📝 Documentation
- **README Overhaul**: 
  - Moved the Agent Skill section to the top for better visibility.
  - Added a professional download table for binaries.
  - List of supported AI Agents expanded to include OpenCode, Codex, Cursor, and Windsurf.
- **API Examples**: Added a working `example.py` in the Skill directory demonstrating Python API integration for DouYin uploads.

### 🔧 Improvements
- **Installation Guide**: Refined installation instructions to prioritize `uv` and direct binaries for better user experience.
- **Skill Structure**: Organized Skill resources into `SKILL.md`, `references/`, and `scripts/` for modularity and easier maintenance.

### 📦 Artifacts
- **Skill Package**: Released `spreado-skill.skill` – a ready-to-import package for AI assistants.
