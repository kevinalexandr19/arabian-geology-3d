/* Arabia 3D — MapLibre viewer. No basemap: background colour + own layers only. */

const TERRAIN_TILES = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png';
const TERRAIN_ATTR =
  'Terrain: <a href="https://registry.opendata.aws/terrain-tiles/">Mapzen Terrain Tiles (AWS Open Data)</a>; ' +
  'SRTM and GMTED2010 courtesy of the U.S. Geological Survey, ETOPO1 by NOAA ' +
  '(<a href="https://github.com/tilezen/joerd/blob/master/docs/attribution.md">full credits</a>)';
const GEO_ATTR = '<a href="https://doi.org/10.3133/ofr97470B">USGS OFR 97-470B (geo2bg)</a>';
const NE_ATTR = '<a href="https://www.naturalearthdata.com/">Natural Earth</a>';
const OSM_ATTR = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> (ODbL)';
const GVP_ATTR = 'Volcanoes: <a href="https://volcano.si.edu/">Smithsonian Global Volcanism Program</a>';
const PB_ATTR = 'Plate boundaries: <a href="https://doi.org/10.1029/2001GC000252">Bird (2003)</a>, ' +
  '<a href="https://github.com/fraxen/tectonicplates">Ahlenius/Nordpil</a> (ODC-BY)';

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
// Home view: whole peninsula. Phones get a flatter camera and room below for the intro card.
const HOME_PITCH = () => (isPhone() ? 20 : 45);
const HOME_PADDING = () => (isPhone() ? { top: 60, bottom: 170, left: 10, right: 10 } : 30);

