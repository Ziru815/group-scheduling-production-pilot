# Post-assessment shutdown checklist

Run this after grading is complete. The shutdown owner records dates and
pass/fail only; never copy secrets or personal data into this file.

## Ownership

- Shutdown owner: `TBD`
- Planned shutdown date: `TBD`
- Actual shutdown date: `TBD`

## Preserve only required evidence

- [ ] Confirm the course retention rules with the team.
- [ ] Export only required screenshots, demo video, redacted test evidence, and source tags.
- [ ] Take a final encrypted PostgreSQL dump only if retention is necessary.
- [ ] Verify any retained dump can list tables, then store its recovery key separately.
- [ ] Delete unnecessary local dumps and browser downloads containing participant data.

## Revoke credentials

- [ ] Rotate/delete the Google OAuth client secret or delete the assessment OAuth client.
- [ ] Remove all assessment redirect URIs and test users if the OAuth project remains.
- [ ] Revoke the OneMap token or change the account password if dedicated credentials were used.
- [ ] Remove Railway project/account tokens and any GitHub deploy keys.
- [ ] Confirm no populated `.env` or credential export remains on team machines.

## Stop billable infrastructure

- [ ] Suspend/delete the Railway application service.
- [ ] Delete the Railway PostgreSQL service after required backup retention is confirmed.
- [ ] Remove volumes, preview environments, and unused services.
- [ ] Check Workspace Usage and Billing for remaining running resources.
- [ ] Cancel/downgrade the Railway plan if it is no longer needed.
- [ ] Verify the next billing page shows no unexpected active workload.

## Close collaboration surfaces

- [ ] Remove temporary collaborators from Railway and Google Cloud.
- [ ] Archive the private GitHub repository if the course rules allow it.
- [ ] Keep protected release tags and the redacted runbooks with the final submission.
- [ ] Mark this checklist complete with the shutdown owner's role and date.

Final status: `NOT STARTED`
