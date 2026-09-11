"""
weaviate_sink.py — Weaviate Cloud Vector DB manager.

Handles schema setup, local embedding generation, and batch upload
of code chunks to Weaviate Cloud.
"""

import os
import sys

# Fix Anaconda OpenMP duplicate DLL conflict on Windows
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"

# Add PyTorch lib directory to Windows DLL search paths (Python 3.8+)
if sys.platform == "win32":
    torch_lib = os.path.join(sys.prefix, "Lib", "site-packages", "torch", "lib")
    if os.path.exists(torch_lib):
        try:
            os.add_dll_directory(torch_lib)
        except Exception:
            pass

import weaviate
from weaviate.classes.init import Auth
from weaviate.classes.config import Configure, Property, DataType
from weaviate.classes.query import MetadataQuery
from sentence_transformers import SentenceTransformer


class WeaviateCloudCodeDB:
    """
    Complete Weaviate Cloud (WCD) Vector DB Manager.
    Requires ZERO Docker! Connects directly to your free Weaviate Cloud Sandbox.
    """

    def __init__(self, cluster_url: str, api_key: str):
        # Connect to Weaviate Cloud Services
        self.client = weaviate.connect_to_weaviate_cloud(
            cluster_url=cluster_url,
            auth_credentials=Auth.api_key(api_key)
        )
        self.collection_name = "CodeChunk"

        # Embedding model (Gemini Embedding Router across models 1 & 2, or local fallback)
        gemini_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if gemini_key:
            from pipeline.gemini_router import GeminiEmbeddingRouter
            self.gemini_router = GeminiEmbeddingRouter(api_key=gemini_key)
            self.encoder = None
            print("Connected to Weaviate Cloud (Embedding: Gemini Embedding Router [1 & 2]).")
        else:
            self.gemini_router = None
            self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            print("Connected to Weaviate Cloud (Embedding: SentenceTransformer local).")

    def close(self):
        self.client.close()

    def setup_schema(self):
        """Creates the 'CodeChunk' collection on Weaviate Cloud."""
        if self.client.collections.exists(self.collection_name):
            print(f"Collection '{self.collection_name}' exists. Re-creating...")
            self.client.collections.delete(self.collection_name)

        # Configure collection to receive custom vectors generated locally
        self.client.collections.create(
            name=self.collection_name,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=[
                Property(name="node_id", data_type=DataType.TEXT, index_filterable=True, index_searchable=True),
                Property(name="file_path", data_type=DataType.TEXT, index_filterable=True, index_searchable=True),
                Property(name="name", data_type=DataType.TEXT, index_filterable=True, index_searchable=True),
                Property(name="chunk_type", data_type=DataType.TEXT, index_filterable=True),
                Property(name="docstring", data_type=DataType.TEXT, index_searchable=True),
                Property(name="inline_comments", data_type=DataType.TEXT_ARRAY, index_searchable=True),
                Property(name="start_line", data_type=DataType.INT),
                Property(name="end_line", data_type=DataType.INT),
                Property(name="content", data_type=DataType.TEXT, index_searchable=True),
            ]
        )
        print(f"Collection '{self.collection_name}' created on Weaviate Cloud.")

    def _encode_text(self, text: str) -> list[float]:
        if self.gemini_router:
            return self.gemini_router.embed_query(text)
        return self.encoder.encode(text).tolist()

    def _encode_batch(self, texts: list[str]) -> list[list[float]]:
        if self.gemini_router:
            return self.gemini_router.embed_documents(texts)
        return self.encoder.encode(texts, show_progress_bar=False).tolist()

    def insert_code_chunks(self, documents: list):
        """
        Generates vector embeddings and batch uploads them to Weaviate Cloud.
        """
        collection = self.client.collections.get(self.collection_name)

        contents = [doc.page_content for doc in documents]

        print(f"Generating vectors for {len(documents)} code chunks...")
        embeddings = self._encode_batch(contents)

        objects_to_insert = []
        for i, doc in enumerate(documents):
            meta = doc.metadata

            properties = {
                "node_id": meta.get("node_id", ""),
                "file_path": meta.get("file_path", ""),
                "name": meta.get("name", ""),
                "chunk_type": meta.get("chunk_type", ""),
                "docstring": meta.get("docstring", ""),
                "inline_comments": meta.get("inline_comments", []),
                "start_line": meta.get("start_line", 0),
                "end_line": meta.get("end_line", 0),
                "content": doc.page_content
            }

            objects_to_insert.append(
                weaviate.classes.data.DataObject(
                    properties=properties,
                    vector=embeddings[i]
                )
            )

        # Upload batch to Weaviate Cloud
        print("Uploading batch to Weaviate Cloud...")
        collection.data.insert_many(objects_to_insert)
        print(f"Successfully uploaded {len(objects_to_insert)} documents to Weaviate Cloud.")

    def search_code(self, query_text: str, limit: int = 5):
        """
        Performs hybrid (dense vector + BM25 keyword) search on Weaviate Cloud.
        """
        collection = self.client.collections.get(self.collection_name)
        objs = []

        # 1. Try Hybrid Search (dense vector + BM25 keywords)
        try:
            query_vector = self._encode_text(query_text)
            response = collection.query.hybrid(
                query=query_text,
                vector=query_vector,
                limit=limit,
                alpha=0.5,
            )
            objs = response.objects
        except Exception:
            objs = []

        # 2. Fallback to BM25 keyword search if hybrid returns 0
        if not objs:
            try:
                response = collection.query.bm25(
                    query=query_text,
                    limit=limit,
                )
                objs = response.objects
            except Exception:
                objs = []

        results = []
        for obj in objs:
            results.append({
                "node_id": obj.properties.get("node_id"),
                "file_path": obj.properties.get("file_path"),
                "name": obj.properties.get("name"),
                "chunk_type": obj.properties.get("chunk_type"),
                "docstring": obj.properties.get("docstring"),
                "inline_comments": obj.properties.get("inline_comments"),
                "content": obj.properties.get("content"),
                "distance": getattr(obj.metadata, "distance", None)
            })
        return results
