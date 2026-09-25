"""
UrbanPulse Bengaluru — interactive dashboard
Satellite-based analysis of lake loss, urban heat, flood risk and groundwater
across Bengaluru's 225 BBMP wards.

Run locally:  streamlit run app.py
Needs:        urbanpulse_wards.geojson in the same folder
"""

import branca.colormap as cm
import folium
import geopandas as gpd
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

st.set_page_config(page_title="UrbanPulse Bengaluru", page_icon="🌆", layout="wide")

DATA_PATH = "urbanpulse_wards.geojson"

# Map layers: column, colour ramp (low -> high), short explanation
LAYERS = {
    "Combined vulnerability": ("vulnerability", ["#1a9850", "#fee08b", "#d73027"],
                               "average of heat, flood and lake-loss scores"),
    "Heat (day + night)": ("heat_score", ["#ffffcc", "#fd8d3c", "#800026"],
                           "percentile of day and night surface temperature"),
    "Flood susceptibility": ("flood_score", ["#f7fbff", "#6baed6", "#08306b"],
                             "percentile of terrain-based flood risk"),
    "Lake loss": ("lake_score", ["#fcfbfd", "#9e9ac8", "#3f007d"],
                  "wards with at least 5 ha of lost lake area"),
}

ACTION_INFO = {
    "Lake restoration & recharge": "Significant lake area lost in flood-prone ground. Desilt, clear and "
                                   "reconnect lakes to restore storage, cooling and groundwater recharge.",
    "Urban greening": "Hot ward with little tree cover. Street trees, pocket parks and green roofs "
                      "would lower surface temperatures.",
    "Drainage upgrade": "Dense, built-up ward on flood-prone terrain. Storm-water drains and "
                        "permeable surfaces would reduce waterlogging.",
    "Priority: flood mitigation": "Flood risk is this ward's dominant stress. Prioritise drainage "
                                  "capacity and protecting low-lying areas.",
    "Priority: lake revival": "Lake loss is this ward's dominant stress. Prioritise reviving "
                              "remaining water bodies and recharge zones.",
    "Priority: heat mitigation": "Heat is this ward's dominant stress. Prioritise shade, trees "
                                 "and cool surfaces.",
    "Maintain / monitor": "No major overlapping stress detected. Keep monitoring.",
}

NUMERIC_COLS = ["population", "area_km2", "lst_day", "lst_night", "flood", "lost_frac", "tree",
                "built", "lost_lake_km2", "pop_density", "heat_score", "flood_score",
                "lake_score", "vulnerability", "rank"]


@st.cache_data
def load_wards():
    gdf = gpd.read_file(DATA_PATH)
    gdf["geometry"] = gdf.geometry.simplify(0.0001, preserve_topology=True)
    for c in NUMERIC_COLS:
        if c in gdf.columns:
            gdf[c] = pd.to_numeric(gdf[c], errors="coerce")
    gdf["rank"] = gdf["rank"].astype(int)
    gdf["action"] = gdf["action"].fillna("Maintain / monitor")
    return gdf


wards = load_wards()
n_wards = len(wards)
n_top = int(n_wards * 0.2)
names = sorted(wards["name_en"].dropna().unique())

# ---------- Ward selection state (dropdown + map clicks) ----------
if "pending_ward" in st.session_state:
    st.session_state["ward"] = st.session_state.pop("pending_ward")
if "ward" not in st.session_state:
    st.session_state["ward"] = wards.sort_values("rank").iloc[0]["name_en"]

# ---------- Sidebar ----------
with st.sidebar:
    st.title("🌆 UrbanPulse")
    st.caption("Heat, floods and lost lakes in Bengaluru, mapped from space.")
    layer_name = st.radio("Map layer", list(LAYERS))
    st.selectbox("Find a ward", names, key="ward")
    st.caption("Tip: you can also click a ward on the map.")
    st.markdown("---")
    st.caption("Data: Landsat 5/7/8/9, MODIS, ESA WorldCover, JRC Global Surface Water, "
               "MERIT Hydro, Copernicus DEM, GRACE / GLDAS, CHIRPS, BBMP 2023 wards (OpenCity).")

ward_name = st.session_state["ward"]

# ---------- Header ----------
st.title("UrbanPulse Bengaluru")
st.markdown("**How lost lakes, heat and flooding overlap across Bengaluru's "
            f"{n_wards} wards**, built from 25 years of satellite data.")

top_pop = wards.loc[wards["rank"] <= n_top, "population"].sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Lake extent change", "−26%", help="Water present in ≥25% of clear observations, "
          "1999–2003 vs 2020–2024 (≈12 km² net loss).")
