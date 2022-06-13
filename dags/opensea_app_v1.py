import os
import time
import json
import logging
from datetime import datetime, timedelta
from selenium.webdriver.chrome.options import Options
from selenium import webdriver
from airflow import DAG
from airflow.operators.python_operator import PythonOperator, BranchPythonOperator
from airflow.operators.dummy_operator import DummyOperator
from airflow.operators.slack_operator import SlackAPIPostOperator
from airflow.operators.latest_only_operator import LatestOnlyOperator

default_args = {
    'owner': 'Jeremy Chen',
    'start_date': datetime(2022, 6, 12, 0, 0),
    'schedule_interval': '@daily',
    'retries': 2,
    'retry_delay': timedelta(minutes=1)
}

nft_page_template = 'https://opensea.io/collection/{}'

def process_metadata(mode, **context):

    file_dir = os.path.dirname(__file__)
    metadata_path = os.path.join(file_dir, '../data/opensea.json')

    if mode == 'read':
        with open(metadata_path, 'r') as fp:
            metadata = json.load(fp)
            print("Read History loaded: {}".format(metadata))
            return metadata

    elif mode == 'write':
        print("Saving latest nft information..")
        _, all_nft_info = context['task_instance'].xcom_pull(task_ids='check_nft_info')

        for nft_id, nft_info in dict(all_nft_info).items(): # update to latest chapter
            all_nft_info[nft_id]['previous_floor_price'] = nft_info['latest_floor_price']

        with open(metadata_path, 'w') as fp:
            json.dump(all_nft_info, fp, indent=2, ensure_ascii=False)

def check_nft_info(**context):
    metadata = context['task_instance'].xcom_pull(task_ids='get_read_history')
    driver = webdriver.Chrome()
    driver.get('https://opensea.io/')
    print("Arrived top page.")

    all_nft_info = metadata
    anything_new = False

    # 遍歷../data/collection.json中所有感興趣的NFT項目
    for nft_id, nft_info in dict(all_nft_info).items():
        nft_name = nft_info['name']
        print("Fetching {}'s floor price list..".format(nft_name))
        driver.get(nft_page_template.format(nft_id))

        # 尋找的元素有可能因為網站改版而遺失，在抓資料前可以先跑測試
        floor = driver.find_elements_by_xpath(
            "//*[@class='fresnel-container fresnel-greaterThanOrEqual-md ']"
        )
        latest_floor_price = floor[3].text.split('\n')[0]
        previous_floor_price = nft_info['previous_floor_price']

        all_nft_info[nft_id]['latest_floor_price'] = latest_floor_price
        all_nft_info[nft_id]['new_price_available'] = latest_floor_price != previous_floor_price
        if all_nft_info[nft_id]['new_price_available']:
            anything_new = True
            print("There are new floor price for {}(latest: {})".format(nft_name, latest_floor_price))

    if not anything_new:
        print("Nothing new now, prepare to end the workflow.")

    driver.quit()

    return anything_new, all_nft_info

def decide_what_to_do(**context):
    anything_new, _ = context['task_instance'].xcom_pull(task_ids='check_nft_info')

    print("跟紀錄比較，有沒有新地板價？")
    if anything_new:
        return 'yes_generate_notification'
    else:
        return 'no_do_nothing'

def get_token():
    file_dir = os.path.dirname(__file__)
    token_path = os.path.join(file_dir, '../data/credentials/slack.json')
    with open(token_path, 'r') as fp:
        token = json.load(fp)['token']
        return token

def generate_message(**context):
    _, all_nft_info = context['task_instance'].xcom_pull(task_ids='check_nft_info')

    message = ''
    for nft_id, nft_info in all_nft_info.items():
        if nft_info['new_price_available']:
            name = nft_info['name']
            latest = nft_info['latest_floor_price']
            prev = nft_info['previous_floor_price']
            message += '{} 最新地板價: {}（上次地板價：{}）\n'.format(name, latest, prev)
            message += '連結地址: ' + nft_page_template.format(nft_id) + '\n\n'

    file_dir = os.path.dirname(__file__)
    message_path = os.path.join(file_dir, '../data/message.txt')
    with open(message_path, 'w') as fp:
        fp.write(message)

def get_message_text():
    file_dir = os.path.dirname(__file__)
    message_path = os.path.join(file_dir, '../data/message.txt')
    with open(message_path, 'r') as fp:
        message = fp.read()

    return message

with DAG('opensea_app_v1', default_args=default_args) as dag:

    latest_only = LatestOnlyOperator(task_id='latest_only')

    get_read_history = PythonOperator(
        task_id='get_read_history',
        python_callable=process_metadata,
        op_args=['read'],
        provide_context=True
    )

    check_nft_info = PythonOperator(
        task_id='check_nft_info',
        python_callable=check_nft_info,
        provide_context=True
    )

    decide_what_to_do = BranchPythonOperator(
        task_id='new_price_available',
        python_callable=decide_what_to_do,
        provide_context=True
    )

    update_read_history = PythonOperator(
        task_id='update_read_history',
        python_callable=process_metadata,
        op_args=['write'],
        provide_context=True
    )

    generate_notification = PythonOperator(
        task_id='yes_generate_notification',
        python_callable=generate_message,
        provide_context=True
    )

    send_notification = SlackAPIPostOperator(
        task_id='send_notification',
        token=get_token(),
        channel='#opensea-floor-price',
        text=get_message_text(),
        icon_url='http://airbnb.io/img/projects/airflow3.png'
    )

    do_nothing = DummyOperator(task_id='no_do_nothing')

    latest_only >> get_read_history
    get_read_history >> check_nft_info >> decide_what_to_do
    decide_what_to_do >> generate_notification
    decide_what_to_do >> do_nothing
    generate_notification >> send_notification >> update_read_history
