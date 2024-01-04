__all__ = [
    'Constant', 'Content', 'DictStr', 'DictStrScale', 'IntOrNone',
    'Object', 'Path', 'Processor', 'Processors', 'Scale', 'StrOrNone',
]


import pathlib as p
import typing as t


class DictStr:
    def __class_getitem__(cls, Type: type) -> type:
        return t.Dict[str, Type]


Constant = t.Dict[str, t.Dict[int, str]]
Content = t.Union[bytearray, bytes, str]
IntOrNone = t.Optional[int]
Object = t.Any
Path = t.Union[str, p.Path]
Processor = t.Callable[[t.Optional[int]], str]
Scale = t.Union[float, int, str]
StrOrNone = t.Optional[str]

DictStrScale = DictStr[Scale]
Processors = t.List[t.Tuple[t.List[str], Processor]]
