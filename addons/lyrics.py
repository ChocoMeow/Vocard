import aiohttp, random, bs4, re
import function as func

from abc import ABC, abstractmethod
from urllib.parse import quote
from math import floor
from importlib import import_module

userAgents = '''Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2228.0 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/41.0.2227.1 Safari/537.36
Mozilla/5.0 (Macintosh; Intel Mac OS X 10_6_8) AppleWebKit/535.19 (KHTML, like Gecko) Chrome/18.0.1025.11 Safari/535.19
Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.66 Safari/535.11
Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/532.2 (KHTML, like Gecko) Chrome/4.0.221.3 Safari/532.2
Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/532.2 (KHTML, like Gecko) Chrome/4.0.221.0 Safari/532.2
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.220.1 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.6 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.5 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.5 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.4 Safari/532.1
Mozilla/5.0 (X11; U; Linux x86_64; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.3 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.3 Safari/532.1
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/532.1 (KHTML, like Gecko) Chrome/4.0.219.3 Safari/532.1
Mozilla/5.0 (X11; U; Linux i686; en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/3.0.197.0 Safari/532.0
Mozilla/5.0 (X11; U; Linux i686 (x86_64); en-US) AppleWebKit/532.0 (KHTML, like Gecko) Chrome/3.0.197.0 Safari/532.0
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/2.0.172.23 Safari/530.5
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/2.0.172.2 Safari/530.5
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/2.0.172.2 Safari/530.5
Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/530.4 (KHTML, like Gecko) Chrome/2.0.172.0 Safari/530.4
Mozilla/5.0 (Windows; U; Windows NT 5.2; eu) AppleWebKit/530.4 (KHTML, like Gecko) Chrome/2.0.172.0 Safari/530.4
Mozilla/5.0 (Windows; U; Windows NT 5.2; en-US) AppleWebKit/530.4 (KHTML, like Gecko) Chrome/2.0.172.0 Safari/530.4
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/2.0.172.0 Safari/530.5
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.4 (KHTML, like Gecko) Chrome/2.0.171.0 Safari/530.4
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/530.1 (KHTML, like Gecko) Chrome/2.0.170.0 Safari/530.1
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/530.1 (KHTML, like Gecko) Chrome/2.0.169.0 Safari/530.1
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.1 (KHTML, like Gecko) Chrome/2.0.168.0 Safari/530.1
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.1 (KHTML, like Gecko) Chrome/2.0.164.0 Safari/530.1
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.0 (KHTML, like Gecko) Chrome/2.0.162.0 Safari/530.0
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/530.0 (KHTML, like Gecko) Chrome/2.0.160.0 Safari/530.0
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/528.10 (KHTML, like Gecko) Chrome/2.0.157.2 Safari/528.10
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/528.10 (KHTML, like Gecko) Chrome/2.0.157.2 Safari/528.10
Mozilla/5.0 (Windows; U; Windows NT 6.0; en-US) AppleWebKit/528.11 (KHTML, like Gecko) Chrome/2.0.157.0 Safari/528.11
Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/528.9 (KHTML, like Gecko) Chrome/2.0.157.0 Safari/528.9
Mozilla/5.0 (Linux; U; en-US) AppleWebKit/525.13 (KHTML, like Gecko) Chrome/0.2.149.27 Safari/525.13
Mozilla/5.0 (Macintosh; U; Mac OS X 10_6_1; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/ Safari/530.5
Mozilla/5.0 (Macintosh; U; Mac OS X 10_5_7; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/ Safari/530.5
Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_6; en-US) AppleWebKit/530.9 (KHTML, like Gecko) Chrome/ Safari/530.9
Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_6; en-US) AppleWebKit/530.6 (KHTML, like Gecko) Chrome/ Safari/530.6
Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_5_6; en-US) AppleWebKit/530.5 (KHTML, like Gecko) Chrome/ Safari/530.5'''

class LyricsPlatform(ABC):
    @abstractmethod
    async def getLyrics():
        ...

