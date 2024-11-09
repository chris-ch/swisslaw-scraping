import argparse
import json

import chromadb

from helpers import setup_logging_levels


def main():

    setup_logging_levels()

    usage = """Exporting current entries."""
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    parser.add_argument("chromadb_path", type=str, help="Chroma DB Path")
    args = parser.parse_args()

    # Vector database/Search index
    db_client = chromadb.PersistentClient(
        path=args.chromadb_path,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
        tenant=chromadb.config.DEFAULT_TENANT,
        database=chromadb.config.DEFAULT_DATABASE,
    )
    
    vectordb = db_client.get_collection(name="swiss_legal_articles")
    included_fields = [chromadb.api.types.IncludeEnum.metadatas,
                       chromadb.api.types.IncludeEnum.documents,
                       chromadb.api.types.IncludeEnum.embeddings]
    docs = vectordb.get(include=included_fields)
    rows = zip(docs["ids"], docs["embeddings"], docs["documents"], docs["metadatas"])

    output_file = "chromadb_export.jsonl"
    with open(output_file, "w") as f:
        for row in rows:
            line = {
                "uid": row[0],
                "embedding": row[1].tolist(),  # Convert ndarray to list for JSON serialization
                "document": row[2],
                "metadata": row[3]
            }
            f.write(json.dumps(line) + "\n")  # Write each dictionary as a JSON line

    print(f"Data exported to {output_file}")


if __name__ == "__main__":
    main()
