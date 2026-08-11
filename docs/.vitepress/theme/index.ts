import DefaultTheme from "vitepress/theme";
import DrawioDiagram from "./components/DrawioDiagram.vue";
import "./custom.css";

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component("DrawioDiagram", DrawioDiagram);
  },
};
