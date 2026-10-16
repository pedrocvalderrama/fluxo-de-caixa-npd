"""Utilitários de manipulação de datas para o sistema financeiro."""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple, Dict
import calendar

# Constants
DATE_FORMAT_BR = "%d/%m/%Y"
DATE_FORMAT_ISO = "%Y-%m-%d"
MONTHS_PT_BR = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}
MONTHS_PT_BR_SHORT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr",
    5: "Mai", 6: "Jun", 7: "Jul", 8: "Ago",
    9: "Set", 10: "Out", 11: "Nov", 12: "Dez"
}

def formatar_data(d: date | datetime | None) -> str:
    """Formata data para DD/MM/YYYY. Retorna string vazia para None."""
    if d is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(d):
            return ""
    except (TypeError, ValueError, ImportError):
        pass
    if isinstance(d, datetime):
        return d.strftime(DATE_FORMAT_BR)
    if isinstance(d, date):
        return d.strftime(DATE_FORMAT_BR)
    # Timestamp pandas ou similar
    if hasattr(d, "strftime"):
        try:
            return d.strftime(DATE_FORMAT_BR)
        except Exception:
            return ""
    return ""


def formatar_data_hora(d: date | datetime | None) -> str:
    """Formata data/hora para DD/MM/YYYY HH:MM."""
    if d is None:
        return ""
    try:
        import pandas as pd
        if pd.isna(d):
            return ""
    except (TypeError, ValueError, ImportError):
        pass
    if isinstance(d, datetime):
        return d.strftime("%d/%m/%Y %H:%M")
    if isinstance(d, date):
        return d.strftime(DATE_FORMAT_BR)
    if hasattr(d, "strftime"):
        try:
            return d.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return ""
    return ""


def formatar_coluna_data_para_exibicao(serie):
    """Converte uma Series de datas para strings DD/MM/YYYY (exibição em tabelas)."""
    import pandas as pd

    def _fmt(v):
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(v, (date, datetime)) or hasattr(v, "strftime"):
            return formatar_data(v)
        parsed = parse_data_excel(v)
        return formatar_data(parsed) if parsed else str(v)

    return serie.map(_fmt)


def formatar_datas_dataframe(df, colunas: list[str] | None = None):
    """
    Retorna cópia do DataFrame com colunas de data em formato PT-BR (DD/MM/YYYY).
    Se colunas não for informado, detecta automaticamente colunas datetime/date
    e nomes comuns (data, data_transacao, vencimento, etc.).
    """
    import pandas as pd

    if df is None or df.empty:
        return df

    out = df.copy()
    nomes_comuns = {
        "data", "data_transacao", "vencimento", "created_at", "updated_at",
        "data_importacao", "data_saldo_inicial",
    }

    if colunas is None:
        colunas = []
        for col in out.columns:
            if pd.api.types.is_datetime64_any_dtype(out[col]):
                colunas.append(col)
            elif str(col).lower() in nomes_comuns:
                colunas.append(col)
            elif out[col].dtype == object:
                sample = out[col].dropna().head(5)
                if not sample.empty and all(isinstance(v, (date, datetime)) for v in sample):
                    colunas.append(col)

    for col in colunas:
        if col in out.columns:
            out[col] = formatar_coluna_data_para_exibicao(out[col])
    return out


STREAMLIT_DATE_FORMAT = "DD/MM/YYYY"
PLOTLY_DATE_FORMAT = "%d/%m/%Y"

