import Link from "next/link";
import { StatusIndicator } from "@/components/StatusIndicator";

export function SiteHeader() {
  return (
    <header className="site-header">
      <Link className="wordmark" href="/">
        ProductIQ
      </Link>
      <nav aria-label="Primary">
        <Link href="/search">Search</Link>
      </nav>
      <StatusIndicator />
    </header>
  );
}
