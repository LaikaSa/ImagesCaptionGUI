@echo off
set CUDA_VISIBLE_DEVICES=1
call venv\Scripts\activate
python src/main.py
pause