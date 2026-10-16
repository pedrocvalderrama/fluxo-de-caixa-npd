# Manual de Consulta SQL - Contas a Pagar & Fluxo de Caixa (ERP Sisplan)

Este manual documenta a regra de conexão, mapeamento de tabelas e a consulta SQL utilizada para extrair os dados de **Contas a Pagar** da tela **130 (Inclusão / Manutenção Pagar)** do ERP Sisplan.

---

> [!CAUTION]
> ### REGRA CRÍTICA DE SEGURANÇA: SOMENTE LEITURA (READ-ONLY)
> **NUNCA EXECUTAR COMANDOS DE ESCRITA OU ALTERAÇÃO (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`) NO BANCO DE DADOS DO SISPLAN (`14215F.FDB`).**
> - **Sempre utilize consultas estritamente de leitura (`SELECT`)**.

---

## 1. Mapeamento de Tabelas e Campos da Tela 130

### Tabela Principal: `PAGTO_001` (Contas a Pagar / Títulos)

- `NUM_AP`: Número da Autorização de Pagamento (Número do Título no Pagar).
- `DOCTO`: Número do Documento / Nota Fiscal / Boleto.
- `DUPLI`: Identificação da Parcela / Duplicata (ex: `050876-04`).
- `CODCRE`: Código do Credor / Fornecedor (relaciona com `ENTIDADE_001.CODCLI`).
- `NUM_OS`: Código da Classe / Natureza Contábil (relaciona com `CLASSE_GER_001.CODIGO`).
- `DT_EMI`: Data de Emissão da Nota/Título.
- `DT_VEN`: Data de Vencimento do título.
- `VALOR`: Valor total da parcela do título a pagar.
- `VAL_PAG`: Valor já pago/baixado até o momento.
- `VAL_DEV`: Valor devolvido.
- `EMP_ID`: Código da Empresa (`1` = NPD, `2` = COMPRE, `3` = DEMO, `4` = CS).
- `STATUS`: Filtro de Tipo do Título:
  - `'DUPL'`: Duplicatas / A.P. (Padrão selecionado na tela: `[X] A.P.`)
  - `'ANTE'`: Antecipações
  - `'ORCA'`: Orçamentos
  - `'DESD'`: Desdobradas
  - `'AGRU'`: Agrupadas
- `SITUACAO`: Código da Situação do Título.
- `BLOQUEIO`: Status de Bloqueio (`N` = Liberada, `S` = Bloqueada, etc.).

### Tabelas Complementares (Joins e Subqueries):

1. **`ENTIDADE_001`**: Cadastro de Fornecedores/Credores (`ENTIDADE_001.CODCLI = PAGTO_001.CODCRE`).
   - `NOME`: Razão Social / Nome do Fornecedor.
2. **`CLASSE_GER_001`**: Cadastro de Classes / Naturezas Contábeis (`CLASSE_GER_001.CODIGO = PAGTO_001.NUM_OS`).
   - `DESCRICAO`: Nome da Natureza Contábil (ex: `MP - TINTA`, `FR - FRETES VENDAS`).
3. **`PAGTO1_001`**: Baixas e Pagamentos Efetuados (`PAGTO1_001.NUM_AP = PAGTO_001.NUM_AP`).
   - `DT_LAN`: Data da baixa/pagamento (utiliza-se `MAX(P1.DT_LAN)` para capturar a data em que foi pago).

---

## 2. Consulta SQL Oficial para Contas a Pagar (Tela 130)

Esta consulta extrai todos os títulos a pagar detalhados com fornecedor, natureza contábil, valor, valor pago e saldo em aberto, respeitando os filtros da tela 130:
- **Situação**: Todas
- **Status**: Todas
- **Tipo**: `[X] A.P.` (`STATUS = 'DUPL'`)
- **Empresas**: Todas (`EMP_ID IN (1, 2, 3, 4)`)
- **Período de Vencimento**: `11/09/2026` a `15/09/2026`

```sql
SELECT 
    P.EMP_ID AS EMPRESA,
    P.NUM_AP AS NUMERO_AP,
    P.DOCTO AS NOTA_DOC,
    P.DUPLI AS PARCELA,
    P.CODCRE AS COD_FORNECEDOR,
    COALESCE(E.NOME, 'NÃO INFORMADO') AS FORNECEDOR,
    P.NUM_OS AS COD_CLASSE,
    COALESCE(C.DESCRICAO, 'DESPESAS GERAIS') AS NATUREZA_CONTABIL,
    P.DT_EMI AS DATA_EMISSAO,
    P.DT_VEN AS DATA_VENCIMENTO,
    (SELECT MAX(P1.DT_LAN) FROM PAGTO1_001 P1 WHERE P1.NUM_AP = P.NUM_AP) AS DATA_PAGTO,
    P.VALOR AS VALOR_TITULO,
    COALESCE(P.VAL_PAG, 0) AS VALOR_PAGO,
    CASE 
        WHEN COALESCE(P.VAL_PAG, 0) >= P.VALOR THEN 0 
        ELSE (P.VALOR - COALESCE(P.VAL_PAG, 0)) 
    END AS SALDO_A_PAGAR,
    P.SITUACAO,
    P.STATUS,
    P.BANCO
FROM PAGTO_001 P
LEFT JOIN ENTIDADE_001 E ON (P.CODCRE = E.CODCLI)
LEFT JOIN CLASSE_GER_001 C ON (P.NUM_OS = C.CODIGO)
WHERE P.DT_VEN >= '2026-09-11' AND P.DT_VEN <= '2026-09-15'
  AND P.STATUS = 'DUPL'
ORDER BY P.DT_VEN ASC, P.NUM_AP ASC;
```

---

## 3. Resumo Consolidado do Período (11/09/2026 a 15/09/2026)

```sql
SELECT 
    P.DT_VEN AS DATA_VENCIMENTO,
    COUNT(*) AS QTD_TITULOS,
    SUM(P.VALOR) AS TOTAL_VALOR,
    SUM(COALESCE(P.VAL_PAG, 0)) AS TOTAL_PAGO,
    SUM(CASE WHEN COALESCE(P.VAL_PAG, 0) >= P.VALOR THEN 0 ELSE (P.VALOR - COALESCE(P.VAL_PAG, 0)) END) AS SALDO_A_PAGAR
FROM PAGTO_001 P
WHERE P.DT_VEN >= '2026-09-11' AND P.DT_VEN <= '2026-09-15'
  AND P.STATUS = 'DUPL'
GROUP BY P.DT_VEN
ORDER BY P.DT_VEN;
```
