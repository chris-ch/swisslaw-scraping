import asyncio
import logging
import os
import random
from typing import List
import xml.etree.ElementTree as ET


# Helper function to get the full text from an XML element, including nested tags
def get_full_text(element):
    return ' '.join(element.itertext()).strip() if element is not None else ""


async def task(document_path: str):
    # Load the XML document
    logging.info("loading document from %s", document_path)
    tree = ET.parse(document_path)
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

    # Recursive function to extract paragraphs with context
    def extract_paragraphs(element, context):
        paragraphs = []

        if not element:
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
    paragraphs = extract_paragraphs(root.find("akn:act/akn:body", ns), {"section": "", "article": ""})
    for paragraph in paragraphs:
        print("-------------------")
        print(paragraph)


def list_all_files(root_dir: str)-> List[str]:
    # Collect all files from the root directory and subdirectories
    all_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename.endswith(".xml") and not filename.endswith("unavailable.xml"):
                all_files.append(os.path.join(dirpath, filename))

    return all_files


def pick_random_files(root_dir: str, num_files: int=10) -> List[str]:
    all_files = list_all_files(root_dir)
    # If there are fewer than `num_files`, return all files
    if len(all_files) <= num_files:
        return all_files

    # Randomly select `num_files` from all files
    random_files = random.sample(all_files, num_files)
    return random_files


def main():
    #files= pick_random_files("output/downloads", 10):
    files = list_all_files("output/downloads")
    for count, filename in enumerate(files):
        try:
            asyncio.run(task(filename))
        except Exception as err:
            logging.error("failed to process %s: %s", filename, err)
            break

    logging.warning("processed %s files out of %s", count + 1, len(files))
