"""
api/app.py -- Persona 4.

FastAPI. Semana 1 (reinicio): solo /health, para tener el esqueleto
corriendo de punta a punta. Despues se agregan /ask,
/ask?strategy=flat|para, /provenance, /cost, /projects (ver plan,
contrato C3).
"""

from fastapi import FastAPI

app = FastAPI(title="Atlas / Selfware API")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
