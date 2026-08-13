"use client";

import { useEffect, useCallback, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import {
  TextStyle,
  Color,
  FontFamily,
  FontSize,
} from "@tiptap/extension-text-style";
import Highlight from "@tiptap/extension-highlight";
import Link from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import {
  Table,
  TableRow,
  TableHeader,
  TableCell,
} from "@tiptap/extension-table";

interface RichTextEditorProps {
  value: string; // HTML
  onChange: (html: string) => void;
  tx: (key: string, fallback: string) => string;
}

const FONT_FAMILIES = [
  { label: "Inter", value: "Inter, sans-serif" },
  { label: "Arial", value: "Arial, sans-serif" },
  { label: "Times New Roman", value: "'Times New Roman', serif" },
  { label: "Georgia", value: "Georgia, serif" },
  { label: "Courier New", value: "'Courier New', monospace" },
];

const FONT_SIZES = [
  "10",
  "11",
  "12",
  "13",
  "14",
  "16",
  "18",
  "20",
  "24",
  "28",
  "32",
];

const TEXT_COLORS = [
  "#1a1a1a",
  "#dc2626",
  "#ea580c",
  "#eab308",
  "#16a34a",
  "#0ea5e9",
  "#2563eb",
  "#7c3aed",
];
const HIGHLIGHT_COLORS = [
  "#fef08a",
  "#bbf7d0",
  "#bfdbfe",
  "#fbcfe8",
  "#fed7aa",
];
const TABLE_BORDER_COLORS = [
  "#e7e5e4",
  "#004D25",
  "#d9a700",
  "#dc2626",
  "#2563eb",
];

const ALIGN_LABELS: Record<"left" | "center" | "right" | "justify", [string, string]> = {
  left: ["Align left", "Rata Kiri"],
  center: ["Align center", "Rata Tengah"],
  right: ["Align right", "Rata Kanan"],
  justify: ["Align justify", "Rata Kiri-Kanan"],
};

// Extend TableCell/TableHeader dengan attribute borderColor kustom (disimpan sebagai inline
// style di HTML, jadi ikut kesave/kebaca lewat editor.getHTML() seperti attribute bawaan lain).
const TableCellWithBorder = TableCell.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      borderColor: {
        default: null,
        parseHTML: (element: HTMLElement) => element.style.borderColor || null,
        renderHTML: (attributes: { borderColor?: string | null }) => {
          if (!attributes.borderColor) return {};
          return { style: `border-color: ${attributes.borderColor};` };
        },
      },
    };
  },
});
const TableHeaderWithBorder = TableHeader.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      borderColor: {
        default: null,
        parseHTML: (element: HTMLElement) => element.style.borderColor || null,
        renderHTML: (attributes: { borderColor?: string | null }) => {
          if (!attributes.borderColor) return {};
          return { style: `border-color: ${attributes.borderColor};` };
        },
      },
    };
  },
});

