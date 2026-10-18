"""Three runners with identical SQL/report tools and observable shared state."""
import copy
from .backend import BudgetExceeded
from .data import SCHEMA,RULES
from .templates import TEMPLATES,intent
from .tools import query,statistics,make_report


def initial(task):
    return dict(question=task['question'],schema=SCHEMA,rules=RULES,sql='',rows=[],statistics={},report={},plan={},errors=[],history=[],completed=False)


def error(board,role,exc):
    message=dict(role=role,message=str(exc))
    board['errors'].append(message)
    board['history'].append(dict(event='error',**message))


def do_sql(db,board,sql):
    board.update(sql=sql,rows=[],statistics={},report={})
    board['rows']=query(db,sql)
    board['statistics']=statistics(board['rows'])
    board['history'].append(dict(event='sql_result',sql=sql,rows=copy.deepcopy(board['rows'])))


def workflow(db,task,backend):
    board=initial(task)
    try:
        name=intent(task['question'])
        if name=='returns':
            raise ValueError('Шаблон с возвратами отсутствует в базовом workflow')
        do_sql(db,board,TEMPLATES[name])
        leader=board['statistics']['leader']
        board['report']=make_report(board['rows'],dict(chart='line' if name=='monthly' else 'bar',summary=f"Максимум: {leader['label']} = {leader['value']:.3f}.",claim=leader))
        board['completed']=True
    except Exception as exc:
        error(board,'Workflow',exc)
    return board,copy.deepcopy(board)


def single(db,task,backend):
    board=initial(task)
    first=None
    sql_attempts=0
    while backend.calls<backend.args.max_calls:
        try:
            response=backend.call('Single',board)
            action=response.get('action')
            if action=='sql':
                if sql_attempts>=backend.args.max_attempts:
                    raise BudgetExceeded('Лимит SQL-попыток')
                sql_attempts+=1
                try:
                    do_sql(db,board,response['sql'])
                except Exception as exc:
                    if first is None:
                        first=copy.deepcopy(board)
                    error(board,'Single.SQL',exc)
            elif action=='report':
                board['report']=make_report(board['rows'],response)
                board['history'].append(dict(event='report',report=copy.deepcopy(board['report'])))
                board['completed']=True
                if first is None:
                    first=copy.deepcopy(board)
                break
            else:
                raise ValueError('Неизвестное action')
        except BudgetExceeded as exc:
            error(board,'Budget',exc)
            break
        except Exception as exc:
            if first is None:
                first=copy.deepcopy(board)
            error(board,'Single',exc)
            # Transport failures or missing usage cannot safely be silently retried.
            if not backend.usage_known:
                break
    return board,first if first is not None else copy.deepcopy(board)


def mas(db,task,backend):
    board=initial(task)
    first=None
    for attempt in range(backend.args.max_attempts):
        board['attempt']=attempt+1
        try:
            plan=backend.call('Planner',board)
            steps=plan.get('steps',[])
            roles=[s.get('role') for s in steps]
            if roles not in (['SQL','Analyst','Critic'],['Analyst','Critic']) or (not board['rows'] and roles[0]!='SQL'):
                raise ValueError('Неверный порядок зависимостей плана')
            if not isinstance(plan.get('subquestions'),list) or not plan['subquestions']:
                raise ValueError('План должен содержать subquestions')
            board['plan']=plan
            board['history'].append(dict(event='plan',plan=copy.deepcopy(plan)))
            accepted=False
            for step in steps:
                role=step['role']
                board['instruction']=step.get('instruction','')
                response=backend.call(role,board)
                if role=='SQL':
                    do_sql(db,board,response['sql'])
                elif role=='Analyst':
                    board['report']=make_report(board['rows'],response)
                    if first is None:
                        first=copy.deepcopy(board)
                elif role=='Critic':
                    if not isinstance(response.get('ok'),bool):
                        raise ValueError('Critic должен вернуть булево ok')
                    board['history'].append(dict(event='verification',**response))
                    if response['ok']:
                        accepted=True
                    else:
                        error(board,'Critic',response.get('reason','Нужна переделка'))
                        board['repair_target']=response.get('target','SQL')
            if accepted:
                board['completed']=True
                break
        except BudgetExceeded as exc:
            error(board,'Budget',exc)
            break
        except Exception as exc:
            if first is None:
                first=copy.deepcopy(board)
            error(board,'MAS',exc)
            if not backend.usage_known:
                break
    return board,first if first is not None else copy.deepcopy(board)

RUNNERS={'workflow':workflow,'single':single,'mas':mas}
