<script setup>
defineProps({
  logRows: {
    type: Array,
    default: () => [],
  },
  tone: {
    type: Function,
    default: () => 'gray',
  },
})

const emit = defineEmits(['export'])
</script>

<template>
  <section class="page-grid">
    <article class="card">
      <div class="card-head">
        <h2>Optimization records</h2>
        <button class="btn small" @click="emit('export')">Export</button>
      </div>
      <div class="card-body table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Campaign</th>
              <th>Change</th>
              <th>Review</th>
              <th>Pilot</th>
              <th>Result</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in logRows" :key="row[0]">
              <td>{{ row[0] }}</td>
              <td class="name"><strong>{{ row[1] }}</strong></td>
              <td>{{ row[2] }}</td>
              <td><span class="tag" :class="tone(row[3])">{{ row[3] }}</span></td>
              <td>{{ row[4] }}</td>
              <td>{{ row[5] }}</td>
              <td><span class="tag" :class="tone(row[6])">{{ row[6] }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>
