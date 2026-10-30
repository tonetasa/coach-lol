# Quíron

Coach por voz para League of Legends, feito para ajudar a subir de elo **dentro das regras da Riot**.

> Quíron não é endossado pela Riot Games. League of Legends é marca registrada da Riot Games, Inc.

## Instalar

Baixe o `Quiron-Setup-<versão>.exe` mais recente em [Releases](../../releases) e execute.
Instala só para o seu usuário (sem administrador) e aparece em *Configurações → Aplicativos*.
O app avisa quando sai versão nova e se atualiza com um clique.

## O que ele faz

Interface com quatro telas (Coach, Builds, Relatório e Configurações) no visual "hextech": status da partida, teia de desempenho (farm, visão, lutas, abates e sobrevivência), dica do dia, builds com a página de runas e avisos ao vivo. Ela usa o WebView2 do Windows; sem ele, o app abre na interface clássica (também dá para forçar com `Quiron.exe --interface-classica`).

Na primeira vez, o Quíron pergunta seu Riot ID, elo, funções e campeões (pool). Tudo é ajustado a partir disso e pode ser mudado em *Configurações → Perfil*.

- **Cliente do LoL:** aceita a fila sozinho e importa a página de runas e o conjunto de itens do campeão escolhido.
- **Draft:** seu histórico na função, na sua vez, a melhor escolha para o draft entre todos os campeões da função (força no patch pela tier list Esmeralda+, o que falta no seu time e a resposta ao time inimigo) e a melhor do seu pool, com os motivos e, quando o draft fecha, os pontos positivos e de atenção do seu time.
- **Início da partida:** build, opções de itens contra a composição inimiga, plano de jogo (fase forte, iniciação, ameaças, sua rota) e, para o caçador, a rota inicial da selva.
- **Durante a partida** (opcional): diferença de ouro dos times, ouro para o próximo item, CS/min, caçador inimigo visto em abates/objetivos, recompensas.
- **Fim da partida:** resumo falado, alerta de sequência de derrotas e de jogo de madrugada.
- **Relatório:** evolução de participação em abates, mortes antes dos 14 min, por campeão e por horário.
- **Comandos de voz** (offline), sempre com a palavra de chamada antes ("Quíron", trocável em Configurações → Voz):
  - "itens": o que comprar agora (próximo item da build ou, se um inimigo estiver forte, o item de situação contra ele), pelo ouro que você tem
  - "repete os itens": a build completa e os ajustes contra o time inimigo
  - "placar": abates, torres, dragões e diferença de ouro em itens
  - "farm": seu CS e CS por minuto, comparado à meta da função
  - "ameaça": o inimigo mais forte agora (abates, nível, ouro em itens)
  - "rota": você contra o seu oponente direto (nível, itens, CS, abates)
  - "plano": repete o plano do início da partida
  - "repete": repete o último aviso
  - "menos": só os avisos importantes ("volta" traz todos de novo)
  - "mais alto" / "mais baixo": volume da voz
  - "silêncio", "volta", "anota"
- **Objetivos neutros**: avisa 1 minuto antes de dragão, vastilarvas, arauto e barão nascerem, pelos tempos padrão e pelos abates anunciados no jogo.
- **Voz à escolha**: qualquer voz do Windows instalada, em três velocidades.
- **Perfil pelo cliente**: busca o Riot ID, preenche o elo e sugere funções e campeões pelas últimas partidas.
- **Builds para qualquer campeão:** os campeões em `builds.json` têm build pesquisada a cada patch; os demais recebem uma build genérica pela classe (mago, atirador, tanque...), com versão própria para a selva. Campeões fora da função em que costumam ser jogados (lista em `funcoes_comuns.py`) aparecem com aviso: a build é uma estimativa. No app, *Pedir build pesquisada* abre um pedido aqui no GitHub, e a atualização semanal inclui o campeão.
- **Builds editáveis** no app; suas edições ficam só no seu PC e têm prioridade.

## Som e microfone

Os comandos de voz abrem o microfone só durante a partida. Com fone Bluetooth, microfone aberto faz o Windows trocar o fone para o modo "telefone" (som mais abafado); em *Configurações → Voz* dá para escolher outro microfone.

## Regras

O Quíron usa apenas a [Live Client Data API](https://developer.riotgames.com/docs/lol#game-client-api) oficial (só roda no seu PC) e mostra só informação que já está na sua tela.
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

1. Mude `VERSAO` em `versao.py` (ex.: `1.0.1`), faça commit e push na `main`.
2. O GitHub Actions monta o instalador no Windows e publica a Release `v1.0.1`.
3. Quem tem o app instalado recebe o aviso "Versão 1.0.1 disponível".

### Builds

`builds.json` é atualizado a cada patch. O app baixa esse arquivo; edições feitas no app ficam só no seu PC e têm prioridade.
