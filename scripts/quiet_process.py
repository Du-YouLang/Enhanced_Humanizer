"""Explicit noninteractive child launches; preserve pipes, errors and timeouts."""
import os
import subprocess


def background_kwargs(kwargs=None):
    values=dict(kwargs or {})
    if os.name!='nt':return values
    flags=values.get('creationflags',0)
    conflict=getattr(subprocess,'CREATE_NEW_CONSOLE',0x10)|getattr(subprocess,'DETACHED_PROCESS',0x8)
    if flags&conflict:raise ValueError('Interactive/detached flags conflict with a background-only launch')
    values['creationflags']=flags|subprocess.CREATE_NO_WINDOW
    startup=values.get('startupinfo') or subprocess.STARTUPINFO()
    startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow=subprocess.SW_HIDE
    values['startupinfo']=startup
    return values


def run(*args,**kwargs):return subprocess.run(*args,**background_kwargs(kwargs))
def check_output(*args,**kwargs):return subprocess.check_output(*args,**background_kwargs(kwargs))
def Popen(*args,**kwargs):return subprocess.Popen(*args,**background_kwargs(kwargs))
