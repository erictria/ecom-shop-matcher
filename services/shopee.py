import re
import json
import urllib3
import requests
from services.constants import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def shopee_search(request):
    search_keyword = request['search_keyword']
    proxy = request['proxy']
    api_link = 'https://shopee.ph/api/v4/search/search_items?by=relevancy&keyword={}&limit=100&newest=0&order=desc&page_type=search&scenario=PAGE_GLOBAL_SEARCH&version=2'.format(search_keyword)

    res = requests.get(api_link, proxies=proxy, verify=False)
    data = res.json()
    items = data['items']

    response = {
        'items': items
    }
    return response

def shopee_shop_items(request):
    shop_api_url = 'https://shopee.ph/api/v4/search/search_items?by=pop&entry_point=ShopByPDP&limit={0}&match_id={1}&newest={2}&order=desc&page_type=shop&scenario=PAGE_OTHERS&version=2'
    page_limit = 100
    starting_point = 0
    print(request)
    shop_id = request['shop_id']
    proxy = request['proxy']
    cont = True

    # get items
    items = []
    while cont:
        res = requests.get(shop_api_url.format(page_limit, shop_id, starting_point), proxies=proxy, verify=False)
        data = res.json()
        total_items = data['total_count']
        if data.get('items'):
            items += data['items']
            # print(len(items), '/', total_items)
            starting_point += page_limit
            if len(items) >= total_items:
                break
        else:
            cont = False

    response = {
        'items': items
    }
    return response

def shopee_shop_details(request):
    base_url = "https://shopee.ph/api/v2/shop/get?shopid={0}"
    shopid = request['shop_id']
    proxy = request['proxy']

    search_url = base_url.format(shopid)
    response = {}

    res = requests.get(search_url, proxies=proxy, verify=False)
    json_response = json.loads(res.text)
    shop_details = json_response.get('data')

    response = shop_details

    return response