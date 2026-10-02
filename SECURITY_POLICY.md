# Application security boundaries

Technical guidance only. [SECURITY.md](SECURITY.md) retains the reporting guidance; this file does not invent a private reporting channel, contact address, response SLA or repository policy guarantee. Confirm an available private channel with the maintainer before transmitting sensitive vulnerability details.

- Keep credentials, private databases, Book text, model weights and Live private assets out of public source/artifacts
- Book/StudyMate/Live/ChatContextVault remain separate authorities; capture and voice input remain explicit and consent-scoped
- Hosted synthetic acceptance is not user-device, provider, signing, distribution-license or production-security acceptance
- Current acceptance and unresolved gates are in [CURRENT_STATE](docs/CURRENT_STATE.md) and the [checkpoint](docs/GOVERNANCE_CHECKPOINT_20261002.md)
- Stop older processes and take a private local backup before schema-v2 migration; no mixed-version access or in-place downgrade

Repository license, branch protection, retention, contact/SLA and release decisions are not changed by this technical reconciliation. The previous file only stated that it was historical; it supplied no active application policy.