const style = {
  version: 8,
  glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
  sources: {
    // Two sources on the same tiles: MapLibre recommends separate sources for terrain and hillshade.
    'dem-terrain': demSource(),
    'dem-hillshade': demSource(),
    'dem-relief': demSource(),
    geology: { type: 'geojson', data: 'data/geology.geojson', attribution: GEO_ATTR },
    roads: { type: 'geojson', data: 'data/roads.geojson', attribution: OSM_ATTR },
    cities: { type: 'geojson', data: 'data/cities.geojson', attribution: NE_ATTR },
    tour: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
    plates: { type: 'geojson', data: 'data/plates.geojson', attribution: PB_ATTR },
    volcanoes: { type: 'geojson', data: 'data/volcanoes.geojson', attribution: GVP_ATTR },
    sites: { type: 'geojson', data: 'data/geoheritage.geojson' },
    profile: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
  },
  layers: [
    { id: 'background', type: 'background', paint: { 'background-color': '#d7dde2' } },
    // Sea floor coloured by depth from the same Terrarium tiles (bathymetry: ETOPO1/GEBCO); land stays transparent.
    {
      id: 'sea-depth', type: 'color-relief', source: 'dem-relief',
      paint: {
        'color-relief-color': ['interpolate', ['linear'], ['elevation'],
          -6000, '#12355b', -4500, '#1a4a7a', -3000, '#25629a', -2000, '#3779b3', -1200, '#5293c7',
          -600, '#73acd8', -200, '#98c5e5', -60, '#b9d8ee', -10, '#d2e6f3', -0.5, '#dcebf4', 0, 'rgba(220,235,244,0)'],
      },
    },
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
    // Plate boundaries (Bird 2003): drawn over the sea shading, under roads and labels.
    {
      id: 'plates-casing', type: 'line', source: 'plates',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': 'rgba(255,255,255,0.75)', 'line-width': ['interpolate', ['linear'], ['zoom'], 3, 3, 8, 6] },
    },
    {
      id: 'plates', type: 'line', source: 'plates', filter: ['!=', ['get', 'cls'], 'convergent'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: {
        'line-color': ['match', ['get', 'cls'], 'spreading', '#c0262d', '#1d232a'],
        'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.6, 8, 3.2],
      },
    },
    {
      id: 'plates-conv', type: 'line', source: 'plates', filter: ['==', ['get', 'cls'], 'convergent'],
      layout: { 'line-join': 'round' },
      paint: {
        'line-color': '#6b2d8c',
        'line-width': ['interpolate', ['linear'], ['zoom'], 3, 1.6, 8, 3.2],
        'line-dasharray': [3, 1.5],
      },
    },
    // Tour: outline of the polygons a stop is about (filter set per stop).
    {
      id: 'focus-glow', type: 'line', source: 'geology', layout: { visibility: 'none' },
      paint: { 'line-color': '#ffffff', 'line-width': 4.5, 'line-blur': 1.5, 'line-opacity': 0.9 },
    },
    {
      id: 'focus-line', type: 'line', source: 'geology', layout: { visibility: 'none' },
      paint: { 'line-color': '#1d232a', 'line-width': 1.6 },
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
    // Elevation profile line.
    {
      id: 'profile-casing', type: 'line', source: 'profile',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 6 },
    },
    {
      id: 'profile-line', type: 'line', source: 'profile',
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#0b5cad', 'line-width': 3 },
    },
    // Explore points: volcanoes (triangle-like dark-orange dots) and geoheritage sites (teal).
    {
      id: 'volcs', type: 'circle', source: 'volcanoes',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4.5, 9, 7],
        'circle-color': '#c2410c', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.8,
        'circle-pitch-alignment': 'viewport',
      },
    },
    {
      id: 'sites', type: 'circle', source: 'sites',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 4.5, 9, 7],
        'circle-color': ['case', ['==', ['get', 'kind'], 'Geopark'], '#0e7490', '#0f766e'],
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 1.8,
        'circle-pitch-alignment': 'viewport',
      },
    },
    {
      id: 'volcs-label', type: 'symbol', source: 'volcanoes', minzoom: 5.5,
      layout: {
        'text-field': ['get', 'name'], 'text-font': FONT_BOLD, 'text-size': 11.5,
        'text-variable-anchor': ['top', 'bottom', 'right', 'left'], 'text-radial-offset': 0.9, 'text-padding': 2,
      },
      paint: { 'text-color': '#9a3412', 'text-halo-color': 'rgba(255,255,255,0.95)', 'text-halo-width': 1.6 },
    },
    {
      id: 'sites-label', type: 'symbol', source: 'sites', minzoom: 6,
      layout: {
        'text-field': ['get', 'name'], 'text-font': FONT_BOLD, 'text-size': 11.5,
        'text-variable-anchor': ['top', 'bottom', 'right', 'left'], 'text-radial-offset': 0.9, 'text-padding': 2,
        'text-max-width': 12,
      },
      paint: { 'text-color': '#115e59', 'text-halo-color': 'rgba(255,255,255,0.95)', 'text-halo-width': 1.6 },
    },
    // Tour annotations: escarpment lines for the active stop (flags and area labels are DOM markers).
    {
      id: 'tour-line-casing', type: 'line', source: 'tour', filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#ffffff', 'line-width': 6, 'line-opacity': 0.85 },
    },
    {
      id: 'tour-line', type: 'line', source: 'tour', filter: ['==', ['geometry-type'], 'LineString'],
      layout: { 'line-join': 'round', 'line-cap': 'round' },
      paint: { 'line-color': '#b3122e', 'line-width': 3, 'line-dasharray': [2, 1.2] },
    },
    {
      id: 'tour-line-label', type: 'symbol', source: 'tour', filter: ['==', ['geometry-type'], 'LineString'],
      layout: {
        'symbol-placement': 'line', 'text-field': ['get', 'name'], 'text-font': FONT_BOLD,
        'text-size': 13, 'text-offset': [0, -1.1], 'text-letter-spacing': 0.05, 'symbol-spacing': 320,
      },
      paint: { 'text-color': '#b3122e', 'text-halo-color': '#ffffff', 'text-halo-width': 2 },
    },
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
  fitBoundsOptions: { padding: HOME_PADDING() },
  pitch: HOME_PITCH(),
  maxPitch: 75,
  // Right-drag (or Ctrl+drag) rotation speed: ~1/3 of MapLibre's default 0.8 deg/px.
  // Direction is unchanged (MapLibre default behaviour).
  rotateDegreesPerPixelMoved: 0.25,
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
// Sources that load later add their attribution and re-open the compact box: keep it closed until the user opens it.
let attribTouched = false;
map.on('sourcedata', () => {
  const a = document.querySelector('.maplibregl-ctrl-attrib');
  if (!a) return;
  if (!a.dataset.watch) {
    a.dataset.watch = '1';
    a.querySelector('.maplibregl-ctrl-attrib-button')?.addEventListener('click', () => { attribTouched = true; });
  }
  if (!attribTouched) a.classList.remove('maplibregl-compact-show');
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

const fmt = (v) => v.toLocaleString('en-US').replace('-', '−');

function buildLegend(classes) {
  const ul = document.getElementById('legend');
  for (const c of classes) {
    enabled.add(c.name);
    const li = document.createElement('li');
    li.dataset.cls = c.name;
    li.innerHTML =
      `<label><input type="checkbox" checked>` +
      `<span class="swatch" style="background:${c.colour}"></span>` +
      `<span class="text"><span class="name">${c.name}</span><br><span class="codes">${c.codes.join(', ')}</span></span></label>`;
    li.querySelector('input').addEventListener('change', (e) => {
      if (e.target.checked) enabled.add(c.name); else enabled.delete(c.name);
      applyClassFilter();
    });
    ul.appendChild(li);
  }
  document.getElementById('all-on').onclick = () => { classes.forEach((c) => enabled.add(c.name)); applyClassFilter(); };
  document.getElementById('all-off').onclick = () => { enabled.clear(); applyClassFilter(); };
}

const getJSON = (url) => fetch(url).then((r) => r.json());
const unitsReady = Promise.all([
  getJSON('data/units.json'),
  getJSON('data/elev_stats.json').catch(() => null),
]).then(([j, e]) => { units = j.units; source = j.source; buildLegend(j.classes); if (e) buildStats(j.classes, e); });

Promise.all([unitsReady, new Promise((res) => map.once('load', res))]).then(applyClassFilter);

// ---- Elevation statistics window ----
// Box plots on a shared 0..ELEV_MAX m axis; values below 0 (coastal pixels on bathymetry) clip to 0.
const ELEV_MAX = 3700;
const SHIELD = 'Precambrian basement (Arabian Shield)';
const L2_FEATURES = [  // [L2 label in elev_stats.json, short name, parent L1 class]
  ['Yemen traps (Oligocene-Miocene)', 'Yemen traps', 'Cenozoic volcanics'],
  ['Harrats (Oligocene-Quaternary)', 'Harrats (Oligocene–Quaternary)', 'Cenozoic volcanics'],
  ['Alluvium and gravel', 'Alluvium and gravel', 'Neogene-Quaternary surficial deposits'],
  ['Eolian sand', 'Eolian sand', 'Neogene-Quaternary surficial deposits'],
  ['Neogene-Quaternary gravels', 'Neogene-Quaternary gravels', 'Neogene-Quaternary surficial deposits'],
  ['Sabkha', 'Sabkha', 'Neogene-Quaternary surficial deposits'],
];

function boxPlot(st, colour) {
  const c = (v) => Math.min(Math.max(v, 0), ELEV_MAX) / ELEV_MAX * 100;
  const tip = `min ${fmt(st.min)} · p10 ${fmt(st.p10)} · median ${fmt(st.median)} · p90 ${fmt(st.p90)} · max ${fmt(st.max)} m`;
  return `<div class="strack" title="${tip}">` +
    `<span class="whisk" style="left:${c(st.min)}%;width:${c(st.max) - c(st.min)}%"></span>` +
    `<span class="box" style="left:${c(st.p10)}%;width:${c(st.p90) - c(st.p10)}%;background:${colour}"></span>` +
    `<span class="med" style="left:${c(st.median)}%"></span></div>`;
}

function chart(rows) {
  const ticks = [0, 1000, 2000, 3000].map((t) =>
    `<span style="left:${t / ELEV_MAX * 100}%">${fmt(t)}${t === 3000 ? ' m' : ''}</span>`).join('');
  return rows.map(([name, st, colour]) =>
    `<div class="srow"><span class="slabel"><span class="sw" style="background:${colour}"></span>${esc(name)}</span>` +
    `${boxPlot(st, colour)}<span class="smed">${fmt(st.median)}</span></div>`).join('') +
    `<div class="srow saxis"><span></span><div class="sticks">${ticks}</div><span class="smed">median</span></div>`;
}

function buildStats(classes, e) {
  const L1 = e.level1, L2 = e.level2 || {};
  const colour = Object.fromEntries(classes.map((c) => [c.name, c.colour]));
  const short = (n) => (n === SHIELD ? 'Precambrian basement' : n);
  const rows1 = classes.filter((c) => L1[c.name]).map((c) => [short(c.name), L1[c.name], c.colour])
    .sort((a, b) => b[1].median - a[1].median);
  document.getElementById('stats-chart').innerHTML = chart(rows1);
  const rows2 = L2_FEATURES.filter(([k]) => L2[k]).map(([k, name, parent]) => [name, L2[k], colour[parent]])
    .sort((a, b) => b[1].median - a[1].median);
  document.getElementById('stats-chart-l2').innerHTML = chart(rows2);

  // Observations: wording fixed, numbers read from elev_stats.json.
  const m = (n) => `${fmt(L1[n].median)} m`;
  const r = (n) => `${fmt(L1[n].p10)}–${fmt(L1[n].p90)} m`;
  const notes = [];
  const V = 'Cenozoic volcanics', traps = L2['Yemen traps (Oligocene-Miocene)'];
  notes.push(`<b>The highest ground is volcanic or basement.</b> Cenozoic volcanics (median ${m(V)}) and the Precambrian basement (median ${m(SHIELD)}) top the ranking. Both sit on the shoulder of the Red Sea rift, uplifted since the Oligocene` +
    (traps ? `; the Yemen traps alone have a median of ${fmt(traps.median)} m and reach ${fmt(traps.max)} m near Jabal an-Nabi Shu'ayb.` : '.'));
  notes.push(`<b>The Shield is a tilted block.</b> Its 10th–90th percentile range spans ${r(SHIELD)}, one of the widest of any class: about 3,000 m along the Hijaz–Asir escarpment, falling gently east to a few hundred metres where the basement passes beneath the sedimentary cover.`);
  const chain = ['Paleozoic', 'Cretaceous', 'Paleogene-Neogene sedimentary', 'Neogene-Quaternary surficial deposits'].filter((n) => L1[n]);
  notes.push(`<b>Across the Arabian Platform, younger means lower.</b> Medians fall from ${chain.map((n) => `${short(n)} (${m(n)})`).join(' to ')}. The cover dips gently east and north-east off the Shield, so successively younger units crop out closer to the Gulf, where the land surface reaches sea level.`);
  if (L1.Jurassic && L1.Triassic && L1.Jurassic.median > L1.Triassic.median) {
    notes.push(`<b>The Jurassic breaks the trend.</b> Its median (${m('Jurassic')}) is above the Triassic (${m('Triassic')}) and its 90th percentile reaches ${fmt(L1.Jurassic.p90)} m: resistant Tuwaiq limestones hold up the highest cuesta of central Arabia, and Jurassic strata also crop out in the Yemen highlands and the Hajar windows. The Triassic outcrop is small (a narrow cuesta belt), so its numbers are less robust.`);
  }
  if (L1.Cretaceous) {
    notes.push(`<b>Cretaceous: low median, high maximum.</b> Most Cretaceous outcrop is low cuesta country in central and eastern Arabia (median ${m('Cretaceous')}), but the class also contains the Semail ophiolite and Hawasina nappes of the Hajar Mountains, which reach ${fmt(L1.Cretaceous.max)} m.`);
  }
  const sab = L2.Sabkha, sand = L2['Eolian sand'];
  if (sab && sand) {
    notes.push(`<b>Surficial deposits fill the lows.</b> Sabkhas have a median of ${fmt(sab.median)} m (10th percentile ${fmt(sab.p10)} m): coastal flats at sea level plus inland sabkhas in closed depressions. Eolian sand (median ${fmt(sand.median)} m) mantles the low eastern half of the platform, from the Rub' al Khali to the Dahna and Nafud.`);
  }
  document.getElementById('stats-notes').innerHTML = notes.map((n) => `<li>${n}</li>`).join('');

  const head = '<tr><th>Class</th><th>min</th><th>p10</th><th>median</th><th>p90</th><th>max</th><th>pixels</th></tr>';
  const body = classes.filter((c) => L1[c.name]).map((c) => {
    const st = L1[c.name];
    return `<tr><td><span class="sw" style="background:${c.colour}"></span>${esc(short(c.name))}</td>` +
      [st.min, st.p10, st.median, st.p90, st.max, st.n_px].map((v) => `<td>${fmt(v)}</td>`).join('') + '</tr>';
  }).join('');
  document.getElementById('stats-table').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
}

// ---- Windows (elevation statistics, about): open from the panel, close on ×, backdrop or Esc ----
let lastOpener = null;
function openWin(id, opener) {
  closeWins();
  const w = document.getElementById(id);
  w.hidden = false;
  lastOpener = opener || null;
  w.querySelector('.win-close').focus();
  if (isPhone()) document.body.classList.remove('panel-visible');
}
function closeWins() {
  let was = false;
  document.querySelectorAll('.win-backdrop').forEach((w) => { if (!w.hidden) was = true; w.hidden = true; });
  if (was && lastOpener && !isPhone()) lastOpener.focus();
}
document.querySelectorAll('[data-open]').forEach((b) => { b.onclick = () => openWin(b.dataset.open, b); });
document.querySelectorAll('.win-backdrop').forEach((w) => {
  w.addEventListener('click', (e) => { if (e.target === w) closeWins(); });
  w.querySelector('.win-close').onclick = closeWins;
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeWins(); });

// ---- Sliders ----
const exag = document.getElementById('exag');
exag.addEventListener('input', () => {
  const v = parseFloat(exag.value);
  document.getElementById('exag-val').textContent = `${v.toFixed(1)}×`;
  map.setTerrain({ source: 'dem-terrain', exaggeration: v });
});
const opacity = document.getElementById('opacity');
let dimKeep = null;   // tour overview stops: L1 classes kept at full opacity, the rest faded
function setFillOpacity() {
  const v = parseFloat(opacity.value);
  if (!map.getLayer('geology-fill')) return;
  map.setPaintProperty('geology-fill', 'fill-opacity', dimKeep
    ? ['case', ['in', ['get', 'level1_class'], ['literal', dimKeep]], v, v * 0.15]
    : v);
}
opacity.addEventListener('input', () => {
  document.getElementById('opacity-val').textContent = parseFloat(opacity.value).toFixed(2);
  setFillOpacity();
});

// ---- Popups ----
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const ROAD_LAYERS = ['roads-motorway', 'roads-trunk', 'roads-primary'];

function roadText(p) {
  const parts = [p.ref, p.name_en].filter(Boolean).map(esc);
  return `${parts.join(' · ') || '<i>unnamed</i>'} <span style="color:#5d6873">(${esc(p.class)})</span>`;
}

const PLACE_LAYERS = ['volcs', 'sites'];
const visibleLayers = (ls) => ls.filter((l) => map.getLayer(l) && map.getLayoutProperty(l, 'visibility') !== 'none');

map.on('click', (e) => {
  if (prof.on) return;   // the profile tool takes map clicks
  const box6 = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
  const place = map.queryRenderedFeatures(box6, { layers: visibleLayers(PLACE_LAYERS) })[0];
  if (place) { showPlace(place.layer.id === 'volcs' ? 'volc' : 'site', place.properties, place.geometry.coordinates); return; }
  const plate = map.queryRenderedFeatures(box6, { layers: visibleLayers(['plates', 'plates-conv']) })[0];
  if (plate) { plateTip(plate.properties, e.lngLat); return; }
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
    (p.contact_adjusted ? `<tr><th>Boundary</th><td>Mountain-front contact moved to the foot of the slope in the terrain data (not in geo2bg)</td></tr>` : '') +
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
  if (prof.on) { map.getCanvas().style.cursor = 'crosshair'; return; }
  const box6 = [[e.point.x - 6, e.point.y - 6], [e.point.x + 6, e.point.y + 6]];
  const hot = map.queryRenderedFeatures(box6, { layers: visibleLayers([...PLACE_LAYERS, 'plates', 'plates-conv']) }).length ||
    map.queryRenderedFeatures(e.point, { layers: ['geology-fill'] }).length;
  map.getCanvas().style.cursor = hot ? 'pointer' : '';
});

// ---- Bookmarks and tour ----
// Captions: sentence 1 = the geology, sentence 2 = how it shows in the relief. Edit here.
const TUWAIQ = [[45.14, 20.0], [45.18, 20.25], [45.32, 20.5], [45.34, 20.75], [45.44, 21.0], [45.52, 21.25], [45.59, 21.5], [45.68, 21.75], [45.9, 22.25], [46.01, 22.5], [46.1, 22.75], [46.26, 23.0], [46.33, 23.25], [46.41, 23.5], [46.46, 23.75], [46.38, 24.0], [46.35, 24.25], [46.42, 24.5], [46.1, 24.75], [45.96, 25.0], [46.05, 25.25]];
const PLATFORM = ['Paleozoic', 'Triassic', 'Jurassic', 'Cretaceous', 'Paleogene-Neogene sedimentary'];
// A stop has either `camera` (fixed preset) or `bounds` + pitch/bearing (fitted to the screen, for overviews).
// marks.dim: L1 classes kept at full opacity; all others are faded while the stop is shown.
const STOPS = [
  {
    title: 'The Arabian Shield',
    bounds: [[35.0, 13.4], [46.4, 29.6]], pitch: 35, bearing: -15,
    marks: {
      areas: [['Arabian Shield', 42.4, 23.6], ['Red Sea', 37.7, 21.2], ['Arabian Platform', 46.6, 27.4]],
      dim: ['Precambrian basement (Arabian Shield)'],
    },
    caption: 'The Arabian Shield is the exposed Neoproterozoic basement of the Arabian Plate: island arcs, ophiolite belts and granites accreted during the East African Orogeny and stabilized by about 550 Ma, now cropping out over some 500,000 km² along the Red Sea. ' +
      'It is a block tilted to the east, highest on the uplifted rift shoulder of the Hijaz and Asir (2,000–3,000 m) and descending eastward to a few hundred metres, where it passes beneath the sedimentary cover.',
  },
  {
    title: 'Hijaz–Asir escarpment',
    camera: { center: [42.6, 18.8], zoom: 8, pitch: 62, bearing: 65 },
    marks: {
      flags: [['Jabal Sawda', '~3,000 m', 42.369, 18.266]],
      areas: [['Arabian Shield', 43.0, 19.35], ['Tihamah', 41.3, 19.0]],
      lines: [['Asir escarpment', [[42.71, 18.0], [42.31, 18.25], [42.21, 18.5], [42.21, 18.75], [42.06, 19.0], [42.04, 19.25], [41.86, 19.5], [41.85, 19.75], [41.38, 20.0], [41.19, 20.25]]]],
    },
    caption: 'The Arabian Shield is Neoproterozoic crystalline basement (island-arc volcanics, metasediments and granites accreted c. 870–550 Ma), exposed where the Red Sea rift flank was uplifted. ' +
      'The Asir highlands reach nearly 3,000 m and fall in a steep west-facing escarpment to the Tihamah coastal plain, while the Shield surface slopes gently east beneath the sedimentary cover.',
  },
  {
    title: 'Harrat Rahat and Harrat Khaybar',
    camera: { center: [39.9, 24.4], zoom: 7, pitch: 55, bearing: 0 },
    marks: {
      areas: [['Harrat Rahat', 40.1, 23.7], ['Harrat Khaybar', 40.1, 25.6]],
      focus: ['==', ['slice', ['get', 'level2_label'], 0, 7], 'Harrats'],
    },
    caption: 'Harrat Rahat and Harrat Khaybar are Cenozoic alkali-basalt lava fields erupted through the Shield along north–south vent alignments; the youngest Rahat flow, south-east of Madinah, erupted in AD 1256. ' +
      'They form broad dark lava plateaux at about 1,000–2,000 m, studded with scoria cones and domes and standing above the eroded basement around them.',
  },
  {
    title: 'The Arabian Platform',
    bounds: [[40.5, 17.0], [55.0, 31.0]], pitch: 45, bearing: 15,
    marks: {
      areas: [['Arabian Platform', 50.4, 23.2], ['Arabian Shield', 42.2, 22.2], ['Arabian Gulf', 51.3, 27.6]],
      lines: [['Tuwaiq escarpment', TUWAIQ]],
      dim: PLATFORM,
    },
    caption: 'The Arabian Platform is the Phanerozoic sedimentary cover that laps onto the Shield: Paleozoic to Neogene sandstones, shales and carbonates thickening to about 10 km toward the Gulf, host to the giant oil and gas fields of the region. ' +
      'The layers dip gently east and north-east, so successively younger units crop out eastward in a belt of west-facing cuestas while the land surface falls from about 1,000 m to sea level at the Gulf.',
  },
  {
    title: 'Tuwaiq escarpment',
    camera: { center: [46.4, 24.3], zoom: 8, pitch: 62, bearing: 90 },
    marks: {
      areas: [['Arabian Shield', 45.05, 23.75], ['Jurassic outcrop', 46.75, 23.6]],
      lines: [['Tuwaiq escarpment', TUWAIQ]],
      focus: ['in', ['get', 'GLG'], ['literal', ['J', 'JTr']]],
    },
    caption: 'The Tuwaiq escarpment is held up by resistant Middle–Upper Jurassic limestones (Tuwaiq Mountain and Jubaila formations) that dip gently east off the Shield. ' +
      'It is the largest of the central Arabian cuestas: a west-facing cliff several hundred metres high that arcs for about 1,000 km past Riyadh.',
  },
  {
    title: 'Rub\' al Khali',
    camera: { center: [51.0, 21.0], zoom: 6.5, pitch: 50, bearing: 0 },
    marks: {
      areas: [['Rub\' al Khali', 50.5, 20.4]],
    },
    caption: 'The Rub\' al Khali is the largest continuous sand sea on Earth: Quaternary eolian sand with interdune sabkhas over a thick Cenozoic basin fill. ' +
      'Its relief is made of dunes, not bedrock, with linear and star mega-dunes up to about 250 m high on a floor that falls from about 800 m in the south-west to near sea level in the north-east.',
  },
  {
    title: 'Hajar Mountains',
    camera: { center: [57.5, 23.1], zoom: 8, pitch: 60, bearing: 180 },
    marks: {
      flags: [['Jabal Shams', '~3,000 m', 57.277, 23.216]],
      areas: [['Jabal Akhdar window', 57.65, 23.12], ['Saih Hatat window', 58.35, 23.35],
        ['Semail ophiolite', 57.95, 23.5], ['Batinah plain', 57.2, 24.0]],
      focus: ['all', ['in', ['get', 'level1_class'], ['literal', ['Paleozoic', 'Triassic', 'Jurassic']]],
        ['within', { type: 'Polygon', coordinates: [[[56.5, 22.4], [59.5, 22.4], [59.5, 24.2], [56.5, 24.2], [56.5, 22.4]]] }]],
    },
    caption: 'The Hajar Mountains expose the Semail ophiolite and Hawasina deep-water sediments thrust onto the Arabian margin in the Late Cretaceous (both kept within the Cretaceous class here), with the underlying Paleozoic–Mesozoic shelf succession exposed in the Jabal Akhdar and Saih Hatat windows. ' +
      'Neogene uplift raised the Jabal Akhdar dome to about 3,000 m, and the range rises abruptly above the Batinah gravel plain and the interior foreland.',
  },
  {
    title: 'Yemen highlands and traps',
    camera: { center: [44.2, 15.0], zoom: 7.5, pitch: 60, bearing: 90 },
    marks: {
      flags: [['Jabal an-Nabi Shu\'ayb', '~3,660 m', 43.973, 15.279, 'left', 46]],
      areas: [['Yemen traps', 44.6, 14.4], ['Tihamah', 43.1, 14.9]],
      focus: ['==', ['slice', ['get', 'level2_label'], 0, 11], 'Yemen traps'],
    },
    caption: 'The Yemen highlands are capped by the Oligocene–Miocene Yemen traps, flood basalts and silicic volcanics erupted c. 31–29 Ma over Jurassic–Cretaceous sediments and Precambrian basement. ' +
      'The traps build a plateau at 2,000–3,000 m, cut by deep wadis and topped by Jabal an-Nabi Shu\'ayb (c. 3,660 m, the highest point of the peninsula), which drops steeply west to the Tihamah.',
  },
  {
    title: 'Dhofar',
    camera: { center: [54.0, 17.5], zoom: 8.2, pitch: 58, bearing: 0 },
    marks: {
      flags: [['Jabal Samhan', '', 54.849, 17.178]],
      areas: [['Jabal Qara', 53.75, 17.12], ['Dhofar plateau', 54.0, 17.85]],
    },
    caption: 'Dhofar is a plateau of Paleocene–Eocene shelf limestones uplifted on the northern shoulder of the Gulf of Aden rift. ' +
      'The Qara and Samhan mountains rise in a south-facing escarpment up to about 2,000 m above the Salalah plain and slope gently north into the interior.',
  },
  {
    title: 'UAE coastal sabkhas and Musandam',
    camera: { center: [55.4, 25.1], zoom: 7.5, pitch: 55, bearing: 40 },
    marks: {
      flags: [['Jebel Harim', '~2,090 m', 56.234, 25.973]],
      areas: [['Abu Dhabi coastal sabkha', 53.9, 24.05], ['Musandam', 56.3, 26.2]],
      focus: ['==', ['get', 'level2_label'], 'Sabkha'],
    },
    caption: 'The Abu Dhabi coastal sabkhas are Holocene supratidal evaporite flats along the Gulf, while the Musandam peninsula exposes Mesozoic shelf carbonates folded and uplifted with the Oman mountains. ' +
      'The sabkhas are almost flat surfaces within a few metres of sea level; Musandam rises to about 2,000 m and drops straight into the sea along drowned valleys (khawrs).',
  },
];
const DWELL_MS = 4500;     // pause after each flight
const FLY_MS = 3500;       // flight duration in the tour (~8 s per stop in total)

const caption = document.getElementById('caption');
let tour = null;           // { i, timer } while the tour runs
let current = -1;          // stop on screen, -1 when none

function showCaption(i) {
  const st = STOPS[i];
  current = i;
  caption.classList.remove('place');
  caption.querySelector('.cap-kicker').textContent = 'Tour';
  caption.querySelector('h3').textContent = `${i + 1}. ${st.title}`;
  caption.querySelector('.cap-body').textContent = st.caption;
  document.querySelectorAll('.placelist button').forEach((b) => b.classList.remove('active'));
  document.getElementById('cap-count').textContent = `${i + 1} / ${STOPS.length}`;
  document.getElementById('cap-prev').disabled = i === 0;
  document.getElementById('cap-next').disabled = i === STOPS.length - 1;
  caption.hidden = false;
  document.querySelectorAll('#bookmarks button').forEach((b, j) => b.classList.toggle('active', j === i));
}
// Flags are DOM markers: they stand upright on the terrain whatever the pitch.
let flagMarkers = [];
function makeFlag(name, note, side, pole) {
  const el = document.createElement('div');
  el.className = side === 'left' ? 'flag flag-left' : 'flag';
  el.innerHTML = `<div class="flag-cloth">${esc(name)}${note ? `<small>${esc(note)}</small>` : ''}</div><div class="flag-pole"${pole ? ` style="height:${pole}px"` : ''}></div>`;
  return el;
}
function clearMarks() {
  flagMarkers.forEach((m) => m.remove());
  flagMarkers = [];
  map.getSource('tour')?.setData({ type: 'FeatureCollection', features: [] });
  ['focus-glow', 'focus-line'].forEach((l) => map.getLayer(l) && map.setLayoutProperty(l, 'visibility', 'none'));
  dimKeep = null;
  setFillOpacity();
}
function showMarks(i) {
  clearMarks();
  const mk = STOPS[i].marks || {};
  // Flag: [name, note, lon, lat, side, pole px]; side 'left' puts the cloth left of the pole and a taller pole lifts it (to keep labels clear).
  for (const [name, note, lon, lat, side, pole] of mk.flags || []) {
    const left = side === 'left';
    flagMarkers.push(new maplibregl.Marker({
      opacityWhenCovered: '1',
      element: makeFlag(name, note, side, pole), anchor: left ? 'bottom-right' : 'bottom-left', offset: [left ? 1 : -1, 0],
    })
      .setLngLat([lon, lat]).addTo(map));
  }
  // Area labels are DOM markers too, so terrain occlusion never hides them mid-tour.
  for (const [name, lon, lat] of mk.areas || []) {
    const el = document.createElement('div');
    el.className = 'area-label';
    el.textContent = name;
    flagMarkers.push(new maplibregl.Marker({ element: el, anchor: 'center', opacityWhenCovered: '1' })
      .setLngLat([lon, lat]).addTo(map));
  }
  const features = [
    ...(mk.lines || []).map(([name, coords]) => ({
      type: 'Feature', properties: { name }, geometry: { type: 'LineString', coordinates: coords },
    })),
  ];
  map.getSource('tour').setData({ type: 'FeatureCollection', features });
  if (mk.dim) { dimKeep = mk.dim; setFillOpacity(); }
  if (mk.focus) {
    for (const l of ['focus-glow', 'focus-line']) {
      map.setFilter(l, mk.focus);
      map.setLayoutProperty(l, 'visibility', 'visible');
    }
  }
}

function hideCaption() {
  caption.hidden = true;
  current = -1;
  document.querySelectorAll('#bookmarks button, .placelist button').forEach((b) => b.classList.remove('active'));
}
caption.querySelector('.caption-close').onclick = hideCaption;

// Overview stops are fitted to the visible map area (leaving room for the caption).
function stopCamera(st) {
  if (st.camera) return st.camera;
  const padding = isPhone() ? { top: 220, bottom: 30, left: 10, right: 10 } : { top: 150, bottom: 40, left: 40, right: 60 };
  const cam = map.cameraForBounds(st.bounds, { padding, bearing: st.bearing || 0 });
  return { ...cam, pitch: st.pitch || 0, bearing: st.bearing || 0 };
}

function goTo(i, duration) {
  hideIntro();
  showCaption(i);
  showMarks(i);
  if (isPhone()) document.body.classList.remove('panel-visible');
  // Only pass duration when set: an explicit undefined overrides MapLibre's default and yields NaN frames.
  map.flyTo({ ...stopCamera(STOPS[i]), ...(duration ? { duration } : {}), essential: true });
}

function stopTour() {
  if (!tour) return;
  clearTimeout(tour.timer);
  tour = null;
  document.getElementById('tour-play').disabled = false;
  document.getElementById('tour-stop').disabled = true;
  document.getElementById('cap-stop').hidden = true;
}

function tourStep() {
  if (!tour) return;
  if (tour.i >= STOPS.length) { stopTour(); return; }
  const i = tour.i++;
  goTo(i, FLY_MS);
  map.once('moveend', () => { if (tour) tour.timer = setTimeout(tourStep, DWELL_MS); });
}

function startTour() {
  stopTour();
  tour = { i: 0, timer: null };
  document.getElementById('tour-play').disabled = true;
  document.getElementById('tour-stop').disabled = false;
  document.getElementById('cap-stop').hidden = false;
  document.querySelector('details.tour').open = true;  // keep Stop/Home in reach in the panel too
  tourStep();
}

function goHome() {
  stopTour();
  hideCaption();
  clearMarks();
  showIntro();
  const cam = map.cameraForBounds(PENINSULA, { padding: HOME_PADDING() });
  map.flyTo({ ...cam, pitch: HOME_PITCH(), bearing: 0, essential: true });
}

const bm = document.getElementById('bookmarks');
STOPS.forEach((st, i) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.textContent = `${i + 1}. ${st.title}`;
  b.onclick = () => { stopTour(); goTo(i); };
  bm.appendChild(b);
});
document.getElementById('tour-play').onclick = startTour;
document.getElementById('tour-stop').onclick = stopTour;
document.getElementById('tour-home').onclick = goHome;
document.getElementById('cap-stop').onclick = stopTour;
// Prev / Next step through the stops by hand (and stop the automatic tour).
const step = (d) => { const i = current + d; if (i < 0 || i >= STOPS.length) return; stopTour(); goTo(i); };
document.getElementById('cap-prev').onclick = () => step(-1);
document.getElementById('cap-next').onclick = () => step(1);
document.getElementById('cap-home').onclick = goHome;
// Any user drag, zoom, rotate or tilt stops the tour (programmatic flyTo has no originalEvent).
map.on('movestart', (e) => { if (e.originalEvent) stopTour(); });

// ---- Intro card (first view) ----
const intro = document.getElementById('intro');
function hideIntro() { intro.hidden = true; }
function showIntro() { intro.hidden = false; }
intro.querySelector('.intro-close').onclick = hideIntro;
document.getElementById('intro-tour').onclick = startTour;

// ---- Loading message: until the geology GeoJSON is parsed and drawn ----
const loading = document.getElementById('loading');
function hideLoading() { loading.hidden = true; }
map.on('sourcedata', (e) => { if (e.sourceId === 'geology' && map.isSourceLoaded('geology')) hideLoading(); });
map.on('error', (e) => {
  if (e.sourceId === 'geology') { loading.textContent = 'Could not load the geology layer. Please reload.'; }
});

// ---- Cursor readout: geographic coordinates + elevation ----
// Elevation is decoded from the Terrarium tile under the cursor (true metres, independent of the
// exaggeration slider; MapLibre's queryTerrainElevation includes the exaggeration and uses coarse tiles).
const readout = document.getElementById('readout');
const tileCache = new Map();   // "z/x/y" -> Promise<ImageData|null>
const TILE_CACHE_MAX = 160;   // the profile tool can touch a few dozen tiles per line

function getTile(z, x, y) {
  const key = `${z}/${x}/${y}`;
  if (tileCache.has(key)) return tileCache.get(key);
  const p = fetch(TERRAIN_TILES.replace('{z}', z).replace('{x}', x).replace('{y}', y))
    .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
    .then((b) => createImageBitmap(b))
    .then((img) => {
      const c = document.createElement('canvas');
      c.width = img.width; c.height = img.height;
      const ctx = c.getContext('2d', { willReadFrequently: true });
      ctx.drawImage(img, 0, 0);
      return ctx.getImageData(0, 0, c.width, c.height);
    })
    .catch(() => null);
  tileCache.set(key, p);
  if (tileCache.size > TILE_CACHE_MAX) tileCache.delete(tileCache.keys().next().value);
  return p;
}

async function elevationAt(lng, lat, zoom) {
  const z = zoom ?? Math.max(7, Math.min(12, Math.floor(map.getZoom()) + 2));
  const n = 2 ** z;
  const fx = (lng + 180) / 360 * n;
  const fy = (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * n;
  const x = Math.floor(fx), y = Math.floor(fy);
  const img = await getTile(z, x, y);
  if (!img) return null;
  const px = Math.min(img.width - 1, Math.floor((fx - x) * img.width));
  const py = Math.min(img.height - 1, Math.floor((fy - y) * img.height));
  const i = (py * img.width + px) * 4;
  return img.data[i] * 256 + img.data[i + 1] + img.data[i + 2] / 256 - 32768;
}

const hemi = (v, pos, neg) => `${Math.abs(v).toFixed(4)}° ${v >= 0 ? pos : neg}`;
let readoutSeq = 0;
async function updateReadout(lngLat) {
  const seq = ++readoutSeq;
  const { lng, lat } = lngLat;
  const coords = `${hemi(lat, 'N', 'S')}, ${hemi(lng, 'E', 'W')}`;
  readout.hidden = false;
  readout.textContent = coords;
  const h = await elevationAt(lng, lat);
  if (seq !== readoutSeq) return;  // a newer position arrived meanwhile
  readout.textContent = h == null ? coords : `${coords} · ${fmt(Math.round(h))} m`;
}
let readoutTimer = null;
map.on('mousemove', (e) => {
  clearTimeout(readoutTimer);
  readoutTimer = setTimeout(() => updateReadout(e.lngLat), 60);
});
map.on('click', (e) => updateReadout(e.lngLat));   // phones: tap shows the readout
map.getCanvasContainer().addEventListener('mouseleave', () => { if (!isPhone()) readout.hidden = true; });

// ---- Explore: geoheritage sites and Holocene volcanoes ----
// Lists in the panel; a click flies to the place and shows a card (like a tour stop, but outside the tour).
const KIND_LABEL = { site: 'Geoheritage site', volc: 'Holocene volcano' };
const yearText = (y) => (y == null ? 'Holocene, date unknown' : y < 0 ? `${fmt(-y)} BCE` : y < 1500 ? `AD ${y}` : `${y}`);

function placeBody(kind, p) {
  if (kind === 'site') {
    // Photo (Wikimedia Commons, credited with author and licence as the licences require).
    const lic = p.photo_licence_url
      ? `<a href="${esc(p.photo_licence_url)}" target="_blank" rel="noopener">${esc(p.photo_licence)}</a>`
      : esc(p.photo_licence);
    const fig = p.photo
      ? `<figure class="cap-photo"><a href="${esc(p.photo_page)}" target="_blank" rel="noopener">` +
        `<img src="${esc(p.photo)}" width="${esc(p.photo_w)}" height="${esc(p.photo_h)}" alt="${esc(p.photo_caption)}" loading="lazy"></a>` +
        `<figcaption>${esc(p.photo_caption)}. Photo: <a href="${esc(p.photo_page)}" target="_blank" rel="noopener">${esc(p.photo_author)}</a>, ${lic}, via Wikimedia Commons (resized).</figcaption></figure>`
      : '';
    return fig + `<p>${esc(p.description)}</p>`;
  }
  const facts = [p.type, p.rock, p.elev_m != null ? `summit ${fmt(p.elev_m)} m` : ''].filter(Boolean).map(esc).join(' · ');
  return `<p class="cap-facts"><b>Last eruption: ${esc(yearText(p.last_eruption))}</b><br>${facts}</p>` +
    (p.note ? `<p>${esc(p.note)}</p>` : '') +
    `<p class="cap-src">Source: <a href="https://volcano.si.edu/volcano.cfm?vn=${esc(p.vnum)}" target="_blank" rel="noopener">Smithsonian GVP, volcano ${esc(p.vnum)}</a></p>`;
}

function showPlace(kind, p, coords) {
  stopTour();
  hideIntro();
  clearMarks();
  current = -1;
  caption.classList.add('place');
  caption.querySelector('.cap-kicker').textContent = kind === 'site'
    ? (p.kind === 'Geopark' ? `UNESCO Global Geopark${p.unesco_year ? ` · designated ${p.unesco_year}` : ''}` : 'Geoheritage site')
    : KIND_LABEL.volc;
  caption.querySelector('h3').textContent = p.name;
  caption.querySelector('.cap-body').innerHTML = placeBody(kind, p);
  caption.hidden = false;
  document.querySelectorAll('#bookmarks button').forEach((b) => b.classList.remove('active'));
  document.querySelectorAll('.placelist button').forEach((b) =>
    b.classList.toggle('active', b.dataset.kind === kind && b.dataset.name === p.name));
  if (isPhone()) document.body.classList.remove('panel-visible');
  const cam = kind === 'site'
    ? { zoom: +p.zoom, pitch: +p.pitch, bearing: +p.bearing }
    : /field/i.test(p.type) ? { zoom: 8, pitch: 50, bearing: 0 } : { zoom: 10.5, pitch: 50, bearing: 0 };  // lava fields vs. single edifices
  map.flyTo({ center: coords, ...cam, essential: true });
}

function buildPlaceList(id, kind, feats) {
  const box = document.getElementById(id);
  for (const f of feats) {
    const p = f.properties;
    const b = document.createElement('button');
    b.type = 'button';
    b.dataset.kind = kind;
    b.dataset.name = p.name;
    const tag = kind === 'site' ? (p.kind === 'Geopark' ? `UNESCO ${p.unesco_year || ''}`.trim() : '') : yearText(p.last_eruption).replace('Holocene, date unknown', 'date unknown');
    b.innerHTML = `<span>${esc(p.name)}</span>${tag ? `<small>${esc(tag)}</small>` : ''}`;
    b.onclick = () => showPlace(kind, p, f.geometry.coordinates);
    box.appendChild(b);
  }
}
getJSON('data/geoheritage.geojson').then((g) => buildPlaceList('sites', 'site', g.features)).catch(() => {});
getJSON('data/volcanoes.geojson').then((g) => buildPlaceList('volcs', 'volc', g.features)).catch(() => {});

// ---- Plate boundaries: click for plates and relative velocity ----
const PLATE_CLS = { spreading: 'Spreading ridge / rift', transform: 'Transform', convergent: 'Convergent (collision or subduction)' };
function plateTip(p, lngLat) {
  new maplibregl.Popup({ maxWidth: '260px' }).setLngLat(lngLat).setHTML(
    `<div class="pop"><h3>${esc(p.name)}</h3><table>` +
    `<tr><th>Type</th><td>${esc(PLATE_CLS[p.cls] || p.cls)}</td></tr>` +
    `<tr><th>Rate</th><td>${esc(p.v_mm)} mm/yr (relative, model)</td></tr></table>` +
    `<div class="src">Bird (2003) PB2002 plate model.</div></div>`).addTo(map);
}

// ---- Overlay toggles ----
const OVERLAY_LAYERS = {
  sites: ['sites', 'sites-label'], volcs: ['volcs', 'volcs-label'],
  plates: ['plates', 'plates-conv', 'plates-casing'], sea: ['sea-depth'],
};
document.querySelectorAll('.toggles input[data-layer]').forEach((cb) => {
  cb.addEventListener('change', () => {
    for (const l of OVERLAY_LAYERS[cb.dataset.layer]) {
      if (map.getLayer(l)) map.setLayoutProperty(l, 'visibility', cb.checked ? 'visible' : 'none');
    }
  });
});

// ---- Elevation profile tool ----
// A map button opens a non-modal window at the bottom; click two points to draw a line. The profile is sampled
// from the Terrarium tiles (true metres) and filled with the Level 1 colour of the polygon under each sample.
const prof = { on: false, pts: [], markers: [], hover: null, data: null };
const profEl = document.getElementById('profile');
const PROF_N = 400;
const SEA_COLOUR = '#9cc7e6';
const NODATA_COLOUR = '#c9ced4';

class ProfileControl {
  onAdd() {
    const d = document.createElement('div');
    d.className = 'maplibregl-ctrl maplibregl-ctrl-group profile-ctrl';
    d.innerHTML = '<button type="button" title="Elevation profile" aria-label="Elevation profile">' +
      '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M2 19 L8 9 L12 14 L16 6 L22 19 Z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>' +
      '<span>Profile</span></button>';
    d.querySelector('button').onclick = () => (prof.on ? closeProfile() : openProfile());
    this.el = d;
    return d;
  }
  onRemove() { this.el.remove(); }
}
map.addControl(new ProfileControl(), 'top-right');

const haversineKm = (a, b) => {
  const r = Math.PI / 180, dLat = (b[1] - a[1]) * r, dLon = (b[0] - a[0]) * r;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[1] * r) * Math.cos(b[1] * r) * Math.sin(dLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
};

// Point-in-polygon lookup on the geology GeoJSON (fetched once; the browser has it cached already).
let geoIndex = null;
function loadGeoIndex() {
  if (!geoIndex) {
    geoIndex = getJSON('data/geology.geojson').then((g) => g.features.map((f) => {
      const polys = f.geometry.type === 'Polygon' ? [f.geometry.coordinates] : f.geometry.coordinates;
      let x0 = 180, y0 = 90, x1 = -180, y1 = -90;
      for (const pl of polys) for (const [x, y] of pl[0]) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
      return { p: f.properties, polys, bb: [x0, y0, x1, y1] };
    }));
  }
  return geoIndex;
}
function inRing(x, y, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function geologyAt(idx, x, y) {
  for (const f of idx) {
    const b = f.bb;
    if (x < b[0] || x > b[2] || y < b[1] || y > b[3]) continue;
    for (const pl of f.polys) {
      if (inRing(x, y, pl[0]) && !pl.slice(1).some((h) => inRing(x, y, h))) return f.p;
    }
  }
  return null;
}

function setHint(t) {
  const h = document.getElementById('prof-hint');
  h.textContent = t;
  h.hidden = !t;
}
function openProfile() {
  closeWins();
  stopTour();
  hideIntro();
  prof.on = true;
  profEl.hidden = false;
  document.body.classList.add('profiling');
  document.querySelector('.profile-ctrl button').classList.add('on');
  if (isPhone()) document.body.classList.remove('panel-visible');
  resetProfile();
}
function resetProfile() {
  prof.pts = [];
  prof.data = null;
  prof.markers.forEach((m) => m.remove());
  prof.markers = [];
  prof.hover?.remove();
  prof.hover = null;
  map.getSource('profile')?.setData({ type: 'FeatureCollection', features: [] });
  document.getElementById('prof-chart').innerHTML = '';
  document.getElementById('prof-legend').innerHTML = '';
  document.getElementById('prof-info').textContent = '';
  document.getElementById('prof-new').hidden = true;
  setHint('Click the start point on the map.');
}
function closeProfile() {
  resetProfile();
  prof.on = false;
  profEl.hidden = true;
  document.body.classList.remove('profiling');
  document.querySelector('.profile-ctrl button')?.classList.remove('on');
  map.getCanvas().style.cursor = '';
}
document.getElementById('prof-close').onclick = closeProfile;
document.getElementById('prof-new').onclick = resetProfile;
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && prof.on) closeProfile(); });

