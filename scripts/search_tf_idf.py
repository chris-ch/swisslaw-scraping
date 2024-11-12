"""
**TF-IDF (Term Frequency-Inverse Document Frequency)** is a numerical statistic used in information retrieval
and text mining to measure the importance of a word in a document relative to a collection (or "corpus")
of documents.

It helps identify words that are significant within a document  but are not too common across all documents,
making it valuable for tasks like keyword extraction and document similarity analysis.
"""
import argparse
import gzip
import json
import os

import numpy
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from helpers import setup_logging_levels


def main():

    setup_logging_levels()

    usage = """Looking for similarities using TF-IDF.
    """
    parser = argparse.ArgumentParser(description=usage,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter
                                     )
    parser.add_argument("documents_file", type=str, help="Documents file as .jsonl (may be gzipped)")
    parser.add_argument("request", type=str, help="User request")

    args = parser.parse_args()

    articles = []
    is_gzipped = args.documents_file.endswith('.gz')
    open_func = gzip.open if is_gzipped else open

    # Process the file
    with open_func(args.documents_file, 'rt', encoding='utf-8') as file:
        for line in file:
            data = json.loads(line)
            if 'text' in data:
                articles.append(data['text'])
                
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(articles + [args.request])
    similarites = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1]).flatten()
    scores = numpy.argsort(similarites)[::-1]
    top_n = 10
    for article, score in ((articles[i], similarites[i]) for i in scores[:top_n]):
        print(f"---------------------------- score: {score}")
        print(article)
        print()


if __name__ == "__main__":
    main()
