import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = field(default_factory=lambda: ROOT / ".data")
    api_key: str = field(default="", repr=False)
    model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    max_steps: int = 5

    @property
    def model_options(self):
        # These are configured choices, not a claim of account-level access.
        return tuple(dict.fromkeys((self.model, "gpt-4.1-mini", "gpt-4.1", "gpt-4.1-nano")))

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT / ".env", override=False)
        return cls(
            data_dir=Path(os.getenv("ATLAS_DATA_DIR", str(ROOT / ".data"))),
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )
