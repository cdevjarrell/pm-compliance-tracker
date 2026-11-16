"""Settings page: edit the asset list and which cells are tracked each month."""

from datetime import date

import streamlit as st

from pmtracker.settings import (
    MONTH_NAMES,
    load_assets,
    load_scope,
    save_assets,
    save_scope,
    scope_grid,
    update_scope_year,
    validate_assets,
)

st.set_page_config(page_title="Settings", layout="wide")
st.title("Settings")

assets_tab, scope_tab = st.tabs(["Assets", "Tracking scope"])

# ---------- Assets ----------
with assets_tab:
    st.write("Each ObjectID belongs to one cell. Add a row at the bottom, or select rows and delete them.")
    st.caption("Changes apply to the next import. Re-import your exports to update work orders already saved.")
    
    edited = st.data_editor(
        load_assets(),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        key="assets_editor",
        column_config={
            "object_id": st.column_config.TextColumn("ObjectID", required=True),
            "description": st.column_config.TextColumn("Description"),
            "cell": st.column_config.TextColumn("Cell", required=True),
        },
    )
    
    if st.button("Save assets", type="primary"):
        clean, errors = validate_assets(edited)
        if errors:
            for message in errors:
                st.error(message)
        else:
            save_assets(clean)
            st.success(f"Saved {len(clean)} assets.")

# ---------- Tracking Scope ----------
with scope_tab:
    st.write("Checked means the cell counts toward totals that month. Unchecked cells are left out of every total.")
    
    this_year = date.today().year
    year = st.selectbox("Year", list(range(this_year - 2, this_year + 2)), index=2)
    
    scope = load_scope()
    cells = sorted(set(load_assets()["cell"]) | {cell for _, cell in scope})
    grid = scope_grid(scope, year, cells)
    
    edited_grid = st.data_editor(
        grid,
        width="stretch",
        key=f"scope_editor_{year}",
        column_config={name: st.column_config.CheckboxColumn(name) for name in MONTH_NAMES},
        
    )
    
    if st.button("Save scope", type="primary"):
        save_scope(update_scope_year(scope, year, edited_grid))
        st.success(f"Saved tracking scope for {year}.")