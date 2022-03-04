import requests
import bs4
import streamlit as st
import json
import hashlib
import time

EBISU_URL = "https://retty.me/API/WOUT/acp-ebisu-contents/"
POPULAR_RESUTAURANTS_URL = "https://retty.me/API/WOUT/get-popular-restaurants-acp/"

@st.cache
def fetch_pref_dict():
    print("fetch called")
    AREA_TABLE_URL = "https://retty.me/area/"
    TO_FETCH_PREFECTURE_LIST = ["東京", "神奈川", "千葉", "埼玉", "大阪"] #, "名古屋"]
    area_soup = bs4.BeautifulSoup(requests.get(AREA_TABLE_URL).text)
    pref_dict = {}
    for prefecture_to_find in TO_FETCH_PREFECTURE_LIST:
        prefecture_dict = {}
        prefecture_dict["name"] = prefecture_to_find
        prefecture_a_el = area_soup.find("a", string=prefecture_to_find)
        prefecture_dict["url"] = prefecture_a_el["href"]
        small_area_td = prefecture_a_el.parent.next_sibling
        small_area_li_el_list = small_area_td.ul.find_all("li", recursive=False)
        prefecture_dict["small_areas"] = {}
        for small_area_li in small_area_li_el_list:
            small_area_dict = {}
            small_area_dict["name"] = small_area_li.a.text
            small_area_dict["url"] = small_area_li.a["href"]
            prefecture_dict["small_areas"][small_area_dict["name"]] = small_area_dict
        pref_dict[prefecture_to_find] = prefecture_dict
    return pref_dict

pref_dict = fetch_pref_dict()

selected_pref = st.sidebar.selectbox(
    "都道府県",
    pref_dict.keys()
)

selected_area = st.sidebar.selectbox(
    "エリア",
    pref_dict[selected_pref]["small_areas"].keys()
)

print(selected_pref)

INTERVAL = st.number_input("お店をさらに読み込むインターバル（秒）", value=3.0)
MAX_READ_MORE = st.number_input("何回お店をさらに読み込むか（回）", min_value = 0)

def get_sorted_ids_from_restaurant_list(restaurant_list):
    ids = [x["restaurant_id"] for x in restaurant_list]
    int_id_list = [int(x) for x in ids]
    int_id_list.sort()
    sorted_id_list = [str(x) for x in int_id_list]
    return sorted_id_list

def make_post_data_from_restaurant_list(restaurant_list):
    data = {}
    key_f = "exclude_ids[{}]"
    ids = get_sorted_ids_from_restaurant_list(restaurant_list)
    for i, str_id in enumerate(ids, 1):
        data[key_f.format(i)] = str_id
    return data

def get_hash_from_restaurant_list(restaurant_list):
    ids = get_sorted_ids_from_restaurant_list(restaurant_list)
    joined_ids = ",".join(ids)
    md5_ob = hashlib.md5()
    md5_ob.update(joined_ids.encode("utf-8"))
    hashed_exist_ids =  md5_ob.hexdigest()
    return hashed_exist_ids

# if 'read_more_times' not in st.session_state:
st.session_state['read_more_times'] = 0

PER_PAGE = 20
already_fetched_ebisu_restaurants = []
if st.button("取得開始"):
    progressbar = st.progress(0)
    area_referer_url = pref_dict[selected_pref]["small_areas"][selected_area]["url"]
    referer_header = {"referer":area_referer_url}
    while True:
        if MAX_READ_MORE - st.session_state["read_more_times"] < 0:
            break
        res = requests.post(EBISU_URL,
                            params={"hashed_exist_ids": get_hash_from_restaurant_list(already_fetched_ebisu_restaurants)},
                            data=make_post_data_from_restaurant_list(already_fetched_ebisu_restaurants),
                            headers={"referer":area_referer_url})
        ebisu_json = json.loads(res.text)
        already_fetched_ebisu_restaurants += ebisu_json
        if len(ebisu_json) < PER_PAGE:
            break
        time.sleep(INTERVAL)
        st.session_state.read_more_times += 1
        progressbar.progress(st.session_state['read_more_times']/(MAX_READ_MORE+1))

    limit=PER_PAGE
    offset=0
    already_fetched_popular_restaurants = []
    while True:
        if MAX_READ_MORE - st.session_state["read_more_times"] < 0:
            break
        popular_restaurant_json = json.loads(requests.get(POPULAR_RESUTAURANTS_URL, params={"limit":limit, "offset":offset}, headers=referer_header).text)
        already_fetched_popular_restaurants += popular_restaurant_json
        offset += limit
        if len(popular_restaurant_json) < PER_PAGE:
            break
        time.sleep(INTERVAL)
        st.session_state.read_more_times += 1
        progressbar.progress(st.session_state['read_more_times']/(MAX_READ_MORE+1))

    restaurants = already_fetched_ebisu_restaurants+already_fetched_popular_restaurants
    len(restaurants)
    # complete fetch
    # 名前、URL,エリア、ジャンル、電話番号
    # restaurant_name, url_index, area_name→sub_area_name, category_name, restaurant_tel
    download_csv_str = "名前, URL, エリア, ジャンル, 電話番号\n"
    for restaurant in restaurants:
        if "url_index" in restaurant:
            restaurant_url = restaurant["url_index"]
        else:
            restaurant_url = restaurant["restaurant_url"]
        str_to_append = "{}, {}, {}, {}, {}\n".format(restaurant["restaurant_name"], restaurant_url, restaurant["area_name"] + "/" + restaurant["sub_area_name"], restaurant["category_name"], restaurant["restaurant_tel"])
        download_csv_str += str_to_append
    st.download_button("CSVダウンロード", download_csv_str, "output.csv")