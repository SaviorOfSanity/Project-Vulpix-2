// Project Vulpix 2.0 - Client Controller & Chart Engine
// Connects to Python REST backend on localhost:8080

let currentTab = 'gauntlet';
let archetypesData = {};

// Chart.js Instances
let gauntletBarChart = null;
let gauntletRadarChart = null;
let gauntletPrizeChart = null;
let builderDonutChart = null;
let antiMetaChart = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
  initLucideIcons();
  await loadArchetypes();
  initSampleCharts();
  switchTab('gauntlet');
});

function initLucideIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function switchTab(tabId) {
  currentTab = tabId;
  const tabs = ['gauntlet', 'builder', 'antimeta', 'gameplan', 'coach'];
  
  tabs.forEach(t => {
    const viewEl = document.getElementById(`view-${t}`);
    const navBtn = document.getElementById(`nav-btn-${t}`);
    
    if (t === tabId) {
      viewEl.classList.remove('hidden');
      navBtn.classList.remove('text-slate-400', 'bg-transparent');
      navBtn.classList.add('text-white', 'bg-indigo-600', 'shadow-lg');
    } else {
      viewEl.classList.add('hidden');
      navBtn.classList.remove('text-white', 'bg-indigo-600', 'shadow-lg');
      navBtn.classList.add('text-slate-400', 'bg-transparent');
    }
  });

  initLucideIcons();
}

async function loadArchetypes() {
  try {
    const res = await fetch('/api/archetypes');
    const data = await res.json();
    if (data.status === 'success') {
      archetypesData = data.archetypes;
      populateArchetypeDropdowns();
    }
  } catch (err) {
    console.error("Failed to load archetypes from backend:", err);
  }
}

function populateArchetypeDropdowns() {
  const names = Object.keys(archetypesData);
  const gauntletSelect = document.getElementById('gauntlet-preset-select');
  const planOppSelect = document.getElementById('plan-opp-select');
  const planMySelect = document.getElementById('plan-my-select');

  if (gauntletSelect) {
    gauntletSelect.innerHTML = '<option value="">-- Or Select Standard Meta Preset --</option>';
    names.forEach(name => {
      gauntletSelect.innerHTML += `<option value="${name}">${name}</option>`;
    });
  }

  if (planOppSelect) {
    planOppSelect.innerHTML = '';
    names.forEach(name => {
      planOppSelect.innerHTML += `<option value="${name}">${name}</option>`;
    });
  }

  const builderTargetSelect = document.getElementById('builder-target-select');
  if (builderTargetSelect) {
    builderTargetSelect.innerHTML = '';
    names.forEach(name => {
      builderTargetSelect.innerHTML += `<option value="${name}">${name}</option>`;
    });
  }

  if (planMySelect) {
    planMySelect.innerHTML = '<option value="">-- Use Pasted Deck Above --</option>';
    names.forEach(name => {
      planMySelect.innerHTML += `<option value="${name}">${name}</option>`;
    });
  }
}

function loadPresetIntoGauntlet() {
  const select = document.getElementById('gauntlet-preset-select');
  const name = select.value;
  if (name && archetypesData[name]) {
    document.getElementById('gauntlet-deck-input').value = archetypesData[name].ptcgl_text;
    document.getElementById('gauntlet-deck-name').value = name;
    parsePastedDeck('gauntlet');
  }
}

// -------------------------------------------------------------
// TAB 1: META GAUNTLET TESTING & VISUAL CHARTS
// -------------------------------------------------------------
async function runGauntletSim() {
  const deckText = document.getElementById('gauntlet-deck-input').value.trim();
  const deckName = document.getElementById('gauntlet-deck-name').value.trim() || "Candidate Deck";
  const gamesCount = parseInt(document.getElementById('gauntlet-games-count').value || "2");
  const mctsIterations = parseInt(document.getElementById('gauntlet-mcts-iter').value || "40");

  const btn = document.getElementById('btn-run-gauntlet');
  const spinner = document.getElementById('gauntlet-spinner');
  const statusText = document.getElementById('gauntlet-status-text');

  btn.disabled = true;
  spinner.classList.remove('hidden');
  statusText.textContent = `Simulating ${gamesCount * 8} matches against Standard Meta...`;

  try {
    const res = await fetch('/api/run_gauntlet', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deck_text: deckText,
        deck_name: deckName,
        games_per_matchup: gamesCount,
        mcts_iterations: mctsIterations
      })
    });

    const data = await res.json();
    if (!data.success) {
      alert("Simulation error: " + (data.error || "Unknown"));
      return;
    }

    renderGauntletResults(data.report, data.chart_data);
    statusText.textContent = `Gauntlet complete in ${data.report.elapsed_seconds.toFixed(2)}s!`;
  } catch (err) {
    alert("Network error running gauntlet: " + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
  }
}

