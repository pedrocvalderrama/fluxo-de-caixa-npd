"""
Componentes de filtro para a interface.
Filtros renderizados no topo da página principal (não na sidebar).
"""
from __future__ import annotations

from typing import Any, Optional
import datetime
import streamlit as st

from finance_app.services.filter_service import FiltrosPesquisa
from finance_app.utils.dates import periodos_rapidos, STREAMLIT_DATE_FORMAT
from finance_app.database.models import Empresa, Categoria, Banco
from finance_app.config.empresas import ordem_empresa_chave

# Chave NÃO usada por nenhum widget — sobrevive ao cleanup do Streamlit
# (widgets sumidos numa rerun de navegação têm o state apagado).
_PERSIST_SALDO = "_persist_saldo_inicial"


def _chave_conta(empresa_id: int, banco_id: int) -> str:
    return f"{empresa_id}_{banco_id}"


def _garantir_persist_saldo(data_padrao: datetime.date, session: Optional[Any] = None) -> dict:
    if _PERSIST_SALDO not in st.session_state:
        saldos_db = {}
        data_ini = data_padrao
        if session is not None:
            try:
                from finance_app.services.saldo_service import obter_saldo_por_data, obter_saldo_mais_recente
                rec_padrao = obter_saldo_por_data(data_padrao, session=session)
                if rec_padrao:
                    data_ini = data_padrao
                    for (eid, bid), val in rec_padrao["saldos"].items():
                        saldos_db[f"{eid}_{bid}"] = float(val)
                else:
                    rec = obter_saldo_mais_recente(session)
                    if rec:
                        max_dt, mapa_saldos = rec
                        data_ini = max_dt
                        for (eid, bid), val in mapa_saldos.items():
                            saldos_db[f"{eid}_{bid}"] = float(val)
            except Exception:
                pass

        st.session_state[_PERSIST_SALDO] = {
            "usar": bool(saldos_db),
            "data": data_ini,
            "saldos": saldos_db,
        }
    return st.session_state[_PERSIST_SALDO]


def _restaurar_widget_se_ausente(widget_key: str, valor) -> None:
    """Recoloca o valor do widget só se o Streamlit tiver apagado a chave."""
    if widget_key not in st.session_state:
        st.session_state[widget_key] = valor