class A_ZLyrics(LyricsPlatform):
    async def get(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url=url, headers={'User-Agent': random.choice(userAgents)})
                if resp.status != 200:
                    return None
                return await resp.text()
        except:
            return ""

    async def getLyrics(self, title: str):
        link = await self.googleGet(title=title)
        if not link:
            return 0

        page = await self.get(link)

        metadata = [elm.text for elm in self.htmlFindAll(page)('b')]
        
        if not metadata:
            return None
        
        try:
            title = ''.join(i for i in metadata[1][1:-1] if i not in r'<>:"/\|?*')

            divs = [i.text for i in self.htmlFindAll(page)('div', {'class': None})]
            
            lyrics = max(divs, key=len).strip()

            if not lyrics:
                return print("Lyrics not found")

            rr = re.split(r"(\[[\w\S_ ]+\:])", lyrics)
            for item in rr: 
                if item == "": 
                    rr.remove(item)

            count = len(rr)
            if count > 1:
                if (count % 2) != 0:
                    del rr[count-1]
                return {rr[i].replace("[", "").replace(":]", ""): self.clearText(rr[i + 1]) for i in range(0, len(rr), 2)}
            return {"default": self.clearText(rr[0])}
        except:
            return None

    async def googleGet(self, acc = 0.6, artist='', title=''):
        data = artist + ' ' * (title != '' and artist != '') + title
        encoded_data = quote(data.replace(' ', '+'))


        google_page = await self.get('{}{}+site%3Aazlyrics.com'.format(
                                        'https://duckduckgo.com/html/?q=', encoded_data))

        try:
            results = re.findall(r'(azlyrics\.com\/lyrics\/[a-z0-9]+\/(\w+).html)', google_page)
        except:
            return None
            
        if len(results):
            jaro_artist = 1.0
            jaro_title = 1.0
            
            if artist:
                jaro_artist = self.jaro_distance(artist.replace(' ', ''), results[0][0])
            if title:
                jaro_title = self.jaro_distance(title.replace(' ', ''), results[0][1])
            
            if jaro_artist >= acc and jaro_title >= acc:
                return 'https://www.' + results[0][0]
            else:
                return None
        return None

    def jaro_distance(self, s1, s2): 
        if (s1 == s2): 
            return 1.0
    
        len1, len2 = len(s1), len(s2)
        max_dist = floor(max(len1, len2) / 2) - 1
        match = 0
        hash_s1, hash_s2 = [0] * len(s1), [0] * len(s2)
    
        for i in range(len1):
            for j in range(max(0, i - max_dist),  
                        min(len2, i + max_dist + 1)):
                if (s1[i] == s2[j] and hash_s2[j] == 0):
                    hash_s1[i], hash_s2[j] = 1, 1
                    match += 1
                    break

        if (match == 0): 
            return 0.0

        t = 0
        point = 0
    
        for i in range(len1): 
            if (hash_s1[i]): 
                while (hash_s2[point] == 0): 
                    point += 1
    
                if (s1[i] != s2[point]): 
                    point += 1
                    t += 1
        t = t//2

        return (match/ len1 + match / len2 + (match - t + 1) / match)/ 3.0

    def htmlFindAll(self, page):
        soup = bs4.BeautifulSoup(page, "html.parser")
        return soup.findAll

    def clearText(self, text: str):
        if text.startswith("\n\n"):
            text = text.replace("\n\n", "", 1)
            
        return text

class Genius(LyricsPlatform):
    def __init__(self) -> None:
        self.module = import_module("lyricsgenius")
        self.genius = self.module.Genius(func.tokens.genius_token)

    async def getLyrics(self, name: str):
        song = self.genius.search_song(title=name)
        if not song:
            return None
        
        return {"default": song.lyrics}

lyricsPlatform: dict[str, LyricsPlatform] = {
    "a_zlyrics": A_ZLyrics,
    "genius": Genius
}