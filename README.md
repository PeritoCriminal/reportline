# ReportLine

Sistema web robusto e modular para a gestão e produção automatizada de laudos e relatórios periciais/forenses. O projeto foi desenvolvido utilizando boas práticas de arquitetura de software, servindo tanto para uso prático quanto como base de aprendizado para a comunidade de desenvolvimento Python/Django.

---

## 🎯 Objetivo do Projeto

O **ReportLine** foi idealizado para otimizar o fluxo de trabalho de peritos e examinadores forenses. O sistema visa substituir a edição manual e fragmentada de documentos por uma estrutura dinâmica e centralizada, garantindo:
* **Padronização:** Modelos de relatórios estruturados de forma lógica e jurídica.
* **Segurança:** Controle rígido de autenticação e integridade dos dados sensíveis.
* **Flexibilidade:** Arquitetura pensada para a criação de relatórios modulares.

---

## 🚀 Tecnologias Utilizadas

* **Python 3.11+**
* **Django 6.0.x** (Framework web de alto nível)
* **PostgreSQL** (Banco de dados relacional robusto para produção)
* **Python-dotenv** (Gerenciamento seguro de variáveis de ambiente)
* **Git & GitHub** (Versionamento utilizando o padrão *Conventional Commits*)

---

## 🛠️ Arquitetura e Boas Práticas Implementadas

* **CustomUser Base:** Implementação preventiva de um modelo de usuário personalizado (`CustomUser`) estendendo `AbstractUser`, garantindo que o banco de dados nasça pronto para futuras expansões (como inserção de Registros Profissionais/Cargos).
* **Isolamento de Credenciais:** Configuração de segurança via arquivo `.env` para impedir a exposição de chaves secretas e senhas de banco de dados no repositório público.
* **Histórico Semântico:** Mensagens de commit padronizadas para facilitar a leitura e evolução do projeto por outros desenvolvedores.

---

## 💻 Como Rodar o Projeto Localmente

### Requisitos Prévios
Antes de começar, certifique-se de ter o **Python** e o **PostgreSQL** instalados na sua máquina.

### Passo a Passo

1. **Clonar o repositório:**
   ```bash
   git clone [https://github.com/PeritoCriminal/reportline.git](https://github.com/PeritoCriminal/reportline.git)
   cd reportline
   
2. **Criar e ativar o ambiente virtual (venv):**
   ```PowerShell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   
3. **Instalar as dependências:**
   ```Bash
   pip install -r requirements.txt
   
4. **Configurar as Variáveis de Ambiente:**
Crie um arquivo .env na raiz do projeto e adicione as suas credenciais locais do PostgreSQL:

Snippet de código
DB_NAME=reportline
DB_USER=postgres
DB_PASSWORD=sua_senha_aqui
DB_HOST=localhost
DB_PORT=5432

5. **Rodar as Migrações do Banco de Dados:**

   ```Bash
   python manage.py migrate```

6. **Iniciar o Servidor de Desenvolvimento:**
   ```Bash
   python manage.py runserver
   
7. **Acesse http://127.0.0.1:8000/ no seu navegador.**

📝 Licença
Este projeto é aberto e voltado para fins educacionais e de portfólio. Sinta-se à vontade para estudar, clonar e contribuir!
