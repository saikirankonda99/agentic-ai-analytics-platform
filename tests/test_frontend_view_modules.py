from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from ui.views.common import ViewServices, cached_dataframe_csv_bytes, cached_json_bytes, latest_items
from ui.views import onboarding, reports, telemetry
from workspace import workspace_memory_fingerprint


class FakeColumn:
    def __init__(self, root):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def button(self, *args, **kwargs):
        self.root.buttons.append((args, kwargs))
        return False


class AttrDict(dict):
    __getattr__ = dict.get

    def __setattr__(self, key, value):
        self[key] = value


class FakeStreamlit:
    def __init__(self):
        self.session_state = AttrDict({
            "workspace_memory": {"onboarding": {"dismissed": False, "completed_steps": []}, "workspace_preferences": {}},
            "result_filter": "",
            "result_sort_column": "",
            "result_sort_ascending": True,
            "streaming_workflow": {"telemetry_events": []},
        })
        self.markdowns = []
        self.downloads = []
        self.buttons = []

    def markdown(self, body, **kwargs):
        self.markdowns.append(body)

    def columns(self, spec, **kwargs):
        count = spec if isinstance(spec, int) else len(spec)
        return [FakeColumn(self) for _ in range(count)]

    def download_button(self, *args, **kwargs):
        self.downloads.append((args, kwargs))

    def button(self, *args, **kwargs):
        self.buttons.append((args, kwargs))
        return False

    def text_input(self, *args, **kwargs):
        return kwargs.get("value", "")

    def selectbox(self, label, options, **kwargs):
        return options[kwargs.get("index", 0)]

    def toggle(self, *args, **kwargs):
        return kwargs.get("value", False)

    def dataframe(self, *args, **kwargs):
        return None

    def caption(self, *args, **kwargs):
        return None


def fake_services() -> ViewServices:
    return ViewServices(
        ensure_schema_semantics=lambda: None,
        persist_workspace_memory=lambda: None,
        persist_workspace_preferences=lambda **kwargs: None,
        build_workspace_report_payload=lambda **kwargs: {
            "question": "Revenue by country",
            "rows": 2,
            "insight": "Revenue is concentrated.",
            "sql": "select * from invoices",
            "trace": [{"step": "planner"}],
        },
        persist_report_view=lambda **kwargs: None,
        run_monitoring_workflow=lambda **kwargs: None,
        run_query=lambda *args, **kwargs: None,
        is_scalar_result=lambda df: False,
        can_render_chart=lambda df: False,
        build_column_options=lambda df: [],
        get_numeric_column_options=lambda df: [],
        current_chart_state=lambda: {},
        build_ai_recommendations=lambda *args, **kwargs: [],
        persist_query_bookmark=lambda **kwargs: None,
        persist_investigation_pin=lambda **kwargs: None,
        persist_investigation_bookmark=lambda **kwargs: None,
        persist_shared_query_bookmark=lambda **kwargs: None,
        persist_shared_report_view=lambda **kwargs: None,
        persist_shared_investigation=lambda **kwargs: None,
        current_timestamp=lambda: "2026-05-23T00:00:00",
    )


def test_onboarding_view_renders_workspace_progress(monkeypatch) -> None:
    fake_st = FakeStreamlit()
    monkeypatch.setattr(onboarding, "st", fake_st)

    onboarding.render_onboarding_workspace_panel(fake_services())

    assert "Workspace Onboarding" in fake_st.markdowns[0]
    assert len(fake_st.buttons) == 4


def test_report_exports_render_download_actions(monkeypatch) -> None:
    fake_st = FakeStreamlit()
    monkeypatch.setattr(reports, "st", fake_st)

    reports.render_report_exports(fake_services(), scope="analytics")

    assert [item[0][0] for item in fake_st.downloads] == ["Executive Summary", "Workflow Trace"]


def test_result_explorer_and_telemetry_exports_render_smoke(monkeypatch) -> None:
    fake_st = FakeStreamlit()
    monkeypatch.setattr(reports, "st", fake_st)
    reports.render_result_explorer(pd.DataFrame({"country": ["USA"], "revenue": [10]}), fake_services())

    telemetry_st = SimpleNamespace(
        session_state={"streaming_workflow": {"telemetry_events": []}},
        columns=lambda count: [FakeColumn(fake_st) for _ in range(count)],
        download_button=fake_st.download_button,
    )
    monkeypatch.setattr(telemetry, "st", telemetry_st)
    telemetry.render_telemetry_exports({"correlation_id": "abc", "latency_ms": 10}, [], fake_services())

    assert any(item[0][0] == "Download Full CSV" for item in fake_st.downloads)
    assert any(item[0][0] == "Export Telemetry JSON" for item in fake_st.downloads)


def test_render_helpers_cache_exports_and_bound_latest_items(monkeypatch) -> None:
    fake_st = FakeStreamlit()
    monkeypatch.setattr("ui.views.common.st", fake_st)

    payload = {"b": 2, "a": 1}
    first_json = cached_json_bytes("unit", payload)
    second_json = cached_json_bytes("unit", {"a": 1, "b": 2})
    first_csv = cached_dataframe_csv_bytes("unit", pd.DataFrame({"country": ["USA"], "revenue": [10]}))
    second_csv = cached_dataframe_csv_bytes("unit", pd.DataFrame({"country": ["USA"], "revenue": [10]}))

    assert first_json is second_json
    assert first_csv is second_csv
    assert [item["id"] for item in latest_items([{"id": 1}, {"id": 2}, {"id": 3}], 2)] == [3, 2]


def test_workspace_memory_fingerprint_ignores_save_timestamp() -> None:
    base = {"workspace_id": "team.user", "query_history": [{"sql": "select 1"}], "updated_at": "first"}
    changed_timestamp = {**base, "updated_at": "second"}

    assert workspace_memory_fingerprint(base) == workspace_memory_fingerprint(changed_timestamp)
