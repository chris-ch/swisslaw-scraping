"""_summary_

    Returns:
        _type_: _description_
"""
import logging
import sys
import time
from typing import List

from chromadb import EmbeddingFunction

from mistralai import Mistral, SDKError


MAX_NUMBER_DOCS = 41666  # ChromaDB limit


class MistralEmbeddingFunction(EmbeddingFunction):
    """_summary_

    Args:
        EmbeddingFunction (_type_): _description_
    """
    def __init__(self, api_key: str, model_deployment: str):
        self._client = Mistral(api_key=api_key)
        self._model = model_deployment

    def __call__(self, documents: List[str]) -> List[float]:
        retries = 5
        backoff_factor = 0.3

        for attempt in range(retries):
            try:
                resp = self._client.embeddings.create(model=self._model, inputs=documents)
                if resp is not None:
                    return [d.embedding for d in resp.data]
            except SDKError as e:
                if e.status_code == 429:
                    wait_time = backoff_factor * (2 ** attempt)
                    logging.info("rate limit exceeded. Retrying in %s seconds...", wait_time)
                    time.sleep(wait_time)
                else:
                    logging.error("raising from embedding function", e)
                    raise  # Re-raise the exception if it's not a rate limit error
            
            # resp is None
            raise RuntimeError("failed to create embedding")

        raise RuntimeError("max retries exceeded. Failed to create embedding.")


class EmbeddingModel:
    """_summary_
    """
    def __init__(self, model_deployment: str, api_key: str, batch_size: int=100):
        """Use API calls to embed content"""
        self.embedding_fun = MistralEmbeddingFunction(
                api_key=api_key,
                model_deployment=model_deployment,
            )
        self.batch_size = batch_size

    def embed(self, docs: List[str])-> List[float]:
        """_summary_

        Args:
            doc (Documents): _description_

        Returns:
            _type_: _description_
        """

        count_batches = len(docs) // self.batch_size
        if len(docs) % self.batch_size != 0:
            count_batches += 1

        embeddings = []
        for batch_idx in range(count_batches):
            idx_start = batch_idx * self.batch_size
            idx_end = (batch_idx + 1) * self.batch_size
            batch = docs[idx_start:idx_end]
            try:
                embeddings += self.embedding_fun(batch)
            except SDKError as e:
                if e.status_code == 400:
                    logging.error("batch processing error: skipping ...", e)
                else:
                    raise  # Re-raise the exception if it's not a rate limit error

            # Progress indicator
            progress = (batch_idx + 1) / count_batches
            bar_length = 30
            filled_length = int(bar_length * progress)
            progress_bar = '=' * filled_length + '-' * (bar_length - filled_length)

            sys.stdout.write(f'\rProgress: [{progress_bar}] {progress:.1%} ({batch_idx + 1}/{count_batches})')
            sys.stdout.flush()

        # Print a newline after the loop completes
        print()

        return embeddings
