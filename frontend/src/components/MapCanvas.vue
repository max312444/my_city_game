<script setup>
import { onMounted, onUnmounted, ref, reactive, watch } from 'vue'
import { useMapStore } from '../stores/map'
import { useNationStore } from '../stores/nation'
import { useDiplomacyStore } from '../stores/diplomacy'
import { useTerritoryStore } from '../stores/territory'
import { useCityStore } from '../stores/city'
import { useBuildingStore } from '../stores/buildings'
import { useTechStore } from '../stores/tech'

const mapStore = useMapStore()
const nationStore = useNationStore()
const diplomacyStore = useDiplomacyStore()
const territoryStore = useTerritoryStore()
const cityStore = useCityStore()
const buildingStore = useBuildingStore()
const techStore = useTechStore()
const canvasRef = ref(null)

// Two shades per terrain (low, high) — the noise layer blends between them so
// each tile reads as a natural, uneven surface instead of one flat color.
const TERRAIN_SHADES = {
  grass: [
    [66, 108, 52],
    [104, 150, 74],
  ],
  forest: [
    [24, 54, 30],
    [46, 84, 42],
  ],
  mountain: [
    [96, 92, 86],
    [148, 144, 136],
  ],
  water: [
    [24, 62, 98],
    [58, 108, 152],
  ],
  desert: [
    [168, 138, 84],
    [214, 186, 128],
  ],
}

// Mirrors backend RESOURCE_TYPES (app/services/map_service.py) — the backend is the
// source of truth for which stat each type boosts, this is just icon/label for display.
const RESOURCE_META = {
  gold_mine: { name: '금광', icon: '⛏️' },
  iron_ore: { name: '철광', icon: '⚒️' },
  fertile_soil: { name: '비옥한 토양', icon: '🌾' },
  timber: { name: '목재', icon: '🌲' },
  spice: { name: '향신료', icon: '🌶️' },
  horses: { name: '말', icon: '🐎' },
  fish: { name: '어장', icon: '🐟' },
}

const RIVAL_COLORS = ['#e0484d', '#a855f7', '#f97316', '#22c1a8']
const PLAYER_COLOR = '#4a90d9'

// tier: 0 village, 1 town, 2 city, 3 metropolis — driven by how many tiles an
// owner (player or rival) actually holds, since everyone expands the same way
// now: claiming tiles one at a time, adjacent to what they already own. Shown as
// an emoji badge instead of a Korean label so the name plate stays uncluttered.
const TIER_EMOJI = ['🏘️', '🏙️', '🌆', '🌃']
const MIN_CITY_DISTANCE = 3
const TEXTURE_PX_PER_TILE = 24

function tierFromTileCount(count) {
  if (count >= 60) return 3
  if (count >= 30) return 2
  if (count >= 15) return 1
  return 0
}

// --- deterministic value noise (no deps) -----------------------------------
function makeNoise2D(seed) {
  let s = seed >>> 0
  const rand = () => {
    s = (s * 1664525 + 1013904223) >>> 0
    return s / 4294967296
  }
  const perm = new Uint8Array(256)
  for (let i = 0; i < 256; i++) perm[i] = i
  for (let i = 255; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1))
    const t = perm[i]
    perm[i] = perm[j]
    perm[j] = t
  }
  const p = new Uint8Array(512)
  for (let i = 0; i < 512; i++) p[i] = perm[i & 255]

  const fade = (t) => t * t * t * (t * (t * 6 - 15) + 10)
  const lerp = (a, b, t) => a + t * (b - a)
  const grad = (hash, x, y) => {
    const h = hash & 3
    const u = h < 2 ? x : y
    const v = h < 2 ? y : x
    return (h & 1 ? -u : u) + (h & 2 ? -2 * v : 2 * v)
  }
  return (x, y) => {
    const X = Math.floor(x) & 255
    const Y = Math.floor(y) & 255
    const xf = x - Math.floor(x)
    const yf = y - Math.floor(y)
    const u = fade(xf)
    const v = fade(yf)
    const aa = p[p[X] + Y]
    const ab = p[p[X] + Y + 1]
    const ba = p[p[X + 1] + Y]
    const bb = p[p[X + 1] + Y + 1]
    const res = lerp(
      lerp(grad(aa, xf, yf), grad(ba, xf - 1, yf), u),
      lerp(grad(ab, xf, yf - 1), grad(bb, xf - 1, yf - 1), u),
      v,
    )
    return (res + 1) / 2
  }
}

const noiseA = makeNoise2D(1337)
const noiseB = makeNoise2D(90210)

function lerpColor(c1, c2, t) {
  return [c1[0] + (c2[0] - c1[0]) * t, c1[1] + (c2[1] - c1[1]) * t, c1[2] + (c2[2] - c1[2]) * t]
}

function buildTerrainTexture(tiles, mapW, mapH) {
  const tw = mapW * TEXTURE_PX_PER_TILE
  const th = mapH * TEXTURE_PX_PER_TILE
  const off = document.createElement('canvas')
  off.width = tw
  off.height = th
  const octx = off.getContext('2d')
  const img = octx.createImageData(tw, th)
  const data = img.data

  for (let py = 0; py < th; py++) {
    const ty = Math.floor(py / TEXTURE_PX_PER_TILE)
    for (let px = 0; px < tw; px++) {
      const tx = Math.floor(px / TEXTURE_PX_PER_TILE)
      const terrain = tiles[ty][tx]
      const shades = TERRAIN_SHADES[terrain] || [
        [60, 60, 60],
        [90, 90, 90],
      ]
      const n1 = noiseA(px * 0.09, py * 0.09)
      const n2 = noiseB(px * 0.22, py * 0.22) * 0.4
      const t = Math.max(0, Math.min(1, n1 * 0.75 + n2 + 0.15))
      const [r, g, b] = lerpColor(shades[0], shades[1], t)
      const idx = (py * tw + px) * 4
      data[idx] = r
      data[idx + 1] = g
      data[idx + 2] = b
      data[idx + 3] = 255
    }
  }
  octx.putImageData(img, 0, 0)
  return off
}