function endMarker(label) {
  const el = document.createElement('div');
  el.className = 'prof-pin';
  el.textContent = label;
  return el;
}
map.on('click', (e) => {
  if (!prof.on) return;
  if (prof.pts.length === 2) resetProfile();
  const p = [e.lngLat.lng, e.lngLat.lat];
  prof.pts.push(p);
  prof.markers.push(new maplibregl.Marker({ element: endMarker(prof.pts.length === 1 ? 'A' : 'B'), opacityWhenCovered: '1' })
    .setLngLat(p).addTo(map));
  if (prof.pts.length === 1) { setHint('Now click the end point.'); return; }
  map.getSource('profile').setData({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: prof.pts } });
  runProfile();
});

async function runProfile() {
  const [a, b] = prof.pts;
  const L = haversineKm(a, b);
  if (L < 0.5) { resetProfile(); setHint('Line too short. Click the start point on the map.'); return; }
  const z = L < 25 ? 12 : L < 60 ? 11 : L < 150 ? 10 : L < 350 ? 9 : L < 800 ? 8 : 7;
  setHint(`Sampling ${PROF_N} points…`);
  document.getElementById('prof-new').hidden = false;
  const pts = Array.from({ length: PROF_N }, (_, i) => {
    const t = i / (PROF_N - 1);
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, t * L];
  });
  const [idx, hs] = await Promise.all([loadGeoIndex(), Promise.all(pts.map(([x, y]) => elevationAt(x, y, z)))]);
  if (prof.pts.length !== 2 || prof.pts[1] !== b) return;   // a new line was started meanwhile
  prof.data = pts.map(([x, y, d], i) => {
    const g = geologyAt(idx, x, y);
    const h = hs[i] ?? 0;
    return { x, y, d, h, cls: g ? g.level1_class : h < 0 ? 'Sea' : '', col: g ? g.level1_colour : h < 0 ? SEA_COLOUR : NODATA_COLOUR, gl: g };
  });
  setHint('');
  drawProfile();
}

