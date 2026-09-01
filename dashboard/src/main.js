/**
 * The client entry point: mount the shell into `index.html`.
 *
 * Data flow:
 *     index.html -> here -> App.vue -> the seven views
 */

import { createApp } from "vue";

import App from "./App.vue";
import "./style.css";

createApp(App).mount("#app");