def render_global_filters(session: Any) -> FiltrosPesquisa:
    """
    Renderiza os filtros globais no topo da página e retorna um objeto FiltrosPesquisa.
    Os filtros são divididos em duas colunas principais.
    """
    # Pré-carregar empresas e bancos (usados na coluna direita e no saldo inicial)
    empresas_db = []
    empresas_map = {}
    bancos_db = []
    bancos_map = {}
    try:
        empresas_raw = session.query(Empresa).all()
        empresas_db = sorted(empresas_raw, key=ordem_empresa_chave)
        if empresas_db:
            empresas_map = {e.nome: e.id for e in empresas_db}
        bancos_db = session.query(Banco).filter(Banco.ativo == True).order_by(Banco.codigo).all()
        if bancos_db:
            bancos_map = {b.nome: b.id for b in bancos_db}
    except Exception:
        pass

    with st.expander("🔍 **Filtros**", expanded=True):
        col_esquerda, col_direita = st.columns([1, 1])

        # ── Coluna Esquerda ────────────────────────────────────────────────
        with col_esquerda:
            dict_periodos = periodos_rapidos()
            opcoes_periodo = list(dict_periodos.keys())

            periodo_selecionado = st.selectbox(
                "Período Rápido", opcoes_periodo, index=2
            )
            data_ini_def, data_fim_def = dict_periodos.get(
                periodo_selecionado, (datetime.date.today(), datetime.date.today())
            )
            # Padrão: quando "Este Mês" está selecionado, o vencimento inicial parte do dia atual
            if periodo_selecionado == "Este Mês":
                data_ini_def = datetime.date.today()

            col_inicio, col_fim = st.columns([1, 1])
            with col_inicio:
                data_inicio = st.date_input(
                    "Vencimento inicial", data_ini_def, format=STREAMLIT_DATE_FORMAT
                )
            with col_fim:
                data_fim = st.date_input(
                    "Vencimento final", data_fim_def, format=STREAMLIT_DATE_FORMAT
                )

            opcoes_status = {
                "Projetado (Em Aberto)": "projetado",
                "Realizado (Pago/Recebido)": "realizado",
                "Todos": "todos",
            }
            status_sel = st.selectbox(
                "Status das Movimentações", list(opcoes_status.keys()), index=0
            )
            status_val = opcoes_status[status_sel]

            col_anom, col_dup = st.columns([1, 1])
            with col_anom:
                ignorar_anomalias = st.checkbox("Ignorar Anomalias", value=True)
            with col_dup:
                ignorar_duplicatas = st.checkbox("Ignorar Duplicatas", value=True)

        # ── Coluna Direita ─────────────────────────────────────────────────
        with col_direita:
            # Empresas
            empresas_ids = None
            if empresas_map:
                empresas_sel = st.multiselect(
                    "Empresas", list(empresas_map.keys()), default=list(empresas_map.keys())
                )
                if len(empresas_sel) < len(empresas_map):
                    empresas_ids = [empresas_map[nome] for nome in empresas_sel]

            # Bancos (separação dentro de cada empresa)
            bancos_ids = None
            if bancos_map:
                bancos_sel = st.multiselect(
                    "Bancos", list(bancos_map.keys()), default=list(bancos_map.keys())
                )
                if len(bancos_sel) < len(bancos_map):
                    bancos_ids = [bancos_map[nome] for nome in bancos_sel]

            # Grupos de Categorias
            grupos_categoria = None
            try:
                grupos_db = session.query(Categoria.grupo).distinct().all()
                grupos_lista = sorted([g[0] for g in grupos_db if g[0]])
                if grupos_lista:
                    grupos_sel = st.multiselect(
                        "Grupos / Categorias", grupos_lista, default=grupos_lista
                    )
                    if len(grupos_sel) < len(grupos_lista):
                        grupos_categoria = grupos_sel
            except Exception:
                pass

    # ── Quadro de Saldo Inicial (persistente entre páginas) ───────────────────
    persist = _garantir_persist_saldo(data_inicio, session=session)

    # ── Sincronização automática: Vencimento Inicial -> Saldo Inicial ─────────
    _ULTIMA_DATA_INICIO = "_ultima_data_inicio_sincronizada"
    data_inicio_anterior = st.session_state.get(_ULTIMA_DATA_INICIO)

    if data_inicio_anterior != data_inicio:
        st.session_state[_ULTIMA_DATA_INICIO] = data_inicio
        st.session_state["filtro_data_saldo_inicial"] = data_inicio
        persist["data"] = data_inicio

        # Puxa automaticamente o saldo registrado desta data no banco de dados
        if session is not None:
            from finance_app.services.saldo_service import obter_saldo_por_data
            res_saldo = obter_saldo_por_data(data_inicio, session=session)
            saldos_dict = persist.setdefault("saldos", {})
            if res_saldo:
                for (eid, bid), val in res_saldo["saldos"].items():
                    k = f"{eid}_{bid}"
                    saldos_dict[k] = float(val)
                    st.session_state[f"saldo_manual_{k}"] = float(val)
            else:
                if empresas_db and bancos_db:
                    for emp in empresas_db:
                        for bco in bancos_db:
                            k = f"{emp.id}_{bco.id}"
                            saldos_dict[k] = 0.0
                            st.session_state[f"saldo_manual_{k}"] = 0.0

    # Restaura widgets se o Streamlit limpou as chaves na navegação
    _restaurar_widget_se_ausente("filtro_usar_saldo_manual", bool(persist["usar"]))
    _restaurar_widget_se_ausente(
        "filtro_data_saldo_inicial",
        persist.get("data") or data_inicio,
    )

    with st.expander("💰 **Saldo Inicial**", expanded=bool(persist["usar"])):
        from finance_app.services.saldo_service import (
            obter_saldo_mais_recente,
            obter_saldo_por_data,
            listar_datas_com_saldo,
            salvar_saldos_banco,
            ler_e_atualizar_saldo_excel,
        )

        rec_oficial = obter_saldo_mais_recente(session) if session else None
        if rec_oficial:
            dt_oficial, mapa_oficial = rec_oficial
            tot_oficial = sum(mapa_oficial.values())
            st.caption(
                f"🏦 **Saldo Bancário Registrado Mais Recente**: `R$ {tot_oficial:,.2f}` (Data: {dt_oficial.strftime('%d/%m/%Y')})"
                .replace(",", "X").replace(".", ",").replace("X", ".")
            )

        col_chk, col_btn = st.columns([3, 2])
        with col_chk:
            usar_saldo_manual = st.checkbox(
                "Definir Saldo Inicial Manual",
                key="filtro_usar_saldo_manual",
            )
            persist["usar"] = bool(usar_saldo_manual)

        with col_btn:
            if st.button("🔄 Atualizar Saldo do Dia (Excel)", key="btn_quick_atualizar_saldo", use_container_width=True):
                try:
                    with st.spinner("Atualizando saldos bancários a partir do Excel..."):
                        res = ler_e_atualizar_saldo_excel(session=session)
                    tot_fmt = f"R$ {res['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.session_state["_msg_saldo_sucesso"] = (
                        f"✅ Saldo de {res['data'].strftime('%d/%m/%Y')} gravado no banco de dados com sucesso! Total: {tot_fmt}"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ Erro ao ler Excel: {exc}")

        if "_msg_saldo_sucesso" in st.session_state:
            st.success(st.session_state.pop("_msg_saldo_sucesso"))

        saldos_iniciais_por_conta: dict = {}
        data_saldo_inicial: Optional[datetime.date] = None

        if usar_saldo_manual:
            datas_gravadas = listar_datas_com_saldo(session) if session else []
            mapa_opcoes = {d["label"]: d for d in datas_gravadas}
            opcoes_dropdown = ["-- Selecione uma data gravada para puxar do banco --"] + [d["label"] for d in datas_gravadas]

            def _on_selecionar_data_gravada():
                sel = st.session_state.get("sel_data_banco_saldo")
                if sel and sel in mapa_opcoes:
                    d_info = mapa_opcoes[sel]
                    dt_sel = d_info["data"]
                    res_saldo = obter_saldo_por_data(dt_sel, session=session)
                    if res_saldo:
                        st.session_state["filtro_data_saldo_inicial"] = dt_sel
                        persist["data"] = dt_sel
                        st.session_state["_ultima_data_inicio_sincronizada"] = dt_sel
                        saldos_dict = persist.setdefault("saldos", {})
                        for (eid, bid), val in res_saldo["saldos"].items():
                            k = f"{eid}_{bid}"
                            saldos_dict[k] = float(val)
                            st.session_state[f"saldo_manual_{k}"] = float(val)
                        tot_fmt = f"R$ {res_saldo['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        st.session_state["_msg_saldo_sucesso"] = f"✅ Saldo do dia {dt_sel.strftime('%d/%m/%Y')} carregado do banco de dados! Total: {tot_fmt}"
                    # Reseta o dropdown para a opção neutra
                    st.session_state["sel_data_banco_saldo"] = opcoes_dropdown[0]

            col_puxar, col_data = st.columns([3, 2])
            with col_puxar:
                st.selectbox(
                    "📅 Puxar Saldo Gravado no Banco de Dados:",
                    options=opcoes_dropdown,
                    index=0,
                    key="sel_data_banco_saldo",
                    on_change=_on_selecionar_data_gravada,
                )

            with col_data:
                data_saldo_inicial = st.date_input(
                    "📅 Data do Saldo Inicial",
                    format=STREAMLIT_DATE_FORMAT,
                    key="filtro_data_saldo_inicial",
                )
                persist["data"] = data_saldo_inicial

            col_btn_puxar, col_btn_gravar = st.columns([1, 1])
            with col_btn_puxar:
                if st.button("📥 Puxar Saldo Desta Data do Banco", key="btn_puxar_saldo_data", use_container_width=True):
                    res_saldo = obter_saldo_por_data(data_saldo_inicial, session=session)
                    if res_saldo:
                        saldos_dict = persist.setdefault("saldos", {})
                        for (eid, bid), val in res_saldo["saldos"].items():
                            k = f"{eid}_{bid}"
                            saldos_dict[k] = float(val)
                            st.session_state[f"saldo_manual_{k}"] = float(val)
                        tot_fmt = f"R$ {res_saldo['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        st.session_state["_msg_saldo_sucesso"] = f"✅ Saldo de {data_saldo_inicial.strftime('%d/%m/%Y')} carregado do banco de dados! Total: {tot_fmt}"
                        st.rerun()
                    else:
                        st.warning(f"⚠️ Nenhum saldo gravado no banco de dados para a data {data_saldo_inicial.strftime('%d/%m/%Y')}.")

            with col_btn_gravar:
                if st.button("💾 Gravar Saldo Deste Dia no Banco de Dados", key="btn_salvar_saldo_banco", use_container_width=True, type="primary"):
                    mapa_para_salvar = {}
                    for emp in empresas_db:
                        for banco in bancos_db:
                            k = _chave_conta(emp.id, banco.id)
                            val = float(st.session_state.get(f"saldo_manual_{k}", 0.0))
                            mapa_para_salvar[(emp.id, banco.id)] = val
                    res = salvar_saldos_banco(
                        data_saldo=data_saldo_inicial,
                        saldos_map=mapa_para_salvar,
                        origem="MANUAL",
                        session=session,
                    )
                    st.cache_data.clear()
                    tot_fmt = f"R$ {res['total_geral']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    st.session_state["_msg_saldo_sucesso"] = f"💾 Saldo do dia {data_saldo_inicial.strftime('%d/%m/%Y')} gravado no banco de dados com sucesso! Total: {tot_fmt}"
                    st.rerun()

            if empresas_db and bancos_db:
                st.caption("Informe o saldo de cada empresa em cada banco na data selecionada:")
                saldos_salvos: dict = persist.setdefault("saldos", {})
                for emp in empresas_db:
                    st.markdown(f"**{emp.nome}**")
                    cols_banco = st.columns(len(bancos_db))
                    for idx, banco in enumerate(bancos_db):
                        with cols_banco[idx]:
                            conta_key = _chave_conta(emp.id, banco.id)
                            widget_key = f"saldo_manual_{conta_key}"
                            _restaurar_widget_se_ausente(
                                widget_key,
                                float(saldos_salvos.get(conta_key, 0.0)),
                            )
                            valor = st.number_input(
                                f"{banco.nome} (R$)",
                                step=1000.0,
                                format="%.2f",
                                key=widget_key,
                            )
                            valor_f = float(valor)
                            saldos_salvos[conta_key] = valor_f
                            saldos_iniciais_por_conta[(emp.id, banco.id)] = valor_f

                # Resumo visual consolidado dos saldos informados
                tot_atual = sum(saldos_iniciais_por_conta.values())
                tot_fmt = f"R$ {tot_atual:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                subtotais = []
                for emp in empresas_db:
                    tot_emp = sum(
                        val for (eid, bid), val in saldos_iniciais_por_conta.items() if eid == emp.id
                    )
                    if tot_emp != 0.0 or emp.nome in ["NPD", "COMPRE", "CS"]:
                        fmt_emp = f"R$ {tot_emp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        subtotais.append(f"{emp.nome}: `{fmt_emp}`")
                resumo_subtotais = " | ".join(subtotais)
                st.info(f"📊 **Total do Saldo ({data_saldo_inicial.strftime('%d/%m/%Y')}):** `{tot_fmt}`  \n{resumo_subtotais}")

            elif not empresas_db:
                st.warning("Nenhuma empresa cadastrada para definir saldo.")
            else:
                st.warning("Nenhum banco cadastrado para definir saldo.")
        else:
            # Checkbox desligado: ainda aplica os últimos saldos salvos se religar;
            # para o cálculo atual, não usa saldo manual.
            saldos_iniciais_por_conta = {}
            data_saldo_inicial = None

    filtros = FiltrosPesquisa(
        data_inicio=data_inicio,
        data_fim=data_fim,
        empresas_ids=empresas_ids,
        bancos_ids=bancos_ids,
        grupos_categoria=grupos_categoria,
        status=status_val,
        ignorar_anomalias=ignorar_anomalias,
        ignorar_duplicatas=ignorar_duplicatas,
        usar_saldo_manual=usar_saldo_manual,
        saldos_iniciais_por_conta=saldos_iniciais_por_conta,
        data_saldo_inicial=data_saldo_inicial,
    )
    return filtros
