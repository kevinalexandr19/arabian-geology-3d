/* Arabia 3D — MapLibre viewer. No basemap: background colour + own layers only. */

const TERRAIN_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const TERRAIN_ATTR =
  'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen Terrain Tiles (AWS Open Data)</a>; ' +
  'SRTM and GMTED2010 courtesy of the U.S. Geological Survey, ETOPO1 by NOAA ' +
  '(<a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md">full credits</a>)';
const GEO_ATTR = '<a href="https://doi.org/10.3133/ofr97470B">USGS OFR 97-470B (geo2bg)</a>';
const NE_ATTR = '<a href="https://www.naturalearthdata.com/">Natural Earth</a>';
const OSM_ATTR = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)';

const DEFAULT_EXAG = 1.5;
const DEFAULT_OPACITY = 0.75;
const PENINSULA = [[34.4, 12.4], [60.0, 32.2]];

const FONT = ['Noto Sans Regular'];
const FONT_BOLD = ['Noto Sans Bold'];

const demSource = () => ({
  type: 'raster-dem',
  tiles: [TERRAIN_TILES],
  encoding: 'terrarium',
  tileSize: 256,
  maxzoom: 15,
  attribution: TERRAIN_ATTR,
});

const isPhone = () => window.matchMedia('(max-width: 700px)').matches;

const style = {
  version: 8,
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {
    // Two sources on the same tiles: MapLibre recommends separate sources for terrain and hillshade.
    'dem-terrain': demSource(),
    'dem-hillshade': demSource(),
    geology: { type: 'geojson', data: 'data/geology.geojson', attribution: GEO_ATTR },
    roads: { type: 'geojson', data: 'data/roads.geojson', attribution: OSM_ATTR },
    cities: { type: 'geojson', data: 'data/cities.geojson', attribution: NE_ATTR },
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#d7dde2' } },
    {
      id: 'geology-fill', type: 'fill', source: 'geology',
      paint: { 'fill-color': ['get', 'level1_colour'], 'fill-opacity': DEFAULT_OPACITY },
    },
    {
      id: 'hillshade', type: 'hillshade', source: 'dem-hillshade',
      paint: {
        'hillshade-exaggeration': 0.55,
        'hillshade-shadow-color': 'rgba(20, 20, 30, 0.55)',
        'hillshade-highlight-color': 'rgba(255, 255, 255, 0.25)',
        'hillshade-accent-color': 'rgba(0, 0, 0, 0.15)',
      },
    },
    {
      id: 'geology-line', type: 'line', source: 'geology', minzoom: 8,
      paint: {
        'line-color': 'rgba(40, 40, 40, 0.55)',
        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.3, 12, 1],
      },
    },
    {
      id: 'roads-primary', type: 'line', source: 'roads', minzoom: 6,
      filter: ['==', ['get', 'class'], 'primary'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#555555',
        'line-opacity': 0.85,
        'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.6, 10, 1.6, 14, 3],
      },
    },
    {
      id: 'roads-trunk', type: 'line', source: 'roads',
      filter: ['==', ['get', 'class'], 'trunk'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#3d2b2b',
        'line-opacity': 0.85,
        'line-width': ['interpolate', ['linear'], ['zoom'], 4, 0.6, 8, 1.6, 14, 4],
      },
    },
    {
      id: 'roads-motorway', type: 'line', source: 'roads',
      filter: ['==', ['get', 'class'], 'motorway'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': '#5a1e1e',
        'line-opacity': 0.9,
        'line-width': ['interpolate', ['linear'], ['zoom'], 4, 1, 8, 2.4, 14, 6],
      },
    },
    // City dots. Visibility by scalerank tier; capitals drawn as squares (larger, inverted).
    ...cityLayers(),
  ],
};

