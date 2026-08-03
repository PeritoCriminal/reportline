# Runbook — exportação PDF do laudo (Playwright)

Procedimento para habilitar `GET /reports/<uuid>/document/` em ambientes de servidor.

Documentação de arquitetura: [08-report-document-render.md](./architecture/08-report-document-render.md)

## Dependências

```bash
pip install -r requirements-server.txt
playwright install chromium
```

O comando `playwright install chromium` baixa o binário do Chromium usado pelo Playwright em modo headless.

## Verificação rápida

1. Autentique-se como autor de um laudo.
2. Abra `/reports/<uuid>/document/?html=1` — deve retornar HTML contínuo (`report-document-pdf`), **sem** script `paginateDocument`.
3. Abra `/reports/<uuid>/document/` — deve retornar `application/pdf` inline.
4. (Opcional) Compare com `/reports/<uuid>/preview/` — preview paginado no navegador (não exige Playwright).

Atalhos na toolbar do editor: ícone **olho** (preview) e ícone **PDF** (document).

## Falha esperada sem Chromium

Sem Playwright ou sem Chromium instalado, a rota `/document/` responde **HTTP 503** com a página
`reports/document/unavailable.html` (mensagem suavizada no tema escuro).

O preview (`/preview/`) continua disponível normalmente.

## Margens e cabeçalho/rodapé

- Margens ABNT (3 cm / 2 cm / 2 cm / 3 cm) em `report_document_pdf.py` (`ABNT_PDF_MARGINS`).
- Cabeçalho e rodapé vêm de `Report.page_layout`, repetidos via `header_template` / `footer_template` do Playwright.
- Logos das faixas são inlined como **data URI** em `report_document_pdf_fragments.py`.
- Numeração no rodapé usa classes nativas `<span class="pageNumber">` / `<span class="totalPages">`.

No **preview**, a numeração é atualizada pelo JS (`data-report-page-current` / `data-report-page-total`).

## Desenvolvimento local

Ambiente de desenvolvimento pode usar apenas `requirements.txt` (sem Playwright):

| Rota | Sem Playwright |
|---|---|
| `/reports/<uuid>/preview/` | ✅ Funciona |
| `/reports/<uuid>/document/` | 503 (página indisponível) |
| `/reports/<uuid>/document/?html=1` | ✅ HTML de debug (não exige Chromium) |

## Referências

- [08-report-document-render.md](./architecture/08-report-document-render.md)
- [07-reports.md](./architecture/07-reports.md)
- [Playwright — page.pdf()](https://playwright.dev/python/docs/api/class-page#page-pdf)
