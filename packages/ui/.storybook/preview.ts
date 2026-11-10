import type { Preview } from "@storybook/react";

import "./storybook.css";

const preview: Preview = {
  parameters: {
    layout: "padded",
    controls: { expanded: true },
    a11y: { element: "#storybook-root" },
    viewport: {
      viewports: {
        sm: { name: "360 (phone)", styles: { width: "360px", height: "740px" } },
        md: { name: "768 (tablet)", styles: { width: "768px", height: "1024px" } },
        lg: { name: "1024 (laptop)", styles: { width: "1024px", height: "768px" } },
        xl: { name: "1440 (desktop)", styles: { width: "1440px", height: "900px" } },
      },
    },
  },
};

export default preview;
