# === GRAPH (SMOOTH + STYLED) ===
fig = px.line(
    df_view,
    x="Time",
    y="Solar Yield (W/m²)",
    title=f"☀️ Global Horizontal Irradiance — {loc['name']} ({view_mode})",
    labels={"Solar Yield (W/m²)": "Yield (W/m²)", "Time": "Hour of Day"},
)

# Style the line and markers
fig.update_traces(
    line=dict(color="rgba(0, 123, 255, 0.5)", width=3),
    mode="lines+markers",
    marker=dict(
        size=10,
        color="rgba(0, 123, 255, 0.6)",
        line=dict(width=1.5, color="white"),
    ),
    hovertemplate="Time: %{x|%H:%M}<br>Yield: %{y:.0f} W/m²<extra></extra>",
    line_shape="spline",  # ✅ smoother curve
)

# Smooth layout style — clean and modern look
fig.update_layout(
    height=420,
    margin=dict(l=30, r=30, t=60, b=40),
    title_x=0.5,
    plot_bgcolor="white",
    paper_bgcolor="white",
    hovermode="x unified",
    xaxis=dict(
        showgrid=False,
        showline=False,
        tickformat="%H:%M",
        tickfont=dict(size=13),
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor="rgba(200,200,200,0.3)",
        zeroline=False,
        tickfont=dict(size=13),
    ),
)

# Interactive controls (minimal for clean feel)
config = {
    "displayModeBar": False,
    "scrollZoom": False,
}
