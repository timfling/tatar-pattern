"""Expire deleted works every hour and on library access; files follow committed rows."""
import logging
import psycopg
from psycopg.rows import dict_row
from .catalog import safe_path
logger = logging.getLogger(__name__)

def purge(settings, user_id=None):
    with psycopg.connect(settings.database_url, row_factory=dict_row, connect_timeout=3) as conn:
        conn.execute('SET statement_timeout=10000')
        where = "deleted_at < now()-interval '7 days'"
        args = []
        if user_id is not None:
            where += ' AND user_id=%s'
            args.append(user_id)
        rows = conn.execute(f'DELETE FROM generations WHERE {where} RETURNING result_path',args).fetchall()
    for row in rows:
        if row['result_path']:
            try:
                path = safe_path(settings.storage_root,row['result_path'])
                path.unlink(missing_ok=True)
                path.with_suffix('.jpg').unlink(missing_ok=True)
                path.with_name(path.stem+'.module.png').unlink(missing_ok=True)
            except (ValueError,OSError):
                logger.warning('Expired trash file cleanup failed')
