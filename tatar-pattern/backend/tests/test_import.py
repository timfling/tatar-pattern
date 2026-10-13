import copy
import json
from pathlib import Path
from uuid import uuid4
import psycopg
from PIL import Image

from scripts.catalog_import import validate, db_conflicts, import_reviewed
from scripts.fixtures import build_fixture
from app.catalog import catalog
from app.config import Settings


def write_manifest(tmp_path,data):
    path=tmp_path/'reviewed.json'
    path.write_text(json.dumps(data,ensure_ascii=False))
    return path


def test_validation_reports_missing_review_files_duplicates_and_escape(tmp_path):
    fixture=build_fixture(tmp_path)
    data=json.loads(fixture.read_text())
    _,report=validate(fixture,tmp_path)
    assert report['valid']
    assert report['counts']['elements']==8
    changed=copy.deepcopy(data)
    changed['humanApproved']=False
    changed['artifacts'][0]['reviewStatus']='авто'
    changed['elements'][0]['path']='../outside.png'
    changed['elements'][1]['path']=changed['elements'][2]['path']
    changed['elements'][3]['verifiedBy']=''
    changed['elements'][4]['aiRetouched']=True
    changed['elements'][5]['motifIdentity']=changed['elements'][6]['motifIdentity']
    _,report=validate(write_manifest(tmp_path,changed),tmp_path)
    assert not report['valid'] and len(report['errors'])>=5 and len(report['duplicates'])>=2
    csv=tmp_path/'annotations.csv'
    csv.write_text('frame,review_status\nDSC1,авто\n')
    assert validate(csv,tmp_path)[1]['valid'] is False
    malformed=copy.deepcopy(data)
    malformed['sources'][0]['key']={"invalid":"type"}
    malformed['elements'][0]['code']=['not','a','code']
    assert validate(write_manifest(tmp_path,malformed),tmp_path)[1]['valid'] is False
    changed=copy.deepcopy(data)
    Image.new('RGB',(64,64),'red').save(tmp_path/changed['elements'][0]['path'])
    _,report=validate(write_manifest(tmp_path,changed),tmp_path)
    assert not report['valid'] and any('прозрачный' in e for e in report['errors'])


def test_fixture_not_counted_and_duplicate_import_is_blocked(prepared):
    settings,data=prepared
    path=next(settings.storage_root.glob('fixtures/*/reviewed-fixture.json'))
    _,report=validate(path,settings.storage_root)
    with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
        db_conflicts(conn,data,report)
        assert not report['valid'] and len(report['duplicates'])==8
        sql=(Path(__file__).resolve().parents[2]/'db/queries/count_real_elements.sql').read_text().split(';')[0]+';'
        assert conn.execute(sql).fetchone()['real_unique_elements_with_files_and_provenance']==0


def test_changed_or_missing_files_fail_closed(prepared):
    settings,data=prepared
    path=settings.storage_root/data['elements'][0]['path']
    original=path.read_bytes()
    with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
        before=len(catalog(conn,settings))
        path.write_bytes(b'changed PNG')
        try:
            assert len(catalog(conn,settings))==before-1
        finally:
            path.write_bytes(original)


def test_import_real_registry_count_and_provenance_on_separate_schema(prepared,tmp_path):
    # Validate importer independently of fixtures in its own test schema.
    settings,_=prepared
    schema='import_'+uuid4().hex
    from psycopg import sql
    with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for file in sorted((Path(__file__).resolve().parents[2]/'db/migrations').glob('*.sql')):
            conn.execute(file.read_text())
        fixture=build_fixture(tmp_path)
        data,report=validate(fixture,tmp_path)
        db_conflicts(conn,data,report)
        assert report['valid']
        import_reviewed(conn,data,report)
        # These are synthetic test records inside a disposable test schema,
        # used to exercise the real importer branch, not the production tally.
        sql_count=(Path(__file__).resolve().parents[2]/'db/queries/count_real_elements.sql').read_text().split(';')[0]+';'
        assert conn.execute(sql_count).fetchone()['real_unique_elements_with_files_and_provenance']==8
        assert len(catalog(conn,Settings(settings.database_url,tmp_path)))==8
        duplicate=validate(fixture,tmp_path)[1]
        db_conflicts(conn,data,duplicate)
        assert not duplicate['valid']
        conn.execute("UPDATE artifacts SET usage_scope='контекст'")
        assert conn.execute(sql_count).fetchone()['real_unique_elements_with_files_and_provenance']==0
        conn.execute("UPDATE elements SET is_fixture=true")


def test_legacy_database_preserves_demo_and_records_migrations(prepared,monkeypatch):
    from scripts.migrate import main as migrate
    settings,_=prepared
    schema='legacy_'+uuid4().hex
    from psycopg import sql
    base=Path(__file__).resolve().parents[2]/'db'
    with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        conn.execute(sql.SQL('SET LOCAL search_path TO {}').format(sql.Identifier(schema)))
        for file in sorted((base/'migrations').glob('00[1-4]*.sql')):
            conn.execute(file.read_text())
        conn.execute((base/'seeds/010_seed.sql').read_text())
    scoped=psycopg.conninfo.make_conninfo(settings.database_url,options=f'-c search_path={schema}')
    monkeypatch.setenv('DATABASE_URL',scoped)
    migrate()
    migrate()
    with psycopg.connect(scoped,row_factory=psycopg.rows.dict_row) as conn:
        assert conn.execute('SELECT count(*) AS n FROM elements').fetchone()['n']==5
        assert conn.execute('SELECT count(*) AS n FROM elements WHERE is_fixture').fetchone()['n']==5
        assert conn.execute('SELECT count(*) AS n FROM generations').fetchone()['n']==1
        assert conn.execute('SELECT count(*) AS n FROM users').fetchone()['n']==1
        assert conn.execute('SELECT count(*) AS n FROM schema_migrations').fetchone()['n']==len(list((base/'migrations').glob('*.sql')))
