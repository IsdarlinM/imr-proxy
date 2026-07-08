@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ASSUME_YES=0"
set "USER_PYTHON="
set "PYTHON_INSTALLER_VERSION=3.11.9"
set "PYTHON_INSTALLER_URL=https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
set "PYTHON_CMD="
set "PYTHON_ARGS="

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="/Y" (
    set "ASSUME_YES=1"
    shift
    goto parse_args
)
if /I "%~1"=="--yes" (
    set "ASSUME_YES=1"
    shift
    goto parse_args
)
if /I "%~1"=="/ASSUMEYES" (
    set "ASSUME_YES=1"
    shift
    goto parse_args
)
if /I "%~1"=="/PYTHON" (
    set "USER_PYTHON=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="/PYTHONURL" (
    set "PYTHON_INSTALLER_URL=%~2"
    shift
    shift
    goto parse_args
)
if /I "%~1"=="/PYTHONVERSION" (
    set "PYTHON_INSTALLER_VERSION=%~2"
    shift
    shift
    goto parse_args
)
for /F "tokens=1,* delims==" %%A in ("%~1") do (
    if /I "%%~A"=="/PYTHON" set "USER_PYTHON=%%~B"
    if /I "%%~A"=="/PYTHONURL" set "PYTHON_INSTALLER_URL=%%~B"
    if /I "%%~A"=="/PYTHONVERSION" set "PYTHON_INSTALLER_VERSION=%%~B"
)
shift
goto parse_args

:args_done
set "SCRIPT_DIR=%~dp0"
pushd "%SCRIPT_DIR%\.." >nul 2>&1
if errorlevel 1 (
    echo [!] Could not resolve project root from %SCRIPT_DIR%\..
    exit /b 1
)
set "PROJECT_ROOT=%CD%"
popd >nul 2>&1
set "VENV_DIR=%PROJECT_ROOT%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "COMMAND_PATH=%VENV_DIR%\Scripts\imr-proxy.exe"

call :info "Installing imr-proxy"
call :info "Project root: %PROJECT_ROOT%"

if not exist "%PROJECT_ROOT%\pyproject.toml" (
    echo [!] pyproject.toml was not found at "%PROJECT_ROOT%".
    echo [!] Keep the scripts directory inside the imr-proxy project root.
    exit /b 1
)

if exist "%SCRIPT_DIR%\.venv" (
    echo [!] Warning: a previous virtual environment exists inside scripts\.venv.
    echo [!] It is not used anymore. You can delete it after this install succeeds:
    echo [!] %SCRIPT_DIR%\.venv
)

call :find_python
if errorlevel 1 (
    call :install_python311
    if errorlevel 1 exit /b 1
    call :find_python
)

if not defined PYTHON_CMD (
    echo [!] Python 3.11+ still was not found.
    echo [!] Open a new Command Prompt or run: scripts\install_windows.cmd /PYTHON "C:\Path\To\Python311\python.exe"
    exit /b 1
)

for /f "delims=" %%V in ('"%PYTHON_CMD%" %PYTHON_ARGS% --version 2^>^&1') do set "PYTHON_VERSION_TEXT=%%V"
call :info "Using Python: %PYTHON_VERSION_TEXT%"

call :run_python -m venv "%VENV_DIR%"
if errorlevel 1 exit /b 1

"%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 (
    echo [!] Command failed with exit code %ERRORLEVEL%: "%VENV_PYTHON%" -m pip install --upgrade pip setuptools wheel
    exit /b %ERRORLEVEL%
)

pushd "%PROJECT_ROOT%" >nul 2>&1
"%VENV_PYTHON%" -m pip install -e .
set "PIP_INSTALL_EXIT=%ERRORLEVEL%"
popd >nul 2>&1
if not "%PIP_INSTALL_EXIT%"=="0" (
    echo [!] Command failed with exit code %PIP_INSTALL_EXIT%: "%VENV_PYTHON%" -m pip install -e .
    exit /b %PIP_INSTALL_EXIT%
)

call :create_launcher
if errorlevel 1 exit /b 1

call :info "Installed successfully."
echo.
echo Next steps:
echo   cd "%PROJECT_ROOT%"
echo   .venv\Scripts\activate.bat
echo   imr-proxy --version
echo.
echo Direct command without activation:
echo   "%COMMAND_PATH%" --version
echo.
echo Global launcher created at:
echo   "%USERPROFILE%\.imr-proxy\bin\imr-proxy.cmd"
echo.
echo If this is the first time that folder was added to PATH, open a new CMD window before running:
echo   imr-proxy --version
exit /b 0

:info
echo [*] %~1
exit /b 0

:confirm
if "%ASSUME_YES%"=="1" exit /b 0
if /I "%IMR_PROXY_ASSUME_YES%"=="1" exit /b 0
set "REPLY="
set /p "REPLY=%~1 [y/N] "
if /I "%REPLY%"=="y" exit /b 0
if /I "%REPLY%"=="yes" exit /b 0
exit /b 1

