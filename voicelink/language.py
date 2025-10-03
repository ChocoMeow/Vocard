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

import os
import json
import logging

from typing import Optional, Union, List, Dict, Any

from .config import Config
from .mongodb import MongoDBHandler

logger = logging.getLogger("vocard.language")

class LangHandler:
    """
    Static class for handling language and localization strings.
    Preloads all language files at initialization for fast access.
    """

    _langs: dict[str, dict[str, str]] = {}
    _local_langs: dict[str, dict[str, str]] = {}
    _default_lang: str = "EN"

    @classmethod
    def init(
        cls,
        langs_dir: str = Config.WORKING_DIR / "langs",
        local_langs_dir: str = Config.WORKING_DIR / "local_langs"
    ) -> "LangHandler":
        """
        Initialize the language handler by preloading all language files
        from the given directories into memory.

        Args:
            langs_dir (str): Directory containing main language JSON files.
            local_langs_dir (str): Directory containing localization JSON files.

        Returns:
            LangHandler: The class itself with loaded languages.
        """
        targets = [
            (langs_dir, cls._langs, "language"),
            (local_langs_dir, cls._local_langs, "local language"),
        ]

        for directory, storage, label in targets:
            if not os.path.exists(directory):
                logger.warning(f"{label.capitalize()} directory '{directory}' does not exist.")
                continue

            for file in os.listdir(directory):
                if file.endswith(".json"):
                    lang_code = file.split(".")[0].upper()
                    filepath = os.path.join(directory, file)
                    try:
                        with open(filepath, encoding="utf8") as f:
                            storage[lang_code] = cls._flatten_json(json.load(f))
                            logger.info(f"Loaded {label}: {lang_code}")
                    except Exception as e:
                        logger.error(f"Failed to load {label} file '{filepath}': {e}")

        return cls
    
    @classmethod
    def _flatten_json(cls, nested_json: Dict[str, Any], parent_key: str = '', separator: str = '.') -> Dict[str, str]:
        """
        Flatten a nested JSON object into a single-level dictionary with dot-separated keys.
        
        Args:
            nested_json (dict): The nested JSON object to flatten
            parent_key (str): The base key for recursion (used internally)
            separator (str): The separator to use between keys (default: '.')
        
        Returns:
            dict: Flattened dictionary with dot-separated keys
        """
        flattened = {}
        
        for key, value in nested_json.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key
            
            if isinstance(value, dict):
                flattened.update(cls._flatten_json(value, new_key, separator))
            else:
                flattened[new_key] = value
        
        return flattened

    @classmethod
    def _get_lang(cls, lang: str, *keys) -> Optional[Union[list[str], str]]:
        """
        Internal helper to retrieve strings from the preloaded cls._lang cache.

        Args:
            lang (str): Language code (e.g., "EN", "FR").
            *keys: One or more keys to fetch from the language dictionary.

        Returns:
            str | list[str] | None: The requested string(s), or "Not found!" if missing.
        """
        if not lang:
            lang = cls._default_lang
            
        lang = lang.upper()
        if lang not in cls._langs:
            lang = cls._default_lang

        lang_dict = cls._langs.get(lang, {})
        if len(keys) == 1:
            value = lang_dict.get(keys[0], "Not found!")
            return value

        values = [lang_dict.get(key, "Not found!") for key in keys]
        return values

    @classmethod
    async def get_lang(cls, guild_id: int, *keys) -> Optional[Union[list[str], str]]:
        """
        Fetch the language setting for a guild from the database and return
        the requested string(s).

        Args:
            guild_id (int): Guild ID to fetch settings for.
            *keys: One or more keys to fetch from the language dictionary.

        Returns:
            str | list[str] | None: The requested string(s).
        """
        settings = await MongoDBHandler.get_settings(guild_id)
        lang = settings.get("lang", LangHandler._default_lang)
        return cls._get_lang(lang, *keys)

    @classmethod
    def get_all_languages(cls) -> List[str]:
        """
        Get a combined list of all loaded language codes (main + local).

        Returns:
            list[str]: List of all available language codes.
        """
        return cls._langs.keys()