function hashTile(x, y, salt) {
  let h = (x * 374761393 + y * 668265263 + salt * 2246822519) | 0
  h = (h ^ (h >>> 13)) * 1274126177
  h = (h ^ (h >>> 16)) >>> 0
  return h / 4294967295
}

function drawTileDetails(ctx, x, y, terrain, px, py, size) {
  if (terrain === 'forest') {
    const n = 3 + Math.floor(hashTile(x, y, 2) * 3)
    for (let i = 0; i < n; i++) {
      const ox = px + size * (0.2 + hashTile(x, y, 10 + i) * 0.6)
      const oy = py + size * (0.25 + hashTile(x, y, 20 + i) * 0.55)
      const s = size * (0.16 + hashTile(x, y, 60 + i) * 0.08)
      ctx.fillStyle = 'rgba(10,20,10,0.25)'
      ctx.beginPath()
      ctx.ellipse(ox + s * 0.15, oy + s * 0.75, s * 0.7, s * 0.28, 0, 0, Math.PI * 2)
      ctx.fill()
      const greens = ['rgba(20,50,22,0.95)', 'rgba(32,68,32,0.95)', 'rgba(46,86,40,0.9)']
      ctx.fillStyle = greens[i % greens.length]
      ctx.beginPath()
      ctx.ellipse(ox, oy - s * 0.5, s * 0.55, s * 0.6, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.ellipse(ox - s * 0.35, oy - s * 0.2, s * 0.4, s * 0.42, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.ellipse(ox + s * 0.35, oy - s * 0.15, s * 0.4, s * 0.42, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = 'rgba(58,38,20,0.9)'
      ctx.fillRect(ox - s * 0.06, oy + s * 0.1, s * 0.12, s * 0.55)
    }
  } else if (terrain === 'mountain') {
    const cx = px + size * 0.5
    const baseY = py + size * 0.88
    const peaks = [
      { dx: -0.28, h: 0.55, w: 0.42 },
      { dx: 0.08, h: 0.72, w: 0.5 },
      { dx: 0.38, h: 0.48, w: 0.38 },
    ]
    for (const pk of peaks) {
      const peakX = cx + size * pk.dx
      const peakY = py + size * (0.88 - pk.h)
      const grad = ctx.createLinearGradient(0, peakY, 0, baseY)
      grad.addColorStop(0, 'rgba(150,146,140,0.95)')
      grad.addColorStop(0.55, 'rgba(94,90,84,0.95)')
      grad.addColorStop(1, 'rgba(64,60,56,0.95)')
      ctx.fillStyle = grad
      ctx.beginPath()
      ctx.moveTo(peakX - size * pk.w, baseY)
      ctx.lineTo(peakX - size * pk.w * 0.15, peakY + size * 0.08)
      ctx.lineTo(peakX, peakY)
      ctx.lineTo(peakX + size * pk.w * 0.2, peakY + size * 0.1)
      ctx.lineTo(peakX + size * pk.w, baseY)
      ctx.closePath()
      ctx.fill()
      ctx.strokeStyle = 'rgba(40,38,34,0.35)'
      ctx.lineWidth = Math.max(1, size * 0.02)
      ctx.beginPath()
      ctx.moveTo(peakX - size * pk.w * 0.3, baseY - size * 0.05)
      ctx.lineTo(peakX - size * pk.w * 0.05, peakY + size * 0.28)
      ctx.stroke()
      ctx.fillStyle = 'rgba(245,247,250,0.95)'
      ctx.beginPath()
      ctx.moveTo(peakX - size * pk.w * 0.22, peakY + size * 0.18)
      ctx.lineTo(peakX, peakY)
      ctx.lineTo(peakX + size * pk.w * 0.24, peakY + size * 0.2)
      ctx.lineTo(peakX + size * pk.w * 0.06, peakY + size * 0.14)
      ctx.lineTo(peakX - size * pk.w * 0.04, peakY + size * 0.24)
      ctx.closePath()
      ctx.fill()
    }
  } else if (terrain === 'water') {
    const grad = ctx.createLinearGradient(px, py, px, py + size)
    grad.addColorStop(0, 'rgba(255,255,255,0.05)')
    grad.addColorStop(1, 'rgba(0,20,40,0.12)')
    ctx.fillStyle = grad
    ctx.fillRect(px, py, size, size)
    ctx.strokeStyle = 'rgba(220,238,250,0.45)'
    ctx.lineWidth = Math.max(1, size * 0.035)
    for (let i = 0; i < 3; i++) {
      const oy = py + size * (0.22 + i * 0.28 + hashTile(x, y, 30 + i) * 0.08)
      ctx.beginPath()
      ctx.moveTo(px + size * 0.1, oy)
      ctx.quadraticCurveTo(px + size * 0.5, oy - size * 0.1, px + size * 0.9, oy)
      ctx.stroke()
    }
    if (hashTile(x, y, 8) > 0.6) {
      ctx.fillStyle = 'rgba(255,255,255,0.55)'
      ctx.beginPath()
      ctx.arc(px + size * hashTile(x, y, 9), py + size * hashTile(x, y, 11), size * 0.025, 0, Math.PI * 2)
      ctx.fill()
    }
  } else if (terrain === 'desert') {
    ctx.strokeStyle = 'rgba(120,92,48,0.35)'
    ctx.lineWidth = Math.max(1, size * 0.05)
    for (let i = 0; i < 2; i++) {
      const oy = py + size * (0.35 + i * 0.32 + hashTile(x, y, 12 + i) * 0.1)
      ctx.beginPath()
      ctx.moveTo(px + size * 0.05, oy)
      ctx.quadraticCurveTo(px + size * 0.5, oy + size * 0.14, px + size * 0.95, oy - size * 0.02)
      ctx.stroke()
    }
    ctx.fillStyle = 'rgba(90,65,30,0.25)'
    const n = 2 + Math.floor(hashTile(x, y, 3) * 3)
    for (let i = 0; i < n; i++) {
      const ox = px + size * hashTile(x, y, 40 + i)
      const oy = py + size * hashTile(x, y, 50 + i)
      ctx.beginPath()
      ctx.arc(ox, oy, size * 0.03, 0, Math.PI * 2)
      ctx.fill()
    }
  } else if (terrain === 'grass') {
    const n = hashTile(x, y, 4) > 0.55 ? 2 : 0
    for (let i = 0; i < n; i++) {
      ctx.strokeStyle = `rgba(200,230,175,${0.35 + hashTile(x, y, 70 + i) * 0.2})`
      ctx.lineWidth = Math.max(1, size * 0.035)
      const ox = px + size * hashTile(x, y, 5 + i * 3)
      const oy = py + size * (0.55 + hashTile(x, y, 6 + i * 3) * 0.35)
      ctx.beginPath()
      ctx.moveTo(ox, oy)
      ctx.quadraticCurveTo(ox - size * 0.03, oy - size * 0.14, ox - size * 0.07, oy - size * 0.22)
      ctx.moveTo(ox + size * 0.04, oy)
      ctx.quadraticCurveTo(ox + size * 0.06, oy - size * 0.12, ox + size * 0.03, oy - size * 0.2)
      ctx.stroke()
    }
  }

  ctx.strokeStyle = 'rgba(0,0,0,0.06)'
  ctx.lineWidth = 1
  ctx.strokeRect(px + 0.5, py + 0.5, size - 1, size - 1)
}

// Every owner's territory is a real, possibly-irregular set of claimed tiles —
// fill each owned tile, then draw a border only along edges that face a
// tile owned by someone else (or no one), so the outline hugs the actual
// claimed shape instead of a fixed geometric block.
function drawOwnedTerritory(ctx, ownedTiles, offsetX, offsetY, tileSize, color) {
  const ownedSet = new Set(ownedTiles.map((t) => `${t.x},${t.y}`))
  ctx.fillStyle = `${color}22`
  for (const t of ownedTiles) {
    ctx.fillRect(offsetX + t.x * tileSize, offsetY + t.y * tileSize, tileSize, tileSize)
  }
  ctx.strokeStyle = color
  ctx.lineWidth = 3
  ctx.beginPath()
  for (const t of ownedTiles) {
    const px = offsetX + t.x * tileSize
    const py = offsetY + t.y * tileSize
    if (!ownedSet.has(`${t.x},${t.y - 1}`)) {
      ctx.moveTo(px, py)
      ctx.lineTo(px + tileSize, py)
    }
    if (!ownedSet.has(`${t.x},${t.y + 1}`)) {
      ctx.moveTo(px, py + tileSize)
      ctx.lineTo(px + tileSize, py + tileSize)
    }
    if (!ownedSet.has(`${t.x - 1},${t.y}`)) {
      ctx.moveTo(px, py)
      ctx.lineTo(px, py + tileSize)
    }
    if (!ownedSet.has(`${t.x + 1},${t.y}`)) {
      ctx.moveTo(px + tileSize, py)
      ctx.lineTo(px + tileSize, py + tileSize)
    }
  }
  ctx.stroke()
}

function shadeColor([r, g, b], amt) {
  const cl = (v) => Math.max(0, Math.min(255, v))
  return `rgb(${cl(r + amt)},${cl(g + amt)},${cl(b + amt)})`
}

function hexToRgb(hex) {
  const v = hex.replace('#', '')
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)]
}

const ROOF_COLORS = ['rgba(122,44,34,0.95)', 'rgba(101,58,30,0.95)', 'rgba(140,55,45,0.95)']

// Era visuals are scoped to the player only — rivals have no tech tree of their own
// (an existing, documented simplification), so there's no meaningful era to derive
// for them. `era` is left null for every rival drawCity() call below.
const ERA_ROOF_COLORS = {
  primitive: ['rgba(120,84,42,0.95)', 'rgba(102,70,36,0.95)'],
  bronze: ['rgba(150,108,54,0.95)', 'rgba(128,92,42,0.95)'],
  iron: ['rgba(90,90,96,0.95)', 'rgba(76,76,82,0.95)'],
  classical: ROOF_COLORS,
  medieval: ['rgba(58,78,108,0.95)', 'rgba(70,68,88,0.95)', 'rgba(64,90,96,0.95)'],
  renaissance: ['rgba(110,70,120,0.95)', 'rgba(150,120,50,0.95)'],
  enlightenment: ['rgba(90,60,140,0.95)', 'rgba(60,100,140,0.95)'],
  industrial: ['rgba(70,70,74,0.95)', 'rgba(90,60,40,0.95)'],
}
const ERA_ICON = {
  primitive: '🔥',
  bronze: '🪓',
  iron: '⚒️',
  classical: '🏛️',
  medieval: '🏰',
  renaissance: '🎨',
  enlightenment: '💡',
  industrial: '⚙️',
}

function drawCity(ctx, cx, cy, tileSize, tier, color, name, isPlayer, seed, era = null) {
  const buildings = [
    [{ w: 0.5, h: 0.4, roof: true }],
    [
      { w: 0.4, h: 0.4, roof: true, dx: -0.32 },
      { w: 0.4, h: 0.5, roof: true, dx: 0.32 },
      { w: 0.35, h: 0.35, roof: true, dx: 0 },
    ],
    [
      { w: 0.32, h: 0.55, dx: -0.4 },
      { w: 0.32, h: 0.7, dx: 0 },
      { w: 0.32, h: 0.45, dx: 0.4 },
      { w: 0.22, h: 0.35, dx: -0.65 },
      { w: 0.22, h: 0.35, dx: 0.65 },
    ],
    [
      { w: 0.28, h: 0.75, dx: -0.5 },
      { w: 0.3, h: 1.0, dx: -0.15 },
      { w: 0.26, h: 0.85, dx: 0.2 },
      { w: 0.22, h: 0.6, dx: 0.55 },
      { w: 0.22, h: 0.5, dx: -0.8 },
      { w: 0.2, h: 0.45, dx: 0.85 },
    ],
  ][tier]

  const scale = tileSize * (1.3 + tier * 0.35)
  const baseY = cy + scale * 0.4

  if (isPlayer) {
    ctx.beginPath()
    ctx.arc(cx, cy, scale * 0.75, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(255, 209, 102, 0.18)'
    ctx.fill()
  }

  // ground clearing so buildings don't look like they float on the grass
  ctx.beginPath()
  ctx.ellipse(cx, baseY - scale * 0.02, scale * 0.95, scale * 0.32, 0, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(120,100,70,0.35)'
  ctx.fill()

  buildings.forEach((b, i) => {
    const bw = scale * b.w
    const bh = scale * b.h
    const bx = cx + scale * (b.dx || 0) - bw / 2
    const by = baseY - bh

    // soft drop shadow
    ctx.beginPath()
    ctx.ellipse(bx + bw / 2, by + bh + bh * 0.08, bw * 0.55, bh * 0.12, 0, 0, Math.PI * 2)
    ctx.fillStyle = 'rgba(0,0,0,0.25)'
    ctx.fill()

    const base = hexToRgb(color)
    const grad = ctx.createLinearGradient(bx, by, bx, by + bh)
    grad.addColorStop(0, shadeColor(base, 18))
    grad.addColorStop(1, shadeColor(base, -22))
    ctx.fillStyle = grad
    ctx.fillRect(bx, by, bw, bh)
    ctx.strokeStyle = 'rgba(0,0,0,0.3)'
    ctx.lineWidth = 1
    ctx.strokeRect(bx, by, bw, bh)

    if (b.roof) {
      const roofColors = ERA_ROOF_COLORS[era] || ROOF_COLORS
      ctx.fillStyle = roofColors[(i + seed) % roofColors.length]
      ctx.beginPath()
      ctx.moveTo(bx - bw * 0.1, by)
      ctx.lineTo(bx + bw / 2, by - bh * 0.5)
      ctx.lineTo(bx + bw * 1.1, by)
      ctx.closePath()
      ctx.fill()
    } else {
      ctx.fillStyle = 'rgba(255,230,150,0.7)'
      const rows = Math.max(1, Math.floor(bh / (tileSize * 0.3)))
      for (let r = 0; r < rows; r++) {
        ctx.fillRect(bx + bw * 0.2, by + bh * 0.15 + (r * (bh * 0.7)) / rows, bw * 0.2, bh * 0.12)
        ctx.fillRect(bx + bw * 0.6, by + bh * 0.15 + (r * (bh * 0.7)) / rows, bw * 0.2, bh * 0.12)
      }
    }
  })

  ctx.fillStyle = 'white'
  ctx.font = `bold ${Math.max(11, tileSize * 0.42)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.shadowColor = 'rgba(0,0,0,0.8)'
  ctx.shadowBlur = 3
  ctx.fillText(`${era ? ERA_ICON[era] + ' ' : ''}${TIER_EMOJI[tier]} ${name}`, cx, baseY + scale * 0.4)
  ctx.shadowBlur = 0
}

// A defeated rival's capital is drawn as quiet ruins instead of a living city —
// dim rubble, no territory fill (they own nothing anymore), name struck through
// with a skull to make the fall legible at a glance.
function drawRuins(ctx, cx, cy, tileSize, name) {
  const scale = tileSize * 1.3
  const baseY = cy + scale * 0.4

  ctx.beginPath()
  ctx.ellipse(cx, baseY - scale * 0.02, scale * 0.85, scale * 0.28, 0, 0, Math.PI * 2)
  ctx.fillStyle = 'rgba(90,80,65,0.3)'
  ctx.fill()

  const rubble = [
    { dx: -0.3, w: 0.22, h: 0.18 },
    { dx: 0.05, w: 0.3, h: 0.28 },
    { dx: 0.35, w: 0.18, h: 0.14 },
  ]
  rubble.forEach((b) => {
    const bw = scale * b.w
    const bh = scale * b.h
    const bx = cx + scale * b.dx - bw / 2
    const by = baseY - bh
    ctx.fillStyle = 'rgba(90,86,80,0.55)'
    ctx.fillRect(bx, by, bw, bh)
    ctx.strokeStyle = 'rgba(40,38,34,0.5)'
    ctx.lineWidth = 1
    ctx.strokeRect(bx, by, bw, bh)
  })

  ctx.fillStyle = 'rgba(220,214,200,0.75)'
  ctx.font = `bold ${Math.max(10, tileSize * 0.36)}px sans-serif`
  ctx.textAlign = 'center'
  ctx.fillText(`💀 ${name} (멸망)`, cx, baseY + scale * 0.4)
}

// Kept in sync at the end of every draw() so the click handler can translate
// mouse coordinates back into tile coordinates.
const layout = reactive({ offsetX: 0, offsetY: 0, tileSize: 1 })
let cachedTexture = null
let cachedTextureKey = ''

const purchasePrompt = ref(null)
const foundCityPrompt = ref(null)
const attackPrompt = ref(null)
const buildingPrompt = ref(null)

function draw() {
  const canvas = canvasRef.value
  if (!canvas || !mapStore.tiles.length) return
  const ctx = canvas.getContext('2d')
  const dpr = window.devicePixelRatio || 1
  const w = window.innerWidth
  const h = window.innerHeight
  canvas.width = w * dpr
  canvas.height = h * dpr
  canvas.style.width = `${w}px`
  canvas.style.height = `${h}px`
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  ctx.clearRect(0, 0, w, h)

  const tileSize = Math.floor(Math.min(w / mapStore.width, h / mapStore.height))
  const offsetX = (w - tileSize * mapStore.width) / 2
  const offsetY = (h - tileSize * mapStore.height) / 2
  layout.offsetX = offsetX
  layout.offsetY = offsetY
  layout.tileSize = tileSize

  const textureKey = `${mapStore.width}x${mapStore.height}:${mapStore.tiles.flat().join(',')}`
  if (!cachedTexture || cachedTextureKey !== textureKey) {
    cachedTexture = buildTerrainTexture(mapStore.tiles, mapStore.width, mapStore.height)
    cachedTextureKey = textureKey
  }
  ctx.imageSmoothingEnabled = true
  ctx.drawImage(
    cachedTexture, 0, 0, cachedTexture.width, cachedTexture.height,
    offsetX, offsetY, tileSize * mapStore.width, tileSize * mapStore.height,
  )

  for (let y = 0; y < mapStore.height; y++) {
    for (let x = 0; x < mapStore.width; x++) {
      drawTileDetails(ctx, x, y, mapStore.tiles[y][x], offsetX + x * tileSize, offsetY + y * tileSize, tileSize)
    }
  }

  for (const res of mapStore.resources) {
    const meta = RESOURCE_META[res.type]
    if (!meta) continue
    const rx = offsetX + res.x * tileSize + tileSize / 2
    const ry = offsetY + res.y * tileSize + tileSize / 2
    ctx.font = `${tileSize * 0.55}px sans-serif`
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillText(meta.icon, rx, ry)
  }

  const tilesByOwner = new Map()
  for (const t of territoryStore.allTiles) {
    if (!tilesByOwner.has(t.owner)) tilesByOwner.set(t.owner, [])
    tilesByOwner.get(t.owner).push(t)
  }

  const colorForOwner = (owner) => {
    if (owner === 'player') return PLAYER_COLOR
    const idx = mapStore.rivalCapitals.findIndex((rc) => rc.rival_id === owner)
    return RIVAL_COLORS[(idx >= 0 ? idx : 0) % RIVAL_COLORS.length]
  }

  for (const [owner, tiles] of tilesByOwner) {
    if (owner === 'player') continue
    drawOwnedTerritory(ctx, tiles, offsetX, offsetY, tileSize, colorForOwner(owner))
  }
  drawOwnedTerritory(ctx, tilesByOwner.get('player') || [], offsetX, offsetY, tileSize, PLAYER_COLOR)

  if (mapStore.capital) {
    const cx = offsetX + mapStore.capital.x * tileSize + tileSize / 2
    const cy = offsetY + mapStore.capital.y * tileSize + tileSize / 2
    const tier = tierFromTileCount((tilesByOwner.get('player') || []).length)
    drawCity(ctx, cx, cy, tileSize, tier, PLAYER_COLOR, nationStore.nation.name || '수도', true, 0, nationStore.nation.era)
  }
  for (const c of cityStore.cities) {
    const cx = offsetX + c.x * tileSize + tileSize / 2
    const cy = offsetY + c.y * tileSize + tileSize / 2
    const isPlayerCity = c.owner === 'player'
    drawCity(ctx, cx, cy, tileSize, 0, colorForOwner(c.owner), c.name, isPlayerCity, 0, isPlayerCity ? nationStore.nation.era : null)
  }
  mapStore.rivalCapitals.forEach((rc, i) => {
    const cx = offsetX + rc.x * tileSize + tileSize / 2
    const cy = offsetY + rc.y * tileSize + tileSize / 2
    const rival = diplomacyStore.rivals.find((r) => r.rival_id === rc.rival_id)
    if (rival?.relationship === 'defeated') {
      drawRuins(ctx, cx, cy, tileSize, rc.name)
      return
    }
    const tier = tierFromTileCount((tilesByOwner.get(rc.rival_id) || []).length)
    const color = RIVAL_COLORS[i % RIVAL_COLORS.length]
    drawCity(ctx, cx, cy, tileSize, tier, color, rc.name, false, i + 1)
    if (rival?.relationship === 'war') {
      ctx.font = `${tileSize * 0.7}px sans-serif`
      ctx.textAlign = 'center'
      ctx.fillText('⚔', cx, cy - tileSize * 1.7)
    }
  })

  // highlight the tile currently under a purchase/founding prompt
  const highlighted = purchasePrompt.value || foundCityPrompt.value || attackPrompt.value || buildingPrompt.value
  if (highlighted) {
    const { x, y } = highlighted
    ctx.strokeStyle = '#ffd166'
    ctx.lineWidth = 3
    ctx.strokeRect(offsetX + x * tileSize + 1.5, offsetY + y * tileSize + 1.5, tileSize - 3, tileSize - 3)
  }
}

function tileFromEvent(e) {
  const rect = canvasRef.value.getBoundingClientRect()
  const mouseX = e.clientX - rect.left
  const mouseY = e.clientY - rect.top
  const tx = Math.floor((mouseX - layout.offsetX) / layout.tileSize)
  const ty = Math.floor((mouseY - layout.offsetY) / layout.tileSize)
  return { tx, ty }
}

function rivalNameFor(ownerId) {
  const rc = mapStore.rivalCapitals.find((r) => r.rival_id === ownerId)
  return rc ? rc.name : ownerId
}

function distanceOk(x1, y1, x2, y2, min) {
  return Math.max(Math.abs(x1 - x2), Math.abs(y1 - y2)) >= min
}

function handleClick(e) {
  const { tx, ty } = tileFromEvent(e)
  buildingPrompt.value = null
  if (tx < 0 || tx >= mapStore.width || ty < 0 || ty >= mapStore.height) {
    purchasePrompt.value = null
    foundCityPrompt.value = null
    attackPrompt.value = null
    return
  }
  const owner = territoryStore.ownerAt(tx, ty)

  if (owner && owner !== 'player') {
    const rivalCapital = mapStore.rivalCapitals.find((rc) => rc.x === tx && rc.y === ty)
    const rivalCity = cityStore.cities.find((c) => c.x === tx && c.y === ty && c.owner === owner)
    const settlement = rivalCapital || rivalCity
    if (settlement) {
      purchasePrompt.value = null
      foundCityPrompt.value = null
      attackPrompt.value = {
        x: tx,
        y: ty,
        screenX: layout.offsetX + tx * layout.tileSize + layout.tileSize / 2,
        screenY: layout.offsetY + ty * layout.tileSize,
        cityName: settlement.name,
        rivalId: owner,
        rivalName: rivalNameFor(owner),
        attacking: false,
        attackError: '',
      }
      draw()
      return
    }
  }
  attackPrompt.value = null

  if (owner === 'player') {
    purchasePrompt.value = null
    const isCapital = mapStore.capital && tx === mapStore.capital.x && ty === mapStore.capital.y
    const existingCity = cityStore.cities.some((c) => c.x === tx && c.y === ty)
    if (isCapital || existingCity) {
      foundCityPrompt.value = null
      return
    }

    const tooCloseToCapital =
      mapStore.capital && !distanceOk(tx, ty, mapStore.capital.x, mapStore.capital.y, MIN_CITY_DISTANCE)
    const tooCloseToCity = cityStore.cities.some((c) => !distanceOk(tx, ty, c.x, c.y, MIN_CITY_DISTANCE))
    foundCityPrompt.value = {
      x: tx,
      y: ty,
      screenX: layout.offsetX + tx * layout.tileSize + layout.tileSize / 2,
      screenY: layout.offsetY + ty * layout.tileSize,
      cost: cityStore.estimatedCost(),
      error: tooCloseToCapital || tooCloseToCity ? '수도/다른 도시와 너무 가깝습니다' : null,
      nearbyResources: mapStore.resourcesNear(tx, ty).map((r) => RESOURCE_META[r.type]).filter(Boolean),
      name: '',
      founding: false,
      foundError: '',
    }
    draw()
    return
  }
  foundCityPrompt.value = null

  const terrain = mapStore.tiles[ty][tx]
  const adjacent = territoryStore.isAdjacentToOwned(tx, ty)
  const screenX = layout.offsetX + tx * layout.tileSize + layout.tileSize / 2
  const screenY = layout.offsetY + ty * layout.tileSize
  purchasePrompt.value = {
    x: tx,
    y: ty,
    terrain,
    adjacent,
    cost: territoryStore.estimatedCost(),
    screenX,
    screenY,
    error: owner
      ? `이미 ${rivalNameFor(owner)}이(가) 소유한 영토입니다`
      : terrain === 'water'
        ? '물 위에는 영토를 확장할 수 없습니다'
        : !adjacent
          ? '기존 영토와 인접한 칸만 구매할 수 있습니다'
          : null,
    purchasing: false,
    purchaseError: '',
  }
  draw()
}

function handleRightClick(e) {
  const { tx, ty } = tileFromEvent(e)
  purchasePrompt.value = null
  foundCityPrompt.value = null
  attackPrompt.value = null
  if (tx < 0 || tx >= mapStore.width || ty < 0 || ty >= mapStore.height) {
    buildingPrompt.value = null
    return
  }
  // Buildings are a nation-wide queue, not tied to a specific tile (see
  // building_service.py) — right-clicking any owned tile just opens the same list;
  // where exactly you clicked only decides where the popup appears.
  if (territoryStore.ownerAt(tx, ty) !== 'player') {
    buildingPrompt.value = null
    return
  }
  buildingPrompt.value = {
    screenX: layout.offsetX + tx * layout.tileSize + layout.tileSize / 2,
    screenY: layout.offsetY + ty * layout.tileSize,
    error: '',
  }
  draw()
}

function requiredTechName(techId) {
  return techStore.tree.find((t) => t.id === techId)?.name || techId
}

function buildingStatus(building) {
  if (buildingStore.built.includes(building.id)) return 'done'
  if (buildingStore.currentBuilding === building.id) return 'active'
  if (!buildingStore.researched.includes(building.requires_tech)) return 'locked'
  return 'available'
}

async function buildFromMap(buildingId) {
  const p = buildingPrompt.value
  if (!p) return
  p.error = ''
  await buildingStore.build(buildingId)
  if (buildingStore.error) {
    p.error = buildingStore.error
  } else {
    buildingPrompt.value = null
  }
}

function cancelBuilding() {
  buildingPrompt.value = null
  draw()
}

async function confirmPurchase() {
  const p = purchasePrompt.value
  if (!p || p.error) return
  p.purchasing = true
  try {
    await territoryStore.purchase(p.x, p.y)
    purchasePrompt.value = null
    draw()
  } catch (err) {
    p.purchaseError = err.message
  } finally {
    if (purchasePrompt.value) purchasePrompt.value.purchasing = false
  }
}

function cancelPurchase() {
  purchasePrompt.value = null
  draw()
}

async function confirmFoundCity() {
  const p = foundCityPrompt.value
  if (!p || p.error) return
  const trimmed = p.name.trim()
  if (!trimmed) {
    p.foundError = '도시 이름을 입력해주세요'
    return
  }
  p.founding = true
  try {
    await cityStore.found(p.x, p.y, trimmed)
    foundCityPrompt.value = null
    draw()
  } catch (err) {
    p.foundError = err.message
  } finally {
    if (foundCityPrompt.value) foundCityPrompt.value.founding = false
  }
}

function cancelFoundCity() {
  foundCityPrompt.value = null
  draw()
}

async function confirmAttack() {
  const p = attackPrompt.value
  if (!p) return
  p.attacking = true
  try {
    await diplomacyStore.attackCity(p.x, p.y)
    attackPrompt.value = null
    draw()
  } catch (err) {
    p.attackError = err.message
  } finally {
    if (attackPrompt.value) attackPrompt.value.attacking = false
  }
}

function cancelAttack() {
  attackPrompt.value = null
  draw()
}

function handleResize() {
  draw()
}

onMounted(async () => {
  await mapStore.fetchMap()
  await diplomacyStore.fetchRivals()
  await territoryStore.fetchTerritory()
  await cityStore.fetchCities()
  await buildingStore.fetchState()
  await techStore.fetchTree()
  draw()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

watch(() => nationStore.nation.population, draw)
watch(() => diplomacyStore.rivals, draw, { deep: true })
watch(() => territoryStore.allTiles, draw, { deep: true })
watch(() => cityStore.cities, draw, { deep: true })
</script>

<template>
  <canvas
    ref="canvasRef"
    class="map-canvas"
    @click="handleClick"
    @contextmenu.prevent="handleRightClick"
  ></canvas>

  <div
    v-if="purchasePrompt"
    class="purchase-popup"
    :style="{ left: purchasePrompt.screenX + 'px', top: purchasePrompt.screenY + 'px' }"
  >
    <template v-if="purchasePrompt.error">
      <div class="popup-error">{{ purchasePrompt.error }}</div>
      <button class="popup-btn cancel" @click="cancelPurchase">닫기</button>
    </template>
    <template v-else>
      <div class="popup-title">영토 확장</div>
      <div class="popup-cost">💰 {{ purchasePrompt.cost }}</div>
      <div v-if="purchasePrompt.purchaseError" class="popup-error">
        {{ purchasePrompt.purchaseError }}
      </div>
      <div class="popup-actions">
        <button class="popup-btn buy" :disabled="purchasePrompt.purchasing" @click="confirmPurchase">
          구매
        </button>
        <button class="popup-btn cancel" @click="cancelPurchase">취소</button>
      </div>
    </template>
  </div>

  <div
    v-if="foundCityPrompt"
    class="purchase-popup"
    :style="{ left: foundCityPrompt.screenX + 'px', top: foundCityPrompt.screenY + 'px' }"
  >
    <template v-if="foundCityPrompt.error">
      <div class="popup-error">{{ foundCityPrompt.error }}</div>
      <button class="popup-btn cancel" @click="cancelFoundCity">닫기</button>
    </template>
    <template v-else>
      <div class="popup-title">도시 건설</div>
      <input
        v-model="foundCityPrompt.name"
        class="popup-input"
        maxlength="20"
        placeholder="도시 이름"
        @keyup.enter="confirmFoundCity"
      />
      <div class="popup-cost">💰 {{ foundCityPrompt.cost }}</div>
      <div v-if="foundCityPrompt.nearbyResources.length" class="popup-resources">
        인근 자원:
        <span v-for="(r, i) in foundCityPrompt.nearbyResources" :key="i">{{ r.icon }} {{ r.name }}</span>
      </div>
      <div v-else class="popup-resources muted">인근에 자원이 없습니다</div>
      <div v-if="foundCityPrompt.foundError" class="popup-error">
        {{ foundCityPrompt.foundError }}
      </div>
      <div class="popup-actions">
        <button class="popup-btn buy" :disabled="foundCityPrompt.founding" @click="confirmFoundCity">
          건설
        </button>
        <button class="popup-btn cancel" @click="cancelFoundCity">취소</button>
      </div>
    </template>
  </div>

  <div
    v-if="attackPrompt"
    class="purchase-popup"
    :style="{ left: attackPrompt.screenX + 'px', top: attackPrompt.screenY + 'px' }"
  >
    <div class="popup-title">도시 공격</div>
    <div class="popup-attack-target">{{ attackPrompt.rivalName }}의 '{{ attackPrompt.cityName }}'</div>
    <div v-if="attackPrompt.attackError" class="popup-error">{{ attackPrompt.attackError }}</div>
    <div class="popup-actions">
      <button class="popup-btn attack" :disabled="attackPrompt.attacking" @click="confirmAttack">공격</button>
      <button class="popup-btn cancel" @click="cancelAttack">취소</button>
    </div>
  </div>

  <div
    v-if="buildingPrompt"
    class="purchase-popup building-popup"
    :style="{ left: buildingPrompt.screenX + 'px', top: buildingPrompt.screenY + 'px' }"
  >
    <div class="popup-title">건물 건설</div>
    <div v-if="buildingPrompt.error" class="popup-error">{{ buildingPrompt.error }}</div>
    <div class="building-list">
      <div
        v-for="building in buildingStore.buildings"
        :key="building.id"
        class="building-row"
        :class="buildingStatus(building)"
      >
        <div class="building-row-name">
          {{ building.name }}
          <span v-if="buildingStatus(building) === 'done'" class="badge done-badge">완료</span>
          <span v-else-if="buildingStatus(building) === 'active'" class="badge active-badge">
            건설 중 · {{ buildingStore.currentBuildingMonthsLeft }}개월
          </span>
        </div>
        <div v-if="buildingStatus(building) === 'locked'" class="building-row-req">
          선행 기술: {{ requiredTechName(building.requires_tech) }}
        </div>
        <div v-else class="building-row-cost">{{ building.cost }} · {{ building.duration_months }}개월</div>
        <button
          v-if="buildingStatus(building) === 'available'"
          :disabled="!!buildingStore.currentBuilding || nationStore.nation.treasury < building.cost"
          @click="buildFromMap(building.id)"
        >
          건설
        </button>
      </div>
    </div>
    <button class="popup-btn cancel" @click="cancelBuilding">닫기</button>
  </div>
</template>

<style scoped>
.map-canvas {
  position: fixed;
  inset: 0;
  cursor: pointer;
}
.purchase-popup {
  position: fixed;
  transform: translate(-50%, -110%);
  background: var(--panel-bg);
  border: 1px solid var(--accent);
  border-radius: var(--panel-radius);
  padding: 10px 12px;
  color: var(--text);
  font-family: var(--font-body);
  font-size: 13px;
  box-shadow: var(--panel-shadow);
  z-index: 25;
  min-width: 140px;
  text-align: center;
}
.popup-title {
  font-family: var(--font-heading);
  font-weight: bold;
  margin-bottom: 4px;
  color: var(--accent-strong);
}
.popup-cost {
  color: var(--accent-strong);
  font-weight: bold;
  margin-bottom: 8px;
}
.popup-error {
  color: var(--text-negative);
  font-size: 12px;
  margin-bottom: 8px;
}
.popup-resources {
  font-size: 12px;
  margin-bottom: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  align-items: center;
}
.popup-resources.muted {
  color: var(--text-muted, #999);
}
.popup-input {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  border-radius: 5px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  font-size: 12px;
  margin-bottom: 8px;
  text-align: center;
  font-family: var(--font-body);
}
.popup-actions {
  display: flex;
  gap: 6px;
}
.popup-btn {
  flex: 1;
  padding: 6px 8px;
  border-radius: 5px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 12px;
  font-family: var(--font-body);
}
.popup-btn.buy {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--accent-strong);
}
.popup-btn.attack {
  background: rgba(226, 104, 90, 0.18);
  border-color: var(--text-negative);
  color: var(--text-negative);
}
.popup-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.popup-attack-target {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 8px;
  text-align: center;
}
.building-popup {
  width: 240px;
}
.building-list {
  max-height: 320px;
  overflow-y: auto;
  margin-bottom: 8px;
}
.building-row {
  background: rgba(0, 0, 0, 0.22);
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  padding: 7px 8px;
  margin-bottom: 6px;
  text-align: left;
}
.building-row.done {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.building-row.locked {
  opacity: 0.5;
}
.building-row.active {
  border-color: var(--accent-strong);
  background: rgba(255, 209, 102, 0.12);
}
.building-row-name {
  font-weight: bold;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.building-row-req,
.building-row-cost {
  font-size: 11px;
  color: var(--text-faint);
  margin-top: 3px;
}
.building-row button {
  width: 100%;
  margin-top: 6px;
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 11px;
  font-family: var(--font-body);
}
.building-row button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.building-row button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.badge.done-badge {
  font-size: 10px;
  background: var(--accent);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
}
.badge.active-badge {
  font-size: 10px;
  background: var(--accent-strong);
  color: #241d12;
  padding: 1px 6px;
  border-radius: 4px;
  font-weight: normal;
  white-space: nowrap;
}
</style>
