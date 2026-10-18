"""Clients and tokens are scoped to one Streamlit browser session, never a shared cache."""
import base64
import json
from urllib.parse import urlparse

import streamlit as st

from .repository import SupabaseRepository
from .seed import demo_repository


def configuration():
    try:
        return st.secrets.to_dict()
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return {}


def validate_config(config):
    url, key = config.get("url", ""), config.get("key", "")
    if urlparse(url).scheme != "https" or not urlparse(url).hostname:
        raise ValueError("Configura la URL HTTPS de tu proyecto Supabase.")
    if key.startswith("sb_secret_"):
        raise ValueError("Usa la clave publishable o anon. Nunca service_role ni secret.")
    if key.startswith("eyJ"):
        try:
            payload = key.split(".")[1]
            role = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("role")
        except Exception as exc:
            raise ValueError("La clave de Supabase no tiene un formato válido.") from exc
        if role != "anon":
            raise ValueError("Sólo se admite la clave pública anon o publishable.")
    elif not key.startswith("sb_publishable_"):
        raise ValueError("Configura la clave pública publishable o anon de Supabase.")


def logout():
    client = st.session_state.get("auth_client")
    if client:
        try:
            client.auth.sign_out({"scope": "local"})
        except Exception:
            pass
    for key in list(st.session_state):
        del st.session_state[key]
    st.rerun()


def get_repository():
    if "repository" in st.session_state:
        return st.session_state.repository
    cfg = configuration()
    st.markdown("<div class='eyebrow'>LEARNING ATLAS · TU ESPACIO DE CRECIMIENTO</div>", unsafe_allow_html=True)
    st.title("Lo que aprendes, empieza a conectar.")
    st.write("Tus rutas, certificaciones, práctica y descubrimientos, en un mismo lugar.")
    left, right = st.columns([1.25, 1], gap="large")
    with left, st.container(border=True):
        st.subheader("Entrar a mi espacio")
        if "supabase" in cfg:
            with st.form("signin"):
                email = st.text_input("Correo", key="login_email")
                password = st.text_input("Contraseña", type="password", key="login_password")
                submit = st.form_submit_button("Entrar", type="primary", width="stretch")
            if submit:
                try:
                    validate_config(cfg["supabase"])
                    from supabase import create_client, ClientOptions
                    client = create_client(cfg["supabase"]["url"], cfg["supabase"]["key"],
                                           options=ClientOptions(persist_session=False, auto_refresh_token=True))
                    response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
                    if not response.user or not response.session:
                        raise ValueError("No se pudo iniciar sesión.")
                    repo = SupabaseRepository(client, str(response.user.id))
                    st.session_state.auth_client = client
                    st.session_state.repository = repo
                    st.session_state.pop("login_password", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except Exception:
                    st.error("No se pudo entrar. Comprueba tus credenciales y que la migración de Supabase esté instalada.")
            st.caption("La cuenta se crea en tu proyecto Supabase. Si olvidaste la contraseña, usa la recuperación de tu administrador.")
        else:
            st.info("La app está lista para conectar Supabase. Sigue docs/DEPLOYMENT.md y añade los secretos de tu proyecto.")
    with right, st.container(border=True):
        st.subheader("Explora antes de conectar")
        st.write("Prueba el recorrido con ejemplos de Python, Power BI y redes. Los cambios viven sólo en esta sesión del navegador.")
        if cfg.get("app", {}).get("allow_demo", True):
            if st.button("Explorar demo", type="primary", width="stretch", key="enter_demo"):
                st.session_state.repository = demo_repository()
                st.rerun()
        st.caption("La demo contiene actividad ficticia. Tu cuenta real empieza vacía.")
    st.stop()
