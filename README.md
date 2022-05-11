# Airflow-slack-app
在這裡我們依照[一段Airflow與資料工程的故事：談如何用Python追漫畫連載](https://leemeng.tw/a-story-about-airflow-and-data-engineering-using-how-to-use-python-to-catch-up-with-latest-comics-as-an-example.html#app-v2)教學，同樣實作利用Slack做訊息更新的服務並依照`comic_app_v3.py`架構修改成`opensea_app_v1.py`，改成一個追蹤Opensea自己感興趣NFT地板價（Floor price）的App。

我們會利用自動化網頁測試工具Selenium去搜尋特定NFT的價錢，並按照設定時間回傳至Slack的Channel中，在下面講解Chrome和Chrome driver安裝的部分可交互參照這二篇精彩的教學：

1. [ChromeDriver in WSL2](https://www.gregbrisebois.com/posts/chromedriver-in-wsl2/)
2. [Run Selenium and Chrome on WSL2 using Python and Selenium webdriver](https://cloudbytes.dev/snippets/run-selenium-and-chrome-on-wsl2)

## 下載並安裝Chrome
首先，我們先下載Linux版本的Chrome並安裝相關的函式庫：

```
sudo apt-get update
sudo apt-get install -y curl unzip xvfb libxi6 libgconf-2-4
```

下載目前Chrome的穩定版本：

```
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

安裝成功後可以執行以下指令確認：

```
google-chrome --version # Google Chrome 101.0.4951.54 for example
```

## 下載並安裝Chrome driver
這裡第一種作法是直接到該[網頁](https://chromedriver.storage.googleapis.com/)中查詢對應Chrome版號的version，下載後再解壓縮：

```
sudo apt-get install unzip
wget https://chromedriver.storage.googleapis.com/<version>/chromedriver_linux64.zip
unzip chromedriver_linux64.zip
```

也可以自動偵測目前Chrome的版本放到`chrome_driver`變數中：

```
chrome_driver=$(curl "https://chromedriver.storage.googleapis.com/LATEST_RELEASE")
echo "$chrome_driver"
```

再來下載相對應版號的Chrome driver後解壓縮：

```
curl -Lo chromedriver_linux64.zip "https://chromedriver.storage.googleapis.com/${chrome_driver}/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
```

最後，我們把解壓縮後的Chrome driver移到`/usr/bin`並加入`~/.bashrc`中：

```
sudo mv -f ~/chromedriver /usr/bin
echo 'export PATH=$PATH:/usr/bin' >> ~/.bashrc
```

完成後可以執行以下指令確認：

```
chromedriver --version
which chromedriver # should be /usr/bin/chromedriver
```

最後，我們設定使用權限：

```
sudo chown root:root /usr/bin/chromedriver
sudo chmod +x /usr/bin/chromedriver
```

最後，如果想要將呼叫Selenium啟動自動測試的畫面顯示出來，可以參考[ChromeDriver in WSL2](https://www.gregbrisebois.com/posts/chromedriver-in-wsl2/)建立X Server的部分，主要是用`DISPLAY`去讓GUI application知道X Server要使用哪個連接埠（Port），我們可以把它寫到`~/.bashrc`裡並做測試：

```
echo 'export DISPLAY=$(cat /etc/resolv.conf | grep nameserver | awk '{print $2; exit;}'):0.0' >> ~/.bashrc
echo $DISPLAY # 172.26.144.1:0.0 for example
```

註：Windows可能要解決防火牆問題，啟動X Server時記得勾選「Disable access control」並到左下角搜尋「允許應用程式通過Windows防火牆」、勾選「VcXsrv windows xserver」即可。

## 建立Selenium環境
首先，我們需要Selenium套件去做網頁訪問，因此先執行以下指令分別安裝Selenium套件：

```
pip install selenium
```

同時，我們建立一個`opensea_selenium.py`測試腳本確認一切準備就緒：

```
from selenium import webdriver

browser = webdriver.Chrome()
browser.get("https://opensea.io/collection/alphasharksofficial")
print("Hello! Opensea!") # should be shown in terminal
browser.quit()
```

## Slack App設定
到[Slack官網](https://slack.com/intl/zh-tw/help/articles/209038037-%E4%B8%8B%E8%BC%89-Slack-Windows-%E7%89%88)下載安裝後開始進行設定。我們先建立一個`airflow-test`的Workspace，並在Channels的地方增加`#opensea-floor-price`頻道。

接著，我們需要在`#opensea-floor-price`頻道中加入一個機器人（Bot），利用這個Bot去把`opensea_app_v1.py`中SlackAPIPostOperator傳遞的訊息寫進頻道中。到[Slack API頁面](https://api.slack.com/apps)先`Create New App`、選擇From Scratch後輸入頻道和Workspace：

![image](https://user-images.githubusercontent.com/100120881/167762978-af43e2ba-2825-4bc1-ba3e-bfabf8ce2534.png)

新增完App後應該會在下方App Name看到剛剛的App，點進去後應該會看到這個App的設定頁面：

![image](https://user-images.githubusercontent.com/100120881/167763774-192be817-fbed-486a-a588-7c2857583729.png)

打開左側`Incoming Webhooks`、再把Activate Incoming Webhook「On」起來，Slack就會幫你建立一個Webhook URL，妳可以複製下方curl指令測試Bot是不是有正常工作：

![image](https://user-images.githubusercontent.com/100120881/167764442-d4da2a7f-9c7e-4286-a5e1-2d76934211d5.png)

打開左側`OAuth & Permissions`看到自動生成的OAuth Tokens for Your Workspace，把這串Token複製貼上到`data/credentials/slack.json`。最後，在Scope中新增一個OAuth Scope並把`chat:write`加入，這樣就允許我們用API去訪問並控制Slack Bot寫訊息：

![image](https://user-images.githubusercontent.com/100120881/167765094-bcc55875-ad1e-4505-ae73-898bcb0a76ef.png)

## 修改程式碼
程式碼僅列出一些比較重要的修改部分：

```
nft_page_template = 'https://opensea.io/collection/{}'

def process_metadata(mode, **context):
    ...
    metadata_path = os.path.join(file_dir, '../data/opensea.json') # 另外開一個opensea.json專門記錄nft資訊
    ...

def check_nft_info(**context):
    ...
    for nft_id, nft_info in dict(all_nft_info).items():
        ...
        floor = driver.find_elements_by_xpath( # 定位出頁面中floor price區域位置
            "//*[@class='Blockreact__Block-sc-1xf18x6-0 Textreact__Text-sc-1w94ul3-0 cLsBvb kscHgv']"
        )
        latest_floor_price = floor[2].text
        previous_floor_price = nft_info['previous_floor_price']
        ...

with DAG('opensea_app_v1', default_args=default_args) as dag:
    ...
    send_notification = SlackAPIPostOperator(
        task_id='send_notification',
        token=get_token(),
        channel='#opensea-floor-price', # 開一個名稱為「opensea-floor-price」的Slack channel
        text=get_message_text(),
        icon_url='http://airbnb.io/img/projects/airflow3.png'
    )
    ...
```

接著，就可以把DAG的Graph中開啟看資料管線處理過程，以及觀察在各步驟成功與否：

![image](https://user-images.githubusercontent.com/100120881/167760740-2aa08725-1b83-4ed0-9e4e-8290e309a4db.png)

最後，右下角應該會彈出Slack通知視窗，並在Slack#opensea-floor-price中獲取最新地板價訊息：

![image](https://user-images.githubusercontent.com/100120881/167761415-932c3e93-dc5c-4325-8e47-71d7edb1ef79.png)

## 注意事項
* 在Linux中若想要和Google drive作互動，可以參考[[Python] 使用 gdown 套件來下載 Google 雲端硬碟的檔案](https://clay-atlas.com/blog/2020/03/13/python-chinese-note-package-gdown-download-google-drive/)安裝函式庫`gdown`
* 在Windows系統中也可以直接在`\\wsl$\Ubuntu-18.04`路徑找到Linux子系統的相關檔案
