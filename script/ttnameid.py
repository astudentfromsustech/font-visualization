import ast
import json
import functools as f
import pathlib as p
import re
import typing as t

import requests

if t.TYPE_CHECKING:
    from typing_extensions import Self


class TrueTypeNameID:
    '''
    - Reference:
        - https://github.com/freetype/freetype/blob/master/include/freetype/ttnameid.h
    '''

    root = p.Path(__file__).absolute().parent

    def __init__(self, text: str) -> None:
        self._text = text

    @classmethod
    def from_internet(cls, overwrite: bool = False) -> 'Self':
        path = cls.root / 'ttnameid.h'
        if overwrite or not path.exists():
            url = 'https://github.com/freetype/freetype/raw/master/include/freetype/ttnameid.h'
            path.write_bytes(requests.get(url, timeout=7).content)
        return cls(path.read_text())

    @f.cached_property
    def macros(self) -> t.Dict[str, t.Optional[int]]:
        '''#define XXX YYY'''
        ans = {}
        pattern_comment = re.compile(r'(/\*)([\s\S]+?)(\*/)')
        pattern_newline = re.compile(r'(\\\n)')
        pattern_macro = re.compile(r'(#define)( +)([A-Z\d_]+)( *)([^\n]*)')
        pattern_stream = re.compile(r'(\()(\d+)(L?)( *<< *)(\d+)(\))')
        text = pattern_comment.sub('', pattern_newline.sub('', self._text))
        for _, _, key, _, value in pattern_macro.findall(text):
            ans[key] = value.strip()
        ans.pop('TTNAMEID_H_')
        # str -> Optional[int]
        for key, value in ans.items():
            if not value:
                ans[key] = None
            elif value.isdecimal() or value.startswith('0x'):
                ans[key] = ast.literal_eval(value.rstrip('U'))
            elif '<<' in value:
                _, a, _, _, b, _ = pattern_stream.search(value).groups()
                ans[key] = ast.literal_eval(a) << ast.literal_eval(b)
            elif value.isidentifier():
                ans[key] = ans[value]
            else:
                raise Exception(key, value)
        return ans

    @f.cached_property
    def enums(self) -> t.Dict[str, t.Dict[int, str]]:
        ans = {}
        prefixes = {
            'TT_PLATFORM_': 'PLATFORM',
            'TT_APPLE_ID_': 'APPLE_UNICODE_ENCODING_ID',
            'TT_MAC_ID_': 'MACINTOSH_ENCODING_ID',
            'TT_ISO_ID_': 'ISO_ENCODING_ID',
            'TT_MS_ID_': 'MICROSOFT_ENCODING_ID',
            'TT_ADOBE_ID_': 'ADOBE_ENCODING_ID',
            'TT_MAC_LANGID_': 'MACINTOSH_LANGUAGE_ID',
            'TT_MS_LANGID_': 'MICROSOFT_LANGUAGE_ID',
            'TT_NAME_ID_': 'NAME_ID',
            'TT_UCR_': 'UNICODE_RANGE',
        }
        for macro, number in self.macros.items():
            if number is None:
                continue
            for prefix, key in prefixes.items():
                if macro.startswith(prefix):
                    ans.setdefault(key, {})
                    value = macro[len(prefix):]
                    if number in ans[key]:
                        ans[key][number] += ' | ' + value
                    else:
                        ans[key][number] = value
                    break
            else:
                raise Exception(macro, number)
        return ans

    def save_enums(self, *paths: str) -> 'Self':
        path = self.root / p.Path(*paths)
        path.write_text(json.dumps(self.enums, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    TrueTypeNameID \
        .from_internet(overwrite=False) \
        .save_enums('..', 'util', 'constant.json')
