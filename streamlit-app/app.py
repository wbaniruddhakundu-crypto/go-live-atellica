import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date
import plotly.express as px
import plotly.graph_objects as go
import os
import io
from fpdf import FPDF
import workbook as wb

st.set_page_config(
    page_title="Atellica Go-Live Command Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

@st.cache_resource
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_connection()

def init_db():
    conn.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            country TEXT NOT NULL,
            instrument TEXT NOT NULL,
            serial_number TEXT,
            planned_golive DATE,
            actual_golive DATE,
            timeframe TEXT,
            site_ready TEXT DEFAULT 'Pending',
            reagent_ready TEXT DEFAULT 'Pending',
            consumables_ready TEXT DEFAULT 'Pending',
            installation TEXT DEFAULT 'Pending',
            connectivity TEXT DEFAULT 'Pending',
            validation TEXT DEFAULT 'Pending',
            training TEXT DEFAULT 'Pending',
            delay_reason TEXT,
            status TEXT DEFAULT 'On Track',
            notes TEXT
        )
    """)
    for col, coltype in (("timeframe", "TEXT"), ("serial_number", "TEXT")):
        try:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {col} {coltype}")
            conn.commit()
        except Exception:
            pass
    conn.commit()

init_db()

@st.cache_resource
def _wb_schema_ready():
    return wb.ensure_schema()

_wb_schema_ready()

STATUS_OPTIONS = ["On Track", "Delayed", "Completed", "At Risk", "On Hold"]
TIMEFRAME_OPTIONS = ["3 months", "6 months", "9 months", "1 year", "18 months", "2 years", "Other"]
READINESS_OPTIONS = ["Pending", "In Progress", "Complete", "Blocked"]
INSTRUMENTS = [
    "Atellica Solution",
    "Atellica IM",
    "Atellica CH",
    "Atellica CI",
    "Atellica NEPH",
    "Other",
]
COUNTRIES = sorted([
    "Argentina", "Australia", "Austria", "Belgium", "Brazil", "Canada",
    "Chile", "China", "Colombia", "Czech Republic", "Denmark", "Finland",
    "France", "Germany", "Greece", "Hungary", "India", "Indonesia",
    "Ireland", "Israel", "Italy", "Japan", "Malaysia", "Mexico",
    "Netherlands", "New Zealand", "Norway", "Peru", "Philippines", "Poland",
    "Portugal", "Romania", "Saudi Arabia", "Singapore", "South Africa",
    "South Korea", "Spain", "Sweden", "Switzerland", "Thailand",
    "Turkey", "UAE", "UK", "USA", "Other",
])

READINESS_COLS = [
    "site_ready", "reagent_ready", "consumables_ready",
    "installation", "connectivity", "validation", "training",
]

STATUS_COLORS = {
    "On Track": "#22c55e",
    "Delayed": "#ef4444",
    "Completed": "#3b82f6",
    "At Risk": "#f97316",
    "On Hold": "#94a3b8",
}

def load_projects() -> pd.DataFrame:
    df = pd.read_sql_query("SELECT * FROM projects ORDER BY planned_golive ASC", conn)
    return df

def readiness_score(row) -> int:
    score = sum(1 for col in READINESS_COLS if row.get(col) == "Complete")
    return score

def readiness_pct(row) -> float:
    return readiness_score(row) / len(READINESS_COLS) * 100

# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Siemens_Healthineers_logo.svg/320px-Siemens_Healthineers_logo.svg.png",
        width=200,
    )
    st.markdown("## Atellica Go-Live")
    st.markdown("Command Center")
    st.divider()
    menu = st.selectbox(
        "Navigate",
        ["📤 Upload Workbook", "🔧 Installation Tracker", "⚠️ Issues & Failures", "📊 Dashboard", "➕ New Project", "📋 Project List", "✏️ Edit Project", "📥 Bulk Import", "📅 Gantt Chart", "🗺️ World Map", "📑 PDF Report"],
        label_visibility="collapsed",
    )
    st.divider()
    st.markdown("**📎 Share this app**")
    try:
        _host = st.context.headers.get("host", "")
    except Exception:
        _host = ""
    if _host:
        st.code(f"https://{_host}", language=None)
        st.caption("Copy this link to share. Use your published (.replit.app) link for permanent 24/7 access.")
    else:
        st.caption("Open the published (.replit.app) link to share this app.")
    st.divider()
    st.caption("© Siemens Healthineers")

# ── Workbook pages ────────────────────────────────────────────────────────────

if menu == "📤 Upload Workbook":
    wb.render_upload()

elif menu == "🔧 Installation Tracker":
    wb.render_tracker()

elif menu == "⚠️ Issues & Failures":
    wb.render_issues()

# ── Dashboard ─────────────────────────────────────────────────────────────────

elif menu == "📊 Dashboard":
    st.title("🚀 Atellica Go-Live Command Center")
    st.caption(f"Last refreshed: {datetime.now().strftime('%d %b %Y  %H:%M')}")

    df = load_projects()

    if df.empty:
        st.info("No projects yet. Use **➕ New Project** in the sidebar to add your first go-live.")
        st.stop()

    # Add computed columns
    df["readiness_pct"] = df.apply(readiness_pct, axis=1)
    df["readiness_score"] = df.apply(readiness_score, axis=1)

    today = date.today()

    # ── KPI row
    total = len(df)
    on_track = len(df[df["status"] == "On Track"])
    delayed = len(df[df["status"] == "Delayed"])
    at_risk = len(df[df["status"] == "At Risk"])
    completed = len(df[df["status"] == "Completed"])

    overdue = 0
    if "planned_golive" in df.columns:
        df["planned_golive_dt"] = pd.to_datetime(df["planned_golive"], errors="coerce")
        overdue = len(df[(df["planned_golive_dt"] < pd.Timestamp(today)) & (~df["status"].isin(["Completed"]))])

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Projects", total)
    k2.metric("On Track", on_track, delta=None)
    k3.metric("Completed", completed)
    k4.metric("Delayed", delayed, delta=f"-{delayed}" if delayed else None, delta_color="inverse")
    k5.metric("At Risk", at_risk, delta=f"-{at_risk}" if at_risk else None, delta_color="inverse")
    k6.metric("Overdue", overdue, delta=f"-{overdue}" if overdue else None, delta_color="inverse")

    st.divider()

    # ── Row 2: Status donut + Country bar
    col_a, col_b = st.columns([1, 2])

    with col_a:
        st.subheader("Projects by Status")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        color_map = {s: c for s, c in STATUS_COLORS.items()}
        fig_pie = px.pie(
            status_counts,
            values="Count",
            names="Status",
            hole=0.55,
            color="Status",
            color_discrete_map=color_map,
        )
        fig_pie.update_traces(textposition="inside", textinfo="percent+label")
        fig_pie.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=300)
        st.plotly_chart(fig_pie, width='stretch')

    with col_b:
        st.subheader("Projects by Country")
        country_counts = df.groupby(["country", "status"]).size().reset_index(name="Count")
        fig_bar = px.bar(
            country_counts,
            x="country",
            y="Count",
            color="status",
            barmode="stack",
            color_discrete_map=STATUS_COLORS,
            labels={"country": "Country", "Count": "Projects"},
        )
        fig_bar.update_layout(
            showlegend=True,
            legend_title="Status",
            margin=dict(t=10, b=10),
            height=300,
            xaxis_tickangle=-30,
        )
        st.plotly_chart(fig_bar, width='stretch')

    # ── Row 3: Instrument breakdown + Readiness heatmap
    col_c, col_d = st.columns([1, 2])

    with col_c:
        st.subheader("Projects by Instrument")
        inst_counts = df["instrument"].value_counts().reset_index()
        inst_counts.columns = ["Instrument", "Count"]
        fig_inst = px.bar(
            inst_counts,
            x="Count",
            y="Instrument",
            orientation="h",
            color="Count",
            color_continuous_scale="Blues",
        )
        fig_inst.update_layout(
            showlegend=False,
            coloraxis_showscale=False,
            margin=dict(t=10, b=10),
            height=300,
        )
        st.plotly_chart(fig_inst, width='stretch')

    with col_d:
        st.subheader("Go-Live Readiness by Project")
        readiness_labels = {
            "site_ready": "Site",
            "reagent_ready": "Reagents",
            "consumables_ready": "Consumables",
            "installation": "Installation",
            "connectivity": "Connectivity",
            "validation": "Validation",
            "training": "Training",
        }
        heatmap_df = df[["customer"] + READINESS_COLS].copy()
        heatmap_df = heatmap_df.rename(columns=readiness_labels)
        value_map = {"Pending": 0, "In Progress": 1, "Complete": 2, "Blocked": -1}
        heat_num = heatmap_df.set_index("customer").replace(value_map)
        color_scale = [
            [0.0, "#ef4444"],
            [0.25, "#f97316"],
            [0.5, "#facc15"],
            [0.75, "#22c55e"],
            [1.0, "#15803d"],
        ]
        fig_heat = go.Figure(
            data=go.Heatmap(
                z=heat_num.values,
                x=list(readiness_labels.values()),
                y=heat_num.index.tolist(),
                colorscale=color_scale,
                zmin=-1,
                zmax=2,
                showscale=False,
                text=heatmap_df.set_index("customer").values,
                texttemplate="%{text}",
                hovertemplate="Customer: %{y}<br>Item: %{x}<br>Status: %{text}<extra></extra>",
            )
        )
        fig_heat.update_layout(
            margin=dict(t=10, b=10),
            height=max(300, 40 * len(df)),
            xaxis=dict(side="top"),
        )
        st.plotly_chart(fig_heat, width='stretch')

    # ── Upcoming Go-Lives
    st.subheader("📅 Upcoming Go-Lives (Next 60 Days)")
    if "planned_golive_dt" in df.columns:
        upcoming = df[
            (df["planned_golive_dt"] >= pd.Timestamp(today))
            & (df["planned_golive_dt"] <= pd.Timestamp(today) + pd.Timedelta(days=60))
        ].sort_values("planned_golive_dt")
        if upcoming.empty:
            st.info("No go-lives scheduled in the next 60 days.")
        else:
            display_cols = ["customer", "country", "instrument", "planned_golive", "status", "readiness_pct"]
            up_show = upcoming[display_cols].copy()
            up_show["readiness_pct"] = up_show["readiness_pct"].apply(lambda x: f"{x:.0f}%")
            up_show.columns = ["Customer", "Country", "Instrument", "Planned Go-Live", "Status", "Readiness"]
            st.dataframe(up_show, width='stretch', hide_index=True)

# ── New Project ───────────────────────────────────────────────────────────────

elif menu == "➕ New Project":
    st.title("➕ New Go-Live Project")
    st.caption("Fill in the details below to register a new Atellica go-live.")

    with st.form("new_project_form", clear_on_submit=True):
        st.subheader("Customer & Instrument")
        c1, c2, c3 = st.columns(3)
        customer = c1.text_input("Customer Name *", placeholder="e.g. City General Hospital")
        country = c2.selectbox("Country *", COUNTRIES)
        instrument = c3.selectbox("Instrument *", INSTRUMENTS)
        serial_number = st.text_input("Serial Number", placeholder="e.g. ATL-IN-045")

        st.subheader("Timeline")
        t1, t2 = st.columns(2)
        proposed_golive = t1.date_input("Proposed Go-Live Date", value=None)
        actual_golive = t2.date_input("Actual Go-Live Date (if completed)", value=None)
        planned_golive = proposed_golive
        timeframe = None

        st.subheader("Readiness Checklist")
        r1, r2, r3, r4 = st.columns(4)
        site_ready = r1.selectbox("Site Ready", READINESS_OPTIONS, key="site")
        reagent_ready = r2.selectbox("Reagents Ready", READINESS_OPTIONS, key="reagent")
        consumables_ready = r3.selectbox("Consumables Ready", READINESS_OPTIONS, key="consumables")
        installation = r4.selectbox("Installation", READINESS_OPTIONS, key="install")

        r5, r6, r7, _ = st.columns(4)
        connectivity = r5.selectbox("Connectivity", READINESS_OPTIONS, key="connectivity")
        validation = r6.selectbox("Validation", READINESS_OPTIONS, key="validation")
        training = r7.selectbox("Training", READINESS_OPTIONS, key="training")

        st.subheader("Status & Notes")
        s1, s2 = st.columns(2)
        status = s1.selectbox("Project Status", STATUS_OPTIONS)
        delay_reason = s2.text_input("Delay Reason (if any)", placeholder="e.g. Reagent supply delay")
        notes = st.text_area("Notes", placeholder="Any additional context...")

        submitted = st.form_submit_button("💾 Save Project", type="primary", width='stretch')

        if submitted:
            if not customer.strip():
                st.error("Customer Name is required.")
            else:
                conn.execute("""
                    INSERT INTO projects
                        (customer, country, instrument, serial_number, planned_golive, actual_golive,
                         timeframe, site_ready, reagent_ready, consumables_ready, installation,
                         connectivity, validation, training, delay_reason, status, notes)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    customer.strip(), country, instrument,
                    serial_number.strip() or None,
                    str(planned_golive) if planned_golive else None,
                    str(actual_golive) if actual_golive else None,
                    timeframe or None,
                    site_ready, reagent_ready, consumables_ready, installation,
                    connectivity, validation, training,
                    delay_reason.strip() or None,
                    status,
                    notes.strip() or None,
                ))
                conn.commit()
                st.success(f"✅ Project for **{customer}** saved successfully!")
                st.balloons()

