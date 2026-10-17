"""Windows current-user DPAPI encryption; POSIX relies on private file modes."""
import base64
import ctypes
import os

PREFIX = b"VOICESCOPE-DPAPI-1\n"

def _dpapi(raw, decrypt=False):
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_ = [("size",wintypes.DWORD),("data",ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(raw)
    source=Blob(len(raw),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    output=Blob()
    crypt=ctypes.WinDLL("crypt32",use_last_error=True)
    fn=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    fn.restype=wintypes.BOOL
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(output)):
        raise OSError(ctypes.get_last_error(),"Protection DPAPI indisponible pour ce compte Windows.")
    try:
        return ctypes.string_at(output.data,output.size)
    finally:
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        kernel.LocalFree.argtypes=[ctypes.c_void_p]
        kernel.LocalFree.restype=ctypes.c_void_p
        kernel.LocalFree(output.data)

def protect(raw):
    return PREFIX+base64.b64encode(_dpapi(raw)) if os.name=="nt" else raw

def unprotect(raw):
    if raw.startswith(PREFIX):
        if os.name!="nt":
            raise ValueError("Profils Windows protégés : utiliser l'export JSON sur le compte d'origine.")
        return _dpapi(base64.b64decode(raw[len(PREFIX):],validate=True),decrypt=True)
    return raw  # Backward-compatible legacy JSON, encrypted on the next save.
