import time
import io
import re
import pandas as pd
import itertools
import Levenshtein
from functools import wraps
from datetime import datetime, timedelta
from multiprocessing import Pool
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
from concurrent.futures import ThreadPoolExecutor, as_completed

from services.constants import *
from services.shopee import *
from services.lazada import *

MAX_RETRY = 3
MAX_CONNECTIONS = 5

def clean_item_name(item_name):
    item_name = ''.join([i for i in item_name if i.isalnum() or i==' ']).lower()
    item_name = item_name if len(item_name) > 0 else None
    return item_name

def try_int(str):
    try:
        int_str = int(str)
        return True
    except:
        return False

def search_lzd_items(item_name, proxy):
    req_worked = False
    retry = 0

    req_data = {
        'search_keyword': item_name,
        'proxy': proxy
    }
    items = []
    
    while retry <= MAX_RETRY and not req_worked:
        data = {}
        try:
            data = lazada_search(req_data)
            items = data['items']
            req_worked = True
        except Exception as e:
            delay = 7 + (2 * retry)
            time.sleep(delay)
            retry += 1
            print('RETRYING', retry, item_name, str(e))

    if len(items) > 0:
        items = list(map(lambda x: {
            'sellerId': x['sellerId'],
            'sellerName': x['sellerName'],
            'LZD_item_name': x['name'],
            'LZD_item_url': 'https:' + x['productUrl'],
            'price': x['price'],
            'inStock': x['inStock'],
            'item_name': item_name
        }, items))

    return items

def get_lzd_item_details(lzd_item_url, proxy, timeout=5):
    req_worked = False
    retry = 0

    req_data = {
        'item_url': lzd_item_url,
        'proxy': proxy
    }
    details = {}

    while retry <= MAX_RETRY and not req_worked:
        try:
            data = lazada_item_details(req_data)
            details = data
            req_worked = True
        except Exception as e:
            delay = timeout + (2 * retry)
            time.sleep(delay)
            print('Error getting lzd item details', lzd_item_url, e)
            retry += 1

    return details

def get_lzd_shop_items(lzd_item_url, proxy, timeout=5):
    req_worked = False
    retry = 0

    item_details = get_lzd_item_details(lzd_item_url, proxy)
    lzd_shop_url = item_details.get('shop_url')

    req_data = {
        'shop_url': lzd_shop_url,
        'proxy': proxy
    }
    items = []

    while not req_worked and retry < MAX_RETRY:
        try:
            data = lazada_shop_items(req_data)
            items.extend(data.get('items'))
            req_worked = True
        except Exception as e:
            delay = timeout + (2 * retry)
            time.sleep(delay)
            print('Error getting lzd shop items', lzd_shop_url, e)
            retry += 1
    for item in items:
        item['key'] = lzd_item_url

    return items

def get_shopee_items(shop_id, proxy):
    req_worked = False
    retry = 0

    req_data = {
        'shop_id': shop_id,
        'proxy': proxy
    }
    
    item_details = []
    while not req_worked and retry < MAX_RETRY:
        try:
            shop_details = shopee_shop_details(req_data)
            username = shop_details['account']['username']
            shop_items = shopee_shop_items(req_data)
            items = shop_items['items']
            item_details = list(map(lambda x: {
                'itemid': x.get('itemid'),
                'shopid': x.get('shopid'),
                'item_name': x.get('item_basic', {}).get('name'),
                'username': username,
                'sold': x.get('item_basic', {}).get('sold'),
                'historical_sold': x.get('item_basic', {}).get('historical_sold'),
                'liked_count': x.get('item_basic', {}).get('liked_count'),
            }, items))
            req_worked = True
        except Exception as e:
            print('ERROR IN SHOPEE ITEMS', str(e))
            retry += 1
            time.sleep(2 * (retry + 1))
    return item_details

