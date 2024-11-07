import argparse
import gzip
import hashlib
import json
import logging
import os
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

from helpers import setup_logging_levels


def get_full_text(element: ET.Element) -> str:
    """Recursively extracts all text from an XML element, preserving order and spacing."""
    texts = []

    if element is None:
        return ""

    # Add element's text, if it exists
    if element.text and element.text.strip():
        texts.append(element.text.strip())
    
    # Recursively get text from each child element
    for child in element:
        texts.append(get_full_text(child))
        
        # Include any tail text that follows the child
        if child.tail and child.tail.strip():
            texts.append(child.tail.strip())
    
    # Join all collected text parts with spaces for readability
    return ' '.join(texts)


def find_paragraphs_with_parents(root: ET.Element, ns):
    # Function to find the full path of parents for each matching element
    def get_parent_chain(element):
        path = []
        while element is not None:
            path.append(element)
            element = element_map.get(element)  # Move to the parent
        return path[::-1]  # Reverse to get root-to-child order

    # Build a map of elements to their parents
    element_map = {child: parent for parent in root.iter() for child in parent}
    paragraphs_with_parents = []

    # Find all `akn:paragraph` elements and retrieve their parent chain
    for paragraph in root.findall(".//akn:paragraph", ns):
        parent_chain = get_parent_chain(paragraph)
        paragraphs_with_parents.append((paragraph, parent_chain))
    
    return paragraphs_with_parents


def single_line(text):
    # Remove newlines and reduce multiple spaces to a single space
    return ' '.join(text.replace('\n', ' ').split())


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
    doc_title = single_line(get_full_text(doc_title_element) if doc_title_element is not None else "Unknown Title")

    logging.info("document title: %s", doc_title)

    def extract_paragraphs(root_element: Optional[ET.Element], context: Dict[str, str]) -> List[Dict[str, str]]:
        paragraphs = []
        if root_element is None:
            logging.info("empty element found for context : '%s'", context)
            return paragraphs

        # Append paragraph text with current context
        for para, parent_chain in find_paragraphs_with_parents(root_element, ns):
            para_text_element = para.find("akn:content", ns)
            para_text = get_full_text(para_text_element)
            para_num = get_full_text(para.find("akn:num", ns)) or ""
            hierarchy = [f"{get_full_text(p.find("akn:num", ns))} {get_full_text(p.find("akn:heading", ns))}" for p in parent_chain if p.tag != "body"]
            hierarchy_text = single_line(" / ".join(hierarchy))

            paragraph_with_context = {
                "doc_title": doc_title,
                "doc_date": dates["document"],
                "entry_in_force": dates["entry_in_force"],
                "applicability": dates["applicability"],
                "hierarchy": hierarchy_text,
                "paragraph_number": para_num,
                "paragraph_text": para_text
            }
            if paragraph_with_context["paragraph_text"]:
                paragraphs.append(paragraph_with_context)

        return paragraphs
    
    # Initialize extraction with root body context, handle articles directly within the body
    extracted = extract_paragraphs(root.find("akn:act/akn:body", ns), {})
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
            f"Hierarchy: {chunk['hierarchy'] or 'N/A'}\n"
            f"Paragraph Number: {chunk['paragraph_number'] or 'N/A'}\n"
            f"Paragraph Text: {chunk['paragraph_text']}\n"
        )
        
        formatted_chunks.append(formatted_chunk.strip())  # Remove any trailing whitespace
    
    return formatted_chunks


def main():

    setup_logging_levels()
    logging.getLogger("httpx").setLevel(logging.WARNING)

    usage = """Generating documents list for embedding."""
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    parser.add_argument("downloads_folder", type=str, help="Raw documents folder")
    parser.add_argument("output_folder", type=str, help="Directory where documents file is saved")

    args = parser.parse_args()

    output_file = f"{args.output_folder}/law_articles.jsonl.gz"

    logging.info("processing documents from %s", args.downloads_folder)

    documents = sorted(list_all_files(args.downloads_folder))
    count_vectors = 0

    with gzip.open(output_file, "wt", encoding="utf-8") as out_file:
        for count_doc, document in enumerate(documents):

            logging.info(f"creating documents for {document}")

            structured_paragraphs = load_paragraphs(document)
            paragraphs = format_chunks(structured_paragraphs)
            if len(paragraphs) == 0:
                logging.warning("unable to extract data from document: %s", document)
                continue

            doc_meta = {
                "doc_url": document[len(args.downloads_folder):],
                "doc_date": structured_paragraphs[-1]["doc_date"],
                "entry_in_force": structured_paragraphs[-1]["entry_in_force"],
                "applicability": structured_paragraphs[-1]["applicability"],
            }

            lengths = [len(p) for p in paragraphs]
            logging.info(f"processing {len(paragraphs)} paragraphs, for a total of {sum(lengths)} characters (max {max(lengths)}) ")

            doc_ids = [hashlib.md5(paragraph.encode()).hexdigest() for paragraph in paragraphs]

            for count_para, paragraph in enumerate(paragraphs):
                count_vectors += 1
                doc_data = doc_meta.copy()
                doc_data.update({"text": paragraph, "uid": doc_ids[count_para]})
                out_file.write(json.dumps(doc_data) + "\n")

        logging.warning("saved under %s: processed %s files out of %s (%s vectors)", os.path.abspath(output_file), count_doc + 1, len(documents), count_vectors)


if __name__ == "__main__":
    main()
