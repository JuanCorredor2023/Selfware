#    Copyright 2026 [name of copyright owner]
from pydantic import BaseModel
from typing import Literal
import datetime

# ContextItem(id, source, text, ts, hash, para_path, meta)
class ContextItem(BaseModel):
    id : str
    source : Literal["gmail"]    # A futuro va a haber más posible sources
    text : str
    ts : datetime
    hash : str
    para_path : str | None          # None es temporal
    meta : dict

# Chunk(text, item_id, para_path, ts, score)
class Chunk(BaseModel):
    text : str
    item_id : str
    para_path : str | None
    ts : datetime
    score : float

class Provenance(BaseModel):
    para_path : str | None
    source_items_ids : list[str]
    dates: list[datetime]

class Answer(BaseModel):
    text: str
    confidence: float               # 0–1
    provenance: list[Chunk]
    used_web: bool
    tier_calls: list["TierCall"]

# TierCall(model, tokens_in, tokens_out, latency_ms, cost_usd)
class TierCall(BaseModel):
    model : str
    tokens_in : int # cambiar a long long prob, no se como es en python
    tokens_out : int 
    latency_ms : int
    cost_usd : float # o double? 
