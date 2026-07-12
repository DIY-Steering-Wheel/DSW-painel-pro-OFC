# Plugin de telemetria My Summer Car

Plugin para ler diretamente o WebSocket do mod de telemetria do My Summer Car.

## Requisito

Antes de tudo, instale o `MSC Loader`, porque o jogo precisa dele para carregar mods em DLL.

## Como funciona

- o DSW copia `VehicleTelemetry.dll` para a pasta `Mods` do jogo
- o DSW copia `WebSocketSharp.dll` para a pasta `Mods/References` do jogo
- o mod publica JSON via WebSocket em `ws://127.0.0.1:2609`
- o DSW consome esse fluxo diretamente
- a marcha e convertida para o padrao do DSW:
- re = `-1`
- neutro = `0`
- primeira em diante = `1+`

## Observacoes

- a instalacao correta e: MSC Loader primeiro, depois copiar `VehicleTelemetry.dll` para `Mods` e `WebSocketSharp.dll` para `Mods/References`
- o plugin nao depende do EXE do jogo para comecar; ele valida atividade pela telemetria
- se o mod parar de enviar, o painel volta para zero
