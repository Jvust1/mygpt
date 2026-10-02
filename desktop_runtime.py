"""Local desktop lifetime, single-instance lock and explicit intake configuration."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import webbrowser

VERSION='2026.09.25-rc1'

def resource_root():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))

class InstanceLock:
    def __init__(self,home):
        self.file=(home/'.instance.lock').open('a+b')
        if self.file.seek(0,2)==0:self.file.write(b'0');self.file.flush()
        self.file.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close();raise RuntimeError('同一数据目录已有 mygpt 运行实例。') from None
    def close(self):self.file.close()

def open_app(url):
    if not url.startswith('http://127.0.0.1:'):raise ValueError('只打开本机应用')
    if os.name=='nt':
        for key in ('ProgramFiles(x86)','ProgramFiles','LOCALAPPDATA'):
            root=os.environ.get(key)
            if root:
                exe=Path(root)/'Microsoft/Edge/Application/msedge.exe'
                if exe.is_file():subprocess.Popen([str(exe),'--app='+url,'--no-first-run']);return
    if not webbrowser.open(url):raise RuntimeError('未找到浏览器。请使用控制窗口中的本机地址。')

def main(adapter):
    parser=argparse.ArgumentParser()
    parser.add_argument('--headless',action='store_true');parser.add_argument('--data-dir',type=Path)
    parser.add_argument('--ready-file',type=Path);parser.add_argument('--stop-file',type=Path)
    parser.add_argument('--self-test',type=Path);parser.add_argument('--enable-selection-intake',action='store_true')
    args=parser.parse_args()
    home=args.data_dir or Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'mygptDesktop'
    home=home.resolve();home.mkdir(parents=True,exist_ok=True)
    if args.self_test:
        with tempfile.TemporaryDirectory(prefix='mygpt-native-') as tmp:result=adapter.self_test(Path(tmp),resource_root())
        args.self_test.parent.mkdir(parents=True,exist_ok=True)
        args.self_test.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0 if result['ok'] else 1
    lock=InstanceLock(home);service=None
    try:
        service=adapter.start(home,resource_root(),args.enable_selection_intake)
        if args.headless:
            if args.ready_file:
                args.ready_file.parent.mkdir(parents=True,exist_ok=True)
                args.ready_file.write_text(json.dumps({'url':service.url,'version':VERSION}),encoding='utf-8')
            while not args.stop_file or not args.stop_file.exists():time.sleep(.15)
            return 0
        import tkinter as tk
        from tkinter import ttk,messagebox
        window=tk.Tk();window.title('mygpt · 本机控制窗口');window.geometry('700x400')
        box=ttk.Frame(window,padding=24);box.pack(fill='both',expand=True)
        ttk.Label(box,text=adapter.TITLE,font=('Segoe UI',20)).pack(anchor='w')
        ttk.Label(box,text=adapter.DESCRIPTION,wraplength=640).pack(anchor='w',pady=15)
        address=tk.StringVar(value=service.url);ttk.Entry(box,textvariable=address,state='readonly').pack(fill='x')
        def show():
            try:open_app(service.url)
            except Exception as e:messagebox.showerror('打开失败',str(e))
        ttk.Button(box,text='打开学习工作台',command=show).pack(anchor='w',pady=10)
        intake=tk.BooleanVar(value=args.enable_selection_intake)
        ttk.Checkbutton(box,text='允许本次手动选段接收',variable=intake).pack(anchor='w')
        def apply():
            nonlocal service
            if not messagebox.askokcancel('重新设置本次服务','请先保存网页笔记；旧页面连接和临时选段将清空，已保存笔记保持不变。继续？'):return
            service.close();service=None
            try:
                service=adapter.start(home,resource_root(),intake.get());address.set(service.url);show()
            except Exception as e:messagebox.showerror('启动失败',str(e));window.destroy()
        ttk.Button(box,text='应用选段设置并重新打开',command=apply).pack(anchor='w',pady=8)
        def close():
            if messagebox.askokcancel('退出','请先保存网页中编辑的笔记。确定关闭本机服务？'):window.destroy()
        ttk.Button(box,text='退出',command=close).pack(anchor='w',pady=8)
        ttk.Label(box,text='数据目录：'+str(home)+'\n'+adapter.BOUNDARY,wraplength=640).pack(anchor='w',pady=10)
        window.protocol('WM_DELETE_WINDOW',close);window.after(200,show);window.mainloop();return 0
    finally:
        if service:service.close()
        lock.close()
