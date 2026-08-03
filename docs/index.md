---
title: Redirecting to English documentation
description: Open the English Marketing ROI Analysis documentation.
head:
  - - meta
    - http-equiv: refresh
      content: 0; url=/en/
  - - link
    - rel: canonical
      href: /en/
---

# Documentation

Redirecting to the [English documentation](/en/).

- [English documentation](/en/)

<script setup>
import { onMounted } from "vue";

onMounted(() => {
  if (window.location.pathname === "/") {
    window.location.replace("/en/");
  }
});
</script>
