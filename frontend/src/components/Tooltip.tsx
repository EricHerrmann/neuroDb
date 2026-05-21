import { useState } from 'react'
import type { ReactNode } from 'react'

export default function Tooltip({ children, text }: { children: ReactNode; text: string }) {
  const [visible, setVisible] = useState(false)

  return (
    <span
      style={{ position: 'relative', display: 'inline-flex' }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onFocus={() => setVisible(true)}
      onBlur={() => setVisible(false)}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          style={{
            position: 'absolute',
            right: 0,
            top: 'calc(100% + 6px)',
            zIndex: 20,
            width: 260,
            padding: '6px 8px',
            borderRadius: 4,
            background: '#0f172a',
            color: '#fff',
            fontSize: 11,
            lineHeight: 1.35,
            boxShadow: '0 8px 20px rgba(15, 23, 42, 0.2)',
            whiteSpace: 'normal',
          }}
        >
          {text}
        </span>
      )}
    </span>
  )
}
