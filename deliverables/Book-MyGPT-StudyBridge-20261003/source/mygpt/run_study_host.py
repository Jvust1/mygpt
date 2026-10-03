"""Start the real local polling host against the existing pinned mygpt runtime."""
import importlib.util
from pathlib import Path
import sys

from run_mcp_bridge import load_overlay


if __name__ == '__main__':
    sys.dont_write_bytecode = True
    load_overlay()
    spec = importlib.util.spec_from_file_location('mygpt_brain.study_host', Path(__file__).with_name('study_host.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.main()

