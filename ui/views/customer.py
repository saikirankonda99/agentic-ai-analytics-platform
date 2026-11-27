"""Calm, business-facing presentation for the sales workspace.

These helpers only present supplied results. They never infer AI availability,
invent findings, or execute an analysis.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st


def _html(value: object) -> str:
    return escape("" if value is None else str(value), quote=True)


def render_customer_hero(has_data: bool = False, source_name: str = "", source_rows: int | None = None) -> None:
    """Render the compact introduction and a purely decorative CSS 3D model."""
    description = (
        "Ask a sales question. Get a clear answer you can check against your data."
        if has_data
        else "Bring your sales data. Find the answers that help you decide what to do next."
    )
    faces = '<i class="face front"></i><i class="face back"></i><i class="face left"></i><i class="face right"></i><i class="face top"></i><i class="face bottom"></i>'
    st.markdown(
        '<section class="customer-hero" data-testid="customer-hero">'
        '<div class="customer-hero-copy"><div class="customer-eyebrow">YOUR BUSINESS. A CLEARER PICTURE.</div>'
        '<h1>Your sales,<br><em>made clear.</em></h1>'
        f'<p>{description}</p></div>'
        '<div class="sales-model" aria-hidden="true">'
        '<div class="model-halo"></div><div class="model-card card-back"></div>'
        '<div class="model-card card-front"><div class="model-card-line"></div>'
        '<div class="model-card-line short"></div></div>'
        '<div class="model-stage"><div class="model-platform"></div>'
        f'<div class="model-bar bar-coral">{faces}</div>'
        f'<div class="model-bar bar-plum">{faces}</div>'
        f'<div class="model-bar bar-sage">{faces}</div></div>'
        '<div class="model-orbit"></div><div class="model-spark">✦</div>'
        '<span class="model-label">A little perspective.</span></div></section>',
        unsafe_allow_html=True,
    )


def render_data_source(source_name: str, source_rows: int | None, synthetic: bool = False) -> None:
    count = f" · {source_rows:,} sales rows" if source_rows is not None else ""
    kind = "Sample data" if synthetic else "Your data"
    st.markdown(
        '<div class="customer-data-source">'
        f'<span class="source-dot"></span><strong>{kind}</strong>'
        f'<span>{_html(source_name)}{count}</span></div>',
        unsafe_allow_html=True,
    )


def render_ai_status(available: bool, *, used: bool = False, message: str = "") -> None:
    """Availability means configured; only ``used`` means a model answered."""
    if used:
        label, tone = "AI-assisted answer", "used"
        default = "AI selected relevant findings and suggested checks; the figures were calculated from your data."
    elif available:
        label, tone = "AI assistance available", "available"
        default = "AI can review calculated findings and suggest checks. A live response has not been verified yet."
    else:
        label, tone = "Calculated reports", "offline"
        default = "Sales reports work now. AI is not connected in this session."
    st.markdown(
        f'<div class="customer-ai-status {tone}" role="status">'
        f'<span class="ai-symbol" aria-hidden="true">✦</span><div><strong>{label}</strong>'
        f'<p>{_html(message or default)}</p></div></div>',
        unsafe_allow_html=True,
    )


def render_customer_welcome() -> None:
    st.markdown(
        '<div class="customer-welcome"><span class="customer-kicker">START WITH ONE QUESTION</span>'
        '<h2>What would you like to know about your sales?</h2>'
        '<p>Upload a CSV or try the retail sample. Review the columns once, then explore your sales.</p>'
        '</div>',
        unsafe_allow_html=True,
    )


def customer_chart(df: pd.DataFrame, currency: str = "") -> go.Figure | None:
    """Use the actual result columns; keep decorative 3D out of data charts."""
    if df is None or len(df) < 2:
        return None
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categories = [c for c in df.columns if c not in numeric]
    if not numeric or not categories:
        return None
    x_col, y_col = categories[0], numeric[0]
    label = str(y_col).replace("_", " ").title()
    suffix = f" ({currency})" if currency and "revenue" in str(y_col).lower() else ""
    figure = go.Figure()
    if "month" in str(x_col).lower() or "date" in str(x_col).lower():
        figure.add_trace(go.Scatter(
            x=df[x_col], y=df[y_col], mode="lines+markers",
            line={"color": "#9D4937", "width": 3},
            marker={"color": "#9D4937", "size": 8},
            fill="tozeroy", fillcolor="rgba(196, 101, 74, 0.10)",
            hovertemplate=f"%{{x}}<br>{label}: %{{y:,.2f}}{_html(suffix)}<extra></extra>",
        ))
    else:
        figure.add_trace(go.Bar(
            x=df[x_col], y=df[y_col], marker_color="#995F73",
            marker_line_width=0,
            hovertemplate=f"%{{x}}<br>{label}: %{{y:,.2f}}{_html(suffix)}<extra></extra>",
        ))
    figure.update_layout(
        height=310, margin={"l": 12, "r": 12, "t": 24, "b": 12},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, sans-serif", "color": "#3D2939", "size": 12},
        showlegend=False, hoverlabel={"bgcolor": "#FFF8EE", "font_color": "#3D2939"},
        xaxis_title=None, yaxis_title=label + suffix,
        xaxis={"showgrid": False, "zeroline": False, "tickfont": {"color": "#6B5A63"}},
        yaxis={"gridcolor": "#E9DED4", "zerolinecolor": "#D8C8BD", "tickfont": {"color": "#6B5A63"}},
    )
    return figure


def render_customer_answer(
    question: str,
    df: pd.DataFrame | None,
    insight: str,
    *,
    currency: str = "",
    source_name: str = "",
    source_rows: int | None = None,
    ai_used: bool = False,
    warnings: tuple | list = (),
    chart_key: str = "customer_result",
) -> None:
    if df is None or df.empty:
        return
    st.markdown(
        '<div class="customer-answer-heading"><span class="customer-kicker">YOUR ANSWER</span>'
        f'<h2>{_html(question)}</h2></div>', unsafe_allow_html=True,
    )
    if len(df) == 1:
        columns = st.columns(min(len(df.columns), 3))
        for i, column in enumerate(df.columns):
            value = df.iloc[0][column]
            if isinstance(value, (int, float)) or pd.api.types.is_number(value):
                shown = f"{value:,.2f}" if "revenue" in str(column).lower() else f"{value:,.0f}"
                if currency and "revenue" in str(column).lower():
                    shown += f" {currency}"
            else:
                shown = str(value)
            columns[i % len(columns)].metric(str(column).replace("_", " ").title(), shown)
    if insight:
        st.markdown('<div class="customer-section-label">What this means</div>', unsafe_allow_html=True)
        st.markdown(insight)
    fig = customer_chart(df, currency)
    if fig is not None:
        st.plotly_chart(fig, width="stretch", key=chart_key, config={"displayModeBar": False})
    for warning in warnings:
        st.warning(str(warning))
    with st.expander("See the numbers and how this was calculated", expanded=False):
        st.dataframe(df, width="stretch", hide_index=True)
        if source_name:
            rows = f" · {source_rows:,} source rows" if source_rows is not None else ""
            st.caption(f"Source: {source_name}{rows}.")
        st.caption(
            "AI selected relevant findings and suggested checks. The displayed figures were calculated from the accepted sales data."
            if ai_used else
            "Calculated from the accepted sales data. No AI model was used for this answer."
        )