function niceStep(range, n) {
  const raw = range / n, p = 10 ** Math.floor(Math.log10(raw)), m = raw / p;
  return (m < 1.5 ? 1 : m < 3 ? 2 : m < 7 ? 5 : 10) * p;
}

function drawProfile() {
  const D = prof.data;
  if (!D) return;
  const box = document.getElementById('prof-chart');
  const W = Math.max(280, box.clientWidth), H = isPhone() ? 150 : 180;
  const m = { l: 46, r: 10, t: 10, b: 24 };
  const pw = W - m.l - m.r, ph = H - m.t - m.b;
  const L = D[D.length - 1].d;
  let lo = Math.min(...D.map((p) => p.h)), hi = Math.max(...D.map((p) => p.h));
  const pad = Math.max(20, (hi - lo) * 0.08);
  lo = lo < 0 ? lo - pad : Math.max(0, lo - pad);
  hi += pad;
  const X = (d) => m.l + d / L * pw, Y = (h) => m.t + (hi - h) / (hi - lo) * ph;
  const ve = (L * 1000 / pw) / ((hi - lo) / ph);
  // Coloured fill: one polygon per run of samples with the same colour.
  let fills = '';
  let start = 0;
  for (let i = 1; i <= D.length; i++) {
    if (i === D.length || D[i].col !== D[start].col) {
      const seg = D.slice(start, Math.min(i + 1, D.length));
      const top = seg.map((p) => `${X(p.d).toFixed(1)},${Y(p.h).toFixed(1)}`).join(' ');
      fills += `<polygon fill="${D[start].col}" points="${X(seg[0].d).toFixed(1)},${Y(lo).toFixed(1)} ${top} ${X(seg[seg.length - 1].d).toFixed(1)},${Y(lo).toFixed(1)}"/>`;
      start = i;
    }
  }
  const line = D.map((p, i) => `${i ? 'L' : 'M'}${X(p.d).toFixed(1)},${Y(p.h).toFixed(1)}`).join('');
  let grid = '';
  const ys = niceStep(hi - lo, 4);
  for (let v = Math.ceil(lo / ys) * ys; v <= hi; v += ys) {
    grid += `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(v)}" y2="${Y(v)}" class="g"/><text x="${m.l - 5}" y="${Y(v) + 3.5}" text-anchor="end">${fmt(Math.round(v))}</text>`;
  }
  const xs = niceStep(L, isPhone() ? 4 : 7);
  for (let v = 0; v <= L + 1e-9; v += xs) {
    if (X(v) > W - m.r - 24) break;   // keep clear of the "km" unit label
    grid += `<text x="${X(v)}" y="${H - 6}" text-anchor="middle">${fmt(+v.toFixed(1))}</text>`;
  }
  const sea = lo < 0 ? `<line x1="${m.l}" x2="${W - m.r}" y1="${Y(0)}" y2="${Y(0)}" class="sea"/>` : '';
  box.innerHTML =
    `<svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" class="prof-svg" role="img" aria-label="Elevation profile chart">` +
    `${grid}<g class="fill">${fills}</g>${sea}<path d="${line}" class="ln"/>` +
    `<text x="${W - m.r}" y="${H - 6}" text-anchor="end" class="unit">km</text>` +
    `<text x="${m.l - 5}" y="${m.t - 1}" text-anchor="end" class="unit">m</text>` +
    `<g class="hover" visibility="hidden"><line class="hl" y1="${m.t}" y2="${m.t + ph}"/><circle r="4"/></g>` +
    `<rect x="${m.l}" y="${m.t}" width="${pw}" height="${ph}" fill="transparent" class="hit"/></svg>`;
  document.getElementById('prof-info').textContent =
    `${fmt(+L.toFixed(1))} km · ${fmt(Math.round(Math.min(...D.map((p) => p.h))))} to ${fmt(Math.round(Math.max(...D.map((p) => p.h))))} m · vertical exaggeration ≈ ${ve >= 10 ? fmt(Math.round(ve)) : ve.toFixed(1)}×`;
  // Legend: classes crossed, in order of first appearance, with their share of the line.
  const share = new Map();
  for (const p of D) if (p.cls) share.set(p.cls, { col: p.col, n: (share.get(p.cls)?.n || 0) + 1 });
  document.getElementById('prof-legend').innerHTML = [...share].map(([c, v]) =>
    `<span><i style="background:${v.col}"></i>${esc(c)} <b>${Math.round(v.n / D.length * 100)}%</b></span>`).join('');
  // Hover / touch: crosshair on the chart, dot on the map.
  const svg = box.querySelector('svg'), hov = svg.querySelector('.hover');
  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const d = Math.min(L, Math.max(0, (ev.clientX - r.left - m.l) / pw * L));
    const p = D[Math.round(d / L * (D.length - 1))];
    hov.setAttribute('visibility', 'visible');
    hov.querySelector('line').setAttribute('x1', X(p.d)); hov.querySelector('line').setAttribute('x2', X(p.d));
    hov.querySelector('circle').setAttribute('cx', X(p.d)); hov.querySelector('circle').setAttribute('cy', Y(p.h));
    setHint(`${fmt(+p.d.toFixed(1))} km · ${fmt(Math.round(p.h))} m · ${p.cls || 'no geology mapped'}${p.gl?.level2_label ? ` (${p.gl.level2_label})` : ''}`);
    if (!prof.hover) {
      const el = document.createElement('div');
      el.className = 'prof-hover';
      prof.hover = new maplibregl.Marker({ element: el, opacityWhenCovered: '1' });
    }
    prof.hover.setLngLat([p.x, p.y]).addTo(map);
  };
  const leave = () => { hov.setAttribute('visibility', 'hidden'); prof.hover?.remove(); setHint(''); };
  svg.addEventListener('pointermove', move);
  svg.addEventListener('pointerdown', move);
  svg.addEventListener('pointerleave', leave);
}
window.addEventListener('resize', () => { if (prof.on && prof.data) drawProfile(); });

