@echo off
setlocal

set "ROOT=%~dp0"
set "SRC=%ROOT%Game Plugins"
set "DST=%ROOT%build_nuitka\DSW Painel Pro.dist\Game Plugins"

if not exist "%SRC%" (
  echo Pasta de origem nao encontrada:
  echo %SRC%
  exit /b 1
)

if not exist "%ROOT%build_nuitka\DSW Painel Pro.dist" (
  echo Build Nuitka nao encontrado.
  echo Compile o app pelo menos uma vez antes de atualizar so os plugins.
  exit /b 1
)

echo Atualizando plugins de jogo em:
echo %DST%
robocopy "%SRC%" "%DST%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
  echo Falha ao atualizar os plugins. Codigo do robocopy: %RC%
  exit /b %RC%
)

echo Plugins atualizados com sucesso.
exit /b 0
