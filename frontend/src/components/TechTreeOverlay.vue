<script setup>
import { computed } from 'vue'
import { useTechStore } from '../stores/tech'
import { useNationStore } from '../stores/nation'

const emit = defineEmits(['close'])

const techStore = useTechStore()
const nationStore = useNationStore()

const NODE_WIDTH = 176
const NODE_HEIGHT = 118
const COL_GAP = 70
const ROW_GAP = 26
const PADDING = 40

// Layered graph layout: column = longest-path depth from a root tech (no prereqs),
// row = barycenter of each node's prereqs' rows, sorted per column — a standard
// Sugiyama-style layering that keeps prereq -> dependent edges flowing left to right
// with minimal crossing, without hardcoding positions per tech (so this keeps working
// automatically if the tree grows again later).
const layout = computed(() => {
  const tree = techStore.tree
  if (!tree.length) return { nodes: [], edges: [], width: 0, height: 0 }

  const byId = Object.fromEntries(tree.map((t) => [t.id, t]))
  const depthCache = {}
  function depthOf(id) {
    if (id in depthCache) return depthCache[id]
    depthCache[id] = 0 // guard against a malformed cycle during computation
    const t = byId[id]
    const d = t.prereqs.length ? 1 + Math.max(...t.prereqs.map(depthOf)) : 0
    depthCache[id] = d
    return d
  }

  const columns = []
  for (const t of tree) {
    const d = depthOf(t.id)
    ;(columns[d] ??= []).push(t.id)
  }

  const rowOf = {}
  columns[0].forEach((id, i) => (rowOf[id] = i))
  for (let c = 1; c < columns.length; c++) {
    const ids = columns[c] || []
    const scored = ids.map((id) => {
      const prereqs = byId[id].prereqs
      const avg = prereqs.length ? prereqs.reduce((s, p) => s + rowOf[p], 0) / prereqs.length : 0
      return { id, avg }
    })
    scored.sort((a, b) => a.avg - b.avg)
    scored.forEach((s, i) => (rowOf[s.id] = i))
  }

  const maxRows = Math.max(...columns.map((c) => c.length))
  const positions = {}
  columns.forEach((ids, c) => {
    const colOffset = ((maxRows - ids.length) * (NODE_HEIGHT + ROW_GAP)) / 2
    ids.forEach((id) => {
      positions[id] = {
        x: PADDING + c * (NODE_WIDTH + COL_GAP),
        y: PADDING + colOffset + rowOf[id] * (NODE_HEIGHT + ROW_GAP),
      }
    })
  })

  const nodes = tree.map((t) => ({ tech: t, ...positions[t.id] }))
  const edges = []
  for (const t of tree) {
    for (const p of t.prereqs) {
      edges.push({ from: positions[p], to: positions[t.id], done: techStore.researched.includes(p) })
    }
  }

  const width = PADDING * 2 + columns.length * NODE_WIDTH + (columns.length - 1) * COL_GAP
  const height = PADDING * 2 + maxRows * NODE_HEIGHT + (maxRows - 1) * ROW_GAP
  return { nodes, edges, width, height }
})

function isResearched(id) {
  return techStore.researched.includes(id)
}
function isAvailable(tech) {
  return tech.prereqs.every((p) => techStore.researched.includes(p))
}
function isInProgress(id) {
  return techStore.currentResearch === id
}
function canAfford(tech) {
  return nationStore.nation.treasury >= tech.cost
}

function edgePath(edge) {
  const x1 = edge.from.x + NODE_WIDTH
  const y1 = edge.from.y + NODE_HEIGHT / 2
  const x2 = edge.to.x
  const y2 = edge.to.y + NODE_HEIGHT / 2
  const midX = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`
}
</script>

<template>
  <Teleport to="body">
    <div class="overlay" @click.self="emit('close')">
      <div class="frame panel">
        <div class="header">
          <div class="title">테크트리</div>
          <button class="close-btn" @click="emit('close')">✕</button>
        </div>
        <div class="scroll-area">
          <div class="canvas" :style="{ width: layout.width + 'px', height: layout.height + 'px' }">
            <svg class="edges" :width="layout.width" :height="layout.height">
              <path
                v-for="(edge, i) in layout.edges"
                :key="i"
                :d="edgePath(edge)"
                :class="{ done: edge.done }"
                fill="none"
              />
            </svg>
            <div
              v-for="n in layout.nodes"
              :key="n.tech.id"
              class="node"
              :class="{
                done: isResearched(n.tech.id),
                locked: !isResearched(n.tech.id) && !isAvailable(n.tech),
                active: isInProgress(n.tech.id),
              }"
              :style="{ left: n.x + 'px', top: n.y + 'px', width: NODE_WIDTH + 'px', height: NODE_HEIGHT + 'px' }"
            >
              <div class="node-name">
                {{ n.tech.name }}
                <span v-if="isResearched(n.tech.id)" class="badge done-badge">완료</span>
                <span v-else-if="isInProgress(n.tech.id)" class="badge active-badge">
                  {{ techStore.currentResearchMonthsLeft }}개월
                </span>
              </div>
              <div class="node-desc">{{ n.tech.description }}</div>
              <div class="node-footer">
                <span class="node-cost">{{ n.tech.cost }} · {{ n.tech.duration_months }}개월</span>
                <button
                  v-if="!isResearched(n.tech.id) && !isInProgress(n.tech.id)"
                  :disabled="!isAvailable(n.tech) || !canAfford(n.tech) || !!techStore.currentResearch"
                  @click="techStore.research(n.tech.id)"
                >
                  연구
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 8, 4, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 60;
  padding: 24px;
}
.frame {
  width: 100%;
  height: 100%;
  max-width: 1400px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--panel-border-soft);
  flex-shrink: 0;
}
.title {
  font-family: var(--font-heading);
  font-size: 18px;
  font-weight: bold;
  color: var(--accent-strong);
}
.close-btn {
  background: none;
  border: 1px solid var(--panel-border-soft);
  border-radius: 6px;
  color: var(--text);
  width: 30px;
  height: 30px;
  cursor: pointer;
  font-size: 14px;
}
.close-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.scroll-area {
  flex: 1;
  overflow: auto;
  padding: 20px;
}
.canvas {
  position: relative;
}
.edges {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
}
.edges path {
  stroke: var(--panel-border-soft);
  stroke-width: 2;
}
.edges path.done {
  stroke: var(--accent);
}
.node {
  position: absolute;
  box-sizing: border-box;
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid var(--panel-border-soft);
  border-radius: 8px;
  padding: 9px 10px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.node.done {
  border-color: var(--accent);
  background: var(--accent-dim);
}
.node.locked {
  opacity: 0.45;
}
.node.active {
  border-color: var(--accent-strong);
  background: rgba(255, 209, 102, 0.14);
}
.node-name {
  font-weight: bold;
  font-size: 13px;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
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
.node-desc {
  font-size: 10.5px;
  color: var(--text-dim);
  line-height: 1.35;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}
.node-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.node-cost {
  font-size: 11px;
  color: var(--accent-strong);
  white-space: nowrap;
}
.node button {
  padding: 3px 9px;
  border-radius: 4px;
  border: 1px solid var(--panel-border-soft);
  background: rgba(0, 0, 0, 0.3);
  color: var(--text);
  cursor: pointer;
  font-size: 11px;
  font-family: var(--font-body);
}
.node button:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.node button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
