import argparse
import gzip
import json
import logging
import os
from typing import Dict, List

import chromadb

from embedding import EmbeddingModel
from helpers import setup_logging_levels


def load_jsonl(file_path: str) -> List[Dict[str, str]]:
    data = []
    open_func = gzip.open if file_path.endswith('.gz') else open
    
    with open_func(file_path, 'rt', encoding='utf-8') as f:
        for line in f:
            data.append(json.loads(line.strip()))
    
    return data


def embed_and_store(embedding_model: EmbeddingModel, vectordb: chromadb.Collection, new_documents: List[str]) -> None:
    new_documents_text = [item["text"] for item in new_documents]
    new_documents_uid = [item["uid"] for item in new_documents]
    new_vectors = embedding_model.embed(new_documents_text)
    doc_metadata = [
        {
            "doc_url": document["doc_url"],
            "doc_date": document["doc_date"],
            "entry_in_force": document["entry_in_force"],
            "applicability": document["applicability"]
        } for document in new_documents
    ]
    vectordb.add(
        embeddings=new_vectors,
        documents=new_documents_text,
        ids=new_documents_uid,
        metadatas=doc_metadata,
    )


def batch_process_documents(embedding_model, vectordb, new_documents, batch_size=1000):
    for i in range(0, len(new_documents), batch_size):
        batch = new_documents[i:i + batch_size]
        embed_and_store(embedding_model, vectordb, batch)
        logging.info("stored %s elements in db", len(batch))


def main():

    setup_logging_levels()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    usage = """Setting up Chroma Vector Database.
    Requires environment variable MISTRAL_API_KEY.
    """
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    
    parser.add_argument("-m", "--embedding-model", required=False, default="mistral-embed",
                        action="store", type=str, dest="embedding_model", help="Embedding model")
    parser.add_argument('-b', '--batch-size', type=int, help='Batch size for reducing requests rate', default=20)
    parser.add_argument("chromadb_path", type=str, help="Chroma DB Path")
    parser.add_argument("documents_file", type=str, help="Documents file as .jsonl (may be gzipped)")

    args = parser.parse_args()

    embedding_api_key = os.environ.get("MISTRAL_API_KEY")

    db_client = chromadb.PersistentClient(
        path=args.chromadb_path,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
        tenant=chromadb.config.DEFAULT_TENANT,
        database=chromadb.config.DEFAULT_DATABASE,
    )
    
    embedding_model = EmbeddingModel(
        model_deployment=args.embedding_model,
        api_key=embedding_api_key,
        batch_size=args.batch_size
    )

    vectordb = db_client.get_or_create_collection(name="swiss_legal_articles")
    documents = load_jsonl(args.documents_file)
    doc_ids = [item["uid"] for item in documents if "uid" in item]

    logging.info("processing documents from %s", args.documents_file)
    logging.info("loaded %s documents", len(documents))
    logging.info("found %s uids", len(doc_ids))

    lookup_ids_batch_size = 10000
    existing_doc_ids = []

    for i in range(0, len(doc_ids), lookup_ids_batch_size):
        batch = doc_ids[i:i + lookup_ids_batch_size]
        result = vectordb.get(ids=batch, include=["uris"])
        existing_doc_ids.extend(result['ids'])  # Append each batch's results to the final list

    logging.info("gathered %s existing ids from database", len(existing_doc_ids))

    new_documents = [d for d in documents if d["uid"] not in existing_doc_ids]

    batch_process_documents(embedding_model, vectordb, new_documents, batch_size=1000)

    logging.warning("processed %s files", len(documents))


if __name__ == "__main__":
    main()
