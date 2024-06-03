@echo off
call .\env\Scripts\activate
uvicorn main:app --reload

