"""Native Windows entry point. No automatic package/model installation."""
from pathlib import Path
import os
import sys
import multiprocessing

if __name__=='__main__':
    multiprocessing.freeze_support()
    root=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
    sys.path.insert(0,str(root/'brain'))
    log=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'mygptDesktop'/'boot.log'
    log.parent.mkdir(parents=True,exist_ok=True)
    for name in ('stdout','stderr'):
        if getattr(sys,name) is None:setattr(sys,name,log.open('a',encoding='utf-8',buffering=1))
    if sys.stdin is None:sys.stdin=open(os.devnull,'r')
    try:
        from desktop_runtime import main
        import desktop_adapter
        raise SystemExit(main(desktop_adapter))
    except Exception as error:
        import traceback
        traceback.print_exc();sys.stderr.flush()
        if not any(flag in sys.argv for flag in ('--self-test','--headless')):
            from tkinter import messagebox
            messagebox.showerror('mygpt 无法启动',str(error)+'\n未删除已有数据。请查看 boot.log。')
        raise SystemExit(1)
