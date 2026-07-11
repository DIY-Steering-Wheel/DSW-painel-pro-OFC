# Plugin de telemetria Farming Simulator

Plugin para ler o mod Farming Simulator Telemetry via pipe nomeado local.

## Fonte do mod

- https://github.com/Marciel032/FarmingSimulatorTelemetry

## Como funciona

- o mod escreve telemetria no pipe `\\.\pipe\fssimx`
- o DSW consome esse pipe diretamente
- campos textuais, como nome do veiculo, sao ignorados
- o foco fica em campos numericos e booleanos, incluindo implementos

## Implementos

O plugin expoe:

- contagem de implementos
- quantos estao abaixados
- quantos estao selecionados
- quantos estao ligados
- desgaste medio
- slots 1 a 8 para posicao, desgaste e estados
