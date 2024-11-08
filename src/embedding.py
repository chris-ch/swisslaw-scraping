"""_summary_

    Returns:
        _type_: _description_
"""
import logging
import sys
import time
from typing import List

from chromadb import EmbeddingFunction
from chromadb.api.types import Document, Embedding

from mistralai import EmbeddingResponse, Mistral, SDKError


MAX_NUMBER_DOCS = 41666  # ChromaDB limit


class MistralEmbeddingFunction(EmbeddingFunction):
    """_summary_

    Args:
        EmbeddingFunction (_type_): _description_
    """
    def __init__(self, api_key: str, model_deployment: str, batch_size: int=200):
        self._client = Mistral(api_key=api_key)
        self._model = model_deployment
        self._batch_size = batch_size

    def __call__(self, docs: List[Document]) -> List[Embedding]:
        all_embeddings = []
        
        for i in range(0, len(docs), self._batch_size):
            batch = docs[i:i + 100]
            embeddings_batch_response = self.managed_request(batch)
            all_embeddings.extend([entry.embedding for entry in embeddings_batch_response.data])
        
        return all_embeddings
    
    def managed_request(self, batch: List[Document]) -> EmbeddingResponse:
        retries = 5
        backoff_factor = 0.3

        for attempt in range(retries):
            try:
                logging.info("processing inputs: %s", [len(b) for b in batch])
                resp = self._client.embeddings.create(model=self._model, inputs=batch)
                if resp is None:
                    raise RuntimeError("Failed to create embedding")
                return resp
            except SDKError as e:
                if e.status_code == 429:
                    wait_time = backoff_factor * (2 ** attempt)
                    logging.info("Rate limit exceeded. Retrying in %s seconds...", wait_time)
                    time.sleep(wait_time)
                else:
                    raise  # Re-raise the exception if it's not a rate limit error

        raise RuntimeError("Max retries exceeded. Failed to create embedding.")


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

    def embed(self, docs: List[Document])-> List[Embedding]:
        """_summary_

        Args:
            doc (Documents): _description_

        Returns:
            _type_: _description_
        """

        count_batches = len(docs) // self.batch_size
        if len(docs) % self.batch_size != 0:
            count_batches += 1

        if False and len(docs) > MAX_NUMBER_DOCS:
            msg = f"resulting batch size {len(docs)} exceeding maximum of {
                MAX_NUMBER_DOCS}, populate using smaller datasets."
            logging.error(msg)
            raise RuntimeError(msg)

        embeddings = []
        for batch_idx in range(count_batches):
            idx_start = batch_idx * self.batch_size
            idx_end = (batch_idx + 1) * self.batch_size
            batch = docs[idx_start:idx_end]
            embeddings += self.embedding_fun(batch)

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
