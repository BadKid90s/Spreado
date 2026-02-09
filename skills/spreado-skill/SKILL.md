---
name: spreado-skill
description: Comprehensive tool for uploading short videos to multiple social media platforms (Douyin, Xiaohongshu, Kuaishou, Shipinhao). Handles installation via binary or Python, platform authentication, status verification, and automated video publishing.
---

# Spreado Skill

This skill provides all the necessary knowledge and workflows to install, configure, and use the `spreado` CLI tool for multi-platform video distribution.

## 🚀 Quick Start Workflow

### 1. Installation
Depending on the user's environment, choose the best installation method.
- **Trigger**: "Install spreado", "How to set up spreado?"
- **Guidance**: See [installation.md](references/installation.md) for binary download links and Python-based installations (`uv`, `pip`).

### 2. Authentication
Before first use, the user must log in to each target platform.
- **Trigger**: "Connect my Douyin account", "Login to platforms"
- **Action**: `spreado login <platform>`

### 3. Verification
Checking if platforms are ready for upload.
- **Trigger**: "Check status", "Are my cookies valid?"
- **Action**: `spreado verify all --parallel`

### 4. Uploading Content
Publishing videos with metadata.
- **Trigger**: "Post this video", "Upload to all platforms"
- **Action**: Use `spreado upload` with appropriate flags.
- **Reference**: See [cli_usage.md](references/cli_usage.md) for detailed command syntax.

## 🛠️ Scripts & Automation
The skill includes helper scripts to speed up development:
- **[example.py](scripts/example.py)**: A template showing how to use the Spreado Python API for programmatic uploads.

## 📋 Common Scenarios

### Case: Posting to multiple platforms simultaneously
1. Verify status for all platforms.
2. If any are invalid, request the user to run the login command.
3. Perform a parallel upload: `spreado upload all --video video.mp4 --title "My Title" --parallel`

### Case: Using without Python
Redirect users to download the official binaries for their OS (Windows/macOS/Linux).
See [installation.md](references/installation.md).

## 🔧 Advanced Features
- **Scheduling**: Post videos at a specific time using `--schedule`.
- **Custom Cookies**: Manage multiple accounts by specifying `--cookies` path.
- **API Access**: Use the Python API for programmatic integration (see project README).