// ---- Stratigraphic column window ----
// Generalized outcrop succession of central/northern Arabia (top = youngest). th = approx. thickness (m),
// res = resistance to erosion (1 weak, 2 moderate, 3 escarpment-former), lith = pattern. Edit here.
const STRAT = [
  { cls: 'Neogene-Quaternary surficial deposits', period: 'Neogene–Quaternary', units: [
    { n: 'Eolian sand, sabkha and gravels', age: 'Pliocene–Holocene', lith: 'sand', th: 60, res: 1, note: 'Rub\' al Khali, Nafud and Dahna sand seas; coastal and inland sabkhas; alluvial fans' },
  ] },
  { cls: 'Paleogene-Neogene sedimentary', period: 'Paleogene–Neogene', units: [
    { n: 'Hadrukh, Dam and Hofuf fms', age: 'Miocene–Pliocene', lith: 'sand', th: 270, res: 2, note: 'Continental sandstone and marl with marine limestone (Dam)' },
    { n: 'Dammam Fm', age: 'Eocene', lith: 'lime', th: 35, res: 2, note: 'Shallow-marine limestone (Qatar, Bahrain, Al-Ahsa)' },
    { n: 'Rus Fm', age: 'Early Eocene', lith: 'anhy', th: 60, res: 1, note: 'Anhydrite, gypsum and chalky limestone' },
    { n: 'Umm er Radhuma Fm', age: 'Paleocene–Early Eocene', lith: 'lime', th: 240, res: 3, esc: 'Summan plateau', note: 'Dolomitic limestone; major aquifer' },
  ] },
  { cls: 'Cretaceous', period: 'Cretaceous', units: [
    { n: 'Aruma Fm', age: 'Late Cretaceous (Campanian–Maastrichtian)', lith: 'lime', th: 140, res: 3, esc: 'Aruma escarpment', note: 'Shallow-marine limestone' },
    { n: 'Wasia Fm', age: 'Mid-Cretaceous (Cenomanian)', lith: 'sand', th: 40, res: 1, note: 'Sandstone and shale; thickens to the Gulf' },
    { n: 'Biyadh Sandstone', age: 'Early Cretaceous (Aptian–Albian)', lith: 'sand', th: 420, res: 2, note: 'Continental to marginal-marine sandstone' },
    { n: 'Thamama Group (Sulaiy, Yamama, Buwaib)', age: 'Early Cretaceous (Berriasian–Valanginian)', lith: 'lime', th: 240, res: 2, note: 'Shelf limestones' },
  ] },
  { cls: 'Jurassic', period: 'Jurassic', units: [
    { n: 'Hith Anhydrite', age: 'Late Jurassic (Tithonian)', lith: 'anhy', th: 90, res: 1, note: 'Evaporite seal of the Arab reservoirs' },
    { n: 'Arab Fm', age: 'Late Jurassic (Kimmeridgian–Tithonian)', lith: 'mixed', th: 125, res: 2, note: 'Limestone–anhydrite cycles' },
    { n: 'Jubaila Fm', age: 'Late Jurassic (Kimmeridgian)', lith: 'lime', th: 120, res: 3, esc: 'Jubaila escarpment', note: 'Micritic limestone' },
    { n: 'Hanifa Fm', age: 'Late Jurassic (Oxfordian)', lith: 'lime', th: 115, res: 2, note: 'Limestone and calcareous shale' },
    { n: 'Tuwaiq Mountain Limestone', age: 'Middle Jurassic (Callovian)', lith: 'lime', th: 200, res: 3, esc: 'Tuwaiq escarpment', note: 'Coral–stromatoporoid limestone' },
    { n: 'Dhruma Fm', age: 'Middle Jurassic (Bajocian–Bathonian)', lith: 'mixed', th: 375, res: 2, note: 'Limestone and shale' },
    { n: 'Marrat Fm', age: 'Early Jurassic (Toarcian)', lith: 'mixed', th: 115, res: 2, note: 'Shale, limestone and sandstone' },
  ] },
  { cls: 'Triassic', period: 'Triassic', units: [
    { n: 'Minjur Sandstone', age: 'Late Triassic', lith: 'sand', th: 315, res: 2, note: 'Continental sandstone' },
    { n: 'Jilh Fm', age: 'Middle–Late Triassic', lith: 'mixed', th: 325, res: 2, note: 'Limestone, sandstone and gypsum' },
    { n: 'Sudair Shale', age: 'Early Triassic', lith: 'shale', th: 115, res: 1, note: 'Red and green shale' },
  ] },
  { cls: 'Paleozoic', period: 'Paleozoic', units: [
    { n: 'Khuff Fm', age: 'Late Permian', lith: 'lime', th: 170, res: 3, esc: 'Khuff escarpment', note: 'Shelf limestone; major gas reservoir in the subsurface' },
    { n: 'Unayzah Fm', age: 'Carboniferous–Early Permian', lith: 'sand', th: 100, res: 1, note: 'Glacial and fluvial sandstone; poorly exposed' },
    { n: 'Tawil and Jauf fms', age: 'Devonian', lith: 'mixed', th: 300, res: 2, note: 'Sandstone with limestone and shale (Jauf)' },
    { n: 'Qalibah Group (Qusaiba Shale)', age: 'Silurian', lith: 'shale', th: 600, res: 1, note: 'Graptolitic shale; main Paleozoic source rock' },
    { n: 'Qasim Fm', age: 'Ordovician', lith: 'mixed', th: 500, res: 2, note: 'Sandstone and shale, incl. Late Ordovician glacial deposits (Sarah)' },
    { n: 'Saq Sandstone', age: 'Cambrian–Ordovician', lith: 'sand', th: 600, res: 3, esc: 'cliffs (AlUla, Tabuk)', note: 'Fluvial to shallow-marine sandstone; major aquifer' },
  ] },
  { cls: 'Precambrian basement (Arabian Shield)', period: 'Precambrian', units: [
    { n: 'Arabian Shield', age: 'Neoproterozoic (c. 870–550 Ma)', lith: 'base', th: 0, res: 3, note: 'Island-arc volcanic and sedimentary rocks, ophiolites, gneiss and granites' },
  ] },
];

