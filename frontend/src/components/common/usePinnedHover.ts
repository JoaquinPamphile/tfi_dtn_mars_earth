import { useState } from "react";

/** Hover o foco muestran el ítem. El click lo deja fijo para la exposición. */
export function usePinnedHover() {
  const [pinned, setPinned] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);

  function bind(id: string) {
    return {
      "data-active": hovered === id || (hovered === null && pinned === id) ? "true" : "false",
      "aria-pressed": pinned === id,
      onMouseEnter: () => setHovered(id),
      onMouseLeave: () => setHovered(null),
      onFocus: () => setHovered(id),
      onBlur: () => setHovered(null),
      onClick: () => setPinned((actual) => (actual === id ? null : id)),
    } as const;
  }

  return {
    pinned,
    active: hovered ?? pinned,
    bind,
  };
}