function renderGauntletResults(report, chartData) {
  // Update Top KPIs
  document.getElementById('kpi-record').textContent = report.overall_record;
  document.getElementById('kpi-winrate').textContent = `${report.overall_win_rate.toFixed(1)}%`;
  document.getElementById('kpi-tier').textContent = report.meta_tier;
  document.getElementById('kpi-prizediff').textContent = `${report.net_prize_diff >= 0 ? '+' : ''}${report.net_prize_diff}`;
  document.getElementById('kpi-mulligan').textContent = `${report.mulligan_rate.toFixed(1)}%`;

  // Render Table Rows
  const tbody = document.getElementById('gauntlet-table-body');
  let html = '';
  
  Object.keys(report.matchup_breakdown).forEach(opp => {
    const m = report.matchup_breakdown[opp];
    let badgeClass = "bg-rose-500/20 text-rose-300 border-rose-500/40";
    if (m.classification === "Favorable") badgeClass = "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    else if (m.classification === "Even") badgeClass = "bg-amber-500/20 text-amber-300 border-amber-500/40";

    html += `
      <tr class="hover:bg-slate-800/40 transition border-b border-slate-800/60">
        <td class="p-3 font-semibold text-slate-200">${opp}</td>
        <td class="p-3"><span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold border ${badgeClass}">${m.classification}</span></td>
        <td class="p-3 font-mono text-slate-300">${m.record}</td>
        <td class="p-3 font-mono font-bold ${m.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}">${m.win_rate.toFixed(1)}%</td>
        <td class="p-3 font-mono ${m.prize_diff >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${m.prize_diff >= 0 ? '+' : ''}${m.prize_diff}</td>
      </tr>
    `;
  });
  tbody.innerHTML = html;

  // Render Chart.js Visuals
  renderGauntletBarChart(chartData);
  renderGauntletRadarChart(chartData);
  renderGauntletPrizeChart(chartData);
}

