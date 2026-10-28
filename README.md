# Coach LoL

Coach por voz para League of Legends, feito para ajudar a subir de elo **dentro das regras da Riot**.

> Coach LoL não é endossado pela Riot Games. League of Legends é marca registrada da Riot Games, Inc.

## Instalar

Baixe o `CoachLoL-Setup-<versão>.exe` mais recente em [Releases](../../releases) e execute.
Instala só para o seu usuário (sem administrador) e aparece em *Configurações → Aplicativos*.
O app avisa quando sai versão nova e se atualiza com um clique.

## O que ele faz

- **Seleção de campeões:** seu histórico na função e notas sobre os campeões inimigos.
- **Início da partida:** build do seu campeão e opções de itens contra a composição inimiga.
- **Durante a partida** (opcional): ouro para o próximo item, CS/min, caçador inimigo visto em abates/objetivos, recompensas.
- **Fim da partida:** resumo falado, alerta de sequência de derrotas e de jogo de madrugada.
- **Relatório:** evolução de participação em abates, mortes antes dos 14 min, por campeão e por horário.
- **Comandos de voz** (offline): "coach itens", "coach silêncio", "coach volta", "coach anota".
- **Builds editáveis** no app; as builds do patch novo são publicadas em `builds.json` e baixadas automaticamente.

## Regras

O coach usa apenas a [Live Client Data API](https://developer.riotgames.com/docs/lol#game-client-api) oficial (só roda no seu PC) e mostra só informação que já está na sua tela.
Não lê memória do jogo, não lê a tela, não rastreia recargas de feitiços ou ultimates inimigos e só **informa** — a decisão é sua.
Avisos durante a partida podem ser desligados (modo "antes e depois").

## Desenvolvimento

```
python -m pip install -r requirements.txt
pythonw coach_app.py          # app
python coach_lol.py           # só o coach, no terminal
python relatorio_lol.py       # relatório HTML
criar_instalador.bat          # gera o instalador localmente (Windows)
```

### Lançar uma versão

1. Mude `VERSAO` em `versao.py` (ex.: `1.0.1`) e faça commit.
2. Crie e envie a tag: `git tag v1.0.1 && git push origin v1.0.1`.
3. O GitHub Actions monta o instalador e publica a Release.

### Builds

`builds.json` é atualizado a cada patch. O app baixa esse arquivo; edições feitas no app ficam só no seu PC e têm prioridade.
