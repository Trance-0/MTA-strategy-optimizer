import DefaultTheme from "vitepress/theme";
import DrawioDiagram from "./components/DrawioDiagram.vue";
import Layout from "./Layout.vue";
import "./custom.css";

export default {
  extends: DefaultTheme,
  Layout,
  enhanceApp({ app }) {
    app.component("DrawioDiagram", DrawioDiagram);
  },
};
