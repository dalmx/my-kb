@echo off
cd /d %~dp0
set HF_ENDPOINT=https://hf-mirror.com
py server.py
