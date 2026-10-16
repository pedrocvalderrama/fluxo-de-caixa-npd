"""Configurações centralizadas do sistema de gestão financeira."""
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Configurações do sistema, carregadas do .env ou com valores padrão."""

    # Aplicação
    APP_NAME: str = "Sistema de Gestão Financeira"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Caminhos — diretório base é a raiz do projeto (pai de finance_app)
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    DATA_DIR: Path = BASE_DIR / "data"
    BACKUP_DIR: Path = BASE_DIR / "data" / "backups"

    # Banco de dados
    DATABASE_URL: str = ""

    # Conexão ERP Sisplan (Firebird 3)
    SISPLAN_HOST: str = "192.168.100.168"
    SISPLAN_PORT: int = 3051
    SISPLAN_DATABASE: str = r"C:\Sisplan\Base\14215F.FDB"
    SISPLAN_USER: str = "SYSDBA"
    SISPLAN_PASSWORD: str = "masterkey"
    SISPLAN_CLIENT_DLL: str = r"C:\dev\auto_sisplan\fbclient_x64.dll"

    # Importação
    SUPPORTED_EXTENSIONS: list[str] = [".xlsx"]
    MAX_PREVIEW_ROWS: int = 100

    # Configurações financeiras
    CURRENCY_SYMBOL: str = "R$"
    CURRENCY_LOCALE: str = "pt_BR"
    DATE_FORMAT: str = "%d/%m/%Y"
    DATE_FORMAT_ISO: str = "%Y-%m-%d"

    # Detecção de anomalias
    IQR_MULTIPLIER: float = 1.5

    # Limiares de saúde financeira
    HEALTH_COVERAGE_GREEN: float = 3.0    # meses
    HEALTH_COVERAGE_YELLOW: float = 1.0   # meses
    HEALTH_TREND_YELLOW: float = -10.0    # % de queda
    HEALTH_CONCENTRATION_YELLOW: float = 50.0   # % top 3 categorias
    HEALTH_CONCENTRATION_RED: float = 70.0      # % top 3 categorias

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def model_post_init(self, __context) -> None:
        """Define DATABASE_URL padrão se não foi configurado via .env."""
        if not self.DATABASE_URL:
            db_path = self.DATA_DIR / "finance.db"
            self.DATABASE_URL = f"sqlite:///{db_path}"

    def ensure_dirs(self) -> None:
        """Garante que os diretórios necessários existam."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