:test_python
set "TEST_CMD=%~1"
set "TEST_ARGS=%~2"
"%TEST_CMD%" %TEST_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "PYTHON_CMD=%TEST_CMD%"
set "PYTHON_ARGS=%TEST_ARGS%"
exit /b 0

:find_python
set "PYTHON_CMD="
set "PYTHON_ARGS="
if defined USER_PYTHON (
    call :test_python "%USER_PYTHON%" ""
    if not errorlevel 1 exit /b 0
    echo [!] The Python path supplied with /PYTHON is not Python 3.11+: "%USER_PYTHON%"
    exit /b 1
)

call :test_python "py" "-3.11"
if not errorlevel 1 exit /b 0
call :test_python "python" ""
if not errorlevel 1 exit /b 0
call :test_python "python3" ""
if not errorlevel 1 exit /b 0
if defined LOCALAPPDATA (
    call :test_python "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" ""
    if not errorlevel 1 exit /b 0
)
exit /b 1

:install_python311
call :confirm "Python 3.11+ was not found. Do you want to download and install Python %PYTHON_INSTALLER_VERSION% from python.org now?"
if errorlevel 1 (
    echo [!] Python 3.11+ is required. Install it manually or rerun with /Y.
    exit /b 1
)

set "TEMP_DIR=%TEMP%\imr-proxy-python"
if not exist "%TEMP_DIR%" mkdir "%TEMP_DIR%"
if errorlevel 1 exit /b 1
set "INSTALLER_PATH=%TEMP_DIR%\python-%PYTHON_INSTALLER_VERSION%-amd64.exe"

call :info "Downloading %PYTHON_INSTALLER_URL%"
where curl.exe >nul 2>&1
if not errorlevel 1 (
    curl.exe -L --fail -o "%INSTALLER_PATH%" "%PYTHON_INSTALLER_URL%"
    if errorlevel 1 (
        echo [!] curl.exe download failed.
        exit /b 1
    )
) else (
    call :info "curl.exe was not found. Trying PowerShell only for file download, not for script execution."
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_INSTALLER_URL%' -OutFile '%INSTALLER_PATH%' -UseBasicParsing"
    if errorlevel 1 (
        echo [!] Download failed.
        exit /b 1
    )
)

call :info "Starting Python installer for current user."
start /wait "" "%INSTALLER_PATH%" /passive InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0
if errorlevel 1 (
    echo [!] Python installer failed with exit code %ERRORLEVEL%.
    exit /b 1
)
call :info "Python installer finished. If Python is not detected immediately, open a new CMD window."
exit /b 0

:run_python
"%PYTHON_CMD%" %PYTHON_ARGS% %*
if errorlevel 1 (
    echo [!] Python command failed with exit code %ERRORLEVEL%.
    exit /b %ERRORLEVEL%
)
exit /b 0

:create_launcher
set "USER_BIN=%USERPROFILE%\.imr-proxy\bin"
if not exist "%USER_BIN%" mkdir "%USER_BIN%"
if errorlevel 1 exit /b 1

(
    echo @echo off
    echo "%COMMAND_PATH%" %%*
) > "%USER_BIN%\imr-proxy.cmd"
if errorlevel 1 (
    echo [!] Could not create launcher at "%USER_BIN%\imr-proxy.cmd".
    exit /b 1
)

set "PATH_CHECK=;%PATH%;"
echo(!PATH_CHECK! | find /I ";%USER_BIN%;" >nul 2>&1
if not errorlevel 1 exit /b 0

call :confirm "Do you want to add %USER_BIN% to your user PATH so imr-proxy works as a normal command in new CMD windows?"
if errorlevel 1 (
    echo [!] PATH was not changed. You can still use:
    echo [!] "%USER_BIN%\imr-proxy.cmd" --version
    exit /b 0
)

set "USER_PATH="
for /f "skip=2 tokens=1,2,*" %%A in ('reg query HKCU\Environment /v Path 2^>nul') do (
    set "USER_PATH=%%C"
)
if defined USER_PATH (
    echo(!USER_PATH! | find /I "%USER_BIN%" >nul 2>&1
    if not errorlevel 1 (
        call :info "%USER_BIN% is already in the user PATH."
        exit /b 0
    )
    set "NEW_USER_PATH=!USER_PATH!;%USER_BIN%"
) else (
    set "NEW_USER_PATH=%USER_BIN%"
)
reg add HKCU\Environment /v Path /t REG_EXPAND_SZ /d "!NEW_USER_PATH!" /f >nul
if errorlevel 1 (
    echo [!] Could not update user PATH automatically.
    echo [!] Add this folder manually to your user PATH: %USER_BIN%
    exit /b 0
)
set "PATH=%PATH%;%USER_BIN%"
call :info "Added %USER_BIN% to your user PATH. Open a new CMD window to use it globally."
exit /b 0
