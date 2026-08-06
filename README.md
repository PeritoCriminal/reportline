# ReportLine

Sistema web robusto e modular para a gestão e produção automatizada de laudos e relatórios periciais/forenses. O projeto foi desenvolvido utilizando boas práticas de arquitetura de software, servindo tanto para uso prático quanto como base de aprendizado para a comunidade de desenvolvimento Python/Django.

---

## Objetivo do Projeto

O **ReportLine** foi idealizado para otimizar o fluxo de trabalho de peritos e examinadores forenses. O sistema visa substituir a edição manual e fragmentada de documentos por uma estrutura dinâmica e centralizada, garantindo:

* **Padronização:** Modelos de relatórios estruturados de forma lógica e jurídica.
* **Segurança:** Controle rígido de autenticação, sanitização de PII antes de IA externa e integridade dos dados sensíveis.
* **Flexibilidade:** Arquitetura pensada para a criação de relatórios modulares.

---

## Tecnologias Utilizadas

* **Python 3.11+**
* **Django 6.0.x** (Framework web de alto nível)
* **PostgreSQL** (Banco de dados relacional robusto para produção)
* **Python-dotenv** (Gerenciamento seguro de variáveis de ambiente)
* **OpenAI API** (extração e redação assistida no laudo pericial)
* **Presidio + spaCy** (sanitização local de PII antes do envio à IA)
* **Git & GitHub** (Versionamento utilizando o padrão *Conventional Commits*)

---

## Arquitetura e Boas Práticas Implementadas

* **CustomUser Base:** Modelo de usuário personalizado (`CustomUser`) com UUID, pronto para expansões futuras.
* **Isolamento de Credenciais:** Configuração via `.env` (fora do Git); ver [ADR-0005](docs/decisions/0005-external-api-credentials.md).
* **Sanitização PII:** Pipeline local antes da OpenAI; ver [ADR-0008](docs/decisions/0008-ai-pii-sanitization.md) e [docs/architecture/09-forensic-ai-privacy.md](docs/architecture/09-forensic-ai-privacy.md).
* **Documentação de arquitetura:** Diagramas Mermaid em `docs/architecture/`; ADRs em `docs/decisions/`.

---

## Como Rodar o Projeto Localmente

### Requisitos prévios

Antes de começar, certifique-se de ter **Python** e **PostgreSQL** instalados na sua máquina.

### Passo a passo

1. **Clonar o repositório:**

   ```bash
   git clone https://github.com/PeritoCriminal/reportline.git
   cd reportline
   ```

2. **Criar e ativar o ambiente virtual (venv):**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. **Instalar as dependências:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar variáveis de ambiente:**

   Copie `.env.example` para `.env` e preencha as credenciais locais:

   ```env
   DB_NAME=reportline
   DB_USER=postgres
   DB_PASSWORD=sua_senha_aqui
   DB_HOST=localhost
   DB_PORT=5432

   # Opcional — IA no laudo pericial
   OPENAI_API_KEY=sua_chave_aqui
   FORENSIC_AI_SANITIZATION_ENABLED=true
   FORENSIC_AI_BLOCK_ON_RESIDUAL_PII=true
   PRESIDIO_SPACY_MODEL=pt_core_news_lg
   ```

5. **Modelo spaCy (sanitização de PII — recomendado no servidor):**

   ```bash
   python -m spacy download pt_core_news_lg
   ```

   Sem o modelo, a sanitização opera apenas com regex (Presidio fica desabilitado).

6. **Rodar as migrações:**

   ```bash
   python manage.py migrate
   ```

7. **Iniciar o servidor de desenvolvimento:**

   ```bash
   python manage.py runserver
   ```

8. **Acesse** http://127.0.0.1:8000/ **no navegador.**

> **Nota:** Peritos acessam o sistema pelo navegador — não precisam instalar Python.
> Apenas quem **hospeda** o ReportLine instala deps e o modelo spaCy.

### Arquivos de mídia (logos e uploads)

A pasta **`media/`** guarda uploads do Django (ex.: logos do cabeçalho do
laudo em `Institution.sp_logo` e `Institution.sptc_logo`). Ela **não sobe no
Git** — quem faz deploy precisa tratar mídia no servidor separadamente do
código.

**Desenvolvimento:**

```bash
# Opcional — o Django cria no primeiro upload
mkdir media\institution_ic_sp\logos
```

Depois de `migrate`, envie os logos pelo **Django Admin** (Instituição →
*Logos do cabeçalho*).

**Produção / hospedagem:** preserve `MEDIA_ROOT` entre deploys, configure o
servidor web para servir `/media/`, faça backup da pasta junto com o banco e
reponha os logos após instalar em servidor novo. Checklist completo em
[docs/architecture/04-institution-ic-sp.md](docs/architecture/04-institution-ic-sp.md#logos-e-mídia-no-deploy).

---

## Documentação

| Recurso | Caminho |
|---|---|
| Visão do sistema | [docs/architecture/01-context.md](docs/architecture/01-context.md) |
| Mapa de apps | [docs/architecture/03-apps-map.md](docs/architecture/03-apps-map.md) |
| IA e privacidade (PII) | [docs/architecture/09-forensic-ai-privacy.md](docs/architecture/09-forensic-ai-privacy.md) |
| Decisões arquiteturais | [docs/decisions/](docs/decisions/) |

---

## Licença

Este projeto é aberto e voltado para fins educacionais e de portfólio. Sinta-se à vontade para estudar, clonar e contribuir!
