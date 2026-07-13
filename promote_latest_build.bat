@echo off
setlocal

set "ROOT=%~dp0"
set "SRC=%ROOT%build_nuitka\main.dist"
set "DST=%ROOT%build_nuitka\DSW Painel Pro.dist"

if not exist "%SRC%" (
  echo Build novo nao encontrado em:
  echo %SRC%
  exit /b 1
)

echo Promovendo build mais recente...
robocopy "%SRC%" "%DST%" /MIR /R:1 /W:1 /NFL /NDL /NJH /NJS /NP
set "RC=%ERRORLEVEL%"

if %RC% GEQ 8 (
  echo Falha ao promover o build. Feche o app compilado e tente novamente.
  exit /b %RC%
)

echo Build promovido com sucesso para:
echo %DST%
exit /b 0
