# Plugin de telemetria My Summer Car

Plugin para ler diretamente o WebSocket do mod de telemetria do My Summer Car.

## Requisito

Instale o mod de telemetria:

- https://www.nexusmods.com/games/mysummercar

## Como funciona

- o mod publica JSON via WebSocket em `ws://127.0.0.1:2609`
- o DSW consome esse fluxo diretamente
- a marcha e convertida para o padrao do DSW:
- re = `-1`
- neutro = `0`
- primeira em diante = `1+`

## Observacoes

- o plugin nao depende do EXE do jogo para comecar; ele valida atividade pela telemetria
- se o mod parar de enviar, o painel volta para zero
