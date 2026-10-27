# Production Pilot Implementation Roadmap

The approved design is implemented in this order. Each plan produces a reviewable, independently testable result.

1. `2026-10-27-production-foundation-implementation.md` — reproducible baseline, production configuration, same-origin container, CI and Railway skeleton.
2. `2026-10-27-google-login-hardening-implementation.md` — browser-bound Google OpenID Connect with PKCE/nonce and production-safe sessions.
3. `2026-10-27-real-venue-catalog-implementation.md` — real data.gov.sg ingestion, verified public venue catalogue, migration and source display.
4. `2026-10-27-public-pilot-release-implementation.md` — live provider checks, Railway deployment, multi-account rehearsal, backup and shutdown runbook.

Every phase must keep the existing local demo usable. A phase is merged only after its automated checks pass and its manual acceptance item is recorded.

