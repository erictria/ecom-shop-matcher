import re
import json
import urllib3
import requests
from html2text import html2text
from services.constants import *

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def lazada_search_api(request):
    search_keyword = request['search_keyword']
    proxy = request['proxy']
    api_link = 'https://www.lazada.com.ph/catalog/?_keyori=ss&ajax=true&from=input&page=1&q={}'.format(search_keyword)

    res = requests.get(api_link, proxies=proxy, verify=False)
    data = res.json()
    items = data['mods']['listItems']

    response = {
        'items': items
    }
    return response

def lazada_search(request):
    search_keyword = str(request['search_keyword'])
    proxy = request['proxy']
    lzd_search_url = 'https://www.lazada.com.ph/catalog/?q={}&_keyori=ss&from=input'.format(search_keyword.replace(' ','+'))

    res = requests.get(lzd_search_url, proxies=proxy, verify=False)
    data = json.loads(re.search('<script>\n    window.pageData = (.+)?;\n  </script>', res.text).group(1))
    items = data['mods']['listItems']

    response = {
        'items': items
    }
    return response

def lazada_item_details(request):
    item_url = request['item_url']
    proxy = request['proxy']

    # get item data
    res = requests.get(item_url, proxies=proxy, verify=False)
    result = re.search('var __moduleData__ = (.+);\n', res.text).group(1)
    data = json.loads(result)['data']['root']['fields']
    default_model = data['skuInfos']['0']


    # get shared item data
    item_output = {}

    # shop-level data
    item_output['shop_id'] = data['seller']['shopId']
    item_output['shop_name'] = data['seller']['name']
    item_output['shop_url'] = 'https:' + data['seller']['url'].split('?')[0]

    # item-level
    item_output['parent_item_url'] = item_url
    item_output['item_name'] = re.search('\/products\/(.+)-i[0-9]+-s[0-9]+\.html', data['product']['link']).group(1)
    item_output['item_name_actual'] = data['product'].get('title', item_output['item_name'])
    item_output['description'] = (
        html2text(data['product'].get('highlights',''))
        .encode('latin-1', errors='ignore').decode('latin-1')
    )
    item_output['fulfilled_by_lazada'] = 1 if 'Fulfilled by Lazada' in res.text else 0
    item_output['ships_from_overseas'] = 1 if 'Ships from Overseas' in res.text else 0

    # main category
    cat_list = default_model['dataLayer'].get('pdt_category', None)
    if type(cat_list) != list:
        item_output['category'] = cat_list
    else:
        categ_tiers = ['category', 'sub_category', 'level3_category']
        for i, cat in enumerate(categ_tiers):
            try:
                item_output[cat] = cat_list[i]
            except:
                item_output[cat] = ''

    # get ratings (0 if no ratings)
    ratings = data['review']['ratings']
    item_output['num_ratings'] = ratings['rateCount']
    item_output['avg_rating'] = ratings['average']
    item_output['review_count'] = ratings['reviewCount']

    return item_output

def lazada_shop_items(request):
    shop_api_url = 'https://www.lazada.com.ph/shop/site/api/seller/products?shopId={0}&offset={1}&limit={2}'
    LIMIT = 500
    MAX_OFFSET = 22
    shop_url = request['shop_url']
    proxy = request['proxy']

    # get shopid
    res = requests.get(shop_url, proxies=proxy, verify=False)
    shop_results = re.search('window.pageData =(.+)\;', res.text).group(1)
    shopid = json.loads(shop_results)['shopId']

    # get items
    items = []
    for offset in range(1, MAX_OFFSET):
        res = requests.get(shop_api_url.format(shopid, offset, LIMIT), proxies=proxy, verify=False)
        data = res.json()['result']
        total_items = data['meta']['total']
        if data.get('products'):
            items += data['products']
            # print(len(items), '/', total_items)
            if len(items) >= total_items:
                break

    for item in items:
        item['shop_url'] = shop_url

    response = {
        'items': items
    }
    return response