def parse_data(texto: str) -> date | None:
    """Faz o parse de uma string de data para objeto date."""
    if not texto or not isinstance(texto, str):
        return None
    texto = texto.strip()
    for fmt in (DATE_FORMAT_BR, DATE_FORMAT_ISO, "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(texto, fmt).date()
        except ValueError:
            pass
    return None

def parse_data_excel(valor) -> date | None:
    """Faz parse de valores de data do Excel (datetime, string, int/float serial).
    
    Trata corretamente pandas.NaT, None, strings, datetimes e seriais do Excel.
    """
    import math
    # Verificar nulo/NaT primeiro (pandas.NaT, None, float NaN)
    try:
        import pandas as pd
        if pd.isna(valor):
            return None
    except (TypeError, ValueError):
        pass  # pd.isna levanta TypeError para alguns tipos não-escalares
    
    if valor is None:
        return None
    if isinstance(valor, datetime):
        try:
            d = valor.date()
            # Garantir que não é NaT disfarçado (year muito baixo indica problema)
            if d.year < 100:
                return None
            return d
        except (ValueError, AttributeError, OverflowError):
            return None
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        return parse_data(valor.strip())
    if isinstance(valor, (int, float)):
        if math.isnan(valor):
            return None
        try:
            return (datetime(1899, 12, 30) + timedelta(days=int(valor))).date()
        except (ValueError, OverflowError):
            return None
    return None

def is_data_anomala(d: date | None) -> bool:
    """Verifica se a data é anômala (antes de 1950 ou depois de 2050)."""
    if not d:
        return False
    return d.year < 1950 or d.year > 2050

def nome_mes(mes: int) -> str:
    """Retorna nome do mês em PT-BR."""
    return MONTHS_PT_BR.get(mes, "")

def nome_mes_curto(mes: int) -> str:
    """Retorna nome curto do mês em PT-BR."""
    return MONTHS_PT_BR_SHORT.get(mes, "")

def periodo_label(data_inicio: date, data_fim: date) -> str:
    """Cria label de período legível."""
    return f"{nome_mes_curto(data_inicio.month)}/{data_inicio.year} a {nome_mes_curto(data_fim.month)}/{data_fim.year}"

def primeiro_dia_mes(d: date) -> date:
    """Primeiro dia do mês."""
    return date(d.year, d.month, 1)

def ultimo_dia_mes(d: date) -> date:
    """Último dia do mês."""
    _, last_day = calendar.monthrange(d.year, d.month)
    return date(d.year, d.month, last_day)

def primeiro_dia_ano(d: date) -> date:
    """Primeiro dia do ano."""
    return date(d.year, 1, 1)

def ultimo_dia_ano(d: date) -> date:
    """Último dia do ano."""
    return date(d.year, 12, 31)

def mes_anterior(d: date) -> tuple[date, date]:
    """Retorna (primeiro_dia, ultimo_dia) do mês anterior."""
    first_day_current = primeiro_dia_mes(d)
    last_day_previous = first_day_current - timedelta(days=1)
    return primeiro_dia_mes(last_day_previous), last_day_previous

def mesmo_mes_ano_anterior(d: date) -> tuple[date, date]:
    """Retorna (primeiro_dia, ultimo_dia) do mesmo mês no ano anterior."""
    try:
        dt = date(d.year - 1, d.month, d.day)
    except ValueError:
        dt = date(d.year - 1, d.month, 28)
    first = primeiro_dia_mes(dt)
    last = ultimo_dia_mes(dt)
    return first, last

def ultimos_n_dias(n: int, referencia: date | None = None) -> tuple[date, date]:
    """Retorna (inicio, fim) para os últimos N dias."""
    ref = referencia or date.today()
    return ref - timedelta(days=n), ref

def periodos_rapidos() -> dict[str, tuple[date, date]]:
    """Retorna dicionário de seleções de período rápido."""
    hoje = date.today()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    
    return {
        "Hoje": (hoje, hoje),
        "Esta Semana": (inicio_semana, fim_semana),
        "Este Mês": (primeiro_dia_mes(hoje), ultimo_dia_mes(hoje)),
        "Mês Anterior": mes_anterior(hoje),
        "Últimos 30 dias": ultimos_n_dias(30, hoje),
        "Últimos 90 dias": ultimos_n_dias(90, hoje),
        "Este Ano": (primeiro_dia_ano(hoje), ultimo_dia_ano(hoje)),
        "Ano Anterior": (date(hoje.year - 1, 1, 1), date(hoje.year - 1, 12, 31))
    }

def trimestre(d: date) -> int:
    """Retorna número do trimestre (1-4)."""
    return (d.month - 1) // 3 + 1

def semana_do_ano(d: date) -> int:
    """Retorna número da semana ISO."""
    return d.isocalendar()[1]

def dias_uteis_no_periodo(inicio: date, fim: date) -> int:
    """Conta dias úteis (Seg-Sex) no período."""
    delta = fim - inicio
    dias = 0
    for i in range(delta.days + 1):
        if (inicio + timedelta(days=i)).weekday() < 5:
            dias += 1
    return dias
