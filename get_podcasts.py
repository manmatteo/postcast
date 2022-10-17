import requests
import argparse
from bs4 import BeautifulSoup
from dateutil.parser import parse, parserinfo

parser = argparse.ArgumentParser(description="Genera un feed RSS per gli episodi più recenti dei podcast de Il Post")
parser.add_argument("user")
parser.add_argument("password")
parser.add_argument("podcast")
args=parser.parse_args()

wp_login = 'https://www.ilpost.it/wp-login.php'
podcast_home = 'https://www.ilpost.it/podcasts/' + args.podcast
podcast_pages = [podcast_home]
username = args.user
password = args.password
podcast_head = '<?xml version="1.0" encoding="UTF-8"?> <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0"> <channel> </channel> </rss>'

class ItalianParserInfo(parserinfo):
    MONTHS = [('Gen', 'January'), ('Feb', 'February'), ('Mar', 'March'), ('Apr', 'April'), ('Mag', 'May'), ('Giu', 'June'), ('Lug', 'July'), ('Ago', 'August'), ('Set', 'Sett', 'September'), ('Ott', 'October'), ('Nov', 'November'), ('Dic', 'December')]

with requests.Session() as s:
    headers1 = { 'Cookie':'wordpress_test_cookie=WP Cookie check' }
    datas={
        'log':username, 'pwd':password, 'wp-submit':'Log In',
        'redirect_to':podcast_home, 'testcookie':'1'
    }
    s.post(wp_login, headers=headers1, data=datas)
    resp = s.get(podcast_home)
    source_soup = BeautifulSoup(resp.text, 'html.parser')
    out_soup = BeautifulSoup(podcast_head, 'xml')

    channel_tag = out_soup.rss.channel

    for meta_tag in source_soup.find_all('meta'):
        if (meta_tag.get('property') == 'og:title'):
            title_tag = out_soup.new_tag("title")
            title_tag.string = meta_tag.get('content')
        if (meta_tag.get('property') == 'og:image'):
            podcast_picture = meta_tag.get('content')
            image_tag = out_soup.new_tag("itunes:image", href=podcast_picture)
        if (meta_tag.get('property') == 'og:description'):
            description_tag = out_soup.new_tag("description")
            description_tag.string = meta_tag.get('content')

    channel_tag.append(title_tag)
    channel_tag.append(image_tag)
    channel_tag.append(description_tag)

    for podcast_page in podcast_pages:
        resp = s.get(podcast_page)
        source_soup = BeautifulSoup(resp.text, 'html.parser')
        for link in source_soup.find_all('a'):
            if (link.get('class') == ['next', 'page-numbers']):
                podcast_pages.append(link.get('href'))
            if (link.get('class') == ['play'] and link.get("data-title")):
                new_episode_tag = out_soup.new_tag("item")
                channel_tag.append(new_episode_tag)
                new_episode_title_tag = out_soup.new_tag("title")
                new_episode_title_tag.string = link.get('data-title')
                new_episode_tag.append(new_episode_title_tag)
                episode_link = link.get('data-url')
                new_episode_enclosure_tag = out_soup.new_tag("enclosure",url=episode_link)
                new_episode_tag.append(new_episode_enclosure_tag)
    
                new_episode_date = link.get('data-desc')[:-8]
                parsed_date = parse(new_episode_date,parserinfo=ItalianParserInfo())
                new_episode_date_tag = out_soup.new_tag("pubDate")
                new_episode_date_tag.string = parsed_date.strftime('%a, %-d %b %Y')
                new_episode_tag.append(new_episode_date_tag)
    
    print(out_soup.prettify())