def match_shopee_shop(shopid, proxy):
    empty_df = pd.DataFrame()

    # GET SHOPEE SHOP ITEMS
    all_shopee_items = get_shopee_items(shopid, proxy)
    all_shopee_items_df = pd.DataFrame(all_shopee_items)
    top_shopee_items_df = all_shopee_items_df.sort_values(by=['sold'], ascending=False)[:10] # top ADO items

    # SEARCH FOR SHOP ITEMS
    search_df = pd.DataFrame()
    item_names = top_shopee_items_df['item_name'].drop_duplicates().values.tolist()

    search_results = []
    with ThreadPoolExecutor(max_workers=MAX_CONNECTIONS) as executor:
        future_to_url = {
            executor.submit(search_lzd_items, shopid, proxy)
            for item_name in item_names
        }
        for future in as_completed(future_to_url):
            res = future.result()
            if len(res) > 0:
                search_results.extend(res)
    search_df = pd.DataFrame(search_results)

    # NO RESULTING SEARCH ITEMS
    if len(search_df) == 0:
        return empty_df

    master_search_df = search_df.merge(top_shopee_items_df, on='item_name', how='inner')

    top_shops = master_search_df.groupby(['shopid','sellerName']).agg({'LZD_item_url':'count'}).reset_index().sort_values(['shopid','LZD_item_url'], ascending=[True,False]).groupby('shopid').head(20)
    top_shops = top_shops[['shopid','sellerName']].merge(top_shopee_items_df, how='left', on='shopid').merge(master_search_df.drop_duplicates('sellerName')[['sellerName','LZD_item_url']])

    # LZD SHOP ITEMS / ITEM LEVEL SEARCH
    laz_item_urls = top_shops['LZD_item_url'].drop_duplicates().values.tolist()
    laz_shops_items = []
    with ThreadPoolExecutor(max_workers=MAX_CONNECTIONS) as executor:
        future_to_url = {
            executor.submit(get_lzd_shop_items, item_url, proxy)
            for item_url in laz_item_urls
        }
        for future in as_completed(future_to_url):
            res = future.result()
            if len(res) > 0:
                laz_shops_items.extend(res)

    laz_items_df = pd.DataFrame(laz_shops_items)
    df = (
        top_shops[['shopid','sellerName','LZD_item_url']]
        .drop_duplicates('LZD_item_url')
        .rename(columns={'LZD_item_url':'key','shopid':'shp_shopid'})
        .merge(laz_items_df, how='left', on='key')
    )
    df = df[['shp_shopid','sellerName','shop_url','mobileUrl','title']]
    lazada_shop = df.fillna('')
    shopee_shop = all_shopee_items_df.fillna('').rename(columns={'item_name':'title'}).drop_duplicates(['shopid','title'])

    # MATCHING
    all_matches = []
    MATCH_THRESHOLD = 0.4
    debug = 0
    # NO LZD SHOP ITEMS
    if len(lazada_shop) == 0:
        return empty_df
    
    all_items = pd.concat([shopee_shop['title'], lazada_shop['title']]).reset_index(drop=True)
    all_items_list = all_items.values.tolist()
    vectorizer = TfidfVectorizer(strip_accents='unicode', max_df=0.95)
    X = vectorizer.fit_transform(all_items_list)
    scores = cosine_similarity(X[:len(shopee_shop)], X[len(shopee_shop):])

    # MAP MATCHES
    for ind in range(len(scores)):
        try:
            best_score_ind = scores[ind].argmax()
            levenshtein_score = Levenshtein.ratio(shopee_shop['title'].iloc[ind], lazada_shop['title'].iloc[best_score_ind])
            if (debug == 0 and max(scores[ind]) < MATCH_THRESHOLD and levenshtein_score < MATCH_THRESHOLD) or (debug != 0 and max(scores[ind]) < 0.6):
                continue
            
            match = [
                lazada_shop.iloc[best_score_ind]['sellerName'],
                lazada_shop.iloc[best_score_ind]['shop_url'],
                lazada_shop.iloc[best_score_ind]['title'],
                lazada_shop.iloc[best_score_ind]['mobileUrl'],
                shopee_shop.iloc[ind]['itemid'],
                shopee_shop.iloc[ind]['shopid']
            ]
            all_matches.append(match)
        except Exception as e:
            continue

    all_matches_df = pd.DataFrame(all_matches, columns=['sellerName','shop_url','laz_item_name','laz_item_url','itemid','shopid'])
    all_matches_df = shopee_shop.merge(all_matches_df, how='left', on=['shopid','itemid'])
    all_matches_df['laz_item_url_unique'] = all_matches_df['laz_item_url']

    final_matches_df = (
        all_matches_df
        .groupby(['shopid','username','sellerName','shop_url'])
        .agg({'laz_item_url':'count', 'laz_item_url_unique': pd.Series.nunique})
        .reset_index().fillna(0)
        .sort_values('laz_item_url', ascending=False)
    )
    shopee_count = max(len(shopee_shop), 1)
    laz_count = max(len(lazada_shop), 1)
    final_matches_df['percent_shopee_covered'] = final_matches_df['laz_item_url'] / shopee_count
    final_matches_df['percent_lazada_covered'] = final_matches_df['laz_item_url_unique'] / laz_count
    final_matches_df['timestamp'] = datetime.now().strftime('%m/%d/%Y %H:%M')

    print('DONE WITH {}: {} results'.format(shopid, len(final_matches_df)))
    if len(final_matches_df) > 0:
        return final_matches_df
    # NO MATCHING RESULTS
    else:
        return empty_df