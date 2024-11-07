import argparse
import os

import chromadb

from embedding import EmbeddingModel
from helpers import setup_logging_levels


def main():

    setup_logging_levels()

    usage = """Looking for similar vectors in Chroma DB.
    Requires environment variable MISTRAL_API_KEY.
    """
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    
    parser.add_argument("-m", "--embedding-model", required=False, default="mistral-embed",
                        action="store", type=str, dest="embedding_model", help="Embedding model")
    parser.add_argument('-b', '--batch-size', type=int, help='Batch size for reducing requests rate', default=1)
    parser.add_argument("chromadb_path", type=str, help="Chroma DB Path")
    parser.add_argument("request", type=str, help="User request")

    args = parser.parse_args()

    embedding_api_key = os.environ.get("MISTRAL_API_KEY")

    embedding_model = EmbeddingModel(
        model_deployment=args.embedding_model,
        api_key=embedding_api_key,
        batch_size=args.batch_size
    )

    # Vector database/Search index
    db_client = chromadb.PersistentClient(
        path=args.chromadb_path,
        settings=chromadb.config.Settings(anonymized_telemetry=False),
        tenant=chromadb.config.DEFAULT_TENANT,
        database=chromadb.config.DEFAULT_DATABASE,
    )
    
    vectordb = db_client.get_or_create_collection(name="swiss_legal_articles")
    
    embedding_response = embedding_model.embed([args.request])
    if len(embedding_response) != 1:
        raise RuntimeError(f"returned inconsistent embedding: {embedding_response}")
    
    request_vector = embedding_response[0]

    print(f"request vector size: {len(request_vector)}")
    
    matches = vectordb.query(request_vector, n_results=5)
    print(matches)


if __name__ == "__main__":
    main()
