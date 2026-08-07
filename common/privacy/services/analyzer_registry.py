# reportline/common/privacy/services/analyzer_registry.py
"""
Registro lazy do engine Presidio — carregado uma vez por processo worker.
"""

from __future__ import annotations

import logging
import threading

from django.conf import settings

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_analyzer_engine = None
_load_failed = False


def get_analyzer_engine():
    """
    Retorna ``AnalyzerEngine`` do Presidio com spaCy em português.

    Retorna ``None`` quando dependências ou modelo spaCy não estiverem
    disponíveis — nesse caso o pipeline usa apenas regex.
    """
    global _analyzer_engine, _load_failed

    if _load_failed:
        return None
    if _analyzer_engine is not None:
        return _analyzer_engine

    with _lock:
        if _load_failed:
            return None
        if _analyzer_engine is not None:
            return _analyzer_engine

        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider
        except ImportError:
            logger.warning(
                "Presidio não instalado; sanitização usará apenas regex institucional."
            )
            _load_failed = True
            return None

        model_name = getattr(settings, "PRESIDIO_SPACY_MODEL", "pt_core_news_lg")
        try:
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "pt", "model_name": model_name}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            _analyzer_engine = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["pt"],
            )
        except Exception:
            logger.exception(
                "Falha ao carregar Presidio/spaCy (%s); usando apenas regex.",
                model_name,
            )
            _load_failed = True
            return None

        return _analyzer_engine