// Scalerank tiers -> minimum zoom at which a city appears.
function cityLayers() {
  const tiers = [
    { id: 'a', filter: ['<=', ['get', 'scalerank'], 4], minzoom: 0 },
    { id: 'b', filter: ['all', ['>', ['get', 'scalerank'], 4], ['<=', ['get', 'scalerank'], 7]], minzoom: 5.3 },
    { id: 'c', filter: ['>', ['get', 'scalerank'], 7], minzoom: 6.3 },
  ];
  const capital = ['==', ['get', 'capital'], 1];
  const layers = [];
  for (const t of tiers) {
    layers.push({
      id: `city-dot-${t.id}`, type: 'circle', source: 'cities', minzoom: t.minzoom, filter: t.filter,
      paint: {
        'circle-radius': ['case', capital, 4.5, 3],
        'circle-color': ['case', capital, '#1d1d1d', '#ffffff'],
        'circle-stroke-color': ['case', capital, '#ffffff', '#1d1d1d'],
        'circle-stroke-width': ['case', capital, 1.5, 1.4],
        'circle-pitch-alignment': 'viewport',
      },
    });
  }
  // Labels after all dots so they draw on top; higher tiers placed first.
  for (const t of tiers) {
    layers.push({
      id: `city-label-${t.id}`, type: 'symbol', source: 'cities', minzoom: t.minzoom, filter: t.filter,
      layout: {
        'text-field': ['get', 'name'],
        'text-font': ['case', capital, ['literal', FONT_BOLD], ['literal', FONT]],
        'text-size': ['case', capital, 14, ['<=', ['get', 'scalerank'], 4], 13, 12],
        'text-variable-anchor': ['left', 'right', 'top', 'bottom'],
        'text-radial-offset': 0.6,
        'text-justify': 'auto',
        'symbol-sort-key': ['get', 'scalerank'],
        'text-padding': 3,
      },
      paint: {
        'text-color': '#111111',
        'text-halo-color': 'rgba(255,255,255,0.9)',
        'text-halo-width': 1.6,
      },
    });
  }
  return layers;
}

const map = new maplibregl.Map({
  container: 'map',
  style,
  bounds: PENINSULA,
  fitBoundsOptions: { padding: isPhone() ? 10 : 30 },
  pitch: 45,
  maxPitch: 75,
  attributionControl: false,
  hash: true,
});

map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');
map.addControl(new maplibregl.AttributionControl({
  compact: true,
  customAttribution: '<a href="https://maplibre.org/">MapLibre</a>',
}), 'bottom-right');

map.on('load', () => {
  map.setTerrain({ source: 'dem-terrain', exaggeration: DEFAULT_EXAG });
  // The compact attribution opens expanded; start it collapsed (the (i) button opens it).
  document.querySelector('.maplibregl-ctrl-attrib.maplibregl-compact-show')?.classList.remove('maplibregl-compact-show');
});

// ---- Legend and class toggles ----
let units = {};
let source = {};
const enabled = new Set();

function applyClassFilter() {
  const f = ['in', ['get', 'level1_class'], ['literal', [...enabled]]];
  map.setFilter('geology-fill', f);
  map.setFilter('geology-line', f);
  document.querySelectorAll('#legend li').forEach((li) => {
    const on = enabled.has(li.dataset.cls);
    li.classList.toggle('off', !on);
    li.querySelector('input').checked = on;
  });
}

function buildLegend(classes) {
  const ul = document.getElementById('legend');
  for (const c of classes) {
    enabled.add(c.name);
    const li = document.createElement('li');
    li.dataset.cls = c.name;
    li.innerHTML =
      `<label><input type="checkbox" checked>` +
      `<span class="swatch" style="background:${c.colour}"></span>` +
      `<span><span class="name">${c.name}</span><br><span class="codes">${c.codes.join(', ')}</span></span></label>`;
    li.querySelector('input').addEventListener('change', (e) => {
      if (e.target.checked) enabled.add(c.name); else enabled.delete(c.name);
      applyClassFilter();
    });
    ul.appendChild(li);
  }
  document.getElementById('all-on').onclick = () => { classes.forEach((c) => enabled.add(c.name)); applyClassFilter(); };
  document.getElementById('all-off').onclick = () => { enabled.clear(); applyClassFilter(); };
}

