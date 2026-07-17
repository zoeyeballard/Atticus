// The reading field, closed by a colophon: the quiet last line every printed legal
// document carries. Pages scroll; the colophon sits after the content, not fixed.
export default function MainContent({ children }) {
  return (
    <main className="flex-1 overflow-y-auto flex flex-col">
      <div className="flex-1">{children}</div>
      <footer className="mx-auto w-full max-w-4xl px-8 pb-8 pt-16">
        <div className="border-t border-borderc pt-4 flex items-baseline justify-between gap-6">
          <p className="colophon">
            <a href="/landing.html" className="link-quiet hover:text-accent">Atticus</a> · a
            verification-first drafting instrument · every assertion traceable to its source
          </p>
          <p className="colophon shrink-0">Attorney review required</p>
        </div>
      </footer>
    </main>
  );
}
