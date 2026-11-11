import { Fragment, useMemo, useState, type ReactNode } from 'react'

/**
 * A page's text, readable (Phase 12).
 *
 * Chandra returns its transcription as layout HTML — `<div data-label="Table">`,
 * `<table>`, `<br/>`. Shown raw it is unreadable markup; shown with
 * `dangerouslySetInnerHTML` it would be a hole, because the text came out of a
 * file somebody uploaded and the model will faithfully reproduce whatever was
 * written on the page, `<script>` included.
 *
 * So the HTML is **parsed, never injected**: `DOMParser` builds an inert
 * document (scripts in it never run), and this component walks it and emits
 * React elements from text alone. Only a known set of tags becomes structure —
 * paragraphs, line breaks, lists, tables, emphasis. Everything else contributes
 * its text, except script/style, which contribute nothing. Images become their
 * alt text in brackets.
 *
 * Plain text (a PDF's own text layer) is shown as it is.
 */

const HTML_HINT = /<\/?(div|p|table|tr|td|th|br|h[1-6]|ul|ol|li|span|u|b|strong|em|i|img)\b/i

const BLOCK_LABELS: Record<string, string> = {
  'Page-Header': 'Header',
  'Section-Header': 'Heading',
  'Page-Footer': 'Footer',
  Table: 'Table',
  Image: 'Image',
  Signature: 'Signature',
  Form: 'Form',
}

const DROP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'IFRAME', 'OBJECT', 'EMBED'])

function children(node: Node, key: string): ReactNode[] {
  return Array.from(node.childNodes).map((child, index) => renderNode(child, `${key}.${index}`))
}

function renderNode(node: Node, key: string): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent
  if (node.nodeType !== Node.ELEMENT_NODE) return null

  const element = node as Element
  const tag = element.tagName
  if (DROP.has(tag)) return null

  switch (tag) {
    case 'BR':
      return <br key={key} />
    case 'IMG': {
      const alt = element.getAttribute('alt')?.trim()
      return (
        <span key={key} className="italic text-text-muted">
          [Image{alt ? `: ${alt}` : ''}]
        </span>
      )
    }
    case 'P':
    case 'H1':
    case 'H2':
    case 'H3':
    case 'H4':
    case 'H5':
    case 'H6':
      return (
        <p key={key} className={tag === 'P' ? '' : 'font-semibold text-text-primary'}>
          {children(element, key)}
        </p>
      )
    case 'UL':
    case 'OL': {
      const List = tag === 'UL' ? 'ul' : 'ol'
      return (
        <List key={key} className={tag === 'UL' ? 'list-disc pl-5' : 'list-decimal pl-5'}>
          {children(element, key)}
        </List>
      )
    }
    case 'LI':
      return <li key={key}>{children(element, key)}</li>
    case 'B':
    case 'STRONG':
      return <strong key={key}>{children(element, key)}</strong>
    case 'U':
      return <u key={key}>{children(element, key)}</u>
    case 'I':
    case 'EM':
      return <em key={key}>{children(element, key)}</em>
    case 'TABLE':
      return <OcrTable key={key} table={element} />
    case 'DIV': {
      const label = element.getAttribute('data-label')
      const content = children(element, key)
      if (!label) return <div key={key}>{content}</div>
      const name = BLOCK_LABELS[label]
      return (
        <div key={key} className="space-y-1">
          {name && name !== 'Table' && name !== 'Image' && (
            <span className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{name}</span>
          )}
          <div>{content}</div>
        </div>
      )
    }
    default:
      return <Fragment key={key}>{children(element, key)}</Fragment>
  }
}

function OcrTable({ table }: { table: Element }) {
  const rows = Array.from(table.querySelectorAll('tr'))
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full border-collapse text-caption">
        <tbody>
          {rows.map((row, r) => (
            <tr key={r} className="border-b border-border-subtle">
              {Array.from(row.children).map((cell, c) => {
                const Cell = cell.tagName === 'TH' ? 'th' : 'td'
                return (
                  <Cell
                    key={c}
                    className={`px-2 py-1 text-left align-top ${Cell === 'th' ? 'font-semibold text-text-primary' : ''}`}
                  >
                    {children(cell, `${r}.${c}`)}
                  </Cell>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function looksLikeHtml(text: string): boolean {
  return HTML_HINT.test(text)
}

export function OcrText({ text }: { text: string }) {
  const [raw, setRaw] = useState(false)
  const isHtml = looksLikeHtml(text)

  const rendered = useMemo(() => {
    if (!isHtml) return null
    // An inert document: nothing in it executes, loads or touches this page.
    const doc = new DOMParser().parseFromString(text, 'text/html')
    return children(doc.body, 'ocr')
  }, [text, isHtml])

  if (!isHtml || raw) {
    return (
      <div>
        <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words text-caption text-text-secondary">
          {text}
        </pre>
        {isHtml && (
          <button type="button" className="mt-1 text-caption text-text-muted underline" onClick={() => setRaw(false)}>
            Show readable text
          </button>
        )}
      </div>
    )
  }

  return (
    <div>
      <div className="max-h-96 space-y-2 overflow-auto break-words text-small text-text-secondary">{rendered}</div>
      <button type="button" className="mt-2 text-caption text-text-muted underline" onClick={() => setRaw(true)}>
        Show raw OCR output
      </button>
    </div>
  )
}
