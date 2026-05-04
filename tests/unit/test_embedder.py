from unittest.mock import MagicMock, patch
from neurodb.embedder import Embedder


def test_model_not_loaded_on_init():
    embedder = Embedder()
    assert embedder._model is None


def test_embed_loads_model_lazily():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2, 0.3]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        result = embedder.embed(["test text"])

    mock_cls.assert_called_once_with("allenai/specter2_base")
    assert result == [[0.1, 0.2, 0.3]]


def test_embed_does_not_reload_model_on_second_call():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        embedder.embed(["first"])
        embedder.embed(["second"])

    mock_cls.assert_called_once()  # model constructed only once


def test_embed_returns_list_of_float_lists():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2], [0.3, 0.4]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model):
        result = embedder.embed(["text one", "text two"])

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(v, float) for v in result[0])


def test_embed_passes_normalize_embeddings_true():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.5]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model):
        embedder.embed(["text"])

    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


def test_custom_model_name_passed_to_sentence_transformer():
    embedder = Embedder(model_name="custom/model")
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        embedder.embed(["text"])

    mock_cls.assert_called_once_with("custom/model")
