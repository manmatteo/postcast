import requests
import argparse
import json
import re
from typing import TypedDict, Optional, Any
from bs4 import BeautifulSoup
from bs4 import CData
from bs4.element import Tag
from dateutil.parser import parse, parserinfo
from datetime import datetime
from email.utils import format_datetime
import dataclasses
import os
from logging import getLogger, basicConfig

logger = getLogger(__name__)
basicConfig(level='INFO')

base_url = 'https://www.ilpost.it/'
# Type definitions
class PodcastInfoDict(TypedDict):
    title: str
    author: str
    id: int
    access_level: int
    image: str
    description: str

class EpisodeData(TypedDict):
    title: str
    url: str
    date: str
    minutes: int
    content_html: str
    podcast_raw_url: str
    episode_raw_url: str
    id: int
    podcast_id: int
    image: str

class PodcastParent(TypedDict):
    slug: str
    title: str
    author: str
    id: int
    access_level: int
    image: str
    description: str

class PodcastPageItem(TypedDict):
    parent: PodcastParent
    title: str
    url: str
    date: str
    minutes: int
    content_html: str
    episode_raw_url: str
    id: int
    image: str

class EpisodeContent(TypedDict, total=False):
    content_html: str

class PodcastListData(TypedDict):
    postcastList: list[EpisodeData]
    msg: str

def parse_italian_date(date_str: str) -> datetime:
    """Parse date strings with Italian month names (e.g., '31 gen 2026')"""
    months: dict[str, str] = {
        'gen': 'Jan', 'feb': 'Feb', 'mar': 'Mar', 'apr': 'Apr', 'mag': 'May', 'giu': 'Jun',
        'lug': 'Jul', 'ago': 'Aug', 'set': 'Sep', 'ott': 'Oct', 'nov': 'Nov', 'dic': 'Dec'
    }
    match = re.search(r'\b([a-z]{3})\b', date_str, re.IGNORECASE)
    if match:
        ita = match.group(1).lower()
        if ita in months:
            date_str = re.sub(r'\b' + ita + r'\b', months[ita], date_str, flags=re.IGNORECASE)
    result = parse(date_str)
    if isinstance(result, datetime):
        return result
    raise ValueError(f"Could not parse date: {date_str}")

@dataclasses.dataclass
class Episode:
    title: str
    url: str
    date: datetime
    minutes: int
    content_html: str
    podcast_raw_url: str
    id: int
    podcast_id: int
    image: str
    
    def get_tag(self) -> Tag:
        out_soup = BeautifulSoup("", 'xml')
        item_tag = out_soup.new_tag("item")
        out_soup.append(item_tag)
        title_tag = out_soup.new_tag("title")
        title_tag.string = self.title
        item_tag.append(title_tag)
        item_tag.append(out_soup.new_tag("enclosure", url=self.podcast_raw_url,
                                         type="audio/mpeg", length=self.minutes*60))
        link_tag = out_soup.new_tag("link")
        link_tag.string = self.url
        item_tag.append(link_tag)
        pubdate_tag = out_soup.new_tag("pubDate")
        pubdate_tag.string = format_datetime(self.date)
        item_tag.append(pubdate_tag)
        duration_tag = out_soup.new_tag("itunes:duration")
        duration_tag.string = str(self.minutes*60)
        item_tag.append(duration_tag)
        description_tag = out_soup.new_tag("description")
        description_tag.string = self.content_html
        item_tag.append(description_tag)
        postcast_id_tag = out_soup.new_tag(name="guid", isPermaLink="false")
        postcast_id_tag.string = str(self.id)
        item_tag.append(postcast_id_tag)
        return item_tag

class Postcast:
    slug: str
    title: str
    author: str
    id: int
    access_level: int
    image: str
    description: str
    feed: Optional[BeautifulSoup]
    
    def __init__(self, slug: str, podcast_info_dict: PodcastInfoDict) -> None:
        self.slug = slug
        self.title = podcast_info_dict['title']
        self.author = podcast_info_dict['author']
        self.id = podcast_info_dict['id']
        self.access_level = podcast_info_dict['access_level']
        self.image = podcast_info_dict['image']
        self.description = podcast_info_dict['description']
        self.feed = None

    def is_initialized(self) -> bool:
        return self.feed is not None

    def load_existing_feed(self, folder: str = ".") -> None:
        file_name = folder + "/" + self.slug + '.xml'
        with open(file_name, 'r') as in_file:
            self.feed = BeautifulSoup(in_file.read(), 'xml')

    def initialize_feed(self) -> None:
        self.feed = BeautifulSoup("""
                                  <rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
                                  <channel>
                                  <itunes:block>Yes</itunes:block>
                                  </channel>
                                  </rss>""", 'xml')
        if self.feed.rss is None or self.feed.rss.channel is None:
            raise AttributeError("Feed XML structure is invalid: missing <rss> or <channel> tag")
        channel_tag = self.feed.rss.channel
        title_tag = self.feed.new_tag("title")
        title_tag.string = self.title
        author_tag = self.feed.new_tag("itunes:author")
        author_tag.string = self.author
        explicit_tag = self.feed.new_tag("itunes:explicit")
        explicit_tag.string = "false"
        image_tag = self.feed.new_tag("itunes:image", href=self.image)
        description_tag = self.feed.new_tag("description")
        description_tag.string = self.description
        language_tag = self.feed.new_tag("language")
        language_tag.string = "it"
        link_tag = self.feed.new_tag("link")
        link_tag.string = base_url + 'podcasts/' + self.slug
        channel_tag.append(title_tag)
        channel_tag.append(image_tag)
        channel_tag.append(description_tag)
        channel_tag.append(language_tag)
        channel_tag.append(link_tag)
        channel_tag.append(author_tag)
        channel_tag.append(explicit_tag)
    
    def has_episode(self, episode_id: int) -> bool:
        if self.feed is None or self.feed.channel is None:
            raise AttributeError("Feed not loaded or initialized")
        for item in self.feed.channel.find_all('guid'):
            if int(item.string) == episode_id:
                return True
        return False
    
    def add_episode(self, episode: Episode) -> None:
        if self.feed is None or self.feed.channel is None:
            raise AttributeError("Feed not loaded or initialized")
        if self.has_episode(episode.id):
            logger.info(f'Episode {episode.title} of podcast {self.slug} already in feed')
            return
        new_episode_tag = episode.get_tag()
        self.feed.channel.append(new_episode_tag)

