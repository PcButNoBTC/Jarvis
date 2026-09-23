"""Tamper-evident action receipts for consequential agent actions."""
from __future__ import annotations
import hashlib, json

def receipt_hash(previous_hash, payload):
    raw=(previous_hash or "")+"|"+json.dumps(payload,sort_keys=True,separators=(",",":"))
    return hashlib.sha256(raw.encode()).hexdigest()

def make_receipt(*, action, decision, actor, entity_type=None, entity_id=None,
                 cost=0.0, previous_hash=None, metadata=None):
    payload={"action":action,"decision":decision,"actor":actor,"entity_type":entity_type,
             "entity_id":entity_id,"cost":float(cost or 0),"metadata":metadata or {}}
    return {**payload,"previous_hash":previous_hash,"hash":receipt_hash(previous_hash,payload)}
