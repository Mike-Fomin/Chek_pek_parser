import json
import os
import time
import traceback
from datetime import datetime

import requests
from bs4 import BeautifulSoup

HEADERS: dict = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
}

TOP_TITLES_KEYS: list = [
    'user',
    'metadata',
    'userInn',
    'dateTime',
    'requestNumber',
    'shiftNumber',
    'cashier',
    'operationType'
]

SOLD_TITLES_KEYS: list = [
    'positionNumber',
    'name',
    'price',
    'quantity',
    'sum'
]

FISCAL_DATA: list = [
    'fiscalDriveNumber',
    'fiscalDocumentNumber'
]


def parse_check(data: BeautifulSoup) -> dict:
    """ function reads check information and return the dictionary with results """
    check_id: str = data.get('id')[4:]
    check: dict = {'checkID': int(check_id)}

    items_in_check_table: BeautifulSoup = data.find('table').extract()
    fiscal_info: BeautifulSoup = data.find('p').extract()
    _: BeautifulSoup = data.find('div').extract()

    top_check_block: list = data.text.strip().split('\n')
    if top_check_block[0].startswith('ИНН'):
        for _ in range(2):
            top_check_block.insert(0, '')
    elif top_check_block[1].startswith('ИНН'):
        top_check_block.insert(1, '')

    for key, value in zip(TOP_TITLES_KEYS, top_check_block):
        key: str
        value: str

        match key:

            case 'metadata':
                value: dict = {'address': value}

            case 'userInn':
                value: str = value.replace('ИНН ', '').strip()

            case 'dateTime':
                value: str = value.replace(' \xa0 ', ' ')

            case 'requestNumber':
                value: str = value.replace('Чек №', '').strip()

            case 'shiftNumber':
                value: str = value.replace('Смена №', '').strip()

            case 'cashier':
                continue

        check[key] = value

    sold_items: list = []
    tr_rows: list = items_in_check_table.find_all('tr')
    for tr_row in tr_rows:
        tr_row: BeautifulSoup

        class_name: list = tr_row.get('class')
        if not class_name:
            continue

        match class_name[0]:

            case 'check_items':
                sold_item: dict = {}
                for key, val in zip(SOLD_TITLES_KEYS, tr_row.find_all('td')):
                    key: str
                    val: BeautifulSoup

                    value: str = val.text.strip()
                    sold_item[key] = value
                sold_items.append(sold_item)

            case 'itg':
                check['items'] = sold_items
                check['totalSum'] = tr_row.find_all('td')[-1].text.strip()

            case 'alterbtm':
                key, value = tr_row.find_all('td')
                key: BeautifulSoup
                value: BeautifulSoup
                key: str = key.text.strip()
                value: str = value.text.strip()

                match key:
                    case 'Наличные':
                        check['cashTotalSum'] = value
                    case 'Карта':
                        check['ecashTotalSum'] = value
                    case 'НДС не облагается':
                        check['noNds'] = value
                    case 'НДС итога чека со ставкой 0%':
                        check['nds0'] = value
                    case 'НДС итога чека со ставкой 10%':
                        check['nds10'] = value
                    case 'НДС итога чека со ставкой 20%':
                        check['nds20'] = value

            case 'lastbrd':
                check['kktRegId'] = tr_row.find('td').text.strip()[15:]

    fi: list = fiscal_info.text.split('\n')
    for key, value in zip(FISCAL_DATA, fi):
        key: str
        value: str
        check[key] = value[4:]

    return check


def parse_page(page: int) -> list | None:
    """ function reads html-page and returns the list of checks on the page """
    params: dict = {
        'step': page,
    }
    try:
        response: requests.Response = requests.get('https://chek-pek.ru/', params=params, headers=HEADERS)
        print(f"Page {page}: status code {response.status_code}")
        if response.status_code == 200:
            soup: BeautifulSoup = BeautifulSoup(markup=response.text, features='lxml')
            checklist: list = soup.find_all(name='div', class_='oneChek')
        else:
            raise ConnectionError(f'Status code is {response.status_code}!')
    except:
        print(f"Page {page} error!")
        traceback.print_exc()
    else:
        return checklist


def main() -> None:
    """ main function for website parsing"""
    max_value_item: int = 0
    if os.path.exists('files/today_checks.json'):
        print('Считываются данные из файла...')
        with open('files/today_checks.json', mode='r', encoding='utf-8') as full_file:
            data_from_file: list = json.load(full_file)

        if data_from_file:
            last_item_from_file: dict = data_from_file[0]
            print('Данные успешно прочитаны...')
            max_value_item: int = last_item_from_file['checkID']

    all_items: list = []
    break_flag: bool = False
    for page in range(1, 50_000):
        page: int

        checklist: list | None = parse_page(page)

        if checklist is not None:

            if not checklist:
                break_flag: bool = True
                print('Достигнут лимит доступных страниц!')
            else:
                for check in checklist:
                    check: BeautifulSoup

                    item_dict: dict = parse_check(check)
                    if item_dict['checkID'] > max_value_item:
                        if item_dict not in all_items:
                            all_items.append(item_dict)
                    else:
                        break_flag: bool = True
                        print('Достигнут чек из предыдущего парсинга!')
                        break

        if break_flag:
            break
        time.sleep(1)

    if not os.path.exists('files'):
        os.makedirs('files')
    with open('files/today_checks.json', 'w', encoding='utf-8') as json_file1:
        json.dump(all_items, json_file1, indent=4, ensure_ascii=False)

    with open(f"files/all_checks_{datetime.now().strftime('%d_%m_%Y')}.json", "w", encoding="utf-8") as json_file2:
        json.dump(all_items, json_file2, indent=4, ensure_ascii=False)

    print('Парсинг успешно завершен!')
    print(f'Итоговое количество чеков {len(all_items)}')


if __name__ == '__main__':
    main()
