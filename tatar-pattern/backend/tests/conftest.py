import os
from uuid import uuid4
import pytest
import psycopg
from psycopg import sql
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from scripts.db_admin import backup
from scripts.migrate import main as migrate
from scripts.fixtures import load_fixture

@pytest.fixture(scope='session')
def prepared(tmp_path_factory):
    url=os.getenv('TP_TEST_DATABASE_URL')
    if not url:
        pytest.fail('Set TP_TEST_DATABASE_URL to the separate test PostgreSQL. No working DB fallback.')
    info=psycopg.conninfo.conninfo_to_dict(url)
    if not info.get('dbname','').endswith('_test'):
        pytest.fail('Safety gate: test database name must end in _test')
    os.environ['TP_ENVIRONMENT']='isolated_test'
    os.environ['TP_TEST_BACKUP_ROOT']=str(tmp_path_factory.mktemp('db-backups'))
    os.environ['DATABASE_URL']=url
    backup()
    schema='test_'+uuid4().hex
    with psycopg.connect(url) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
    options=f'-c search_path={schema}'
    scoped=psycopg.conninfo.make_conninfo(url,options=options)
    os.environ['DATABASE_URL']=scoped
    migrate()
    migrate()  # Verify ledger idempotency.
    root=tmp_path_factory.mktemp('catalog')
    with psycopg.connect(scoped,row_factory=psycopg.rows.dict_row) as conn:
        fixtures=load_fixture(conn,root)
    settings=Settings(scoped,root,allow_fixtures=True,local_catalog=True)
    return settings,fixtures

@pytest.fixture
def client(prepared):
    with TestClient(create_app(prepared[0])) as client:
        yield client

@pytest.fixture
def signed_in(client):
    email=f'{uuid4().hex}@example.com'
    password='correct test password 2026'
    response=client.post('/api/auth/register',json={'email':email,'password':password})
    assert response.status_code==201,response.text
    return client,email,password
