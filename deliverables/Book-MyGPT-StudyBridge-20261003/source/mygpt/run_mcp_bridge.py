"""Launch the additive MCP delta against the already pinned mygpt brain source."""
from pathlib import Path
import importlib.util
import os
import sys


def load_overlay():
    here = Path(__file__).resolve().parent
    root = here.parents[2]
    default = root / 'work/mygpt-fusion-snapshot/mygpt-1e766c00d7ccb857d7d5a858e7af776f66b611df/brain'
    source = Path(os.environ.get('MYGPT_SOURCE_ROOT', str(default))).resolve()
    if not (source / 'mygpt_brain/core.py').is_file():
        raise RuntimeError('Set MYGPT_SOURCE_ROOT to the existing mygpt brain directory.')
    sys.path.insert(0, str(source))
    for name in ('book_progress', 'dot_events', 'mcp_bridge_core', 'mcp_bridge_client', 'https_callback', 'mcp_bridge_server'):
        spec = importlib.util.spec_from_file_location('mygpt_brain.' + name, here / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules['mygpt_brain.mcp_bridge_server']


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    load_overlay().main()

