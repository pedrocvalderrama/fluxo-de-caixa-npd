"""
Modelos ORM (SQLAlchemy) para o banco de dados.
"""
from datetime import date, datetime
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Boolean, Float, Date, DateTime, Text, ForeignKey, func, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finance_app.database.connection import Base

class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    movimentacoes: Mapped[List["Movimentacao"]] = relationship("Movimentacao", back_populates="empresa")

    def __repr__(self) -> str:
        return f"<Empresa(id={self.id}, codigo='{self.codigo}', nome='{self.nome}')>"


class Banco(Base):
    __tablename__ = "bancos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    movimentacoes: Mapped[List["Movimentacao"]] = relationship("Movimentacao", back_populates="banco")

    def __repr__(self) -> str:
        return f"<Banco(id={self.id}, codigo='{self.codigo}', nome='{self.nome}')>"

class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    codigo: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nome: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    grupo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tipo_predominante: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    movimentacoes: Mapped[List["Movimentacao"]] = relationship("Movimentacao", back_populates="categoria")

    def __repr__(self) -> str:
        return f"<Categoria(id={self.id}, nome='{self.nome}', grupo='{self.grupo}')>"

class Importacao(Base):
    __tablename__ = "importacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arquivo: Mapped[str] = mapped_column(String(500), nullable=False)
    hash_arquivo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    data_importacao: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    qtd_registros: Mapped[int] = mapped_column(Integer, default=0)
    qtd_erros: Mapped[int] = mapped_column(Integer, default=0)
    qtd_duplicados: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default='PENDENTE')
    observacoes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    movimentacoes_raw: Mapped[List["MovimentacaoRaw"]] = relationship("MovimentacaoRaw", back_populates="importacao")
    movimentacoes: Mapped[List["Movimentacao"]] = relationship("Movimentacao", back_populates="importacao")

    def __repr__(self) -> str:
        return f"<Importacao(id={self.id}, arquivo='{self.arquivo}', status='{self.status}')>"

class MovimentacaoRaw(Base):
    __tablename__ = "movimentacoes_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    importacao_id: Mapped[int] = mapped_column(ForeignKey("importacoes.id"), nullable=False)
    empresa_original: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    banco_original: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    movimentacao_original: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    titular_original: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    natureza_original: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    data_transacao_original: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vencimento_original: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    valor_original: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    documento_original: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    centro_custo_original: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    linha_excel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    importacao: Mapped["Importacao"] = relationship("Importacao", back_populates="movimentacoes_raw")
    movimentacao: Mapped[Optional["Movimentacao"]] = relationship("Movimentacao", back_populates="raw", uselist=False)

    def __repr__(self) -> str:
        return f"<MovimentacaoRaw(id={self.id}, linha_excel={self.linha_excel})>"

class Movimentacao(Base):
    __tablename__ = "movimentacoes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_id: Mapped[Optional[int]] = mapped_column(ForeignKey("movimentacoes_raw.id"), unique=True, nullable=True)
    importacao_id: Mapped[int] = mapped_column(ForeignKey("importacoes.id"), nullable=False)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    banco_id: Mapped[Optional[int]] = mapped_column(ForeignKey("bancos.id"), nullable=True)
    categoria_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categorias.id"), nullable=True)
    
    data_transacao: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vencimento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    titular: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)
    valor: Mapped[float] = mapped_column(Float, nullable=False)
    valor_absoluto: Mapped[float] = mapped_column(Float, nullable=False)
    documento: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    centro_custo: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hash_registro: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    
    is_duplicata: Mapped[bool] = mapped_column(Boolean, default=False)
    is_anomalia_data: Mapped[bool] = mapped_column(Boolean, default=False)
    em_aberto: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    raw: Mapped[Optional["MovimentacaoRaw"]] = relationship("MovimentacaoRaw", back_populates="movimentacao")
    importacao: Mapped["Importacao"] = relationship("Importacao", back_populates="movimentacoes")
    empresa: Mapped["Empresa"] = relationship("Empresa", back_populates="movimentacoes")
    banco: Mapped[Optional["Banco"]] = relationship("Banco", back_populates="movimentacoes")
    categoria: Mapped[Optional["Categoria"]] = relationship("Categoria", back_populates="movimentacoes")

    __table_args__ = (
        Index('idx_mov_data', 'data_transacao'),
        Index('idx_mov_tipo', 'tipo'),
        Index('idx_mov_empresa', 'empresa_id'),
        Index('idx_mov_banco', 'banco_id'),
        Index('idx_mov_categoria', 'categoria_id'),
        Index('idx_mov_data_tipo', 'data_transacao', 'tipo'),
        Index('idx_mov_hash', 'hash_registro'),
        Index('idx_mov_documento', 'documento'),
        Index('idx_mov_centro_custo', 'centro_custo'),
    )

    def __repr__(self) -> str:
        return f"<Movimentacao(id={self.id}, tipo='{self.tipo}', valor={self.valor})>"


class SaldoDiario(Base):
    __tablename__ = "saldos_diarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False)
    banco_id: Mapped[int] = mapped_column(ForeignKey("bancos.id"), nullable=False)
    saldo: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    empresa: Mapped["Empresa"] = relationship("Empresa")
    banco: Mapped["Banco"] = relationship("Banco")

    __table_args__ = (
        Index('idx_saldo_data_empresa_banco', 'data', 'empresa_id', 'banco_id', unique=True),
        Index('idx_saldo_data', 'data'),
    )

    def __repr__(self) -> str:
        return f"<SaldoDiario(data={self.data}, empresa_id={self.empresa_id}, banco_id={self.banco_id}, saldo={self.saldo})>"


class SaldoDiarioConsolidado(Base):
    __tablename__ = "saldos_diarios_consolidados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    saldo_total: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saldo_npd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saldo_compre: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    saldo_cs: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    origem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="EXCEL")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<SaldoDiarioConsolidado(data={self.data}, saldo_total={self.saldo_total})>"
