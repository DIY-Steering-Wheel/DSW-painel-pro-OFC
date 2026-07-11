# Design Guide

Este arquivo descreve o design visual e estrutural do `DSW Painel Pro` para reaproveitar a mesma linguagem em outro app.

## Objetivo visual

O app usa uma identidade de painel técnico para simuladores:

- aparência escura
- contraste alto
- sensação de cockpit / software embarcado
- foco em leitura rápida
- destaque forte para ações principais

O resultado combina:

- fundo com gradientes escuros
- cartões com vidro fosco leve
- bordas suaves com brilho azul
- ações críticas em vermelho
- estados ativos em azul e verde

## Stack visual

- HTML estático em `frontend/index.html`
- CSS customizado em `frontend/style.css`
- Bootstrap 5.3 como base utilitária
- Bootstrap Icons para ícones
- JavaScript puro em `frontend/app.js`
- PyWebView como shell desktop

## Paleta principal

As variáveis ficam em `:root` dentro de `frontend/style.css`.

Cores principais:

- `--bg-deep`: fundo mais escuro
- `--bg-mid`: fundo intermediário
- `--panel`: cartão translúcido
- `--panel-strong`: cartão mais denso
- `--text`: texto principal
- `--muted`: texto secundário
- `--accent`: azul principal
- `--danger`: vermelho de ação

Direção da paleta:

- azul = configuração, destaque, estado ativo
- vermelho = ação principal, instalar, salvar, excluir crítico
- verde = transmissão/atividade em tempo real

## Tipografia

Fonte atual:

- `"Segoe UI", Tahoma, sans-serif`

Regras:

- títulos curtos e fortes
- labels pequenas com caixa alta em `.eyebrow`
- texto secundário sempre com `--muted`
- números e telemetria em blocos com espaçamento compacto

## Estrutura da tela principal

O layout usa duas colunas:

1. barra lateral esquerda com biblioteca de jogos
2. área principal com jogo ativo, telemetria e ações

Partes:

- `aside.game-sidebar`
- `section.main-stage`
- `header.game-header`
- `main.telemetry-panel`
- `footer.footer-bar`

### Sidebar

Função:

- listar jogos/plugins
- mostrar qual está selecionado
- sinalizar se está aberto/fechado e instalado/não instalado

Estilo:

- cartões pequenos
- hover com leve elevação
- item selecionado com brilho azul

### Header

Função:

- logo do jogo
- nome do jogo
- estado atual
- botão principal de ação
- toggle de início automático

Estilo:

- leitura imediata
- botão principal grande
- bloco visual limpo para o jogo atual

### Telemetria

Função:

- mostrar linhas de dados em tempo real

Estilo:

- lista vertical
- cada linha é um cartão curto
- label à esquerda, valor à direita

### Footer

Função:

- abrir os módulos do app

Botões:

- configurações básicas
- painel
- motion
- instalador
- web server

Estilo:

- grid de 5 ações
- botão ativo pode ganhar estado visual de transmissão

## Modais

O app usa modais como superfícies principais de configuração.

Padrão:

- fundo escuro translúcido
- cartão central com bordas arredondadas
- toolbar superior fixa
- conteúdo rolável

Classes importantes:

- `.modal-shell`
- `.modal-card`
- `.modal-card-lg`
- `.modal-card-xl`
- `.modal-toolbar`
- `.modal-body-scroll`

Todos os modais seguem a mesma estrutura para facilitar cópia entre projetos.

## Linguagem de componentes

### Cartões

Usados em:

- configurações
- templates
- plugins
- releases
- status serial
- tutoriais

Padrão visual:

- borda sutil
- fundo translúcido
- cantos arredondados
- sombra interna leve

### Chips

Usados para:

- status
- modo ativo
- preview resumido

Padrão:

- formato cápsula
- fundo azul translúcido
- texto claro

### Botões

Tipos:

- `.btn-primary`: navegação/configuração
- `.btn-danger`: ação principal
- `.btn-outline-light`: ação secundária

Regra de uso:

- salvar, importar e instalar usam vermelho
- abrir, navegar, buscar e fechar usam outline

## Catálogos visuais

### Templates HTML

Cada template é um card com:

- preview
- nome
- descrição
- autor
- versão
- indicador mobile
- ações de selecionar/excluir

Estado selecionado:

- classe `.template-card.is-active`

### Plugins

Cada plugin aparece em linha com:

- nome
- origem
- necessidade de instalador
- estado de seleção

Estado selecionado:

- classe `.plugin-item.is-selected`

### GitHub Releases

O modal de releases usa:

- cartão por release
- sublista de assets
- ações rápidas por asset

Boa prática para copiar:

- manter release como bloco pai
- manter asset como bloco filho clicável
- usar botão principal só para `baixar e importar`

## Motion preview

O preview do motion usa `canvas` para desenhar 3 curvas:

- X verde
- Y azul
- Z rosa/vermelho

Objetivo:

- leitura rápida do comportamento sem abrir software externo

## Responsividade

Mesmo sendo app desktop, o CSS já derruba várias grades para coluna única em telas menores.

Breakpoint atual:

- `@media (max-width: 860px)`

Grades que colapsam:

- settings
- motion
- fallbacks
- installs
- formulários de servidor
- catálogo de templates
- slots do painel

## Experiência de uso

O design prioriza:

- baixo atrito
- confirmação visual imediata
- mudança rápida entre jogos
- configuração modular
- leitura contínua de telemetria

Padrões importantes de UX:

- seleção sempre precisa ficar evidente
- importações devem refletir na lista imediatamente
- ações destrutivas pedem confirmação
- status ativo deve ser visível sem abrir mais telas

## Como replicar em outro app

Para copiar esse design para outra aplicação:

1. Reaproveite a estrutura de `frontend/index.html`.
2. Copie os tokens de cor e os componentes base de `frontend/style.css`.
3. Preserve o padrão `sidebar + stage + footer`.
4. Reutilize o sistema de modais com toolbar fixa.
5. Use o mesmo padrão de cartões translúcidos para listas técnicas.
6. Separe os estados visuais em `selecionado`, `ativo`, `erro`, `protegido` e `desligado`.

## Arquivos de referência

- [frontend/index.html](/C:/Users/Valdemir/Desktop/DSW%20PAINEL%20PRO/frontend/index.html)
- [frontend/style.css](/C:/Users/Valdemir/Desktop/DSW%20PAINEL%20PRO/frontend/style.css)
- [frontend/app.js](/C:/Users/Valdemir/Desktop/DSW%20PAINEL%20PRO/frontend/app.js)
- [main.py](/C:/Users/Valdemir/Desktop/DSW%20PAINEL%20PRO/main.py)

## Resumo rápido

Se for recriar do zero, pense no design assim:

- cockpit escuro
- dados em cartões
- azul para estado/configuração
- vermelho para ação principal
- modais como centros de trabalho
- sidebar para contexto
- stage central para operação em tempo real