# ── Project List ──────────────────────────────────────────────────────────────

elif menu == "📋 Project List":
    st.title("📋 Project List")

    wb.render_project_list_section()

    st.divider()
    st.subheader("✍️ Manually Added Projects")

    df = load_projects()

    if df.empty:
        st.info("No manually-added projects yet. Use **➕ New Project** to add one. Your uploaded workbook instruments appear above.")
        st.stop()

    # Filters
    with st.expander("🔍 Filter Projects", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        filter_country = fc1.multiselect("Country", sorted(df["country"].unique()))
        filter_instrument = fc2.multiselect("Instrument", sorted(df["instrument"].unique()))
        filter_status = fc3.multiselect("Status", STATUS_OPTIONS)
        filter_search = fc4.text_input("Search Customer", placeholder="Type to search...")

    filtered = df.copy()
    if filter_country:
        filtered = filtered[filtered["country"].isin(filter_country)]
    if filter_instrument:
        filtered = filtered[filtered["instrument"].isin(filter_instrument)]
    if filter_status:
        filtered = filtered[filtered["status"].isin(filter_status)]
    if filter_search:
        filtered = filtered[filtered["customer"].str.contains(filter_search, case=False, na=False)]

    st.caption(f"Showing {len(filtered)} of {len(df)} projects")

    # Computed readiness
    filtered = filtered.copy()
    filtered["readiness_pct"] = filtered.apply(readiness_pct, axis=1).apply(lambda x: f"{x:.0f}%")

    display_cols = {
        "id": "ID",
        "customer": "Customer",
        "country": "Country",
        "instrument": "Instrument",
        "serial_number": "Serial Number",
        "timeframe": "Timeframe",
        "planned_golive": "Proposed Go-Live",
        "actual_golive": "Actual Go-Live",
        "status": "Status",
        "readiness_pct": "Readiness",
        "delay_reason": "Delay Reason",
    }

    show = filtered[[c for c in display_cols.keys() if c in filtered.columns]].rename(columns=display_cols)

    st.dataframe(
        show,
        width='stretch',
        hide_index=True,
        column_config={
            "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
            "Readiness": st.column_config.TextColumn("Readiness"),
            "Proposed Go-Live": st.column_config.DateColumn("Proposed Go-Live"),
            "Actual Go-Live": st.column_config.DateColumn("Actual Go-Live"),
        },
    )

    # ── Export buttons
    st.divider()
    st.subheader("⬇️ Export Data")

    export_df = filtered.copy()
    export_df["readiness_pct"] = export_df.apply(readiness_pct, axis=1).apply(lambda x: f"{x:.0f}%")
    export_cols = [
        "id", "customer", "country", "instrument", "serial_number", "timeframe",
        "planned_golive", "actual_golive", "status",
        "site_ready", "reagent_ready", "consumables_ready",
        "installation", "connectivity", "validation", "training",
        "readiness_pct", "delay_reason", "notes",
    ]
    export_df = export_df[[c for c in export_cols if c in export_df.columns]]
    export_df = export_df.rename(columns={
        "id": "ID", "customer": "Customer", "country": "Country",
        "instrument": "Instrument", "serial_number": "Serial Number", "timeframe": "Timeframe",
        "planned_golive": "Proposed Go-Live",
        "actual_golive": "Actual Go-Live", "status": "Status",
        "site_ready": "Site Ready", "reagent_ready": "Reagent Ready",
        "consumables_ready": "Consumables Ready", "installation": "Installation",
        "connectivity": "Connectivity", "validation": "Validation",
        "training": "Training", "readiness_pct": "Readiness %",
        "delay_reason": "Delay Reason", "notes": "Notes",
    })

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    ex1, ex2 = st.columns(2)

    # CSV
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    ex1.download_button(
        label="📄 Download CSV",
        data=csv_bytes,
        file_name=f"atellica_golive_{timestamp}.csv",
        mime="text/csv",
        width='stretch',
    )

    # Excel
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
        export_df.to_excel(writer, index=False, sheet_name="Go-Live Projects")
        ws = writer.sheets["Go-Live Projects"]
        for col_cells in ws.columns:
            max_len = max((len(str(cell.value or "")) for cell in col_cells), default=10)
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)
    excel_bytes = excel_buf.getvalue()
    ex2.download_button(
        label="📊 Download Excel",
        data=excel_bytes,
        file_name=f"atellica_golive_{timestamp}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        width='stretch',
    )

    st.caption(f"Exporting {len(export_df)} project(s) — filters applied above are reflected in the export.")

    # Delete project
    st.divider()
    st.subheader("🗑️ Delete a Project")
    if not filtered.empty:
        del_options = {f"#{row['id']} — {row['customer']} ({row['country']})": row['id']
                       for _, row in filtered.iterrows()}
        del_choice = st.selectbox("Select project to delete", list(del_options.keys()))
        if st.button("Delete Project", type="secondary"):
            pid = del_options[del_choice]
            conn.execute("DELETE FROM projects WHERE id = ?", (pid,))
            conn.commit()
            st.success("Project deleted.")
            st.rerun()

