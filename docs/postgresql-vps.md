# PostgreSQL deployment on the VPS

RepairBase uses ordinary PostgreSQL 16. Supabase is not required for the new
`rb_` schema. Existing Supabase-backed ApplianceRepairBase code remains
unchanged while the new platform is introduced.

## Network model

PostgreSQL is bound to `127.0.0.1` on the VPS and must not be published on a
public interface. Applications on the same VPS connect locally. Administrative
access should use an SSH tunnel.

## Provisioning with Docker Compose

On the VPS, copy `deploy/postgres/compose.yaml` and create a sibling `.env`
from its example. Set a unique, long password, then run:

```sh
docker compose up -d
docker compose ps
```

Do not commit the deployment `.env` file. Restrict it to the deployment user.

The initial database bootstrap creates three distinct roles:

- `repairbase_owner`: cluster/database owner used only by PostgreSQL bootstrap.
- `repairbase_migrator`: owns schema changes and runs migrations.
- `repairbase_app`: restricted runtime role; phase 1 grants read access only.

Use the migrator role for `DATABASE_URL` while applying migrations. Application
services must use a separate URL containing the `repairbase_app` credentials.
The bootstrap scripts run only when PostgreSQL initializes an empty data
volume. For an existing volume, create or update these roles through a reviewed
administrative migration rather than deleting the volume.

## Application connection

Set this in the application's private environment on the VPS:

```text
DATABASE_URL=postgresql://repairbase_migrator:<password>@127.0.0.1:5432/repairbase
```

If migrations run inside another Compose service, use the PostgreSQL service
name and private network instead of `127.0.0.1`.

## Migration and verification

From the project directory with `DATABASE_URL` configured:

```sh
python -m db.apply_migration --check
python -m db.apply_migration --all
python -m db.apply_migration --verify-repairbase
```

The verification fixture runs inside a transaction and ends with `ROLLBACK`.
It does not leave fixture rows in the database.

## Backups

Configure automated daily `pg_dump` backups to storage outside the VPS before
production data is loaded. Test restoration into a separate database. A backup
that has not been restored successfully is not considered verified.

Run backups with a dedicated backup role or the owner through a locally stored
credential file with restrictive permissions. Do not reuse the application
password for backups.