const unitsReady = fetch('data/units.json')
  .then((r) => r.json())
  .then((j) => { units = j.units; source = j.source; buildLegend(j.classes); });

Promise.all([unitsReady, new Promise((res) => map.once('load', res))]).then(applyClassFilter);

// ---- Sliders ----
const exag = document.getElementById('exag');
exag.addEventListener('input', () => {
  const v = parseFloat(exag.value);
  document.getElementById('exag-val').textContent = `${v.toFixed(1)}×`;
  map.setTerrain({ source: 'dem-terrain', exaggeration: v });
});
const opacity = document.getElementById('opacity');
opacity.addEventListener('input', () => {
  const v = parseFloat(opacity.value);
  document.getElementById('opacity-val').textContent = v.toFixed(2);
  map.setPaintProperty('geology-fill', 'fill-opacity', v);
});

// ---- Popups ----
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ROAD_LAYERS = ['roads-motorway', 'roads-trunk', 'roads-primary'];

function roadText(p) {
  const parts = [p.ref, p.name_en].filter(Boolean).map(esc);
  return `${parts.join(' · ') || '<i>unnamed</i>'} <span style="color:#5d6873">(${esc(p.class)})</span>`;
}

map.on('click', (e) => {
  const geo = map.queryRenderedFeatures(e.point, { layers: ['geology-fill'] })[0];
  if (!geo) return;
  const p = geo.properties;
  const u = units[p.GLG] || {};
  const box = [[e.point.x - 4, e.point.y - 4], [e.point.x + 4, e.point.y + 4]];
  const road = map.queryRenderedFeatures(box, { layers: ROAD_LAYERS.filter((l) => map.getLayer(l)) })[0];
  const html =
    `<div class="pop">` +
    `<h3><span class="swatch" style="background:${esc(p.level1_colour)}"></span>${esc(p.level1_class)}</h3>` +
    `<table>` +
    `<tr><th>pid</th><td class="pid">${esc(p.pid)}</td></tr>` +
    (p.level2_label ? `<tr><th>L2 label</th><td>${esc(p.level2_label)}</td></tr>` : '') +
    `<tr><th>GLG</th><td>${esc(p.GLG)} — ${esc(u.description)}</td></tr>` +
    `<tr><th>Age</th><td>${esc(u.age)}</td></tr>` +
    `<tr><th>Lithology</th><td>${esc(u.lithology)}</td></tr>` +
    `</table>` +
    `<div class="src">Source: <a href="${esc(source.url)}" target="_blank" rel="noopener">${esc(source.short)}</a>, doi:${esc(source.doi)}. ` +
    `Lithology is a generalized summary.</div>` +
    (road ? `<div class="road">Road: ${roadText(road.properties)}</div>` : '') +
    `</div>`;
  new maplibregl.Popup({ maxWidth: '320px' }).setLngLat(e.lngLat).setHTML(html).addTo(map);
});

// Road tooltip on hover (desktop) and pointer cursor over clickable geology.
const roadTip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, className: 'road-tip', offset: 8 });
map.on('mousemove', (e) => {
  const layers = ROAD_LAYERS.filter((l) => map.getLayer(l));
  const box = [[e.point.x - 3, e.point.y - 3], [e.point.x + 3, e.point.y + 3]];
  const road = map.queryRenderedFeatures(box, { layers })[0];
  if (road) roadTip.setLngLat(e.lngLat).setHTML(roadText(road.properties)).addTo(map);
  else roadTip.remove();
  const geo = map.queryRenderedFeatures(e.point, { layers: ['geology-fill'] }).length;
  map.getCanvas().style.cursor = geo ? 'pointer' : '';
});

// ---- Phone panel toggle ----
document.getElementById('panel-open').onclick = () => document.body.classList.add('panel-visible');
document.getElementById('panel-close').onclick = () => document.body.classList.remove('panel-visible');

// Keep the map sized to its container when the layout changes.
window.addEventListener('resize', () => map.resize());
