import unittest
import tempfile
import shutil
from pathlib import Path

from core.issue import Severity, Layer
from core.scorer import Scorer
from analyzers.angular_analyzer import AngularAnalyzer
from analyzers.react_analyzer import ReactAnalyzer
from analyzers.node_analyzer import NodeAnalyzer
from analyzers.sql_analyzer import SqlAnalyzer
from analyzers.aws_analyzer import AwsAnalyzer

class TestAnalyzers(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.path = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_angular_onpush_detection(self):
        ts_file = self.path / 'user.component.ts'
        ts_file.write_text("""
import { Component } from '@angular/core';

@Component({
  selector: 'app-user',
  template: '<div>User</div>'
})
export class UserComponent {}
""", encoding='utf-8')

        analyzer = AngularAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertTrue(any(i.id == 'ANG001' for i in issues))
        ang001 = next(i for i in issues if i.id == 'ANG001')
        self.assertIsNotNone(ang001.line_number)
        self.assertEqual(ang001.layer, Layer.FRONTEND)

    def test_angular_suppression(self):
        ts_file = self.path / 'suppressed.component.ts'
        ts_file.write_text("""
import { Component } from '@angular/core';

// perf-ignore ANG001
@Component({
  selector: 'app-suppressed',
  template: '<div>Suppressed</div>'
})
export class SuppressedComponent {}
""", encoding='utf-8')

        analyzer = AngularAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertFalse(any(i.id == 'ANG001' for i in issues))

    def test_node_n_plus_one(self):
        js_file = self.path / 'order.service.js'
        js_file.write_text("""
async function processOrders(orders) {
  for (const order of orders) {
    order.items = await db.query("SELECT * FROM items WHERE order_id = ?", [order.id]);
  }
}
""", encoding='utf-8')

        analyzer = NodeAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertTrue(any(i.id == 'NODE004' for i in issues))
        node004 = next(i for i in issues if i.id == 'NODE004')
        self.assertEqual(node004.severity, Severity.CRITICAL)
        self.assertEqual(node004.layer, Layer.BACKEND)

    def test_sql_missing_fk_index(self):
        sql_file = self.path / 'schema.sql'
        sql_file.write_text("""
CREATE TABLE order_items (
  id INT PRIMARY KEY,
  order_id INT NOT NULL,
  price DECIMAL(10,2)
);
""", encoding='utf-8')

        analyzer = SqlAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertTrue(any(i.id == 'SQL004' for i in issues))
        sql004 = next(i for i in issues if i.id == 'SQL004')
        self.assertIn('order_items', sql004.title)

    def test_aws_lambda_memory(self):
        yml_file = self.path / 'serverless.yml'
        yml_file.write_text("""
service: payment-api
provider:
  name: aws
  runtime: nodejs18.x
  memorySize: 128
""", encoding='utf-8')

        analyzer = AwsAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertTrue(any(i.id == 'AWS001' for i in issues))

    def test_react_missing_dependency(self):
        jsx_file = self.path / 'UserList.jsx'
        jsx_file.write_text("""
import React, { useEffect, useState } from 'react';

export function UserList() {
  const [users, setUsers] = useState([]);

  useEffect(() => {
    fetch('/api/users').then(r => r.json()).then(setUsers);
  });

  return <div>{users.map((u, index) => <span key={index}>{u.name}</span>)}</div>;
}
""", encoding='utf-8')

        analyzer = ReactAnalyzer(str(self.path))
        issues = analyzer.analyze()
        self.assertTrue(any(i.id == 'REACT003' for i in issues))
        self.assertTrue(any(i.id == 'REACT001' for i in issues))

    def test_scorer_diminishing_returns(self):
        scorer = Scorer()
        ts_file = self.path / 'dummy.component.ts'
        ts_file.write_text("@Component({ selector: 'x' }) export class X {}", encoding='utf-8')
        issues = AngularAnalyzer(str(self.path)).analyze()
        scores = scorer.compute(issues)
        self.assertGreater(scores['overall'], 0)
        self.assertLessEqual(scores['overall'], 100)

if __name__ == '__main__':
    unittest.main()
