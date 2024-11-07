import argparse
import hashlib
import logging
import os
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

import chromadb

from embedding import EmbeddingModel
from helpers import setup_logging_levels


# Helper function to get the full text from an XML element, including nested tags
def get_full_text(element: ET.Element) -> str:
    return ' '.join(element.itertext()).strip() if element is not None else ""


def load_paragraphs(document_path: str) -> List[Dict[str, str]]:
    # Load the XML document
    try:
        tree = ET.parse(document_path)

    except ET.ParseError as e:
        logging.error("error while parsing %s: skipping %s", e, document_path)
        return []

    root = tree.getroot()

    # Namespaces
    ns = {
        'akn': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0',
        'fedlex': 'http://fedlex.admin.ch/'
    }

    # Extract metadata
    meta_data = root.find('akn:act/akn:meta/akn:identification', ns)
    dates = {
        "document": meta_data.find("akn:FRBRWork/akn:FRBRdate[@name='jolux:dateDocument']", ns).get('date'),
        "entry_in_force": meta_data.find("akn:FRBRWork/akn:FRBRdate[@name='jolux:dateEntryInForce']", ns).get('date'),
        "applicability": meta_data.find("akn:FRBRWork/akn:FRBRdate[@name='jolux:dateApplicability']", ns).get('date')
    }

    # Extract full document title using the helper function
    doc_title_element = root.find('akn:act/akn:preface/akn:p/akn:docTitle', ns)
    doc_title = get_full_text(doc_title_element) if doc_title_element is not None else "Unknown Title"

    logging.info("document title: %s", doc_title)

    # Recursive function to extract paragraphs with context
    def extract_paragraphs(element: Optional[ET.Element], context: Dict[str, str]) -> List[Dict[str, str]]:
        paragraphs = []

        if element is None:
            logging.info("empty element found for context : '%s'", context)
            return paragraphs
        
        # Append paragraph text with current context
        for para in element.findall("akn:paragraph", ns):
            para_text_element = para.find("akn:content/akn:p", ns)
            para_text = get_full_text(para_text_element)
            para_num = get_full_text(para.find("akn:num", ns)) if para.find("akn:num", ns) is not None else ""
            
            # Paragraph with contextual headers
            paragraph_with_context = {
                "doc_title": doc_title,
                "doc_date": dates['document'],
                "entry_in_force": dates['entry_in_force'],
                "applicability": dates['applicability'],
                "section_num": context.get('section_num', ""),
                "section": context.get('section', ""),
                "article_num": context.get('article_num', ""),
                "article": context.get('article', ""),
                "paragraph_number": para_num,
                "paragraph_text": para_text
            }
            
            if paragraph_with_context["paragraph_text"]:
                paragraphs.append(paragraph_with_context)
        
        # Check for articles directly within the body or sections
        for article in element.findall("akn:article", ns):
            article_num = get_full_text(article.find("akn:num", ns))
            article_heading = get_full_text(article.find("akn:heading", ns))
            new_context = {**context, "article_num": article_num, "article": article_heading}
            paragraphs.extend(extract_paragraphs(article, new_context))
        
        # Check for sections and recurse within them if they exist
        for section in element.findall("akn:section", ns):
            section_num = get_full_text(section.find("akn:num", ns))
            section_heading = get_full_text(section.find("akn:heading", ns))
            new_context = {**context, "section_num": section_num, "section": section_heading}
            paragraphs.extend(extract_paragraphs(section, new_context))
        
        return paragraphs
    
    # Initialize extraction with root body context, handle articles directly within the body
    extracted = extract_paragraphs(root.find("akn:act/akn:body", ns), {"section": "", "article": ""})
    if extracted is None:
        extracted = []
    logging.info("%s paragraphs extracted from %s", len(extracted), document_path)
    return extracted


def list_all_files(root_dir: str)-> List[str]:
    # Collect all files from the root directory and subdirectories
    all_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".xml") and not filename.endswith("unavailable.xml"):
                all_files.append(os.path.join(dirpath, filename))

    return all_files


def format_chunks(chunks: List[Dict[str, str]]) -> List[str]:
    formatted_chunks = []
    
    for chunk in chunks:
        # Format each chunk with available metadata and paragraph text
        formatted_chunk = (
            f"Title: {chunk['doc_title']}\n"
            f"Section Number: {chunk['section_num'] or 'N/A'}\n"
            f"Section Title: {chunk['section'] or 'N/A'}\n"
            f"Article Number: {chunk['article_num'] or 'N/A'}\n"
            f"Article Title: {chunk['article'] or 'N/A'}\n"
            f"Paragraph Number: {chunk['paragraph_number'] or 'N/A'}\n"
            f"Paragraph Text: {chunk['paragraph_text']}\n"
        )
        
        formatted_chunks.append(formatted_chunk.strip())  # Remove any trailing whitespace
    
    return formatted_chunks


def main():

    setup_logging_levels()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    usage = """Preparing Chroma Vector Database.
    Requires environment variable MISTRAL_API_KEY.
    """
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    
    parser.add_argument("-m", "--embedding-model", required=False, default="mistral-embed",
                        action="store", type=str, dest="embedding_model", help="Embedding model")
    parser.add_argument('-n', '--skip-embedding', action='store_true', help='Skipping embedding phase, only displays chunks')
    parser.add_argument('-b', '--batch-size', type=int, help='Batch size for reducing requests rate', default=1)
    parser.add_argument("chromadb_path", type=str, help="Chroma DB Path")
    parser.add_argument("documents_folder", type=str, help="Documents folder")

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

    logging.info("processing documents from %s", args.documents_folder)

    documents = sorted(list_all_files(args.documents_folder))
    count_vectors = 0
    for count, document in enumerate(documents):

        logging.info(f"creating vectors for {document}")

        structured_paragraphs = load_paragraphs(document)
        paragraphs = format_chunks(structured_paragraphs)
        if len(paragraphs) == 0:
            logging.warning("unable to extract data from document: %s", document)
            continue

        doc_meta = {
            "doc_url": document[len(args.documents_folder):],
            "doc_date": structured_paragraphs[-1]["doc_date"],
            "entry_in_force": structured_paragraphs[-1]["entry_in_force"],
            "applicability": structured_paragraphs[-1]["applicability"],
        }

        lengths = [len(p) for p in paragraphs]
        print(f"------- processing {len(paragraphs)} paragraphs, for a total of {sum(lengths)} characters (max {max(lengths)}) ")
        if args.skip_embedding:
            for paragraph in paragraphs:
                count_vectors += 1
                print(doc_meta)
                print(paragraph)
            continue

        doc_ids = [hashlib.md5(paragraph.encode()).hexdigest() for paragraph in paragraphs]
        existing_doc_data = vectordb.get(
                ids=doc_ids,
                include=["uris"]
        )
        existing_doc_ids = existing_doc_data['ids']

        new_paragraphs = [p for p, id_ in zip(paragraphs, doc_ids) if id_ not in existing_doc_ids]
        new_doc_ids = [id_ for id_ in doc_ids if id_ not in existing_doc_ids]

        new_vectors = embedding_model.embed(new_paragraphs)

        if len(new_vectors) == 0:
            continue

        logging.info("adding %s vectors to DB", len(new_vectors))

        vectordb.add(
            embeddings=new_vectors,
            documents=new_paragraphs,
            ids=new_doc_ids,
            metadatas=[doc_meta] * len(new_vectors),
        )

    logging.warning("processed %s files out of %s (%s vectors)", count + 1, len(documents), count_vectors)


if __name__ == "__main__":
    main()
