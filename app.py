import collections as c
import functools as f
import pathlib as p
import shutil
import typing as t

import streamlit as st

import util

from PIL import Image, ImageDraw, ImageFont
from streamlit.runtime.uploaded_file_manager import UploadedFile

if t.TYPE_CHECKING:
    from typing_extensions import Self


AllApps = util.type.DictStr[t.Callable]
Char2Md5 = t.Dict[int, t.Set[str]]
File2Md5 = Md52Info = util.type.DictStr[str]
Files = t.Set[str]
Md5 = str
Md5s = t.Iterable[Md5]
Md52Files = util.type.DictStr[Files]
Meta = util.type.DictStr[t.Any]
Metas = t.Dict[Md5, Meta]
Keywords = t.List[str]
Rank = util.type.DictStr[t.List[bool]]


class App:
    __version__ = '2023.03.07'

    _cache = p.Path('cache')
    _cache.mkdir(parents=True, exist_ok=True)
    _number = 7
    _default_text = '我能吞下玻璃而不伤身体'
    _default_keywords = '华文 行楷 Regular'

    def __init__(self, metas: Metas) -> None:
        self._all = c.OrderedDict([
            (func.__doc__, func) for func in [
                self.list_font, self.preview_font, self.search_font_by_keyword,
                self.search_font_by_character, self.upload_font,
            ]
        ])
        self._metas = metas

    @classmethod
    def load(cls) -> 'Self':
        metas = {}
        for directory in cls._cache.iterdir():
            if directory.is_dir():
                meta = util.json.loads((directory/'meta.json').read_text())
                assert meta['version'] == cls.__version__
                metas[directory.name] = meta
        return cls(metas)

    @property
    def all(self) -> AllApps:
        return self._all

    @f.cached_property
    def char2md5(self) -> Char2Md5:
        # TODO: numberOfContours, Dict[str, Optional[int]]
        ans = {}
        for md5, meta in self._metas.items():
            for table in meta['table']:
                # numbers = table['glyf']['numberOfContours']
                for cmap in table['cmap']:
                    for key in cmap['cmap'].keys():
                        ans \
                            .setdefault(int(key), set()) \
                            .add(md5)
        return ans

    @f.cached_property
    def file2md5(self) -> File2Md5:
        ans = {}
        for md5, meta in self._metas.items():
            for stem in meta['alias']:
                ans[f'{stem}.{meta["type"]} ({md5[:self._number]})'] = md5
        return ans

    @f.cached_property
    def md52files(self) -> Md52Files:
        ans = {}
        for md5, meta in self._metas.items():
            for stem in meta['alias']:
                ans \
                    .setdefault(md5, set()) \
                    .add(f'{stem}.{meta["type"]} ({md5[:self._number]})')
        return ans

    @f.cached_property
    def md52info(self) -> Md52Info:
        ans = {}
        func = lambda table: '\n\n'.join([
            f'## {key}\n```\n{util.json.dumps(table[key])}\n```'
            for key in ['name', 'head', 'hhea', 'maxp', 'post']
        ])
        for md5, meta in self._metas.items():
            ans[md5] = '\n\n\n'.join([
                f'# Font {ith+1}\n{func(table)}\n'
                for ith, table in enumerate(meta['table'])
            ])
        return ans

    def list_font(self) -> None:
        '''List Font Information and Download'''
        options = st.multiselect('Choose a font', self.file2md5.keys(), max_selections=1)
        if options:
            option = options[0]
            md5 = self.file2md5[option]
            path = self._cache / md5 / 'data.bin'
            filename = option[:-self._number-3]
            info = self._list_font_info(md5)
            st.download_button('Download font', data=path.read_bytes(), file_name=filename, on_click=st.balloons)
            if st.checkbox('Raw data', key=option):
                st.json(info, expanded=True)
            else:
                st.markdown(self._list_font_markdown(info))

    def preview_font(self) -> None:
        '''Preview Fonts'''
        options = st.multiselect('Choose fonts', self.file2md5.keys())
        size = st.number_input('Choose font size', min_value=1, max_value=128, value=64, step=1)
        text = st.text_input('Input preview text', self._default_text)
        if options:
            for option in options:
                md5 = self.file2md5[option]
                path = self._cache / md5 / 'data.bin'
                font = ImageFont.truetype(path.as_posix(), size=size)
                _, _, width, height = font.getbbox(text)
                with Image.new(mode='RGBA', size=(width, height)) as image:
                    ImageDraw \
                        .Draw(image) \
                        .text(xy=(0, 0), text=text, fill='#000000', font=font)
                    st.markdown(f'# {option}')
                    st.image(image, use_column_width=False)
                    st.markdown('---')

    def search_font_by_keyword(self) -> None:
        '''Search Fonts by Keywords'''
        keywords = st.text_input('Input keywords', self._default_keywords)
        rank = self._search_font_by_keyword(keywords.split())
        for md5 in sorted(rank.keys(), key=lambda md5: sum(rank[md5]), reverse=True):
            prefix = ''.join(['🟥✅'[i] for i in rank[md5]])
            files = ' | '.join(self._files([md5]))
            with st.expander(f'{prefix} {files}'):
                st.markdown(self.md52info[md5])

    def search_font_by_character(self) -> None:
        '''Search Fonts by Contained Characters'''
        characters = st.text_input('Input characters', self._default_text)
        md5s = self._search_font_by_character(characters)
        st.markdown('\n'.join(
            f'- :green[{file}]'
            for file in sorted(self._files(md5s))
        ))

    def upload_font(self) -> None:
        '''Upload Fonts'''
        files = st.file_uploader('Choose OTF or TTF files', type=['otf', 'ttc', 'ttf'], accept_multiple_files=True)
        for file in files:
            md5 = self._upload_font_save(file)
            if md5 is None:
                st.markdown(f'- {file.name}: :red[Not a TrueType or OpenType font (not enough data)]')
            else:
                st.markdown(f'- {file.name}: :green[{md5}]')

    def _dump(self) -> None:
        for md5, meta in self._metas.items():
            (self._cache/md5/'meta.json').write_text(util.json.dumps(meta))

    def _files(self, md5s: Md5s) -> Files:
        return f.reduce(set.union, map(self.md52files.__getitem__, md5s), set())

    def _list_font_info(self, md5: Md5) -> Meta:
        meta = self._metas[md5]
        func = lambda x: f'{x["platform"]} ▸ {x["platEnc"]} ▸ {x["lang"]}'.upper()
        return {
            'md5': md5,
            'size': meta['size'],
            'type': meta['type'],
            'table': [
                {
                    'name': {
                        func(name): name['unicode']
                        for name in table['name']
                    },
                    'cmap': {
                        func(cmap): len(cmap['cmap'])
                        for cmap in table['cmap']
                    },
                    'glyf': len(table['glyf']['numberOfContours']),
                    'head': table['head'],
                    'hhea': table['hhea'],
                    'maxp': table['maxp'],
                    'post': table['post'],
                } for table in meta['table']
            ],
        }

    def _list_font_markdown(self, info: Meta) -> str:
        func = lambda ith, table: '\n'.join([
            f'- Font {ith}:',
            f'  - Table cmap:',
            *[
                f'    - :green[{key}]: :blue[{value} characters]'
                for key, value in table['cmap'].items()
            ],
            f'  - Table glyf: :green[{table["glyf"]} glyphs]',
            f'  - Table name:',
            *[
                f'  - :green[{key}]:\n'+'\n'.join([
                    f'    - :blue[{k}]: :orange[{v!r}]'
                    for k, v in value.items()
                ])
                for key, value in table['name'].items()
            ],
        ])
        return '\n'.join([
            f'- Type: :green[{info["type"]}]',
            f'- Size: :green[{info["size"]/1048576:.3f} MB]',
            f'- Hash: :green[{info["md5"]}]',
            *[
                func(ith+1, table)
                for ith, table in enumerate(info['table'])
            ],
        ])

    def _search_font_by_keyword(self, keywords: Keywords) -> Rank:
        ans = {}
        for md5, info in self.md52info.items():
            ins = [keyword.lower() in info.lower() for keyword in keywords]
            if sum(ins) > 0:
                ans[md5] = ins
        return ans

    def _search_font_by_character(self, characters: str) -> Md5s:
        if characters:
            return f.reduce(
                set.intersection, [
                    self.char2md5.get(ord(character), set())
                    for character in characters.replace(' ', '')
                ],
            )
        else:
            return set()

    def _upload_font_save(self, file: UploadedFile) -> t.Optional[Md5]:
        src = p.Path(file.name)
        content = file.read()
        md5 = util.hash.md5(content)
        directory = self._cache / md5
        dst = directory / 'data.bin'
        if directory.exists():
            self._metas[md5]['alias'] = sorted({src.stem}.union(self._metas[md5]['alias']))
        else:
            directory.mkdir(parents=False, exist_ok=False)
            dst.write_bytes(content)
            try:
                self._metas[md5] = self._upload_font_meta(src, dst)
            except Exception:
                shutil.rmtree(directory)
                return None
        # post-process
        self._dump()
        for attr in ['char2md5', 'file2md5', 'md52files', 'md52info']:
            getattr(self, attr)
            delattr(self, attr)
        return md5

    def _upload_font_meta(self, src: p.Path, dst: p.Path) -> Meta:
        fonts = util.font.Font.from_path(dst)
        tables = [None] * len(fonts)
        for ith, font in enumerate(fonts):
            with font:
                tables[ith] = font.tables()
        return {
            'alias': [src.stem],
            'size': dst.stat().st_size,  # Byte
            'type': src.suffix.lstrip('.').lower(),
            'version': self.__version__,
            # font tables
            'table': tables,
        }


if __name__ == '__main__':
    st.set_page_config(
        page_title='FontHub',
        page_icon='random',
        layout='centered',
        initial_sidebar_state='auto',
    )

    app = App.load()
    with st.sidebar:
        with st.form('sidebar'):
            name = st.selectbox('Choose an App', app.all.keys())
            st.form_submit_button('Run')
    app.all[name]()
