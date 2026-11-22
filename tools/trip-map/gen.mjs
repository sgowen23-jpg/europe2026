// Builds trip-map.js (the map landing screen) from template.js.
// Projects real coastlines into SVG paths and works out city positions.
// Run from this folder:  npm install && node gen.mjs
import * as d3 from 'd3-geo';
import * as topo from 'topojson-client';
import fs from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
const HERE = path.dirname(fileURLToPath(import.meta.url));

const W = 1000, H = 1080;
const INSET = { x: 590, y: 752, w: 396, h: 316 };
const world = JSON.parse(fs.readFileSync(path.join(HERE, 'node_modules/world-atlas/countries-50m.json')));
const countries = topo.feature(world, world.objects.countries);

const AFRICA = new Set(['Morocco', 'Algeria', 'Tunisia', 'Libya', 'Egypt', 'W. Sahara', 'Mauritania', 'Mali', 'Niger',
  'Chad', 'Sudan', 'S. Sudan', 'Somalia', 'Somaliland', 'Ethiopia', 'Eritrea', 'Djibouti', 'Kenya', 'Tanzania',
  'Madagascar', 'Mozambique', 'Uganda']);
const notAfrica = { type: 'FeatureCollection', features: countries.features.filter(f => !AFRICA.has(f.properties.name)) };

// Main map: Lambert conformal conic centred on Europe.
const main = d3.geoConicConformal().parallels([38, 56]).rotate([-11, 0]);
main.fitWidth(W, { type: 'MultiPoint', coordinates: [[-10.5, 36], [-10.5, 57], [31, 36], [31, 57]] });
const [tx, ty] = main.translate();
main.translate([tx, ty + 40]).clipExtent([[0, 0], [W, H]]);
const mainPath = d3.geoPath(main).digits(1);
const land = mainPath(notAfrica);
const borders = mainPath(topo.mesh(world, world.objects.countries, (a, b) => a !== b));

// Inset: Mercator from the Gulf to Australia.
const inset = d3.geoMercator();
inset.fitExtent([[INSET.x + 10, INSET.y + 34], [INSET.x + INSET.w - 10, INSET.y + INSET.h - 8]],
  { type: 'MultiPoint', coordinates: [[50, 27], [153, -39], [50, -39], [153, 27]] });
inset.clipExtent([[INSET.x, INSET.y], [INSET.x + INSET.w, INSET.y + INSET.h]]);
const insetPath = d3.geoPath(inset).digits(1);
const insetLand = insetPath(notAfrica);

const C = {
  ADL: ['Adelaide', 138.6, -34.93, 'i', 'Home · 11 Sep & 17 Oct'],
  DXB: ['Dubai', 55.27, 25.2, 'i', '12 Sep · layover'],
  SIN: ['Singapore', 103.82, 1.35, 'i', 'Late Sep – early Oct'],
  ATH: ['Athens', 23.73, 37.98, 'm', '12–16 Sep'],
  IKA: ['Ikaria', 26.15, 37.6, 'm', '16–22 Sep'],
  KAL: ['Kalamata', 22.11, 37.04, 'm', '22–26 Sep'],
  THE: ['Thessaloniki', 22.94, 40.64, 'm', '22–26 Sep'],
  NCE: ['Nice', 7.26, 43.7, 'm', '22–26 Sep'],
  PAR: ['Paris & Disneyland', 2.5, 48.86, 'm', '27 Sep – 3 Oct'],
  LON: ['UK', -0.13, 51.5, 'm', '~3 Oct'],
  BEG: ['Belgrade', 20.46, 44.79, 'm', '3–9 Oct'],
  VLC: ['Valencia', -0.38, 39.47, 'm', '1–3 Oct'],
  BCN: ['Barcelona', 2.17, 41.39, 'm', '3–6 Oct'],
  MAD: ['Madrid', -3.7, 40.42, 'm', '6–9 Oct'],
  FLR: ['Florence', 11.26, 43.77, 'm', '9–12 Oct'],
  ROM: ['Rome', 12.5, 41.9, 'm', '12–16 Oct']
};
const cities = {};
for (const id in C) {
  const [name, lon, lat, which, dates] = C[id];
  const p = (which === 'i' ? inset : main)([lon, lat]);
  cities[id] = { name, x: +p[0].toFixed(1), y: +p[1].toFixed(1), dates, inset: which === 'i' };
}

let js = fs.readFileSync(path.join(HERE, 'template.js'), 'utf8');
js = js.replace('__LAND__', land).replace('__BORDERS__', borders).replace('__INSETLAND__', insetLand)
  .replace('__CITIES__', JSON.stringify(cities)).replace('__INSET__', JSON.stringify(INSET));
fs.writeFileSync(path.join(HERE, '../../trip-map.js'), js);
console.log('wrote trip-map.js,', Math.round(js.length / 1024), 'KB');