function stratSVG() {
  const colour = {};
  document.querySelectorAll('#legend li').forEach((li) => {
    colour[li.dataset.cls] = li.querySelector('.swatch').style.background;
  });
  const W = 660, perX = 0, perW = 118, colX = perW + 8, colW = 130, txtX = colX + colW + 18;
  const hOf = (u) => (u.lith === 'base' ? 62 : Math.max(26, Math.round(u.th * 0.11)));
  const widthOf = (u) => colW * (u.res === 3 ? 1 : u.res === 2 ? 0.8 : 0.6);
  let y = 8, body = '', per = '';
  for (const g of STRAT) {
    const y0 = y;
    const c = colour[g.cls] || '#ccc';
    for (const u of g.units) {
      const h = hOf(u), w = widthOf(u);
      const top = u.lith === 'base'
        ? `M${colX},${y + 6} q${w / 8},-8 ${w / 4},0 t${w / 4},0 t${w / 4},0 t${w / 4},0 V${y + h} H${colX} Z`
        : `M${colX},${y} H${colX + w} V${y + h} H${colX} Z`;
      body += `<path d="${top}" fill="${c}" stroke="rgba(0,0,0,.45)" stroke-width="1"/>` +
        `<path d="${top}" fill="url(#p-${u.lith})" stroke="none"/>`;
      if (u.esc) body += `<text x="${colX + w + 4}" y="${y + 13}" class="esc">▲</text>`;
      const mid = y + h / 2;
      body += `<text x="${txtX}" y="${mid - (h >= 34 ? 6 : 1)}" class="un">${esc(u.n)}` +
        (u.th ? ` <tspan class="th">~${fmt(u.th)} m</tspan>` : '') + `</text>` +
        `<text x="${txtX}" y="${mid + (h >= 34 ? 8 : 11)}" class="ua">${esc(u.age)}${u.esc ? ` · <tspan class="escn">${esc(u.esc)}</tspan>` : ''}</text>` +
        (h >= 48 ? `<text x="${txtX}" y="${mid + 21}" class="un2">${esc(u.note)}</text>` : '');
      body += `<title>${esc(`${u.n} — ${u.age}. ${u.note}`)}</title>`;
      y += h;
    }
    const lines = g.period.includes('–') && y - y0 >= 40 ? g.period.replace('–', '–\n').split('\n') : [g.period];
    per += `<rect x="${perX}" y="${y0}" width="${perW}" height="${y - y0}" fill="${c}" stroke="rgba(0,0,0,.45)"/>` +
      `<text x="${perX + perW / 2}" y="${(y0 + y) / 2 + 4 - (lines.length - 1) * 6}" text-anchor="middle" class="per">` +
      lines.map((t, k) => `<tspan x="${perX + perW / 2}" dy="${k ? 12 : 0}">${esc(t)}</tspan>`).join('') + `</text>`;
  }
  const pat = `<defs>
    <pattern id="p-sand" width="8" height="8" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r=".9" fill="rgba(0,0,0,.45)"/><circle cx="6" cy="6" r=".9" fill="rgba(0,0,0,.45)"/></pattern>
    <pattern id="p-lime" width="16" height="8" patternUnits="userSpaceOnUse"><path d="M0 0H16M0 8H16M4 0V8" stroke="rgba(0,0,0,.35)" stroke-width=".8"/></pattern>
    <pattern id="p-shale" width="12" height="5" patternUnits="userSpaceOnUse"><path d="M1 2.5H7" stroke="rgba(0,0,0,.4)" stroke-width=".9"/></pattern>
    <pattern id="p-anhy" width="8" height="8" patternUnits="userSpaceOnUse"><path d="M0 8L8 0" stroke="rgba(0,0,0,.35)" stroke-width=".8"/></pattern>
    <pattern id="p-mixed" width="16" height="10" patternUnits="userSpaceOnUse"><path d="M0 0H16M4 0V5M0 5H16" stroke="rgba(0,0,0,.33)" stroke-width=".8"/><path d="M8 7.5H13" stroke="rgba(0,0,0,.4)" stroke-width=".9"/></pattern>
    <pattern id="p-base" width="12" height="12" patternUnits="userSpaceOnUse"><path d="M3 3l3 6 3-6" fill="none" stroke="rgba(0,0,0,.4)" stroke-width=".9"/></pattern>
  </defs>`;
  return `<svg viewBox="0 0 ${W} ${y + 10}" class="strat-svg" role="img" aria-label="Generalized stratigraphic column of the Arabian Platform">${pat}${per}${body}</svg>` +
    `<div class="strat-key"><span><i class="k-sand"></i>Sandstone</span><span><i class="k-lime"></i>Limestone / dolomite</span><span><i class="k-shale"></i>Shale</span>` +
    `<span><i class="k-anhy"></i>Anhydrite / gypsum</span><span><i class="k-mixed"></i>Mixed carbonate–clastic</span><span><i class="k-base"></i>Crystalline basement</span><span>▲ escarpment-former</span></div>` +
    `<p class="strat-vol"><i style="background:${colour['Cenozoic volcanics'] || '#D9B400'}"></i><span><b>Cenozoic volcanics</b> are not part of the layered platform succession: the Yemen traps (flood basalts and silicic volcanics, c. 31–29 Ma) cap the Yemen highlands, and the harrats (alkali basalt fields, Miocene–Holocene) lie directly on the Shield.</span></p>`;
}
document.querySelector('[data-open="strat-win"]').addEventListener('click', () => {
  const box = document.getElementById('strat-col');
  if (!box.innerHTML) box.innerHTML = stratSVG();
});

// ---- Phone panel toggle ----
document.getElementById('panel-open').onclick = () => document.body.classList.add('panel-visible');
document.getElementById('panel-close').onclick = () => document.body.classList.remove('panel-visible');

// Keep the map sized to its container when the layout changes.
window.addEventListener('resize', () => map.resize());
