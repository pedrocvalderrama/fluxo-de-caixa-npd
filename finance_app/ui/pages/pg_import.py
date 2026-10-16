import streamlit as st
import time
from pathlib import Path
import tempfile
import pandas as pd
from datetime import date, timedelta, datetime

from finance_app.database.connection import SessionLocal, init_db, reset_db, get_meta
from finance_app.database.repositories.importacao_repo import ImportacaoRepository
from finance_app.ingestion.importer import (
    importar_excel,
    sincronizar_movimentacoes_normalizadas,
    ProgressoImportacao,
    carregar_banco_para_conciliacao,
)
from finance_app.ingestion.excel_reader import ler_excel
from finance_app.ingestion.validator import validar_dataframe
from finance_app.ingestion.normalizer import normalizar_dataframe
from finance_app.ingestion.duplicate_detector import processar_analise_importacao
from finance_app.ingestion.firebird_client import testar_conexao_sisplan
from finance_app.ingestion.firebird_extractor import extrair_receber_sisplan, extrair_pagar_sisplan
from finance_app.config.settings import settings
from finance_app.services.saldo_service import (
    ler_e_atualizar_saldo_excel,
    obter_saldo_mais_recente,
    DEFAULT_SALDO_EXCEL_PATH,
)
from processar_fluxo_caixa import processar_fluxo_caixa


def _limpar_banco_dados() -> None:
    """Esvazia o banco recriando o schema (sem apagar o arquivo .db)."""
    reset_db()


def _reset_estado_importacao() -> None:
    st.session_state.import_state = "upload"
    st.session_state.import_source = None
    st.session_state.sql_movimentacoes = None
    st.session_state.sql_origem_nome = None
    st.session_state.uploaded_file_path = None
    st.session_state.preview_data = None
    st.session_state.validation_stats = None
    st.session_state.final_result = None
    st.session_state.pop("elapsed_time", None)


def _preparar_preview_sql(movs: list, nome_origem: str) -> None:
    """Prepara a tela de prévia e conciliação para os registros extraídos via SQL."""
    with SessionLocal() as session:
        hashes_banco, mapa_negocio_banco = carregar_banco_para_conciliacao(session)
        analise = processar_analise_importacao(movs, hashes_banco, mapa_negocio_banco)

    preview_list = []
    for m in movs[:100]:
        preview_list.append({
            "Empresa": m.empresa,
            "Tipo": m.movimentacao,
            "Documento": m.documento or "",
            "Titular": m.titular or "",
            "Natureza": m.natureza,
            "Vencimento": m.vencimento.strftime("%d/%m/%Y") if m.vencimento else "",
            "Data Transação": m.data_transacao.strftime("%d/%m/%Y") if m.data_transacao else "Em Aberto",
            "Valor": f"R$ {m.valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "Status": "Em Aberto" if m.em_aberto else "Pago",
        })

    st.session_state.preview_data = pd.DataFrame(preview_list)
    st.session_state.sql_movimentacoes = movs
    st.session_state.sql_origem_nome = nome_origem
    st.session_state.import_source = "sql"
    st.session_state.validation_stats = {
        "total": len(movs),
        "erros": 0,
        "ja_existentes": analise.ja_existentes_count,
        "atualizacoes": len(analise.atualizacoes),
        "novos": len(analise.novos_para_inserir),
        "duplicatas_internas": analise.duplicatas_internas_count,
        "em_aberto": sum(1 for m in movs if m.em_aberto),
        "anomalias": sum(1 for m in movs if m.is_anomalia_data),
    }
    st.session_state.import_state = "preview"
    st.rerun()


