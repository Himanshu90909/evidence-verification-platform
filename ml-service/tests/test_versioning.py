"""Model versioning: every prediction must record full model metadata."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.versioning import model_info, pipeline_config_hash

import app.config as config


def test_model_info_shape():
    settings = config.Settings(embedding_model="test-emb", nli_model="test-nli")
    info = model_info(settings, {"nli_backend": "transformers", "corpus_documents": 100})
    assert info["model"] == "hybrid-bm25-dense-nli"
    assert info["version"] == "1.0.0"
    assert info["embedding_model"] == "test-emb"
    assert info["nli_model"] == "test-nli"
    assert info["retriever"]
    assert info["config_hash"]
    assert info["temperature"] == settings.temperature


def test_config_hash_stable_and_sensitive():
    s1 = config.Settings(embedding_model="a", nli_model="b")
    s2 = config.Settings(embedding_model="a", nli_model="b")
    s3 = config.Settings(embedding_model="a", nli_model="c")
    assert pipeline_config_hash(s1) == pipeline_config_hash(s2)
    assert pipeline_config_hash(s1) != pipeline_config_hash(s3)
