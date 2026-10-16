"""
Validação dos dados extraídos do Excel antes da importação.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import pandas as pd

from finance_app.utils.dates import is_data_anomala, parse_data_excel, formatar_data
from finance_app.config.bancos import resolver_codigo_banco

class SeveridadeProblema(Enum):
    ERRO = "ERRO"        # Impede importação da linha
    AVISO = "AVISO"      # Linha importada com ressalvas
    INFO = "INFO"        # Apenas informativo

@dataclass
class ProblemaValidacao:
    linha: int           # Número da linha no Excel
    coluna: str          # Nome da coluna com problema
    severidade: SeveridadeProblema
    mensagem: str
    valor_original: str  # Valor que causou o problema

@dataclass
class ResultadoValidacao:
    total_linhas: int
    linhas_validas: int
    linhas_com_aviso: int
    linhas_com_erro: int
    linhas_em_aberto: int    # Sem data de transação
    linhas_com_data_anomala: int
    linhas_com_valor_zero: int
    problemas: list[ProblemaValidacao] = field(default_factory=list)
    
    @property
    def pode_importar(self) -> bool:
        """True se há pelo menos uma linha válida para importar."""
        return self.linhas_validas > 0
    
    def resumo_texto(self) -> str:
        """Gera texto resumido do resultado da validação."""
        linhas = [
            f"Total de registros: {self.total_linhas:,}",
            f"Registros válidos: {self.linhas_validas:,}",
            f"Registros com aviso: {self.linhas_com_aviso:,}",
            f"Registros com erro: {self.linhas_com_erro:,}",
            f"Títulos em aberto (sem data pagamento): {self.linhas_em_aberto:,}",
            f"Datas anômalas: {self.linhas_com_data_anomala:,}",
            f"Registros com valor zero: {self.linhas_com_valor_zero:,}",
        ]
        return "\n".join(linhas)

def validar_dataframe(df: pd.DataFrame) -> ResultadoValidacao:
    """Valida as linhas do DataFrame importado do Excel segundo regras de negócio."""
    resultado = ResultadoValidacao(
        total_linhas=len(df),
        linhas_validas=0,
        linhas_com_aviso=0,
        linhas_com_erro=0,
        linhas_em_aberto=0,
        linhas_com_data_anomala=0,
        linhas_com_valor_zero=0,
        problemas=[]
    )
    
    for _, row in df.iterrows():
        linha_excel = int(row['linha_excel'])
        erros_linha = 0
        avisos_linha = 0
        
        is_em_aberto = False
        
        # 1. Empresa
        empresa = row['empresa']
        if pd.isna(empresa) or str(empresa).strip() == "":
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'empresa', SeveridadeProblema.ERRO, "Empresa não pode ser vazia", str(empresa)))
            erros_linha += 1

        # 1b. Banco (opcional; aviso se informado e não reconhecido)
        if 'banco' in row.index:
            banco_raw = row['banco']
            if pd.notna(banco_raw) and str(banco_raw).strip() != "":
                if resolver_codigo_banco(str(banco_raw)) is None:
                    resultado.problemas.append(ProblemaValidacao(
                        linha_excel, 'banco', SeveridadeProblema.AVISO,
                        "Banco não reconhecido (use Banco do Brasil, Santander ou Sicred)",
                        str(banco_raw),
                    ))
                    avisos_linha += 1

        # 2. Movimentação
        mov = str(row['movimentacao']).strip().upper() if pd.notna(row['movimentacao']) else ""
        if mov not in ['PAGAR', 'RECEBER']:
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'movimentacao', SeveridadeProblema.ERRO, "Movimentação deve ser PAGAR ou RECEBER", str(row['movimentacao'])))
            erros_linha += 1
            
        # 3. Titular
        titular = row['titular']
        if pd.isna(titular) or str(titular).strip() == "":
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'titular', SeveridadeProblema.AVISO, "Titular não preenchido", str(titular)))
            avisos_linha += 1
            
        # 4. Natureza
        natureza = row['natureza']
        if pd.isna(natureza) or str(natureza).strip() == "":
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'natureza', SeveridadeProblema.AVISO, "Natureza não preenchida", str(natureza)))
            avisos_linha += 1
            
        # 5. Data da Transação
        dt_transacao = row['data_transacao']
        if pd.isna(dt_transacao):
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'data_transacao', SeveridadeProblema.INFO, "Título em aberto", str(dt_transacao)))
            is_em_aberto = True
            resultado.linhas_em_aberto += 1
        else:
            dt_parsed = parse_data_excel(dt_transacao)
            if dt_parsed is None:
                resultado.problemas.append(ProblemaValidacao(linha_excel, 'data_transacao', SeveridadeProblema.AVISO, "Data da transação inválida", str(dt_transacao)))
                avisos_linha += 1
            elif is_data_anomala(dt_parsed):
                resultado.problemas.append(ProblemaValidacao(linha_excel, 'data_transacao', SeveridadeProblema.AVISO, f"Data anômala: {formatar_data(dt_parsed)}", str(dt_transacao)))
                avisos_linha += 1
                resultado.linhas_com_data_anomala += 1
                
        # 6. Vencimento
        vencimento = row['vencimento']
        if pd.notna(vencimento) and str(vencimento).strip() != "":
            dt_venc = parse_data_excel(vencimento)
            if dt_venc is not None and is_data_anomala(dt_venc):
                resultado.problemas.append(ProblemaValidacao(linha_excel, 'vencimento', SeveridadeProblema.AVISO, f"Data anômala: {formatar_data(dt_venc)}", str(vencimento)))
                avisos_linha += 1
                
        # 7. Valor
        valor = row['valor']
        if pd.isna(valor) or str(valor).strip() == "":
            resultado.problemas.append(ProblemaValidacao(linha_excel, 'valor', SeveridadeProblema.ERRO, "Valor não preenchido", str(valor)))
            erros_linha += 1
        else:
            try:
                v = float(valor)
                if v < 0:
                    resultado.problemas.append(ProblemaValidacao(linha_excel, 'valor', SeveridadeProblema.AVISO, "Valor não deveria ser negativo", str(valor)))
                    avisos_linha += 1
                elif v == 0:
                    resultado.linhas_com_valor_zero += 1
                    if not is_em_aberto:
                        resultado.problemas.append(ProblemaValidacao(linha_excel, 'valor', SeveridadeProblema.INFO, "Valor é zero", str(valor)))
            except ValueError:
                resultado.problemas.append(ProblemaValidacao(linha_excel, 'valor', SeveridadeProblema.ERRO, "Valor não numérico", str(valor)))
                erros_linha += 1
                
        if erros_linha > 0:
            resultado.linhas_com_erro += 1
        elif avisos_linha > 0:
            resultado.linhas_com_aviso += 1
        else:
            resultado.linhas_validas += 1
            
    return resultado
