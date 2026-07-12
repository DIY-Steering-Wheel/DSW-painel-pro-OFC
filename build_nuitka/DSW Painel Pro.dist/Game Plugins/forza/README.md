# Plugin de telemetria Forza

Plugin derivado da estrutura do plugin do Live for Speed, com recepção UDP e decodificação automática dos formatos de telemetria do Forza.

## Jogos e formatos suportados

- Forza Motorsport 7 e Forza Motorsport: `Sled` de 232 bytes e `Dash` de 311 bytes;
- Forza Motorsport com extensão de desgaste/pista: 331 bytes;
- Forza Horizon 4, 5 e 6: pacote Horizon de 324 bytes.

## Configuração no jogo

1. Abra **Configurações > HUD e Jogabilidade**.
2. Ative **Data Out** ou **UDP Race Telemetry**.
3. Use `127.0.0.1` quando o jogo e o DSW estiverem no mesmo computador.
4. Use a porta `9999`.
5. No Forza Motorsport, selecione **Dash / Car Dash**.
6. Entre na pista e comece a dirigir.

Para Xbox ou outro computador, informe no jogo o IP local do PC que executa o DSW e libere a porta UDP 9999 no firewall.

## Configuração opcional pelo host

O `collect(settings)` aceita:

- `telemetry_ip` ou `udp_ip`;
- `telemetry_port` ou `udp_port`;
- `speed_unit`: `KM/H`, `MPH` ou `M/S`;
- `pressure_unit`: `BAR` ou `PSI`;
- `temperature_unit`: `Celsius` ou `Fahrenheit`.

Também podem ser usadas as variáveis de ambiente `FORZA_UDP_IP` e `FORZA_UDP_PORT`.

## Observações

- A porta padrão é `9999`.
- O socket escuta em `0.0.0.0`, permitindo receber tanto do próprio PC quanto de um Xbox na rede local.
- Dados ficam zerados após 2 segundos sem pacote para evitar que o painel permaneça congelado com valores antigos.
- O Forza não fornece temperatura da água, pressão/temperatura do óleo, luzes, ABS ou controle de tração no pacote Data Out; esses campos não são inventados pelo plugin.