def _render_automation_status() -> None:
    """Exibe o status e métricas da automação em segundo plano."""
    try:
        hb_str = get_meta("automacao_heartbeat")
        ativo = False
        if hb_str:
            try:
                hb_dt = datetime.strptime(hb_str, "%d/%m/%Y %H:%M:%S")
                # Ativo se o batimento ocorreu nos últimos 3 minutos
                if (datetime.now() - hb_dt).total_seconds() < 180:
                    ativo = True
            except Exception:
                ativo = False

        db_sync = get_meta("automacao_db_ultimo_sucesso") or "Ainda não executado"
        db_res = get_meta("automacao_db_resumo") or ""
        saldo_sync = get_meta("automacao_saldo_ultimo_sucesso") or "Ainda não executado"
        saldo_res = get_meta("automacao_saldo_resumo") or ""

        with st.container():
            if ativo:
                st.markdown(
                    """
                    <div style="background-color: #ECFDF5; border: 1px solid #10B981; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;">
                        <span style="font-size: 15px; font-weight: bold; color: #065F46;">🟢 Automação em Segundo Plano: ATIVA</span><br>
                        <span style="font-size: 13px; color: #047857;">
                            Sincronizando banco de dados Sisplan a cada 2 horas e atualizando saldos bancários todo dia às 12:00.
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    """
                    <div style="background-color: #F3F4F6; border: 1px solid #9CA3AF; border-radius: 8px; padding: 12px 16px; margin-bottom: 12px;">
                        <span style="font-size: 15px; font-weight: bold; color: #374151;">⚪ Automação em Segundo Plano: PARADA</span><br>
                        <span style="font-size: 13px; color: #4B5563;">
                            Para rodar as atualizações automáticas contínuas (a cada 2h e às 12h), utilize <code>iniciar_segundo_plano.vbs</code> ou <code>iniciar_servicos.bat</code>.
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            col_aut1, col_aut2 = st.columns(2)
            with col_aut1:
                st.caption("🔄 **Último Sync Sisplan (a cada 2h)**")
                st.write(f"📅 **{db_sync}**")
                if db_res:
                    st.caption(f"_{db_res}_")
            with col_aut2:
                st.caption("💰 **Última Atualização de Saldo (12:00)**")
                st.write(f"📅 **{saldo_sync}**")
                if saldo_res:
                    st.caption(f"_{saldo_res}_")

            st.divider()
    except Exception:
        pass


def render_import_page():
    st.title("📥 Sincronização & Importação de Dados")

    # Garante que o BD está inicializado
    init_db()

    if "import_state" not in st.session_state:
        st.session_state.import_state = "upload"
    if "import_source" not in st.session_state:
        st.session_state.import_source = None
    if "sql_movimentacoes" not in st.session_state:
        st.session_state.sql_movimentacoes = None
    if "uploaded_file_path" not in st.session_state:
        st.session_state.uploaded_file_path = None
    if "preview_data" not in st.session_state:
        st.session_state.preview_data = None
    if "validation_stats" not in st.session_state:
        st.session_state.validation_stats = None
    if "final_result" not in st.session_state:
        st.session_state.final_result = None

    state = st.session_state.import_state

    if state == "upload":
        _render_automation_status()

        if st.session_state.pop("msg_banco_limpo", False):
            st.success("Banco de dados limpo com sucesso!")

        # ── SEÇÃO 1: SINCRONIZAÇÃO DIRETA SQL COM SISPLAN (FIREBIRD) ─────────
        st.markdown("### 🔄 Sincronização Direta com ERP Sisplan (SQL)")
        st.write(
            "Conecta diretamente ao banco de dados do Sisplan (`14215F.FDB`) via SQL estritamente para leitura, "
            "eliminando a necessidade de exportar ou manipular arquivos CSV."
        )

        sisplan_conectado, sisplan_msg = testar_conexao_sisplan()
        if sisplan_conectado:
            st.success(f"🟢 **Conectado ao ERP Sisplan**: `{settings.SISPLAN_HOST}:{settings.SISPLAN_PORT}`")
        else:
            st.warning(
                f"⚠️ **Não foi possível conectar ao Sisplan**: `{sisplan_msg}`\n\n"
                "Verifique se o computador está na rede da empresa ou se a VPN está ativa."
            )

        col_filtro1, col_filtro2 = st.columns([1, 1])

        with col_filtro1:
            opcao_periodo = st.selectbox(
                "📅 Período de Vencimento:",
                ["Todo o Histórico", "Ano Atual (2026)", "Últimos 12 Meses", "Período Personalizado"],
                index=1,
            )

            dt_inicio_sql = None
            dt_fim_sql = None
            hoje = date.today()

            if opcao_periodo == "Ano Atual (2026)":
                dt_inicio_sql = date(2026, 1, 1)
                dt_fim_sql = date(2026, 12, 31)
            elif opcao_periodo == "Últimos 12 Meses":
                dt_inicio_sql = hoje - timedelta(days=365)
                dt_fim_sql = hoje + timedelta(days=365)
            elif opcao_periodo == "Período Personalizado":
                col_sub1, col_sub2 = st.columns(2)
                dt_inicio_sql = col_sub1.date_input("Data Início:", value=date(2026, 1, 1))
                dt_fim_sql = col_sub2.date_input("Data Fim:", value=hoje + timedelta(days=180))

        with col_filtro2:
            opcao_empresa = st.selectbox(
                "🏢 Empresa:",
                ["Todas as Empresas", "1 - NPD", "2 - COMPRE", "3 - DEMO", "4 - CS"],
                index=0,
            )
            emp_id_sql = None
            if opcao_empresa.startswith("1"):
                emp_id_sql = 1
            elif opcao_empresa.startswith("2"):
                emp_id_sql = 2
            elif opcao_empresa.startswith("3"):
                emp_id_sql = 3
            elif opcao_empresa.startswith("4"):
                emp_id_sql = 4

        # Botão principal unificado (Pagar + Receber)
        if st.button(
            "⚡ Sincronizar Tudo (Pagar + Receber)",
            type="primary",
            use_container_width=True,
            disabled=not sisplan_conectado,
        ):
            try:
                with st.spinner("Consultando Contas a Pagar e Contas a Receber diretamente no banco Sisplan..."):
                    movs_rec = extrair_receber_sisplan(
                        data_inicio=dt_inicio_sql,
                        data_fim=dt_fim_sql,
                        emp_id=emp_id_sql,
                        apenas_duplicatas=True,
                        filtrar_devolucoes=True,
                    )
                    movs_pag = extrair_pagar_sisplan(
                        data_inicio=dt_inicio_sql,
                        data_fim=dt_fim_sql,
                        emp_id=emp_id_sql,
                        apenas_ap=True,
                    )
                    movs_total = movs_rec + movs_pag

                if not movs_total:
                    st.info("Nenhum registro de Contas a Pagar ou Receber encontrado para os filtros selecionados.")
                else:
                    _preparar_preview_sql(movs_total, "Sisplan Fluxo Completo (Pagar + Receber)")
            except Exception as exc:
                st.error(f"Erro ao consultar Sisplan: {exc}")

        # Botões individuais (apenas receber ou apenas pagar)
        col_btn_rec, col_btn_pag = st.columns(2)

        with col_btn_rec:
            if st.button(
                "📥 Apenas Contas a Receber",
                use_container_width=True,
                disabled=not sisplan_conectado,
            ):
                try:
                    with st.spinner("Consultando dados de Contas a Receber diretamente no banco Sisplan..."):
                        movs = extrair_receber_sisplan(
                            data_inicio=dt_inicio_sql,
                            data_fim=dt_fim_sql,
                            emp_id=emp_id_sql,
                            apenas_duplicatas=True,
                            filtrar_devolucoes=True,
                        )

                    if not movs:
                        st.info("Nenhum registro de Contas a Receber encontrado para os filtros selecionados.")
                    else:
                        _preparar_preview_sql(movs, "Sisplan Contas a Receber (SQL)")
                except Exception as exc:
                    st.error(f"Erro ao consultar Sisplan: {exc}")

        with col_btn_pag:
            if st.button(
                "📤 Apenas Contas a Pagar",
                use_container_width=True,
                disabled=not sisplan_conectado,
            ):
                try:
                    with st.spinner("Consultando dados de Contas a Pagar diretamente no banco Sisplan (Tela 130)..."):
                        movs = extrair_pagar_sisplan(
                            data_inicio=dt_inicio_sql,
                            data_fim=dt_fim_sql,
                            emp_id=emp_id_sql,
                            apenas_ap=True,
                        )

                    if not movs:
                        st.info("Nenhum registro de Contas a Pagar encontrado para os filtros selecionados.")
                    else:
                        _preparar_preview_sql(movs, "Sisplan Contas a Pagar (SQL)")
                except Exception as exc:
                    st.error(f"Erro ao consultar Sisplan: {exc}")

        st.divider()

        # ── SEÇÃO: ATUALIZAÇÃO DE SALDO DIÁRIO ───────────────────────────────
        st.markdown("### 💰 Atualizar Saldo do Dia (Bancos)")
        st.write(
            "Atualiza os saldos bancários diários das empresas (**CS**, **NPD**, **COMPRE**) nos bancos "
            "(**Banco do Brasil**, **Santander**, **Sicredi**) diretamente da planilha financeira da tesouraria."
        )

        col_caminho, col_status = st.columns([3, 1])
        with col_caminho:
            caminho_saldo = st.text_input(
                "📁 Caminho do Relatório Diário Financeiro:",
                value=DEFAULT_SALDO_EXCEL_PATH,
                key="caminho_saldo_input",
            )
        with col_status:
            arquivo_existe = Path(caminho_saldo).exists() if caminho_saldo else False
            if arquivo_existe:
                st.markdown("<br><span style='color: #10B981; font-weight: bold;'>🟢 Arquivo Encontrado</span>", unsafe_allow_html=True)
            else:
                st.markdown("<br><span style='color: #EF4444; font-weight: bold;'>🔴 Arquivo Não Encontrado</span>", unsafe_allow_html=True)

        arquivo_para_ler = caminho_saldo if arquivo_existe else None

        if not arquivo_existe:
            st.warning(
                "⚠️ O arquivo na rede não está acessível no momento. "
                "Caso prefira, faça o upload manual do arquivo `.xlsx` abaixo:"
            )
            uploaded_saldo = st.file_uploader(
                "Upload manual de RELATORIO DIARIO FINANCEIRO.xlsx",
                type=["xlsx"],
                key="uploader_saldo_manual",
            )
            if uploaded_saldo is not None:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_saldo:
                    tmp_saldo.write(uploaded_saldo.getvalue())
                    arquivo_para_ler = tmp_saldo.name

        if st.button(
            "💰 Atualizar Saldo do Dia",
            type="primary",
            use_container_width=True,
            disabled=arquivo_para_ler is None,
        ):
            try:
                with st.spinner("Lendo arquivo Excel e atualizando saldos bancários..."):
                    res_saldo = ler_e_atualizar_saldo_excel(arquivo_para_ler)
                st.session_state["ultimo_resultado_saldo"] = res_saldo
                st.success(f"✅ Saldos do dia {res_saldo['data'].strftime('%d/%m/%Y')} atualizados com sucesso!")
            except Exception as e:
                st.error(f"❌ Erro ao atualizar saldo do dia: {e}")

        # Exibição do resumo dos saldos mais recentes
        res_saldo_exibir = st.session_state.get("ultimo_resultado_saldo")
        if not res_saldo_exibir:
            with SessionLocal() as s_rec:
                rec = obter_saldo_mais_recente(s_rec)
                if rec:
                    dt_rec, mapa_rec = rec
                    from finance_app.database.models import SaldoDiario
                    regs = s_rec.query(SaldoDiario).filter(SaldoDiario.data == dt_rec).all()
                    detalhes_db = []
                    por_emp_db = {}
                    for r in regs:
                        nome_emp = r.empresa.nome if r.empresa else f"Emp {r.empresa_id}"
                        nome_bco = r.banco.nome if r.banco else f"Bco {r.banco_id}"
                        detalhes_db.append({
                            "empresa": nome_emp,
                            "banco": nome_bco,
                            "saldo": r.saldo,
                        })
                        por_emp_db[nome_emp] = por_emp_db.get(nome_emp, 0.0) + r.saldo
                    res_saldo_exibir = {
                        "data": dt_rec,
                        "total_geral": sum(r.saldo for r in regs),
                        "por_empresa": por_emp_db,
                        "detalhes": detalhes_db,
                    }

        if res_saldo_exibir:
            st.markdown(
                f"##### 📊 Saldos Registrados ({res_saldo_exibir['data'].strftime('%d/%m/%Y')}): "
                f"**Total R$ {res_saldo_exibir['total_geral']:,.2f}**".replace(",", "X").replace(".", ",").replace("X", ".")
            )
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
            with col_kpi1:
                npd_val = res_saldo_exibir["por_empresa"].get("NPD", 0.0)
                st.metric("NPD Embalagens", f"R$ {npd_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col_kpi2:
                compre_val = res_saldo_exibir["por_empresa"].get("COMPRE", 0.0)
                st.metric("Compre Sacola", f"R$ {compre_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
            with col_kpi3:
                cs_val = res_saldo_exibir["por_empresa"].get("CS", 0.0)
                st.metric("CS Embalagens", f"R$ {cs_val:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

            with st.expander("🔍 Ver detalhamento por banco", expanded=False):
                from finance_app.config.empresas import ordem_empresa_chave
                detalhes_ordenados = sorted(
                    res_saldo_exibir["detalhes"],
                    key=lambda d: ordem_empresa_chave(d["empresa"])
                )
                df_det = pd.DataFrame([
                    {
                        "Empresa": d["empresa"],
                        "Banco": d["banco"],
                        "Saldo": f"R$ {d['saldo']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                    }
                    for d in detalhes_ordenados
                ])
                st.dataframe(df_det, use_container_width=True, hide_index=True)

        st.divider()

        # ── SEÇÃO 2: MÉTODOS ALTERNATIVOS (EXCEL E CSVS) ──────────────────────
        with st.expander("📁 Métodos Alternativos (Importação por Planilha ou CSV)", expanded=False):
            st.info(
                "ℹ️ Formato esperado: **FLUXODECAIXA.xlsx** com colunas: "
                "Empresa | Banco | Movimentação | Titular | Natureza Contábil | Data da Transação | "
                "Vencimento | Valor | Numero | Duplicata."
            )

            col_proc, col_up = st.columns([1, 1])

            with col_proc:
                st.markdown("##### ⚡ Processar CSVs da Pasta")
                st.write(
                    "Lê `contasapagar.csv` e `contasareceber.csv` da pasta do projeto e gera `FLUXODECAIXA.xlsx`."
                )
                if st.button("⚡ Processar Fluxo de Caixa (CSVs)", use_container_width=True):
                    try:
                        excel_path = Path("FLUXODECAIXA.xlsx").resolve()
                        with st.spinner("Processando CSVs de Contas a Pagar e Receber..."):
                            processar_fluxo_caixa(excel_saida=str(excel_path))
                        st.success("Planilha FLUXODECAIXA.xlsx gerada com sucesso!")
                        st.session_state.uploaded_file_path = str(excel_path)
                        st.session_state.import_source = "file"
                        st.session_state.import_state = "analyzing"
                        st.rerun()
                    except PermissionError:
                        st.error("❌ O arquivo 'FLUXODECAIXA.xlsx' está aberto em outro programa. Feche-o e tente novamente.")
                    except Exception as e:
                        st.error(f"❌ Erro ao processar fluxo de caixa: {e}")

            with col_up:
                st.markdown("##### 📤 Upload Manual de Arquivo .xlsx")
                st.write("Ou selecione manualmente qualquer arquivo Excel de fluxo de caixa:")
                uploaded_file = st.file_uploader(
                    "Arrastar ou clicar para fazer upload do arquivo .xlsx",
                    type=["xlsx", "xls"],
                    key="uploader_manual_excel"
                )

                if uploaded_file is not None:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                        tmp.write(uploaded_file.getvalue())
                        st.session_state.uploaded_file_path = tmp.name
                        st.session_state.import_source = "file"
                        st.session_state.import_state = "analyzing"
                        st.rerun()

        # ── SEÇÃO 3: HISTÓRICO E MANUTENÇÃO ──────────────────────────────────
        st.markdown("### 🕒 Últimas Sincronizações / Importações")
        with SessionLocal() as session:
            repo = ImportacaoRepository(session)
            recentes = repo.get_recentes(limit=5)
            if recentes:
                for imp in recentes:
                    st.text(
                        f"📅 {imp.data_importacao.strftime('%d/%m/%Y %H:%M')} | "
                        f"📄 {imp.arquivo} | 📊 {imp.qtd_registros} registros | Status: {imp.status}"
                    )
            else:
                st.write("Nenhuma importação ou sincronização recente encontrada.")

        st.divider()
        with st.expander("⚠️ Limpar banco de dados local", expanded=False):
            st.warning(
                "Esta ação apaga permanentemente todas as movimentações, empresas, "
                "categorias e o histórico de importações do banco SQLite local."
            )
            confirmar_limpeza = st.checkbox(
                "Eu entendo que os dados serão apagados permanentemente.",
                key="confirmar_limpeza_banco",
            )
            if st.button(
                "🗑️ Limpar Banco de Dados Local",
                type="primary",
                disabled=not confirmar_limpeza,
                use_container_width=True,
            ):
                try:
                    _limpar_banco_dados()
                    _reset_estado_importacao()
                    st.session_state.msg_banco_limpo = True
                    st.rerun()
                except Exception as e:
                    st.error(f"Não foi possível limpar o banco de dados. Erro: {e}")

    elif state == "analyzing":
        with st.spinner("Analisando e validando arquivo Excel..."):
            try:
                file_path = Path(st.session_state.uploaded_file_path)
                res_leitura = ler_excel(file_path)
                df = res_leitura.df_mapped

                res_validacao = validar_dataframe(df)
                movs_norm, erros_norm = normalizar_dataframe(df)

                with SessionLocal() as session:
                    hashes_banco, mapa_negocio_banco = carregar_banco_para_conciliacao(session)
                    analise = processar_analise_importacao(movs_norm, hashes_banco, mapa_negocio_banco)

                em_aberto = sum(1 for m in movs_norm if m.em_aberto)
                anomalias_data = sum(1 for m in movs_norm if m.is_anomalia_data)

                from finance_app.utils.dates import formatar_datas_dataframe
                st.session_state.preview_data = formatar_datas_dataframe(df.head(100))
                st.session_state.validation_stats = {
                    "total": len(movs_norm),
                    "erros": len(erros_norm),
                    "ja_existentes": analise.ja_existentes_count,
                    "atualizacoes": len(analise.atualizacoes),
                    "novos": len(analise.novos_para_inserir),
                    "duplicatas_internas": analise.duplicatas_internas_count,
                    "em_aberto": em_aberto,
                    "anomalias": anomalias_data,
                }
                st.session_state.import_state = "preview"
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao analisar arquivo: {e}")
                if st.button("Tentar Novamente"):
                    st.session_state.import_state = "upload"
                    st.rerun()

    elif state == "preview":
        origem_txt = "ERP Sisplan (SQL)" if st.session_state.import_source == "sql" else "Arquivo Excel"
        st.success(f"✅ Dados conciliados com sucesso a partir de: **{origem_txt}**")

        stats = st.session_state.validation_stats

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("📊 Total de Registros Lidos", stats["total"])
        col2.metric("📥 Novos a Inserir", stats["novos"])
        col3.metric("🔄 A Atualizar no BD", stats["atualizacoes"])
        col4.metric("⏭️ Inalterados (Ignorados)", stats["ja_existentes"])

        st.markdown("### Relatório de Conciliação")
        if stats["atualizacoes"] > 0:
            st.success(
                f"🔄 **{stats['atualizacoes']:,}** registros já existentes no banco local serão **ATUALIZADOS** "
                "(ex: valor renegociado, novo vencimento ou título que foi quitado no Sisplan)."
            )
        if stats["ja_existentes"] > 0:
            st.info(
                f"⏭️ **{stats['ja_existentes']:,}** registros já existem no banco SQL local idênticos — "
                "NÃO serão duplicados nem alterados."
            )
        if stats["duplicatas_internas"] > 0:
            st.warning(
                f"⚠️ **{stats['duplicatas_internas']:,}** duplicatas internas entre os novos registros — "
                "serão salvas e sinalizadas como duplicadas no programa."
            )
        if stats["em_aberto"] > 0:
            st.warning(
                f"⚠️ **{stats['em_aberto']:,}** títulos em aberto (sem data de pagamento) — "
                "serão cadastrados/atualizados e sinalizados como pendentes."
            )
        if stats["anomalias"] > 0:
            st.warning(
                f"⚠️ **{stats['anomalias']:,}** datas anômalas identificadas."
            )
        if stats["erros"] > 0:
            st.error(f"❌ **{stats['erros']:,}** erros críticos que impedirão a importação correta de algumas linhas.")
        if stats["ja_existentes"] == 0 and stats["atualizacoes"] == 0 and stats["duplicatas_internas"] == 0 and stats["em_aberto"] == 0 and stats["erros"] == 0:
            st.info("Nenhum aviso ou erro encontrado!")

        st.markdown("### Preview dos primeiros 100 registros")
        st.dataframe(st.session_state.preview_data)

        col_btn1, col_btn2 = st.columns([1, 1])
        with col_btn1:
            btn_txt = "🚀 Confirmar Sincronização no Banco" if st.session_state.import_source == "sql" else "🚀 Confirmar Importação"
            if st.button(btn_txt, use_container_width=True, type="primary"):
                st.session_state.import_state = "importing"
                st.rerun()
        with col_btn2:
            if st.button("❌ Cancelar", use_container_width=True):
                _reset_estado_importacao()
                st.rerun()

    elif state == "importing":
        st.markdown("### 🔄 Gravando e Conciliando Dados no Banco Local")
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def update_progress(prog: ProgressoImportacao):
            progress_bar.progress(prog.progresso)
            status_text.text(f"{prog.etapa}: {prog.mensagem}")

        with SessionLocal() as session:
            start_time = time.time()
            if st.session_state.import_source == "sql":
                resultado = sincronizar_movimentacoes_normalizadas(
                    st.session_state.sql_movimentacoes,
                    session,
                    nome_origem=st.session_state.get("sql_origem_nome", "Sisplan SQL"),
                    callback_progresso=update_progress,
                )
            else:
                file_path = st.session_state.uploaded_file_path
                resultado = importar_excel(file_path, session, callback_progresso=update_progress)

            elapsed_time = time.time() - start_time

        st.session_state.final_result = resultado
        st.session_state.elapsed_time = elapsed_time
        st.session_state.import_state = "completed"
        st.rerun()

    elif state == "completed":
        st.balloons()
        st.success("🎉 Sincronização / Importação Concluída com Sucesso!")

        res = st.session_state.final_result
        elapsed = st.session_state.elapsed_time

        if res.sucesso:
            st.markdown(
                f"""
            **Métricas finais:**
            - 📊 **{res.total_lidos:,}** registros processados
            - 📥 **{res.total_importados:,}** novos registros salvos no banco local
            - 🔄 **{res.total_atualizados:,}** registros existentes ATUALIZADOS no banco local (valor, vencimento ou pagamento)
            - ⏭️ **{res.total_ja_existentes:,}** registros inalterados ignorados (já existiam idênticos no BD)
            - ⚠️ **{res.total_duplicatas:,}** duplicatas internas salvas e sinalizadas
            - ⏱️ Concluído em **{elapsed:.2f}** segundos
            """
            )
        else:
            st.error(res.mensagem)
            for det in res.detalhes:
                st.write(f"- {det}")

        if st.button("🏠 Ir para o Dashboard"):
            _reset_estado_importacao()
            st.session_state.pagina_ativa = "dashboard"
            st.rerun()


if __name__ == "__main__":
    render_import_page()
