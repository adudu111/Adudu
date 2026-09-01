# Security Policy

## Data model

adudu is a **local, offline-first** application. The verified data model is:

- All content is stored in a **local SQLite database** created under your Windows profile at
  `%APPDATA%\CyberGlossary\` (default), overridable with the `CYBERGLOSSARY_DATA_DIR`
  environment variable.
- Settings, backups, and the database live only on your machine.

## Network & telemetry

adudu makes **no network requests**. The application source references no HTTP client,
socket, or analytics/telemetry libraries, and there is no account system or cloud sync.
The global lookup hotkey reads selected text **only** to resolve it against your local
profile; it is not logged or transmitted.

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability. Instead, report it
privately to the maintainers. Include:

- a description of the issue,
- the affected adudu version and OS,
- steps to reproduce,
- any relevant artifacts (redacted) or a proof-of-concept.

We will acknowledge and respond as soon as possible.

## Data safety note

Because adudu stores everything locally and does not sync, you are responsible for
backing up your data. Use the built-in **Backup**/**Export** features (Settings / tray /
File) and store backups outside the application folder.
