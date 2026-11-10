"""T003: ORM mappings must match the migrated platform schema.

Run only against a disposable local PostgreSQL database named
``smartbooking_migration_test_*``. No application DATABASE_URL is used.
"""

import os
import subprocess
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from sqlalchemy import UniqueConstraint, create_engine, inspect, text
from sqlalchemy.exc import IntegrityError


BACKEND_ROOT = Path(__file__).resolve().parents[1]
NEW_TABLES = (
    "platform_admins",
    "platform_admin_sessions",
    "platform_login_attempts",
    "business_memberships",
    "owner_invitations",
    "password_resets",
    "password_reset_request_attempts",
    "admin_audit_events",
    "message_events",
    "message_cost_records",
)


class PlatformModelTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        url = os.environ.get("TEST_DATABASE_URL", "")
        if not url:
            raise unittest.SkipTest("TEST_DATABASE_URL is required")
        parsed = urlparse(url)
        if (
            parsed.hostname is not None
            or parse_qs(parsed.query).get("host") != ["/tmp"]
            or parse_qs(parsed.query).get("port") != ["55432"]
            or not parsed.path.lstrip("/").startswith("smartbooking_migration_test_")
        ):
            raise ValueError("Refusing to run platform model tests outside local disposable DB")

        env = os.environ.copy()
        env["DATABASE_URL"] = url
        subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
            cwd=BACKEND_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )
        cls.engine = create_engine(url)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.engine.dispose()

    def test_platform_mappings_match_migration(self) -> None:
        from app.core.database import Base
        from app import models

        inspector = inspect(self.engine)
        for table_name in NEW_TABLES:
            with self.subTest(table=table_name):
                self.assertIn(table_name, Base.metadata.tables)
                mapped = Base.metadata.tables[table_name]
                database_columns = {
                    column["name"]: column for column in inspector.get_columns(table_name)
                }
                self.assertEqual(set(mapped.columns.keys()), set(database_columns))
                for column in mapped.columns:
                    self.assertEqual(column.nullable, database_columns[column.name]["nullable"])

                database_indexes = {
                    index["name"]
                    for index in inspector.get_indexes(table_name)
                    if not index.get("duplicates_constraint")
                }
                mapped_indexes = {index.name for index in mapped.indexes}
                self.assertEqual(mapped_indexes, database_indexes)
                database_uniques = {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints(table_name)
                }
                mapped_uniques = {
                    constraint.name
                    for constraint in mapped.constraints
                    if isinstance(constraint, UniqueConstraint)
                }
                self.assertEqual(mapped_uniques, database_uniques)

        self.assertTrue(models.Owner.__table__.c.name.nullable)
        self.assertFalse(models.Owner.__table__.c.is_active.nullable)
        self.assertTrue(models.Owner.__table__.c.access_revoked_at.nullable)
        self.assertTrue(models.Business.__table__.c.onboarding_completed_at.nullable)

    def test_concurrent_pending_invites_allow_only_one_email(self) -> None:
        from app.models import OwnerInvitation, PlatformAdmin

        nonce = uuid4().hex
        email = f"owner-{nonce}@example.test"
        with self.engine.begin() as connection:
            admin_id = connection.execute(
                PlatformAdmin.__table__.insert()
                .values(email=f"admin-{nonce}@example.test", hashed_password="hash")
                .returning(PlatformAdmin.id)
            ).scalar_one()

        first = self.engine.connect()
        second = self.engine.connect()
        first_tx = first.begin()
        try:
            first.execute(
                OwnerInvitation.__table__.insert().values(
                    email=email.upper(),
                    token_hash=nonce * 2,
                    invited_by_admin_id=admin_id,
                    expires_at=text("now() + interval '1 day'"),
                )
            )

            started = Event()

            def competing_insert() -> None:
                with second.begin():
                    started.set()
                    second.execute(
                        OwnerInvitation.__table__.insert().values(
                            email=email,
                            token_hash=uuid4().hex * 2,
                            invited_by_admin_id=admin_id,
                            expires_at=text("now() + interval '1 day'"),
                        )
                    )

            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(competing_insert)
                self.assertTrue(started.wait(timeout=5))
                self.assertFalse(future.done())
                first_tx.commit()
                with self.assertRaises(IntegrityError):
                    future.result(timeout=5)
        finally:
            if first_tx.is_active:
                first_tx.rollback()
            first.close()
            second.close()


if __name__ == "__main__":
    unittest.main()
