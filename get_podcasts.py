import requests
import argparse
from bs4 import BeautifulSoup
from dateutil.parser import parse, parserinfo

parser = argparse.ArgumentParser(description="Genera un feed RSS per gli episodi più recenti dei podcast de Il Post")
parser.add_argument("user")
parser.add_argument("password")
target = parser.add_mutually_exclusive_group(required=True)
target.add_argument("--podcast", nargs='+', default = [])
target.add_argument("--download-all", action='store_true')
args=parser.parse_args()

base_url = 'https://www.ilpost.it/'
wp_ajax = base_url + 'wp-admin/admin-ajax.php'
wp_login = base_url + 'wp-login.php'
# TODO: Automatically retrieve public podcast IDs
podcast_ids = {'morning' : 227474, 'tienimi-bordone' : 227193, 'politics' : 229701, 'podcast-eurovision' : 227496, 'tienimi_morning' : 231758, 'il-podcast-del-post-su-sanremo' : 227196}
username = args.user
password = args.password

podcast_head = '<?xml version="1.0" encoding="UTF-8"?> <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0"> <channel> <itunes:block>yes</itunes:block> <googleplay:block>yes</googleplay:block> </channel> </rss>'

class ItalianParserInfo(parserinfo):
    MONTHS = [('Gen', 'January'), ('Feb', 'February'), ('Mar', 'March'), ('Apr', 'April'), ('Mag', 'May'), ('Giu', 'June'), ('Lug', 'July'), ('Ago', 'August'), ('Set', 'Sett', 'September'), ('Ott', 'October'), ('Nov', 'November'), ('Dic', 'December')]

def build_feed(podcast_name, data):
    """
    data is a dict with keys msg, subscriber, userType, onlySubscriber, postcastList
    postcastList is a list of dict with dict_keys(['content', 'date', 'description', 'free', 'hash', 'id', 'image', 'milliseconds', 'minutes', 'object', 'old_podcast_id', 'old_timestamp', 'podcast', 'podcast_id', 'podcast_raw_url', 'range', 'timestamp', 'title', 'type', 'url']
    """
    if data['msg'] != 'OK' :
        raise Exception('Ajax server answered' + data['msg'] + 'on podcast' + podcast_name)
    out_soup = BeautifulSoup(podcast_head, 'xml')
    podcast_info_dict = data['postcastList'][0]['podcast'] #['author', 'chronological', 'count', 'cyclicality', 'description', 'free', 'gift', 'gift_all', 'id', 'image', 'imageweb', 'object', 'order', 'pushnotification', 'robot', 'title', 'type', 'url']
    channel_tag = out_soup.rss.channel
    title_tag = out_soup.new_tag("title")
    title_tag.string = podcast_info_dict['title']
    podcast_picture = podcast_info_dict['image']
    image_tag = out_soup.new_tag("itunes:image", href=podcast_picture)
    description_tag = out_soup.new_tag("description")
    description_tag.string = podcast_info_dict['description']
    channel_tag.append(title_tag)
    channel_tag.append(image_tag)
    channel_tag.append(description_tag)

    for episode in data['postcastList'] :
        new_episode_tag = out_soup.new_tag("item")
        channel_tag.append(new_episode_tag)
        new_episode_title_tag = out_soup.new_tag("title")
        new_episode_title_tag.string = episode['title']
        new_episode_tag.append(new_episode_title_tag)
        episode_link = episode['podcast_raw_url']
        new_episode_enclosure_tag = out_soup.new_tag("enclosure",url=episode_link)
        new_episode_tag.append(new_episode_enclosure_tag)
    
        new_episode_date = episode['date'][:-8]
        parsed_date = parse(new_episode_date,parserinfo=ItalianParserInfo())
        new_episode_date_tag = out_soup.new_tag("pubDate")
        new_episode_date_tag.string = parsed_date.strftime('%a, %-d %b %Y')
        new_episode_tag.append(new_episode_date_tag)
    return out_soup

with requests.Session() as s :
    headers_login = { 'Cookie':'wordpress_test_cookie=WP Cookie check' }
    login_data={
        'log':username, 'pwd':password, 'wp-submit':'Log In',
        'redirect_to':base_url, 'testcookie':'1'
    }
    s.post(wp_login, headers=headers_login, data=login_data)
    target_podcasts = podcast_ids.keys() if args.download_all else args.podcast
    for current_podcast in target_podcasts:
        podcast_home = base_url + 'podcasts/' + current_podcast
        headers_ajax = {'User-Agent' : 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/113.0', 'Accept' : 'application/json, text/javascript, */*; q=0.01', 'Accept-Language' : 'en-US,en;q=0.5', 'Accept-Encoding' : 'gzip, deflate, br', 'Content-Type' : 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With' : 'XMLHttpRequest', 'Origin' : base_url, 'Connection' : 'keep-alive', 'Referer' : podcast_home, 'Sec-Fetch-Dest' : 'empty', 'Sec-Fetch-Mode' : 'cors', 'Sec-Fetch-Site' : 'same-origin', 'TE' : 'trailers'}
        data_ajax = {'action':'checkpodcast','cookie':'wordpress_logged_in_5750c61ce9761193028d298b19b5c708','post_id':0, 'podcast_id':podcast_ids[current_podcast]}
        resp = s.post(wp_ajax, headers=headers_ajax, data=data_ajax)
        out_feed = build_feed(current_podcast, resp.json()['data'])
        with open(current_podcast + '.xml', 'w') as out_file:
            out_file.write(out_feed.prettify())