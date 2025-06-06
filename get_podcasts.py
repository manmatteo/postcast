import requests
import argparse
import json
from bs4 import BeautifulSoup
from bs4 import CData
from dateutil.parser import parse, parserinfo

base_url = 'https://www.ilpost.it/'


def build_info_dicts(s):
    podcast_info_dicts = {}
    response = s.get('https://www.ilpost.it/podcasts/')
    soup = BeautifulSoup(response.text, 'html.parser')
    script = soup.find('script', {'id': '__NEXT_DATA__'})
    data = script.string
    data = json.loads(data)
    for section in data['props']['pageProps']['pageData']['data']:
        if section['key'] == 'all_podcasts' or section['key'] == 'archivio':
            for podcast in  section['data']:
                podcast = podcast['parent']
                podcast_info_dicts[podcast['slug']] = {
                    'title': podcast['title'],
                    'author': podcast['author'],
                    'id': podcast['id'],
                    'access_level': podcast['access_level'],
                    'image': podcast['image'],
                    'description': podcast['description']
                }
    return podcast_info_dicts

podcast_ids = {'15-anni': 240274, "amare-parole": 233226, 'per-fare-il-post' : 234755, 'morning' : 227474, 'tienimi-bordone' : 227193, 'politics' : 229701, 'podcast-eurovision' : 227496, 'tienimi_morning' : 231758, 'il-podcast-del-post-su-sanremo' : 227196, 'tienimi-parigi' : 237733, 'altre-indagini':236670, 'globo' : 232180, 'ci-vuole-una-scienza' : 230388}

class ItalianParserInfo(parserinfo):
    MONTHS = [('Gen', 'January'), ('Feb', 'February'), ('Mar', 'March'), ('Apr', 'April'), ('Mag', 'May'), ('Giu', 'June'), ('Lug', 'July'), ('Ago', 'August'), ('Set', 'Sett', 'September'), ('Ott', 'October'), ('Nov', 'November'), ('Dic', 'December')]

def build_feed(logged_session, podcast_info_dicts, podcast_name, data):
    """
    data is a dict with keys msg, subscriber, userType, onlySubscriber, postcastList
    postcastList is a list of dict with dict_keys(['content', 'date', 'description', 'free', 'hash', 'id', 'image', 'milliseconds', 'minutes', 'object', 'old_podcast_id', 'old_timestamp', 'podcast', 'podcast_id', 'podcast_raw_url', 'range', 'timestamp', 'title', 'type', 'url']
    the logged_session is used further down to get_episode_content
    """
    podcast_head = '<?xml version="1.0" encoding="UTF-8"?> <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0"> <channel> <itunes:block>yes</itunes:block> <googleplay:block>yes</googleplay:block> </channel> </rss>'
    if data['msg'] != 'OK' :
        raise Exception('Ajax server answered' + data['msg'] + 'on podcast' + podcast_name)
    out_soup = BeautifulSoup(podcast_head, 'xml')
    # podcast_info_dict = data['postcastList'][0]['podcast'] #['author', 'chronological', 'count', 'cyclicality', 'description', 'free', 'gift', 'gift_all', 'id', 'image', 'imageweb', 'object', 'order', 'pushnotification', 'robot', 'title', 'type', 'url']
    podcast_info_dict = podcast_info_dicts[podcast_name]
    channel_tag = out_soup.rss.channel
    title_tag = out_soup.new_tag("title")
    title_tag.string = podcast_info_dict['title']
    author_tag = out_soup.new_tag("itunes:author")
    author_tag.string = podcast_info_dict['author']
    explicit_tag = out_soup.new_tag("itunes:explicit")
    explicit_tag.string = "false"
    podcast_picture = podcast_info_dict['image']
    image_tag = out_soup.new_tag("itunes:image", href=podcast_picture)
    description_tag = out_soup.new_tag("description")
    description_tag.string = podcast_info_dict['description']
    language_tag = out_soup.new_tag("language")
    language_tag.string = "it"
    link_tag = out_soup.new_tag("link")
    link_tag.string = base_url + 'podcasts/' + podcast_name
    channel_tag.append(title_tag)
    channel_tag.append(image_tag)
    channel_tag.append(description_tag)
    channel_tag.append(language_tag)
    channel_tag.append(link_tag)
    channel_tag.append(author_tag)
    channel_tag.append(explicit_tag)

    for episode in data['postcastList'] :
        episode_content = get_episode_content(logged_session, episode['id'])
        new_episode_tag = out_soup.new_tag("item")
        channel_tag.append(new_episode_tag)
        new_episode_title_tag = out_soup.new_tag("title")
        new_episode_title_tag.string = episode['title']
        new_episode_tag.append(new_episode_title_tag)
        new_episode_enclosure_tag = out_soup.new_tag("enclosure",url=episode['podcast_raw_url'], type='audio/mpeg')
        new_episode_tag.append(new_episode_enclosure_tag)
    
        new_episode_date = episode['date'][:-8]
        parsed_date = parse(new_episode_date,parserinfo=ItalianParserInfo())
        new_episode_date_tag = out_soup.new_tag("pubDate")
        new_episode_date_tag.string = parsed_date.strftime('%a, %-d %b %Y')
        new_episode_tag.append(new_episode_date_tag)

        new_episode_link_tag = out_soup.new_tag("link")
        new_episode_link_tag.string = episode['url']
        new_episode_tag.append(new_episode_link_tag)
        new_episode_duration_tag = out_soup.new_tag("itunes:duration")
        new_episode_duration_tag.string = str(episode['minutes']*60)
        new_episode_tag.append(new_episode_duration_tag)
        # Data disappeared from api answer
        # new_episode_description_tag = out_soup.new_tag("description")
        # desc_data = CData(episode['content'])
        # new_episode_description_tag.string = desc_data
        # new_episode_tag.append(new_episode_description_tag)
        ## description is now in content_html of episode content
        if 'content_html' in episode_content :
            new_episode_description_tag = out_soup.new_tag("description")
            new_episode_description_tag.string = CData(episode_content['content_html'])
            new_episode_tag.append(new_episode_description_tag)
        else:
            print('No content_html in episode ' + episode['title'] + ' of podcast ' + podcast_name)
    return out_soup

