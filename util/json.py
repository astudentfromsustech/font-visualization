__all__ = ['dumps', 'loads']


import json

from .type import Content, Object


def dumps(obj: Object) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


def loads(content: Content) -> Object:
    return json.loads(content)
