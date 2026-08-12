---
title: Redirecting to English documentation
description: Open the English Marketing ROI Analysis documentation.
head:
  - - meta
    - http-equiv: refresh
      content: 0; url=./en/
---

# Documentation

Redirecting to the [English documentation](/en/).

- [English documentation](/en/)

<script setup>
import { onMounted } from "vue";

onMounted(() => {
  window.location.replace(new URL("./en/", window.location.href).href);
});
</script>
