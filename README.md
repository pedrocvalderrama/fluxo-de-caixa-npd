# 💰 Sistema de Gestão e Análise Financeira

Aplicativo desktop/web construído em Python e Streamlit para transformar planilhas Excel de fluxo de caixa num poderoso sistema de Business Intelligence financeiro.

## ✨ Funcionalidades

### 📊 Dashboard Executivo
- KPIs de saldo, entradas, saídas e resultado
- Gráfico de evolução do fluxo de caixa
- Top categorias de despesas

### 💰 Fluxo de Caixa
- Detalhamento diário com saldo acumulado
- Exportação para CSV

### 📋 Movimentações
- Tabela com todas as transações
- Busca por titular
- Filtros avançados

### 📈 Entradas / 📉 Saídas
- Evolução temporal
- Top 10 clientes/fornecedores
- Análise por categoria

### 🏷️ Categorias
- Treemap interativo
- Análise hierárquica (Grupo → Categoria)
- Percentual de representação

### 🔄 Comparação de Períodos
- Análise lado a lado de dois períodos
- Variação percentual de KPIs

### 📄 Relatórios
- Exportação para Excel e CSV
- Filtros personalizados

### ❤️ Saúde Financeira
- Score geral (A a F)
- Margem operacional e índice de liquidez
- Pontos fortes e de atenção

### 💡 Insights & Anomalias
- Insights automáticos sobre concentração e performance
- Detecção estatística de despesas fora do padrão (Z-Score)

### 📥 Importação de Excel
- Upload com validação e preview
- Detecção de duplicatas
- Progresso em tempo real
- Auto-backup antes de cada importação

### ⚙️ Configurações
- Backup e restauração do banco de dados
- Histórico de importações
- Reset completo do sistema

## 🏗️ Arquitetura

```
finance_app/
├── config/         # Configurações centralizadas (pydantic-settings)
├── database/       # SQLAlchemy ORM + repositórios
├── ingestion/      # Pipeline ETL (Reader → Validator → Normalizer → Dedup → Importer)
├── services/       # Camada de negócio (KPIs, saúde, insights, anomalias)
├── ui/             # Interface Streamlit (12 páginas + componentes)
│   ├── components/ # Sidebar, filtros, gráficos, métricas
│   └── pages/      # Páginas do sistema
├── utils/          # Utilitários (datas, moeda, formatação)
└── tests/          # Suite de testes pytest
```

## 🛡️ Stack Tecnológica

| Tecnologia | Versão | Uso |
|---|---|---|
| Python | 3.12+ | Core |
| Streamlit | ≥1.45 | Interface web |
| SQLAlchemy | ≥2.0 | ORM + Database |
| SQLite | WAL mode | Banco de dados local |
| Pandas | ≥2.2 | Processamento de dados |
| Plotly | ≥6.0 | Gráficos interativos |
| Pydantic | ≥2.0 | Validação de configurações |

## 🚀 Como Executar

### Pré-requisitos
- Python 3.12 ou superior

### Instalação
```bash
# Clone ou copie o projeto
cd "FLUXO DE CAIXA"

# Crie e ative o ambiente virtual
python -m venv venv
venv\Scripts\activate  # Windows

# Instale as dependências
pip install -r requirements.txt
```

### Executando
```bash
streamlit run app.py
```

Na interface, vá até **📥 Importar Excel** e faça upload da planilha. O sistema processa 80.000+ linhas em menos de 30 segundos.

## 🧪 Testes

```bash
# Executar todos os testes
python -m pytest finance_app/tests/ -v

# Executar testes por módulo
python -m pytest finance_app/tests/test_utils/ -v
python -m pytest finance_app/tests/test_ingestion/ -v
python -m pytest finance_app/tests/test_services/ -v
```

## 🔐 Segurança

O sistema opera 100% offline (local-first), protegendo dados empresariais sem vazar métricas pela internet. Backups automáticos são criados antes de cada importação.

---
*Desenvolvido em módulos — Fases 1 a 8 Completas.*
