---
title: Redirecting to English documentation
description: Open the English Marketing ROI Analysis documentation.
compact: "Redirect stub that forwards to the English site root. No content; never needs to be read for a task."
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
