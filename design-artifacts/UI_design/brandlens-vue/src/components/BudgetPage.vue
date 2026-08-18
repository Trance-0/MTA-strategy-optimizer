<script setup>
const props = defineProps({
  campaigns: {
    type: Array,
    default: () => [],
  },
  money: {
    type: Function,
    default: () => '$0K',
  },
  pct: {
    type: Function,
    default: () => '0%',
  },
  budgetState: {
    type: Function,
    default: () => ['On track', 'green'],
  },
})

const emit = defineEmits(['openOptimizer'])

const pacingRows = (props.campaigns && props.campaigns[0] && props.campaigns[0].groups)
  ? props.campaigns[0].groups.map((group, index) => {
      const actual = [105, 136, 71, 62][index] ?? group[1]
      const ratio = Math.min(Math.round((actual / group[1]) * 100), 100)

      return {
        name: group[0],
        total: group[1],
        actual,
        ratio,
      }
    })
  : []
</script>

<template>
  <section class="page-grid budget-page">
    <aside class="filters card">
      <h3>Filters</h3>
      <div class="field">
        <label>Fiscal year</label>
        <select><option>FY25–26</option></select>
      </div>
      <div class="field">
        <label>Retailer</label>
        <select><option>Amazon</option></select>
      </div>
      <div class="field">
        <label>Market</label>
        <select><option>US</option></select>
      </div>
      <div class="field">
        <label>Category</label>
        <select><option>Shave Care</option></select>
      </div>
    </aside>

    <div class="stack">
      <article class="card">
        <div class="card-head">
          <h2>Budget utilization</h2>
          <select class="btn small">
            <option>FY25–26</option>
            <option>Q2</option>
          </select>
        </div>
        <div class="card-body">
          <div class="metrics">
            <div class="metric"><label>Approved budget</label><b>$5.00M</b></div>
            <div class="metric"><label>Actual spend</label><b>$3.74M</b><span>75% utilized</span></div>
            <div class="metric"><label>Remaining</label><b>$1.26M</b></div>
            <div class="metric"><label>Forecast</label><b>$4.92M</b><span>End of period</span></div>
          </div>
          <div class="progress-row">
            <div class="progress"><i style="width:75%"></i></div>
            <b>75%</b>
          </div>
        </div>
      </article>

      <article class="card">
        <div class="card-head">
          <h2>Spend by campaign</h2>
          <span class="sub">Exceptions open in optimizer</span>
        </div>
        <div class="card-body table-wrap">
          <table>
            <thead>
              <tr>
                <th>Campaign</th>
                <th class="num">Budget</th>
                <th class="num">Spend</th>
                <th class="num">Pacing</th>
                <th class="num">Forecast</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in campaigns" :key="item.id">
                <td class="name"><strong>{{ item.name }}</strong><span>{{ item.groups.length }} ad groups</span></td>
                <td class="num">{{ money(item.budget) }}</td>
                <td class="num">{{ money(item.spend) }}</td>
                <td class="num">{{ pct(item.spend, item.budget) }}</td>
                <td class="num">{{ money(item.forecast) }}</td>
                <td><span class="tag" :class="budgetState(item)[1]">{{ budgetState(item)[0] }}</span></td>
                <td><button class="btn link small" @click="emit('openOptimizer', item.id)">Review</button></td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="card-body pacing-block">
          <div class="pacing-title">
            <h3>Ad-group pacing · Shave Care — US</h3>
            <span>Current period</span>
          </div>

          <div v-for="row in pacingRows" :key="row.name" class="pacing-item">
            <strong>{{ row.name }}</strong>
            <span>{{ money(row.actual) }} / {{ money(row.total) }}</span>
            <div class="progress"><i :style="{ width: row.ratio + '%' }"></i></div>
            <strong class="pacing-value">{{ row.ratio }}%</strong>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>