function renderGauntletBarChart(chartData) {
  const ctx = document.getElementById('gauntlet-bar-canvas').getContext('2d');
  if (gauntletBarChart) gauntletBarChart.destroy();

  const colors = chartData.win_rates.map(wr => wr >= 55 ? '#10b981' : (wr >= 45 ? '#f59e0b' : '#f43f5e'));

  gauntletBarChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartData.labels,
      datasets: [{
        label: 'Win Rate (%)',
        data: chartData.win_rates,
        backgroundColor: colors,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          max: 100,
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          ticks: { color: '#94a3b8', font: { family: 'Segoe UI' } }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#cbd5e1', font: { family: 'Segoe UI', size: 10 } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderGauntletRadarChart(chartData) {
  const ctx = document.getElementById('gauntlet-radar-canvas').getContext('2d');
  if (gauntletRadarChart) gauntletRadarChart.destroy();

  gauntletRadarChart = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: chartData.labels,
      datasets: [{
        label: 'Win Rate (%)',
        data: chartData.win_rates,
        backgroundColor: 'rgba(99, 102, 241, 0.25)',
        borderColor: '#6366f1',
        pointBackgroundColor: '#818cf8',
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          min: 0,
          max: 100,
          ticks: { stepSize: 25, color: '#64748b', backdropColor: 'transparent' },
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          pointLabels: { color: '#cbd5e1', font: { size: 10, family: 'Segoe UI' } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

function renderGauntletPrizeChart(chartData) {
  const ctx = document.getElementById('gauntlet-prize-canvas').getContext('2d');
  if (gauntletPrizeChart) gauntletPrizeChart.destroy();

  const colors = chartData.prize_diffs.map(p => p >= 0 ? '#38bdf8' : '#f43f5e');

  gauntletPrizeChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartData.labels,
      datasets: [{
        label: 'Net Prize Differential',
        data: chartData.prize_diffs,
        backgroundColor: colors,
        borderRadius: 6
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          ticks: { color: '#94a3b8' }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#cbd5e1', font: { size: 10 } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// -------------------------------------------------------------
// TAB 2: SCRATCH DECK BUILDER & COMPOSITION DONUT
// -------------------------------------------------------------
async function generateScratchDeck() {
  const attacker = document.getElementById('builder-attacker-input').value.trim() || "Ceruledge ex";
  const aceSpec = document.getElementById('builder-ace-input').value.trim() || null;

  try {
    const res = await fetch('/api/build_scratch_deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ attacker: attacker, ace_spec: aceSpec })
    });

    const data = await res.json();
    if (!data.success) {
      alert("Error generating deck: " + data.error);
      return;
    }

    document.getElementById('builder-deck-output').value = data.ptcgl_text;
    renderBuilderDonut(data.composition);

    document.getElementById('builder-count-pkmn').textContent = data.composition.pokemon;
    document.getElementById('builder-count-tr').textContent = data.composition.trainers;
    document.getElementById('builder-count-nr').textContent = data.composition.energy;
    document.getElementById('builder-ace-badge').textContent = data.ace_spec;
    document.getElementById('builder-mode-title').textContent = `Synthesized Deck: ${attacker}`;
    document.getElementById('builder-strategy-box').classList.add('hidden');
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function buildTargetedCounterDeck() {
  const targetSelect = document.getElementById('builder-target-select');
  const targetName = targetSelect ? targetSelect.value : "Charizard ex";

  try {
    const res = await fetch('/api/target_counter_deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ target_name: targetName })
    });

    const data = await res.json();
    if (!data.success) {
      alert("Error: " + data.error);
      return;
    }

    document.getElementById('builder-deck-output').value = data.ptcgl_text;
    renderBuilderDonut(data.composition);

    document.getElementById('builder-count-pkmn').textContent = data.composition.pokemon;
    document.getElementById('builder-count-tr').textContent = data.composition.trainers;
    document.getElementById('builder-count-nr').textContent = data.composition.energy;
    document.getElementById('builder-ace-badge').textContent = data.ace_spec;

    document.getElementById('builder-mode-title').textContent = `🎯 Dedicated Counter: ${data.counter_deck_name}`;
    const stratBox = document.getElementById('builder-strategy-box');
    stratBox.classList.remove('hidden');
    document.getElementById('builder-strategy-text').innerHTML = data.strategy_rationale.replace(/\n/g, '<br>');
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function discoverRogueDeck() {
  try {
    const res = await fetch('/api/generate_rogue_deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });

    const data = await res.json();
    if (!data.success) {
      alert("Error: " + data.error);
      return;
    }

    document.getElementById('builder-deck-output').value = data.ptcgl_text;
    renderBuilderDonut(data.composition);

    document.getElementById('builder-count-pkmn').textContent = data.composition.pokemon;
    document.getElementById('builder-count-tr').textContent = data.composition.trainers;
    document.getElementById('builder-count-nr').textContent = data.composition.energy;
    document.getElementById('builder-ace-badge').textContent = data.ace_spec;

    document.getElementById('builder-mode-title').textContent = `🎲 Rogue Innovation: ${data.rogue_name}`;
    const stratBox = document.getElementById('builder-strategy-box');
    stratBox.classList.remove('hidden');
    document.getElementById('builder-strategy-text').innerHTML = `<b>Archetype Concept:</b> ${data.archetype_concept}<br><br><b>Why it beats the top meta:</b><br>${data.why_it_wins}`;
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

function renderBuilderDonut(comp) {
  const ctx = document.getElementById('builder-donut-canvas').getContext('2d');
  if (builderDonutChart) builderDonutChart.destroy();

  builderDonutChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Pokémon', 'Trainers', 'Energy'],
      datasets: [{
        data: [comp.pokemon, comp.trainers, comp.energy],
        backgroundColor: ['#f59e0b', '#3b82f6', '#10b981'],
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { position: 'bottom', labels: { color: '#cbd5e1', font: { size: 11 } } }
      },
      cutout: '70%'
    }
  });
}

async function parsePastedDeck(context) {
  const text = document.getElementById(`${context}-deck-input`).value.trim();
  if (!text) return;

  try {
    const res = await fetch('/api/parse_deck', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deck_text: text })
    });

    const data = await res.json();
    if (data.success) {
      const statusBadge = document.getElementById(`${context}-valid-badge`);
      if (statusBadge) {
        statusBadge.textContent = data.is_valid ? "✅ Legal 60-Card Deck" : `❌ Invalid (${data.errors[0]})`;
        statusBadge.className = data.is_valid ? "px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40" : "px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40";
      }
    }
  } catch (err) {
    console.error("Parse check error:", err);
  }
}

function copyDeckText(textareaId) {
  const text = document.getElementById(textareaId).value;
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    alert("Decklist copied to clipboard!");
  });
}

// -------------------------------------------------------------
// TAB 3: ANTI-META EV TOURNAMENT OPTIMIZER
// -------------------------------------------------------------
function applyWorldsPreset(preset) {
  if (preset === 'day1') {
    document.getElementById('slider-dp').value = 43;
    document.getElementById('slider-dp-val').textContent = '43%';
    document.getElementById('slider-tm').value = 11;
    document.getElementById('slider-tm-val').textContent = '11%';
    document.getElementById('slider-zr').value = 8;
    document.getElementById('slider-zr-val').textContent = '8%';
    document.getElementById('slider-ak').value = 7;
    document.getElementById('slider-ak-val').textContent = '7%';
    document.getElementById('slider-sk').value = 6;
    document.getElementById('slider-sk-val').textContent = '6%';
    document.getElementById('slider-ex').value = 4;
    document.getElementById('slider-ex-val').textContent = '4%';
    document.getElementById('slider-cz').value = 21;
    document.getElementById('slider-cz-val').textContent = '21%';
  } else if (preset === 'day2') {
    document.getElementById('slider-dp').value = 30;
    document.getElementById('slider-dp-val').textContent = '30%';
    document.getElementById('slider-tm').value = 14;
    document.getElementById('slider-tm-val').textContent = '14%';
    document.getElementById('slider-zr').value = 8;
    document.getElementById('slider-zr-val').textContent = '8%';
    document.getElementById('slider-ak').value = 10;
    document.getElementById('slider-ak-val').textContent = '10%';
    document.getElementById('slider-sk').value = 8;
    document.getElementById('slider-sk-val').textContent = '8%';
    document.getElementById('slider-ex').value = 6;
    document.getElementById('slider-ex-val').textContent = '6%';
    document.getElementById('slider-cz').value = 24;
    document.getElementById('slider-cz-val').textContent = '24%';
  }
}

async function runAntiMetaOptimizer() {
  const dpShare = parseFloat(document.getElementById('slider-dp').value) / 100;
  const tmShare = parseFloat(document.getElementById('slider-tm').value) / 100;
  const zrShare = parseFloat(document.getElementById('slider-zr').value) / 100;
  const akShare = parseFloat(document.getElementById('slider-ak').value) / 100;
  const skShare = parseFloat(document.getElementById('slider-sk').value) / 100;
  const exShare = parseFloat(document.getElementById('slider-ex').value) / 100;
  const czShare = parseFloat(document.getElementById('slider-cz').value) / 100;

  const total = dpShare + tmShare + zrShare + akShare + skShare + exShare + czShare;
  if (total <= 0) {
    alert("Please set at least one expected meta share percentage.");
    return;
  }

  const metaDist = {
    "Dragapult ex": dpShare / total,
    "Teal Mask / Lillie's Clefairy": tmShare / total,
    "N's Zoroark ex": zrShare / total,
    "Alakazam / Dudunsparce": akShare / total,
    "Slowking": skShare / total,
    "Mega Excadrill ex / Metang": (exShare * 0.6) / total,
    "Crustle": (exShare * 0.4) / total,
    "Charizard ex": (czShare * 0.5) / total,
    "Gardevoir ex": (czShare * 0.5) / total
  };

  const btn = document.getElementById('btn-run-antimeta');
  const spinner = document.getElementById('antimeta-spinner');
  btn.disabled = true;
  spinner.classList.remove('hidden');

  try {
    const res = await fetch('/api/optimize_anti_meta', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ meta_distribution: metaDist, mcts_iterations: 30 })
    });

    const data = await res.json();
    if (!data.success) {
      alert("Optimizer error: " + data.error);
      return;
    }

    document.getElementById('antimeta-best-name').textContent = data.best_deck_name;
    document.getElementById('antimeta-best-wr').textContent = `${(data.expected_winrate * 100).toFixed(1)}% Expected Field Win Rate`;
    document.getElementById('antimeta-deck-output').value = data.ptcgl_text;

    renderAntiMetaChart(data.candidates_chart);
  } catch (err) {
    alert("Network error: " + err.message);
  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
  }
}

function renderAntiMetaChart(chartData) {
  const ctx = document.getElementById('antimeta-bar-canvas').getContext('2d');
  if (antiMetaChart) antiMetaChart.destroy();

  antiMetaChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: chartData.labels,
      datasets: [{
        label: 'Field Expected Value (%)',
        data: chartData.win_rates,
        backgroundColor: '#10b981',
        borderRadius: 8
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          beginAtZero: true,
          max: 100,
          grid: { color: 'rgba(51, 65, 85, 0.4)' },
          ticks: { color: '#94a3b8' }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f8fafc', font: { size: 11, weight: 'bold' } }
        }
      },
      plugins: {
        legend: { display: false }
      }
    }
  });
}

// -------------------------------------------------------------
// TAB 4: STRATEGIC MATCHUP GUIDE & PRIZE MAP
// -------------------------------------------------------------
async function generateStrategyGuide() {
  const myDeckPreset = document.getElementById('plan-my-select').value;
  const myDeckPasted = document.getElementById('gauntlet-deck-input').value;
  const oppDeck = document.getElementById('plan-opp-select').value;

  try {
    const res = await fetch('/api/generate_gameplan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        my_deck_name: myDeckPreset || "My Deck",
        my_deck_text: myDeckPreset ? "" : myDeckPasted,
        opp_archetype: oppDeck
      })
    });

    const data = await res.json();
    if (!data.success) {
      alert("Error generating gameplan: " + data.error);
      return;
    }

    const plan = data.gameplan;
    document.getElementById('plan-title').textContent = plan.matchup_title;
    document.getElementById('plan-prize-text').innerHTML = plan.prize_map_plan.replace(/\n/g, '<br>');
    document.getElementById('plan-setup-text').textContent = plan.turn_1_2_setup;

    const warnContainer = document.getElementById('plan-warnings-list');
    warnContainer.innerHTML = plan.threat_warnings.map(w => `<li class="flex items-start gap-2"><span class="text-rose-400 font-bold">•</span><span>${w}</span></li>`).join('');

    const dosContainer = document.getElementById('plan-dos-list');
    dosContainer.innerHTML = plan.dos.map(d => `<li class="flex items-start gap-2"><span class="text-emerald-400 font-bold">✓</span><span>${d}</span></li>`).join('');

    const dontsContainer = document.getElementById('plan-donts-list');
    dontsContainer.innerHTML = plan.donts.map(d => `<li class="flex items-start gap-2"><span class="text-rose-400 font-bold">✗</span><span>${d}</span></li>`).join('');
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

// Initial Sample Charts on Load
function initSampleCharts() {
  const sampleLabels = ['Gardevoir ex', 'Terapagos ex', 'Charizard ex', 'Dragapult ex', 'Miraidon ex', 'Raging Bolt ex', 'Gholdengo ex', 'Ceruledge ex'];
  const sampleWRs = [85.7, 71.4, 71.4, 50.0, 64.3, 50.0, 42.9, 50.0];
  const sampleDiffs = [+8, +6, +5, 0, +4, +1, -2, 0];

  renderGauntletBarChart({ labels: sampleLabels, win_rates: sampleWRs });
  renderGauntletRadarChart({ labels: sampleLabels, win_rates: sampleWRs });
  renderGauntletPrizeChart({ labels: sampleLabels, prize_diffs: sampleDiffs });
  renderBuilderDonut({ pokemon: 14, trainers: 32, energy: 14 });
}
