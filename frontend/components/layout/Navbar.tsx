import Link from "next/link";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Browse Archives" },
  { href: "/saved", label: "My Recommendations" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/evaluation", label: "Evaluation" },
];

export default function Navbar() {
  return (
    <nav className="bg-heritage-dark text-white shadow-md">
      <div className="max-w-6xl mx-auto px-4 flex items-center justify-between h-14">
        <Link href="/" className="font-serif font-bold text-lg tracking-wide hover:text-parchment-200 transition-colors">
          Heritage Recommender
        </Link>
        <ul className="flex items-center gap-1">
          {NAV_LINKS.map((link) => (
            <li key={link.href}>
              <Link
                href={link.href}
                className="px-4 py-2 text-sm font-medium border-r border-heritage-medium last:border-r-0 hover:bg-heritage-medium transition-colors"
              >
                {link.label}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
