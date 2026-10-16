Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\dev\FLUXO DE CAIXA"
WshShell.Run """C:\dev\FLUXO DE CAIXA\venv\Scripts\pythonw.exe"" ""C:\dev\FLUXO DE CAIXA\controle_servicos.py"" iniciar", 0, False
