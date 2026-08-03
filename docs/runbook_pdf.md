# Runbook — exportação PDF do laudo (Playwright)

Procedimento para habilitar `GET /reports/<uuid>/document/` em ambientes de servidor.

## Dependências

```bash
pip install -r requirements-server.txt
playwright install chromium
```

O comando `playwright install chromium` baixa o binário do Chromium usado pelo Playwright em modo headless.

## Verificação rápida

1. Autentique-se como autor de um laudo.
2. Abra `/reports/<uuid>/document/?html=1` — deve retornar HTML contínuo (sem script de paginação).
3. Abra `/reports/<uuid>/document/` — deve retornar `application/pdf` inline.

## Falha esperada sem Chromium

Sem Playwright ou sem Chromium instalado, a rota responde **HTTP 503** com a página `reports/document/unavailable.html`.

## Margens e cabeçalho/rodapé

- Margens ABNT (3 cm / 2 cm / 2 cm / 3 cm) em `report_document_pdf.py` (`ABNT_PDF_MARGINS`).
- Cabeçalho e rodapé vêm de `Report.page_layout`, repetidos via `header_template` / `footer_template` do Playwright.
- Logos das faixas são inlined como **data URI** em `report_document_pdf_fragments.py`.
- Numeração no rodapé usa classes nativas `<span class="pageNumber">` / `<span class="totalPages">`.

## Desenvolvimento local

Ambiente de desenvolvimento pode usar apenas `requirements.txt` (sem Playwright). Nesse caso:

- Preview paginado continua em `/reports/<uuid>/preview/`.
- PDF retorna 503 até instalar `requirements-server.txt` e o Chromium.

## Referências

- [08-report-document-render.md](./architecture/08-report-document-render.md)
- [Playwright — page.pdf()](https://playwright.dev/python/docs/api/class-page#page-pdf)
