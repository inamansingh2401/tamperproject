"""Actual PostgreSQL roles/ACLs/RLS; intentionally unavailable on SQLite."""
import os
from pathlib import Path
import unittest
import test_security as fixture
from sqlalchemy import text, inspect
from sqlalchemy.exc import DBAPIError
from database import engine


@unittest.skipUnless(os.getenv('SAFETRACK_TEST_DATABASE_URL'), 'Requires disposable local PostgreSQL role support')
class BrowserRoleIsolationTests(unittest.TestCase):
    def test_browser_roles_cannot_read_or_write_application_tables(self):
        self.assertIn(engine.url.host,('127.0.0.1','localhost'))
        self.assertEqual(engine.url.database,'safetrack_test')
        sql = (Path(__file__).resolve().parents[1]/'migrations/sql/0005_browser_role_isolation.sql').read_text()
        with engine.connect() as conn:
            tx = conn.begin()
            try:
                conn.execute(text('CREATE ROLE anon NOLOGIN NOBYPASSRLS'))
                conn.execute(text('CREATE ROLE authenticated NOLOGIN NOBYPASSRLS'))
                conn.execute(text('GRANT USAGE ON SCHEMA public TO anon, authenticated'))
                conn.execute(text(sql))
                tables = inspect(conn).get_table_names()
                columns = {table:inspect(conn).get_columns(table)[0]['name'] for table in tables}
                for role in ('anon','authenticated'):
                    conn.execute(text('SET LOCAL ROLE '+role))
                    for table in tables:
                        col = columns[table]
                        for statement in (f'SELECT * FROM "{table}" LIMIT 0',
                                f'INSERT INTO "{table}" DEFAULT VALUES',
                                f'UPDATE "{table}" SET "{col}"="{col}"',f'DELETE FROM "{table}"'):
                            with self.subTest(role=role,table=table,operation=statement.split()[0]):
                                savepoint = conn.begin_nested()
                                try:
                                    with self.assertRaises(DBAPIError) as error:
                                        conn.execute(text(statement))
                                    self.assertEqual(error.exception.orig.sqlstate,'42501')
                                finally:
                                    savepoint.rollback()
                    conn.execute(text('RESET ROLE'))
                # Prove restrictive RLS still denies rows if grants and an
                # overly permissive old policy are accidentally restored.
                for table in tables:
                    conn.execute(text(f'GRANT ALL ON TABLE "{table}" TO anon, authenticated'))
                    conn.execute(text(f'CREATE POLICY old_allow ON "{table}" FOR ALL TO anon, authenticated USING (true) WITH CHECK (true)'))
                for role in ('anon','authenticated'):
                    conn.execute(text('SET LOCAL ROLE '+role))
                    for table in tables:
                        self.assertEqual(conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar(),0)
                        self.assertEqual(conn.execute(text(f'DELETE FROM "{table}"')).rowcount,0)
                    savepoint = conn.begin_nested()
                    try:
                        with self.assertRaises(DBAPIError) as error:
                            conn.execute(text("INSERT INTO system_settings (id,category,key,value) VALUES (-999,'probe','probe','probe')"))
                        self.assertEqual(error.exception.orig.sqlstate,'42501')
                    finally:
                        savepoint.rollback()
                    conn.execute(text('RESET ROLE'))
            finally:
                tx.rollback()  # All roles, policies, grants and test writes removed.
