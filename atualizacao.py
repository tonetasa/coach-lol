"""Atualização automática do Coach LoL pelo GitHub Releases.

Para lançar uma versão: mude VERSAO em versao.py, gere o instalador e crie
uma release no GitHub com a tag v<versão> (ex.: v1.0.1) e o arquivo
CoachLoL-Setup-<versão>.exe anexado. O app avisa e instala com um clique.
"""

import subprocess
import sys
import tempfile
from pathlib import Path

import requests

REPO = "tonetasa/coach-lol"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGINA = f"https://github.com/{REPO}"


def _tupla(versao: str) -> tuple:
    try:
        return tuple(int(x) for x in versao.lstrip("vV").split("."))
    except ValueError:
        return (0,)


def verificar(versao_atual: str) -> dict | None:
    """Retorna {versao, url, notas, pagina} se houver versão mais nova; senão None."""
    r = requests.get(API, timeout=6, headers={"Accept": "application/vnd.github+json"})
    if r.status_code == 404:
        return None  # ainda não há releases
    r.raise_for_status()
    rel = r.json()
    nova = rel.get("tag_name", "")
    if _tupla(nova) <= _tupla(versao_atual):
        return None
    instalador = next((a for a in rel.get("assets", [])
                       if a.get("name", "").lower().endswith(".exe")), None)
    return {"versao": nova.lstrip("vV"),
            "url": instalador["browser_download_url"] if instalador else None,
            "notas": (rel.get("body") or "").strip(),
            "pagina": rel.get("html_url", PAGINA)}


def baixar(info: dict, progresso=None) -> Path:
    """Baixa o instalador para a pasta temporária. progresso(0..1) opcional."""
    destino = Path(tempfile.gettempdir()) / f"CoachLoL-Setup-{info['versao']}.exe"
    with requests.get(info["url"], stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0)) or None
        feito = 0
        with open(destino, "wb") as f:
            for bloco in r.iter_content(256 * 1024):
                f.write(bloco)
                feito += len(bloco)
                if progresso and total:
                    progresso(feito / total)
    return destino


def instalar(instalador: Path):
    """Roda o instalador em modo silencioso; ele fecha o app e o reabre no fim."""
    if sys.platform != "win32":
        raise RuntimeError("A atualização automática só funciona no Windows.")
    subprocess.Popen([str(instalador), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                     close_fds=True)