c2.metric("Summer surface warming", "+0.5 °C", help="Mean land surface temperature, "
          "March–May 2014 vs 2024 (Landsat).")
c3.metric("Lost lakes in flood zones", "60%", help="Share of lost-lake area inside the "
          "top-20% flood-susceptibility zone.")
c4.metric("People at highest risk", f"≈{top_pop / 1e5:.1f} lakh",
          help=f"Population of the {n_top} most vulnerable wards (census-based, so approximate).")

map_tab, top_tab, findings_tab, method_tab = st.tabs(
    ["🗺️ Ward map", "📊 Most vulnerable wards", "🔍 Key findings", "⚙️ Methodology"])

# ---------- Map tab ----------
with map_tab:
    map_col, card_col = st.columns([3, 2], gap="large")

    with map_col:
        col, colors, caption = LAYERS[layer_name]
        cmap = cm.LinearColormap(colors, vmin=float(wards[col].min()), vmax=float(wards[col].max()),
                                 caption=f"{layer_name}: {caption}")

        display = wards[["name_en", "rank", "vulnerability", "action", col, "geometry"]].copy()
        display = display.loc[:, ~display.columns.duplicated()]
        display["vuln_txt"] = display["vulnerability"].round(2)
        display[col] = display[col].fillna(0)

        m = folium.Map(location=[12.97, 77.59], zoom_start=11, tiles="OpenStreetMap")
        m.fit_bounds([[12.83, 77.46], [13.14, 77.78]])

        def style(feature):
            v = feature["properties"].get(col)
            return {"fillColor": cmap(v) if v is not None else "#cccccc",
                    "color": "#555555", "weight": 0.4, "fillOpacity": 0.75}

        folium.GeoJson(
            display,
            style_function=style,
            highlight_function=lambda f: {"weight": 2, "color": "#000000"},
            tooltip=folium.GeoJsonTooltip(fields=["name_en", "rank", "vuln_txt", "action"],
                                          aliases=["Ward", "Rank", "Vulnerability", "Action"]),
        ).add_to(m)

        selected = wards[wards["name_en"] == ward_name][["name_en", "geometry"]]
        folium.GeoJson(selected, style_function=lambda f: {"fillOpacity": 0, "color": "#000000",
                                                           "weight": 3}).add_to(m)
        st.caption(f"**{layer_name}**: {caption}. Green/light = lower, red/dark = higher.")

        out = st_folium(m, height=620, use_container_width=True,
                        returned_objects=["last_active_drawing"], key="map")

        clicked = (out or {}).get("last_active_drawing")
        if clicked:
            cname = clicked.get("properties", {}).get("name_en")
            if cname and cname != ward_name and cname != st.session_state.get("last_click"):
                st.session_state["last_click"] = cname
                st.session_state["pending_ward"] = cname
                st.rerun()

    with card_col:
        r = wards[wards["name_en"] == ward_name].iloc[0]
        med = wards[NUMERIC_COLS].median()

        st.subheader(ward_name)
        st.markdown(f"**Rank {r['rank']} of {n_wards}** · vulnerability score **{r['vulnerability']:.2f}**")
        st.progress(min(max(float(r["vulnerability"]), 0.0), 1.0))

        a, b = st.columns(2)
        a.metric("Day surface temp", f"{r['lst_day']:.1f} °C",
                 f"{r['lst_day'] - med['lst_day']:+.1f} °C vs median", delta_color="inverse")
        b.metric("Night surface temp", f"{r['lst_night']:.1f} °C",
                 f"{r['lst_night'] - med['lst_night']:+.1f} °C vs median", delta_color="inverse")
        a.metric("Flood score", f"{r['flood']:.2f}",
                 f"{r['flood'] - med['flood']:+.2f} vs median", delta_color="inverse")
        b.metric("Lost lake area", f"{r['lost_lake_km2'] * 100:.0f} ha")
        a.metric("Tree cover", f"{r['tree'] * 100:.0f}%",
                 f"{(r['tree'] - med['tree']) * 100:+.0f} pts vs median")
        b.metric("Built-up", f"{r['built'] * 100:.0f}%")

        if pd.notna(r["population"]):
            st.caption(f"Population (census-based): {int(r['population']):,}")

        st.markdown("#### Recommended action")
        for act in str(r["action"]).split(", "):
            st.info(f"**{act}**: {ACTION_INFO.get(act, '')}")

