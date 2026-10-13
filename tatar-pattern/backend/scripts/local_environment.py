"""Explicit local launcher. Reads the project's existing DB settings privately."""
import argparse
import os
import subprocess
from pathlib import Path
from dotenv import dotenv_values
from psycopg.conninfo import make_conninfo

def main():
    p=argparse.ArgumentParser(); p.add_argument('environment',choices=['isolated_test','local_project']); p.add_argument('command',nargs=argparse.REMAINDER); args=p.parse_args()
    base=Path(__file__).resolve().parents[1]; env=os.environ.copy()
    env['TP_ENVIRONMENT']=args.environment; env['PG_BIN']='/opt/homebrew/opt/postgresql@16/bin'
    if args.environment=='local_project':
        values=dotenv_values(base.parent/'db/.env')
        if values.get('POSTGRES_DB')!='tatar_pattern': raise SystemExit('Unexpected project database')
        env['DATABASE_URL']=make_conninfo(host='127.0.0.1',port=values.get('POSTGRES_PORT','5432'),dbname=values['POSTGRES_DB'],user=values['POSTGRES_USER'],password=values['POSTGRES_PASSWORD'])
        env['STORAGE_ROOT']=str(base/'catalog-input')
    else:
        env['DATABASE_URL']='postgresql://tp_test@127.0.0.1:55432/tatar_pattern_backend_test'
        env['TP_TEST_DATABASE_URL']=env['DATABASE_URL']; env['STORAGE_ROOT']=str(base/'catalog-input')
    print('Explicit environment:',args.environment,flush=True)
    raise SystemExit(subprocess.call(args.command,cwd=base,env=env))

if __name__=='__main__': main()
