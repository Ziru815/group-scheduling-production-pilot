# Database migrations

For local demo, `AUTO_CREATE_TABLES=true` creates the SQLModel schema. A reviewed initial
migration is included for PostgreSQL. Apply it with:

```bash
alembic upgrade head
```

Future generated migrations must be reviewed on PostgreSQL, especially the circular references
`Session.organiser_participant_id` and `Session.confirmed_combination_id`, unique constraints,
enum columns and create/drop order. Commit the reviewed migration; never autogenerate against
SQLite and assume it is production-equivalent.
