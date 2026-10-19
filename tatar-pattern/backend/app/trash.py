"""Existing seven-day trash policy; durable erasure and retry on library access/hourly.

This existing product interval is not a deadline for account/privacy requests.
"""
import psycopg
from psycopg.rows import dict_row
from .erasure import erase_generation, drain_files

def purge(settings, user_id=None):
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=3) as conn:
        conn.execute('SET statement_timeout=10000')
        # Expired sessions need no continuing authentication purpose.
        conn.execute('DELETE FROM sessions WHERE expires_at<=now()')
        where="deleted_at < now()-interval '7 days'"
        args=[]
        if user_id is not None:
            where+=' AND user_id=%s';args.append(user_id)
        rows=conn.execute(f'SELECT * FROM generations WHERE {where} ORDER BY id FOR UPDATE',args).fetchall()
        for row in rows:erase_generation(conn,row,'trash_expired')
        conn.commit()  # Durable deletion queue survives unlink failure/process exit.
        drain_files(conn,settings.storage_root)
