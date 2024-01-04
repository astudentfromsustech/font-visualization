__all__ = ['Font']


import functools as f
import json
import pathlib as p
import typing as t

from fontTools.misc.fixedTools import ensureVersionIsLong
from fontTools.misc.textTools import num2binary
from fontTools.misc.timeTools import timestampToString
from fontTools.ttLib.ttCollection import TTCollection
from fontTools.ttLib.ttFont import TTFont

from .type import Constant, DictStr, DictStrScale, IntOrNone, Path, Processors, StrOrNone

if t.TYPE_CHECKING:
    from typing_extensions import Self


class Font:
    '''
    - TODO:
        - [v] cmap: character code mapping
        - [v] glyf: glyph outline
        - [v] head: font header
        - [v] hhea: horizontal header
        - [x] hmtx: horizontal metrics
        - [x] loca: glyph location
        - [v] maxp: maximum profile
        - [v] name: name
        - [v] post: glyph name and PostScript compatibility
    '''

    root = p.Path(__file__).absolute().parent

    def __init__(self, font: TTFont) -> None:
        self._font = font

    def __enter__(self) -> 'Self':
        return self

    def __exit__(self, type, value, traceback) -> None:
        self._font.__exit__(type, value, traceback)

    @classmethod
    def from_ttf(cls, path: Path) -> 'Self':
        return cls(TTFont(path))

    @classmethod
    def from_ttc(cls, path: Path) -> t.List['Self']:
        return [cls(font) for font in TTCollection(path).fonts]

    @classmethod
    def from_path(cls, path: Path) -> t.List['Self']:
        try:
            self = cls.from_ttf(path)
        except Exception:
            return cls.from_ttc(path)
        else:
            return [self]

    @f.cached_property
    def constant(self) -> Constant:
        path = self.root / 'constant.json'
        data = json.loads(path.read_text())
        return {
            key: {
                int(k): v
                for k, v in value.items()
            } for key, value in data.items()
        }

    def tables(self) -> DictStr[DictStr]:
        return {
            attr[6:]: getattr(self, attr)()
            for attr in dir(self)
            if attr.startswith('table_')
        }

    def table_head(self) -> DictStrScale:
        processors = [
            (['tableTag'], lambda _: None),
            (['created', 'modified'], self._timestamp2string),
            (['magicNumber', 'checkSumAdjustment'], self._number2hexadecimal),
            (['macStyle', 'flags'], self._number2binary),
        ]
        return self._process(self._font['head'].__dict__.copy(), processors)

    def table_hhea(self) -> DictStrScale:
        processors = [
            (['tableTag'], lambda _: None),
            (['tableVersion'], self._version2hexadecimal),
        ]
        return self._process(self._font['hhea'].__dict__.copy(), processors)

    def table_maxp(self) -> DictStrScale:
        processors = [
            (['tableTag'], lambda _: None),
            (['tableVersion'], hex),
        ]
        return self._process(self._font['maxp'].__dict__.copy(), processors)

    def table_post(self) -> DictStrScale:
        # TODO: mapping, extraNames, data
        processors = [
            (['tableTag'], lambda _: None),
        ]
        return self._process(self._font['post'].__dict__.copy(), processors)

    def table_cmap(self) -> t.List[DictStr]:
        ans = []
        for table in self._font['cmap'].tables:
            platform, encoding, language = self._info(table.platformID, table.platEncID, table.language)
            ans.append({
                'format': table.format,
                'platformID': table.platformID,
                'platform': platform,
                'platEncID': table.platEncID,
                'platEnc': encoding,
                'langID': table.language,
                'lang': language,
                'cmap': table.cmap,  # t.Dict[int, str]
            })
        return ans

    def table_glyf(self) -> DictStr[t.Optional[int]]:
        ans = {}
        try:
            glyf = self._font['glyf']
        except KeyError:
            for name in self._font.getGlyphOrder():
                ans[name] = None
        else:
            for name in glyf.glyphOrder:
                ans[name] = glyf[name].numberOfContours
        return {'numberOfContours': ans}

    def table_name(self) -> t.List[DictStr]:
        ans, tmp = [], {}
        for name in self._font['name'].names:
            key = name.langID, name.platEncID, name.platformID
            tmp \
                .setdefault(key, {}) \
                .setdefault(self._name(name.nameID), name.toUnicode())
        for (langID, platEncID, platformID), data in tmp.items():
            platform, encoding, language = self._info(platformID, platEncID, langID)
            ans.append({
                'platformID': platformID,
                'platform': platform,
                'platEncID': platEncID,
                'platEnc': encoding,
                'langID': langID,
                'lang': language,
                'unicode': data,
            })
        return ans

    def _process(self, data: DictStrScale, processors: Processors) -> DictStrScale:
        for keys, func in processors:
            for key in keys:
                if key in keys:
                    value = func(data.pop(key))
                    if value is not None:
                        data[key] = value
        return data

    def _info(
        self,
        platform_id: IntOrNone = None,
        encoding_id: IntOrNone = None,
        language_id: IntOrNone = None,
    ) -> t.Tuple[StrOrNone, StrOrNone, StrOrNone]:
        platform = self.constant['PLATFORM'].get(platform_id, None)
        encoding = self.constant \
            .get(f'{platform}_ENCODING_ID', {}) \
            .get(encoding_id, None)
        language = self.constant \
            .get(f'{platform}_LANGUAGE_ID', {}) \
            .get(language_id, None)
        return platform, encoding, language

    def _name(self, name_id: IntOrNone = None) -> StrOrNone:
        return self.constant['NAME_ID'].get(name_id, None)

    def _timestamp2string(self, value: int) -> str:
        return timestampToString(value)

    def _number2hexadecimal(self, value: int) -> str:
        if value < 0:
            value += 0x100000000
        ans = hex(value)
        return ans[:-1] if ans[-1:] == "L" else ans

    def _number2binary(self, value: int) -> str:
        return num2binary(value, bits=16)

    def _version2hexadecimal(self, value: int) -> str:
        return '0x%08x' % ensureVersionIsLong(value)
