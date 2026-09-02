@echo off

REM Pindah ke folder tempat batch file berada
cd /d "%~dp0"

echo ================================================================================
echo Running Data Preparation...
echo ================================================================================
python "_02_script\data_preparation.py"

IF ERRORLEVEL 1 (
  echo.
  echo ERROR: Data preparation failed!
  echo Check the error message above.
  pause
  exit /b 1
)

echo.
echo ================================================================================
echo Generating PDF Report...
echo ================================================================================
python "_02_script\generate_report.py"

IF ERRORLEVEL 1 (
  echo.
  echo ERROR: Generate report failed!
  echo Check the error message above.
  pause
  exit /b 1
)

echo.
echo ================================================================================
echo Done! PDF sudah tersimpan langsung di folder _03_output_pdf\
echo ================================================================================
pause
