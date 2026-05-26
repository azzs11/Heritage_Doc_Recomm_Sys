const SITES = [
  "Ajanta Caves", "Taj Mahal", "Hampi", "Khajuraho", "Elephanta Caves",
  "Fatehpur Sikri", "Agra Fort", "Ellora Caves", "Mahabalipuram",
  "Konark Sun Temple", "Qutb Minar", "Red Fort", "Sanchi Stupa",
  "Pattadakal", "Champaner-Pavagadh", "Rani Ki Vav", "Chola Temples",
];

const SEPARATOR = <span className="mx-4 text-heritage-gold opacity-40">·</span>;

export function HeritageMarquee() {
  const doubled = [...SITES, ...SITES];

  return (
    <div className="overflow-hidden border-y py-3" style={{ borderColor: "var(--border)" }}>
      <div className="marquee-track flex whitespace-nowrap">
        {doubled.map((site, i) => (
          <span key={i} className="inline-flex items-center text-[11px] font-semibold uppercase tracking-[0.15em]"
                style={{ color: "var(--text-subtle)" }}>
            {site}
            {SEPARATOR}
          </span>
        ))}
      </div>
    </div>
  );
}
