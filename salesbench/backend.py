"""Interchangeable scripted demonstration and real JSON LLM adapter."""
import json
import os
import time
import urllib.error
import urllib.request
from .templates import TEMPLATES, intent
from .tools import statistics

PROMPTS = {
 'Planner': '''Ты Planner. Декомпозируй вопрос в subquestions (список строк).
Верни JSON {"subquestions":[...],"steps":[{"role":"SQL","instruction":"..."},{"role":"Analyst","instruction":"..."},{"role":"Critic","instruction":"..."}]}.
Порядок определяется зависимостями: SQL до Analyst, Critic в конце.
При исправлении только сводки можешь пропустить SQL. Один SQL должен давать итоговую таблицу.''',
 'SQL': '''Ты SQL Agent. Верни JSON {"sql":"SELECT ..."}. Используй схему, правила,
план и ошибки. Запрос выполнит инструмент PostgreSQL. Не выдумывай результаты.''',
 'Analyst': '''Ты Analyst Agent. Детерминированный инструмент уже вычислил statistics.
По rows и statistics верни JSON {"chart":"bar или line","summary":"краткая сводка на русском",
"claim":{"label":"метка одной строки","value":число из этой строки}}.
Для динамики по месяцам используй line, для категорий bar. Не добавляй неподтвержденных чисел.''',
 'Critic': '''Ты Critic/Verifier. Проверь соответствие SQL вопросу и правилам, затем таблицу,
тип графика и сводку. Особое внимание статусам и дубликатам после JOIN.
Верни JSON {"ok":true/false,"target":"SQL или Analyst","reason":"причина"}.
Не принимай правильный синтаксис за доказательство правильного смысла.''',
 'Single': '''Ты единственный агент, решающий вопрос инструментами.
Каждый ход верни один JSON. Для SQL: {"action":"sql","sql":"SELECT ..."}.
После чтения rows и statistics: {"action":"report","chart":"bar или line",
"summary":"краткая сводка на русском","claim":{"label":"метка строки","value":число строки}}.
При ошибке инструмента исправь решение. Проверь бизнес-правила сам. Для месяцев line, иначе bar.'''
}


class BudgetExceeded(RuntimeError):
    pass


class Backend:
    def __init__(self, mode, args):
        self.mode=mode
        self.args=args
        self.started=time.monotonic()
        self.calls=0
        self.input_tokens=0
        self.output_tokens=0
        self.usage_known=True
        self.events=[]

    def elapsed(self):
        return time.monotonic()-self.started

    def call(self, role, board):
        if self.calls>=self.args.max_calls or self.elapsed()>=self.args.max_seconds:
            raise BudgetExceeded('Лимит вызовов или времени')
        text=json.dumps(board,ensure_ascii=False)
        system=PROMPTS[role]+'\nОтвет только в формате JSON.'
        # UTF-8 bytes + message overhead: conservative admission estimate, not measured usage.
        reserve=len((system+text).encode('utf-8'))+256+self.args.max_output_tokens
        if self.mode=='live' and (not self.usage_known or self.input_tokens+self.output_tokens+reserve>self.args.max_tokens):
            raise BudgetExceeded('Недостаточно общего токен-бюджета для следующего вызова')
        self.calls+=1
        event=dict(role=role,request=json.loads(text),call=self.calls)
        start=time.monotonic()
        try:
            if self.mode=='demo':
                result=self.scripted(role,board)
                event['usage']=dict(input_tokens=0,output_tokens=0)
            else:
                request=urllib.request.Request(self.args.endpoint.rstrip('/')+'/chat/completions',
                    data=json.dumps(dict(model=self.args.model,messages=[dict(role='system',content=system),dict(role='user',content=text)],response_format=dict(type='json_object'),max_completion_tokens=self.args.max_output_tokens)).encode(),
                    headers={'Content-Type':'application/json','Authorization':'Bearer '+os.environ['OPENAI_API_KEY']},method='POST')
                timeout=min(45,max(0.1,self.args.max_seconds-self.elapsed()))
                try:
                    with urllib.request.urlopen(request,timeout=timeout) as response:
                        body=json.load(response)
                except Exception:
                    self.usage_known=False
                    raise
                usage=body.get('usage') or {}
                inp,out=usage.get('prompt_tokens'),usage.get('completion_tokens')
                if isinstance(inp,int) and isinstance(out,int):
                    self.input_tokens+=inp
                    self.output_tokens+=out
                    event['usage']=dict(input_tokens=inp,output_tokens=out)
                else:
                    self.usage_known=False
                    event['usage']=None
                result=json.loads(body['choices'][0]['message']['content'])
            if not isinstance(result,dict):
                raise ValueError('Модель вернула не JSON-объект')
            event['response']=result
            return result
        except urllib.error.HTTPError as exc:
            # Do not persist headers, API key or provider response body.
            event['error']=f'HTTP {exc.code}'
            raise RuntimeError(event['error']) from None
        except Exception as exc:
            event['error']=str(exc)
            raise
        finally:
            event['seconds']=time.monotonic()-start
            self.events.append(event)

    def scripted(self, role, board):
        """Fixed responses are intentional teaching fixtures, not LLM reasoning."""
        name=intent(board['question'])
        if role=='Planner':
            return dict(subquestions=['Определить фильтры и группировку','Выполнить SQL','Сформировать и проверить отчёт'],steps=[dict(role=r,instruction=i) for r,i in [('SQL','Верни итоговую таблицу с учётом ошибок'),('Analyst','Посчитай статистику и выбери график'),('Critic','Проверь правила учёта продаж')]])
        if role in ('SQL','Single') and (role=='SQL' or not board.get('rows')):
            sql=TEMPLATES[name]
            if not board.get('errors'):
                if name=='average':
                    sql=sql.replace('AVG(o.total)','AVG(o.amount)')
                elif name=='total':
                    sql=sql.replace(" WHERE status='completed'",'')
            return dict(action='sql',sql=sql)
        if role in ('Analyst','Single'):
            leader=statistics(board['rows'])['leader']
            return dict(action='report',chart='line' if name=='monthly' else 'bar',summary=f"Наибольшее значение: {leader['label']} = {leader['value']:.3f}. Число групп: {len(board['rows'])}.",claim=leader)
        if role=='Critic':
            if "status='completed'" not in board['sql']:
                return dict(ok=False,target='SQL',reason='Нет фильтра завершённых заказов, в выручку попали отмены')
            return dict(ok=True,target='SQL',reason='Проверка демонстрационного правила пройдена')
        raise ValueError('Неизвестная роль')

    def metrics(self):
        known=self.usage_known
        cost=0.0 if self.mode=='demo' else None
        if self.mode=='live' and known and self.args.input_price is not None and self.args.output_price is not None:
            cost=(self.input_tokens*self.args.input_price+self.output_tokens*self.args.output_price)/1_000_000
        return dict(calls=self.calls,input_tokens=self.input_tokens if known else None,output_tokens=self.output_tokens if known else None,known_input_tokens=self.input_tokens,known_output_tokens=self.output_tokens,usage_complete=known,cost_usd=cost,seconds=self.elapsed())
