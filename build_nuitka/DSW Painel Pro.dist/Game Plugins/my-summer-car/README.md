# Plugin de telemetria My Summer Car

Plugin para receber a telemetria do mod de My Summer Car por um servidor WebSocket local aberto pelo proprio DSW.

## Requisito

Antes de tudo, instale o `MSC Loader`, porque o jogo precisa dele para carregar mods em DLL.

## Como funciona

- o DSW copia `VehicleTelemetry.dll` para a pasta `Mods` do jogo
- o DSW copia `WebSocketSharp.dll` para a pasta `Mods/References` do jogo
- o DSW sobe um servidor WebSocket local em `ws://127.0.0.1:2609`
- o mod `VehicleTelemetry.dll` conecta nesse servidor e envia JSON em tempo real
- a marcha e convertida para o padrao do DSW:
- re = `-1`
- neutro = `0`
- primeira em diante = `1+`

## Observacoes

- a instalacao correta e: MSC Loader primeiro, depois copiar `VehicleTelemetry.dll` para `Mods` e `WebSocketSharp.dll` para `Mods/References`
- para conectar no DSW, use `vt_connect` no console do MSC Loader se o mod nao conectar sozinho
- o plugin nao depende do EXE do jogo para comecar; ele valida atividade pela telemetria
- se o mod parar de enviar, o painel volta para zero
