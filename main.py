#!/usr/bin/env python3
"""Run all three architectures; PostgreSQL backend with psycopg 3."""
import argparse
import datetime
import json
import os
import random
from pathlib import Path
from salesbench.config import load_environment
from salesbench.architectures import RUNNERS
from salesbench.backend import Backend
from salesbench.data import TASKS
from salesbench.database import Database,database_info
from salesbench.evaluate import assess
from salesbench.reporting import write_report

ROOT=Path(__file__).resolve().parent


def parser():
    p=argparse.ArgumentParser(description='SQL Agents: учебное сравнение workflow / single / MAS')
    p.add_argument('--backend',choices=['demo','live'],default='demo')
    p.add_argument('--variant',choices=['all',*RUNNERS],default='all')
    p.add_argument('--task',choices=[t['id'] for t in TASKS])
    p.add_argument('--repeat',type=int,default=1)
    p.add_argument('--model',default=os.getenv('LLM_MODEL',''))
    p.add_argument('--endpoint',default=os.getenv('LLM_ENDPOINT','https://api.openai.com/v1'))
    p.add_argument('--max-calls',type=int,default=12)
    p.add_argument('--max-tokens',type=int,default=16000,help='Общий input+output лимит на задачу и вариант')
    p.add_argument('--max-output-tokens',type=int,default=700)
    p.add_argument('--max-seconds',type=float,default=120)
    p.add_argument('--max-attempts',type=int,default=2)
    p.add_argument('--input-price',type=float,help='USD за 1 млн входных токенов')
    p.add_argument('--output-price',type=float,help='USD за 1 млн выходных токенов')
    p.add_argument('--seed',type=int,default=42,help='Случайный порядок вариантов, не seed LLM')
    p.add_argument('--out',type=Path)
    return p


def main():
    load_environment()
    p=parser()
    args=p.parse_args()
    for field in ['repeat','max_calls','max_tokens','max_output_tokens','max_seconds','max_attempts']:
        if getattr(args,field)<=0:
            p.error(f'{field} должен быть положительным')
    if any(v is not None and v<0 for v in [args.input_price,args.output_price]):
        p.error('Тарифы не могут быть отрицательными')
    if args.backend=='live' and args.variant!='workflow':
        if not os.getenv('OPENAI_API_KEY') or not args.model:
            p.error('Для live задайте OPENAI_API_KEY и LLM_MODEL или --model. Для показа без ключа используйте --backend demo.')
        if not args.endpoint.startswith('https://') and not args.endpoint.startswith(('http://localhost:','http://127.0.0.1:')):
            p.error('Используйте HTTPS или локальный API')
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    out=args.out or ROOT/'results'/f'{args.backend}_{stamp}'
    out.mkdir(parents=True,exist_ok=True)
    if (out/'results.json').exists():
        p.error('Папка уже содержит результаты. Выберите новую --out, чтобы сохранить старый прогон.')
    db=Database.from_env()
    try:
        db_info=database_info(db)
    except Exception:
        p.error('PostgreSQL недоступен или учебная схема не готова. Проверьте DATABASE_URL в .env и запущенный PostgreSQL. Для Docker: docker compose up -d --wait db. Для локальной установки: раздел README «Без Docker». Детали подключения в результаты не записываются.')
    tasks=[t for t in TASKS if args.task is None or t['id']==args.task]
    variants=list(RUNNERS) if args.variant=='all' else [args.variant]
    schedule=[(t,v,r+1) for r in range(args.repeat) for t in tasks for v in variants]
    random.Random(args.seed).shuffle(schedule)
    runs=[]
    config={k:(str(v) if isinstance(v,Path) else v) for k,v in vars(args).items()}
    config.update(created_utc=stamp,fixture_orders=48,fixture_customers=6,database=db_info,python='psycopg 3',demo_faults='T3: amount вместо total, T5: пропущен status в первой попытке' if args.backend=='demo' else None)
    for task,variant,repeat in schedule:
        backend=Backend(args.backend,args)
        state,first=RUNNERS[variant](db,task,backend)
        metrics=backend.metrics()  # before external evaluator, with every failed call included
        runs.append(dict(variant=variant,task=task,repeat=repeat,state=state,first=assess(db,task,first),final=assess(db,task,state,require_complete=True),metrics=metrics,trace=backend.events))
        write_report(out,runs,config)  # checkpoint even if a later task is interrupted
        print(f"{variant:8} {task['id']}  first={runs[-1]['first']['success']} final={runs[-1]['final']['success']} calls={metrics['calls']} time={metrics['seconds']:.4f}s")
    print('\nОтчёт:',(out/'report.html').resolve())
    print(json.dumps(write_report(out,runs,config),ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
