from unittest.mock import MagicMock

import pytest
from streamlit.errors import StreamlitSecretNotFoundError
from streamlit.testing.v1 import AppTest

from app import streamlit_app, ui_auth


class FakeUser(dict):
    def __init__(self, *, token: str | None = "token-one", **kwargs: object) -> None:
        super().__init__(is_logged_in=True, tid="tenant", oid="user-one", name="Ana")
        self.update(kwargs)
        self.tokens = {"access": token} if token else {}

    @property
    def is_logged_in(self) -> bool:
        return bool(self["is_logged_in"])


@pytest.fixture
def ui(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    ui = MagicMock()
    ui.secrets = {
        "auth": {
            "redirect_uri": "http://localhost:8501/oauth2callback",
            "microsoft": {"client_id": "frontend"},
        }
    }
    ui.user = FakeUser()
    ui.session_state = {}
    ui.query_params = {}
    ui.context.url = "http://localhost:8501/"
    ui.button.return_value = False
    monkeypatch.setattr(ui_auth, "st", ui)
    return ui


def test_login_button_starts_microsoft_flow(ui: MagicMock) -> None:
    ui.user = FakeUser(is_logged_in=False)
    ui.button.return_value = True
    assert ui_auth.require_login() is None
    ui.login.assert_called_once_with("microsoft")


def test_login_uses_callback_origin_before_starting_flow(ui: MagicMock) -> None:
    ui.user = FakeUser(is_logged_in=False)
    ui.context.url = "http://127.0.0.1:8501/"

    assert ui_auth.require_login() is None

    ui.button.assert_not_called()
    html = ui.markdown.call_args.args[0]
    assert 'action="http://localhost:8501/"' in html
    assert 'target="_self"' in html
    assert f'name="{ui_auth.LOGIN_REQUEST_PARAM}"' in html


def test_canonical_login_request_redirects_to_microsoft_without_login_screen(
    ui: MagicMock,
) -> None:
    ui.user = FakeUser(is_logged_in=False)
    ui.query_params[ui_auth.LOGIN_REQUEST_PARAM] = "microsoft"

    assert ui_auth.require_login() is None

    ui.login.assert_called_once_with("microsoft")
    ui.title.assert_not_called()
    ui.write.assert_not_called()
    assert ui_auth.LOGIN_REQUEST_PARAM not in ui.query_params


def test_no_configuration_shows_error_and_does_not_login(ui: MagicMock) -> None:
    ui.secrets = {}
    assert ui_auth.require_login() is None
    ui.error.assert_called_once()
    ui.login.assert_not_called()


def test_missing_secrets_file_is_controlled(ui: MagicMock) -> None:
    ui.secrets = MagicMock()
    ui.secrets.__getitem__.side_effect = StreamlitSecretNotFoundError("missing file")
    assert ui_auth.require_login() is None
    ui.error.assert_called_once()


def test_only_returns_access_token_without_displaying_it(ui: MagicMock) -> None:
    assert ui_auth.require_login() == "token-one"
    assert "token-one" not in str(ui.write.call_args_list)
    assert "token-one" not in str(ui.session_state)


def test_authenticated_user_skips_login_screen(ui: MagicMock) -> None:
    assert ui_auth.require_login() == "token-one"
    ui.login.assert_not_called()
    ui.title.assert_not_called()
    assert "Inicia sesión con tu cuenta de Microsoft" not in str(
        ui.write.call_args_list
    )


def test_expired_token_requests_reauthentication(ui: MagicMock) -> None:
    ui.user = FakeUser(token=None)
    ui.button.return_value = True
    assert ui_auth.require_login() is None
    ui.logout.assert_called_once()
    assert ui.session_state == {}


def test_logout_clears_document_state(ui: MagicMock) -> None:
    ui.session_state = {"active_user": ("tenant", "user-one"), "upload_result": "old"}
    ui.button.return_value = True
    assert ui_auth.require_login() is None
    ui.logout.assert_called_once()
    assert ui.session_state == {}


def test_account_switch_clears_old_uploads_and_uses_new_token(ui: MagicMock) -> None:
    assert ui_auth.require_login() == "token-one"
    ui.session_state["upload_result"] = "old"
    ui.user = FakeUser(token="token-two", oid="user-two")
    assert ui_auth.require_login() == "token-two"
    assert "upload_result" not in ui.session_state
    assert ui.session_state["active_user"] == ("tenant", "user-two")


def test_app_does_not_render_upload_until_logged_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ui = MagicMock()
    monkeypatch.setattr(streamlit_app, "st", ui)
    monkeypatch.setattr(streamlit_app, "require_login", lambda: None)
    sidebar = MagicMock()
    monkeypatch.setattr(streamlit_app, "render_sidebar", sidebar)
    streamlit_app.render_app()
    sidebar.assert_not_called()


def test_app_renders_upload_view_after_successful_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ui = MagicMock()
    ui.session_state = {}
    ui.form_submit_button.return_value = False
    ui.file_uploader.return_value = None
    monkeypatch.setattr(streamlit_app, "st", ui)
    monkeypatch.setattr(streamlit_app, "require_login", lambda: "access-token")
    sidebar = MagicMock(return_value="http://api.example")
    monkeypatch.setattr(streamlit_app, "render_sidebar", sidebar)

    streamlit_app.render_app()

    sidebar.assert_called_once_with()
    ui.file_uploader.assert_called_once()
    ui.chat_input.assert_called_once()
    assert ui.chat_input.call_args.kwargs["disabled"] is True


def test_sidebar_uses_configured_api_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ui = MagicMock()
    ui.button.return_value = False
    ui.file_uploader.return_value = None
    settings = MagicMock(api_base_url="https://trusted-api.example")
    monkeypatch.setattr(streamlit_app, "st", ui)
    monkeypatch.setattr(streamlit_app, "get_settings", lambda: settings)
    monkeypatch.setattr(streamlit_app, "fetch_api_health", lambda url: {"version": "1"})
    url = streamlit_app.render_sidebar()
    assert url == "https://trusted-api.example"
    ui.text_input.assert_not_called()
    ui.file_uploader.assert_not_called()


@pytest.fixture
def home_app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setattr(ui_auth.st, "user", FakeUser(is_logged_in=False))
    monkeypatch.setattr(
        streamlit_app,
        "get_settings",
        lambda: MagicMock(api_base_url="http://api.example"),
    )
    monkeypatch.setattr(
        streamlit_app, "fetch_api_health", MagicMock(return_value={"version": "1"})
    )
    app = AppTest.from_string("from app.streamlit_app import render_app\nrender_app()")
    app.secrets = {
        "auth": {
            "redirect_uri": "http://localhost:8501/oauth2callback",
            "microsoft": {"client_id": "frontend"},
        }
    }
    return app


def test_login_return_opens_document_home(
    home_app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    login = MagicMock()
    monkeypatch.setattr(ui_auth.st, "login", login)
    home_app.run()
    assert not home_app.exception
    assert not home_app.file_uploader

    home_app.button[0].click().run()
    login.assert_called_once_with("microsoft")
    assert not home_app.file_uploader

    # El callback OIDC abre una sesión autenticada en la raíz de Streamlit.
    monkeypatch.setattr(ui_auth.st, "user", FakeUser())
    home_app.run()

    assert not home_app.exception
    assert home_app.main.title[0].value == "Asistente de manuales"
    assert home_app.sidebar.subheader[0].value == "Añadir un manual"
    assert len(home_app.sidebar.file_uploader) == 1
    assert not home_app.main.file_uploader
    assert "Iniciar sesión con Microsoft" not in [b.label for b in home_app.button]
    assert home_app.chat_input[0].disabled


def test_login_without_access_token_keeps_document_home_protected(
    home_app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ui_auth.st, "user", FakeUser(token=None))

    home_app.run()

    assert not home_app.exception
    assert not home_app.file_uploader
    assert not home_app.chat_input
    assert "Tu sesión necesita renovarse" in home_app.warning[0].value


def test_document_home_stays_visible_when_api_is_unavailable(
    home_app: AppTest, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ui_auth.st, "user", FakeUser())
    monkeypatch.setattr(
        streamlit_app,
        "fetch_api_health",
        MagicMock(side_effect=streamlit_app.ApiUnavailableError),
    )

    home_app.run()

    assert not home_app.exception
    assert len(home_app.sidebar.file_uploader) == 1
    assert len(home_app.main.chat_message) == 1
    assert home_app.chat_input[0].disabled
    assert home_app.sidebar.error[0].value == "API no disponible"
