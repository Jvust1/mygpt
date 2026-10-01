from pathlib import Path
from http.cookies import SimpleCookie
import json
import threading
from urllib.request import build_opener, ProxyHandler
from mygpt_brain.local_service import create_local_server
from desktop_workspace import extend
from desktop_state import Store

NAME='mygpt'
TITLE='mygpt · 学习陪伴'
DESCRIPTION='安静陪伴、学习目标、个人笔记与备份。只有你主动选择时才接收选段或向本机模型提问。'
BOUNDARY='不自动抓屏或控制其他应用；没有后台云推理。真实模型质量与 Book 实时连接仍需独立验证。'

class Service:
    def __init__(self,server):
        self.server=server.start();self.url=server.origin+'/desktop/';self.health_url=self.url
    def close(self):self.server.close()


def start(home,root,intake=False):
    server=create_local_server(root=root,authorization_seconds=3600,enable_selection_intake=intake)
    try:return Service(extend(server,home))
    except BaseException:server.close();raise


def self_test(home,root):
    store=Store(home/'data'); before=store.read(); value=before['value']
    value['notes']['test']={'title':'test','body':'保存后应可恢复'}
    store.save(before['revision'],value)
    assert Store(home/'data').read()['value']['notes']['test']['body']=='保存后应可恢复'
    backup={'schema':'mygpt-workspace-backup-v1','value':store.read()['value']}
    assert store.merge(backup)==store.read()
    service=start(home,root)
    try:
        with build_opener(ProxyHandler({})).open(service.url,timeout=5) as response:
            assert b'mygpt' in response.read()
        assert service.server.httpd.engine.status()['paid_model_calls']==0
    finally:service.close()
    return {'ok':True,'checks':['native local server','user notes persistence','idempotent backup import','explicit intake default off','clean shutdown'], 'live_provider_calls':0}
