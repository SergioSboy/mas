import csv
import html
import json
import statistics
from pathlib import Path
from .tools import chart_svg

NAMES={'workflow':'Workflow','single':'Одиночный агент','mas':'MAS'}


def aggregate(runs):
    result=[]
    for variant in NAMES:
        group=[r for r in runs if r['variant']==variant]
        if not group:
            continue
        result.append(dict(variant=variant,n=len(group),first_success=sum(r['first']['success'] for r in group),final_success=sum(r['final']['success'] for r in group),mean_seconds=statistics.mean(r['metrics']['seconds'] for r in group),median_seconds=statistics.median(r['metrics']['seconds'] for r in group),total_calls=sum(r['metrics']['calls'] for r in group),input_tokens=sum(r['metrics']['input_tokens'] for r in group) if all(r['metrics']['input_tokens'] is not None for r in group) else None,output_tokens=sum(r['metrics']['output_tokens'] for r in group) if all(r['metrics']['output_tokens'] is not None for r in group) else None,total_cost_usd=sum(r['metrics']['cost_usd'] for r in group) if all(r['metrics']['cost_usd'] is not None for r in group) else None))
    return result


def write_report(out, runs, config):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=True)
    summary=aggregate(runs)
    document=dict(config=config,summary=summary,runs=runs)
    (out/'results.json').write_text(json.dumps(document,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'metrics.csv').open('w',newline='',encoding='utf-8-sig') as f:
        fields=['variant','task','repeat','first_success','final_success','seconds','calls','input_tokens','output_tokens','cost_usd','usage_complete']
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for r in runs:
            writer.writerow(dict(variant=r['variant'],task=r['task']['id'],repeat=r['repeat'],first_success=r['first']['success'],final_success=r['final']['success'],**{k:r['metrics'][k] for k in fields[5:]}))
    esc=lambda v:html.escape(str(v))
    demo=config['backend']=='demo'
    label='ДЕМО: запрограммированные ответы, LLM не вызывалась' if demo else 'Реальные вызовы LLM: '+config['model']
    p=['<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SQL Agents: результаты</title><style>body{font:17px system-ui;margin:40px auto;max-width:1150px;padding:0 24px;color:#172b3a;background:#f7f8fa}h1{font-size:36px}h2{margin-top:36px}table{border-collapse:collapse;width:100%;background:white}td,th{text-align:left;padding:14px;border-bottom:1px solid #ddd}th{background:#172b3a;color:white}details{padding:16px 0;border-bottom:1px solid #bbb}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;word-break:break-word;font-size:13px}svg{max-width:700px;background:white}aside{background:#fff1ce;padding:20px}a{color:#086f86}.ok{color:#13784b}.bad{color:#ad3b29}</style>']
    p+=['<h1>SQL Agents: PostgreSQL</h1><aside>'+esc(label)+'. '+('Числа успеха проверяют сценарий и инструменты. Они не доказывают преимущество MAS. Время относится только к локальному выполнению.' if demo else 'Все попытки, ошибки API и остановки включены. Пустая стоимость означает отсутствие тарифов или usage.')+'</aside>']
    p+=['<p>Автоматическая оценка: итоговая таблица совпадает с эталоном, тип графика верен, сводка содержит проверяемое числовое утверждение. Смысл текста дополнительно проверяет человек.</p><table><tr><th>Вариант</th><th>Сразу</th><th>Итог</th><th>Среднее, мс</th><th>Вызовы</th><th>Токены in / out</th><th>Стоимость, $</th></tr>']
    for s in summary:
        p.append('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in [NAMES[s['variant']],f"{s['first_success']}/{s['n']}",f"{s['final_success']}/{s['n']}",f"{1000*s['mean_seconds']:.2f}",s['total_calls'],f"{s['input_tokens']} / {s['output_tokens']}",s['total_cost_usd'] if s['total_cost_usd'] is not None else 'нет данных'])+'</tr>')
    p.append('</table><h2>Подготовленные случаи</h2><p>Раскройте T3, чтобы увидеть исправление неизвестного столбца. T5 показывает пропущенный фильтр статуса, T6 — границу шаблонного workflow.</p>')
    for r in runs:
        state=r['state']
        status='успех' if r['final']['success'] else 'провал'
        p.append(f'<details><summary>{NAMES[r["variant"]]} · {r["task"]["id"]} · {esc(r["task"]["question"])} · {status}</summary>')
        p.append('<p>'+esc(state.get('report',{}).get('summary','Отчёт не сформирован'))+'</p><pre>'+esc(state.get('sql',''))+'</pre>')
        if state.get('rows'):
            p.append('<table><tr><th>label</th><th>value</th></tr>'+''.join(f'<tr><td>{esc(x["label"])}</td><td>{x["value"]:.6f}</td></tr>' for x in state['rows'])+'</table>')
        if state.get('report'):
            p.append(chart_svg(state['rows'],state['report']['chart']))
        p.append('<h3>Ошибки и переделки</h3><pre>'+esc(json.dumps(state['errors'],ensure_ascii=False,indent=2))+'</pre><h3>История чёрной доски</h3><pre>'+esc(json.dumps(state['history'],ensure_ascii=False,indent=2))+'</pre><h3>Оценка и расход</h3><pre>'+esc(json.dumps(dict(first=r['first'],final=r['final'],metrics=r['metrics']),ensure_ascii=False,indent=2))+'</pre></details>')
    p.append('<h2>Условия запуска</h2><pre>'+esc(json.dumps(config,ensure_ascii=False,indent=2))+'</pre><p><a href="metrics.csv">Скачать метрики CSV</a> · <a href="results.json">Полные результаты JSON</a></p></html>')
    (out/'report.html').write_text(''.join(p),encoding='utf-8')
    return summary