def wplogin(session, username, password):
    login_url = base_url + 'wp-login.php'
    headers_login = { 'Cookie':'wordpress_test_cookie=WP Cookie check' }
    login_data={
        'log':username, 'pwd':password, 'wp-submit':'Log In',
        'redirect_to':base_url, 'testcookie':'1'
    }
    session.post(login_url, headers=headers_login, data=login_data)
    return session

def get_podcast_data(logged_session, current_podcast) :
    wp_ajax = base_url + 'wp-admin/admin-ajax.php'
    podcast_home = base_url + 'podcasts/' + current_podcast
    headers_ajax = {'User-Agent' : 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/113.0', 'Accept' : 'application/json, text/javascript, */*; q=0.01', 'Accept-Language' : 'en-US,en;q=0.5', 'Accept-Encoding' : 'gzip, deflate, br', 'Content-Type' : 'application/x-www-form-urlencoded; charset=UTF-8', 'X-Requested-With' : 'XMLHttpRequest', 'Origin' : base_url, 'Connection' : 'keep-alive', 'Referer' : podcast_home, 'Sec-Fetch-Dest' : 'empty', 'Sec-Fetch-Mode' : 'cors', 'Sec-Fetch-Site' : 'same-origin', 'TE' : 'trailers'}
    data_ajax = {'action':'checkpodcast', 'post_id':0, 'podcast_id':podcast_ids[current_podcast]}
    resp = logged_session.post(wp_ajax, headers=headers_ajax, data=data_ajax)
    return resp.json()['data']

def get_episode_content(logged_session, episode_id) :
    base_url = 'https://api-prod.ilpost.it/content/v1/contents/the_content?id='
    episode_url = base_url + str(episode_id)
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0',
        'Accept': '*/*',
        'Accept-Language': 'it-IT,it;q=0.8,en-US;q=0.5,en;q=0.3',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Referer': 'https://www.ilpost.it/',
        'Content-Type': 'application/json',
        'apikey': 'r309t30ti309ghj3g3tu39t8390t380',
        'Origin': 'https://www.ilpost.it',
        'DNT': '1',
        'Connection': 'keep-alive',
    }
    resp = logged_session.get(episode_url, headers=headers)
    return resp.json()['data']['the_content']['data']
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera un feed RSS per gli episodi più recenti dei podcast de Il Post")
    parser.add_argument("user")
    parser.add_argument("password")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--podcast", nargs='+', default = [])
    target.add_argument("--download-all", action='store_true')
    args=parser.parse_args()
    
    # TODO: Automatically retrieve public podcast IDs
    username = args.user
    password = args.password

    with requests.Session() as s :
        podcast_info_dicts = build_info_dicts(s)
        logged_session = wplogin(s,username,password)
        target_podcasts = podcast_ids.keys() if args.download_all else args.podcast
        for current_podcast in target_podcasts:
            podcast_data = get_podcast_data(logged_session,current_podcast)
            out_feed = build_feed(logged_session,podcast_info_dicts,current_podcast, podcast_data)
            with open(current_podcast + '.xml', 'w') as out_file:
                out_file.write(out_feed.prettify())