# ── Edit Project ──────────────────────────────────────────────────────────────

elif menu == "✏️ Edit Project":
    st.title("✏️ Edit Project")

    df = load_projects()

    if df.empty:
        st.info("No projects to edit yet.")
        st.stop()

    options = {f"#{row['id']} — {row['customer']} ({row['country']})": row['id']
               for _, row in df.iterrows()}
    selection = st.selectbox("Select a project to edit", list(options.keys()))
    pid = options[selection]

    row = conn.execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
    if not row:
        st.error("Project not found.")
        st.stop()

    row = dict(row)

    def safe_date(val):
        if val:
            try:
                return datetime.strptime(val, "%Y-%m-%d").date()
            except Exception:
                return None
        return None

    with st.form("edit_form"):
        st.subheader("Customer & Instrument")
        e1, e2, e3 = st.columns(3)
        customer = e1.text_input("Customer Name *", value=row["customer"])
        country_idx = COUNTRIES.index(row["country"]) if row["country"] in COUNTRIES else 0
        country = e2.selectbox("Country *", COUNTRIES, index=country_idx)
        inst_idx = INSTRUMENTS.index(row["instrument"]) if row["instrument"] in INSTRUMENTS else 0
        instrument = e3.selectbox("Instrument *", INSTRUMENTS, index=inst_idx)
        serial_number = st.text_input("Serial Number", value=row.get("serial_number") or "")

        st.subheader("Timeline")
        timeframe = row.get("timeframe")
        t1, t2 = st.columns(2)
        planned_golive = t1.date_input("Proposed Go-Live Date", value=safe_date(row["planned_golive"]))
        actual_golive = t2.date_input("Actual Go-Live Date", value=safe_date(row["actual_golive"]))

        st.subheader("Readiness Checklist")

        def ro_idx(col):
            val = row.get(col, "Pending")
            return READINESS_OPTIONS.index(val) if val in READINESS_OPTIONS else 0

        r1, r2, r3, r4 = st.columns(4)
        site_ready = r1.selectbox("Site Ready", READINESS_OPTIONS, index=ro_idx("site_ready"))
        reagent_ready = r2.selectbox("Reagents Ready", READINESS_OPTIONS, index=ro_idx("reagent_ready"))
        consumables_ready = r3.selectbox("Consumables Ready", READINESS_OPTIONS, index=ro_idx("consumables_ready"))
        installation = r4.selectbox("Installation", READINESS_OPTIONS, index=ro_idx("installation"))

        r5, r6, r7, _ = st.columns(4)
        connectivity = r5.selectbox("Connectivity", READINESS_OPTIONS, index=ro_idx("connectivity"))
        validation = r6.selectbox("Validation", READINESS_OPTIONS, index=ro_idx("validation"))
        training = r7.selectbox("Training", READINESS_OPTIONS, index=ro_idx("training"))

        st.subheader("Status & Notes")
        s1, s2 = st.columns(2)
        st_idx = STATUS_OPTIONS.index(row["status"]) if row.get("status") in STATUS_OPTIONS else 0
        status = s1.selectbox("Project Status", STATUS_OPTIONS, index=st_idx)
        delay_reason = s2.text_input("Delay Reason", value=row.get("delay_reason") or "")
        notes = st.text_area("Notes", value=row.get("notes") or "")

        saved = st.form_submit_button("💾 Save Changes", type="primary", width='stretch')

        if saved:
            if not customer.strip():
                st.error("Customer Name is required.")
            else:
                conn.execute("""
                    UPDATE projects SET
                        customer=?, country=?, instrument=?, serial_number=?,
                        planned_golive=?, actual_golive=?, timeframe=?,
                        site_ready=?, reagent_ready=?, consumables_ready=?,
                        installation=?, connectivity=?, validation=?, training=?,
                        delay_reason=?, status=?, notes=?
                    WHERE id=?
                """, (
                    customer.strip(), country, instrument,
                    serial_number.strip() or None,
                    str(planned_golive) if planned_golive else None,
                    str(actual_golive) if actual_golive else None,
                    timeframe or None,
                    site_ready, reagent_ready, consumables_ready, installation,
                    connectivity, validation, training,
                    delay_reason.strip() or None,
                    status,
                    notes.strip() or None,
                    pid,
                ))
                conn.commit()
                st.success(f"✅ Project **{customer}** updated.")
                st.rerun()

