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
// Home view: whole peninsula. Phones get a flatter camera and room above for the intro card.
const HOME_PITCH = () => (isPhone() ? 20 : 45);
const HOME_PADDING = () => (isPhone() ? { top: 190, bottom: 40, left: 10, right: 10 } : 30);

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
    tour: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } },
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

// Elevation bar on a shared 0..ELEV_MAX m scale; negative values clip to 0.
const ELEV_MAX = 3700;
const fmt = (v) => v.toLocaleString('en-US').replace('-', '−');

function statsText(st) {
  return `min ${fmt(st.min)} · p10 ${fmt(st.p10)} · <b>median ${fmt(st.median)}</b> · p90 ${fmt(st.p90)} · max ${fmt(st.max)} m`;
}

function elevBar(st, colour) {
  if (!st) return '';
  const x = (v) => `${(Math.min(Math.max(v, 0), ELEV_MAX) / ELEV_MAX * 100).toFixed(2)}%`;
  const w = (a, b) => `${((Math.min(Math.max(b, 0), ELEV_MAX) - Math.min(Math.max(a, 0), ELEV_MAX)) / ELEV_MAX * 100).toFixed(2)}%`;
  const tip =
    `Elevation (m): min ${fmt(st.min)} · p10 ${fmt(st.p10)} · median ${fmt(st.median)} · ` +
    `p90 ${fmt(st.p90)} · max ${fmt(st.max)}\n${fmt(st.n_px)} px at ~1.2 km, ${fmt(st.n_neg)} below 0 m`;
  return `<span class="ebar" title="${tip}" role="button" tabindex="0" aria-label="Show elevation statistics">` +
    `<span class="whisk" style="left:${x(st.min)};width:${w(st.min, st.max)};background:${colour}"></span>` +
    `<span class="box" style="left:${x(st.p10)};width:${w(st.p10, st.p90)};background:${colour}"></span>` +
    `<span class="med" style="left:${x(st.median)}"></span></span>`;
}

function buildLegend(classes, elev) {
  const ul = document.getElementById('legend');
  for (const c of classes) {
    enabled.add(c.name);
    const li = document.createElement('li');
    li.dataset.cls = c.name;
    li.innerHTML =
      `<label><input type="checkbox" checked>` +
      `<span class="swatch" style="background:${c.colour}"></span>` +
      `<span class="text"><span class="name">${c.name}</span><br><span class="codes">${c.codes.join(', ')}</span>` +
      `${elevBar(elev[c.name], c.colour)}</span></label>` +
      (elev[c.name] ? `<div class="estats" hidden>${statsText(elev[c.name])}</div>` : '');
    // Bars sit inside the <label>: stop the click from toggling the checkbox, show the numbers instead.
    const bar = li.querySelector('.ebar');
    if (bar) {
      const toggle = (e) => {
        e.preventDefault();
        e.stopPropagation();
        const box = li.querySelector('.estats');
        box.hidden = !box.hidden;
      };
      bar.addEventListener('click', toggle);
      bar.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') toggle(e); });
    }
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
  getJSON('data/elev_stats.json').catch(() => ({ level1: {} })),
]).then(([j, e]) => { units = j.units; source = j.source; buildLegend(j.classes, e.level1); });

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

// ---- Bookmarks and tour ----
// Captions: sentence 1 = the geology, sentence 2 = how it shows in the relief. Edit here.
const STOPS = [
  {
    title: 'Hijaz–Asir escarpment and the Arabian Shield',
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
    title: 'Tuwaiq escarpment',
    camera: { center: [46.4, 24.3], zoom: 8, pitch: 62, bearing: 90 },
    marks: {
      areas: [['Arabian Shield', 45.05, 23.75], ['Jurassic outcrop', 46.75, 23.6]],
      lines: [['Tuwaiq escarpment', [[45.14, 20.0], [45.18, 20.25], [45.32, 20.5], [45.34, 20.75], [45.44, 21.0], [45.52, 21.25], [45.59, 21.5], [45.68, 21.75], [45.9, 22.25], [46.01, 22.5], [46.1, 22.75], [46.26, 23.0], [46.33, 23.25], [46.41, 23.5], [46.46, 23.75], [46.38, 24.0], [46.35, 24.25], [46.42, 24.5], [46.1, 24.75], [45.96, 25.0], [46.05, 25.25]]]],
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

function showCaption(i) {
  const st = STOPS[i];
  caption.querySelector('h3').textContent = `${i + 1}. ${st.title}`;
  caption.querySelector('p').textContent = st.caption;
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
  if (mk.focus) {
    for (const l of ['focus-glow', 'focus-line']) {
      map.setFilter(l, mk.focus);
      map.setLayoutProperty(l, 'visibility', 'visible');
    }
  }
}

function hideCaption() {
  caption.hidden = true;
  document.querySelectorAll('#bookmarks button').forEach((b) => b.classList.remove('active'));
}
caption.querySelector('.caption-close').onclick = hideCaption;

function goTo(i, duration) {
  hideIntro();
  showCaption(i);
  showMarks(i);
  if (isPhone()) document.body.classList.remove('panel-visible');
  // Only pass duration when set: an explicit undefined overrides MapLibre's default and yields NaN frames.
  map.flyTo({ ...STOPS[i].camera, ...(duration ? { duration } : {}), essential: true });
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
const TILE_CACHE_MAX = 48;

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

async function elevationAt(lng, lat) {
  const z = Math.max(7, Math.min(12, Math.floor(map.getZoom()) + 2));
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

// ---- Phone panel toggle ----
document.getElementById('panel-open').onclick = () => document.body.classList.add('panel-visible');
document.getElementById('panel-close').onclick = () => document.body.classList.remove('panel-visible');

// Keep the map sized to its container when the layout changes.
window.addEventListener('resize', () => map.resize());
