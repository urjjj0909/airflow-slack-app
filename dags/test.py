import os
import time
import json
import logging
from datetime import datetime, timedelta
from selenium import webdriver

file_dir = os.path.dirname(__file__)
metadata_path = os.path.join(file_dir, '../data/opensea.json')

with open(metadata_path, 'r') as fp:
    all_nft_info = json.load(fp)

driver = webdriver.Chrome()
driver.get('https://opensea.io/')
print("Arrived top page.")

nft_page_template = 'https://opensea.io/collection/{}'

for nft_id, nft_info in dict(all_nft_info).items():
    nft_name = nft_info['name']
    print("Fetching {}'s floor price list..".format(nft_name))
    driver.get(nft_page_template.format(nft_id))

    floor = driver.find_elements_by_xpath(
        "//*[@class='fresnel-container fresnel-greaterThanOrEqual-md ']"
    )
    print(floor[3].text.split('\n')[0])