import type { ExtensionContext } from "@foxglove/extension";

import { initPedestalPanel } from "./PedestalPanel";

export function activate(context: ExtensionContext): void {
  context.registerPanel({ name: "Pedestal Control", initPanel: initPedestalPanel });
}
