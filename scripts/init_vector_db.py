"""
Embedding: Importing documents into Vector Database
"""

import argparse
import glob
import logging
import os
import sys
from typing import List
import uuid
import bs4
import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from embedding import EmbeddingModel
from helpers import setup_logging_levels


def _load_and_split_document(f_path: str,
                             splitter: RecursiveCharacterTextSplitter,
                             chunk_size: int) -> List[str]:
    """Load the document (html page), extract the section tags."""
    with open(f_path, mode="r", encoding="utf8") as f:
        soup = bs4.BeautifulSoup(f.read(), 'html.parser')
        sections = soup.find_all("section")

    chunks = []
    for sec in sections:
        # heuristic to keep only legal text
        if "Art" in sec.text and len(sec.text) > 10:
            if len(sec.text) > chunk_size:
                chunks += splitter.split_text(sec.text)
            else:
                chunks.append(sec.text)
    return chunks


def analyze_string_lengths(chunks: List[str]):
    """_summary_

    Args:
        chunks (List[str]): _description_
    """
    if not chunks:
        print("The list is empty.")
        return

    lengths = [len(chunk) for chunk in chunks]

    avg_length = sum(lengths) / len(lengths)
    min_length = min(lengths)
    max_length = max(lengths)

    print(f"Average string length: {avg_length:.0f}")
    print(f"Minimum string length: {min_length}")
    print(f"Maximum string length: {max_length}")


def main():
    """Preparing Chroma Vector Database"""

    setup_logging_levels()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    usage = """Preparing Chroma Vector Database.
    Requires environment variable MISTRAL_API_KEY.
    """
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    parser.add_argument("-s", "--chunk-size", required=False, default=2000,
                        action="store", type=int, dest="chunk_size", help="Chunk size")
    parser.add_argument("-o", "--chunk-overlap", required=False, default=100,
                        action="store", type=int, dest="chunk_overlap", help="Chunk overlap")
    parser.add_argument("-m", "--embedding-model", required=False, default="mistral-embed",
                        action="store", type=str, dest="embedding_model", help="Embedding model")
    parser.add_argument('-n', '--skip-embedding', action='store_true', help='Skipping embedding phase, only displays chunks')
    parser.add_argument("knowledge_folder", type=str, help="Knowledge folder")
    parser.add_argument("batch_size", type=int, help="Batch size for reducing requests rate")
    args = parser.parse_args()

    embedding_api_key = os.environ.get("MISTRAL_API_KEY")

    embedding_model = EmbeddingModel(
        model_deployment=args.embedding_model,
        api_key=embedding_api_key,
        batch_size=args.batch_size
    )

    # Vector database/Search index
    db_client = chromadb.PersistentClient(
        path="chroma",
        settings=chromadb.config.Settings(anonymized_telemetry=False),
        tenant=chromadb.config.DEFAULT_TENANT,
        database=chromadb.config.DEFAULT_DATABASE,
    )
    
    vectordb = db_client.get_or_create_collection(name="swiss_legal_articles")
    logging.info("processing documents from %s", args.knowledge_folder)

    # Collect all the files to process
    all_files = glob.glob(
        f"{args.knowledge_folder}/**/**/**.html", recursive=True)

    # Load & slice the documents by section/articles
    chunks: List[str] = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        length_function=len,
    )
    for f_path in all_files:
        # TODO: store metadata
        logging.info("slicing %s into chunks", f_path)
        chunks += _load_and_split_document(f_path, splitter, args.chunk_size)

    analyze_string_lengths(chunks)

    if args.skip_embedding:
        for chunk in chunks:
            print(chunk)

        sys.exit(0)

    # Embed the content
    logging.info("embedding %s chunks", len(chunks))
    vectors = embedding_model.embed(chunks)

    # Create ids for each chunk
    ids = [str(uuid.uuid4()) for _ in range(len(chunks))]

    logging.info("adding vectors to DB")

    vectordb.add(
        embeddings=vectors,
        documents=chunks,
        ids=ids,
        metadatas=None,
    )


if __name__ == "__main__":
    main()
