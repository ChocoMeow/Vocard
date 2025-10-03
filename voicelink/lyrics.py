"""MIT License

Copyright (c) 2023 - present Vocard Development

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import aiohttp
import random
import re
import hmac
import hashlib
import base64
import json
import urllib.parse

from math import floor
from urllib.parse import quote
from abc import ABC, abstractmethod
from importlib import import_module
from datetime import datetime
from typing import Optional, Type

from .config import Config

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
    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        ...

class A_ZLyrics(LyricsPlatform):
    async def get(self, url) -> str:
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url=url, headers={'User-Agent': random.choice(userAgents)})
                if resp.status != 200:
                    return None
                return await resp.text()
        except:
            return ""

    async def get_lyrics(self, title: str, artist: str) -> dict[str, str]:
        link = await self.googleGet(title=title, artist=artist)
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
                return None

            lyrics_parts = re.split(r"(\[[\w\S_ ]+\:])", lyrics)
            lyrics_parts = [item for item in lyrics_parts if item != ""]

            count = len(lyrics_parts)
            if count > 1:
                if (count % 2) != 0:
                    del lyrics_parts[count-1]
                return {lyrics_parts[i].replace("[", "").replace(":]", ""): self.clearText(lyrics_parts[i + 1]) for i in range(0, len(lyrics_parts), 2)}
            return {"default": self.clearText(lyrics_parts[0])}
        except:
            return None

    async def googleGet(self, acc = 0.6, artist='', title='') -> Optional[str]:
        data = artist + ' ' * (title != '' and artist != '') + title
        encoded_data = quote(data.replace(' ', '+'))

        google_page = await self.get('{}{}+site%3Aazlyrics.com'.format('https://duckduckgo.com/html/?q=', encoded_data))

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

    def jaro_distance(self, s1, s2) -> int:
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

    def htmlFindAll(self, page) -> list:
        soup = bs4.BeautifulSoup(page, "html.parser")
        return soup.findAll

    def clearText(self, text: str) -> str:
        if text.startswith("\n\n"):
            text = text.replace("\n\n", "", 1)
            
        return text

class Genius(LyricsPlatform):
    def __init__(self) -> None:
        self.module = import_module("lyricsgenius")
        self.genius = self.module.Genius(Config().genius_token)

    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        song = self.genius.search_song(title=title, artist=artist)
        if not song:
            return None
        
        return {"default": song.lyrics}

class Lyrist(LyricsPlatform):
    def __init__(self):
        self.base_url: str = "https://lyrist.vercel.app/api/"

    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        try:
            request_url = self.base_url + title + "/" + artist
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url=request_url, headers={'User-Agent': random.choice(userAgents)})
                if resp.status != 200:
                    return None
                
                data = await resp.json()
                return {"default": data["lyrics"]}
        except:
            return None

class Lrclib(LyricsPlatform):
    def __init__(self):
        self.base_url: str = "https://lrclib.net/api/"

    async def get(self, url, params: dict = None) -> list[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                resp = await session.get(url=url, headers={'User-Agent': random.choice(userAgents)}, params=params)
                if resp.status != 200:
                    return None
                return await resp.json()
        except:
            return []
        
    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        params = {"q": title}
        result = await self.get(self.base_url + "search", params)
        if result:
            return {"default": result[0].get("plainLyrics", "")}

"""
Strvm/musicxmatch-api: a reverse engineered API wrapper for MusicXMatch  
Copyright (c) 2025 Strvm

