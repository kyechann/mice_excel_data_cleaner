# sections/draggable_dashboard.py
import streamlit as st
import streamlit.components.v1 as components
from streamlit_elements import elements, dashboard, mui

def _normalize_layout(layout):
    """dashboard.Grid가 받는 형태(dashboard.Item 리스트)로 맞춰줌"""
    items = []
    for it in layout:
        if isinstance(it, dashboard.Item):
            items.append(it)
        else:
            # it: dict 형태 {"i","x","y","w","h",...} 로 들어올 수 있음
            items.append(dashboard.Item(it["i"], it["x"], it["y"], it["w"], it["h"]))
    return items

def render_draggable_charts(fig_map: dict, layout_key: str):
    if layout_key not in st.session_state:
        st.session_state[layout_key] = [
            dashboard.Item("trend", 0, 0, 6, 4),
            dashboard.Item("cum",   6, 0, 6, 4),
            dashboard.Item("stack", 0, 4, 6, 4),
            dashboard.Item("heat",  6, 4, 6, 4),
        ]

    def _on_layout_change(new_layout):
        st.session_state[layout_key] = new_layout

    layout_items = st.session_state[layout_key]
    item_ids = {it.i if hasattr(it, "i") else it["i"] for it in layout_items}

    with elements(f"dash_{layout_key}"):
        with dashboard.Grid(
            layout_items,
            cols=12,
            rowHeight=80,
            draggableHandle=".drag-handle",
            onLayoutChange=_on_layout_change,
        ):
            for key, fig in fig_map.items():
                if key not in item_ids:
                    continue

                with mui.Paper(key=key, elevation=3, sx={"borderRadius": 12, "overflow": "hidden"}):
                    mui.Box(
                        className="drag-handle",
                        sx={"px": 1.5, "py": 1, "cursor": "move", "fontWeight": 700},
                        children=[key],
                    )

                    # ✅ Plotly를 HTML로 렌더 (가장 호환성 좋음)
                    html = fig.to_html(include_plotlyjs="cdn", full_html=False)
                    # height는 grid(h*rowHeight)랑 맞춰주면 좋음 (대충 320~500 사이)
                    components.html(html, height=420, scrolling=False)