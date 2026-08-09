export function SourceChip({sourceRecordId, onClick}: {sourceRecordId: string; onClick?: () => void}) {
  return <button type="button" className="source-chip" data-testid="source-chip" onClick={onClick}>
    <span aria-hidden="true">↗</span>{sourceRecordId}
  </button>;
}
