// Display a source document with the cited span highlighted.
export default function SourceViewer({ source, span }) {
  if (!source) return <p className="text-sm text-gray-400">Select a citation to view its source.</p>;
  const idx = span ? source.indexOf(span) : -1;
  if (idx === -1)
    return <pre className="whitespace-pre-wrap text-sm text-gray-700">{source}</pre>;
  return (
    <pre className="whitespace-pre-wrap text-sm text-gray-700">
      {source.slice(0, idx)}
      <mark className="bg-yellow-200">{span}</mark>
      {source.slice(idx + span.length)}
    </pre>
  );
}
