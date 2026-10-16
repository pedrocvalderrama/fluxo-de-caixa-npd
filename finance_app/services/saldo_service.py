"""
Serviço para leitura, validação e persistência do Saldo Diário bancário a partir do arquivo Excel da tesouraria.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Optional, Dict, Any, Tuple, List

import openpyxl
from sqlalchemy import func
from sqlalchemy.orm import Session

from finance_app.database.connection import get_session
from finance_app.database.models import Empresa, Banco, SaldoDiario, SaldoDiarioConsolidado
from finance_app.database.repositories.empresa_repo import EmpresaRepository
from finance_app.database.repositories.banco_repo import BancoRepository

# Caminho padrão na rede da empresa
DEFAULT_SALDO_EXCEL_PATH = r"U:\.NPD BACKUP DIARIO\.NPD BACKUP DIARIO\FINANCEIRO\RELATORIO DIARIO FINANCEIRO.xlsx"

# Mapeamento exato das células conforme informado:
# (Linha Excel, Código Empresa, Nome Empresa, Código Banco, Nome Banco)
MAPEAMENTO_SALDO_EXCEL = [
    (3, "_004", "CS", "001", "Banco do Brasil"),
    (4, "_004", "CS", "748", "Sicredi"),
    (6, "_001", "NPD", "001", "Banco do Brasil"),
    (7, "_001", "NPD", "033", "Santander"),
    (8, "_001", "NPD", "748", "Sicredi"),
    (10, "_002", "COMPRE", "001", "Banco do Brasil"),
    (11, "_002", "COMPRE", "033", "Santander"),
    (12, "_002", "COMPRE", "748", "Sicredi"),
]


def _parse_valor(v: Any) -> float:
    """Converte valor numérico ou string monetária brasileira para float."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("R$", "").replace(" ", "")
    if not s:
        return 0.0
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def _parse_data(v: Any) -> Optional[date]:
    """Extrai objeto date a partir de datetime, date ou string."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        v = v.strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"):
            try:
                return datetime.strptime(v, fmt).date()
            except ValueError:
                pass
        m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})", v)
        if m:
            d, mes, y = m.groups()
            y_int = int(y)
            if y_int < 100:
                y_int += 2000
            return date(y_int, int(mes), int(d))
    return None


def ler_e_atualizar_saldo_excel(
    caminho_arquivo: Optional[str] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Lê o arquivo Excel de relatório diário financeiro e grava/atualiza os saldos no banco SQLite.
    Sincroniza também com o estado do Streamlit (se ativo).
    """
    caminho = caminho_arquivo or DEFAULT_SALDO_EXCEL_PATH
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo não encontrado no caminho: {caminho}")

    wb = openpyxl.load_workbook(caminho, data_only=True)
    ws = wb.active
    if ws is None:
        raise ValueError("Nenhuma planilha ativa encontrada no arquivo Excel.")

    # Linha 1, Coluna C (índices 1-based: cell(1, 3))
    raw_data = ws.cell(1, 3).value
    data_saldo = _parse_data(raw_data)
    if data_saldo is None:
        # Fallback de busca na linha 1
        for col in range(1, 6):
            dt_cand = _parse_data(ws.cell(1, col).value)
            if dt_cand:
                data_saldo = dt_cand
                break

    if data_saldo is None:
        raise ValueError("Não foi possível identificar a data dos saldos na Linha 1 Coluna C do arquivo.")

    def _executar(s: Session) -> Dict[str, Any]:
        repo_emp = EmpresaRepository(s)
        repo_bco = BancoRepository(s)

        detalhes: List[Dict[str, Any]] = []

        for linha, emp_cod, emp_nome, bco_cod, bco_nome_padrao in MAPEAMENTO_SALDO_EXCEL:
            # Garante Empresa
            empresa = repo_emp.get_by_codigo(emp_cod)
            if not empresa:
                empresa = repo_emp.get_by_nome(emp_nome)
            if not empresa:
                empresa = repo_emp.get_or_create(emp_cod, emp_nome)
                s.flush()

            # Garante Banco
            banco = repo_bco.get_by_codigo(bco_cod)
            if not banco:
                banco = repo_bco.get_or_create(bco_cod, bco_nome_padrao)
                s.flush()

            # Lê valor da célula
            raw_val = ws.cell(linha, 3).value
            saldo_val = _parse_valor(raw_val)

            # Upsert no banco SQLite
            reg = (
                s.query(SaldoDiario)
                .filter(
                    SaldoDiario.data == data_saldo,
                    SaldoDiario.empresa_id == empresa.id,
                    SaldoDiario.banco_id == banco.id,
                )
                .first()
            )

            if reg:
                reg.saldo = saldo_val
                reg.updated_at = datetime.now()
            else:
                reg = SaldoDiario(
                    data=data_saldo,
                    empresa_id=empresa.id,
                    banco_id=banco.id,
                    saldo=saldo_val,
                )
                s.add(reg)

            detalhes.append({
                "linha": linha,
                "empresa": empresa.nome,
                "empresa_id": empresa.id,
                "empresa_codigo": empresa.codigo,
                "banco": banco.nome,
                "banco_id": banco.id,
                "banco_codigo": banco.codigo,
                "saldo": saldo_val,
            })

        total_geral = sum(d["saldo"] for d in detalhes)
        por_empresa: Dict[str, float] = {}
        for d in detalhes:
            por_empresa[d["empresa"]] = por_empresa.get(d["empresa"], 0.0) + d["saldo"]

        saldo_npd = sum(d["saldo"] for d in detalhes if "NPD" in str(d["empresa"]).upper())
        saldo_compre = sum(
            d["saldo"] for d in detalhes
            if "COMPRE" in str(d["empresa"]).upper() or "SACOLA" in str(d["empresa"]).upper()
        )
        saldo_cs = sum(d["saldo"] for d in detalhes if "CS" in str(d["empresa"]).upper())

        reg_cons = s.query(SaldoDiarioConsolidado).filter(SaldoDiarioConsolidado.data == data_saldo).first()
        if reg_cons:
            reg_cons.saldo_total = total_geral
            reg_cons.saldo_npd = saldo_npd
            reg_cons.saldo_compre = saldo_compre
            reg_cons.saldo_cs = saldo_cs
            reg_cons.origem = "EXCEL"
            reg_cons.updated_at = datetime.now()
        else:
            reg_cons = SaldoDiarioConsolidado(
                data=data_saldo,
                saldo_total=total_geral,
                saldo_npd=saldo_npd,
                saldo_compre=saldo_compre,
                saldo_cs=saldo_cs,
                origem="EXCEL",
            )
            s.add(reg_cons)

        s.commit()

        # Sincroniza com st.session_state se estiver rodando dentro do Streamlit ativo
        try:
            import streamlit as st
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx() is not None:
                st.cache_data.clear()
                _PERSIST_SALDO = "_persist_saldo_inicial"
                persist = st.session_state.setdefault(
                    _PERSIST_SALDO,
                    {"usar": True, "data": data_saldo, "saldos": {}},
                )
                persist["usar"] = True
                persist["data"] = data_saldo
                saldos_dict = persist.setdefault("saldos", {})

                st.session_state["filtro_usar_saldo_manual"] = True
                st.session_state["filtro_data_saldo_inicial"] = data_saldo

                for item in detalhes:
                    conta_key = f"{item['empresa_id']}_{item['banco_id']}"
                    saldos_dict[conta_key] = item["saldo"]
                    st.session_state[f"saldo_manual_{conta_key}"] = item["saldo"]
        except Exception:
            pass

        return {
            "sucesso": True,
            "data": data_saldo,
            "total_geral": total_geral,
            "saldo_npd": saldo_npd,
            "saldo_compre": saldo_compre,
            "saldo_cs": saldo_cs,
            "por_empresa": por_empresa,
            "detalhes": detalhes,
            "arquivo": caminho,
        }

    if session is not None:
        return _executar(session)
    else:
        with get_session() as s:
            return _executar(s)


