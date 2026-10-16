from pathlib import Path

class Settings:
    DATA_DIR: Path = Path("c:/dev/FLUXO DE CAIXA/data")
    DATABASE_URL: str = f"sqlite:///{DATA_DIR}/finance_app.db"
    
    def ensure_dirs(self):
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
