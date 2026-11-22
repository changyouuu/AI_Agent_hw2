<<<<<<< HEAD
# 論文方法工作台

用本機 Ollama 整理英文論文的 What、Why、How，逐項查看英文引文與 PDF 實際頁碼。可以針對方法步驟追問，或從整篇公式索引查看候選算式和 PDF 原圖。

## 從零啟動（Windows）

1. 將 ZIP 解壓到新的資料夾。進入內層的 PaperLens，應可看到 start.ps1、app.py 和 sample.pdf。
2. 在檔案總管的網址列輸入 powershell 並按 Enter。
3. 執行下方指令。第一次會用 Python 3.12 建立專用環境並安裝依賴。如果尚未安裝 Python 3.12，先執行 py install 3.12。

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
~~~

4. 開啟 http://127.0.0.1:8501。保留 PowerShell 視窗。要停止時按 Ctrl+C。
5. 在左側按「開啟範例論文」，再切到「公式與原頁」，可以先看上下標和分式。

## 使用 Ollama 分析

開啟本機 Ollama。若尚無本機模型，可另開 PowerShell 執行 ollama pull qwen3:4b。回到網頁按「重新檢查連線」並選擇模型，再上傳 PDF、按「匯入論文」，最後按「分析研究方法」。本機 Ollama 免填 API 金鑰。預設網址是 http://127.0.0.1:11434。

資料預設保存在新專案的 data 目錄，其中有原始 PDF 與 SQLite 資料庫。請保留此目錄以便下次讀取已匯入的論文、對話和 trace。預設支援 30 MB、50 頁以內的文字型 PDF。

## 公式與出處

「公式與原頁」會建立整篇 PDF 的公式候選索引。可輸入符號、算式片段或可辨識的公式編號。選取候選後，左側顯示擷取文字，右側顯示原始裁切圖，可勾選「顯示整頁」。也可以直接指定頁碼。上下標、分式和公式號碼採版面規則偵測。遇到複雜跨行公式、特殊字型或未偵測到的算式，請以原頁核對。

方法分析使用 PDF Processing、Retrieval、Method Analysis、Evidence Verification 和 Controller。檢索限當篇論文，每次最多 8 片段。模型產生的說明須通過引文原文核對與語意檢查。方法分析的預算為 300 秒及 12 次模型呼叫，追問為 120 秒及 6 次呼叫。

## Podman

包含 Containerfile。Podman 容器與 Windows 上的 Ollama 需要能互相連線，可用 OLLAMA_URL 指定容器可達的 Ollama 位址。請只允許必要的本機或容器網路存取 Ollama。

~~~powershell
podman build -t paperlens .
podman volume create paperlens-data
podman run --rm -p 127.0.0.1:8501:8501 -v paperlens-data:/data paperlens
~~~

## 驗證

安裝 requirements.txt 與 reportlab 後，可執行 python verify_formulas.py 與 python verify_demo.py trace。前者驗證上下標、分式和 PDF 渲染。後者用固定模型回覆測試單欄、雙欄、證據驗證、追問與 SQLite。Ollama 真實模型與 Podman 容器尚未在打包環境驗證。
=======
# AI_Agent_hw2
hw2
>>>>>>> origin/main
