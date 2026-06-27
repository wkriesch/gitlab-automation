# GitLab Automation Framework

Este projeto é um motor de regras baseado em eventos (webhooks) para automatizar fluxos de trabalho no GitLab (Jira-like Automation). Desenvolvido em Python com FastAPI, o framework permite que você defina regras em arquivos YAML simples para automatizar tarefas comuns em Issues do GitLab.

## 🚀 Funcionalidades

- **Associação automática de Epics**: Vincula issues a Epics específicos no GitLab com base em etiquetas (labels).
- **Datas Automáticas**: Define datas de início (`start_date`) e vencimento (`due_date`) baseadas em mudanças de status da issue (ex: labels `status::in-progress` ou `status::done`).
- **Configuração Simples via YAML**: Sem código hardcoded para as regras de automação. Tudo é definido em `config/rules.yaml`.
- **Prevenção de Loops**: Mecanismo dinâmico e inteligente para ignorar atualizações disparadas pelo próprio bot, evitando loops infinitos de execução.
- **Validação Segura de Assinatura**: Autenticação segura usando tokens de webhook com comparação em tempo constante (`secrets.compare_digest`), protegendo contra ataques de temporização (timing attacks).
- **Resiliência a Diferentes Versões**: Tratamento inteligente e logs robustos para recursos Premium/Ultimate (como Epics) caso o projeto seja testado em ambientes GitLab Free.

---

## 🗂️ Estrutura do Projeto

```
gitlab-automation-framework/
├── app/
│   ├── __init__.py
│   ├── config.py           # Configurações do sistema (Pydantic / Env)
│   ├── main.py             # Entrada do FastAPI, rotas de webhook e segurança
│   ├── handler.py          # Processador e distribuidor de eventos
│   ├── rules_engine.py     # Parser YAML e processador de correspondências
│   ├── actions.py          # Executor das ações no GitLab (datas, epics, etc.)
│   └── gitlab_client.py    # Cliente assíncrono para interagir com a API do GitLab
│
├── config/
│   └── rules.yaml          # Definição das regras de automação
│
├── tests/
│   ├── test_rules.py       # Testes unitários para o motor de regras
│   └── test_webhook.py     # Testes do webhook, loop prevention e autenticação
│
├── .env.example            # Exemplo de configuração de variáveis
├── Dockerfile              # Dockerfile multi-stage seguro
└── requirements.txt        # Dependências python fixadas
```

---

## ⚙️ Instalação e Execução Local

### Pré-requisitos

- Python 3.11 ou superior
- Uma conta/instância do GitLab e um Token de Acesso Pessoal (PAT) com escopo `api`
- (Opcional) Docker instalado

### Setup do Ambiente

1. **Clonar e acessar o repositório**:
   ```bash
   cd gitlab-automation-framework
   ```

2. **Criar e ativar o ambiente virtual (virtualenv)**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # No Windows: .venv\Scripts\activate
   ```

3. **Instalar dependências**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configurar as Variáveis de Ambiente**:
   Copie o arquivo `.env.example` para `.env`:
   ```bash
   cp .env.example .env
   ```
   Abra o arquivo `.env` e preencha as variáveis necessárias:
   - `GITLAB_ACCESS_TOKEN`: Token de acesso do bot (ou pessoal).
   - `GITLAB_API_URL`: Use `https://gitlab.com` ou a URL do seu GitLab on-premise.
   - `GITLAB_WEBHOOK_SECRET`: Token arbitrário usado para validar a origem do webhook. Deve ser o mesmo configurado no painel do GitLab.

5. **Iniciar a Aplicação Localmente**:
   ```bash
   uvicorn app.main:app --reload
   ```
   A API estará rodando em `http://localhost:8000`. A documentação interativa (Swagger) pode ser acessada em `http://localhost:8000/docs`.

---

## 🧪 Rodando os Testes

A suíte de testes do projeto utiliza o `pytest`. Os testes mockam a API do GitLab e validam a integridade das regras e comportamento de segurança do webhook:

```bash
# Rodar todos os testes
pytest
```

---

## 🐳 Executando com Docker

O projeto inclui um `Dockerfile` seguro e otimizado com construção em múltiplos estágios (multi-stage) e execução sob usuário sem privilégios de root (`automation`), mitigando vulnerabilidades a nível de container.

1. **Construir a imagem**:
   ```bash
   docker build -t gitlab-automation-framework .
   ```

2. **Executar o container**:
   ```bash
   docker run -d \
     -p 8000:8000 \
     --env-file .env \
     --name gitlab-bot \
     gitlab-automation-framework
   ```

---

## 📜 Configuração de Regras (`config/rules.yaml`)

O motor de automação utiliza um arquivo YAML centralizado para definir o comportamento das regras. Exemplo:

```yaml
rules:
  # Regra 1: Associa um Epic se a label 'tipo::projeto' for detectada
  - name: projeto_epic
    match:
      labels: ["tipo::projeto"]
    actions:
      - set_epic: 123  # ID do Epic na sua organização GitLab

  # Regra 2: Define data de início caso o status seja alterado para 'in-progress'
  - name: start_date
    match:
      labels: ["status::in-progress"]
      on_change: true  # Apenas quando o label for recém-adicionado
    actions:
      - set_start_date: now

  # Regra 3: Define data de entrega caso o status seja alterado para 'done'
  - name: done_date
    match:
      labels: ["status::done"]
      on_change: true  # Apenas quando o label for recém-adicionado
    actions:
      - set_due_date: now
```

### Sintaxe de Correspondência (`match`):
- `labels`: Lista de labels que devem estar presentes na issue para corresponder à regra.
- `on_change`: Se `true`, a regra só disparará no exato momento em que as labels listadas forem adicionadas à issue (evita retriggar em edições subsequentes). Se `false`, o gatilho será avaliado sempre que qualquer alteração ocorrer na issue enquanto ela contiver a label.

### Ações Suportadas (`actions`):
- `set_epic`: Associa a issue a um Epic do grupo. (Valor: número inteiro correspondente ao IID do Epic).
- `set_start_date`: Define a data de início da Issue. (Valores: `"now"` para o dia de hoje, ou string formato `"AAAA-MM-DD"`).
- `set_due_date`: Define a data de vencimento da Issue. (Valores: `"now"` para o dia de hoje, ou string formato `"AAAA-MM-DD"`).



❯ podman run -e "GITLAB_ACCESS_TOKEN=glpat-PwY1wS4uJrQ4CKhJG4_pzm86MQp1OjEH.01.0w1eoccfk" -e "GITLAB_API_URL=https://gitlab.taild6c066.ts.net/" -p 8000:8000 1af4b2fdb394