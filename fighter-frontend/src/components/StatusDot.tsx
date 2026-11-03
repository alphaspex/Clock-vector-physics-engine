import type { ReactNode } from 'react';

interface Props {
  tone: 'good' | 'bad' | 'pending' | 'neutral';
  children: ReactNode;
}

export default function StatusDot({ tone, children }: Props) {
  return (
    <span className={`status-dot status-dot--${tone}`}>
      <span aria-hidden="true" className="status-dot__mark" />
      {children}
    </span>
  );
}
