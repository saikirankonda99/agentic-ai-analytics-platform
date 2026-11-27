def get_theme_css() -> str:
    return """
    <style>
    :root {
        --bg: #FAF5ED;
        --panel: rgba(255, 249, 240, 0.88);
        --panel-strong: #FFF9F0;
        --panel-soft: #F1E7DB;
        --border: rgba(119, 88, 101, 0.16);
        --text: #3D2939;
        --muted: #71606A;
        --accent: #9D4937;
        --accent-2: #795065;
        --success: #3F6A51;
        --warning: #956217;
        --danger: #A13F42;
        --shadow: 0 24px 80px rgba(75, 42, 58, 0.106);
    }

    html, body, #root { margin: 0; padding: 0; overflow-x: hidden; }
    .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
        background: #FAF5ED !important;
        color: var(--text) !important;
    }
    [data-testid="stMain"], [data-testid="stMainBlockContainer"],
    [data-testid="stVerticalBlock"], [data-testid="stHorizontalBlock"],
    [data-testid="column"], [data-testid="stColumn"], .block-container {
        background: transparent !important;
        color: var(--text);
    }

    .block-container,
    [data-testid="stMainBlockContainer"] {
        padding-top: 0.75rem !important;
        padding-bottom: 2rem !important;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
        max-width: 1200px;
        background: transparent !important;
    }

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 0 !important;
        border: none !important;
    }

    [data-testid="stToolbar"] {
        right: 0.75rem;
        top: 0.75rem;
    }

    [data-testid="stDecoration"] {
        display: none;
    }

    #MainMenu,
    footer,
    header {
        visibility: hidden;
    }

    header[data-testid="stHeader"] *,
    [data-testid="stToolbar"] * {
        color: var(--text) !important;
    }

    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.98), rgba(250, 245, 237, 0.96));
        border-right: 1px solid var(--border);
        padding-top: 0 !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.98), rgba(250, 245, 237, 0.96)) !important;
    }

    [data-testid="stSidebarNav"] {
        padding-top: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"],
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] .stToggle label {
        color: var(--text);
    }

    h1, h2, h3, h4, h5, h6, p, span, label {
        color: var(--text);
    }

    div,
    section,
    article,
    aside {
        border-color: var(--border);
    }

    .dashboard-shell {
        display: flex;
        flex-direction: column;
        gap: 0.72rem;
    }

    .hero-card,
    .enterprise-hero,
    .top-nav-shell,
    .section-card,
    .kpi-card,
    .glass-widget,
    .timeline-card,
    .chat-card,
    .table-card,
    .workspace-shell,
    .workspace-panel {
        background: var(--panel);
        border: 1px solid var(--border);
        box-shadow: var(--shadow);
        backdrop-filter: none;
    }

    .hero-card {
        border-radius: 24px;
        padding: clamp(0.75rem, 1.6vw, 1rem) clamp(0.9rem, 2vw, 1.25rem);
        background:
            linear-gradient(135deg, rgba(196, 101, 74, 0.18), rgba(255, 249, 240, 0.92) 45%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.92), rgba(250, 245, 237, 0.94));
    }

    .enterprise-hero {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        align-items: start;
        gap: 0.35rem;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        background:
            linear-gradient(135deg, rgba(196, 101, 74, 0.16), rgba(255, 249, 240, 0.94) 44%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.94), rgba(250, 245, 237, 0.96));
    }

    .enterprise-hero > div {
        min-width: 0;
    }

    .top-nav-shell {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 1rem;
        border-radius: 8px;
        padding: 0.72rem 0.9rem;
        margin-top: 0.35rem;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(250, 245, 237, 0.94));
    }

    .top-nav-title {
        color: #3D2939;
        font-size: 0.98rem;
        font-weight: 700;
    }

    .top-nav-subtitle {
        color: var(--muted);
        font-size: 0.84rem;
        margin-top: 0.16rem;
    }

    [data-testid="stRadio"] div[role="radiogroup"] {
        gap: 0.45rem;
    }

    [data-testid="stRadio"] label {
        min-height: 36px;
        border-radius: 8px;
        padding: 0.42rem 0.65rem;
        border: 1px solid rgba(119, 88, 101, 0.12);
        background: rgba(119, 88, 101, 0.05);
    }

    .hero-eyebrow {
        font-size: 0.8rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.55rem;
    }

    .enterprise-hero h1.hero-title {
        font-size: clamp(1.25rem, 2vw, 1.7rem);
        font-weight: 700;
        line-height: 1.2;
        margin: 0;
        padding: 0;
        max-width: none;
    }

    .enterprise-hero p.hero-copy {
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.45;
        margin: 0.35rem 0 0;
        padding: 0;
        max-width: none;
    }

    .hero-badges {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        margin-top: 0.65rem;
    }

    .hero-badge {
        padding: 0.45rem 0.8rem;
        border-radius: 8px;
        background: rgba(119, 88, 101, 0.08);
        border: 1px solid rgba(119, 88, 101, 0.12);
        color: #604B59;
        font-size: 0.85rem;
    }

    .section-card,
    .chat-card,
    .table-card {
        border-radius: 22px;
        padding: 0.78rem 0.9rem;
    }

    .workspace-shell {
        border-radius: 26px;
        padding: 0.66rem 0.82rem;
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.94), rgba(250, 245, 237, 0.96));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .workspace-panel {
        border-radius: 22px;
        padding: 0.68rem 0.82rem;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(250, 245, 237, 0.92));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .compact-shell {
        margin-bottom: 0.25rem;
    }

    .workspace-shell:hover,
    .workspace-panel:hover,
    .workspace-module:hover,
    .glass-widget:hover,
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(157, 73, 55, 0.22);
        box-shadow: 0 26px 60px rgba(75, 42, 58, 0.095);
    }

    .compact-card {
        padding-bottom: 0.72rem;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.2rem;
    }

    .section-subtitle {
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 0.62rem;
    }

    .kpi-card {
        border-radius: 20px;
        padding: 0.84rem 0.94rem;
        min-height: 92px;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.95), rgba(255, 249, 240, 0.92));
    }

    .kpi-label {
        color: var(--muted);
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.55rem;
    }

    .kpi-value {
        font-size: clamp(1.7rem, 3vw, 2.35rem);
        font-weight: 700;
        line-height: 1;
        margin-bottom: 0.55rem;
    }

    .kpi-delta {
        color: #604B59;
        font-size: 0.88rem;
    }

    .glass-widget {
        border-radius: 22px;
        padding: 0.84rem 0.94rem;
        min-height: 104px;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.74), rgba(255, 249, 240, 0.58));
        position: relative;
        overflow: hidden;
    }

    .glass-widget::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(157, 73, 55, 0.1), transparent 48%);
        pointer-events: none;
        z-index: 0;
    }

    .glass-widget-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.75rem;
        margin-bottom: 0.8rem;
        position: relative;
        z-index: 1;
    }

    .glass-widget-label {
        color: var(--muted);
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    .glass-widget-value {
        position: relative;
        z-index: 1;
        font-size: 1.25rem;
        line-height: 1.25;
        font-weight: 650;
        margin-bottom: 0.45rem;
        color: #3D2939;
        word-break: break-word;
    }

    .glass-widget-copy {
        position: relative;
        z-index: 1;
        color: #71606A;
        font-size: 0.85rem;
        line-height: 1.45;
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.28rem 0.7rem;
        font-size: 0.78rem;
        border: 1px solid rgba(119, 88, 101, 0.16);
        background: rgba(119, 88, 101, 0.08);
    }

    .sidebar-brand {
        padding: 0 0 1rem;
    }

    .sidebar-brand-title {
        font-weight: 700;
        font-size: 1.15rem;
        margin: 0;
    }

    .sidebar-brand-copy {
        color: var(--muted);
        font-size: 0.85rem;
        margin-top: 0.35rem;
    }

    .sample-query {
        padding: 0.7rem 0.85rem;
        border-radius: 14px;
        background: rgba(119, 88, 101, 0.06);
        border: 1px solid rgba(119, 88, 101, 0.1);
        color: #604B59;
        font-size: 0.87rem;
        margin-bottom: 0.55rem;
    }

    .timeline-card {
        border-radius: 20px;
        padding: 0.85rem 1rem;
        min-height: 0;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(255, 249, 240, 0.84));
    }

    .timeline-step {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
        margin-bottom: 0.4rem;
    }

    .timeline-status {
        font-size: 1rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
    }

    .timeline-detail {
        color: #604B59;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .workflow-empty {
        color: var(--muted);
        padding: 0.55rem 0;
    }

    .orchestration-badge-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.58rem;
        margin-bottom: 0.35rem;
    }

    .orchestration-badge {
        min-height: 118px;
        border-radius: 8px;
        padding: 0.72rem 0.82rem;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.86), rgba(250, 245, 237, 0.92));
        border: 1px solid rgba(119, 88, 101, 0.13);
        box-shadow: var(--shadow);
    }

    .orchestration-badge-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.55rem;
        margin-bottom: 0.58rem;
    }

    .orchestration-badge-label {
        color: var(--muted);
        font-size: 0.74rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    .orchestration-badge-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--status-color);
        box-shadow: 0 0 0 5px color-mix(in srgb, var(--status-color) 12%, transparent);
        flex: 0 0 auto;
    }

    .orchestration-badge-value {
        color: #3D2939;
        font-size: 1.15rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.4rem;
        word-break: break-word;
    }

    .orchestration-badge-caption {
        color: #71606A;
        font-size: 0.8rem;
        line-height: 1.45;
    }

    .workflow-timeline-card-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.52rem;
    }

    .workflow-timeline-card {
        display: grid;
        grid-template-columns: 12px minmax(0, 1fr) auto;
        gap: 0.58rem;
        align-items: start;
        min-height: 124px;
        border-radius: 8px;
        padding: 0.66rem 0.7rem;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
    }

    .timeline-card-active {
        border-color: rgba(157, 73, 55, 0.28);
        box-shadow: 0 0 20px rgba(157, 73, 55, 0.1);
    }

    .workflow-timeline-card-marker {
        width: 10px;
        height: 10px;
        margin-top: 0.22rem;
        border-radius: 999px;
        background: var(--status-color);
        box-shadow: 0 0 0 5px color-mix(in srgb, var(--status-color) 12%, transparent);
    }

    .workflow-timeline-card-copy {
        min-width: 0;
    }

    .workflow-timeline-card-title {
        color: #3D2939;
        font-size: 0.9rem;
        font-weight: 650;
        line-height: 1.2;
    }

    .workflow-timeline-card-caption {
        color: var(--muted);
        font-size: 0.72rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-top: 0.18rem;
    }

    .workflow-timeline-card-detail {
        color: #604B59;
        font-size: 0.8rem;
        line-height: 1.42;
        margin-top: 0.48rem;
    }

    .workflow-timeline-card-status {
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        white-space: nowrap;
    }

    .agent-monitor-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.54rem;
    }

    .agent-monitor-panel {
        min-height: 136px;
        border-radius: 8px;
        padding: 0.7rem 0.78rem;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
    }

    .agent-monitor-active {
        border-color: rgba(157, 73, 55, 0.3);
        box-shadow: 0 0 22px rgba(157, 73, 55, 0.12);
    }

    .agent-monitor-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.7rem;
        margin-bottom: 0.55rem;
    }

    .agent-monitor-name {
        color: #3D2939;
        font-size: 0.92rem;
        font-weight: 700;
        line-height: 1.25;
    }

    .agent-monitor-step {
        color: var(--muted);
        font-size: 0.72rem;
        margin-top: 0.18rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .agent-monitor-status {
        display: inline-flex;
        align-items: center;
        border-radius: 8px;
        padding: 0.24rem 0.48rem;
        color: var(--status-color);
        border: 1px solid color-mix(in srgb, var(--status-color) 26%, transparent);
        background: color-mix(in srgb, var(--status-color) 8%, transparent);
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        white-space: nowrap;
    }

    .agent-monitor-caption {
        color: #604B59;
        font-size: 0.82rem;
        line-height: 1.45;
        min-height: 46px;
    }

    .agent-monitor-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.42rem;
        margin-top: 0.6rem;
    }

    .agent-monitor-meta span {
        border-radius: 8px;
        padding: 0.24rem 0.48rem;
        color: #604B59;
        background: rgba(119, 88, 101, 0.08);
        border: 1px solid rgba(119, 88, 101, 0.12);
        font-size: 0.72rem;
    }

    .workflow-rail-shell {
        overflow-x: auto;
        padding-bottom: 0.12rem;
        margin-bottom: 0.25rem;
    }

    .workflow-rail {
        display: flex;
        align-items: stretch;
        gap: 0;
        min-width: 1180px;
    }

    .workflow-node-wrap {
        display: flex;
        align-items: center;
        flex: 1 0 0;
        min-width: 160px;
    }

    .workflow-node {
        position: relative;
        flex: 1 1 auto;
        min-height: 164px;
        padding: 0.82rem 0.9rem;
        border-radius: 22px;
        border: 1px solid rgba(119, 88, 101, 0.14);
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.88), rgba(250, 245, 237, 0.92));
        box-shadow: var(--shadow);
        backdrop-filter: none;
        overflow: hidden;
    }

    .workflow-node::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(157, 73, 55, 0.08), transparent 45%);
        pointer-events: none;
        z-index: 0;
    }

    .workflow-node-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.65rem;
        position: relative;
        z-index: 1;
    }

    .workflow-node-title {
        font-size: 0.96rem;
        font-weight: 650;
        color: #3D2939;
        line-height: 1.2;
    }

    .workflow-node-caption {
        margin-top: 0.2rem;
        color: var(--muted);
        font-size: 0.77rem;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }

    .workflow-status-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        background: var(--status-color);
        box-shadow: 0 0 0 6px color-mix(in srgb, var(--status-color) 14%, transparent);
        flex: 0 0 auto;
        margin-top: 0.12rem;
    }

    .workflow-node-status {
        position: relative;
        z-index: 1;
        font-size: 0.88rem;
        font-weight: 650;
        margin-bottom: 0.45rem;
        transition: color 180ms ease, opacity 180ms ease;
    }

    .workflow-node-detail {
        position: relative;
        z-index: 1;
        color: #604B59;
        font-size: 0.85rem;
        line-height: 1.45;
        min-height: 48px;
    }

    .workflow-node-metadata {
        position: relative;
        z-index: 1;
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.62rem;
    }

    .workflow-node-metadata span {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.28rem 0.55rem;
        font-size: 0.73rem;
        color: #604B59;
        background: rgba(119, 88, 101, 0.08);
        border: 1px solid rgba(119, 88, 101, 0.12);
    }

    .workflow-connector {
        width: 42px;
        height: 2px;
        margin: 0 0.3rem;
        background: linear-gradient(90deg, rgba(157, 73, 55, 0.18), rgba(119, 88, 101, 0.26));
        position: relative;
        opacity: 0.9;
        pointer-events: none;
    }

    .workflow-connector::after {
        content: "";
        position: absolute;
        right: -1px;
        top: -3px;
        width: 8px;
        height: 8px;
        border-top: 2px solid rgba(119, 88, 101, 0.28);
        border-right: 2px solid rgba(119, 88, 101, 0.28);
        transform: rotate(45deg);
        pointer-events: none;
    }

    .active-agent {
        animation: activeAgentGlow 2.8s ease-in-out infinite;
        border-color: rgba(157, 73, 55, 0.34);
    }

    .active-agent .workflow-status-dot {
        animation: subtlePulse 2.6s ease-in-out infinite;
    }

    @keyframes activeAgentGlow {
        0% {
            box-shadow: 0 18px 44px rgba(75, 42, 58, 0.095), 0 0 0 0 rgba(157, 73, 55, 0.08);
        }
        50% {
            box-shadow: 0 18px 44px rgba(75, 42, 58, 0.095), 0 0 22px 0 rgba(157, 73, 55, 0.2);
        }
        100% {
            box-shadow: 0 18px 44px rgba(75, 42, 58, 0.095), 0 0 0 0 rgba(157, 73, 55, 0.08);
        }
    }

    .response-card {
        border-radius: 20px;
        padding: 0.82rem 0.94rem;
        margin-bottom: 0.55rem;
        border: 1px solid rgba(119, 88, 101, 0.12);
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
    }

    .assistant-card {
        background:
            linear-gradient(135deg, rgba(157, 73, 55, 0.09), rgba(255, 249, 240, 0.92) 42%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(250, 245, 237, 0.92));
    }

    .user-card {
        background:
            linear-gradient(135deg, rgba(196, 101, 74, 0.12), rgba(255, 249, 240, 0.9) 46%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.94), rgba(250, 245, 237, 0.92));
    }

    .response-meta {
        color: #9D4937;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.55rem;
    }

    .response-content {
        color: #3D2939;
        font-size: 0.95rem;
        line-height: 1.55;
    }

    .workspace-module {
        border-radius: 24px;
        padding: 0.72rem 0.84rem;
        margin-bottom: 0.42rem;
        border: 1px solid rgba(119, 88, 101, 0.14);
        box-shadow: var(--shadow);
        backdrop-filter: none;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(250, 245, 237, 0.94));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
        overflow: hidden;
    }

    .default-module {
        background:
            linear-gradient(135deg, rgba(157, 73, 55, 0.05), rgba(255, 249, 240, 0.9) 38%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.92), rgba(250, 245, 237, 0.96));
    }

    .workspace-module-head {
        margin-bottom: 0.42rem;
    }

    .workspace-module .section-subtitle {
        margin-bottom: 0;
    }

    .workspace-module-body {
        position: relative;
        color: #3D2939;
    }

    .summary-module {
        background:
            linear-gradient(135deg, rgba(157, 73, 55, 0.08), rgba(255, 249, 240, 0.9) 38%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.92), rgba(250, 245, 237, 0.96));
    }

    .recommendation-module {
        background:
            linear-gradient(135deg, rgba(196, 101, 74, 0.1), rgba(255, 249, 240, 0.92) 42%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.9), rgba(250, 245, 237, 0.95));
    }

    .observability-module {
        background:
            linear-gradient(135deg, rgba(63, 106, 81, 0.06), rgba(255, 249, 240, 0.92) 40%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.92), rgba(250, 245, 237, 0.96));
    }

    .insight-module {
        background:
            linear-gradient(135deg, rgba(149, 98, 23, 0.06), rgba(255, 249, 240, 0.92) 40%),
            linear-gradient(180deg, rgba(255, 249, 240, 0.92), rgba(250, 245, 237, 0.96));
    }

    .summary-stat-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.62rem;
        margin-bottom: 0.62rem;
    }

    .summary-stat {
        border-radius: 18px;
        padding: 0.68rem 0.78rem;
        background: rgba(119, 88, 101, 0.06);
        border: 1px solid rgba(119, 88, 101, 0.12);
    }

    .summary-stat-label,
    .observability-label {
        color: var(--muted);
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        margin-bottom: 0.38rem;
    }

    .summary-stat-value,
    .observability-value {
        color: #3D2939;
        font-size: 0.94rem;
        line-height: 1.4;
        word-break: break-word;
    }

    .executive-callout,
    .workspace-body-copy {
        color: #3D2939;
        font-size: 0.92rem;
        line-height: 1.6;
        padding: 0.72rem 0.82rem;
        border-radius: 18px;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
        overflow-wrap: anywhere;
    }

    .workspace-list-item {
        padding: 0.62rem 0.76rem;
        border-radius: 16px;
        margin-bottom: 0.4rem;
        color: #3D2939;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
        line-height: 1.5;
        overflow-wrap: anywhere;
    }

    .workspace-list-item:last-child {
        margin-bottom: 0;
    }

    .onboarding-progress-shell {
        display: grid;
        gap: 0.52rem;
        margin-bottom: 0.62rem;
    }

    .onboarding-progress-track {
        height: 8px;
        border-radius: 999px;
        overflow: hidden;
        background: rgba(119, 88, 101, 0.1);
        border: 1px solid rgba(119, 88, 101, 0.12);
    }

    .onboarding-progress-track span {
        display: block;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #3F6A51, #9D4937);
    }

    .onboarding-step-grid,
    .quick-action-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.5rem;
    }

    .onboarding-step,
    .quick-action-item {
        min-height: 104px;
        border-radius: 8px;
        padding: 0.66rem 0.72rem;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.11);
    }

    .onboarding-step-done {
        border-color: rgba(63, 106, 81, 0.24);
        background: rgba(63, 106, 81, 0.06);
    }

    .onboarding-step-title,
    .quick-action-label {
        color: #3D2939;
        font-size: 0.9rem;
        font-weight: 700;
        line-height: 1.25;
        margin-bottom: 0.32rem;
    }

    .onboarding-step-copy,
    .quick-action-copy {
        color: #71606A;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .activity-item {
        display: grid;
        grid-template-columns: 14px 1fr auto;
        gap: 0.75rem;
        align-items: start;
        padding: 0.55rem 0;
        border-bottom: 1px solid rgba(119, 88, 101, 0.08);
    }

    .activity-item:last-child {
        border-bottom: none;
        padding-bottom: 0;
    }

    .activity-dot {
        width: 10px;
        height: 10px;
        border-radius: 999px;
        margin-top: 0.28rem;
        box-shadow: 0 0 0 5px rgba(119, 88, 101, 0.08);
    }

    .activity-dot.live {
        background: #9D4937;
        animation: subtlePulse 3s ease-in-out infinite;
    }

    .activity-dot.stable {
        background: #3F6A51;
    }

    .activity-copy {
        min-width: 0;
    }

    .activity-title {
        color: #3D2939;
        font-size: 0.9rem;
        margin-bottom: 0.2rem;
    }

    .activity-subtitle {
        color: #71606A;
        font-size: 0.82rem;
        line-height: 1.45;
    }

    .activity-time {
        color: var(--muted);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding-top: 0.12rem;
    }

    .agent-row {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.55rem;
    }

    .agent-pill {
        border-radius: 18px;
        padding: 0.68rem 0.76rem;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .agent-pill:hover {
        transform: translateY(-2px);
        border-color: rgba(157, 73, 55, 0.2);
    }

    .agent-pill-active {
        border-color: rgba(157, 73, 55, 0.26);
        box-shadow: 0 0 20px rgba(157, 73, 55, 0.12);
    }

    .agent-pill-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.45rem;
    }

    .agent-pill-name {
        color: #3D2939;
        font-size: 0.88rem;
        font-weight: 600;
    }

    .agent-pill-status {
        color: #9D4937;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .agent-pill-copy {
        color: #71606A;
        font-size: 0.8rem;
        line-height: 1.4;
    }

    .log-stream {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }

    .log-line {
        display: grid;
        grid-template-columns: 56px 110px 1fr;
        gap: 0.7rem;
        align-items: start;
        padding: 0.52rem 0.68rem;
        border-radius: 16px;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.08);
    }

    .log-time {
        color: var(--muted);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .log-step {
        color: #9D4937;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .log-message {
        color: #3D2939;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    @keyframes subtlePulse {
        0% { box-shadow: 0 0 0 5px rgba(157, 73, 55, 0.08); }
        50% { box-shadow: 0 0 0 8px rgba(157, 73, 55, 0.14); }
        100% { box-shadow: 0 0 0 5px rgba(157, 73, 55, 0.08); }
    }

    .observability-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.58rem;
    }

    .observability-metric {
        border-radius: 18px;
        padding: 0.56rem 0.68rem;
        background: rgba(119, 88, 101, 0.05);
        border: 1px solid rgba(119, 88, 101, 0.1);
    }

    [data-testid="stForm"] {
        padding: 0.58rem 0.65rem 0.14rem;
        margin-bottom: 0.35rem;
        border-radius: 20px;
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.96), rgba(250, 245, 237, 0.94)) !important;
        border: 1px solid rgba(119, 88, 101, 0.12);
        box-shadow: 0 16px 38px rgba(75, 42, 58, 0.073);
        backdrop-filter: blur(18px);
    }

    .stButton,
    .stDownloadButton,
    [data-testid="stFormSubmitButton"],
    [data-testid="stFileUploader"],
    [data-testid="stRadio"],
    [data-testid="stToggle"],
    [data-testid="stSelectbox"],
    [data-testid="stMultiSelect"],
    [data-testid="stTextInput"],
    [data-testid="stTextArea"],
    [data-testid="stChatInput"] button,
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input,
    div[data-baseweb="select"],
    div[data-baseweb="base-input"],
    div[data-baseweb="input"] {
        position: relative;
        z-index: 36;
        pointer-events: auto;
    }

    div[data-testid="stMetric"] {
        background: transparent;
        border: none;
        padding: 0;
    }

    .stButton > button,
    .stDownloadButton > button,
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"] {
        border-radius: 14px;
        border: 1px solid rgba(157, 73, 55, 0.26);
        background: linear-gradient(135deg, rgba(196, 101, 74, 0.22), rgba(157, 73, 55, 0.12));
        color: var(--text);
        font-weight: 600;
        padding: 0.65rem 0.95rem;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover,
    [data-testid="stFormSubmitButton"] button:hover,
    [data-testid="stFileUploaderDropzone"] button[data-testid="stBaseButton-secondary"]:hover {
        border-color: rgba(157, 73, 55, 0.45);
        color: var(--text);
    }

    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"] > div,
    div[data-baseweb="input"] > div,
    textarea {
        background: rgba(255, 249, 240, 0.85);
        border-radius: 14px;
        border: 1px solid rgba(119, 88, 101, 0.16);
        color: var(--text) !important;
        box-shadow: none !important;
    }

    .stChatMessage {
        background: rgba(255, 249, 240, 0.5);
        border: 1px solid rgba(119, 88, 101, 0.12);
        border-radius: 18px;
        padding: 0.35rem 0.5rem;
    }

    [data-testid="stChatInput"] {
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.92), rgba(250, 245, 237, 0.98)) !important;
        border-top: 1px solid rgba(119, 88, 101, 0.12);
        padding-top: 0.8rem;
        padding-bottom: 0.6rem;
        margin-top: 0 !important;
    }

    [data-testid="stChatInput"] > div {
        background: transparent !important;
        max-width: 1440px;
    }

    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input,
    [data-testid="stChatInput"] div[data-baseweb="textarea"] {
        background: rgba(255, 249, 240, 0.92) !important;
        color: var(--text) !important;
        border: 1px solid rgba(157, 73, 55, 0.18) !important;
        border-radius: 18px !important;
    }

    [data-testid="stChatInput"] button {
        background: linear-gradient(135deg, rgba(196, 101, 74, 0.24), rgba(157, 73, 55, 0.18)) !important;
        color: var(--text) !important;
        border: 1px solid rgba(157, 73, 55, 0.24) !important;
    }

    [data-testid="stChatInput"]::before {
        content: "";
        position: absolute;
        inset: 0;
        background:
            linear-gradient(180deg, rgba(255, 249, 240, 0.1), rgba(250, 245, 237, 0.3));
        pointer-events: none;
        z-index: 0;
    }

    [data-testid="stChatInputContainer"],
    [data-testid="stChatInputContainer"] > div,
    [data-testid="stChatInputContainer"] > div > div,
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        background:
            linear-gradient(180deg, rgba(250, 245, 237, 0.96), rgba(250, 245, 237, 1)) !important;
        color: var(--text) !important;
        margin: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
    }

    [data-testid="stChatMessageContent"],
    [data-testid="stChatMessageContent"] > div,
    [data-testid="stChatMessageContent"] p {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stChatMessageContainer"],
    [data-testid="stChatMessageContainer"] > div,
    [data-testid="stChatMessageContainer"] [data-testid="stVerticalBlock"] {
        background: transparent !important;
    }

    [data-testid="stChatMessageList"],
    [data-testid="stChatMessageList"] > div,
    [data-testid="stChatMessageList"] [data-testid="stVerticalBlock"] {
        background: transparent !important;
        margin-bottom: 0 !important;
    }

    .stDataFrame,
    div[data-testid="stCodeBlock"],
    [data-testid="stTable"] {
        border-radius: 16px;
        overflow: hidden;
        border: 1px solid rgba(119, 88, 101, 0.12);
        background: rgba(255, 249, 240, 0.74) !important;
    }

    [data-testid="stDataFrameResizable"] {
        background: rgba(255, 249, 240, 0.74) !important;
    }

    [data-testid="stDataFrameGlideDataEditor"] {
        background: rgba(255, 249, 240, 0.74) !important;
    }

    [data-testid="stDataFrameGlideDataEditor"] * {
        background-color: rgba(255, 249, 240, 0.82) !important;
        color: var(--text) !important;
    }

    .element-container,
    .stMarkdown,
    .stAlert,
    .stExpander,
    .streamlit-expanderHeader,
    .streamlit-expanderContent,
    [data-testid="stExpander"],
    [data-testid="stExpanderDetails"],
    [data-testid="stVerticalBlock"],
    [data-testid="column"],
    [data-testid="stForm"],
    [data-testid="stFormSubmitButton"],
    [data-testid="stNotification"],
    [data-testid="stStatusWidget"],
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottom"],
    [data-testid="stToolbarActions"] {
        background: transparent !important;
        color: var(--text) !important;
    }

    .element-container {
        margin-bottom: 0.28rem !important;
    }

    [data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }

    [data-testid="stHorizontalBlock"] {
        gap: 0.65rem !important;
    }

    div[data-testid="stDownloadButton"] button {
        min-height: 42px;
    }

    .workspace-module,
    .workflow-timeline-card,
    .agent-monitor-panel,
    .orchestration-badge,
    .observability-metric {
        transition: transform 180ms ease, border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }

    .workflow-timeline-card:hover,
    .agent-monitor-panel:hover,
    .orchestration-badge:hover,
    .observability-metric:hover {
        transform: translateY(-1px);
        border-color: rgba(157, 73, 55, 0.22);
    }

    [data-testid="stAppViewBlockContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewContainer"] section[data-testid="stMain"] {
        background: transparent !important;
    }

    [data-testid="stAlertContainer"] {
        background: rgba(255, 249, 240, 0.86) !important;
        border: 1px solid rgba(119, 88, 101, 0.14) !important;
        color: var(--text) !important;
        border-radius: 16px;
    }

    details {
        background: rgba(255, 249, 240, 0.72) !important;
        border: 1px solid rgba(119, 88, 101, 0.12) !important;
        border-radius: 16px !important;
    }

    details summary,
    details summary * {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stFileUploader"],
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(255, 249, 240, 0.74) !important;
        border: 1px dashed rgba(157, 73, 55, 0.22) !important;
        color: var(--text) !important;
        border-radius: 18px !important;
    }

    [data-testid="stFileUploaderDropzoneInstructions"],
    [data-testid="stFileUploaderDropzoneInstructions"] small {
        color: var(--muted) !important;
    }

    [data-testid="stMetric"],
    [data-testid="stMetric"] > div {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stTabs"],
    [data-testid="stTabs"] > div,
    [data-testid="stSegmentedControl"],
    [data-testid="stPopover"] {
        background: transparent !important;
    }

    iframe {
        background: transparent !important;
    }

    [data-testid="stMarkdownContainer"],
    [data-testid="stMarkdownContainer"] > div,
    [data-testid="stCode"],
    pre,
    code {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stAppViewContainer"] [data-testid="stBlock"],
    [data-testid="stAppViewContainer"] [data-testid="stElementContainer"],
    [data-testid="stAppViewContainer"] [data-testid="stText"],
    [data-testid="stAppViewContainer"] [data-testid="stCaptionContainer"] {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stAppViewContainer"] [data-testid="stBlock"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    .js-plotly-plot,
    .plot-container,
    .plotly,
    .main-svg {
        background: transparent !important;
    }

    input::placeholder,
    textarea::placeholder {
        color: #7C6874 !important;
    }

    .footer-note {
        text-align: center;
        color: var(--muted);
        font-size: 0.84rem;
        padding: 0.4rem 0 0;
    }

    @media (max-width: 992px) {
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.85rem;
            padding-right: 0.85rem;
        }

        .hero-card,
        .section-card,
        .chat-card,
        .table-card {
            padding: 0.78rem;
        }

        .workflow-rail {
            min-width: 980px;
        }

        .workflow-node {
            min-height: 176px;
        }

        .summary-stat-strip,
        .observability-grid,
        .agent-row,
        .onboarding-step-grid,
        .quick-action-grid,
        .orchestration-badge-grid,
        .workflow-timeline-card-grid,
        .agent-monitor-grid,
        .enterprise-hero {
            grid-template-columns: 1fr;
        }

        .log-line {
            grid-template-columns: 1fr;
        }
    }

    /* Customer workspace: warm editorial color with dimensional accents. */
    :root { color-scheme: light; }
    .block-container, [data-testid="stMainBlockContainer"] {
        padding-top: 1.4rem !important;
        padding-left: clamp(1rem, 3vw, 2.5rem);
        padding-right: clamp(1rem, 3vw, 2.5rem);
    }
    [data-testid="stSidebar"] { background: #F1E7DC !important; }
    [data-testid="stSidebar"] > div:first-child { background: #F1E7DC !important; padding: 1.4rem 0.7rem; }
    [data-testid="stSidebarCollapsedControl"], [data-testid="collapsedControl"] {
        visibility: visible; background: #F1E7DC; color: #3D2939;
    }
    h1, h2, h3, h4 { letter-spacing: -0.025em; }
    a { color: #8E4031; }
    .stMarkdown a:hover { color: #563548; }
    input, textarea, [data-baseweb="select"], [data-baseweb="popover"], [role="listbox"] {
        color-scheme: light; color: #3D2939 !important;
    }
    [role="listbox"], [data-baseweb="popover"] > div, [data-baseweb="menu"] {
        background: #FFF9F0 !important; color: #3D2939 !important;
    }
    [role="option"] { color: #3D2939 !important; }
    [role="option"]:hover, [aria-selected="true"][role="option"] { background: #F1E3D8 !important; }
    .stTextInput input, .stTextArea textarea, .stSelectbox [data-baseweb="select"] > div {
        background: #FFF9F0 !important; border-color: #D8C6BB; min-height: 44px;
    }
    .stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {
        background: #FFF9F0; border: 1px solid #D4BFAF; color: #563548;
        border-radius: 12px; min-height: 44px; box-shadow: 0 3px 0 #E7D8CD;
        transition: transform 140ms ease, box-shadow 140ms ease, background 140ms ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, [data-testid="stFormSubmitButton"] button:hover {
        background: #F5E6DA; border-color: #A9786F; color: #3D2939;
        box-shadow: 0 4px 0 #DCC5B7; transform: translateY(-1px);
    }
    button[kind="primary"], button[data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"] {
        background: #563548 !important; border-color: #563548 !important;
        box-shadow: 0 4px 0 #D6BAAD !important; color: #FFF9F0 !important;
    }
    button[kind="primary"] p, button[kind="primary"] span,
    button[data-testid="stBaseButton-primary"] p, button[data-testid="stBaseButton-primary"] span,
    button[kind="primaryFormSubmit"] p, button[kind="primaryFormSubmit"] span { color: #FFF9F0 !important; }
    .stButton > button:disabled { background: #EAE0D6 !important; box-shadow: none !important; color: #85747B !important; }
    button:focus-visible, input:focus-visible, textarea:focus-visible, summary:focus-visible {
        outline: 3px solid #9D4937 !important; outline-offset: 3px;
    }
    [data-testid="stCaptionContainer"] p { color: #71606A !important; }
    [data-testid="stMetric"] {
        background: #FFF9F0 !important; border: 1px solid #E3D3C6; border-radius: 16px;
        padding: 1.05rem 1.2rem; box-shadow: 0 5px 0 #EEE2D7;
    }
    [data-testid="stMetricValue"] { color: #563548; }
    [data-testid="stAlertContainer"] { background: #F4EADC !important; border-color: #DCCBBC !important; }
    .customer-hero {
        position: relative; display: grid; grid-template-columns: 1fr 320px;
        align-items: center; min-height: 240px; max-height: 280px;
        padding: 1.85rem 2.25rem; margin: 0 0 1.1rem;
        background: linear-gradient(118deg, #F3E5D6 0%, #F7EBDC 57%, #ECD5C6 100%);
        border: 1px solid #E7D3C1; border-radius: 26px;
        overflow: hidden; box-shadow: 0 7px 0 #ECDDCE, 0 18px 32px rgba(75,42,58,.055);
    }
    .customer-hero-copy { position: relative; z-index: 2; }
    .customer-eyebrow, .customer-kicker {
        font-size: .67rem; font-weight: 750; letter-spacing: .14em; color: #865746;
    }
    .customer-hero h1 {
        font-size: clamp(2rem, 3.7vw, 3.15rem); line-height: 1.04;
        font-weight: 650; letter-spacing: -.045em; margin: .62rem 0 .72rem;
        padding: 0; color: #3D2939;
    }
    .customer-hero h1 em { font-family: Georgia, serif; font-weight: 500; color: #9D4937; }
    .customer-hero-copy p { font-size: .95rem; line-height: 1.55; max-width: 440px; margin: 0; color: #6B5158; }
    .sales-model { width: 300px; height: 210px; position: relative; perspective: 800px; pointer-events: none; justify-self: end; }
    .model-halo { position: absolute; width: 205px; height: 205px; border-radius: 50%; background: #EED2BB; top: -2px; left: 50px; }
    .model-card { position: absolute; width: 166px; height: 112px; border-radius: 12px; transform: rotateX(14deg) rotateY(-20deg) rotateZ(-12deg); border: 1px solid #E1C8B7; }
    .card-back { background: #C79380; left: 82px; top: 32px; transform: rotateX(16deg) rotateY(-20deg) rotateZ(4deg); box-shadow: 3px 6px 0 #BA7F6C; }
    .card-front { left: 66px; top: 47px; background: #FFF8EC; box-shadow: 3px 6px 0 #DEC5B4, 8px 18px 22px rgba(74,38,54,.11); }
    .model-card-line { position: absolute; height: 5px; width: 55px; top: 14px; left: 15px; background: #CBB29E; border-radius: 3px; }
    .model-card-line.short { width: 30px; top: 25px; background: #E2CEBA; }
    .model-stage { position: absolute; left: 56px; top: 16px; width: 200px; height: 154px; transform-style: preserve-3d; transform: rotateX(-16deg) rotateY(-26deg); animation: modelFloat 8s ease-in-out infinite; }
    .model-platform { width: 230px; height: 90px; position: absolute; bottom: -25px; left: -20px; border-radius: 13px; background: #E3C4AE; transform: rotateX(90deg) translateZ(-2px); box-shadow: 0 5px 0 #CCA58E; }
    .model-bar { position: absolute; bottom: 2px; width: 34px; height: var(--bar-height); transform-style: preserve-3d; }
    .bar-coral { --bar-height: 69px; --bar-front: #C6755A; --bar-side: #9F4F3D; --bar-top: #E3A68A; left: 20px; }
    .bar-plum { --bar-height: 100px; --bar-front: #795065; --bar-side: #563548; --bar-top: #AA7D93; left: 79px; transform: translateZ(9px); }
    .bar-sage { --bar-height: 81px; --bar-front: #82947A; --bar-side: #5B7053; --bar-top: #ACB99F; left: 138px; transform: translateZ(18px); }
    .face { display: block; position: absolute; width: 34px; height: var(--bar-height); backface-visibility: hidden; }
    .face.front { background: linear-gradient(90deg, var(--bar-front), var(--bar-front)); transform: translateZ(17px); border-radius: 2px 2px 0 0; }
    .face.back { background: var(--bar-side); transform: rotateY(180deg) translateZ(17px); }
    .face.left { background: var(--bar-side); transform: rotateY(-90deg) translateZ(17px); }
    .face.right { background: var(--bar-side); transform: rotateY(90deg) translateZ(17px); }
    .face.top { height: 34px; background: var(--bar-top); top: -17px; transform: rotateX(90deg); }
    .face.bottom { height: 34px; background: var(--bar-side); bottom: -17px; transform: rotateX(-90deg); }
    .model-orbit { position: absolute; top: 30px; left: 30px; width: 27px; height: 27px; border-radius: 50%; background: radial-gradient(circle at 35% 30%, #EBC5A9, #BD785E); box-shadow: 2px 7px 9px rgba(108,65,53,.14); }
    .model-spark { position: absolute; right: 17px; bottom: 47px; color: #9D4937; font-size: 37px; transform: rotate(12deg); }
    .model-label { position: absolute; bottom: -2px; left: 80px; font-size: .68rem; letter-spacing: .03em; color: #6B5158; }
    @keyframes modelFloat { 0%,100% { transform: translateY(0) rotateX(-16deg) rotateY(-26deg); } 50% { transform: translateY(-5px) rotateX(-12deg) rotateY(-22deg); } }
    .customer-steps { display: flex; align-items: center; gap: .8rem; margin: .3rem 0 1.2rem; padding: .85rem 1.1rem; background: #F3EADF; border-radius: 14px; }
    .customer-step { display: flex; align-items: center; gap: .55rem; flex: 1; color: #77636B; font-size: .8rem; font-weight: 550; }
    .customer-step .step-number { display: inline-flex; align-items: center; justify-content: center; width: 25px; height: 25px; border: 1px solid #CCB8AA; border-radius: 50%; color: #77636B; background: #FAF5ED; font-size: .72rem; flex-shrink: 0; }
    .customer-step.is-current { color: #563548; font-weight: 750; }
    .customer-step.is-current .step-number { background: #563548; color: #FFF9F0; border-color: #563548; }
    .customer-step.is-complete .step-number { background: #E0E6D8; color: #3F6046; border-color: #ACBDA5; }
    .customer-data-source { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; padding: .65rem .9rem; border-radius: 10px; border: 1px solid #D6DDC9; background: #EDF0E5 !important; margin: .3rem 0 .8rem; font-size: .79rem; }
    .customer-data-source span, .customer-data-source strong { color: #456047; }
    .source-dot { width: 7px; height: 7px; border-radius: 50%; background: #61805C; }
    .customer-ai-status { display: flex; gap: .7rem; align-items: flex-start; padding: .9rem 1rem; border: 1px solid #DECBC0; border-radius: 14px; background: #F5EBE2 !important; margin: .5rem 0 .8rem; }
    .customer-ai-status .ai-symbol { font-size: 1.15rem; color: #9D4937; line-height: 1.2; }
    .customer-ai-status strong { display: block; font-size: .8rem; color: #563548; }
    .customer-ai-status p { margin: .15rem 0 0; color: #71606A; line-height: 1.45; font-size: .8rem; }
    .customer-ai-status.used { border-color: #B3C3A9; background: #ECF0E5 !important; }
    .customer-welcome { margin: .5rem 0 .8rem; }
    .customer-welcome h2, .customer-answer-heading h2 { font-size: 1.5rem; letter-spacing: -.025em; color: #3D2939; padding: .3rem 0; margin: 0; }
    .customer-welcome p { color: #71606A; font-size: .92rem; max-width: 630px; margin: .2rem 0 .6rem; }
    .customer-answer-heading { border-top: 1px solid #E1D0C2; padding-top: 1.3rem; margin-top: .75rem; }
    .customer-section-label { font-weight: 700; color: #6B4254; font-size: .87rem; margin: .6rem 0 .15rem; }
    .customer-footer { margin: 1.6rem 0 .3rem; padding-top: 1rem; border-top: 1px solid #E6D8CB; font-size: .75rem; color: #7B666E; }
    @media (max-width: 760px) {
        .customer-hero { grid-template-columns: minmax(0,1fr) 190px; padding: 1.4rem; min-height: 220px; }
        .sales-model { transform: scale(.74); transform-origin: right center; margin-left: -80px; }
        .customer-hero h1 { font-size: 2.3rem; }
        .customer-hero-copy p { font-size: .85rem; }
        .customer-eyebrow { font-size: .58rem; letter-spacing: .08em; }
    }
    @media (max-width: 540px) {
        .customer-hero { grid-template-columns: 1fr; padding: 1.35rem; min-height: 210px; max-height: none; }
        .sales-model { display: none; }
        .customer-hero h1 { font-size: 2.65rem; }
        .customer-steps { padding: .7rem; gap: .5rem; align-items: flex-start; }
        .customer-step { flex-direction: column; gap: .35rem; font-size: .68rem; text-align: center; line-height: 1.35; }
        .customer-welcome h2, .customer-answer-heading h2 { font-size: 1.25rem; }
        .block-container, [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
    }
    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }
        .model-stage { animation: none !important; }
    }
    </style>
    """
