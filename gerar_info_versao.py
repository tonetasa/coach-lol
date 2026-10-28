"""Gera version_info.txt (propriedades do .exe) a partir de versao.py.

Usado pelo criar_instalador.bat; não precisa rodar à mão.
"""
from datetime import date

from versao import AUTOR, AVISO, DESCRICAO, NOME, VERSAO

partes = [int(p) for p in VERSAO.split(".")] + [0] * 4
v4 = tuple(partes[:4])
txt = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(filevers={v4}, prodvers={v4}, mask=0x3f, flags=0x0,
                    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041604b0', [
      StringStruct('CompanyName', {AUTOR!r}),
      StringStruct('FileDescription', {NOME!r}),
      StringStruct('FileVersion', {VERSAO!r}),
      StringStruct('InternalName', 'CoachLoL'),
      StringStruct('LegalCopyright', '© {date.today().year} {AUTOR}'),
      StringStruct('OriginalFilename', 'CoachLoL.exe'),
      StringStruct('ProductName', {NOME!r}),
      StringStruct('ProductVersion', {VERSAO!r}),
      StringStruct('Comments', {(DESCRICAO + '. ' + AVISO)!r})])]),
    VarFileInfo([VarStruct('Translation', [0x0416, 1200])])
  ]
)
"""
with open("version_info.txt", "w", encoding="utf-8") as f:
    f.write(txt)
print(VERSAO)
