__all__ = ['md5']


import hashlib

from .type import Content


def md5(content: Content) -> str:
    if isinstance(content, bytearray):
        string = bytes(content)
    if isinstance(content, bytes):
        string = content
    elif isinstance(content, str):
        string = content.encode()
    else:
        raise NotImplementedError
    return hashlib.md5(string).hexdigest()
