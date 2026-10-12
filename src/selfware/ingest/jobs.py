from selfware.context.embedder import Embedder
from selfware.context.store import ChromaStore

import selfware.ingest.gmail as gmail_ingest

db_instance = ChromaStore(embedder=Embedder(), path="chroma_data")

gmail_ingest.call_ingest("./fetched_emails.json")
