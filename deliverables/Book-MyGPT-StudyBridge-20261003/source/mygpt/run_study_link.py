"""One local process for MCP + real Book polling. Model and dot execution are disabled."""
import argparse
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading

from run_mcp_bridge import load_overlay


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--book-origin')
    source.add_argument('--book-server-file')
    parser.add_argument('--mcp-port', type=int, default=8766)
    parser.add_argument('--state-dir', required=True)
    parser.add_argument('--live-origin')
    parser.add_argument('--allow-https-callback-host', action='append', default=[])
    args = parser.parse_args()
    if not 0 <= args.mcp_port <= 65535:
        parser.error('invalid MCP port')
    server_module = load_overlay()
    spec = importlib.util.spec_from_file_location('mygpt_brain.study_host', Path(__file__).with_name('study_host.py'))
    host_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = host_module
    spec.loader.exec_module(host_module)
    origin = args.book_origin
    if args.book_server_file:
        raw = Path(args.book_server_file).read_bytes()
        if len(raw) > 2048:
            parser.error('Book server metadata exceeds limit')
        metadata = json.loads(raw)
        if not isinstance(metadata, dict) or not isinstance(metadata.get('url'), str):
            parser.error('invalid Book server metadata')
        origin = metadata['url']
    # Validate all credential-bound ports before creating a listener or worker.
    poller = host_module.BookProgressPoller(origin)
    renderer = host_module.LivePresentationPort(args.live_origin, os.environ.get('LIVE_STUDY_TOKEN','')) if args.live_origin else None
    server = server_module.BridgeServer(args.mcp_port,os.environ.get('MCP_BRIDGE_TOKEN'),os.environ.get('MYGPT_INGEST_TOKEN'),args.state_dir,
                                        https_callback_hosts=args.allow_https_callback_host)
    thread = threading.Thread(target=server.serve_forever,kwargs={'poll_interval':0.1},daemon=True)
    thread.start()
    host = host_module.StudyHost(poller=poller,bridge=host_module.LocalMcpBridgeClient(server.origin,os.environ['MYGPT_INGEST_TOKEN']),
                                renderer=renderer,runtime=None,decision_provenance='disabled')
    print(json.dumps({'event':'study_link_listening','mcp_url':server.origin+'/mcp','book_origin':origin,
                      'delivery_mode':server.events.delivery_mode,'model_configured':False,'real_dot_connected':False,
                      'decision_execution':'disabled_until_authentication_and_provider_are_bound'}),flush=True)
    async def serve():
        stop = asyncio.Event()
        task = asyncio.create_task(host.run(stop))
        previous = None
        try:
            while not task.done():
                current = host.status()
                if current != previous:
                    print(json.dumps({'event':'study_link_status',**current},ensure_ascii=False),flush=True)
                    previous = current
                await asyncio.sleep(1)
            await task
        finally:
            stop.set()
            await task
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    main()

