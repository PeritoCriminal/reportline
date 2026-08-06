"""
Utilitários de allowlist para preservar termos durante sanitização Presidio.
"""

from __future__ import annotations

import unicodedata


def fold_text_for_allowlist(value: str) -> str:
    """Normaliza texto para comparação insensível a acentos e caixa."""
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def build_folded_text_index_map(text: str) -> tuple[str, list[int]]:
    """
    Gera versão normalizada do texto e mapa de índices para o original.

    Cada posição em ``folded`` corresponde a um índice no texto de origem.
    """
    folded_chars: list[str] = []
    index_map: list[int] = []
    for index, char in enumerate(text):
        for part in unicodedata.normalize("NFKD", char):
            if unicodedata.combining(part):
                continue
            folded_chars.append(part.lower())
            index_map.append(index)
    return "".join(folded_chars), index_map


def find_protected_spans(text: str, allowlist: tuple[str, ...]) -> list[tuple[int, int]]:
    """Localiza intervalos do texto original cobertos por termos da allowlist."""
    if not text or not allowlist:
        return []

    folded_text, index_map = build_folded_text_index_map(text)
    if not folded_text:
        return []

    spans: list[tuple[int, int]] = []
    for term in sorted(set(allowlist), key=len, reverse=True):
        folded_term = fold_text_for_allowlist(term)
        if not folded_term:
            continue
        start = 0
        while True:
            match_at = folded_text.find(folded_term, start)
            if match_at == -1:
                break
            match_end = match_at + len(folded_term)
            if match_at < len(index_map) and match_end - 1 < len(index_map):
                orig_start = index_map[match_at]
                orig_end = index_map[match_end - 1] + 1
                spans.append((orig_start, orig_end))
            start = match_at + 1

    return merge_spans(spans)


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Funde intervalos sobrepostos ou adjacentes."""
    if not spans:
        return []
    ordered = sorted(spans)
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def span_overlaps(start: int, end: int, protected_spans: list[tuple[int, int]]) -> bool:
    """Indica se o intervalo sobrepõe algum trecho protegido."""
    return any(start < prot_end and end > prot_start for prot_start, prot_end in protected_spans)


def analyzer_result_is_protected(
    *,
    start: int,
    end: int,
    text: str,
    protected_spans: list[tuple[int, int]],
    allowlist: tuple[str, ...],
) -> bool:
    """Indica se um resultado do Presidio deve ser ignorado pela allowlist."""
    if span_overlaps(start, end, protected_spans):
        return True

    snippet = fold_text_for_allowlist(text[start:end])
    if not snippet:
        return False

    allowlist_folded = {fold_text_for_allowlist(term) for term in allowlist}
    return snippet in allowlist_folded


def filter_analyzer_results(
    results,
    *,
    text: str,
    allowlist: tuple[str, ...],
) -> list:
    """Remove detecções do Presidio que intersectam termos da allowlist."""
    if not results or not allowlist:
        return list(results or [])

    protected_spans = find_protected_spans(text, allowlist)
    filtered = []
    for result in results:
        if analyzer_result_is_protected(
            start=result.start,
            end=result.end,
            text=text,
            protected_spans=protected_spans,
            allowlist=allowlist,
        ):
            continue
        filtered.append(result)
    return filtered
