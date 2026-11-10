"""T002: the platform schema must migrate without losing existing businesses.

Run only against a fresh, disposable PostgreSQL database whose name begins with
``smartbooking_migration_test_``. This test intentionally never reads the app's
production DATABASE_URL.
"""

import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import unittest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "f5b6ae5f0595"
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


class PlatformSchemaMigrationTest(unittest.TestCase):
    def test_upgrade_and_downgrade_preserve_existing_owner_and_business(self) -> None:
        url = os.environ.get("TEST_DATABASE_URL", "")
        if not url:
            self.skipTest("TEST_DATABASE_URL is required for the migration test")

        parsed = urlparse(url)
        self.assertIsNone(parsed.hostname)
        self.assertEqual(parse_qs(parsed.query).get("host"), ["/tmp"])
        self.assertEqual(parse_qs(parsed.query).get("port"), ["55432"])
        self.assertTrue(parsed.path.lstrip("/").startswith("smartbooking_migration_test_"))

        env = os.environ.copy()
        env["DATABASE_URL"] = url

        def alembic(*args: str) -> None:
            subprocess.run(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini", *args],
                cwd=BACKEND_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        def query(sql: str) -> str:
            result = subprocess.run(
                ["psql", "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-d", url, "-c", sql],
                cwd=BACKEND_ROOT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout.strip()

        alembic("upgrade", PREVIOUS_REVISION)
        owner_id = query(
            "INSERT INTO owners (name, email, hashed_password, email_verified) "
            "VALUES ('Dueño existente', 'existing-owner@example.test', 'hash', true) "
            "RETURNING id"
        ).splitlines()[0]
        business_id = query(
            "INSERT INTO businesses (name, phone_number, owner_id, is_active) "
            f"VALUES ('Negocio existente', '18095550000', {int(owner_id)}, true) RETURNING id"
        ).splitlines()[0]

        alembic("upgrade", "head")
        for table in NEW_TABLES:
            with self.subTest(table=table):
                self.assertEqual(query(f"SELECT to_regclass('public.{table}') IS NOT NULL"), "t")

        self.assertEqual(
            query("SELECT is_nullable FROM information_schema.columns "
                  "WHERE table_name='owners' AND column_name='name'"),
            "YES",
        )
        self.assertEqual(
            query("SELECT data_type FROM information_schema.columns "
                  "WHERE table_name='owners' AND column_name='access_revoked_at'"),
            "timestamp with time zone",
        )
        self.assertEqual(
            query("SELECT onboarding_completed_at IS NOT NULL FROM businesses "
                  f"WHERE id={int(business_id)}"),
            "t",
        )
        self.assertEqual(
            query("SELECT role FROM business_memberships "
                  f"WHERE business_id={int(business_id)} AND user_id={int(owner_id)}"),
            "owner",
        )
        incomplete_owner_id = query(
            "INSERT INTO owners (name, email, hashed_password, email_verified) "
            "VALUES (NULL, 'incomplete-owner@example.test', 'hash', true) RETURNING id"
        ).splitlines()[0]
        self.assertEqual(
            query(f"SELECT name IS NULL FROM owners WHERE id={int(incomplete_owner_id)}"),
            "t",
        )
        query(f"DELETE FROM owners WHERE id={int(incomplete_owner_id)}")

        alembic("downgrade", PREVIOUS_REVISION)
        self.assertEqual(
            query("SELECT count(*) FROM information_schema.columns "
                  "WHERE table_name='owners' AND column_name='access_revoked_at'"),
            "0",
        )
        for table in NEW_TABLES:
            with self.subTest(table=f"dropped {table}"):
                self.assertEqual(query(f"SELECT to_regclass('public.{table}') IS NULL"), "t")
        self.assertEqual(
            query(f"SELECT email FROM owners WHERE id={int(owner_id)}"),
            "existing-owner@example.test",
        )
        self.assertEqual(
            query(f"SELECT name FROM businesses WHERE id={int(business_id)}"),
            "Negocio existente",
        )


if __name__ == "__main__":
    unittest.main()
