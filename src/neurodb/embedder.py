try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]

MODEL_NAME = "allenai/specter2_base"


class Embedder:
    """Lazy-loading SPECTER2 wrapper. Model is downloaded on first embed() call."""

    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model.encode(texts, normalize_embeddings=True).tolist()
