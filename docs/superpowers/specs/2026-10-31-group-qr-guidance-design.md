# Group QR guidance design

## Intent

Make the existing invitation QR code self-explanatory for an organiser who wants everyone nearby to join the same Session without sending the link one person at a time.

## Chosen experience

- Keep the QR control collapsed by default so the normal invitation page stays compact.
- Keep the existing `Show QR code` / `Hide QR code` controls and the exact invitation URL encoded in the QR.
- Replace the vague expanded-panel caption with: `Show this code so people nearby can scan and join. For online sharing, copy the invitation message.`
- Scanning continues to open the normal invitation flow. It does not bypass Google sign-in, Session access rules, or availability submission.

## Approaches considered

1. **Expanded-panel guidance (chosen):** explains the group-scan and online-sharing use cases exactly where the organiser needs them, without adding permanent page clutter.
2. **Always-visible instructions:** easier to discover, but makes every invitation screen busier even when QR sharing is not used.
3. **Dedicated full-screen presentation mode:** stronger for large rooms, but adds navigation, responsive and accessibility work beyond the requested clarification.

## Constraints and non-goals

- No backend, database, authentication, invitation-token, or SRS workflow changes.
- No external QR service, analytics, network request, or new dependency.
- Do not imply that scanning automatically admits a user; normal sign-in and joining still apply.
- Preserve raw-link copying, complete-message copying, native sharing, QR accessibility, and mobile layout.

## Verification

- A component test must fail before the copy changes and pass afterwards.
- The full frontend tests, lint, and production build must pass.
- On the deployed organiser response page, expanding the QR must show the new guidance while the QR and invitation link continue to work.
