@echo off
start "MindWay Main Server" cmd /k ".venv\Scripts\activate && uvicorn main:app --reload --port 8000"

