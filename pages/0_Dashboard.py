"""Dashboard - Overview of all active projects with checklists."""
import streamlit as st

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.models import load_projects, save_projects


def get_completion_pct(checklist: list[dict]) -> float:
    if not checklist:
        return 0.0
    done = sum(1 for item in checklist if item.get("done", False))
    return done / len(checklist)


st.title("📊 Dashboard")

# Load projects
projects = load_projects()

if not projects:
    st.info("No projects yet. Go to **New Order** to create your first project.")
    st.stop()

# --- Filters ---
col_filter1, col_filter2 = st.columns(2)
with col_filter1:
    status_filter = st.selectbox("Status", ["active", "completed", "archived", "all"], index=0)
with col_filter2:
    priority_filter = st.selectbox("Priority", ["all", "URGENT", "Normal"], index=0)

# Filter projects
filtered = projects
if status_filter != "all":
    filtered = [p for p in filtered if p.get("status", "active") == status_filter]
if priority_filter != "all":
    filtered = [p for p in filtered if p.get("order", {}).get("priority", "") == priority_filter]

# Sort: URGENT first, then by creation date
filtered.sort(key=lambda p: (
    0 if p.get("order", {}).get("priority", "") == "URGENT" else 1,
    p.get("created_at", ""),
))

st.markdown(f"**{len(filtered)} projects** shown")
st.markdown("---")

# --- Project Cards ---
changed = False

for i, project in enumerate(filtered):
    order = project.get("order", {})
    checklist = project.get("checklist", [])
    pct = get_completion_pct(checklist)
    priority = order.get("priority", "Normal")
    pcb_name = order.get("pcb_name", "Unknown")
    pcb_type = order.get("pcb_type", "Rigid")
    quantity = order.get("quantity", 0)
    created = project.get("created_at", "")
    project_id = project.get("id", "?")
    status = project.get("status", "active")

    priority_badge = "🔴 URGENT" if priority == "URGENT" else "🟢 Normal"
    type_badge = "🔵 FPC" if pcb_type == "FPC" else "⬜ Rigid"

    with st.expander(
        f"{priority_badge} | **{pcb_name}** | {type_badge} | Qty: {quantity} | {pct:.0%} done | {created}",
        expanded=(pct < 1.0 and status == "active"),
    ):
        info_col1, info_col2, info_col3 = st.columns(3)
        with info_col1:
            st.markdown(f"**ID:** `{project_id}`")
            st.markdown(f"**Engineer:** {order.get('engineer', 'N/A')}")
            st.markdown(f"**Recipient:** {order.get('recipient', 'N/A')}")
        with info_col2:
            st.markdown(f"**Layers:** {order.get('layers', 'N/A')}")
            st.markdown(f"**Thickness:** {order.get('thickness', 'N/A')}")
            st.markdown(f"**Solder Mask:** {order.get('solder_mask_color', 'N/A')}")
        with info_col3:
            new_smt = st.text_input("SMT Route", value=project.get("smt_route", ""), key=f"smt_{project_id}")
            new_eta = st.text_input("ETA", value=project.get("eta", ""), key=f"eta_{project_id}")
            new_vendor = st.text_input("Vendor Order #", value=project.get("vendor_order_number", ""), key=f"vendor_{project_id}")

            if new_smt != project.get("smt_route", "") or new_eta != project.get("eta", "") or new_vendor != project.get("vendor_order_number", ""):
                project["smt_route"] = new_smt
                project["eta"] = new_eta
                project["vendor_order_number"] = new_vendor
                changed = True

        st.progress(pct)

        st.markdown("**Checklist:**")
        for j, item in enumerate(checklist):
            new_val = st.checkbox(
                item["text"],
                value=item.get("done", False),
                key=f"chk_{project_id}_{item['id']}",
            )
            if new_val != item.get("done", False):
                item["done"] = new_val
                changed = True

        new_notes = st.text_area(
            "Notes",
            value=project.get("notes", ""),
            key=f"notes_{project_id}",
            height=80,
        )
        if new_notes != project.get("notes", ""):
            project["notes"] = new_notes
            changed = True

        action_col1, action_col2, action_col3 = st.columns(3)
        with action_col1:
            if status == "active" and st.button("Mark Completed", key=f"complete_{project_id}"):
                project["status"] = "completed"
                changed = True
        with action_col2:
            if status == "completed" and st.button("Reopen", key=f"reopen_{project_id}"):
                project["status"] = "active"
                changed = True
        with action_col3:
            if st.button("Archive", key=f"archive_{project_id}"):
                project["status"] = "archived"
                changed = True

if changed:
    save_projects(projects)
    st.rerun()
