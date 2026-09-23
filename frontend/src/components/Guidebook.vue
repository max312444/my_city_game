<script setup>
import { ref } from 'vue'

const open = ref(false)
const activeId = ref('overview')

defineExpose({ open })

const SECTIONS = [
  {
    id: 'overview',
    icon: '👑',
    title: '조언자의 역할',
    paragraphs: [
      '그대는 왕이 아니라 왕의 곁을 지키는 조언자다. 국가는 AI가 알아서 통치한다 — 경제·정책·외교·전쟁 대부분이 스스로 굴러간다.',
      '플레이어가 할 수 있는 건 방향을 살짝 트는 정도다: 가끔 뜨는 조언 카드를 고르거나, 연구·건설·외교 같은 몇 가지 선택을 직접 누르는 것.',
      '원래 승패 조건은 없다 — 유일한 예외는 지도의 라이벌 국가를 전부 없애는 "천하 통일" 뿐. 그 외에는 그냥 지켜보는 게임이다.',
    ],
  },
  {
    id: 'hud',
    icon: '📜',
    title: '시간과 화면',
    paragraphs: [
      '화면 위쪽 가운데 국가 이름을 누르면 인구·식량·재화·경제력 같은 핵심 지표가 펼쳐진다. 이름 옆에는 지금 시대(원시~르네상스)와 국가 특성 배지가 항상 보인다.',
      '우측 상단 시계 패널에서 배속(일시정지/1x/2x/4x)을 조절한다 — 일시정지하면 조언 제한시간도 같이 멈춘다.',
      '"☰ 메뉴"에서 국가 통계, 위인 명예의 전당, 게임 로그(연대기), 설정(메인 화면으로/저장/다시하기)을 볼 수 있다.',
    ],
  },
  {
    id: 'map',
    icon: '🗺️',
    title: '지도 조작',
    bullets: [
      '내 땅(파란 영역)을 좌클릭 — 수도나 기존 도시가 아니면 그 자리에 새 도시를 세울 수 있다.',
      '내 땅을 우클릭 — 지금 지을 수 있는 건물 목록이 뜬다.',
      '아무도 소유하지 않은 땅을 클릭 — 돈을 내고 영토를 구매한다(인접한 칸만 가능, 많이 가질수록 다음 칸이 비싸짐).',
      '적국의 수도나 도시를 클릭 — "공격" 버튼으로 그 나라에 선전포고하고, 그 도시를 공격 목표로 지정한다.',
      '땅은 시간이 지나면 조금씩 저절로도 늘어난다(경제력에 비례) — 수동 구매는 그 위에 얹는 것뿐이다.',
    ],
  },
  {
    id: 'advice',
    icon: '💬',
    title: '조언 카드',
    paragraphs: [
      '몇 달에 한 번씩 화면 하단에 조언 카드가 뜬다. 세 가지 선택지 중 하나를 15초 안에 고르면 국가 지표에 작은 변화가 생긴다.',
      '고르지 않고 시간이 다 되면 그냥 넘어간다 — 페널티는 없다. 플레이어는 조언자일 뿐이라 효과는 항상 크지 않게 유지된다.',
    ],
  },
  {
    id: 'tech',
    icon: '📚',
    title: '테크트리',
    paragraphs: [
      '좌측 가장자리의 "▶ 테크 · 건물 · 유산 · 외교 · 교역" 탭을 누르면 서랍이 열린다. 테크트리 패널에서 한 번에 하나씩 연구를 진행한다.',
      '패널 위쪽 "🗺 전체 트리" 버튼을 누르면 전체화면 그래프로 선행조건 관계를 한눈에 볼 수 있다.',
    ],
  },
  {
    id: 'buildings',
    icon: '🏗️',
    title: '건물',
    paragraphs: [
      '건물은 도시별이 아니라 국가 전체에 적용되는 단일 슬롯이다 — 해당 테크를 먼저 연구해야 지을 수 있다(예: 기마술 연구 → 목장 건설 가능).',
      '연구와 건설은 서로 다른 슬롯이라 동시에 진행할 수 있다. 완성되면 관련 지표에 영구 보너스를 준다.',
    ],
  },
  {
    id: 'wonders',
    icon: '🗿',
    title: '문화유산(세계 불가사의)',
    paragraphs: [
      '스톤헨지, 피라미드 같은 문화유산은 세션 안에서 딱 한 나라만 완성할 수 있다 — 플레이어든 라이벌이든 먼저 끝내는 쪽이 가져간다.',
      '관련 테크를 먼저 연구해두면 더 빨리 지을 수 있고, 안 해도 느리게는 시도할 수 있다.',
      '건설 중에 다른 나라가 먼저 완성해버리면 투자한 국고와 시간은 환불 없이 그대로 날아간다 — 진짜 "경쟁"이다.',
    ],
  },
  {
    id: 'diplomacy',
    icon: '⚔️',
    title: '외교와 전쟁',
    paragraphs: [
      '각 라이벌 국가는 고정된 성향(호전적/경제 중심/고립주의)과 무작위 국가 특성(군사·경제·생산·학문 특화)을 갖고 있다.',
      '전쟁은 플레이어가 시작할 수도 있고, 라이벌이 먼저 선전포고할 수도 있다. 전쟁이 길어지면 라이벌이 평화 협정을 제안하기도 하는데, 화면 우측 하단 팝업에서 직접 수락하거나 거절해야 한다 — 저절로 끝나지 않는다.',
      '전투에서 이기면 상대의 국경 지역(도시 포함, 수도는 절대 불가)을 점령한다. 접경하지 않은 먼 나라는 땅을 뺏을 수 없다.',
    ],
  },
  {
    id: 'trade',
    icon: '🚢',
    title: '교역',
    paragraphs: [
      '평화 상태인 라이벌과 교역로를 열면 매달 자동으로 수입이 들어온다(경제력·인근 자원에 따라 금액이 달라짐). 전쟁이 나면 수입만 멈추고, 평화가 돌아오면 다시 자동으로 이어진다.',
      '식량이 넉넉하면 일부를 팔아 국고로 바꿀 수도 있다(최소 비축량은 항상 남겨둠).',
    ],
  },
  {
    id: 'resources',
    icon: '🌾',
    title: '자원과 영토',
    paragraphs: [
      '지도 곳곳에 금광·철광·비옥한 토양·목재·향신료·말·어장 같은 자원이 놓여 있다. 수도나 도시가 자원 바로 옆에 있으면 매달 관련 지표에 추가 보너스가 붙는다.',
      '그래서 도시를 어디에 세우느냐가 실제로 중요하다 — 도시 건설 팝업에 인근 자원이 미리 표시된다.',
    ],
  },
  {
    id: 'events',
    icon: '⚡',
    title: '위인과 이벤트',
    paragraphs: [
      '위인(경제·군사·학문·정치 분야)이 가끔 저절로 등장해 지표를 올려준다 — 같은 위인은 세이브당 한 번만 나온다.',
      '가뭄, 풍작, 유물 발견 같은 큰 사건도 가끔 무작위로 일어난다. 전부 게임 로그(☰ 메뉴 → 게임 로그)에 기록된다.',
    ],
  },
  {
    id: 'victory',
    icon: '🏆',
    title: '천하 통일',
    paragraphs: [
      '지도의 라이벌 국가 3곳이 전부 멸망하면 게임이 끝난다 — 시계가 자동으로 멈추고 승리 화면이 뜬다.',
      '승리 화면에서도 "계속 관찰하기"를 누르면 그 이후 세계도 계속 지켜볼 수 있다.',
    ],
  },
]
</script>

