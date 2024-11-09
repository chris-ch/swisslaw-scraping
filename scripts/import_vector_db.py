import argparse
import gzip
import json

import chromadb

from helpers import setup_logging_levels


def import_data(vectordb: chromadb.Collection, data_path: str) -> None:
    documents = []
    metadatas = []
    ids = []
    embeddings = []

    # Open file (support GZip if file ends in .gz)
    open_func = gzip.open if data_path.endswith(".gz") else open
    with open_func(data_path, 'rt', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            # Append data to lists for batch addition
            ids.append(entry["uid"])
            embeddings.append(entry["embedding"])
            documents.append(entry["document"])
            metadatas.append(entry["metadata"])

    # Define the batch size
    batch_size = 40000

    # Function to chunk data into batches
    def chunk_data(data, batch_size):
        for i in range(0, len(data), batch_size):
            yield data[i:i + batch_size]

    # Iterate through each chunk
    for doc_chunk, meta_chunk, id_chunk, emb_chunk in zip(
        chunk_data(documents, batch_size),
        chunk_data(metadatas, batch_size),
        chunk_data(ids, batch_size),
        chunk_data(embeddings, batch_size),
    ):
        vectordb.add(
            documents=doc_chunk,
            metadatas=meta_chunk,
            ids=id_chunk,
            embeddings=emb_chunk
        )


def main():

    setup_logging_levels()

    usage = """Importing vectors."""
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                            )
    parser.add_argument('-d', '--distance', choices=["l2", "ip", "cosine"], type=str, help='Distance function', default="cosine")
    parser.add_argument("chromadb_path", type=str, help="Chroma DB Path")
    parser.add_argument("data", type=str, help="Data as jsonl file (may be compressed with GZip). Each line contains a dict with keys 'uid', 'embedding', 'document', 'metadata'")
    args = parser.parse_args()

    # Vector database/Search index
    db_client = chromadb.PersistentClient(
        path=args.chromadb_path,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
        tenant=chromadb.config.DEFAULT_TENANT,
        database=chromadb.config.DEFAULT_DATABASE,
    )
    
    vectordb = db_client.create_collection(name="swiss_legal_articles", metadata={"hnsw:space": args.distance})
    import_data(vectordb, args.data)
    print("Data import complete.")


if __name__ == "__main__":
    main()
