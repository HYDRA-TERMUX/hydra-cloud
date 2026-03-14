# Contributing to HYDRA

Thank you for considering a contribution! Here's how to get involved.

---

## Ways to Contribute

- 🐛 **Bug reports** — open an issue using the Bug Report template
- 💡 **Feature requests** — open an issue using the Feature Request template
- 🔧 **Pull requests** — code fixes, improvements, documentation

---

## Pull Request Process

1. **Fork** the repository on GitHub
2. **Create a branch**: `git checkout -b feature/your-feature-name`
3. **Make changes** — keep commits focused and descriptive
4. **Test on a real Android device** with Termux before submitting
5. **Open a PR** with a clear description of what changed and why

---

## Code Style

- Shell scripts: follow the existing style; use the defined helpers (`ok()`, `err()`, `info()`, `warn()`, `section()`)
- Python: PEP 8 compliant, readable variable names
- Comments in English

---

## Reporting Bugs

Include in your issue:
- Android version and device model
- Termux version (`termux-info | head -5`)
- Last 30 lines of `~/.hydra/hydra.log`
- Exact steps to reproduce

---

## Areas Open for Contribution

- Optional password protection / HTTP basic auth
- QR code display for easy URL sharing on mobile
- Directory/folder browsing support
- HTTPS via self-signed certificate
- Download progress bar
- Dark/light theme toggle
- Configurable port via environment variable
