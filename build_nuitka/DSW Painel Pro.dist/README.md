# DSW Painel Pro OFC

<img width="1184" height="497" alt="image" src="https://github.com/user-attachments/assets/10e207de-0656-4c84-aa68-91873426cdb6" />

Aplicativo desktop em PyWebView para leitura de telemetria de jogos, envio serial para painel e motion, e exposição do estado atual por HTTP e UDP.

## Recursos

- seleção de jogos por plugins
- leitura de telemetria
- envio serial para painel
- envio serial para motion
- Web Server com templates HTML
- servidor UDP com resposta JSON
- importação de plugins e templates

## Estrutura principal

- [main.py](main.py)
  inicia a janela principal
- [app_api.py](app_api.py)
  ponte entre frontend e backend
- [telemetry_bridge.py](telemetry_bridge.py)
  estado central do app
- [serial_services.py](serial_services.py)
  envio serial de painel e motion
- [web_runtime.py](web_runtime.py)
  servidor web, UDP e templates
- [frontend/index.html](frontend/index.html)
  interface principal

## Como executar

```bash
python main.py
```

## Configuração

### Painel

- escolha a porta serial
- defina o modo
- escolha os slots
- ajuste o FPS de envio

### Motion

- escolha a porta serial
- ajuste baudrate
- ajuste o FPS de envio
- configure min, max, fases e offsets

### Web Server

- ligue a chave do servidor web
- configure host e porta
- escolha o template HTML ativo
- gere o QR Code para abrir no celular

### UDP

- ligue a chave do servidor UDP
- configure host e porta
- envie um pacote UDP e receba o JSON de resposta

## Templates HTML

Os templates ficam em [web/templates](web/templates).

Cada template precisa ter pelo menos:

- manifest.json
- index.html

O template padrão fica em [web/templates/simple-dashboard](web/templates/simple-dashboard).

## API

A documentação de HTTP e UDP está em [API.md](API.md).

## About / Ajuda

A aba About / Ajuda usa um HTML separado: [frontend/about_dsw.html](frontend/about_dsw.html).

Ali você pode editar:

- apresentação da DSW
- link do Discord
- links futuros de GitHub, site e documentação
- área de doação por Pix

## Observações de desenvolvimento

- o polling da interface principal continua ativo para manter a telemetria viva
- os modais de configuração não devem mais ser reescritos enquanto você está editando
- o template web padrão pode puxar /api/state em até 100 FPS
