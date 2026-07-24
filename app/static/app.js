"use strict";

const map = L.map("map", { zoomControl: true }).setView([40.4168, -3.7038], 6);

L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution:
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
  maxZoom: 20,
}).addTo(map);

const layer = L.layerGroup().addTo(map);

const BATTERY = { 0: "Full", 1: "Medium", 2: "Low", 3: "Very low" };

let tz = undefined;
let currentDays = 7;
let autoTimer = null;

function fmtTime(unix) {
  return new Date(unix * 1000).toLocaleString("en-GB", {
    day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
    timeZone: tz,
  });
}

function batteryLabel(status) {
  return BATTERY[(status >> 6) & 0b11] ?? "?";
}

function relative(unix) {
  const secs = Math.floor(Date.now() / 1000 - unix);
  if (secs < 60) return "seconds ago";
  if (secs < 3600) return `${Math.floor(secs / 60)} min ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)} h ago`;
  return `${Math.floor(secs / 86400)} d ago`;
}

async function loadStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    tz = s.tz || undefined;
    document.getElementById("stat-tz").textContent = s.tz || "–";
    document.getElementById("stat-count").textContent = s.count ?? 0;
    document.getElementById("stat-health").textContent = s.last_error
      ? "⚠ error"
      : s.configured ? "✓ ok" : "not configured";
    document.getElementById("stat-health").title = s.last_error || "";
  } catch (_) {
    document.getElementById("stat-health").textContent = "offline";
  }
}

async function loadPoints() {
  const url = currentDays > 0 ? `/api/points?days=${currentDays}` : "/api/points";
  const points = await (await fetch(url)).json();
  layer.clearLayers();

  if (!points.length) {
    document.getElementById("stat-last").textContent = "no data";
    document.getElementById("stat-batt").textContent = "–";
    return;
  }

  const latlngs = points.map((p) => [p.lat, p.lon]);

  L.polyline(latlngs, { color: "#ff7a45", weight: 2.5, opacity: 0.75 }).addTo(layer);

  points.forEach((p, i) => {
    const isLast = i === points.length - 1;
    if (isLast) return; // drawn separately below
    L.circleMarker([p.lat, p.lon], {
      radius: 4, color: "#ff7a45", weight: 1, fillColor: "#ff7a45", fillOpacity: 0.5,
    })
      .bindPopup(`${fmtTime(p.ts)}<br>±${p.accuracy} m`)
      .addTo(layer);
  });

  const last = points[points.length - 1];
  L.circleMarker([last.lat, last.lon], {
    radius: 8, color: "#fff", weight: 2, fillColor: "#ff7a45", fillOpacity: 1,
  })
    .bindPopup(
      `<b>Last position</b><br>${fmtTime(last.ts)} (${relative(last.ts)})<br>` +
        `±${last.accuracy} m · battery: ${batteryLabel(last.status)}`
    )
    .addTo(layer)
    .openPopup();
  L.circle([last.lat, last.lon], {
    radius: Math.max(last.accuracy, 10), color: "#ff7a45", weight: 1, fillOpacity: 0.08,
  }).addTo(layer);

  map.fitBounds(L.latLngBounds(latlngs).pad(0.2));

  document.getElementById("stat-last").textContent = relative(last.ts);
  document.getElementById("stat-batt").textContent = batteryLabel(last.status);
}

async function refresh() {
  await Promise.all([loadStatus(), loadPoints()]);
}

document.querySelectorAll(".ranges button").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".ranges button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentDays = Number(btn.dataset.days);
    loadPoints();
  });
});

document.getElementById("autorefresh").addEventListener("change", (e) => {
  if (e.target.checked) {
    autoTimer = setInterval(refresh, 60000);
  } else {
    clearInterval(autoTimer);
    autoTimer = null;
  }
});

autoTimer = setInterval(refresh, 60000);
refresh();
