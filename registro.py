"""Registro de erros do Quíron (quiron.log na pasta de dados)."""

import logging
import platform
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

log = logging.getLogger("quiron")
ARQ_LOG: Path | None = None


def configurar(pasta: Path, versao: str) -> Path:
    """Liga o log em arquivo (até 3 arquivos de 1 MB) e captura erros não tratados."""
    global ARQ_LOG
    ARQ_LOG = pasta / "quiron.log"
    if not log.handlers:
        h = RotatingFileHandler(ARQ_LOG, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                         "%Y-%m-%d %H:%M:%S"))
        log.addHandler(h)
        log.setLevel(logging.INFO)

    def erro(tipo, valor, tb):
        log.error("Erro não tratado:\n%s", "".join(traceback.format_exception(tipo, valor, tb)))

    sys.excepthook = erro
    threading.excepthook = lambda a: erro(a.exc_type, a.exc_value, a.exc_traceback)
    log.info("Quíron %s iniciado (%s, Python %s)", versao, platform.platform(),
             platform.python_version())
    return ARQ_LOG


def erro(msg: str, exc: BaseException | None = None):
    if exc:
        log.error("%s\n%s", msg, "".join(traceback.format_exception(exc)))
    else:
        log.error(msg)


def diagnostico(versao: str, pasta: Path, linhas: int = 60) -> str:
    """Texto para copiar e mandar ao Claude quando algo der errado."""
    fim = ""
    if ARQ_LOG and ARQ_LOG.exists():
        fim = "\n".join(ARQ_LOG.read_text(encoding="utf-8", errors="replace")
                        .splitlines()[-linhas:])
    return (f"Quíron {versao}\n"
            f"Windows: {platform.platform()}\n"
            f"Python: {platform.python_version()} "
            f"({'executável' if getattr(sys, 'frozen', False) else 'script'})\n"
            f"Pasta de dados: {pasta}\n\n"
            f"Últimas linhas do log:\n{fim or '(vazio)'}\n")
