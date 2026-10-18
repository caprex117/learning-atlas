import base64
import json
import sys

from .importing import extract_local

if __name__ == "__main__":
    try:
        if sys.platform != "win32":
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        request = json.loads(sys.stdin.read(15 * 1024 * 1024))
        result = extract_local(request["name"], base64.b64decode(request["contents"], validate=True))
    except Exception as exc:
        result = {"error": str(exc) if isinstance(exc, ValueError) else "No se pudo leer el documento."}
    print(json.dumps(result, ensure_ascii=False))
