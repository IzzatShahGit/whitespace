import type { ReactNode } from "react";

import { scriptProps } from "@/components/chat/script";

// The guide writes plain paragraphs, bullet lists and **bold**. This renders exactly
// that as React elements (never raw HTML), so model output can't inject markup.

const INLINE = /(\*\*[^*]+\*\*|\[N\d+\])/g;
const BULLET = /^\s*[-*•]\s+/;
const NUMBERED = /^\s*\d+[.)]\s+/;

function inline(text: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="font-semibold text-fg">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (/^\[N\d+\]$/.test(part)) {
      return (
        <sup key={i} className="ml-0.5 rounded bg-surface-2 px-1 text-xs text-muted">
          {part.slice(1, -1)}
        </sup>
      );
    }
    return part;
  });
}

type Block = { kind: "p"; lines: string[] } | { kind: "ul" | "ol"; items: string[] };

function blocks(text: string): Block[] {
  const out: Block[] = [];
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const last = out.at(-1);
    if (!line.trim()) {
      out.push({ kind: "p", lines: [] }); // paragraph break
    } else if (BULLET.test(line) || NUMBERED.test(line)) {
      const kind = BULLET.test(line) ? "ul" : "ol";
      const item = line.replace(kind === "ul" ? BULLET : NUMBERED, "");
      if (last?.kind === kind) last.items.push(item);
      else out.push({ kind, items: [item] });
    } else if (last?.kind === "p") {
      last.lines.push(line);
    } else {
      out.push({ kind: "p", lines: [line] });
    }
  }
  return out.filter((b) => (b.kind === "p" ? b.lines.length > 0 : b.items.length > 0));
}

export function Markdown({ text }: { text: string }) {
  return (
    <div {...scriptProps(text, "flex flex-col gap-3 text-[15px] text-fg", "leading-7")}>
      {blocks(text).map((block, i) => {
        if (block.kind === "p") return <p key={i}>{inline(block.lines.join(" "))}</p>;
        const List = block.kind;
        return (
          <List
            key={i}
            className={`flex flex-col gap-1.5 pl-5 ${List === "ul" ? "list-disc" : "list-decimal"} marker:text-subtle`}
          >
            {block.items.map((item, j) => (
              <li key={j}>{inline(item)}</li>
            ))}
          </List>
        );
      })}
    </div>
  );
}
