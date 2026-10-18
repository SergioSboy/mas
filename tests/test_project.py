import copy
import io
import json
import os
import uuid
import psycopg
from psycopg import sql
import unittest
from unittest.mock import patch
from salesbench.config import load_environment
from main import parser
from salesbench.architectures import RUNNERS
from salesbench.backend import Backend,BudgetExceeded
from salesbench.data import TASKS,create_database,bootstrap_sql
from salesbench.database import Database,DEFAULT_ADMIN_URL,DEFAULT_READER_URL
from salesbench.evaluate import assess
from salesbench.tools import query,make_report


class ProjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_environment()
        cls.admin=os.getenv('TEST_DATABASE_ADMIN_URL',os.getenv('DATABASE_ADMIN_URL',DEFAULT_ADMIN_URL))
        cls.reader=os.getenv('TEST_DATABASE_URL',os.getenv('DATABASE_URL',DEFAULT_READER_URL))
        cls.schema='salesbench_test_'+uuid.uuid4().hex[:12]
        create_database(cls.admin,schema=cls.schema)
        cls.db=Database(cls.reader,cls.schema)

    @classmethod
    def tearDownClass(cls):
        # Only remove this test run's randomly named schema, never the demo schema.
        with psycopg.connect(cls.admin) as db:
            db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))

    def setUp(self):
        self.args=parser().parse_args([])

    def test_all_three_scenarios(self):
        counts={}
        for variant,runner in RUNNERS.items():
            values=[]
            for task in TASKS:
                b=Backend('demo',self.args)
                state,first=runner(self.db,task,b)
                values.append((assess(self.db,task,first)['success'],assess(self.db,task,state,True)['success']))
            counts[variant]=(sum(v[0] for v in values),sum(v[1] for v in values))
        self.assertEqual(counts,{'workflow':(5,5),'single':(4,5),'mas':(4,6)})

    def test_readonly_and_query_timeout(self):
        forbidden=["DELETE FROM orders", "WITH a AS (SELECT 1) DELETE FROM orders", "WITH removed AS (DELETE FROM orders RETURNING id) SELECT 'x' label,COUNT(*) value FROM removed", "SELECT 1 AS label,2 AS value; DROP TABLE orders"]
        for sql in forbidden:
            with self.subTest(sql=sql),self.assertRaises((ValueError,psycopg.Error)):
                query(self.db,sql)
        with self.assertRaises(psycopg.errors.QueryCanceled):
            query(self.db,"SELECT 'a' label,1 value FROM pg_sleep(0.05)",timeout=0.001)
        self.assertEqual(query(self.db,"SELECT 'orders' label,COUNT(*) value FROM orders")[0]['value'],48)

    def test_reader_has_no_write_or_temp_privileges(self):
        with psycopg.connect(self.reader) as db:
            db.execute('SET TRANSACTION READ WRITE')
            db.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(sql.Identifier(self.schema)))
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                db.execute('DELETE FROM orders')
        with psycopg.connect(self.reader) as db:
            db.execute('SET TRANSACTION READ WRITE')
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                db.execute('CREATE TEMP TABLE should_not_exist(x int)')

    def test_postgresql_date_numeric_and_fixture(self):
        rows=query(self.db,"SELECT to_char(date,'YYYY-MM') label,SUM(total) value FROM orders WHERE status='completed' GROUP BY label")
        self.assertEqual(sorted(r['value'] for r in rows),[4740.0,5115.0,5405.0])
        # Initialization is idempotent without deleting data.
        self.assertFalse(create_database(self.admin,schema=self.schema))

    def test_critic_sees_no_gold_and_repairs_semantics(self):
        b=Backend('demo',self.args)
        state,first=RUNNERS['mas'](self.db,TASKS[4],b)
        self.assertNotIn("status='completed'",first['sql'])
        self.assertIn("status='completed'",state['sql'])
        self.assertEqual(len(state['errors']),1)
        for e in b.events:
            self.assertFalse({'expected','gold','task_id'} & e['request'].keys())

    def test_single_silent_error_survives(self):
        b=Backend('demo',self.args)
        state,_=RUNNERS['single'](self.db,TASKS[4],b)
        self.assertTrue(state['completed'])
        self.assertFalse(assess(self.db,TASKS[4],state,True)['success'])

    def test_duplicate_returns(self):
        b=Backend('demo',self.args)
        state,_=RUNNERS['mas'](self.db,TASKS[5],b)
        self.assertTrue(assess(self.db,TASKS[5],state,True)['success'])
        bad=copy.deepcopy(state)
        bad['rows']=query(self.db,"SELECT c.region label, COUNT(r.order_id)*1.0/COUNT(*) value FROM orders o JOIN customers c ON c.id=o.customer_id LEFT JOIN returns r ON r.order_id=o.id WHERE status='completed' GROUP BY c.region")
        self.assertFalse(assess(self.db,TASKS[5],bad,True)['success'])

    def test_no_final_success_without_verifier(self):
        self.args.max_calls=3
        b=Backend('demo',self.args)
        state,first=RUNNERS['mas'](self.db,TASKS[0],b)
        self.assertTrue(assess(self.db,TASKS[0],first)['success'])
        self.assertFalse(assess(self.db,TASKS[0],state,True)['success'])
        self.assertEqual(b.calls,3)

    def test_numeric_claim_validation(self):
        with self.assertRaises(ValueError):
            make_report([dict(label='x',value=2)],dict(chart='bar',summary='Неподтверждённая сводка',claim=dict(label='x',value=20)))

    def test_live_adapter_and_usage_on_invalid_json(self):
        self.args.model='test-model'
        b=Backend('live',self.args)
        body={'usage':{'prompt_tokens':100,'completion_tokens':20},'choices':[{'message':{'content':'not json'}}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())):
            with self.assertRaises(ValueError):
                b.call('SQL',{'question':'тест'})
        self.assertEqual(b.metrics()['input_tokens'],100)
        self.assertEqual(b.metrics()['output_tokens'],20)
        self.assertEqual(b.metrics()['calls'],1)
        self.assertIsNone(b.metrics()['cost_usd'])

    def test_live_usage_cost_and_payload(self):
        self.args.model='test-model'
        self.args.input_price=1.0
        self.args.output_price=4.0
        b=Backend('live',self.args)
        body={'usage':{'prompt_tokens':100,'completion_tokens':20},'choices':[{'message':{'content':'{"sql":"SELECT 1"}'}}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())) as mock:
            self.assertEqual(b.call('SQL',{'question':'тест'})['sql'],'SELECT 1')
            payload=json.loads(mock.call_args.args[0].data)
            self.assertEqual(payload['model'],'test-model')
            self.assertEqual(payload['max_completion_tokens'],700)
        self.assertAlmostEqual(b.metrics()['cost_usd'],0.00018)

    def test_missing_usage_not_zero(self):
        b=Backend('live',self.args)
        body={'choices':[{'message':{'content':'{"sql":"SELECT 1"}'}}]}
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(body).encode())):
            b.call('SQL',{'question':'тест'})
        self.assertIsNone(b.metrics()['input_tokens'])
        with self.assertRaises(BudgetExceeded):
            b.call('SQL',{'question':'тест'})

    def test_budget_reservation_prevents_request(self):
        self.args.max_tokens=10
        b=Backend('live',self.args)
        with patch('urllib.request.urlopen') as mock,self.assertRaises(BudgetExceeded):
            b.call('SQL',{'question':'тест'})
        mock.assert_not_called()
        self.assertEqual(b.calls,0)


if __name__=='__main__':
    unittest.main()
