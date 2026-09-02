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

        # Local embedding model (converts code into 384-dim vectors)
        self.encoder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        print("Connected to Weaviate Cloud successfully.")

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

    def insert_code_chunks(self, documents: list):
        """
        Generates vector embeddings locally and batch uploads them to Weaviate Cloud.
        """
        collection = self.client.collections.get(self.collection_name)

        contents = [doc.page_content for doc in documents]

        print(f"Generating vectors for {len(documents)} code chunks...")
        embeddings = self.encoder.encode(contents, show_progress_bar=False).tolist()

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
        Encodes query string into a vector and searches Weaviate Cloud.
        """
        collection = self.client.collections.get(self.collection_name)

        query_vector = self.encoder.encode(query_text).tolist()

        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            return_metadata=MetadataQuery(distance=True)
        )

        results = []
        for obj in response.objects:
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