export default function RichTextEditor({
  value,
  onChange,
  tx,
}: RichTextEditorProps) {
  const editor = useEditor({
    immediatelyRender: false,
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        // Link & Underline sudah ikut bawaan StarterKit di TipTap v3 — dimatikan di sini
        // supaya versi custom di bawah (Underline polos, Link dengan openOnClick/autolink)
        // yang dipakai, bukan didaftarkan dua kali (nyebabin warning "Duplicate extension").
        link: false,
        underline: false,
      }),
      Underline,
      TextStyle,
      Color,
      FontFamily,
      FontSize,
      Highlight.configure({ multicolor: true }),
      Link.configure({ openOnClick: false, autolink: true }),
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeaderWithBorder,
      TableCellWithBorder,
    ],
    content: value,
    onUpdate: ({ editor }) => {
      onChange(editor.getHTML());
    },
    editorProps: {
      attributes: {
        class: "rte-content focus:outline-none",
      },
    },
  });

  // Sinkronisasi kalau `value` berubah dari LUAR editor (misal user pindah halaman/section
  // di Step 4, jadi kontennya harus diganti total) — tapi jangan sampai bikin infinite loop
  // atau mengganggu posisi kursor pas user lagi ngetik normal.
  useEffect(() => {
    if (!editor) return;
    const current = editor.getHTML();
    if (value !== current) {
      editor.commands.setContent(value || "", { emitUpdate: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, editor]);

  // BUG DIPERBAIKI: dulu pakai window.prompt() native bawaan browser - terasa asing di
  // tengah toolbar custom yang rapi, dan tidak bisa distyle sama sekali. Diganti dialog
  // kecil sendiri (linkPromptOpen + linkUrlInput di bawah), konsisten dengan pola
  // ConfirmDialog yang sudah dipakai di tempat lain aplikasi ini.
  const [linkPromptOpen, setLinkPromptOpen] = useState(false);
  const [linkUrlInput, setLinkUrlInput] = useState("");

  const setLink = useCallback(() => {
    if (!editor) return;
    const previousUrl = editor.getAttributes("link").href;
    setLinkUrlInput(previousUrl || "https://");
    setLinkPromptOpen(true);
  }, [editor]);

  const confirmSetLink = useCallback(() => {
    if (!editor) return;
    const url = linkUrlInput.trim();
    if (url === "") {
      editor.chain().focus().extendMarkRange("link").unsetLink().run();
    } else {
      editor.chain().focus().extendMarkRange("link").setLink({ href: url }).run();
    }
    setLinkPromptOpen(false);
  }, [editor, linkUrlInput]);

  const insertTable = useCallback(() => {
    if (!editor) return;
    editor
      .chain()
      .focus()
      .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
      .run();
  }, [editor]);

  // Diterapkan ke tableCell DAN tableHeader sekaligus supaya tetap benar kalau seleksi
  // menyentuh baris header — no-op aman kalau cursor sedang tidak berada di dalam tabel.
  const setTableBorderColor = useCallback(
    (color: string | null) => {
      if (!editor) return;
      editor
        .chain()
        .focus()
        .updateAttributes("tableCell", { borderColor: color })
        .updateAttributes("tableHeader", { borderColor: color })
        .run();
    },
    [editor],
  );

  if (!editor) {
    return (
      <div className="w-full h-80 bg-stone-50 border border-stone-250 rounded-xl flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-stone-200 border-t-petro-green rounded-full animate-spin"></div>
      </div>
    );
  }

  const btnClass = (active: boolean) =>
    `inline-flex items-center justify-center w-7 h-7 rounded-md text-xs font-bold transition-colors ${
      active ? "bg-stone-800 text-white" : "text-stone-600 hover:bg-stone-200"
    }`;

  return (
    <div className="border border-stone-250 rounded-xl overflow-hidden bg-white">
      {/* ── TOOLBAR ── */}
      <div className="flex flex-wrap items-center gap-1 p-2 bg-stone-50 border-b border-stone-200">
        {/* Paragraph style */}
        <select
          value={
            editor.isActive("heading", { level: 1 })
              ? "h1"
              : editor.isActive("heading", { level: 2 })
                ? "h2"
                : editor.isActive("heading", { level: 3 })
                  ? "h3"
                  : "p"
          }
          onChange={(e) => {
            const v = e.target.value;
            if (v === "p") editor.chain().focus().setParagraph().run();
            else
              editor
                .chain()
                .focus()
                .toggleHeading({
                  level: Number(v.replace("h", "")) as 1 | 2 | 3,
                })
                .run();
          }}
          className="text-[11px] font-semibold border border-stone-200 rounded-md px-1.5 py-1 bg-white cursor-pointer"
        >
          <option value="p">{tx("Normal text", "Normal text")}</option>
          <option value="h1">{tx("Heading 1", "Heading 1")}</option>
          <option value="h2">{tx("Heading 2", "Heading 2")}</option>
          <option value="h3">{tx("Heading 3", "Heading 3")}</option>
        </select>

        {/* Font family */}
        <select
          onChange={(e) =>
            editor.chain().focus().setFontFamily(e.target.value).run()
          }
          className="text-[11px] font-semibold border border-stone-200 rounded-md px-1.5 py-1 bg-white cursor-pointer max-w-[110px]"
          defaultValue=""
        >
          <option value="" disabled>
            {tx("Font", "Font")}
          </option>
          {FONT_FAMILIES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>

        {/* Font size */}
        <div className="flex items-center border border-stone-200 rounded-md bg-white overflow-hidden">
          <button
            type="button"
            onClick={() =>
              (editor.chain().focus() as any).setFontSize("12px").run()
            }
            className="px-1.5 py-1 text-[11px] font-bold text-stone-500 hover:bg-stone-100"
            title={tx("Decrease font size", "Decrease font size")}
          >
            −
          </button>
          <select
            onChange={(e) =>
              (editor.chain().focus() as any)
                .setFontSize(`${e.target.value}px`)
                .run()
            }
            className="text-[11px] font-semibold px-1 py-1 bg-white cursor-pointer w-11 text-center"
            defaultValue="14"
          >
            {FONT_SIZES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() =>
              (editor.chain().focus() as any).setFontSize("16px").run()
            }
            className="px-1.5 py-1 text-[11px] font-bold text-stone-500 hover:bg-stone-100"
            title={tx("Increase font size", "Increase font size")}
          >
            +
          </button>
        </div>

        <div className="w-px h-5 bg-stone-200 mx-1" />

        {/* Bold / Italic / Underline */}
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBold().run()}
          className={btnClass(editor.isActive("bold"))}
          title={tx("Bold", "Tebal")}
        >
          <span className="font-black">B</span>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleItalic().run()}
          className={btnClass(editor.isActive("italic"))}
          title={tx("Italic", "Miring")}
        >
          <span className="italic">I</span>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          className={btnClass(editor.isActive("underline"))}
          title={tx("Underline", "Garis Bawah")}
        >
          <span className="underline">U</span>
        </button>

        {/* Text color */}
        <div className="relative group">
          <button
            type="button"
            className={btnClass(false)}
            title={tx("Text color", "Text color")}
          >
            <span
              className="font-black"
              style={{
                color: editor.getAttributes("textStyle").color || "#1a1a1a",
              }}
            >
              A
            </span>
          </button>
          <div className="hidden group-hover:flex absolute z-20 top-full left-0 mt-1 p-1.5 bg-white border border-stone-200 rounded-lg shadow-lg gap-1">
            {TEXT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => editor.chain().focus().setColor(c).run()}
                className="w-5 h-5 rounded-full border border-stone-300"
                style={{ backgroundColor: c }}
                title={c}
              />
            ))}
            <button
              type="button"
              onClick={() => editor.chain().focus().unsetColor().run()}
              className="w-5 h-5 rounded-full border border-stone-300 bg-white flex items-center justify-center text-[8px] font-bold text-stone-400"
              title={tx("Reset color", "Reset color")}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Highlight */}
        <div className="relative group">
          <button
            type="button"
            className={btnClass(editor.isActive("highlight"))}
            title={tx("Highlight", "Highlight")}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-3.5 h-3.5"
            >
              <path d="M13.5 3.5a1.5 1.5 0 0 1 2.121 2.121l-8.5 8.5a1.5 1.5 0 0 1-.53.354l-3.09 1.157a.375.375 0 0 1-.483-.483l1.157-3.09a1.5 1.5 0 0 1 .354-.53l8.5-8.5Z" />
            </svg>
          </button>
          <div className="hidden group-hover:flex absolute z-20 top-full left-0 mt-1 p-1.5 bg-white border border-stone-200 rounded-lg shadow-lg gap-1">
            {HIGHLIGHT_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() =>
                  editor.chain().focus().toggleHighlight({ color: c }).run()
                }
                className="w-5 h-5 rounded-full border border-stone-300"
                style={{ backgroundColor: c }}
                title={c}
              />
            ))}
            <button
              type="button"
              onClick={() => editor.chain().focus().unsetHighlight().run()}
              className="w-5 h-5 rounded-full border border-stone-300 bg-white flex items-center justify-center text-[8px] font-bold text-stone-400"
              title={tx("Remove highlight", "Remove highlight")}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Link */}
        <button
          type="button"
          onClick={setLink}
          className={btnClass(editor.isActive("link"))}
          title={tx("Insert link", "Insert link")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path d="M12.232 4.232a2.5 2.5 0 0 1 3.536 3.536l-1.225 1.224a.75.75 0 0 0 1.061 1.06l1.224-1.224a4 4 0 0 0-5.656-5.656l-3 3a4 4 0 0 0 .225 5.865.75.75 0 0 0 .977-1.138 2.5 2.5 0 0 1-.142-3.667l3-3Z" />
            <path d="M11.603 7.963a.75.75 0 0 0-.977 1.138 2.5 2.5 0 0 1 .142 3.667l-3 3a2.5 2.5 0 0 1-3.536-3.536l1.225-1.224a.75.75 0 0 0-1.061-1.06l-1.224 1.224a4 4 0 1 0 5.656 5.656l3-3a4 4 0 0 0-.225-5.865Z" />
          </svg>
        </button>

        <div className="w-px h-5 bg-stone-200 mx-1" />

        {/* Alignment */}
        {(["left", "center", "right", "justify"] as const).map((align) => (
          <button
            key={align}
            type="button"
            onClick={() => editor.chain().focus().setTextAlign(align).run()}
            className={btnClass(editor.isActive({ textAlign: align }))}
            title={tx(...ALIGN_LABELS[align])}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="w-3.5 h-3.5"
            >
              {align === "left" && (
                <path
                  fillRule="evenodd"
                  d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 4A.75.75 0 0 1 2.75 8h9.5a.75.75 0 0 1 0 1.5h-9.5A.75.75 0 0 1 2 8.75Zm0 4a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Zm0 4a.75.75 0 0 1 .75-.75h9.5a.75.75 0 0 1 0 1.5h-9.5a.75.75 0 0 1-.75-.75Z"
                  clipRule="evenodd"
                />
              )}
              {align === "center" && (
                <path
                  fillRule="evenodd"
                  d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75ZM5 8.75A.75.75 0 0 1 5.75 8h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 5 8.75ZM2 12.75a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75ZM5 16.75a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5a.75.75 0 0 1-.75-.75Z"
                  clipRule="evenodd"
                />
              )}
              {align === "right" && (
                <path
                  fillRule="evenodd"
                  d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm6 4A.75.75 0 0 1 8.75 8h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 8 8.75Zm-6 4a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Zm6 4a.75.75 0 0 1 .75-.75h8.5a.75.75 0 0 1 0 1.5h-8.5a.75.75 0 0 1-.75-.75Z"
                  clipRule="evenodd"
                />
              )}
              {align === "justify" && (
                <path
                  fillRule="evenodd"
                  d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 4A.75.75 0 0 1 2.75 8h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 8.75Zm0 4a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Zm0 4a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75Z"
                  clipRule="evenodd"
                />
              )}
            </svg>
          </button>
        ))}

        <div className="w-px h-5 bg-stone-200 mx-1" />

        {/* Lists */}
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          className={btnClass(editor.isActive("bulletList"))}
          title={tx("Bullet list", "Bullet list")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path d="M2 4.75A.75.75 0 0 1 2.75 4h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 2 4.75Zm4 0A.75.75 0 0 1 6.75 4h10.5a.75.75 0 0 1 0 1.5H6.75A.75.75 0 0 1 6 4.75Zm-4 5A.75.75 0 0 1 2.75 9h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 2 9.75Zm4 0A.75.75 0 0 1 6.75 9h10.5a.75.75 0 0 1 0 1.5H6.75A.75.75 0 0 1 6 9.75Zm-4 5a.75.75 0 0 1 .75-.75h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1-.75-.75Zm4 0a.75.75 0 0 1 .75-.75h10.5a.75.75 0 0 1 0 1.5H6.75a.75.75 0 0 1-.75-.75Z" />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          className={btnClass(editor.isActive("orderedList"))}
          title={tx("Numbered list", "Numbered list")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path d="M6.75 4.5h10.5a.75.75 0 0 1 0 1.5H6.75a.75.75 0 0 1 0-1.5Zm0 4.75h10.5a.75.75 0 0 1 0 1.5H6.75a.75.75 0 0 1 0-1.5Zm0 4.75h10.5a.75.75 0 0 1 0 1.5H6.75a.75.75 0 0 1 0-1.5Z" />
            <text x="1.2" y="6.2" fontSize="5" fontWeight="bold">
              1
            </text>
            <text x="1.2" y="10.9" fontSize="5" fontWeight="bold">
              2
            </text>
            <text x="1.2" y="15.6" fontSize="5" fontWeight="bold">
              3
            </text>
          </svg>
        </button>

        {/* Indent */}
        <button
          type="button"
          onClick={() => editor.chain().focus().liftListItem("listItem").run()}
          className={btnClass(false)}
          title={tx("Decrease indent", "Decrease indent")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path
              fillRule="evenodd"
              d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 10.5a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75ZM8 9.75A.75.75 0 0 1 8.75 9h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 8 9.75Zm-2.955-.442 2.5 2a.75.75 0 0 1 0 1.184l-2.5 2a.75.75 0 0 1-1.212-.59v-4a.75.75 0 0 1 1.212-.59Z"
              clipRule="evenodd"
            />
          </svg>
        </button>
        <button
          type="button"
          onClick={() => editor.chain().focus().sinkListItem("listItem").run()}
          className={btnClass(false)}
          title={tx("Increase indent", "Increase indent")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path
              fillRule="evenodd"
              d="M2 4.75A.75.75 0 0 1 2.75 4h14.5a.75.75 0 0 1 0 1.5H2.75A.75.75 0 0 1 2 4.75Zm0 10.5a.75.75 0 0 1 .75-.75h14.5a.75.75 0 0 1 0 1.5H2.75a.75.75 0 0 1-.75-.75ZM8 9.75A.75.75 0 0 1 8.75 9h8.5a.75.75 0 0 1 0 1.5h-8.5A.75.75 0 0 1 8 9.75Zm-3.545 4.442 2.5-2a.75.75 0 0 0 0-1.184l-2.5-2a.75.75 0 0 0-1.212.59v4a.75.75 0 0 0 1.212.59Z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        <div className="w-px h-5 bg-stone-200 mx-1" />

        {/* Insert table */}
        <button
          type="button"
          onClick={insertTable}
          className={btnClass(false)}
          title={tx("Insert table", "Insert table")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path
              fillRule="evenodd"
              d="M2 4.25A2.25 2.25 0 0 1 4.25 2h11.5A2.25 2.25 0 0 1 18 4.25v11.5A2.25 2.25 0 0 1 15.75 18H4.25A2.25 2.25 0 0 1 2 15.75V4.25ZM3.5 6.5v3h4.75v-3H3.5Zm6.25 0v3h6.75v-3h-6.75Zm-6.25 4.5v3.25c0 .414.336.75.75.75h4V11h-4.75Zm6.25 0v4h6a.75.75 0 0 0 .75-.75V11h-6.75Z"
              clipRule="evenodd"
            />
          </svg>
        </button>

        {/* Warna border tabel — aktif kalau kursor sedang di dalam sel tabel */}
        <div className="relative group">
          <button
            type="button"
            className={btnClass(
              editor.isActive("tableCell") || editor.isActive("tableHeader"),
            )}
            title={tx("Table border color", "Table border color")}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className="w-3.5 h-3.5"
            >
              <rect x="3" y="3" width="14" height="14" rx="1.5" />
              <line x1="3" y1="10" x2="17" y2="10" />
              <line x1="10" y1="3" x2="10" y2="17" />
            </svg>
          </button>
          <div className="hidden group-hover:flex absolute z-20 top-full left-0 mt-1 p-1.5 bg-white border border-stone-200 rounded-lg shadow-lg gap-1">
            {TABLE_BORDER_COLORS.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setTableBorderColor(c)}
                className="w-5 h-5 rounded-full border border-stone-300"
                style={{ backgroundColor: c }}
                title={c}
              />
            ))}
            <button
              type="button"
              onClick={() => setTableBorderColor(null)}
              className="w-5 h-5 rounded-full border border-stone-300 bg-white flex items-center justify-center text-[8px] font-bold text-stone-400"
              title={tx("Reset border color", "Reset border color")}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Clear formatting */}
        <button
          type="button"
          onClick={() =>
            editor.chain().focus().unsetAllMarks().clearNodes().run()
          }
          className={btnClass(false)}
          title={tx("Clear formatting", "Clear formatting")}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 20 20"
            fill="currentColor"
            className="w-3.5 h-3.5"
          >
            <path d="M3.28 2.22a.75.75 0 0 0-1.06 1.06l3.5 3.5-1.313 5.84a.75.75 0 0 0 1.342.657l1.14-1.802 8.833 8.833a.75.75 0 1 0 1.06-1.06L3.28 2.22Z" />
            <path d="M8.28 3.22a.75.75 0 0 0-1.06 1.06L8.44 5.5H5.75a.75.75 0 0 0 0 1.5h4.19l6.81 6.81a.75.75 0 0 0 1.06-1.06L8.28 3.22Z" />
          </svg>
        </button>
      </div>

      {/* ── EDITOR AREA ── */}
      <div className="p-4 min-h-[280px] max-h-[420px] overflow-y-auto">
        <EditorContent editor={editor} />
      </div>

      <style jsx global>{`
        .rte-content {
          font-size: 13px;
          color: #292524;
          line-height: 1.6;
          /* Eksplisit supaya kursor selalu terlihat, tidak ikut ketiban warna
             teks/background terang dari fitur Text Color/Highlight. */
          caret-color: #292524;
        }
        .rte-content p {
          margin: 0 0 10px 0;
        }
        .rte-content ul,
        .rte-content ol {
          margin: 0 0 10px 0;
          padding-left: 22px;
        }
        .rte-content h1 {
          font-size: 20px;
          font-weight: 800;
          margin: 12px 0 8px;
        }
        .rte-content h2 {
          font-size: 17px;
          font-weight: 800;
          margin: 10px 0 6px;
        }
        .rte-content h3 {
          font-size: 15px;
          font-weight: 700;
          margin: 8px 0 6px;
        }
        .rte-content a {
          color: #005c3a;
          text-decoration: underline;
        }
        .rte-content table {
          border-collapse: collapse;
          margin: 10px 0;
          width: 100%;
        }
        .rte-content table td,
        .rte-content table th {
          border: 1px solid #e7e5e4;
          padding: 6px 8px;
          font-size: 12px;
        }
        .rte-content table th {
          background: #f5f5f4;
          font-weight: 700;
        }
        .rte-content mark {
          border-radius: 2px;
          padding: 0 1px;
        }
      `}</style>

      {/* Dialog "Masukkan URL" pengganti window.prompt() — lihat catatan di setLink di atas */}
      {linkPromptOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label={tx("Insert link", "Insert link")}
          className="fixed inset-0 z-100 bg-stone-900/40 flex items-center justify-center p-4"
          onClick={() => setLinkPromptOpen(false)}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            className="w-full max-w-sm bg-white rounded-2xl shadow-2xl border border-stone-200/80 p-5 text-left"
          >
            <h3 className="font-black text-stone-900 text-sm mb-3">
              {tx("Enter URL", "Enter URL")}
            </h3>
            <input
              type="text"
              autoFocus
              value={linkUrlInput}
              onChange={(e) => setLinkUrlInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmSetLink();
                if (e.key === "Escape") setLinkPromptOpen(false);
              }}
              className="w-full px-3 py-2 rounded-lg border border-stone-250 text-xs font-semibold text-stone-800 outline-none focus:border-petro-green"
              placeholder="https://"
            />
            <div className="flex justify-end gap-2.5 mt-4">
              <button
                type="button"
                onClick={() => setLinkPromptOpen(false)}
                className="px-4 py-2 rounded-lg bg-white border border-stone-200 hover:bg-stone-50 text-stone-700 font-bold text-xs shadow-sm transition-colors cursor-pointer"
              >
                {tx("Cancel", "Cancel")}
              </button>
              <button
                type="button"
                onClick={confirmSetLink}
                className="px-4 py-2 rounded-lg bg-petro-green hover:bg-petro-green-hover text-white font-bold text-xs shadow-sm transition-colors cursor-pointer"
              >
                {tx("Confirm", "Confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
