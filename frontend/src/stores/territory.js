import { defineStore } from 'pinia'
import { useSessionStore } from './session'
import { useNationStore } from './nation'

const API_BASE = 'http://localhost:8000'
// Mirrors territory_service.compute_cost on the backend — used only for the
// pre-purchase popup preview, the real charge always comes from the server.
const TILE_BASE_COST = 100
const TILE_COST_LINEAR = 20
const TILE_COST_QUADRATIC = 1.0

function playerTilesFrom(allTiles) {
  return allTiles.filter((t) => t.owner === 'player').map((t) => ({ x: t.x, y: t.y }))
}

export const useTerritoryStore = defineStore('territory', {
  state: () => ({
    tiles: [], // the player's own tiles only — used for adjacency/cost checks
    allTiles: [], // every owner's tiles ({x, y, owner}) — used for rendering everyone
  }),
  actions: {
    async fetchTerritory() {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/territory`)
      const data = await res.json()
      this.tiles = data.tiles
      this.allTiles = data.all
    },
    updateAll(allTiles) {
      this.allTiles = allTiles
      this.tiles = playerTilesFrom(allTiles)
    },
    isOwned(x, y) {
      return this.tiles.some((t) => t.x === x && t.y === y)
    },
    ownerAt(x, y) {
      const tile = this.allTiles.find((t) => t.x === x && t.y === y)
      return tile ? tile.owner : null
    },
    isAdjacentToOwned(x, y) {
      return this.tiles.some((t) => Math.abs(t.x - x) <= 1 && Math.abs(t.y - y) <= 1)
    },
    estimatedCost() {
      const n = this.tiles.length
      return TILE_BASE_COST + TILE_COST_LINEAR * n + TILE_COST_QUADRATIC * n * n
    },
    async purchase(x, y) {
      const sessionId = useSessionStore().sessionId
      const res = await fetch(`${API_BASE}/api/session/${sessionId}/territory/purchase`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ x, y }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '구매에 실패했습니다')
      this.tiles = data.tiles
      this.allTiles = data.all
      useNationStore().applyUpdate(data.nation)
      return data
    },
  },
})
