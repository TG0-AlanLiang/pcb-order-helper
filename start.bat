@echo off
title PCB Order Helper
cd /d "%~dp0"
set PCB_LOCAL_DEV=1
streamlit run app.py --server.port 8501
pause
