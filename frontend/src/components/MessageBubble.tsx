import type { Message } from '../hooks/useChat'

function renderInline(text: string) {
  const parts = text.split(/(`[^`]+`|\[[^\]]+\]\([^)]+\))/g)
  return parts.map((part, index) => {
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index} style={{ background: '#e2e8f0', padding: '1px 3px', borderRadius: 3 }}>{part.slice(1, -1)}</code>
    }
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/)
    if (link) {
      return <a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>
    }
    return part
  })
}

function MarkdownContent({ text }: { text: string }) {
  const lines = text.split('\n')
  const blocks = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) {
      index += 1
      continue
    }
    if (line.startsWith('```')) {
      const code = []
      index += 1
      while (index < lines.length && !lines[index].startsWith('```')) {
        code.push(lines[index])
        index += 1
      }
      index += 1
      blocks.push(
        <pre key={blocks.length} style={{ overflowX: 'auto', background: '#e2e8f0', padding: 8, borderRadius: 4 }}>
          <code>{code.join('\n')}</code>
        </pre>,
      )
      continue
    }
    if (line.includes('|') && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1])) {
      const header = line.split('|').map(cell => cell.trim()).filter(Boolean)
      index += 2
      const rows = []
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        rows.push(lines[index].split('|').map(cell => cell.trim()).filter(Boolean))
        index += 1
      }
      blocks.push(
        <table key={blocks.length} style={{ width: '100%', borderCollapse: 'collapse', margin: '6px 0' }}>
          <thead>
            <tr>{header.map(cell => <th key={cell} style={{ textAlign: 'left', borderBottom: '1px solid #cbd5e1', padding: 3 }}>{cell}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex}>{row.map((cell, cellIndex) => <td key={cellIndex} style={{ borderBottom: '1px solid #e2e8f0', padding: 3 }}>{renderInline(cell)}</td>)}</tr>
            ))}
          </tbody>
        </table>,
      )
      continue
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*[-*]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*]\s+/, ''))
        index += 1
      }
      blocks.push(<ul key={blocks.length} style={{ margin: '4px 0 4px 18px', padding: 0 }}>{items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item)}</li>)}</ul>)
      continue
    }
    if (/^\s*\d+\.\s+/.test(line)) {
      const items = []
      while (index < lines.length && /^\s*\d+\.\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+\.\s+/, ''))
        index += 1
      }
      blocks.push(<ol key={blocks.length} style={{ margin: '4px 0 4px 18px', padding: 0 }}>{items.map((item, itemIndex) => <li key={itemIndex}>{renderInline(item)}</li>)}</ol>)
      continue
    }
    const paragraph = []
    while (
      index < lines.length &&
      lines[index].trim() &&
      !lines[index].startsWith('```') &&
      !/^\s*[-*]\s+/.test(lines[index]) &&
      !/^\s*\d+\.\s+/.test(lines[index])
    ) {
      paragraph.push(lines[index])
      index += 1
    }
    blocks.push(<p key={blocks.length} style={{ margin: '4px 0' }}>{renderInline(paragraph.join(' '))}</p>)
  }
  return <>{blocks}</>
}

function ActivityLog({ message }: { message: Message }) {
  if (!message.activity?.length) return null
  return (
    <details style={{ marginTop: 6, fontSize: 11, color: '#475569' }}>
      <summary style={{ cursor: 'pointer' }}>{message.activity.length} tool call(s)</summary>
      <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 4 }}>
        {message.activity.map(item => (
          <div key={item.id} style={{ border: '1px solid #cbd5e1', borderRadius: 4, padding: 6, background: '#fff' }}>
            <div style={{ fontWeight: 700 }}>{item.toolName} · {item.status}</div>
            {item.input !== undefined && (
              <details>
                <summary style={{ cursor: 'pointer' }}>Input</summary>
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(item.input, null, 2)}</pre>
              </details>
            )}
            {item.result && (
              <details>
                <summary style={{ cursor: 'pointer' }}>Result</summary>
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{item.result}</pre>
              </details>
            )}
          </div>
        ))}
      </div>
    </details>
  )
}

export default function MessageBubble({ message }: { message: Message }) {
  const isUser = message.role === 'user'
  return (
    <div style={{
      marginBottom: 8,
      display: 'flex',
      justifyContent: isUser ? 'flex-end' : 'flex-start',
    }}>
      <div style={{
        maxWidth: '80%',
        padding: '6px 12px',
        borderRadius: 8,
        background: isUser ? '#1e3a8a' : message.error ? '#fee2e2' : '#f1f5f9',
        color: isUser ? '#fff' : message.error ? '#dc2626' : '#0f172a',
        fontSize: 13,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        <MarkdownContent text={message.content} />
        {message.streaming && <span style={{ opacity: 0.5 }}>▋</span>}
        <ActivityLog message={message} />
      </div>
    </div>
  )
}
