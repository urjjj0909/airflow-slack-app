from selenium import webdriver

browser = webdriver.Chrome()
browser.get("https://opensea.io/collection/alphasharksofficial")
print("Hello! Opensea!") # should be shown in terminal
browser.quit()