@echo off
cd C:\packing_web_app
CALL .\venv\Scripts\activate
set FLASK_APP=app.py
flask run
pause