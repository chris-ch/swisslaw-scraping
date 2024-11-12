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


# Function to find the full path of parents for each matching element
def get_parent_chain(element: ET.Element, element_map: Dict[ET.Element, ET.Element]) -> List[ET.Element]:
    path = []
    while element is not None:
        path.append(element)
        element = element_map.get(element)  # Move to the parent
    return path[::-1]  # Reverse to get root-to-child order


def find_articles_with_parents(root: ET.Element, ns):

    # Build a map of elements to their parents
    element_map = {child: parent for parent in root.iter() for child in parent}
    articles_with_parents = []

    # Find all `akn:article` elements and retrieve their parent chain
    for article in root.findall(".//akn:article", ns):
        parent_chain = get_parent_chain(article, element_map)
        articles_with_parents.append((article, parent_chain))
    
    return articles_with_parents


def find_first_level_with_parents(root: ET.Element, ns):
    # Build a map of elements to their parents
    element_map = {child: parent for parent in root.iter() for child in parent}
    levels_with_parents = []

    # Find all "level" elements
    all_levels = root.findall(".//akn:level", ns)

    # Filter to get only the "last level" elements (those with no child "level" elements)
    last_levels = [level for level in all_levels if not level.findall(".//akn:level", ns)]

    for level in last_levels:
        parent_chain = get_parent_chain(level, element_map)
        levels_with_parents.append((level, parent_chain))
    
    return levels_with_parents


def single_line(text):
    # Remove newlines and reduce multiple spaces to a single space
    return ' '.join(text.replace('\n', ' ').split())


def load_articles(document_path: str) -> List[Dict[str, str]]:
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

    def extract_items(items_with_parents) -> List[Dict[str, str]]:
        items = []
        # Append item text with current context
        for item, parent_chain in items_with_parents:
            item_text = get_full_text(item)
            item_num = get_full_text(item.find("akn:num", ns)) or ""
            hierarchy = [f"{get_full_text(p.find("akn:num", ns))} {get_full_text(p.find("akn:heading", ns))}" for p in parent_chain if p.tag != "body"]
            hierarchy_text = single_line(" / ".join(hierarchy))

            item_with_context = {
                "doc_title": doc_title,
                "doc_date": dates["document"],
                "entry_in_force": dates["entry_in_force"],
                "applicability": dates["applicability"],
                "hierarchy": hierarchy_text,
                "article_number": item_num,
                "article_text": item_text
            }
            if item_with_context["article_text"]:
                items.append(item_with_context)

        return items
    
    body = root.find("akn:act/akn:body", ns)
    if body is None:
        return []
    
    # Initialize extraction with root body context, handle articles directly within the body
    articles_with_parents = find_articles_with_parents(body, ns)
    extracted = extract_items(articles_with_parents)
    if len(extracted) == 0:
        # try splitting using 1st level
        first_level_with_parents = find_first_level_with_parents(body, ns)
        extracted = extract_items(first_level_with_parents)
        if len(extracted) == 0:
            extracted = [{
                    "doc_title": doc_title,
                    "doc_date": dates["document"],
                    "entry_in_force": dates["entry_in_force"],
                    "applicability": dates["applicability"],
                    "hierarchy": "N/A",
                    "article_number": "N/A",
                    "article_text": get_full_text(root)
                }
            ]
    
    logging.info("%s articles extracted from %s", len(extracted), document_path)
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
        # Format each chunk with available metadata and article text
        formatted_chunk = (
            f"Title: {chunk['doc_title']}\n"
            f"Hierarchy: {chunk['hierarchy'] or 'N/A'}\n"
            f"Article Number: {chunk['article_number'] or 'N/A'}\n"
            f"Article Text: {chunk['article_text']}\n"
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

            structured_articles = load_articles(document)
            articles = format_chunks(structured_articles)
            if len(articles) == 0:
                logging.warning("unable to extract data from document: %s", document)
                continue

            doc_meta = {
                "doc_url": document[len(args.downloads_folder):],
                "doc_date": structured_articles[-1]["doc_date"],
                "entry_in_force": structured_articles[-1]["entry_in_force"],
                "applicability": structured_articles[-1]["applicability"],
            }

            lengths = [len(p) for p in articles]
            logging.info(f"processing {len(articles)} articles, for a total of {sum(lengths)} characters (max {max(lengths)}) ")

            doc_ids = [hashlib.md5(article.encode()).hexdigest() for article in articles]

            for count_para, article in enumerate(articles):
                count_vectors += 1
                doc_data = doc_meta.copy()
                doc_data.update({"text": article, "uid": doc_ids[count_para]})
                out_file.write(json.dumps(doc_data) + "\n")

        logging.warning("saved under %s: processed %s files out of %s (%s vectors)", os.path.abspath(output_file), count_doc + 1, len(documents), count_vectors)


if __name__ == "__main__":
    main()
