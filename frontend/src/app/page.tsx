/** Application shell placeholder. Replaced by the A-10 design-system shell. */
export default function HomePage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center border-b border-[var(--color-border)] px-6">
        <span className="text-lg font-semibold">Numo9</span>
      </header>
      <div className="flex flex-1">
        <nav aria-label="Main" className="w-56 border-e border-[var(--color-border)] p-4" />
        <main className="flex-1 p-6">
          <h1 className="text-2xl font-semibold">Home</h1>
          <p className="mt-2 text-sm text-gray-600">Application shell placeholder.</p>
        </main>
      </div>
    </div>
  );
}