# ── Bulk Import ───────────────────────────────────────────────────────────────

elif menu == "📥 Bulk Import":
    st.title("📥 Bulk Import Projects")
    st.caption("Upload a CSV or Excel file to import multiple go-live projects at once.")

    IMPORT_COLS = {
        "customer":           ("Customer", True),
        "country":            ("Country", True),
        "instrument":         ("Instrument", True),
        "serial_number":      ("Serial Number", False),
        "timeframe":          ("Timeframe", False),
        "planned_golive":     ("Proposed Go-Live", False),
        "actual_golive":      ("Actual Go-Live", False),
        "status":             ("Status", False),
        "site_ready":         ("Site Ready", False),
        "reagent_ready":      ("Reagent Ready", False),
        "consumables_ready":  ("Consumables Ready", False),
        "installation":       ("Installation", False),
        "connectivity":       ("Connectivity", False),
        "validation":         ("Validation", False),
        "training":           ("Training", False),
        "delay_reason":       ("Delay Reason", False),
        "notes":              ("Notes", False),
    }

    # ── Template download
    with st.expander("📄 Download Import Template", expanded=True):
        st.markdown(
            "Download the template, fill it in, then upload it below. "
            "**Bold columns are required.** All others are optional."
        )
        required = [v[0] for v in IMPORT_COLS.values() if v[1]]
        optional = [v[0] for v in IMPORT_COLS.values() if not v[1]]
        st.markdown(f"**Required:** {', '.join(required)}")
        st.markdown(f"Optional: {', '.join(optional)}")

        template_df = pd.DataFrame(columns=[v[0] for v in IMPORT_COLS.values()])
        sample = {
            "Customer": "City General Hospital",
            "Country": "Germany",
            "Instrument": "Atellica Solution",
            "Serial Number": "ATL-DE-001",
            "Timeframe": "1 year",
            "Proposed Go-Live": "2026-07-15",
            "Actual Go-Live": "",
            "Status": "On Track",
            "Site Ready": "Complete",
            "Reagent Ready": "In Progress",
            "Consumables Ready": "Pending",
            "Installation": "Pending",
            "Connectivity": "Pending",
            "Validation": "Pending",
            "Training": "Pending",
            "Delay Reason": "",
            "Notes": "Q3 priority site",
        }
        template_df = pd.concat([template_df, pd.DataFrame([sample])], ignore_index=True)

        t1, t2 = st.columns(2)

        csv_template = template_df.to_csv(index=False).encode("utf-8")
        t1.download_button(
            "📄 Download CSV Template",
            data=csv_template,
            file_name="golive_import_template.csv",
            mime="text/csv",
            width='stretch',
        )

        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            template_df.to_excel(writer, index=False, sheet_name="Import Template")
            ws = writer.sheets["Import Template"]
            for col_cells in ws.columns:
                max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
                ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 4, 40)
        t2.download_button(
            "📊 Download Excel Template",
            data=excel_buf.getvalue(),
            file_name="golive_import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width='stretch',
        )

    st.divider()

    # ── File upload
    uploaded = st.file_uploader(
        "Upload your filled template (CSV or Excel)",
        type=["csv", "xlsx", "xls"],
        help="Must match the template column names. Extra columns are ignored.",
    )

    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                raw_df = pd.read_csv(uploaded, dtype=str).fillna("")
            else:
                raw_df = pd.read_excel(uploaded, dtype=str).fillna("")
        except Exception as e:
            st.error(f"Could not read file: {e}")
            st.stop()

        # Normalise column names: map display names back to internal keys
        col_display_to_key = {v[0]: k for k, v in IMPORT_COLS.items()}
        raw_df.columns = [c.strip() for c in raw_df.columns]
        raw_df = raw_df.rename(columns=col_display_to_key)

        # Normalise date columns: Excel date cells arrive as "2026-05-15 00:00:00";
        # strip the time component so dates show and store cleanly as YYYY-MM-DD.
        def _norm_date(val):
            v = str(val).strip()
            if not v or v.lower() in ("nan", "nat", "none"):
                return ""
            parsed = pd.to_datetime(v, errors="coerce")
            return parsed.strftime("%Y-%m-%d") if pd.notna(parsed) else v

        for _dc in ("planned_golive", "actual_golive"):
            if _dc in raw_df.columns:
                raw_df[_dc] = raw_df[_dc].apply(_norm_date)

        st.subheader(f"Preview — {len(raw_df)} row(s) found")
        st.dataframe(raw_df, width='stretch', hide_index=True)

        # ── Validation
        errors = []
        warnings_list = []

        for i, row in raw_df.iterrows():
            row_num = i + 2
            if not str(row.get("customer", "")).strip():
                errors.append(f"Row {row_num}: **Customer** is required.")
            if not str(row.get("country", "")).strip():
                errors.append(f"Row {row_num}: **Country** is required.")
            if not str(row.get("instrument", "")).strip():
                errors.append(f"Row {row_num}: **Instrument** is required.")

            status_val = str(row.get("status", "")).strip()
            if status_val and status_val not in STATUS_OPTIONS:
                warnings_list.append(
                    f"Row {row_num}: Status **'{status_val}'** not recognised — will default to 'On Track'."
                )

            for col in READINESS_COLS:
                val = str(row.get(col, "")).strip()
                if val and val not in READINESS_OPTIONS:
                    warnings_list.append(
                        f"Row {row_num}: {col.replace('_', ' ').title()} **'{val}'** not recognised — will default to 'Pending'."
                    )

            for date_col in ("planned_golive", "actual_golive"):
                val = str(row.get(date_col, "")).strip()
                if val:
                    try:
                        datetime.strptime(val, "%Y-%m-%d")
                    except ValueError:
                        warnings_list.append(
                            f"Row {row_num}: {date_col} **'{val}'** is not a valid date (expected YYYY-MM-DD) — will be left blank."
                        )

        if errors:
            st.error("**Validation errors** — please fix these before importing:")
            for e in errors:
                st.markdown(f"- {e}")

        if warnings_list:
            with st.expander(f"⚠️ {len(warnings_list)} warning(s) — values will be corrected automatically"):
                for w in warnings_list:
                    st.markdown(f"- {w}")

        if not errors:
            st.divider()
            st.subheader("⚙️ Import Options")
            dup_mode = st.radio(
                "If a project with the same **Customer + Country + Instrument** already exists:",
                ["Skip duplicates", "Overwrite existing", "Always add as new"],
                horizontal=True,
            )

            if st.button("🚀 Import Projects", type="primary", width='stretch'):
                added = skipped = overwritten = 0

                for _, row in raw_df.iterrows():
                    customer   = str(row.get("customer", "")).strip()
                    country    = str(row.get("country", "")).strip()
                    instrument = str(row.get("instrument", "")).strip()
                    serial_number = str(row.get("serial_number", "")).strip() or None

                    def clean_date(val):
                        v = str(val).strip()
                        try:
                            datetime.strptime(v, "%Y-%m-%d")
                            return v
                        except Exception:
                            return None

                    def clean_status(val):
                        v = str(val).strip()
                        return v if v in STATUS_OPTIONS else "On Track"

                    def clean_readiness(val):
                        v = str(val).strip()
                        return v if v in READINESS_OPTIONS else "Pending"

                    planned_golive     = clean_date(row.get("planned_golive", ""))
                    actual_golive      = clean_date(row.get("actual_golive", ""))
                    tf_val             = str(row.get("timeframe", "")).strip()
                    timeframe          = tf_val if tf_val in TIMEFRAME_OPTIONS else None
                    status             = clean_status(row.get("status", ""))
                    site_ready         = clean_readiness(row.get("site_ready", ""))
                    reagent_ready      = clean_readiness(row.get("reagent_ready", ""))
                    consumables_ready  = clean_readiness(row.get("consumables_ready", ""))
                    installation       = clean_readiness(row.get("installation", ""))
                    connectivity       = clean_readiness(row.get("connectivity", ""))
                    validation         = clean_readiness(row.get("validation", ""))
                    training           = clean_readiness(row.get("training", ""))
                    delay_reason       = str(row.get("delay_reason", "")).strip() or None
                    notes              = str(row.get("notes", "")).strip() or None

                    existing = conn.execute(
                        "SELECT id FROM projects WHERE customer=? AND country=? AND instrument=?",
                        (customer, country, instrument)
                    ).fetchone()

                    if existing and dup_mode == "Skip duplicates":
                        skipped += 1
                        continue
                    elif existing and dup_mode == "Overwrite existing":
                        conn.execute("""
                            UPDATE projects SET
                                serial_number=?, planned_golive=?, actual_golive=?, timeframe=?, status=?,
                                site_ready=?, reagent_ready=?, consumables_ready=?,
                                installation=?, connectivity=?, validation=?, training=?,
                                delay_reason=?, notes=?
                            WHERE id=?
                        """, (
                            serial_number, planned_golive, actual_golive, timeframe, status,
                            site_ready, reagent_ready, consumables_ready,
                            installation, connectivity, validation, training,
                            delay_reason, notes, existing["id"]
                        ))
                        overwritten += 1
                    else:
                        conn.execute("""
                            INSERT INTO projects
                                (customer, country, instrument, serial_number, planned_golive, actual_golive,
                                 timeframe, status, site_ready, reagent_ready, consumables_ready,
                                 installation, connectivity, validation, training,
                                 delay_reason, notes)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            customer, country, instrument, serial_number,
                            planned_golive, actual_golive, timeframe, status,
                            site_ready, reagent_ready, consumables_ready,
                            installation, connectivity, validation, training,
                            delay_reason, notes
                        ))
                        added += 1

                conn.commit()

                parts = []
                if added:      parts.append(f"**{added}** project(s) added")
                if overwritten: parts.append(f"**{overwritten}** project(s) overwritten")
                if skipped:    parts.append(f"**{skipped}** duplicate(s) skipped")
                st.success("✅ Import complete — " + ", ".join(parts) + ".")
                st.balloons()

# ── Gantt Chart ───────────────────────────────────────────────────────────────

elif menu == "📅 Gantt Chart":
    st.title("📅 Gantt Chart — Deployment Timeline")
    st.caption("Visual timeline of all go-live projects, colour-coded by status.")

    df = load_projects()

    if df.empty:
        st.info("No projects yet. Add some via **➕ New Project** or **📥 Bulk Import** first.")
        st.stop()

    TIMEFRAME_DAYS = {
        "3 months": 90, "6 months": 180, "9 months": 270,
        "1 year": 365, "18 months": 548, "2 years": 730, "Other": 180,
    }

    gantt_rows = []
    for _, row in df.iterrows():
        proposed = pd.to_datetime(row.get("planned_golive"), errors="coerce")
        actual   = pd.to_datetime(row.get("actual_golive"), errors="coerce")
        tf       = row.get("timeframe", "") or ""
        duration = TIMEFRAME_DAYS.get(tf, 180)

        if pd.isna(proposed):
            continue

        start = proposed - pd.Timedelta(days=duration)
        end   = actual if (not pd.isna(actual)) else proposed

        label = f"{row['customer']} — {row['instrument']}"
        gantt_rows.append({
            "Task":      label,
            "Start":     start,
            "Finish":    end,
            "Status":    row.get("status", "On Track"),
            "Country":   row.get("country", ""),
            "Timeframe": tf or "—",
            "Proposed":  str(row.get("planned_golive", "")),
            "Actual":    str(row.get("actual_golive", "")) if row.get("actual_golive") else "—",
            "Readiness": f"{readiness_pct(row):.0f}%",
        })

    if not gantt_rows:
        st.warning("No projects have a Proposed Go-Live date set. Add dates to see the Gantt chart.")
        st.stop()

    gantt_df = pd.DataFrame(gantt_rows).sort_values("Start")

    # ── Filters
    with st.expander("🔍 Filter", expanded=False):
        f1, f2 = st.columns(2)
        sel_status  = f1.multiselect("Status", STATUS_OPTIONS, default=STATUS_OPTIONS)
        all_countries = sorted(gantt_df["Country"].unique())
        sel_country = f2.multiselect("Country", all_countries, default=all_countries)

    gantt_df = gantt_df[
        gantt_df["Status"].isin(sel_status) &
        gantt_df["Country"].isin(sel_country)
    ]

    if gantt_df.empty:
        st.info("No projects match the selected filters.")
        st.stop()

    color_map = {
        "On Track":  "#22c55e",
        "Delayed":   "#f97316",
        "Completed": "#3b82f6",
        "At Risk":   "#eab308",
        "On Hold":   "#6b7280",
    }

    fig = px.timeline(
        gantt_df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Status",
        color_discrete_map=color_map,
        hover_data={"Country": True, "Timeframe": True, "Proposed": True, "Actual": True, "Readiness": True, "Start": False, "Finish": False},
        title="",
    )

    fig.update_yaxes(autorange="reversed", tickfont=dict(size=12))
    fig.update_xaxes(
        title="",
        tickformat="%b %Y",
        tickangle=-30,
    )
    fig.update_layout(
        height=max(400, len(gantt_df) * 45 + 80),
        legend_title="Status",
        plot_bgcolor="#0f172a",
        paper_bgcolor="#0f172a",
        font_color="#f1f5f9",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=10, r=10, t=20, b=40),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b"),
    )

    # Today line
    fig.add_vline(
        x=pd.Timestamp.today(),
        line_dash="dash",
        line_color="#f43f5e",
        annotation_text="Today",
        annotation_font_color="#f43f5e",
        annotation_position="top right",
    )

    st.plotly_chart(fig, width='stretch')

    st.divider()
    st.caption(f"Showing **{len(gantt_df)}** project(s). Bar start = project kick-off (calculated from timeframe), bar end = Proposed or Actual Go-Live. Red dashed line = today.")

# ── World Map ─────────────────────────────────────────────────────────────────

elif menu == "🗺️ World Map":
    st.title("🗺️ World Map — Deployment Locations")
    st.caption("Each pin is a go-live project, colour-coded by status. Hover for details.")

    df = load_projects()

    if df.empty:
        st.info("No projects yet. Add some via **➕ New Project** or **📥 Bulk Import** first.")
        st.stop()

    COUNTRY_ISO = {
        "Argentina": "ARG", "Australia": "AUS", "Austria": "AUT", "Belgium": "BEL",
        "Brazil": "BRA", "Canada": "CAN", "Chile": "CHL", "China": "CHN",
        "Colombia": "COL", "Czech Republic": "CZE", "Denmark": "DNK", "Finland": "FIN",
        "France": "FRA", "Germany": "DEU", "Greece": "GRC", "Hungary": "HUN",
        "India": "IND", "Indonesia": "IDN", "Ireland": "IRL", "Israel": "ISR",
        "Italy": "ITA", "Japan": "JPN", "Malaysia": "MYS", "Mexico": "MEX",
        "Netherlands": "NLD", "New Zealand": "NZL", "Norway": "NOR", "Peru": "PER",
        "Philippines": "PHL", "Poland": "POL", "Portugal": "PRT", "Romania": "ROU",
        "Saudi Arabia": "SAU", "Singapore": "SGP", "South Africa": "ZAF",
        "South Korea": "KOR", "Spain": "ESP", "Sweden": "SWE", "Switzerland": "CHE",
        "Thailand": "THA", "Turkey": "TUR", "UAE": "ARE", "UK": "GBR",
        "USA": "USA", "Other": None,
    }

    COUNTRY_COORDS = {
        "Argentina": (-34.6, -58.4), "Australia": (-25.3, 133.8), "Austria": (47.8, 13.0),
        "Belgium": (50.5, 4.5), "Brazil": (-14.2, -51.9), "Canada": (56.1, -106.3),
        "Chile": (-35.7, -71.5), "China": (35.9, 104.2), "Colombia": (4.6, -74.1),
        "Czech Republic": (49.8, 15.5), "Denmark": (56.3, 9.5), "Finland": (61.9, 25.7),
        "France": (46.2, 2.2), "Germany": (51.2, 10.5), "Greece": (39.1, 21.8),
        "Hungary": (47.2, 19.5), "India": (20.6, 79.1), "Indonesia": (-0.8, 113.9),
        "Ireland": (53.4, -8.2), "Israel": (31.0, 35.0), "Italy": (41.9, 12.6),
        "Japan": (36.2, 138.3), "Malaysia": (4.2, 108.0), "Mexico": (23.6, -102.6),
        "Netherlands": (52.1, 5.3), "New Zealand": (-40.9, 174.9), "Norway": (60.5, 8.5),
        "Peru": (-9.2, -75.0), "Philippines": (12.9, 121.8), "Poland": (51.9, 19.1),
        "Portugal": (39.4, -8.2), "Romania": (45.9, 24.9), "Saudi Arabia": (23.9, 45.1),
        "Singapore": (1.4, 103.8), "South Africa": (-30.6, 22.9), "South Korea": (35.9, 127.8),
        "Spain": (40.5, -3.7), "Sweden": (60.1, 18.6), "Switzerland": (46.8, 8.2),
        "Thailand": (15.9, 100.9), "Turkey": (38.9, 35.2), "UAE": (23.4, 53.8),
        "UK": (55.4, -3.4), "USA": (37.1, -95.7),
    }

    df["readiness_pct"] = df.apply(readiness_pct, axis=1)

    # ── Filters
    c1, c2 = st.columns(2)
    sel_status  = c1.multiselect("Filter by Status", STATUS_OPTIONS, default=STATUS_OPTIONS)
    all_countries = sorted([c for c in df["country"].unique() if c in COUNTRY_COORDS])
    sel_country = c2.multiselect("Filter by Country", all_countries, default=all_countries)

    map_df = df[df["status"].isin(sel_status) & df["country"].isin(sel_country)].copy()

    if map_df.empty:
        st.info("No projects match the selected filters.")
        st.stop()

    map_df["lat"] = map_df["country"].map(lambda c: COUNTRY_COORDS.get(c, (None, None))[0])
    map_df["lon"] = map_df["country"].map(lambda c: COUNTRY_COORDS.get(c, (None, None))[1])
    map_df["readiness_str"] = map_df["readiness_pct"].apply(lambda x: f"{x:.0f}%")
    map_df["label"] = map_df["customer"] + " — " + map_df["instrument"]
    map_df["proposed_golive"] = map_df["planned_golive"].fillna("—")
    map_df["actual_golive_str"] = map_df["actual_golive"].fillna("—")
    map_df = map_df.dropna(subset=["lat", "lon"])

    color_map = {
        "On Track": "#22c55e", "Delayed": "#f97316",
        "Completed": "#3b82f6", "At Risk": "#eab308", "On Hold": "#6b7280",
    }

    # ── Scatter geo
    fig = px.scatter_geo(
        map_df,
        lat="lat",
        lon="lon",
        color="status",
        color_discrete_map=color_map,
        size="readiness_pct",
        size_max=28,
        hover_name="label",
        hover_data={
            "country": True,
            "status": True,
            "proposed_golive": True,
            "actual_golive_str": True,
            "readiness_str": True,
            "readiness_pct": False,
            "lat": False,
            "lon": False,
        },
        labels={
            "country": "Country",
            "status": "Status",
            "proposed_golive": "Proposed Go-Live",
            "actual_golive_str": "Actual Go-Live",
            "readiness_str": "Readiness",
        },
        projection="natural earth",
    )

    fig.update_geos(
        showland=True, landcolor="#1e293b",
        showocean=True, oceancolor="#0f172a",
        showcoastlines=True, coastlinecolor="#334155",
        showframe=False,
        showcountries=True, countrycolor="#334155",
        bgcolor="#0f172a",
    )
    fig.update_layout(
        height=560,
        paper_bgcolor="#0f172a",
        font_color="#f1f5f9",
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(
            title="Status",
            orientation="h",
            yanchor="bottom", y=0.02,
            xanchor="right", x=0.98,
            bgcolor="rgba(15,23,42,0.7)",
            bordercolor="#334155",
            borderwidth=1,
        ),
    )

    st.plotly_chart(fig, width='stretch')

    # ── Country summary table
    st.divider()
    st.subheader("📊 Projects by Country")
    country_summary = (
        map_df.groupby("country")
        .agg(
            Projects=("customer", "count"),
            Avg_Readiness=("readiness_pct", "mean"),
        )
        .reset_index()
        .rename(columns={"country": "Country", "Avg_Readiness": "Avg Readiness"})
        .sort_values("Projects", ascending=False)
    )
    country_summary["Avg Readiness"] = country_summary["Avg Readiness"].apply(lambda x: f"{x:.0f}%")
    st.dataframe(country_summary, width='stretch', hide_index=True)

# ── PDF Report ────────────────────────────────────────────────────────────────

elif menu == "📑 PDF Report":
    st.title("📑 PDF Report")
    st.caption("Generate a printable snapshot of all go-live projects.")

    df = load_projects()

    if df.empty:
        st.info("No projects yet. Add some via **➕ New Project** first.")
        st.stop()

    # ── Report options
    with st.expander("⚙️ Report Options", expanded=True):
        rc1, rc2, rc3 = st.columns(3)
        rpt_status   = rc1.multiselect("Filter by Status", STATUS_OPTIONS, default=STATUS_OPTIONS)
        rpt_country  = rc2.multiselect("Filter by Country", sorted(df["country"].unique()))
        rpt_sort     = rc3.selectbox("Sort by", ["Planned Go-Live", "Customer", "Country", "Status"])
        include_notes = st.checkbox("Include Notes column", value=True)

    # Apply filters
    rpt_df = df.copy()
    if rpt_status:
        rpt_df = rpt_df[rpt_df["status"].isin(rpt_status)]
    if rpt_country:
        rpt_df = rpt_df[rpt_df["country"].isin(rpt_country)]

    sort_map = {
        "Planned Go-Live": "planned_golive",
        "Customer": "customer",
        "Country": "country",
        "Status": "status",
    }
    rpt_df = rpt_df.sort_values(sort_map[rpt_sort], na_position="last")
    rpt_df["readiness_pct"] = rpt_df.apply(readiness_pct, axis=1).apply(lambda x: f"{x:.0f}%")

    st.subheader(f"Preview — {len(rpt_df)} project(s)")
    preview_cols = ["customer", "country", "instrument", "planned_golive", "status", "readiness_pct"]
    st.dataframe(
        rpt_df[preview_cols].rename(columns={
            "customer": "Customer", "country": "Country", "instrument": "Instrument",
            "planned_golive": "Planned Go-Live", "status": "Status", "readiness_pct": "Readiness",
        }),
        width='stretch',
        hide_index=True,
    )

    st.divider()

    if st.button("📑 Generate PDF", type="primary", width='stretch'):

        class GoLivePDF(FPDF):
            def header(self):
                self.set_font("Helvetica", "B", 14)
                self.set_text_color(0, 48, 99)
                self.cell(0, 10, "Atellica Go-Live Command Center", align="C", new_x="LMARGIN", new_y="NEXT")
                self.set_font("Helvetica", "", 9)
                self.set_text_color(100, 100, 100)
                self.cell(0, 6, f"Report generated: {datetime.now().strftime('%d %b %Y  %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")
                self.ln(3)
                self.set_draw_color(0, 48, 99)
                self.set_line_width(0.5)
                self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
                self.ln(4)

            def footer(self):
                self.set_y(-12)
                self.set_font("Helvetica", "I", 8)
                self.set_text_color(150, 150, 150)
                self.cell(0, 8, f"Page {self.page_no()} — Confidential", align="C")

        pdf = GoLivePDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        # ── Summary KPIs box
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(0, 0, 0)
        pdf.set_fill_color(240, 245, 255)
        pdf.cell(0, 7, "Summary", new_x="LMARGIN", new_y="NEXT", fill=True)
        pdf.set_font("Helvetica", "", 9)

        kpi_items = [
            ("Total Projects", str(len(rpt_df))),
            ("On Track",       str(len(rpt_df[rpt_df["status"] == "On Track"]))),
            ("Completed",      str(len(rpt_df[rpt_df["status"] == "Completed"]))),
            ("Delayed",        str(len(rpt_df[rpt_df["status"] == "Delayed"]))),
            ("At Risk",        str(len(rpt_df[rpt_df["status"] == "At Risk"]))),
        ]
        col_w = 50
        for label, val in kpi_items:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(col_w, 6, f"{label}: ", new_x="RIGHT", new_y="LAST")
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(col_w, 6, val, new_x="RIGHT", new_y="LAST")
        pdf.ln(8)

        # ── Table header
        READINESS_LABELS = {
            "site_ready": "Site",
            "reagent_ready": "Reagents",
            "consumables_ready": "Consumables",
            "installation": "Install",
            "connectivity": "Connect",
            "validation": "Validation",
            "training": "Training",
        }

        base_cols = [
            ("Customer",      48),
            ("Country",       28),
            ("Instrument",    34),
            ("Planned GL",    24),
            ("Status",        22),
            ("Readiness",     18),
        ]
        readiness_cols_pdf = [(lbl, 18) for lbl in READINESS_LABELS.values()]
        if include_notes:
            notes_col = [("Notes", 40)]
        else:
            notes_col = []

        all_cols = base_cols + readiness_cols_pdf + notes_col

        pdf.set_font("Helvetica", "B", 7)
        pdf.set_fill_color(0, 48, 99)
        pdf.set_text_color(255, 255, 255)
        for col_name, col_w in all_cols:
            pdf.cell(col_w, 6, col_name, border=0, fill=True, new_x="RIGHT", new_y="LAST")
        pdf.ln()

        # ── Table rows
        STATUS_SHADE = {
            "On Track":  (220, 250, 220),
            "Completed": (220, 235, 255),
            "Delayed":   (255, 220, 220),
            "At Risk":   (255, 235, 200),
            "On Hold":   (235, 235, 235),
        }
        READY_DOT = {
            "Complete":    "✓",
            "In Progress": "~",
            "Blocked":     "✗",
            "Pending":     "·",
        }

        pdf.set_font("Helvetica", "", 7)
        for idx, (_, row) in enumerate(rpt_df.iterrows()):
            fill_color = STATUS_SHADE.get(str(row.get("status", "")), (255, 255, 255))
            pdf.set_fill_color(*fill_color)
            pdf.set_text_color(0, 0, 0)

            def cell(text, w):
                text = str(text) if text and str(text) not in ("None", "nan") else ""
                pdf.cell(w, 5, text[:30], border=0, fill=True, new_x="RIGHT", new_y="LAST")

            cell(row.get("customer", ""), 48)
            cell(row.get("country", ""), 28)
            cell(row.get("instrument", ""), 34)
            cell(row.get("planned_golive", ""), 24)
            cell(row.get("status", ""), 22)
            cell(row.get("readiness_pct", ""), 18)

            for col_key in READINESS_LABELS:
                val = str(row.get(col_key, "Pending"))
                dot = READY_DOT.get(val, "·")
                if val == "Complete":
                    pdf.set_text_color(34, 139, 34)
                elif val == "Blocked":
                    pdf.set_text_color(200, 0, 0)
                elif val == "In Progress":
                    pdf.set_text_color(200, 120, 0)
                else:
                    pdf.set_text_color(150, 150, 150)
                pdf.cell(18, 5, dot, border=0, fill=True, new_x="RIGHT", new_y="LAST", align="C")
                pdf.set_text_color(0, 0, 0)

            if include_notes:
                notes_val = str(row.get("notes", "")) if row.get("notes") not in (None, "None", "nan", "") else ""
                cell(notes_val, 40)

            pdf.ln()

            # Thin separator every 5 rows
            if (idx + 1) % 5 == 0:
                pdf.set_draw_color(200, 200, 200)
                pdf.set_line_width(0.1)
                pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())

        # ── Legend
        pdf.ln(4)
        pdf.set_font("Helvetica", "I", 7)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 5, "Readiness legend:  ✓ Complete   ~ In Progress   ✗ Blocked   · Pending", new_x="LMARGIN", new_y="NEXT")

        pdf_bytes = bytes(pdf.output())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")

        st.download_button(
            label="⬇️ Download PDF Report",
            data=pdf_bytes,
            file_name=f"atellica_golive_report_{timestamp}.pdf",
            mime="application/pdf",
            width='stretch',
            type="primary",
        )
        st.success("✅ PDF ready — click the button above to download.")