def salvar_saldos_banco(
    data_saldo: date,
    saldos_map: Dict[Tuple[int, int], float],
    origem: str = "MANUAL",
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Grava ou atualiza os saldos bancários no banco SQLite:
    - Grava na tabela granular saldos_diarios (empresa x banco).
    - Grava na tabela saldos_diarios_consolidados (total e totais por empresa).
    """
    def _executar(s: Session) -> Dict[str, Any]:
        empresas = {e.id: e.nome for e in s.query(Empresa).all()}
        bancos = {b.id: b.nome for b in s.query(Banco).all()}

        total_geral = 0.0
        saldo_npd = 0.0
        saldo_compre = 0.0
        saldo_cs = 0.0
        detalhes: List[Dict[str, Any]] = []

        for (emp_id, bco_id), valor in saldos_map.items():
            val_f = float(valor or 0.0)
            total_geral += val_f

            nome_emp = empresas.get(emp_id, "").upper()
            if "NPD" in nome_emp:
                saldo_npd += val_f
            elif "COMPRE" in nome_emp or "SACOLA" in nome_emp:
                saldo_compre += val_f
            elif "CS" in nome_emp:
                saldo_cs += val_f

            reg = (
                s.query(SaldoDiario)
                .filter(
                    SaldoDiario.data == data_saldo,
                    SaldoDiario.empresa_id == emp_id,
                    SaldoDiario.banco_id == bco_id,
                )
                .first()
            )
            if reg:
                reg.saldo = val_f
                reg.updated_at = datetime.now()
            else:
                reg = SaldoDiario(
                    data=data_saldo,
                    empresa_id=emp_id,
                    banco_id=bco_id,
                    saldo=val_f,
                )
                s.add(reg)

            detalhes.append({
                "empresa_id": emp_id,
                "empresa": empresas.get(emp_id, f"Empresa {emp_id}"),
                "banco_id": bco_id,
                "banco": bancos.get(bco_id, f"Banco {bco_id}"),
                "saldo": val_f,
            })

        # Upsert no consolidado
        reg_cons = s.query(SaldoDiarioConsolidado).filter(SaldoDiarioConsolidado.data == data_saldo).first()
        if reg_cons:
            reg_cons.saldo_total = total_geral
            reg_cons.saldo_npd = saldo_npd
            reg_cons.saldo_compre = saldo_compre
            reg_cons.saldo_cs = saldo_cs
            reg_cons.origem = origem
            reg_cons.updated_at = datetime.now()
        else:
            reg_cons = SaldoDiarioConsolidado(
                data=data_saldo,
                saldo_total=total_geral,
                saldo_npd=saldo_npd,
                saldo_compre=saldo_compre,
                saldo_cs=saldo_cs,
                origem=origem,
            )
            s.add(reg_cons)

        s.commit()

        return {
            "sucesso": True,
            "data": data_saldo,
            "total_geral": total_geral,
            "saldo_npd": saldo_npd,
            "saldo_compre": saldo_compre,
            "saldo_cs": saldo_cs,
            "detalhes": detalhes,
            "origem": origem,
        }

    if session is not None:
        return _executar(session)
    else:
        with get_session() as s:
            return _executar(s)


def obter_saldo_por_data(
    data_saldo: date,
    session: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """
    Retorna o saldo registrado no banco SQLite para uma data específica.
    """
    def _executar(s: Session) -> Optional[Dict[str, Any]]:
        registros = s.query(SaldoDiario).filter(SaldoDiario.data == data_saldo).all()
        if not registros:
            return None

        saldos_map: Dict[Tuple[int, int], float] = {
            (r.empresa_id, r.banco_id): float(r.saldo) for r in registros
        }
        total = sum(r.saldo for r in registros)

        cons = s.query(SaldoDiarioConsolidado).filter(SaldoDiarioConsolidado.data == data_saldo).first()
        origem = cons.origem if cons else "EXCEL"

        return {
            "data": data_saldo,
            "total_geral": total,
            "saldos": saldos_map,
            "origem": origem,
            "consolidado": cons,
        }

    if session is not None:
        return _executar(session)
    else:
        with get_session() as s:
            return _executar(s)


def listar_datas_com_saldo(session: Session, limit: int = 180) -> List[Dict[str, Any]]:
    """
    Retorna lista das datas disponíveis com saldos gravados, ordenadas da mais recente para a mais antiga.
    Cada item contém 'data', 'total', 'origem' e 'label' formatado para o selectbox.
    """
    registros_cons = (
        session.query(SaldoDiarioConsolidado)
        .order_by(SaldoDiarioConsolidado.data.desc())
        .limit(limit)
        .all()
    )
    if registros_cons:
        resultado = []
        for c in registros_cons:
            tot_fmt = f"R$ {c.saldo_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            resultado.append({
                "data": c.data,
                "total": c.saldo_total,
                "origem": c.origem or "EXCEL",
                "label": f"{c.data.strftime('%d/%m/%Y')} — Total: {tot_fmt}",
            })
        return resultado

    # Fallback para saldos_diarios se consolidados ainda não existirem
    datas = (
        session.query(SaldoDiario.data)
        .distinct()
        .order_by(SaldoDiario.data.desc())
        .limit(limit)
        .all()
    )
    resultado = []
    for (d,) in datas:
        regs = session.query(SaldoDiario).filter(SaldoDiario.data == d).all()
        total = sum(r.saldo for r in regs)
        tot_fmt = f"R$ {total:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        resultado.append({
            "data": d,
            "total": total,
            "origem": "EXCEL",
            "label": f"{d.strftime('%d/%m/%Y')} — Total: {tot_fmt}",
        })
    return resultado


def backfill_saldos_consolidados(session: Session) -> int:
    """
    Garante que todas as datas presentes em saldos_diarios tenham registro em saldos_diarios_consolidados.
    Retorna o número de registros criados/atualizados.
    """
    datas = [d[0] for d in session.query(SaldoDiario.data).distinct().all()]
    if not datas:
        return 0

    empresas = {e.id: e.nome for e in session.query(Empresa).all()}
    count = 0

    for d in datas:
        cons = session.query(SaldoDiarioConsolidado).filter(SaldoDiarioConsolidado.data == d).first()
        regs = session.query(SaldoDiario).filter(SaldoDiario.data == d).all()
        total = sum(r.saldo for r in regs)

        saldo_npd = sum(r.saldo for r in regs if "NPD" in empresas.get(r.empresa_id, "").upper())
        saldo_compre = sum(
            r.saldo for r in regs
            if "COMPRE" in empresas.get(r.empresa_id, "").upper() or "SACOLA" in empresas.get(r.empresa_id, "").upper()
        )
        saldo_cs = sum(r.saldo for r in regs if "CS" in empresas.get(r.empresa_id, "").upper())

        if not cons:
            cons = SaldoDiarioConsolidado(
                data=d,
                saldo_total=total,
                saldo_npd=saldo_npd,
                saldo_compre=saldo_compre,
                saldo_cs=saldo_cs,
                origem="EXCEL",
            )
            session.add(cons)
            count += 1
        else:
            cons.saldo_total = total
            cons.saldo_npd = saldo_npd
            cons.saldo_compre = saldo_compre
            cons.saldo_cs = saldo_cs

    session.commit()
    return count


def obter_saldo_mais_recente(session: Session) -> Optional[Tuple[date, Dict[Tuple[int, int], float]]]:
    """
    Retorna a data mais recente com saldos cadastrados e o dicionário (empresa_id, banco_id) -> saldo.
    """
    max_data = session.query(func.max(SaldoDiario.data)).scalar()
    if not max_data:
        return None

    registros = session.query(SaldoDiario).filter(SaldoDiario.data == max_data).all()
    saldos_map: Dict[Tuple[int, int], float] = {
        (r.empresa_id, r.banco_id): r.saldo for r in registros
    }
    return max_data, saldos_map


def obter_historico_saldos(session: Session, limit: int = 30) -> List[Dict[str, Any]]:
    """Retorna datas recentes com seus totais consolidados."""
    datas = (
        session.query(SaldoDiario.data)
        .distinct()
        .order_by(SaldoDiario.data.desc())
        .limit(limit)
        .all()
    )
    resultado = []
    for (d,) in datas:
        regs = session.query(SaldoDiario).filter(SaldoDiario.data == d).all()
        total = sum(r.saldo for r in regs)
        resultado.append({
            "data": d,
            "total": total,
            "qtd_contas": len(regs),
        })
    return resultado
