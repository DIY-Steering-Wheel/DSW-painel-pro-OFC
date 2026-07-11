# API DSW Painel Open

Esta documentacao cobre os dois canais expostos pelo app:

- servidor web HTTP
- servidor UDP de resposta em JSON

O app usa a mesma base de estado para os dois transportes. O servidor web serve o template HTML ativo na raiz `/` e expone as rotas `/api/*`. O servidor UDP responde com um snapshot JSON quando algum cliente envia um pacote para a porta configurada.

## Como o app usa internamente

- A interface principal do PyWebView usa `window.pywebview.api.*` para falar com o backend Python.
- O template HTML do Web Server consome `GET /api/state`.
- O servidor UDP nao faz stream continuo sozinho.
  O cliente envia um pacote e recebe o estado atual como resposta.

## HTTP

Host e porta sao definidos na aba `Web Server`.

Exemplo local:

```text
http://127.0.0.1:8080
```

Exemplo na rede:

```text
http://192.168.0.50:8080
```

### `GET /`

Retorna o `index.html` do template ativo.

Uso:

```bash
curl http://127.0.0.1:8080/
```

### `GET /api/health`

Resposta minima de saude do servico.

Exemplo:

```json
{
  "ok": true,
  "service": "dsw-painel-open",
  "time": 1783780000.12
}
```

### `GET /api/state`

Estado atual usado pelos templates HTML.

Uso:

```bash
curl http://127.0.0.1:8080/api/state
```

Campos principais:

- `selected_game`
- `is_collecting`
- `status_text`
- `telemetry_rows`
- `games`
- `device_status`
- `panel_config`
- `motion_config`
- `motion_preview`
- `web_server`

Exemplo resumido:

```json
{
  "selected_game": "BeamNG Drive",
  "is_collecting": true,
  "status_text": "Coletando telemetria",
  "telemetry_rows": [
    { "key": "engine_rpm", "label": "RPM", "value": 3120 },
    { "key": "speed", "label": "Velocidade", "value": 124 }
  ]
}
```

### `GET /api/all`

Retorna o estado completo com metadados e capacidades.

Estrutura:

- `ok`
- `meta`
- `capabilities`
- `state`

### `GET /api/telemetry`

Retorna apenas a parte de telemetria.

Uso:

```bash
curl http://127.0.0.1:8080/api/telemetry
```

### `GET /api/panel-values`

Retorna os valores ja ordenados para envio ao painel serial.

Exemplo:

```json
{
  "ordered_values": [124, 3120, 3, 92, 0, 1],
  "configured_order": ["speed", "engine_rpm", "current_gear", "water_temperature"]
}
```

### `GET /api/motion-preview`

Preview bruto e normalizado do motion.

Exemplo:

```json
{
  "raw": { "x": 0.12, "y": -0.08, "z": 0.54 },
  "normalized": { "x": 12.0, "y": -8.0, "z": 54.0 }
}
```

### `GET /api/games`

Lista de jogos e dados do instalador.

### `GET /api/devices`

Status serial do painel e do motion.

Estados comuns:

- `ready`
- `sending`
- `waiting`
- `disabled`
- `not_configured`
- `port_missing`
- `error`

### `GET /api/config`

Configuracoes atuais do app:

- `basic_settings`
- `panel_config`
- `motion_config`
- `web_server`
- `available_ports`

### `GET /api/capabilities`

Descreve o que a API e o UDP expõem.

### `GET /api/web-server`

Estado atual dos servidores HTTP e UDP, template ativo e QR Code do servidor web.

## UDP

O servidor UDP escuta no host e porta configurados na aba `Web Server`.

Fluxo:

1. o cliente envia qualquer pacote UDP
2. o app responde com JSON do estado atual

Exemplo de requisicao:

```text
ping
```

Exemplo de resposta:

```json
{
  "ok": true,
  "meta": {
    "service": "dsw-painel-open",
    "generated_at": 1783780000.12,
    "transport": "udp"
  },
  "games": [],
  "devices": {},
  "panel_preview": {},
  "motion_preview": {},
  "state": {},
  "web_server": {}
}
```

### Exemplo Python UDP

```python
import json
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(2)
sock.sendto(b"ping", ("127.0.0.1", 28000))
payload, _ = sock.recvfrom(65535)
data = json.loads(payload.decode("utf-8"))
print(data["meta"]["service"])
print(data["state"]["selected_game"])
```

### Exemplo Node.js UDP

```js
const dgram = require("dgram");
const client = dgram.createSocket("udp4");

client.send(Buffer.from("ping"), 28000, "127.0.0.1");
client.on("message", (msg) => {
  const data = JSON.parse(msg.toString("utf8"));
  console.log(data.meta.service);
  console.log(data.state.selected_game);
  client.close();
});
```

## Exemplo do template HTML padrao

O template padrao consulta:

```js
const response = await fetch("/api/state");
const data = await response.json();
```

Depois ele atualiza os campos visuais com `telemetry_rows`, `selected_game`, `status_text` e `is_collecting`.

## Observacoes

- O QR Code do servidor web depende da biblioteca Python `qrcode`.
- O QR de doacao Pix da aba `About` e gerado localmente pelo backend.
- O limite de polling recomendado para templates HTML e `100 FPS`.
- O envio serial do painel e do motion tambem respeita `FPS de envio` configurado no app.
