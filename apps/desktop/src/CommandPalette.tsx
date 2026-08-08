import { useEffect, useMemo, useRef, useState } from "react";

export interface Command {
  id: string;
  title: string;
  hint?: string;
  run: () => void | Promise<void>;
}

/**
 * F09 — command palette and routing.
 *
 * Every command here performs a real action against the control plane or changes the view. None is
 * a label for something unimplemented: a command that opened an empty pane would be a stub with a
 * keyboard shortcut.
 */
export function CommandPalette({
  commands,
  open,
  onClose,
}: {
  commands: Command[];
  open: boolean;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((c) => `${c.title} ${c.hint ?? ""}`.toLowerCase().includes(needle));
  }, [commands, query]);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      inputRef.current?.focus();
    }
  }, [open]);

  useEffect(() => {
    setCursor((c) => Math.min(c, Math.max(matches.length - 1, 0)));
  }, [matches.length]);

  if (!open) return null;

  const accept = async (command: Command | undefined) => {
    if (!command) return;
    onClose();
    await command.run();
  };

  return (
    <div className="palette-scrim" onClick={onClose} role="presentation">
      <div className="palette" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Command palette">
        <input
          ref={inputRef}
          className="palette-input"
          placeholder="Type a command…"
          value={query}
          aria-label="Command"
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            else if (e.key === "ArrowDown") {
              e.preventDefault();
              setCursor((c) => Math.min(c + 1, matches.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setCursor((c) => Math.max(c - 1, 0));
            } else if (e.key === "Enter") {
              e.preventDefault();
              void accept(matches[cursor]);
            }
          }}
        />
        <ul className="palette-list">
          {matches.length === 0 && <li className="palette-empty">No matching command.</li>}
          {matches.map((command, i) => (
            <li key={command.id}>
              <button
                className={`palette-item ${i === cursor ? "sel" : ""}`}
                onMouseEnter={() => setCursor(i)}
                onClick={() => void accept(command)}
              >
                <span>{command.title}</span>
                {command.hint && <span className="palette-hint">{command.hint}</span>}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Ctrl/Cmd-K opens the palette. */
export function usePaletteHotkey(setOpen: (open: boolean) => void) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setOpen]);
}