# ---------- Top wards tab ----------
with top_tab:
    n = st.slider("Show top N wards", 10, 50, 20)
    top = wards.sort_values("rank").head(n)
    table = top[["rank", "name_en", "vulnerability", "lst_day", "lst_night", "flood",
                 "lost_lake_km2", "population", "action"]].rename(columns={
        "rank": "Rank", "name_en": "Ward", "vulnerability": "Vulnerability",
        "lst_day": "Day LST (°C)", "lst_night": "Night LST (°C)", "flood": "Flood score",
        "lost_lake_km2": "Lost lake (km²)", "population": "Population", "action": "Recommended action"})

    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "Vulnerability": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
            "Day LST (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Night LST (°C)": st.column_config.NumberColumn(format="%.1f"),
            "Flood score": st.column_config.NumberColumn(format="%.2f"),
            "Lost lake (km²)": st.column_config.NumberColumn(format="%.2f"),
            "Population": st.column_config.NumberColumn(format="%d"),
        })

    st.markdown("#### Recommended actions across all wards")
    st.bar_chart(wards["action"].value_counts())

    st.download_button("Download all ward scores (CSV)",
                       wards.drop(columns="geometry").to_csv(index=False),
                       "urbanpulse_ward_scores.csv", "text/csv")

# ---------- Findings tab ----------
with findings_tab:
    st.markdown("""
### 1. Heat
- Mean summer surface temperature rose **≈0.5 °C** (2014→2024), with the strongest warming in the south and south-east growth corridors.
- By day, **dry open land is hottest** (≈44.5 °C), hotter than built-up areas (≈41 °C): a "hot fringe, cooler core" pattern.
- **At night the pattern reverses**: built-up areas are warmest and cool ≈3 °C less overnight than cropland.
- Water and wetlands are the strongest coolers, ≈6.5–8 °C cooler than built-up areas by day.

### 2. Lost lakes
- Lake extent fell **≈26%** (≈45.8 → 33.8 km²) between 1999–2003 and 2020–2024, using a 5-year water-frequency method robust to drought years.
- A single-season comparison had suggested −39%, inflated by the 2023 drought; the JRC Global Surface Water dataset independently records ≈14 km² of lost or degraded water.

### 3. Flood risk
- Lost lakes sit in the city's lowest terrain: mean height above nearest drainage **≈1.2 m vs ≈12.7 m** city-wide.
- **60%** of lost-lake area falls in the top-20% flood-risk zone, three times what chance would predict.
- Only **≈1%** of lost-lake area is built over; most became tree cover, cropland or shrubland, so **most lost lakes remain restorable**.

### 4. Groundwater
- Regional groundwater storage (GLDAS, GRACE-assimilated) shows **no significant long-term decline** over 2003–2025.
- End-of-monsoon storage change tracks annual rainfall closely (**r ≈ 0.68**); the 2023 drought caused one of the largest drops, just before the 2024 water crisis.
- The local crisis reflects heavy extraction from small hard-rock aquifers and reduced recharge, below what satellites can resolve.

### 5. What drives heat (machine learning)
- A Random Forest predicts surface temperature with **R² ≈ 0.73** on spatially held-out areas (RMSE ≈ 1.65 °C).
- SHAP analysis: bare/hard surfaces (NDBI) are the main heating factor; tree cover and surface moisture are the main cooling factors.
""")

# ---------- Methodology tab ----------
with method_tab:
    st.markdown("""
### Data
| Theme | Source |
|---|---|
| Surface temperature | Landsat 8/9 thermal (day), MODIS MOD11A2 (day and night) |
| Vegetation, built-up, water indices | Landsat 5/7/8/9 surface reflectance (NDVI, NDBI, MNDWI) |
| Land cover | ESA WorldCover 2021 (10 m) |
| Long-term water history | JRC Global Surface Water 1984–2021 |
| Terrain and drainage | Copernicus DEM (30 m), MERIT Hydro (HAND, upstream area) |
| Groundwater | GLDAS 2.2 CLSM (GRACE-assimilated), GRACE / GRACE-FO mascons |
| Rainfall | CHIRPS daily |
| Wards | BBMP 2023 delimitation, 225 wards (OpenCity) |

### Ward vulnerability index
- **Heat score**: average of the percentile ranks of day and night surface temperature.
- **Flood score**: percentile rank of a susceptibility index (HAND 40%, slope 20%, upstream area 20%, built-up density 20%).
- **Lake score**: percentile rank of lost lake area, counted only for wards with ≥5 ha lost.
- **Vulnerability** = equal-weight average of the three scores.

### Caveats
- Surface temperature is not air temperature.
- Some "lost" lakes may be weed-covered rather than drained.
- Satellite groundwater data is regional (≈27 km) and cannot resolve individual borewells.
- Population figures are census-based estimates.
- Index weights are transparent assumptions, not calibrated against observed flood events.
""")