<template>
  <button class="guide-btn panel" @click="open = true">❓ 가이드북</button>

  <Teleport to="body">
    <div v-if="open" class="overlay" @click.self="open = false">
      <div class="frame panel">
        <div class="header">
          <div class="title">📖 가이드북</div>
          <button class="close-btn" @click="open = false">✕</button>
        </div>
        <div class="body">
          <div class="sidebar">
            <button
              v-for="s in SECTIONS"
              :key="s.id"
              class="nav-item"
              :class="{ active: activeId === s.id }"
              @click="activeId = s.id"
            >
              {{ s.icon }} {{ s.title }}
            </button>
          </div>
          <div class="content">
            <template v-for="s in SECTIONS" :key="s.id">
              <div v-if="activeId === s.id">
                <div class="content-title">{{ s.icon }} {{ s.title }}</div>
                <p v-for="(p, i) in s.paragraphs" :key="i" class="paragraph">{{ p }}</p>
                <ul v-if="s.bullets" class="bullets">
                  <li v-for="(b, i) in s.bullets" :key="i">{{ b }}</li>
                </ul>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.guide-btn {
  width: 100%;
  padding: 10px;
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-body);
  color: var(--text);
}
.guide-btn:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
}
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 8, 4, 0.82);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 70;
  padding: 24px;
}
.frame {
  width: 100%;
  height: 100%;
  max-width: 900px;
  max-height: 640px;
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
.body {
  flex: 1;
  display: flex;
  overflow: hidden;
}
.sidebar {
  width: 200px;
  flex-shrink: 0;
  border-right: 1px solid var(--panel-border-soft);
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  text-align: left;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid transparent;
  background: none;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
  font-family: var(--font-body);
  white-space: nowrap;
}
.nav-item:hover {
  color: var(--text);
}
.nav-item.active {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--accent-strong);
  font-weight: bold;
}
.content {
  flex: 1;
  overflow-y: auto;
  padding: 20px 26px;
}
.content-title {
  font-family: var(--font-heading);
  font-size: 17px;
  font-weight: bold;
  color: var(--accent-strong);
  margin-bottom: 14px;
}
.paragraph {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
  margin: 0 0 12px;
}
.bullets {
  margin: 0;
  padding-left: 20px;
}
.bullets li {
  font-size: 13.5px;
  line-height: 1.7;
  color: var(--text);
  margin-bottom: 8px;
}
</style>
