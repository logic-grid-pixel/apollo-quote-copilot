"""A small in-memory stand-in for simple_salesforce used by the unit tests."""

import itertools
import re

PREFIX = {"Quote": "0Q0", "QuoteLineItem": "0QL", "ContentVersion": "068", "Task": "00T",
          "Opportunity": "006", "ContentDocument": "069"}


class FakeError(Exception):
    pass


class FakeSObject:
    def __init__(self, name, sf):
        self.name, self.sf = name, sf

    def create(self, data):
        hook = self.sf.fail_on.get(self.name)
        if hook and hook(data):
            raise FakeError(f"{self.name} create refused: {data}")
        new_id = f"{PREFIX.get(self.name, '001')}{next(self.sf.counter):012d}"
        self.sf.created.append((self.name, new_id, dict(data)))
        return {"id": new_id, "success": True, "errors": []}

    def upsert(self, key, data):
        self.sf.upserts.append((self.name, key, dict(data)))
        return 201

    def delete(self, record_id):
        self.sf.deleted.append((self.name, record_id))
        return 204


class FakeSF:
    """query()/query_all() answer from `responses`: list of (regex, records)."""

    def __init__(self, responses=None, fail_on=None):
        self.responses = list(responses or [])
        self.fail_on = fail_on or {}
        self.counter = itertools.count(1)
        self.created, self.deleted, self.upserts, self.queries = [], [], [], []

    def __getattr__(self, name):
        if name[0].isupper():
            return FakeSObject(name, self)
        raise AttributeError(name)

    def query(self, soql):
        self.queries.append(soql)
        for pattern, records in self.responses:
            if re.search(pattern, soql, re.IGNORECASE | re.DOTALL):
                recs = records(soql) if callable(records) else records
                return {"records": list(recs), "totalSize": len(recs), "done": True}
        return {"records": [], "totalSize": 0, "done": True}

    query_all = query

    def created_of(self, sobject):
        return [(i, d) for n, i, d in self.created if n == sobject]
