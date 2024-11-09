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


def embed(embedding_model: EmbeddingModel, documents: List[str]) -> None:
    documents_text = [item["text"] for item in documents]
    documents_uid = [item["uid"] for item in documents]
    vectors = embedding_model.embed(documents_text)
    doc_metadata = [
        {
            "doc_url": document["doc_url"],
            "doc_date": document["doc_date"],
            "entry_in_force": document["entry_in_force"],
            "applicability": document["applicability"]
        } for document in documents
    ]
    results = []
    for doc_text, doc_uid, vector, metadata in zip(documents_text, documents_uid, vectors, doc_metadata):
        results.append(
            {"uid": doc_uid, "embedding": vector.tolist(), "document": doc_text, "metadata": metadata}
        )
    return results


def batch_process_documents(output_file, embedding_model, documents, batch_size=1000):
    for i in range(0, len(documents), batch_size):
        batch = documents[i:i + batch_size]
        rows = embed(embedding_model, batch)
        with open(output_file, "a") as f:
            for row in rows:
                f.write(json.dumps(row) + "\n")  # Write each dictionary as a JSON line

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
    parser.add_argument('-b', '--batch-size', type=int, help='Batch size for reducing requests rate', default=5)
    parser.add_argument("documents_file", type=str, help="Documents file as .jsonl (may be gzipped)")

    args = parser.parse_args()

    embedding_api_key = os.environ.get("MISTRAL_API_KEY")

    embedding_model = EmbeddingModel(
        model_deployment=args.embedding_model,
        api_key=embedding_api_key,
        batch_size=args.batch_size
    )

    documents = load_jsonl(args.documents_file)

    logging.info("processing documents from %s", args.documents_file)
    logging.info("loaded %s documents", len(documents))

    vectors_file = "output/law_vectors.jsonl"

    os.makedirs(os.path.dirname(vectors_file), exist_ok=True)

    # Create the empty file if it does not exist
    with open(vectors_file, 'a') as file:
        pass  # 'pass' is used to create the file without adding any content

    stored_uids = set()

    # Open and read the jsonl file
    with open(vectors_file, 'r') as file:
        for line in file:
            # Parse each line as a JSON object
            data = json.loads(line)
            stored_uids.add(data['uid'])
    
    new_documents = [d for d in documents if d["uid"] not in stored_uids]
    logging.info("remaining %s documents", len(new_documents))
    batch_process_documents(vectors_file, embedding_model, new_documents, batch_size=1000)

    logging.warning("processed %s documents", len(new_documents))


if __name__ == "__main__":
    main()
