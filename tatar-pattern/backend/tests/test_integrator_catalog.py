"""Addressed R1/R2 only: simulated health, file mutations, bounded cold GETs."""
import copy
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image
from app import ai_catalog, ai_provider, catalog
from app.config import Settings
from app.errors import APIError
from app.main import create_app


class Rows:
    def __init__(self,rows):self.rows=rows;self.queries=[]
    def execute(self,query,params):
        self.queries.append((query,params))
        self.result=[r for r in self.rows if len(params)==1 or r['code'] in params[1]]
        return self
    def fetchall(self):return copy.deepcopy(self.result)


@pytest.fixture
def files(tmp_path):
    catalog.invalidate_catalog_cache()
    source=tmp_path/'source';source.write_bytes(b'synthetic-source')
    rows=[]
    for i in range(110):
        png=tmp_path/f'{i}.png'
        image=Image.new('RGBA',(32,32));image.putpixel((16,16),(255,0,0,255));image.save(png)
        rows.append(dict(code=f'TP-E-{i:03}',path=png.name,source_path=source.name,
            content_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),
            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            motif_class='тюльпан',local_use_approved=True,public_use_approved=True))
    return Settings('unused',tmp_path),Rows(rows)


def endpoint(settings,path):
    return next(r.endpoint for r in create_app(settings).routes if getattr(r,'path','')==path)


@pytest.mark.parametrize('enabled,expected',[(False,0),(True,1)])
def test_health_snapshot_once_even_after_slow_failure(tmp_path,enabled,expected):
    provider=ai_provider.HTTPProvider('http://example.invalid','x'*32,ai_provider.WORKFLOW,ai_provider.MODEL)
    clock=SimpleNamespace(now=100.)
    clock.monotonic=lambda:clock.now
    def timeout(*a,**kw):
        assert kw['timeout']==5
        clock.now+=5.1
        raise ai_provider.ProviderError('AI_GPU_TRANSPORT_ERROR')
    with patch.object(provider,'_proof_possible',return_value=True),patch.object(provider,'_json',side_effect=timeout) as calls,patch.object(ai_provider,'time',clock):
        response=ai_catalog.catalog_response(Settings('unused',tmp_path,ai_mvp_enabled=enabled),provider)
        assert not response['available'] and calls.call_count==expected
        capabilities=endpoint(Settings('unused',tmp_path,ai_mvp_enabled=enabled),'/api/capabilities')
        with patch('app.main.configured_provider',return_value=provider):
            assert not capabilities(conn=Rows([]))['modes']['ai']['available']
        assert calls.call_count==expected
        if enabled:
            assert not provider.ready and calls.call_count==1  # Cached refusal after completion.
            clock.now+=5.01
            assert not provider.ready and calls.call_count==2
    print(json.dumps({'aiEnabled':enabled,'catalogHealthAttempts':expected,'simulatedSeconds':5.1*expected,'submits':0}))


def test_one_unknown_and_warm_thumbnail(files):
    settings,conn=files
    get=endpoint(settings,'/api/elements/{code}/file')
    with patch.object(catalog,'inspect_png',wraps=catalog.inspect_png) as png,patch.object(catalog.hashlib,'file_digest',wraps=hashlib.file_digest) as sha:
        assert str(get('TP-E-000',conn).path).endswith('0.png')
        assert png.call_count==sha.call_count==1
        get('TP-E-000',conn)
        assert png.call_count==sha.call_count==1
        with pytest.raises(APIError) as exc:get('unknown',conn)
        assert exc.value.status==404 and png.call_count==sha.call_count==1
    assert all('code = ANY(%s)' in q for q,p in conn.queries)
    print(json.dumps({'catalogRows':110,'oneGET':{'png':1,'sourceSHA':1},'warmGET':{'png':0,'sourceSHA':0},'unknownGET':{'png':0,'sourceSHA':0}}))


