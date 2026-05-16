def get_theme_css() -> str:
    return """
    <style>
    :root {
        --bg: #0a0f1c;
        --panel: rgba(14, 20, 35, 0.88);
        --panel-strong: #121a2b;
        --panel-soft: #18233a;
        --border: rgba(148, 163, 184, 0.16);
        --text: #f8fafc;
        --muted: #94a3b8;
        --accent: #56ccf2;
        --accent-2: #2f80ed;
        --success: #34d399;
        --warning: #fbbf24;
        --danger: #f87171;
        --shadow: 0 24px 80px rgba(2, 6, 23, 0.38);
    }

    .stApp {
        background:
            radial-gradient(circle at top left, rgba(47, 128, 237, 0.22), transparent 28%),
            radial-gradient(circle at top right, rgba(86, 204, 242, 0.16), transparent 24%),
            linear-gradient(180deg, #0a0f1c 0%, #08111f 42%, #09111b 100%);
        color: var(--text);
        min-height: 100vh;
    }

    html, body, #root, .stApp, [data-testid="stApp"], [data-testid="stAppViewContainer"] {
        margin: 0;
        padding: 0;
        background: #0a0f1c !important;
        color: var(--text) !important;
        min-height: 100vh;
    }

    html,
    body,
    #root {
        overflow-x: hidden;
    }

    #root > div,
    #root > div > div,
    #root > div > div > div,
    .stApp,
    .stApp > div,
    .stApp > div > div,
    .stApp > div > div > div,
    [data-testid="stApp"],
    [data-testid="stApp"] > div,
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewContainer"] > div,
    [data-testid="stAppViewContainer"] > .main,
    [data-testid="stMain"],
    [data-testid="stMain"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        background:
            radial-gradient(circle at top left, rgba(47, 128, 237, 0.12), transparent 28%),
            radial-gradient(circle at top right, rgba(86, 204, 242, 0.08), transparent 22%),
            linear-gradient(180deg, #0a0f1c 0%, #08111f 45%, #09111b 100%) !important;
        color: var(--text) !important;
        min-height: 100vh;
    }

    [data-testid="stMainBlockContainer"],
    [data-testid="stMainBlockContainer"] > div,
    [data-testid="stBottomBlockContainer"],
    [data-testid="stBottomBlockContainer"] > div,
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stVerticalBlockBorderWrapper"] > div,
    [data-testid="stVerticalBlock"],
    [data-testid="stVerticalBlock"] > div,
    [data-testid="stHorizontalBlock"],
    [data-testid="stHorizontalBlock"] > div,
    [data-testid="column"],
    [data-testid="column"] > div,
    .main .block-container,
    section.main,
    [data-testid="stAppViewBlockContainer"] {
        background:
            radial-gradient(circle at top left, rgba(47, 128, 237, 0.08), transparent 26%),
            linear-gradient(180deg, #0a0f1c 0%, #08111f 45%, #09111b 100%) !important;
        color: var(--text) !important;
    }

    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0.08rem !important;
        padding-left: 1.25rem;
        padding-right: 1.25rem;
        max-width: 1380px;
        background: transparent !important;
    }

    [data-testid="stMainBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
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
            linear-gradient(180deg, rgba(10, 15, 28, 0.98), rgba(9, 17, 27, 0.96));
        border-right: 1px solid var(--border);
        padding-top: 0 !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding-top: 0 !important;
        background:
            linear-gradient(180deg, rgba(10, 15, 28, 0.98), rgba(9, 17, 27, 0.96)) !important;
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
        gap: 1rem;
    }

    .hero-card,
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
        backdrop-filter: blur(16px);
    }

    .hero-card {
        border-radius: 24px;
        padding: 1rem 1.25rem 1.1rem;
        background:
            linear-gradient(135deg, rgba(47, 128, 237, 0.18), rgba(14, 20, 35, 0.92) 45%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.94));
    }

    .hero-eyebrow {
        font-size: 0.8rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--accent);
        margin-bottom: 0.55rem;
    }

    .hero-title {
        font-size: clamp(1.45rem, 2.8vw, 2.25rem);
        font-weight: 700;
        line-height: 1.05;
        margin: 0;
        max-width: 14ch;
    }

    .hero-copy {
        color: var(--muted);
        font-size: 0.9rem;
        margin: 0.55rem 0 0;
        max-width: 72ch;
    }

    .hero-badges {
        display: flex;
        gap: 0.65rem;
        flex-wrap: wrap;
        margin-top: 0.8rem;
    }

    .hero-badge {
        padding: 0.45rem 0.8rem;
        border-radius: 999px;
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.12);
        color: #dbe7ff;
        font-size: 0.85rem;
    }

    .section-card,
    .chat-card,
    .table-card {
        border-radius: 22px;
        padding: 0.95rem 1rem;
    }

    .workspace-shell {
        border-radius: 26px;
        padding: 0.78rem 0.9rem;
        background:
            linear-gradient(180deg, rgba(11, 18, 31, 0.94), rgba(9, 16, 28, 0.96));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .workspace-panel {
        border-radius: 22px;
        padding: 0.82rem 0.9rem;
        background:
            linear-gradient(180deg, rgba(16, 24, 40, 0.9), rgba(10, 16, 29, 0.92));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .compact-shell {
        margin-bottom: 0.45rem;
    }

    .workspace-shell:hover,
    .workspace-panel:hover,
    .workspace-module:hover,
    .glass-widget:hover,
    .kpi-card:hover {
        transform: translateY(-2px);
        border-color: rgba(86, 204, 242, 0.22);
        box-shadow: 0 26px 60px rgba(2, 6, 23, 0.34);
    }

    .compact-card {
        padding-bottom: 0.95rem;
    }

    .section-title {
        font-size: 1.05rem;
        font-weight: 600;
        margin-bottom: 0.2rem;
    }

    .section-subtitle {
        color: var(--muted);
        font-size: 0.9rem;
        margin-bottom: 1rem;
    }

    .kpi-card {
        border-radius: 20px;
        padding: 1rem 1.05rem;
        min-height: 112px;
        background:
            linear-gradient(180deg, rgba(24, 35, 58, 0.95), rgba(14, 20, 35, 0.92));
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
        color: #dbeafe;
        font-size: 0.88rem;
    }

    .glass-widget {
        border-radius: 22px;
        padding: 1rem 1.05rem;
        min-height: 132px;
        background:
            linear-gradient(180deg, rgba(12, 18, 34, 0.74), rgba(17, 27, 46, 0.58));
        position: relative;
        overflow: hidden;
    }

    .glass-widget::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(86, 204, 242, 0.1), transparent 48%);
        pointer-events: none;
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
        color: #f8fbff;
        word-break: break-word;
    }

    .glass-widget-copy {
        position: relative;
        z-index: 1;
        color: #bfd3ea;
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
        border: 1px solid rgba(148, 163, 184, 0.16);
        background: rgba(148, 163, 184, 0.08);
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
        background: rgba(148, 163, 184, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.1);
        color: #dbeafe;
        font-size: 0.87rem;
        margin-bottom: 0.55rem;
    }

    .timeline-card {
        border-radius: 20px;
        padding: 0.85rem 1rem;
        min-height: 94px;
        background:
            linear-gradient(180deg, rgba(18, 26, 43, 0.9), rgba(13, 20, 35, 0.84));
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
        color: #dbeafe;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    .workflow-empty {
        color: var(--muted);
        padding: 1rem 0;
    }

    .workflow-rail-shell {
        overflow-x: auto;
        padding-bottom: 0.2rem;
        margin-bottom: 0.45rem;
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
        min-height: 178px;
        padding: 0.95rem 1rem;
        border-radius: 22px;
        border: 1px solid rgba(148, 163, 184, 0.14);
        background:
            linear-gradient(180deg, rgba(15, 23, 42, 0.88), rgba(10, 15, 28, 0.92));
        box-shadow: var(--shadow);
        backdrop-filter: blur(16px);
        overflow: hidden;
    }

    .workflow-node::before {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(135deg, rgba(86, 204, 242, 0.08), transparent 45%);
        pointer-events: none;
    }

    .workflow-node-top {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 0.75rem;
        margin-bottom: 0.85rem;
        position: relative;
        z-index: 1;
    }

    .workflow-node-title {
        font-size: 0.96rem;
        font-weight: 650;
        color: #f8fbff;
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
        color: #d8e7f8;
        font-size: 0.85rem;
        line-height: 1.45;
        min-height: 60px;
    }

    .workflow-node-metadata {
        position: relative;
        z-index: 1;
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        margin-top: 0.85rem;
    }

    .workflow-node-metadata span {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        padding: 0.28rem 0.55rem;
        font-size: 0.73rem;
        color: #dbeafe;
        background: rgba(148, 163, 184, 0.08);
        border: 1px solid rgba(148, 163, 184, 0.12);
    }

    .workflow-connector {
        width: 42px;
        height: 2px;
        margin: 0 0.3rem;
        background: linear-gradient(90deg, rgba(86, 204, 242, 0.18), rgba(148, 163, 184, 0.26));
        position: relative;
        opacity: 0.9;
    }

    .workflow-connector::after {
        content: "";
        position: absolute;
        right: -1px;
        top: -3px;
        width: 8px;
        height: 8px;
        border-top: 2px solid rgba(148, 163, 184, 0.28);
        border-right: 2px solid rgba(148, 163, 184, 0.28);
        transform: rotate(45deg);
    }

    .active-agent {
        animation: activeAgentGlow 2.8s ease-in-out infinite;
        border-color: rgba(86, 204, 242, 0.34);
    }

    .active-agent .workflow-status-dot {
        animation: subtlePulse 2.6s ease-in-out infinite;
    }

    @keyframes activeAgentGlow {
        0% {
            box-shadow: 0 18px 44px rgba(2, 6, 23, 0.34), 0 0 0 0 rgba(86, 204, 242, 0.08);
        }
        50% {
            box-shadow: 0 18px 44px rgba(2, 6, 23, 0.34), 0 0 22px 0 rgba(86, 204, 242, 0.2);
        }
        100% {
            box-shadow: 0 18px 44px rgba(2, 6, 23, 0.34), 0 0 0 0 rgba(86, 204, 242, 0.08);
        }
    }

    .response-card {
        border-radius: 20px;
        padding: 1rem 1.05rem;
        margin-bottom: 0.85rem;
        border: 1px solid rgba(148, 163, 184, 0.12);
        box-shadow: var(--shadow);
        backdrop-filter: blur(14px);
    }

    .assistant-card {
        background:
            linear-gradient(135deg, rgba(86, 204, 242, 0.09), rgba(15, 23, 42, 0.92) 42%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.9), rgba(10, 15, 28, 0.92));
    }

    .user-card {
        background:
            linear-gradient(135deg, rgba(47, 128, 237, 0.12), rgba(12, 18, 34, 0.9) 46%),
            linear-gradient(180deg, rgba(15, 23, 42, 0.94), rgba(10, 15, 28, 0.92));
    }

    .response-meta {
        color: #8ecdf2;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.55rem;
    }

    .response-content {
        color: #eef6ff;
        font-size: 0.95rem;
        line-height: 1.55;
    }

    .workspace-module {
        border-radius: 24px;
        padding: 0.88rem 0.94rem;
        margin-bottom: 0.62rem;
        border: 1px solid rgba(148, 163, 184, 0.14);
        box-shadow: var(--shadow);
        backdrop-filter: blur(16px);
        background:
            linear-gradient(180deg, rgba(14, 20, 35, 0.9), rgba(10, 15, 28, 0.94));
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .default-module {
        background:
            linear-gradient(135deg, rgba(86, 204, 242, 0.05), rgba(15, 23, 42, 0.9) 38%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.96));
    }

    .workspace-module-head {
        margin-bottom: 0.58rem;
    }

    .workspace-module .section-subtitle {
        margin-bottom: 0;
    }

    .workspace-module-body {
        position: relative;
        color: #eaf3ff;
    }

    .summary-module {
        background:
            linear-gradient(135deg, rgba(86, 204, 242, 0.08), rgba(15, 23, 42, 0.9) 38%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.96));
    }

    .recommendation-module {
        background:
            linear-gradient(135deg, rgba(47, 128, 237, 0.1), rgba(12, 18, 34, 0.92) 42%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.9), rgba(10, 15, 28, 0.95));
    }

    .observability-module {
        background:
            linear-gradient(135deg, rgba(52, 211, 153, 0.06), rgba(15, 23, 42, 0.92) 40%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.96));
    }

    .insight-module {
        background:
            linear-gradient(135deg, rgba(251, 191, 36, 0.06), rgba(15, 23, 42, 0.92) 40%),
            linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.96));
    }

    .summary-stat-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.85rem;
        margin-bottom: 0.9rem;
    }

    .summary-stat {
        border-radius: 18px;
        padding: 0.85rem 0.9rem;
        background: rgba(148, 163, 184, 0.06);
        border: 1px solid rgba(148, 163, 184, 0.12);
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
        color: #f8fbff;
        font-size: 0.94rem;
        line-height: 1.4;
        word-break: break-word;
    }

    .executive-callout,
    .workspace-body-copy {
        color: #e6f0fb;
        font-size: 0.92rem;
        line-height: 1.6;
        padding: 0.95rem 1rem;
        border-radius: 18px;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    .workspace-list-item {
        padding: 0.8rem 0.9rem;
        border-radius: 16px;
        margin-bottom: 0.55rem;
        color: #ebf4ff;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.1);
        line-height: 1.5;
    }

    .workspace-list-item:last-child {
        margin-bottom: 0;
    }

    .activity-item {
        display: grid;
        grid-template-columns: 14px 1fr auto;
        gap: 0.75rem;
        align-items: start;
        padding: 0.75rem 0;
        border-bottom: 1px solid rgba(148, 163, 184, 0.08);
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
        box-shadow: 0 0 0 5px rgba(148, 163, 184, 0.08);
    }

    .activity-dot.live {
        background: #56ccf2;
        animation: subtlePulse 3s ease-in-out infinite;
    }

    .activity-dot.stable {
        background: #34d399;
    }

    .activity-copy {
        min-width: 0;
    }

    .activity-title {
        color: #f5fbff;
        font-size: 0.9rem;
        margin-bottom: 0.2rem;
    }

    .activity-subtitle {
        color: #b7cbe2;
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
        gap: 0.75rem;
    }

    .agent-pill {
        border-radius: 18px;
        padding: 0.85rem 0.9rem;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.1);
        transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
    }

    .agent-pill:hover {
        transform: translateY(-2px);
        border-color: rgba(86, 204, 242, 0.2);
    }

    .agent-pill-active {
        border-color: rgba(86, 204, 242, 0.26);
        box-shadow: 0 0 20px rgba(86, 204, 242, 0.12);
    }

    .agent-pill-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5rem;
        margin-bottom: 0.45rem;
    }

    .agent-pill-name {
        color: #f8fbff;
        font-size: 0.88rem;
        font-weight: 600;
    }

    .agent-pill-status {
        color: #8ecdf2;
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .agent-pill-copy {
        color: #bfd3ea;
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
        padding: 0.68rem 0.8rem;
        border-radius: 16px;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.08);
    }

    .log-time {
        color: var(--muted);
        font-size: 0.74rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .log-step {
        color: #8ecdf2;
        font-size: 0.78rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    .log-message {
        color: #eef6ff;
        font-size: 0.86rem;
        line-height: 1.45;
    }

    @keyframes subtlePulse {
        0% { box-shadow: 0 0 0 5px rgba(86, 204, 242, 0.08); }
        50% { box-shadow: 0 0 0 8px rgba(86, 204, 242, 0.14); }
        100% { box-shadow: 0 0 0 5px rgba(86, 204, 242, 0.08); }
    }

    .observability-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.8rem;
    }

    .observability-metric {
        border-radius: 18px;
        padding: 0.72rem 0.82rem;
        background: rgba(148, 163, 184, 0.05);
        border: 1px solid rgba(148, 163, 184, 0.1);
    }

    [data-testid="stForm"] {
        position: sticky;
        top: 0.65rem;
        z-index: 24;
        padding: 0.58rem 0.65rem 0.14rem;
        margin-bottom: 0.35rem;
        border-radius: 20px;
        background:
            linear-gradient(180deg, rgba(10, 15, 28, 0.96), rgba(8, 17, 31, 0.94)) !important;
        border: 1px solid rgba(148, 163, 184, 0.12);
        box-shadow: 0 16px 38px rgba(2, 6, 23, 0.26);
        backdrop-filter: blur(18px);
    }

    div[data-testid="stMetric"] {
        background: transparent;
        border: none;
        padding: 0;
    }

    .stButton > button,
    .stDownloadButton > button {
        border-radius: 14px;
        border: 1px solid rgba(86, 204, 242, 0.26);
        background: linear-gradient(135deg, rgba(47, 128, 237, 0.22), rgba(86, 204, 242, 0.12));
        color: var(--text);
        font-weight: 600;
        padding: 0.65rem 0.95rem;
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        border-color: rgba(86, 204, 242, 0.45);
        color: white;
    }

    .stTextInput input,
    .stTextArea textarea,
    .stSelectbox div[data-baseweb="select"] > div,
    .stMultiSelect div[data-baseweb="select"] > div,
    div[data-baseweb="base-input"] > div,
    div[data-baseweb="input"] > div,
    textarea {
        background: rgba(15, 23, 42, 0.85);
        border-radius: 14px;
        border: 1px solid rgba(148, 163, 184, 0.16);
        color: var(--text) !important;
        box-shadow: none !important;
    }

    .stChatMessage {
        background: rgba(15, 23, 42, 0.5);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 18px;
        padding: 0.35rem 0.5rem;
    }

    [data-testid="stChatInput"] {
        background:
            linear-gradient(180deg, rgba(10, 15, 28, 0.92), rgba(8, 17, 31, 0.98)) !important;
        border-top: 1px solid rgba(148, 163, 184, 0.12);
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
        background: rgba(15, 23, 42, 0.92) !important;
        color: var(--text) !important;
        border: 1px solid rgba(86, 204, 242, 0.18) !important;
        border-radius: 18px !important;
    }

    [data-testid="stChatInput"] button {
        background: linear-gradient(135deg, rgba(47, 128, 237, 0.24), rgba(86, 204, 242, 0.18)) !important;
        color: var(--text) !important;
        border: 1px solid rgba(86, 204, 242, 0.24) !important;
    }

    [data-testid="stChatInput"]::before {
        content: "";
        position: absolute;
        inset: 0;
        background:
            linear-gradient(180deg, rgba(15, 23, 42, 0.1), rgba(10, 15, 28, 0.3));
        pointer-events: none;
    }

    [data-testid="stChatInputContainer"],
    [data-testid="stChatInputContainer"] > div,
    [data-testid="stChatInputContainer"] > div > div,
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottomBlockContainer"] {
        background:
            linear-gradient(180deg, rgba(10, 15, 28, 0.96), rgba(8, 17, 31, 1)) !important;
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
        border: 1px solid rgba(148, 163, 184, 0.12);
        background: rgba(15, 23, 42, 0.74) !important;
    }

    [data-testid="stDataFrameResizable"] {
        background: rgba(15, 23, 42, 0.74) !important;
    }

    [data-testid="stDataFrameGlideDataEditor"] {
        background: rgba(15, 23, 42, 0.74) !important;
    }

    [data-testid="stDataFrameGlideDataEditor"] * {
        background-color: rgba(15, 23, 42, 0.82) !important;
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

    [data-testid="stAppViewBlockContainer"],
    [data-testid="stMain"],
    [data-testid="stMainBlockContainer"],
    [data-testid="stAppViewContainer"] section[data-testid="stMain"] {
        background: transparent !important;
    }

    [data-testid="stAlert"] {
        background: rgba(15, 23, 42, 0.86) !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        color: var(--text) !important;
        border-radius: 16px;
    }

    details {
        background: rgba(15, 23, 42, 0.72) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        border-radius: 16px !important;
    }

    details summary,
    details summary * {
        background: transparent !important;
        color: var(--text) !important;
    }

    [data-testid="stFileUploader"],
    [data-testid="stFileUploaderDropzone"] {
        background: rgba(15, 23, 42, 0.74) !important;
        border: 1px dashed rgba(86, 204, 242, 0.22) !important;
        color: var(--text) !important;
        border-radius: 18px !important;
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
        color: #7c8ba1 !important;
    }

    .footer-note {
        text-align: center;
        color: var(--muted);
        font-size: 0.84rem;
        padding: 0.65rem 0 0.1rem;
    }

    @media (max-width: 992px) {
        .block-container {
            padding-top: 0 !important;
            padding-left: 0.85rem;
            padding-right: 0.85rem;
        }

        .hero-card,
        .section-card,
        .chat-card,
        .table-card {
            padding: 1rem;
        }

        .workflow-rail {
            min-width: 980px;
        }

        .workflow-node {
            min-height: 190px;
        }

        .summary-stat-strip,
        .observability-grid,
        .agent-row {
            grid-template-columns: 1fr;
        }

        .log-line {
            grid-template-columns: 1fr;
        }
    }
    </style>
    """
