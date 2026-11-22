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

## Podman（Windows / WSL 2）

從包含 `Containerfile` 的資料夾執行。先確認 Podman machine 正在執行。`paperlens-models` 保存 Ollama 模型，`paperlens-data` 保存 PDF、結果、對話與執行紀錄。以下命令適用於尚未建立同名容器的環境。

~~~powershell
podman machine list
podman build -t paperlens .
podman network create paperlens-net
podman volume create paperlens-models
podman volume create paperlens-data
podman run -d --name paperlens-ollama --network paperlens-net -v paperlens-models:/root/.ollama docker.io/ollama/ollama:latest
podman exec paperlens-ollama ollama pull qwen3:4b
podman run -d --name paperlens --network paperlens-net -p 127.0.0.1:8502:8501 -v paperlens-data:/data -e OLLAMA_URL=http://paperlens-ollama:11434 localhost/paperlens:latest
~~~

開啟 [容器版 PaperLens](http://127.0.0.1:8502)。Ollama 只在容器網路提供服務。首次拉取模型需網路連線。可用 `podman exec paperlens-ollama ollama list` 確認模型已下載。停止容器用 `podman stop paperlens paperlens-ollama`，下次先啟動 Podman machine，再執行 `podman start paperlens-ollama paperlens`。

實測同樣使用雙容器網路。Ollama 容器以唯讀掛載使用 Windows 已下載的模型，所以上述從空環境起步的命令改用模型資料卷，方便其他電腦獨立下載。

## Agent 與工具

Controller 根據任務預算及證據檢查結果選擇繼續、重搜或停止。採用狀態式工作流程，讓每一步可重現並確認來源。Method Analysis 用 Ollama 產生說明與選擇來源編號。

| 工具 | 目的 | 輸入 | 輸出 | 錯誤處理 |
| --- | --- | --- | --- | --- |
| PDF Processing | 解析論文 | PDF 位元組、時間預算 | 片段、實際頁碼、章節、提示 | 逾頁數或大小、無可用文字、加密與解析失敗時拒絕 |
| Retrieval | 查詢當篇論文 | 查詢詞、可用片段範圍 | 最多 8 個片段及識別碼 | 無合適來源時保留不足；經 Controller 控制擴大範圍 |
| Evidence Verification | 確認原文可支持說明 | 候選說明、來源 ID、已檢索片段 | 通過的說明、英文原文及頁碼 | 來源不存在或語意未獲支持時略過該欄 |
| SQLite History | 保存及查詢任務資料 | PDF 識別碼、結果、對話、trace | 指定論文的歷史資料 | 以論文識別碼區隔，存取失敗由操作層或系統錯誤訊息呈現 |

## 驗證

### 實際 Podman 流程

以 GraphSAGE 測試。使用者匯入 PDF 並要求分析 → Controller 讀取解析結果、定位方法章節 → Retrieval 取得同篇片段 → Method Analysis 產生候選 What／Why／How → Evidence Verification 核對來源與語意 → Controller 視缺漏重搜或停止 → 輸出附引文和頁碼的方法說明。

使用 `qwen3:4b` 在 Podman 以 CPU 執行。分析在約 244 秒內呼叫 3 次模型，保留 7 筆 What。一次步驟追問約 23 秒、呼叫 2 次，得到 1 筆有來源的說明。重新啟動 PaperLens 容器後仍可讀取結果、對話和 trace。[Podman 實測紀錄](trace/PaperLens-Podman-trace.json)

### 失敗案例與可重現測試

| 情境 | 原因 | 處理與證據 |
| --- | --- | --- |
| 無法抽取文字 | PDF 頁面沒有文字層 | PDF Processing 停止並保留原因。[無文字 trace](trace/failure_no_text.json) |
| 引文找不到 | 測試替身提供了來源中不存在的引文 | 逐字核對未通過，指定範圍重試後停止。[引文錯誤 trace](trace/failure_bad_citation.json) |
| 引文無法支持說明 | 原文字串存在，語意驗證不支持候選說明 | 排除該說明及提示依據不足。[語意不支持 trace](trace/failure_unsupported.json) |

以上失敗情境以合成 PDF 和固定模型回覆進行可控的測試。公式與流程測試依賴 ReportLab。先在 Python 3.12 環境安裝依賴，再執行：

~~~powershell
python -m pip install -r requirements.txt reportlab
python verify_formulas.py
python verify_demo.py trace-run
~~~

`verify_formulas.py` 驗證上下標、分式及原頁渲染。`verify_demo.py` 使用合成單欄、雙欄各兩份 PDF，驗證來源、失敗流程及 SQLite 持久化。另有 [範例 PDF](sample.pdf) 可試用公式介面。