def data_of_podcast_page(s: requests.Session) -> list[PodcastPageItem]:
    """
    Get public data from the podcast page. Session doesn't need to be logged in.
    Returns a list containing one dict for each podcast in the sections
    `all_podcasts` and `archivio`.
    """
    response = s.get('https://www.ilpost.it/podcasts/')
    soup = BeautifulSoup(response.text, 'html.parser')
    script = soup.find('script', {'id': '__NEXT_DATA__'})
    if script is None or script.string is None:
        raise ValueError("Could not find podcast data on page")
    data: Any = json.loads(script.string)
    sections: list[dict[str, Any]] = data['props']['pageProps']['data']['data']
    podcast_data_list: list[PodcastPageItem] = []
    for section in sections:
        if section['key'] == 'all_podcasts' or section['key'] == 'archivio':
            podcast_data_list.extend(section['data'])
    return podcast_data_list

def info_dicts_from_podcast_page(data: list[PodcastPageItem]) -> dict[str, PodcastInfoDict]:
    podcast_info_dicts: dict[str, PodcastInfoDict] = {}
    for podcast_item in data:
        podcast = podcast_item['parent']
        podcast_info_dicts[podcast['slug']] = {
            'title': podcast['title'],
            'author': podcast['author'],
            'id': podcast['id'],
            'access_level': podcast['access_level'],
            'image': podcast['image'],
            'description': podcast['description']
        }
    return podcast_info_dicts

def build_feed(session: requests.Session, podcast: Postcast) -> Postcast:
    if not podcast.is_initialized():
        podcast.initialize_feed()
    logger.info(f'Building feed for podcast {podcast.slug}')
    data = get_podcast_data(session, podcast)
    for json_episode in data:
        if 'content_html' in json_episode:
            content_html: str | CData = CData(json_episode['content_html'])
        else:
            content_html = ""
            logger.info(f'No content_html in episode {json_episode["title"]} of podcast {podcast.slug}')
        if json_episode['episode_raw_url'] == '':
            logger.warning(f'No episode_raw_url in episode {json_episode["title"]} of podcast {podcast.slug}')
            continue

        # Normalize the URL (check if CDN URL works, fallback to ilpost.it if needed)
        # Shouldn't be needed anymore
        # normalized_url = normalize_podcast_url(json_episode['episode_raw_url'], logged_session)

        episode = Episode(title=json_episode['title'],
                          url=json_episode['url'],
                          date=parse_italian_date(json_episode['date']),
                          minutes=json_episode['minutes'],
                          content_html=content_html,
                          podcast_raw_url=json_episode['episode_raw_url'],
                          id=json_episode['id'],
                          podcast_id=json_episode['parent']['id'],
                          image=json_episode['image'])
                        #   type=json_episode['type'])
        podcast.add_episode(episode)
    return podcast

def get_podcast_data(session: requests.Session, podcast: Postcast) -> PodcastListData:
    api_url = f'https://api-prod.ilpost.it/podcast/v1/podcast/{podcast.slug}?&pg=1&hits=100'
    podcast_home = base_url + 'podcasts/' + podcast.slug
    headers_api: dict[str, str] = {
        'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/113.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        'X-Requested-With': 'XMLHttpRequest',
        'Origin': base_url,
        'Connection': 'keep-alive',
        'Referer': podcast_home,
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
        'TE': 'trailers'
    }
    resp = session.get(api_url, headers=headers_api)
    if resp.status_code != 200:
        raise Exception(f"API request failed with status code {resp.status_code} for podcast {podcast.slug}")
    data: PodcastListData = resp.json()['data']
    return data

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genera un feed RSS per gli episodi più recenti dei podcast de Il Post")
    parser.add_argument("-f", help="Cartella in cui salvare i file", default=".")
    parser.add_argument("--podcast", nargs='+', default = [])
    parser.add_argument("--download-all") # This actually does nothing. Keeping it for compatibility
    args=parser.parse_args()

    try:
        with requests.Session() as s :
            podcast_page = data_of_podcast_page(s)
            podcast_info_dicts = info_dicts_from_podcast_page(podcast_page)
            if args.podcast != []:
                podcast_info_dicts = {k:v for k,v in podcast_info_dicts.items() if k in args.podcast}
            
            if "audio-articoli" in podcast_info_dicts:
                del podcast_info_dicts["audio-articoli"]
                logger.info('Rimosso podcast "audio-articoli" dalla lista dei podcast da scaricare')

            logger.info(f"Podcast da scaricare: {podcast_info_dicts.keys()}")

            # Process each podcast
            for slug in podcast_info_dicts.keys():
                p = Postcast(slug, podcast_info_dicts[slug])
                build_feed(s, p)
                if not os.path.exists(args.f):
                    os.makedirs(args.f)
                with open(args.f + "/" + p.slug + '.xml', 'w') as out_file:
                    if p.feed is not None:
                        out_file.write(str(p.feed.prettify()))
    except Exception as e:
        logger.error(f"Errore: {e}")