def test_cache_checks_approval_sha_paths_corruption_missing_and_explicit_invalidation(files):
    settings,conn=files
    one=lambda:catalog.catalog(conn,settings,['TP-E-000'])
    assert one()
    row=conn.rows[0]
    row['public_use_approved']=False;assert not one()
    row['public_use_approved']=True;assert one()
    row['content_sha256']='0'*64;assert not one()
    row['content_sha256']=hashlib.sha256((settings.storage_root/'0.png').read_bytes()).hexdigest();assert one()
    for field in ['path','source_path']:
        original=row[field]
        for invalid in ['../outside','/etc/passwd']:
            row[field]=invalid;assert not one()
        row[field]=original
    path=settings.storage_root/'0.png';original=path.read_bytes()
    path.write_bytes(b'corrupt');assert not one()
    path.write_bytes(original);assert one()
    path.unlink();assert not one()
    path.write_bytes(original);assert one()
    source=settings.storage_root/'source';source.write_bytes(b'changed');assert not one()
    row['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest();assert one()
    with patch.object(catalog,'inspect_png',wraps=catalog.inspect_png) as checked:
        one();assert checked.call_count==0
        catalog.invalidate_catalog_cache();assert one() and checked.call_count==1
        with patch.object(catalog,'CACHE_SECONDS',0):assert one() and checked.call_count==2
    assert len(catalog._verified)<=catalog.CACHE_ENTRIES


def test_scheme_preview_verifies_only_defaults_unknown_verifies_nothing(files,monkeypatch):
    settings,conn=files
    scheme={'id':'known','defaultElementCodes':['TP-E-000','TP-E-001']}
    monkeypatch.setattr('app.main.release_catalog',lambda _: {'schemes':[scheme]})
    monkeypatch.setattr('app.main.ASSETS',settings.storage_root)
    (settings.storage_root/'known.png').write_bytes((settings.storage_root/'0.png').read_bytes())
    get=endpoint(settings,'/api/composition-schemes/{sid}/preview')
    with patch.object(catalog,'inspect_png',wraps=catalog.inspect_png) as png:
        with pytest.raises(APIError):get('unknown',conn)
        assert png.call_count==0
        get('known',conn);assert png.call_count==2
        get('known',conn);assert png.call_count==2
    assert all(params[1]==scheme['defaultElementCodes'] for q,params in conn.queries)


def test_cold_parallel_get_admission(files,monkeypatch):
    settings,conn=files
    get=endpoint(settings,'/api/elements/{code}/file')
    entered=[Event(),Event()];release=Event();original=catalog.inspect_png
    def held(path):
        index=int(path.stem)
        entered[index].set()
        assert release.wait(3)
        return original(path)
    monkeypatch.setattr(catalog,'inspect_png',held)
    with ThreadPoolExecutor(2) as pool:
        futures=[pool.submit(get,f'TP-E-{i:03}',Rows(conn.rows)) for i in range(2)]
        try:
            assert all(event.wait(2) for event in entered)
            with pytest.raises(APIError) as exc:get('TP-E-002',Rows(conn.rows))
            assert exc.value.status==503 and exc.value.payload['error']['code']=='CATALOG_BUSY'
        finally:release.set()
        for future in futures:future.result()
    print(json.dumps({'parallelColdVerifications':2,'third':'503 CATALOG_BUSY'}))


# Real SQL view and accepted 110-file package, still only isolated loopback DB.
from test_guest import real_guest


def test_real_catalog_cache_still_reads_approval_and_provenance(real_guest):
    import psycopg
    settings=real_guest
    catalog.invalidate_catalog_cache()
    with psycopg.connect(settings.database_url,row_factory=psycopg.rows.dict_row) as conn:
        get=endpoint(settings,'/api/elements/{code}/file')
        with patch.object(catalog,'inspect_png',wraps=catalog.inspect_png) as png:
            get('TP-E-050',conn);assert png.call_count==1
            get('TP-E-050',conn);assert png.call_count==1
            conn.execute("UPDATE catalog_releases SET decision=jsonb_set(decision,'{approved}','false')")
            with pytest.raises(APIError) as exc:get('TP-E-050',conn)
            assert exc.value.status==404 and png.call_count==1
            conn.rollback()
            get('TP-E-050',conn);assert png.call_count==1
            conn.execute("UPDATE elements SET provenance=jsonb_set(provenance,'{trainingAllowed}','true') WHERE code='TP-E-050'")
            with pytest.raises(APIError) as exc:get('TP-E-050',conn)
            assert exc.value.status==404 and png.call_count==1
            conn.rollback()
        rows=catalog.catalog(conn,settings)
        assert len(rows)==110
        with patch.object(catalog,'inspect_png',wraps=catalog.inspect_png) as png,patch.object(catalog.hashlib,'file_digest',wraps=hashlib.file_digest) as sha:
            assert len(catalog.catalog(conn,settings))==110
            assert png.call_count==sha.call_count==0
        print(json.dumps({'realAcceptedCatalog':110,'warmListPNG':0,'warmListSourceSHA':0,'approvalRevocation':'404','provenanceChange':'404'}))