Permission is hereby granted, free of charge, to any person obtaining a copy  
of this software and associated documentation files (the "Software"), to deal  
in the Software without restriction, including without limitation the rights  
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell  
copies of the Software, and to permit persons to whom the Software is  
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all  
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR  
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,  
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE  
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER  
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,  
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE  
SOFTWARE.
"""
class MusixMatch(LyricsPlatform):
    def __init__(self):
        self.base_url = "https://www.musixmatch.com/ws/1.1/"
        self.headers = {'User-Agent': random.choice(userAgents)}
        self.secret: Optional[str] = None

    async def search_tracks(self, track_query: str, page: int = 1) -> dict:
        url = f"track.search?app_id=web-desktop-app-v1.0&format=json&q={urllib.parse.quote(track_query)}&f_has_lyrics=true&page_size=5&page={page}"
        return await self.make_request(url)

    async def get_track_lyrics(self, track_id: Optional[str] = None, track_isrc: Optional[str] = None) -> dict:
        if not (track_id or track_isrc):
            raise ValueError("Either track_id or track_isrc must be provided.")
        param = f"track_id={track_id}" if track_id else f"track_isrc={track_isrc}"
        url = f"track.lyrics.get?app_id=web-desktop-app-v1.0&format=json&{param}"
        return await self.make_request(url)

    async def get_latest_app(self):
        url = "https://www.musixmatch.com/search"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers={**self.headers, "Cookie": "mxm_bab=AB"}) as response:
                html_content = await response.text()
                pattern = r'src="([^"]*/_next/static/chunks/pages/_app-[^"]+\.js)"'
                matches = re.findall(pattern, html_content)

                if not matches:
                    raise Exception("_app URL not found in the HTML content.")
                
                return matches[-1]

    async def get_secret(self) -> str:
        async with aiohttp.ClientSession() as session:
            async with session.get(await self.get_latest_app(), headers=self.headers, timeout=5) as response:
                javascript_code = await response.text()

                pattern = r'from\(\s*"(.*?)"\s*\.split'
                match = re.search(pattern, javascript_code)

                if match:
                    encoded_string = match.group(1)
                    reversed_string = encoded_string[::-1]

                    decoded_bytes = base64.b64decode(reversed_string)
                    return decoded_bytes.decode("utf-8")
                else:
                    raise Exception("Encoded string not found in the JavaScript code.")

    async def generate_signature(self, url: str) -> str:
        current_date = datetime.now()
        date_str = f"{current_date.year}{str(current_date.month).zfill(2)}{str(current_date.day).zfill(2)}"
        message = (url + date_str).encode()

        if not self.secret:
            self.secret = await self.get_secret()

        key = self.secret.encode()
        hash_output = hmac.new(key, message, hashlib.sha256).digest()
        signature = (
            "&signature="
            + urllib.parse.quote(base64.b64encode(hash_output).decode())
            + "&signature_protocol=sha256"
        )
        return signature
    
    async def make_request(self, url: str) -> dict:
        url = url.replace("%20", "+").replace(" ", "+")
        url = self.base_url + url
        signed_url = url + await self.generate_signature(url)

        async with aiohttp.ClientSession() as session:
            async with session.get(signed_url, headers=self.headers, timeout=5) as response:
                if response.status != 200:
                    raise Exception(f"HTTP Error: {response.status} for URL: {signed_url}")

                try:
                    text_data = await response.text()
                    return json.loads(text_data)
                except json.JSONDecodeError:
                    raise Exception(f"Failed to parse JSON. Response: {text_data}")

    async def get_lyrics(self, title: str, artist: str) -> Optional[dict[str, str]]:
        results = await self.search_tracks(track_query=f"{artist} {title}" if artist else title)

        track_list = results.get("message", {}).get("body", {}).get("track_list")
        if not track_list:
            return None

        track_id = track_list[0]["track"]["track_id"]
        lyric = await self.get_track_lyrics(track_id=track_id)

        lyrics_body = lyric.get("message", {}).get("body", {}).get("lyrics", {}).get("lyrics_body", "")
        if not lyrics_body:
            return None

        return {"default": lyrics_body}

LYRICS_PLATFORMS: dict[str, Type[LyricsPlatform]] = {
    "a_zlyrics": A_ZLyrics,
    "genius": Genius,
    "lyrist": Lyrist,
    "lrclib": Lrclib,
    "musixmatch": MusixMatch
}