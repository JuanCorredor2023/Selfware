import selfware.ingest.gmail as gmail_ingest
from selfware.context.embedder import Embedder
from selfware.context.store import ChromaStore

# This file is still incomplete
db_instance = ChromaStore(embedder=Embedder(), path="chroma_data")

messages = gmail_ingest.call_ingest()
db_instance.add_documents(messages)
