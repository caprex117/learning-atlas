"""Weekly refresh as the existing owner, under the same RLS rules as the app."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from atlas.auth import validate_config
from atlas.catalog import refresh
from atlas.repository import SupabaseRepository

REQUIRED = ('SUPABASE_URL', 'SUPABASE_KEY', 'ATLAS_EMAIL', 'ATLAS_PASSWORD', 'TAVILY_API_KEY', 'GEMINI_API_KEY')


def main():
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        print('Faltan secretos: ' + ', '.join(missing))
        return 1
    client = None
    try:
        config = {'url': os.environ['SUPABASE_URL'], 'key': os.environ['SUPABASE_KEY']}
        validate_config(config)
        from supabase import create_client, ClientOptions
        client = create_client(config['url'], config['key'], options=ClientOptions(persist_session=False, auto_refresh_token=True))
        response = client.auth.sign_in_with_password({'email': os.environ['ATLAS_EMAIL'], 'password': os.environ['ATLAS_PASSWORD']})
        if not response.user or not response.session:
            raise ValueError('No session')
        repo = SupabaseRepository(client, str(response.user.id))
        result = refresh(repo, os.environ['TAVILY_API_KEY'], os.environ['GEMINI_API_KEY'], origin='weekly')
        if 'skipped' in result:
            print('Sin cambios: actualización semanal desactivada o ya realizada en los últimos seis días.')
        else:
            print(f"Catálogo guardado: {result['added']} nuevas, {result['changed']} modificadas, modelo {result['model']}.")
        return 0
    except Exception:
        # Public Actions logs must never contain credentials, user records or raw HTTP exceptions.
        print('No se completó la revisión. Comprueba los secretos, la migración 002 y el historial de Descubrir. Se conserva el catálogo anterior.')
        return 1
    finally:
        if client is not None:
            try:
                client.auth.sign_out({'scope': 'local'})
            except Exception:
                pass


if __name__ == '__main__':
    raise SystemExit(main())
